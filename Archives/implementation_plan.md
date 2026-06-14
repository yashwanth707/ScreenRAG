# Voice-Based Interview Answering — VocalGauge Integration into ScreenRAG

## Goal

Transform ScreenRAG from a **text-typed** interview to a **voice-spoken** interview. When the AI asks a question, the system immediately activates the microphone. The candidate speaks their answer. The backend transcribes the audio, evaluates **what** they said (technical accuracy via RAG) and **how** they said it (confidence, fluency, reading-detection via VocalGauge metrics). The final summary shows a richer, multi-dimensional score per question.

---

## Your Idea — Review & Feedback

Your core concept is strong. Here's my honest assessment:

**What's excellent:**
- Auto-switching to mic after question display — creates real interview pressure. No time to Google.
- Response latency as a scoring signal — genuinely novel. Measuring hesitation before the first word is spoken.
- Reading-vs-natural detection — the highest-value anti-cheat feature. VocalGauge's pitch variance, pacing consistency, and pause analysis give us the raw signals to build this.

**Suggestions I'd add:**

1. **Keep a text fallback (skip-to-type button)**: Not everyone has a working mic or a quiet environment. A small "Type instead" link keeps the app usable. The text path skips voice metrics and only scores content.

2. **Per-question voice metrics, not just overall**: Rather than one aggregate voice score at the end, score each answer independently. This lets the summary show "Question 3: great content but very hesitant" vs "Question 5: confident delivery but shallow answer."

3. **"Thinking time" vs "Speaking time" split**: Track two timestamps — when the question appeared, and when the first speech was detected. The gap is "thinking time." Then separately measure how long they spoke. Both are useful signals.

4. **Don't penalize accent/dialect**: VocalGauge already has language sensitivity. We should carry that over — Indian English, non-native speakers, etc. should not be penalized for pronunciation patterns.

5. **Real-time audio waveform visualization**: While the candidate is speaking, show a simple waveform/volume bar. This gives visual feedback that the mic is working and makes the UI feel alive.

---

## User Review Required

> [!IMPORTANT]
> **Whisper model size**: VocalGauge defaults to `base`. For interview answers (typically 30-120 seconds each), `base` should be fast enough. Do you want `base` or `small` for higher accuracy? (This affects VRAM usage.)

> [!IMPORTANT]
> **LLM for voice analysis**: VocalGauge uses Ollama/LLaMA3 for linguistic analysis (grammar, sentiment, cohesion). ScreenRAG already has Ollama + Gemini fallback. Should we reuse ScreenRAG's existing `llm_client.py` dual-backend for voice analysis too? (Recommended — avoids duplicating LLM infra.)

> [!WARNING]
> **FFmpeg dependency**: VocalGauge requires FFmpeg on the system PATH for audio processing. This is a new system-level dependency for ScreenRAG that wasn't needed before.

## Open Questions

> [!IMPORTANT]
> **Minimum answer duration**: Should we enforce a minimum speaking time (e.g., 3 seconds) before allowing submission? Or allow the candidate to say "I don't know" quickly and move on?

> [!IMPORTANT]
> **Auto-stop recording**: Should recording stop automatically after X seconds of silence (e.g., 3 seconds of silence = auto-submit)? Or should the candidate explicitly click a "Done" button?

> [!IMPORTANT]
> **Text fallback**: Do you want the "Type instead" fallback, or should voice be mandatory?

---

## Proposed Changes

### Component 1: Backend — Audio Processing Service

Port VocalGauge's core audio pipeline into a new service within ScreenRAG.

#### [NEW] [audio_service.py](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/services/audio_service.py)

A new service that combines VocalGauge's `audio_utils.py`, `transcriber.py`, and `scoring.py` into a single, interview-focused module. Responsibilities:

- **Audio validation**: Accept webm/wav from browser MediaRecorder, validate duration (min 3s, max 300s)
- **Preprocessing**: Convert to 16kHz mono WAV via pydub (same as VocalGauge)
- **Transcription**: Whisper STT, returning text + timed segments
- **Audio metrics extraction**: Pause detection (pydub silence analysis), pitch variance (numpy autocorrelation), WPM, filler word counting, pacing consistency — all ported from VocalGauge's `scoring.py` and `audio_utils.py`
- **Response latency**: Calculate time delta between question-asked timestamp and first speech segment start
- **Reading detection heuristic**: Combine pitch variance (monotone = reading), pacing consistency (too uniform = reading), pause pattern (no natural pauses = reading) into a `naturalness_score` (0-10)

Key data returned:
```python
@dataclass
class VoiceAnalysisResult:
    transcript: str              # What they said (feeds into RAG evaluation)
    duration_seconds: float      # How long they spoke
    response_latency: float      # Seconds before first word
    wpm: float                   # Words per minute
    filler_count: int            # Number of filler words
    filler_percentage: float     # Filler words as % of total
    pause_count: int             # Number of significant pauses
    silence_ratio: float         # Ratio of silence to total duration
    pitch_variance: float        # Voice modulation (low = monotone/reading)
    pacing_consistency: float    # Sentence length variance score (0-10)
    naturalness_score: float     # Reading-vs-natural composite (0-10)
    fluency_label: str           # "Slow" | "Optimal" | "Fast"
    confidence_indicators: dict  # All sub-scores for transparency
```

---

### Component 2: Backend — Interview Router Update

#### [MODIFY] [interview.py](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/routers/interview.py)

Add a new endpoint for voice answer submission alongside the existing text endpoint:

```
POST /interview/answer-voice
```

- Accepts `multipart/form-data` with fields: `session_id`, `question_id`, `audio` (file), `question_asked_at` (ISO timestamp from frontend)
- Saves the audio file temporarily
- Calls `audio_service` to process: validate → preprocess → transcribe → extract metrics
- Saves the transcribed text as the answer (reuses existing `save_answer`)
- Saves voice metrics to a new `voice_metrics` DB table
- Returns the transcript + voice metrics to the frontend for display

The existing `POST /interview/answer` (text) endpoint remains unchanged as the fallback path.

---

### Component 3: Backend — Database Schema

#### [MODIFY] [database.py](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/database.py)

Add a new `voice_metrics` table:

```sql
CREATE TABLE IF NOT EXISTS voice_metrics (
    id TEXT PRIMARY KEY,
    answer_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    duration_seconds REAL,
    response_latency REAL,
    wpm REAL,
    filler_count INTEGER DEFAULT 0,
    filler_percentage REAL DEFAULT 0.0,
    pause_count INTEGER DEFAULT 0,
    silence_ratio REAL DEFAULT 0.0,
    pitch_variance REAL DEFAULT 0.0,
    pacing_consistency REAL DEFAULT 0.0,
    naturalness_score REAL DEFAULT 5.0,
    fluency_label TEXT DEFAULT 'Optimal',
    confidence_score REAL DEFAULT 5.0,
    raw_metrics_json TEXT,          -- Full VocalGauge metrics as JSON backup
    FOREIGN KEY (answer_id) REFERENCES answers(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);
```

Also add `answer_mode` column to the `answers` table: `'text'` or `'voice'` to track how each answer was submitted.

Add CRUD functions: `save_voice_metrics()`, `get_voice_metrics_for_question()`, `get_voice_metrics_for_session()`.

---

### Component 4: Backend — Pydantic Models

#### [MODIFY] [models.py](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/models.py)

Add new models:

- `VoiceAnswerResponse` — returned from `POST /interview/answer-voice` with transcript + voice metrics
- `VoiceMetrics` — Pydantic model for voice metric data
- Update `QAPair` to include optional `voice_metrics` and `answer_mode` fields
- Update `SummaryAnalysis` to include `voice_analysis` aggregate scores

---

### Component 5: Backend — Summary Router Enhancement

#### [MODIFY] [summary.py](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/routers/summary.py)

Enhance `_compute_confidence_score()` to incorporate voice metrics when available:

- Replace the current text-length heuristic with VocalGauge's weighted confidence engine
- Add per-question voice breakdown to the summary response
- Add aggregate voice stats: average response latency, average naturalness, filler trend across questions
- Update the LLM summary prompt to mention voice delivery observations

---

### Component 6: Backend — Config & Dependencies

#### [MODIFY] [config.py](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/config.py)

Add new settings:
```python
# --- Voice/Audio Configuration ---
WHISPER_MODEL: str = "base"
MIN_ANSWER_DURATION: float = 3.0   # seconds
MAX_ANSWER_DURATION: float = 300.0 # 5 minutes
SILENCE_AUTO_STOP: float = 3.0    # seconds of silence to auto-stop
```

#### [MODIFY] [requirements.txt](file:///D:/Projects/ScreenRAG/pgagi-interview-system/backend/requirements.txt)

Add VocalGauge dependencies:
```
# Audio processing (VocalGauge integration)
openai-whisper==20240930
pydub==0.25.1
soundfile==0.12.1
torch>=2.0.0
```

> [!NOTE]
> `librosa` is NOT needed. VocalGauge V1 already switched to pure numpy + pydub for pitch extraction, which is much faster and avoids the heavy librosa dependency.

---

### Component 7: Frontend — InterviewChat Voice Mode

#### [MODIFY] [InterviewChat.jsx](file:///D:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/components/InterviewChat/InterviewChat.jsx)

This is the biggest frontend change. The component currently shows a textarea + submit button. We need to add:

1. **Voice recording state machine**: `idle` → `recording` → `processing` → `done`
2. **Auto-start recording**: When `currentQuestion` changes and is not null, automatically request mic permission and start recording via `MediaRecorder API` (format: `audio/webm`)
3. **Real-time waveform**: Use `AnalyserNode` from Web Audio API to render a simple volume bar/waveform while recording
4. **Recording timer**: Show elapsed recording time
5. **Controls**: "Stop & Submit" button (primary action), "Type instead" link (fallback)
6. **Auto-stop on silence**: Use `AnalyserNode` to detect 3 seconds of continuous silence → auto-stop
7. **After recording**: Show the transcribed answer text (returned from backend) with voice metric badges (WPM, naturalness score, filler count)

#### [MODIFY] [InterviewChat.module.css](file:///D:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/components/InterviewChat/InterviewChat.module.css)

Add styles for:
- Recording indicator (pulsing red dot)
- Waveform visualizer container
- Recording timer
- Voice metric badges on the answer bubble
- "Type instead" link style
- Recording/processing state transitions with smooth animations

---

### Component 8: Frontend — InterviewPage Update

#### [MODIFY] [InterviewPage.jsx](file:///D:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/pages/InterviewPage.jsx)

- Track `questionAskedAt` timestamp when a new question is received (for response latency calculation)
- Add `handleSubmitVoiceAnswer(audioBlob)` handler that sends audio to `POST /interview/answer-voice`
- Pass both `onSubmitAnswer` (text) and `onSubmitVoiceAnswer` (audio) to `InterviewChat`

---

### Component 9: Frontend — API Client

#### [MODIFY] [client.js](file:///D:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/api/client.js)

Add new function:
```javascript
export async function submitVoiceAnswer(sessionId, questionId, audioBlob, questionAskedAt) {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('question_id', questionId);
  formData.append('audio', audioBlob, 'answer.webm');
  formData.append('question_asked_at', questionAskedAt);
  
  const response = await api.post('/interview/answer-voice', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // Whisper can take a moment
  });
  return response.data;
}
```

---

### Component 10: Frontend — Summary Page Enhancement

#### [MODIFY] [SessionSummary.jsx](file:///D:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/components/SessionSummary/SessionSummary.jsx) (and CSS)

Enhance the summary display to show voice analytics per question:
- Naturalness score badge per Q&A pair
- Response latency indicator
- Filler word count
- WPM gauge
- Aggregate "Voice Confidence" ring alongside the existing confidence score

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/services/audio_service.py` | **NEW** | Core audio pipeline (port from VocalGauge) |
| `backend/routers/interview.py` | MODIFY | Add `POST /interview/answer-voice` endpoint |
| `backend/database.py` | MODIFY | Add `voice_metrics` table + CRUD |
| `backend/models.py` | MODIFY | Add voice-related Pydantic models |
| `backend/routers/summary.py` | MODIFY | Enhance scoring with voice metrics |
| `backend/config.py` | MODIFY | Add Whisper/audio settings |
| `backend/requirements.txt` | MODIFY | Add whisper, pydub, soundfile, torch |
| `frontend/src/components/InterviewChat/InterviewChat.jsx` | MODIFY | Add voice recording UI |
| `frontend/src/components/InterviewChat/InterviewChat.module.css` | MODIFY | Voice recording styles |
| `frontend/src/pages/InterviewPage.jsx` | MODIFY | Track timestamps, voice submit handler |
| `frontend/src/api/client.js` | MODIFY | Add `submitVoiceAnswer()` |
| `frontend/src/components/SessionSummary/SessionSummary.jsx` | MODIFY | Voice analytics display |

---

## Verification Plan

### Automated Tests
- Port VocalGauge's `test_scoring.py` test structure for the new `audio_service.py`
- Test the `POST /interview/answer-voice` endpoint with a sample WAV file
- Verify `voice_metrics` CRUD operations

### Manual Verification
1. Start the app, upload a resume, begin an interview
2. Verify mic auto-activates when question appears
3. Speak an answer → verify transcript appears correctly
4. Verify voice metrics (WPM, filler count, naturalness) show on the answer bubble
5. Complete all questions → verify summary page shows voice analytics
6. Test "Type instead" fallback works and skips voice metrics
7. Test with different browsers (Chrome, Firefox, Edge — MediaRecorder support)
