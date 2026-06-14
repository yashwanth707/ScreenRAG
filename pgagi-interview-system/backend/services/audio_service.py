"""
ScreenRAG — Audio Service (VocalGauge Integration)

Ported from VocalGauge V1. Provides a complete audio analysis pipeline
for voice-based interview answers:

    1. Audio validation & preprocessing (pydub)
    2. Speech-to-text transcription (Whisper)
    3. Local speech metrics (WPM, fillers, pacing, hesitation)
    4. Audio signal metrics (pauses, pitch variance)
    5. Naturalness scoring (reading detection)
    6. Composite confidence scoring

Usage:
    result = await process_voice_answer(audio_path, question_asked_at)
    # result.transcript  → feeds into existing RAG evaluation
    # result.naturalness_score → reading vs. natural detection
"""

import os
import re
import math
import logging
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_silence, detect_nonsilent

from config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Constants — ported from VocalGauge scoring.py
# ============================================================
SUPPORTED_FORMATS = {"mp3", "wav", "m4a", "ogg", "mp4", "flac", "webm"}

FILLER_WORDS = [
    "um", "uh", "er", "ah", "like", "you know", "basically",
    "actually", "right", "so", "okay", "ok", "hmm", "well",
    "i mean", "sort of", "kind of", "literally", "honestly",
]

OPTIMAL_WPM_LOW = 120
OPTIMAL_WPM_HIGH = 160


# ============================================================
# Data classes
# ============================================================
@dataclass
class VoiceAnalysisResult:
    """Complete analysis result for a voice answer."""
    transcript: str = ""
    language: str = "en"
    duration_seconds: float = 0.0
    response_latency: float = 0.0       # seconds before first word
    wpm: float = 0.0
    word_count: int = 0
    filler_count: int = 0
    filler_percentage: float = 0.0
    filler_words_found: list = field(default_factory=list)
    pause_count: int = 0
    silence_ratio: float = 0.0
    pitch_variance: float = 0.0
    pacing_consistency: float = 0.0     # 0-10, higher = more consistent
    naturalness_score: float = 5.0      # 0-10, higher = more natural
    fluency_label: str = "Optimal"
    confidence_score: float = 5.0       # 0-10, composite voice confidence
    sentence_count: int = 0
    complete_sentences: int = 0
    completeness_ratio: float = 0.0
    hesitation_count: int = 0


# ============================================================
# Whisper transcription — lazy-loaded singleton
# ============================================================
_whisper_model = None


def _get_whisper_model():
    """Lazily load the Whisper model on first use."""
    global _whisper_model
    if _whisper_model is None:
        import whisper
        model_name = settings.WHISPER_MODEL
        logger.info(f"Loading Whisper model: {model_name}")
        _whisper_model = whisper.load_model(model_name)
        logger.info(f"Whisper model '{model_name}' loaded successfully.")
    return _whisper_model


def transcribe_audio(wav_path: str) -> dict:
    """
    Transcribe a WAV file using Whisper.

    Returns:
        Dict with keys: text, language, segments (list of {start, end, text}).
    """
    model = _get_whisper_model()
    logger.info(f"Transcribing: {wav_path}")
    result = model.transcribe(wav_path, fp16=False)

    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in result.get("segments", [])
    ]

    return {
        "text": result["text"].strip(),
        "language": result.get("language", "en"),
        "segments": segments,
    }


# ============================================================
# Audio preprocessing — ported from VocalGauge audio_utils.py
# ============================================================
class AudioProcessingError(Exception):
    """Raised when audio processing fails."""
    pass


def validate_and_preprocess(input_path: str, output_dir: str | None = None) -> tuple[str, float]:
    """
    Validate and convert audio to 16kHz mono WAV for Whisper.

    Args:
        input_path: Path to the uploaded audio file.
        output_dir: Directory for the processed WAV. Defaults to temp dir.

    Returns:
        Tuple of (processed_wav_path, duration_in_seconds).

    Raises:
        AudioProcessingError: If audio is invalid.
    """
    if not os.path.exists(input_path):
        raise AudioProcessingError("Audio file not found.")

    # Determine format from extension
    ext = Path(input_path).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FORMATS:
        raise AudioProcessingError(
            f"Unsupported audio format: .{ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    try:
        audio = AudioSegment.from_file(input_path, format=ext)
    except Exception as e:
        raise AudioProcessingError(f"Failed to load audio file: {e}")

    duration_seconds = len(audio) / 1000.0

    if duration_seconds < settings.MIN_ANSWER_DURATION:
        raise AudioProcessingError(
            f"Audio too short ({duration_seconds:.1f}s). "
            f"Minimum is {settings.MIN_ANSWER_DURATION}s."
        )

    if duration_seconds > settings.MAX_ANSWER_DURATION:
        raise AudioProcessingError(
            f"Audio too long ({duration_seconds:.1f}s). "
            f"Maximum is {settings.MAX_ANSWER_DURATION}s."
        )

    # Check for speech content
    non_silent = detect_nonsilent(audio, min_silence_len=1000, silence_thresh=-45, seek_step=100)
    if not non_silent:
        raise AudioProcessingError("No speech detected in the audio.")

    # Convert to 16kHz mono WAV (Whisper requirement)
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    # Normalize volume to -20 dBFS
    if audio.dBFS != float("-inf"):
        change_in_dbfs = -20.0 - audio.dBFS
        audio = audio.apply_gain(change_in_dbfs)

    # Write processed file
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="screenrag_audio_")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "processed.wav")
    audio.export(output_path, format="wav")

    return output_path, duration_seconds


# ============================================================
# Audio signal metrics — ported from VocalGauge audio_utils.py
# ============================================================
def extract_audio_metrics(file_path: str) -> dict:
    """
    Extract physical audio metrics (pauses and pitch variance).

    Uses pydub for silence detection and numpy autocorrelation for pitch.
    This is the VocalGauge approach — no librosa dependency.

    Returns:
        dict with audio_pause_count, silence_ratio, pitch_variance.
    """
    # 1. Pause detection using pydub
    try:
        audio = AudioSegment.from_file(file_path)
        total_duration_ms = len(audio)

        # Pauses: silence > 500ms below -40 dBFS
        silences = detect_silence(audio, min_silence_len=500, silence_thresh=-40)
        audio_pause_count = len(silences)
        total_silence_ms = sum(end - start for start, end in silences)
        silence_ratio = total_silence_ms / total_duration_ms if total_duration_ms > 0 else 0.0
    except Exception as e:
        logger.warning(f"Pause detection failed: {e}")
        audio_pause_count = 0
        silence_ratio = 0.0
        audio = None

        # 2. Latency (time before first non-silent segment)
        non_silent = detect_nonsilent(audio, min_silence_len=300, silence_thresh=-40)
        audio_latency_ms = non_silent[0][0] if non_silent else 0
        response_latency = audio_latency_ms / 1000.0

        # 3. Pitch variance using numpy autocorrelation (ported from VocalGauge)
        pitch_variance = 0.0
        try:
            if audio is not None:
                samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
                if audio.channels == 2:
                    samples = samples.reshape((-1, 2)).mean(axis=1)

                sr = audio.frame_rate
                frame_length = int(sr * 0.03)
                hop_length = int(sr * 0.015)

                pitches = []
                if len(samples) >= frame_length:
                    for i in range(0, len(samples) - frame_length, hop_length * 3):
                        frame = samples[i:i + frame_length]
                        corr = np.correlate(frame, frame, mode='full')
                        corr = corr[len(corr) // 2:]

                        min_lag = sr // 500
                        max_lag = sr // 50

                        if max_lag > len(corr):
                            max_lag = len(corr)

                        if min_lag < len(corr) and min_lag < max_lag:
                            peak_lag = np.argmax(corr[min_lag:max_lag]) + min_lag
                            pitch = sr / peak_lag
                            if 50 < pitch < 500:
                                pitches.append(pitch)

                if pitches:
                    pitch_variance = float(np.std(pitches))
        except Exception as e:
            logger.warning(f"Pitch extraction failed: {e}")

        return {
            "audio_pause_count": audio_pause_count,
            "silence_ratio": round(silence_ratio, 3),
            "response_latency": round(response_latency, 2),
            "pitch_variance": round(pitch_variance, 2),
        }


# ============================================================
# Text-based speech metrics — ported from VocalGauge scoring.py
# ============================================================
def compute_speech_metrics(transcript: str, duration_seconds: float) -> dict:
    """
    Compute rule-based speech metrics from the transcript text.
    Fast, deterministic, no LLM needed.

    Returns:
        Dict with WPM, filler stats, fluency label, sentence analysis,
        pacing data, and hesitation count.
    """
    words = transcript.lower().split()
    word_count = len(words)

    # Words per minute
    duration_minutes = duration_seconds / 60.0
    wpm = round(word_count / duration_minutes, 2) if duration_minutes > 0 else 0

    # Filler word detection
    transcript_lower = transcript.lower()
    filler_hits = []

    # Multi-word fillers first
    for filler in FILLER_WORDS:
        if " " in filler:
            count = transcript_lower.count(filler)
            filler_hits.extend([filler] * count)

    # Single-word fillers
    single_fillers = {f for f in FILLER_WORDS if " " not in f}
    for word in words:
        cleaned = word.strip(",.?!;:'\"")
        if cleaned in single_fillers:
            filler_hits.append(cleaned)

    filler_count = len(filler_hits)
    filler_percentage = round((filler_count / word_count) * 100, 2) if word_count else 0

    # Fluency label based on WPM
    if wpm < OPTIMAL_WPM_LOW:
        fluency_label = "Slow"
    elif wpm <= OPTIMAL_WPM_HIGH:
        fluency_label = "Optimal"
    else:
        fluency_label = "Fast"

    # Sentence analysis
    sentences = re.split(r'[.!?]+', transcript)
    sentences = [s.strip() for s in sentences if s.strip()]
    total_sentences = len(sentences)

    complete_sentences = sum(1 for s in sentences if len(s.split()) >= 3)
    completeness_ratio = (
        round(complete_sentences / total_sentences, 2)
        if total_sentences > 0 else 0
    )

    # Pacing consistency: variance in words per sentence
    words_per_sentence = [len(s.split()) for s in sentences] if sentences else [0]
    avg_wps = sum(words_per_sentence) / len(words_per_sentence) if words_per_sentence else 0
    pacing_variance = (
        sum((w - avg_wps) ** 2 for w in words_per_sentence) / len(words_per_sentence)
        if words_per_sentence else 0
    )
    pacing_consistency = max(0, 10 - math.sqrt(pacing_variance))

    # Hesitation detection: repeated consecutive words
    hesitation_count = sum(1 for i in range(1, len(words)) if words[i] == words[i - 1])

    unique_fillers = list(set(filler_hits))

    return {
        "wpm": wpm,
        "word_count": word_count,
        "filler_count": filler_count,
        "filler_percentage": filler_percentage,
        "filler_words_found": unique_fillers,
        "fluency_label": fluency_label,
        "sentence_count": total_sentences,
        "complete_sentences": complete_sentences,
        "completeness_ratio": completeness_ratio,
        "pacing_consistency": round(pacing_consistency, 2),
        "hesitation_count": hesitation_count,
    }


# ============================================================
# Naturalness scoring — NEW (reading vs. natural detection)
# ============================================================
def compute_naturalness_score(
    pitch_variance: float,
    pacing_consistency: float,
    silence_ratio: float,
    pause_count: int,
    filler_percentage: float,
    duration_seconds: float,
) -> float:
    """
    Compute a naturalness score (0-10) that estimates whether the speaker
    is answering naturally vs. reading from a prepared source.

    Signals that indicate READING (lower score):
        - Very low pitch variance (monotone delivery)
        - Very high pacing consistency (unnaturally even sentence lengths)
        - Very low silence ratio (no thinking pauses at all)
        - Zero filler words (suspiciously polished)

    Signals that indicate NATURAL speech (higher score):
        - Moderate pitch variance (expressive but not erratic)
        - Some pacing variation (natural thought flow)
        - Occasional pauses (thinking)
        - A few filler words (normal for spontaneous speech)

    Returns:
        Float score 0-10, where 10 = completely natural.
    """
    scores = []

    # 1. Pitch variance (0-10)
    #    Monotone (<10) = reading. Dynamic (15-40) = natural. Erratic (>50) = nervous.
    if pitch_variance < 5:
        pitch_score = 2.0   # Very monotone — likely reading
    elif pitch_variance < 15:
        pitch_score = 5.0   # Somewhat flat
    elif pitch_variance <= 40:
        pitch_score = 9.0   # Natural range
    else:
        pitch_score = 6.0   # Erratic — nervous or excited
    scores.append(("pitch", pitch_score, 0.30))

    # 2. Pacing variation (0-10)
    #    Too consistent (>8) = reading. Moderate (4-7) = natural. Too erratic (<3) = struggling.
    if pacing_consistency > 8.5:
        pacing_score = 3.0  # Suspiciously uniform — reading
    elif pacing_consistency >= 4:
        pacing_score = 9.0  # Natural variation
    else:
        pacing_score = 5.0  # Very erratic — struggling
    scores.append(("pacing", pacing_score, 0.25))

    # 3. Pause pattern (0-10)
    #    No pauses at all = reading. Some pauses = thinking. Too many = struggling.
    if silence_ratio < 0.02:
        pause_score = 3.0   # No pauses — likely reading fluently
    elif silence_ratio <= 0.15:
        pause_score = 9.0   # Natural thinking pauses
    elif silence_ratio <= 0.25:
        pause_score = 6.0   # Quite hesitant
    else:
        pause_score = 3.0   # Excessive silence
    scores.append(("pauses", pause_score, 0.25))

    # 4. Filler word presence (0-10)
    #    Zero fillers in a long answer = suspicious. Some fillers = natural. Too many = unprepared.
    if duration_seconds > 10 and filler_percentage == 0:
        filler_score = 4.0  # Suspiciously clean for a long answer
    elif filler_percentage <= 5:
        filler_score = 9.0  # Normal range
    elif filler_percentage <= 10:
        filler_score = 6.0  # Somewhat disfluent
    else:
        filler_score = 3.0  # Very disfluent
    scores.append(("fillers", filler_score, 0.20))

    # Weighted average
    naturalness = sum(score * weight for _, score, weight in scores)
    return round(min(10, max(0, naturalness)), 2)


# ============================================================
# Composite voice confidence score
# ============================================================
def compute_voice_confidence(
    wpm: float,
    filler_percentage: float,
    silence_ratio: float,
    pause_count: int,
    pitch_variance: float,
    pacing_consistency: float,
    completeness_ratio: float,
) -> float:
    """
    Compute a voice confidence score (0-10) from audio signals.
    Ported from VocalGauge's 8-signal confidence engine,
    adapted for interview context.
    """
    # 1. Filler word penalty (weight: 0.20)
    filler_score = max(0, 10 - filler_percentage)

    # 2. Pause penalty (weight: 0.15)
    pause_score = max(0, 10 - (silence_ratio * 40))

    # 3. Rate deviation (weight: 0.15)
    if OPTIMAL_WPM_LOW <= wpm <= OPTIMAL_WPM_HIGH:
        rate_score = 10.0
    else:
        if wpm < OPTIMAL_WPM_LOW:
            deviation = OPTIMAL_WPM_LOW - wpm
        else:
            deviation = wpm - OPTIMAL_WPM_HIGH
        rate_score = max(0, 10 - (deviation / 10))

    # 4. Pacing consistency (weight: 0.10)
    pacing_score = min(10, pacing_consistency)

    # 5. Sentence completeness (weight: 0.10)
    completeness_score = completeness_ratio * 10

    # 6. Voice modulation (weight: 0.15)
    if pitch_variance == 0:
        modulation_score = 5.0
    else:
        modulation_score = min(10.0, pitch_variance / 4.0)

    # 7. Speaking pace steadiness (weight: 0.15) — new for interviews
    #    Penalize very fast or very slow speaking
    if wpm == 0:
        steadiness_score = 0.0
    elif 100 <= wpm <= 180:
        steadiness_score = 9.0
    else:
        steadiness_score = 5.0

    weights = {
        "filler": 0.20,
        "pause": 0.15,
        "rate": 0.15,
        "pacing": 0.10,
        "completeness": 0.10,
        "modulation": 0.15,
        "steadiness": 0.15,
    }
    scores = {
        "filler": filler_score,
        "pause": pause_score,
        "rate": rate_score,
        "pacing": pacing_score,
        "completeness": completeness_score,
        "modulation": modulation_score,
        "steadiness": steadiness_score,
    }

    confidence = sum(weights[k] * scores[k] for k in weights)
    return round(min(10, max(0, confidence)), 2)


# ============================================================
# Main pipeline — orchestrates the full analysis
# ============================================================
async def process_voice_answer(
    audio_path: str,
    question_asked_at: str | None = None,
) -> VoiceAnalysisResult:
    """
    Full audio analysis pipeline for a voice answer.

    Pipeline:
        1. Validate & preprocess audio → 16kHz mono WAV
        2. Extract audio signal metrics (pauses, pitch)
        3. Transcribe with Whisper
        4. Compute text-based speech metrics
        5. Calculate response latency from timestamps
        6. Compute naturalness score (reading detection)
        7. Compute composite confidence score

    Args:
        audio_path: Path to the uploaded audio file.
        question_asked_at: ISO timestamp of when the question was shown.

    Returns:
        VoiceAnalysisResult with all metrics.

    Raises:
        AudioProcessingError: If audio is invalid or processing fails.
    """
    # Step 1: Validate and preprocess
    processed_path, duration = validate_and_preprocess(audio_path)

    try:
        # Step 2: Extract audio signal metrics
        audio_metrics = extract_audio_metrics(processed_path)

        # Step 3: Transcribe
        transcription = transcribe_audio(processed_path)
        transcript = transcription["text"]
        segments = transcription["segments"]
        language = transcription["language"]

        if not transcript.strip():
            logger.warning("Whisper returned empty transcript")
            return VoiceAnalysisResult(
                transcript="(No speech detected)",
                duration_seconds=duration,
                language=language,
            )

        # Step 4: Compute text-based speech metrics
        speech_metrics = compute_speech_metrics(transcript, duration)

        # Step 5: Calculate response latency
        # Use the latency calculated by pydub's detect_nonsilent which is much more
        # accurate for finding the true start of speech than Whisper's segment timing.
        response_latency = audio_metrics.get("response_latency", 0.0)

        # Step 6: Compute naturalness score
        naturalness = compute_naturalness_score(
            pitch_variance=audio_metrics["pitch_variance"],
            pacing_consistency=speech_metrics["pacing_consistency"],
            silence_ratio=audio_metrics["silence_ratio"],
            pause_count=audio_metrics["audio_pause_count"],
            filler_percentage=speech_metrics["filler_percentage"],
            duration_seconds=duration,
        )

        # Step 7: Compute composite confidence
        confidence = compute_voice_confidence(
            wpm=speech_metrics["wpm"],
            filler_percentage=speech_metrics["filler_percentage"],
            silence_ratio=audio_metrics["silence_ratio"],
            pause_count=audio_metrics["audio_pause_count"],
            pitch_variance=audio_metrics["pitch_variance"],
            pacing_consistency=speech_metrics["pacing_consistency"],
            completeness_ratio=speech_metrics["completeness_ratio"],
        )

        return VoiceAnalysisResult(
            transcript=transcript,
            language=language,
            duration_seconds=round(duration, 2),
            response_latency=response_latency,
            wpm=speech_metrics["wpm"],
            word_count=speech_metrics["word_count"],
            filler_count=speech_metrics["filler_count"],
            filler_percentage=speech_metrics["filler_percentage"],
            filler_words_found=speech_metrics["filler_words_found"],
            pause_count=audio_metrics["audio_pause_count"],
            silence_ratio=audio_metrics["silence_ratio"],
            pitch_variance=audio_metrics["pitch_variance"],
            pacing_consistency=speech_metrics["pacing_consistency"],
            naturalness_score=naturalness,
            fluency_label=speech_metrics["fluency_label"],
            confidence_score=confidence,
            sentence_count=speech_metrics["sentence_count"],
            complete_sentences=speech_metrics["complete_sentences"],
            completeness_ratio=speech_metrics["completeness_ratio"],
            hesitation_count=speech_metrics["hesitation_count"],
        )

    finally:
        # Clean up processed WAV
        try:
            if processed_path != audio_path and os.path.exists(processed_path):
                os.remove(processed_path)
                parent = os.path.dirname(processed_path)
                if parent and os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
        except Exception:
            pass
