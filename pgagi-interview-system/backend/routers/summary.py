"""
ScreenRAG — Summary Router

Generates structured interview summaries using LLM analysis.

Endpoints:
    GET /summary/{session_id} — Generate and return interview summary
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from services.session_manager import get_session, complete_session
from services.llm_client import generate_json
from models import SummaryResponse, SummaryAnalysis, QAPair, VoiceMetrics, VoiceAggregate
import database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summary", tags=["Summary"])


# ---------------------------------------------------------------------------
# LLM prompt for summary generation
# ---------------------------------------------------------------------------
SUMMARY_PROMPT = """Analyze the following technical interview transcript and provide a structured assessment.

Role: {role}
Candidate: {candidate_name}

Interview Transcript:
{transcript}

Provide a structured analysis as JSON ONLY:
{{
    "topics_covered": ["<topic1>", "<topic2>", "..."],
    "strengths": ["<strength1>", "<strength2>", "<strength3>"],
    "areas_for_improvement": ["<area1>", "<area2>"],
    "overall_assessment": "<1-2 sentence summary of candidate performance>"
}}

Rules:
- List 3-5 specific topics that were covered
- Identify 2-4 strengths based on the quality and depth of answers
- Identify 1-3 areas where the candidate could improve
- The overall assessment should be constructive and specific
- Respond with JSON ONLY — no markdown, no explanation"""


SUMMARY_SYSTEM = (
    "You are a senior technical interviewer providing structured feedback. "
    "Be constructive, specific, and fair in your assessment. "
    "Always respond with valid JSON only."
)


# ---------------------------------------------------------------------------
# Confidence score heuristic
# ---------------------------------------------------------------------------
def _compute_confidence_score(
    qa_pairs: list[dict],
    voice_metrics_map: dict[str, dict] | None = None,
) -> float:
    """
    Compute a confidence score (0-10).

    If voice metrics are available (voice mode), uses VocalGauge's
    composite confidence score. Otherwise falls back to the text-length
    heuristic for text-mode answers.
    """
    if not qa_pairs:
        return 0.0

    answered = [qa for qa in qa_pairs if qa.get("answer_text")]
    if not answered:
        return 0.0

    # Check if we have voice metrics
    voice_scores = []
    text_scores = []

    for qa in answered:
        q_id = qa.get("question_id", "")
        vm = voice_metrics_map.get(q_id) if voice_metrics_map else None

        if vm and vm.get("confidence_score") is not None:
            voice_scores.append(vm["confidence_score"])
        else:
            # Text-mode fallback: simple heuristic
            words = len(qa["answer_text"].split())
            length_score = min(4.0, words / 50.0 * 4.0)
            text_scores.append(length_score + 3.0)  # baseline

    # Weighted combination: voice metrics are more reliable
    all_scores = voice_scores + text_scores
    if not all_scores:
        return 0.0

    avg = sum(all_scores) / len(all_scores)
    return round(min(10.0, avg), 1)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.get("/{session_id}", response_model=SummaryResponse)
async def get_summary(session_id: str):
    """
    Generate a structured summary of an interview session.
    
    Pipeline:
        1. Fetch all Q&A pairs
        2. Build interview transcript for LLM
        3. Generate structured analysis via LLM
        4. Compute confidence score heuristic
        5. Mark session as completed
        6. Return summary
    """
    # Fetch session
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    qa_pairs_raw = session.get("qa_pairs", [])
    if not qa_pairs_raw:
        raise HTTPException(
            status_code=400,
            detail="No questions found for this session.",
        )

    # Fetch voice metrics for all questions in the session
    voice_metrics_list = await database.get_voice_metrics_for_session(session_id)
    voice_metrics_map = {
        vm["question_id"]: vm for vm in voice_metrics_list
    }

    # Build transcript for LLM
    role_display = {
        "ai_ml": "AI/ML Engineer",
        "backend": "Backend Engineer",
        "data_science": "Data Scientist",
    }
    role = session.get("role", "ai_ml")
    candidate_name = session.get("candidate_name", "Unknown Candidate")

    transcript_parts = []
    for qa in qa_pairs_raw:
        q_num = qa.get("question_number", "?")
        q_text = qa.get("question_text", "")
        a_text = qa.get("answer_text", "(No answer provided)")
        mode = qa.get("answer_mode", "text")
        mode_label = " [spoken]" if mode == "voice" else ""
        transcript_parts.append(
            f"Q{q_num} [{qa.get('topic', 'general')}]: {q_text}\n"
            f"A{q_num}{mode_label}: {a_text}"
        )
    transcript = "\n\n".join(transcript_parts)

    # Generate LLM analysis
    prompt = SUMMARY_PROMPT.format(
        role=role_display.get(role, role),
        candidate_name=candidate_name,
        transcript=transcript,
    )

    try:
        analysis_data = await generate_json(prompt, system=SUMMARY_SYSTEM, retries=1)
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        analysis_data = {
            "topics_covered": list({qa.get("topic", "general") for qa in qa_pairs_raw if qa.get("topic")}),
            "strengths": ["Completed the interview"],
            "areas_for_improvement": ["LLM analysis unavailable"],
            "overall_assessment": "Interview completed. Detailed analysis unavailable.",
        }

    # Compute confidence score (uses voice metrics when available)
    confidence = _compute_confidence_score(qa_pairs_raw, voice_metrics_map)

    # Build response Q&A pairs with voice metrics attached
    qa_response = []
    for qa in qa_pairs_raw:
        q_id = qa.get("question_id", "")
        vm = voice_metrics_map.get(q_id)

        voice_data = None
        if vm:
            voice_data = VoiceMetrics(
                duration_seconds=vm.get("duration_seconds", 0),
                response_latency=vm.get("response_latency", 0),
                wpm=vm.get("wpm", 0),
                filler_count=vm.get("filler_count", 0),
                filler_percentage=vm.get("filler_percentage", 0),
                pause_count=vm.get("pause_count", 0),
                silence_ratio=vm.get("silence_ratio", 0),
                pitch_variance=vm.get("pitch_variance", 0),
                pacing_consistency=vm.get("pacing_consistency", 0),
                naturalness_score=vm.get("naturalness_score", 5),
                fluency_label=vm.get("fluency_label", "Optimal"),
                confidence_score=vm.get("confidence_score", 5),
            )

        qa_response.append(QAPair(
            question_id=q_id,
            question_number=qa.get("question_number", 0),
            question_text=qa.get("question_text", ""),
            topic=qa.get("topic"),
            difficulty=qa.get("difficulty"),
            answer_text=qa.get("answer_text"),
            answer_mode=qa.get("answer_mode", "text"),
            answered_at=qa.get("answered_at"),
            voice_metrics=voice_data,
        ))

    # Count answers
    answers_given = sum(1 for qa in qa_pairs_raw if qa.get("answer_text"))

    # Compute voice aggregate stats
    voice_aggregate = None
    if voice_metrics_list:
        vm_count = len(voice_metrics_list)
        voice_aggregate = VoiceAggregate(
            avg_response_latency=round(
                sum(vm.get("response_latency", 0) for vm in voice_metrics_list) / vm_count, 2
            ),
            avg_naturalness=round(
                sum(vm.get("naturalness_score", 0) for vm in voice_metrics_list) / vm_count, 2
            ),
            avg_wpm=round(
                sum(vm.get("wpm", 0) for vm in voice_metrics_list) / vm_count, 1
            ),
            total_fillers=sum(vm.get("filler_count", 0) for vm in voice_metrics_list),
            avg_confidence=round(
                sum(vm.get("confidence_score", 0) for vm in voice_metrics_list) / vm_count, 2
            ),
            voice_answers_count=vm_count,
        )

    # Mark session as completed
    await complete_session(session_id)

    return SummaryResponse(
        session_id=session_id,
        candidate_name=candidate_name,
        role=role,
        questions_asked=len(qa_pairs_raw),
        answers_given=answers_given,
        qa_pairs=qa_response,
        analysis=SummaryAnalysis(
            topics_covered=analysis_data.get("topics_covered", []),
            strengths=analysis_data.get("strengths", []),
            areas_for_improvement=analysis_data.get("areas_for_improvement", []),
            overall_assessment=analysis_data.get("overall_assessment", ""),
            confidence_score=confidence,
            voice_aggregate=voice_aggregate,
        ),
    )
