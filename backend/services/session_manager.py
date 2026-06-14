"""
Manages interview session lifecycle and state transitions.
Coordinates between database layer and business logic.
"""

import uuid
import logging
from typing import Any

import database
from config import settings

logger = logging.getLogger(__name__)


# Session lifecycle
async def start_session(role: str, resume_data: dict[str, Any]) -> str:
    """Create a new interview session."""
    session_id = str(uuid.uuid4())

    await database.create_session(
        session_id=session_id,
        candidate_name=resume_data.get("name", "Unknown Candidate"),
        role=role,
        resume_text=resume_data.get("raw_text", ""),
        resume_skills=resume_data.get("skills", []),
    )

    logger.info(
        f"Session started: {session_id} "
        f"(role={role}, candidate={resume_data.get('name', 'Unknown')})"
    )
    return session_id


async def get_session(session_id: str) -> dict[str, Any] | None:
    """Fetch a complete session with all Q&A data."""
    session = await database.get_session(session_id)
    if not session:
        return None

    # Attach Q&A pairs
    qa_pairs = await database.get_session_qa_pairs(session_id)
    session["qa_pairs"] = qa_pairs
    session["questions_count"] = len(qa_pairs)

    return session


async def get_session_data_for_generation(session_id: str) -> dict[str, Any] | None:
    """Fetch session data formatted for question generation."""
    session = await database.get_session(session_id)
    if not session:
        return None

    skills = session.get("resume_skills", [])
    if isinstance(skills, str):
        import json
        try:
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            skills = []

    return {
        "role": session.get("role", "ai_ml"),
        "skills": skills,
        "experience_level": _infer_experience_from_session(session),
        "resume_text": session.get("resume_text", ""),
    }


def _infer_experience_from_session(session: dict) -> str:
    """
    Infer experience level from session data.
    The resume parser stores this in the skills JSON or we default to 'mid'.
    """
    # Try to get from resume_text context clues
    resume = session.get("resume_text", "").lower()
    if any(word in resume for word in ["senior", "lead", "principal", "staff", "10+ years", "8+ years"]):
        return "senior"
    if any(word in resume for word in ["intern", "fresher", "entry level", "student", "graduate"]):
        return "junior"
    return "mid"


# Question management
async def save_question(session_id: str, question_data: dict[str, Any]) -> str:
    """Save a generated question to the database."""
    question_id = str(uuid.uuid4())
    question_count = await database.get_question_count(session_id)

    await database.save_question(
        question_id=question_id,
        session_id=session_id,
        question_number=question_count + 1,
        question_text=question_data.get("question_text", ""),
        rag_context=question_data.get("rag_context"),
        topic=question_data.get("topic"),
        difficulty=question_data.get("difficulty"),
    )

    logger.info(
        f"Question saved: {question_id} "
        f"(session={session_id}, num={question_count + 1}, "
        f"topic={question_data.get('topic')})"
    )
    return question_id


# Answer management
async def save_answer(
    session_id: str,
    question_id: str,
    answer_text: str,
) -> str:
    """Save a candidate's answer to a question."""
    answer_id = str(uuid.uuid4())

    await database.save_answer(
        answer_id=answer_id,
        session_id=session_id,
        question_id=question_id,
        answer_text=answer_text,
    )

    logger.info(f"Answer saved: {answer_id} (question={question_id})")
    return answer_id


# Session completion
async def complete_session(session_id: str) -> None:
    """Mark a session as completed."""
    await database.update_session_status(session_id, "completed")
    logger.info(f"Session completed: {session_id}")


async def is_session_complete(session_id: str) -> bool:
    """Check if a session has reached the maximum number of questions."""
    question_count = await database.get_question_count(session_id)
    return question_count >= settings.MAX_QUESTIONS


# Previous Q&A retrieval
async def get_previous_qa(session_id: str) -> list[dict]:
    """Get all previous Q&A pairs formatted for the question generator."""
    qa_pairs = await database.get_session_qa_pairs(session_id)
    
    return [
        {
            "question": qa.get("question_text", ""),
            "answer": qa.get("answer_text", ""),
            "topic": qa.get("topic", ""),
        }
        for qa in qa_pairs
    ]
