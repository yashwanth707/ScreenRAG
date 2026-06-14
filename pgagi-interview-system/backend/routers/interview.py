"""
Interview router handling question generation and answer submission.
"""

import logging
import json
import os
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from config import settings
from services.session_manager import (
    get_session_data_for_generation,
    get_previous_qa,
    save_question,
    save_answer as save_answer_service,
    is_session_complete,
)
from services.question_generator import generate_question
from models import (
    NextQuestionRequest,
    AnswerRequest,
    QuestionResponse,
    AnswerResponse,
    VoiceAnswerResponse,
    VoiceMetrics,
)
import database
from services.audio_service import process_voice_answer, AudioProcessingError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview", tags=["Interview"])


@router.post("/next-question", response_model=QuestionResponse)
async def next_question(request: NextQuestionRequest):
    """Generate the next interview question for a session."""
    session_id = request.session_id

    session_data = await get_session_data_for_generation(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    if await is_session_complete(session_id):
        question_count = await database.get_question_count(session_id)
        return QuestionResponse(
            question_id="",
            question_text="",
            question_number=question_count,
            total_questions=settings.MAX_QUESTIONS,
            done=True,
        )

    previous_qa = await get_previous_qa(session_id)
    question_num = len(previous_qa) + 1

    try:
        question_data = await generate_question(
            session_data=session_data,
            previous_qa=previous_qa,
            question_num=question_num,
            max_questions=settings.MAX_QUESTIONS,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Question generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate question: {str(e)}",
        )

    question_id = await save_question(session_id, question_data)

    return QuestionResponse(
        question_id=question_id,
        question_text=question_data["question_text"],
        question_number=question_num,
        total_questions=settings.MAX_QUESTIONS,
        topic=question_data.get("topic"),
        difficulty=question_data.get("difficulty"),
        done=False,
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(request: AnswerRequest):
    """Submit an answer to an interview question."""
    session = await database.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found.",
        )

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=400,
            detail="This interview session has already been completed.",
        )

    # Validate question exists and belongs to this session
    question = await database.fetch_one(
        "SELECT * FROM questions WHERE id = ? AND session_id = ?",
        (request.question_id, request.session_id),
    )
    if not question:
        raise HTTPException(
            status_code=404,
            detail=f"Question '{request.question_id}' not found in session '{request.session_id}'.",
        )

    existing_answer = await database.get_answer_for_question(request.question_id)
    if existing_answer:
        raise HTTPException(
            status_code=400,
            detail="This question has already been answered.",
        )

    await save_answer_service(
        session_id=request.session_id,
        question_id=request.question_id,
        answer_text=request.answer_text,
    )

    return AnswerResponse(
        saved=True,
        question_number=question.get("question_number", 0),
    )


@router.post("/answer-voice", response_model=VoiceAnswerResponse)
async def submit_voice_answer(
    session_id: str = Form(...),
    question_id: str = Form(...),
    audio: UploadFile = File(...),
    question_asked_at: str = Form(""),
):
    """Submit a voice answer to an interview question."""
    session = await database.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=400,
            detail="This interview session has already been completed.",
        )

    # Validate question exists and belongs to this session
    question = await database.fetch_one(
        "SELECT * FROM questions WHERE id = ? AND session_id = ?",
        (question_id, session_id),
    )
    if not question:
        raise HTTPException(
            status_code=404,
            detail=f"Question '{question_id}' not found in session '{session_id}'.",
        )

    existing_answer = await database.get_answer_for_question(question_id)
    if existing_answer:
        raise HTTPException(
            status_code=400,
            detail="This question has already been answered.",
        )

    from config import settings
    os.makedirs(settings.AUDIO_UPLOAD_DIR, exist_ok=True)

    audio_filename = f"{session_id}_{question_id}_{uuid.uuid4().hex[:8]}"
    ext = ".webm"
    if audio.filename and "." in audio.filename:
        ext = "." + audio.filename.rsplit(".", 1)[-1].lower()
    audio_path = os.path.join(settings.AUDIO_UPLOAD_DIR, audio_filename + ext)

    try:
        content = await audio.read()
        with open(audio_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {e}")

    try:
        result = await process_voice_answer(
            audio_path=audio_path,
            question_asked_at=question_asked_at or None,
        )
    except AudioProcessingError as e:
        # Clean up on failure
        if os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        logger.error(f"Voice processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {e}")

    answer_text = result.transcript or "(No speech detected)"

    answer_id = str(uuid.uuid4())
    await database.save_answer(
        answer_id=answer_id,
        session_id=session_id,
        question_id=question_id,
        answer_text=answer_text,
        answer_mode="voice",
    )

    metrics_id = str(uuid.uuid4())
    await database.save_voice_metrics(
        metrics_id=metrics_id,
        answer_id=answer_id,
        session_id=session_id,
        question_id=question_id,
        duration_seconds=result.duration_seconds,
        response_latency=result.response_latency,
        wpm=result.wpm,
        filler_count=result.filler_count,
        filler_percentage=result.filler_percentage,
        pause_count=result.pause_count,
        silence_ratio=result.silence_ratio,
        pitch_variance=result.pitch_variance,
        pacing_consistency=result.pacing_consistency,
        naturalness_score=result.naturalness_score,
        fluency_label=result.fluency_label,
        confidence_score=result.confidence_score,
        raw_metrics_json=json.dumps({
            "word_count": result.word_count,
            "filler_words_found": result.filler_words_found,
            "sentence_count": result.sentence_count,
            "complete_sentences": result.complete_sentences,
            "completeness_ratio": result.completeness_ratio,
            "hesitation_count": result.hesitation_count,
            "language": result.language,
        }),
    )

    logger.info(
        f"Voice answer saved: question={question_id}, "
        f"transcript_len={len(answer_text)}, "
        f"naturalness={result.naturalness_score}, "
        f"confidence={result.confidence_score}"
    )

    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        pass

    return VoiceAnswerResponse(
        saved=True,
        question_number=question.get("question_number", 0),
        transcript=answer_text,
        voice_metrics=VoiceMetrics(
            duration_seconds=result.duration_seconds,
            response_latency=result.response_latency,
            wpm=result.wpm,
            filler_count=result.filler_count,
            filler_percentage=result.filler_percentage,
            pause_count=result.pause_count,
            silence_ratio=result.silence_ratio,
            pitch_variance=result.pitch_variance,
            pacing_consistency=result.pacing_consistency,
            naturalness_score=result.naturalness_score,
            fluency_label=result.fluency_label,
            confidence_score=result.confidence_score,
        ),
    )
