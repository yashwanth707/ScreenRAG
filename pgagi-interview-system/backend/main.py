"""
ScreenRAG — FastAPI Application Entry Point

AI-Powered Technical Interview Platform

Routes:
    POST /resume/upload              → Upload resume + create session
    GET  /session/{session_id}       → Get session with Q&A data
    POST /interview/next-question    → Generate next interview question
    POST /interview/answer           → Submit answer to a question
    GET  /summary/{session_id}       → Generate interview summary
    GET  /health                     → System health check

Run with:
    uvicorn main:app --reload --port 8000
"""

import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from config import settings
from models import HealthResponse
from services.llm_client import check_ollama_health
from services.rag_engine import check_chroma_health
from routers import resume, session, interview, summary

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("screenrag")


# ---------------------------------------------------------------------------
# Application lifespan — startup/shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    
    Startup:
        - Create required directories (uploads, data, chroma_store)
        - Initialize SQLite database tables
    
    Shutdown:
        - Log shutdown (cleanup handled by aiosqlite)
    """
    # Startup
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.AUDIO_UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

    await database.init_db()
    logger.info("ScreenRAG backend started successfully.")
    logger.info(f"  Ollama:    {settings.OLLAMA_BASE_URL} (model: {settings.OLLAMA_MODEL})")
    logger.info(f"  ChromaDB:  {settings.CHROMA_PERSIST_DIR}")
    logger.info(f"  Database:  {settings.DB_PATH}")
    logger.info(f"  Uploads:   {settings.UPLOAD_DIR}")
    logger.info(f"  Questions: {settings.MAX_QUESTIONS} per session")

    yield

    # Shutdown
    logger.info("ScreenRAG backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ScreenRAG API",
    description=(
        "AI-Powered Technical Interview Platform — "
        "Resume parsing, RAG-grounded question generation, "
        "interactive interviews, and structured summaries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow Vite dev server and common dev origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(resume.router)
app.include_router(session.router)
app.include_router(interview.router)
app.include_router(summary.router)


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Check system health: Ollama, ChromaDB, and SQLite status.
    """
    # Check Ollama
    ollama_status = await check_ollama_health()
    ollama_ok = ollama_status.get("reachable", False)

    # Check ChromaDB
    chroma_status = check_chroma_health()
    chroma_ok = chroma_status.get("available", False)

    # Check SQLite
    db_ok = False
    try:
        result = await database.fetch_one("SELECT 1 as ok")
        db_ok = result is not None
    except Exception:
        pass

    overall = "ok" if (ollama_ok or True) and db_ok else "degraded"

    return HealthResponse(
        status=overall,
        ollama=ollama_ok,
        chroma=chroma_ok,
        db=db_ok,
    )


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    """API root — basic info."""
    return {
        "name": "ScreenRAG API",
        "version": "1.0.0",
        "description": "AI-Powered Technical Interview Platform",
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Direct run support
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
