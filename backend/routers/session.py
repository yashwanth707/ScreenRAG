"""
Session router handling session retrieval.
"""

import logging

from fastapi import APIRouter, HTTPException

from services.session_manager import get_session
from models import SessionResponse, QAPair

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["Session"])


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_endpoint(session_id: str):
    """Retrieve a complete session by ID."""
    session = await get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    qa_pairs = [
        QAPair(
            question_id=qa.get("question_id", ""),
            question_number=qa.get("question_number", 0),
            question_text=qa.get("question_text", ""),
            topic=qa.get("topic"),
            difficulty=qa.get("difficulty"),
            answer_text=qa.get("answer_text"),
            answered_at=qa.get("answered_at"),
        )
        for qa in session.get("qa_pairs", [])
    ]

    return SessionResponse(
        session_id=session["id"],
        candidate_name=session.get("candidate_name"),
        role=session["role"],
        status=session.get("status", "active"),
        questions_count=len(qa_pairs),
        created_at=session.get("created_at"),
        qa_pairs=qa_pairs,
    )
