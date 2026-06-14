"""
ScreenRAG — Resume Router

Handles PDF resume upload, parsing, and session creation.

Endpoints:
    POST /resume/upload — Upload resume PDF + select role → creates session
"""

import os
import uuid
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from config import settings
from services.resume_parser import parse_resume_pdf
from services.session_manager import start_session
from models import ResumeUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resume", tags=["Resume"])


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file"),
    role: str = Form(..., description="Target role: ai_ml, backend, or data_science"),
):
    """
    Upload a candidate's resume and create an interview session.
    
    Pipeline:
        1. Validate file (must be PDF)
        2. Save to uploads/ directory
        3. Parse with pdfplumber + LLM
        4. Create session in database
        5. Delete the uploaded file (privacy)
        6. Return session info
    """
    # Validate role
    valid_roles = {"ai_ml", "backend", "data_science"}
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}",
        )

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # Save file to uploads directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Resume saved: {file_path} ({len(content)} bytes)")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {str(e)}",
        )

    # Parse the resume
    try:
        resume_data = await parse_resume_pdf(file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Resume parsing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}",
        )
    finally:
        # Always delete the uploaded file after parsing (privacy)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Uploaded file deleted: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to delete uploaded file: {e}")

    # Create session
    try:
        session_id = await start_session(role, resume_data)
    except Exception as e:
        logger.error(f"Session creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}",
        )

    return ResumeUploadResponse(
        session_id=session_id,
        candidate_name=resume_data.get("name", "Unknown Candidate"),
        skills=resume_data.get("skills", []),
        experience_level=resume_data.get("experience_level", "mid"),
        role=role,
    )
