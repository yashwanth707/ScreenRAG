"""
SQLite database layer for persistent storage of sessions, questions, and answers.
Uses aiosqlite for async operations.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)


def _get_db_path() -> str:
    db_path = settings.DB_PATH
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return db_path


DB_PATH = _get_db_path()


# Schema definitions
SCHEMA_SQL = """
-- Sessions table: one row per candidate interview
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,                    -- UUID
    candidate_name TEXT,
    role TEXT NOT NULL,                     -- 'ai_ml' | 'backend' | 'data_science'
    resume_text TEXT,                       -- Full extracted resume text
    resume_skills TEXT,                     -- JSON array of extracted skills
    status TEXT DEFAULT 'active',           -- 'active' | 'completed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Questions table: generated interview questions
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,                    -- UUID
    session_id TEXT NOT NULL,
    question_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    rag_context TEXT,                       -- Retrieved chunk used to generate question
    topic TEXT,                             -- e.g. 'decision_trees', 'neural_networks'
    difficulty TEXT,                        -- 'basic' | 'intermediate' | 'advanced'
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Answers table: candidate responses
CREATE TABLE IF NOT EXISTS answers (
    id TEXT PRIMARY KEY,                    -- UUID
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    answer_mode TEXT DEFAULT 'text',         -- 'text' | 'voice'
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

-- Voice metrics table: per-answer audio analytics (VocalGauge integration)
CREATE TABLE IF NOT EXISTS voice_metrics (
    id TEXT PRIMARY KEY,                    -- UUID
    answer_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    duration_seconds REAL,
    response_latency REAL,                  -- seconds before first word
    wpm REAL,
    filler_count INTEGER DEFAULT 0,
    filler_percentage REAL DEFAULT 0.0,
    pause_count INTEGER DEFAULT 0,
    silence_ratio REAL DEFAULT 0.0,
    pitch_variance REAL DEFAULT 0.0,
    pacing_consistency REAL DEFAULT 0.0,
    naturalness_score REAL DEFAULT 5.0,     -- reading vs. natural (0-10)
    fluency_label TEXT DEFAULT 'Optimal',
    confidence_score REAL DEFAULT 5.0,
    raw_metrics_json TEXT,                  -- Full metrics as JSON backup
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (answer_id) REFERENCES answers(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);
"""



async def init_db() -> None:
    """Initialize the database tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    logger.info(f"Database initialized at {DB_PATH}")


# Generic query helpers
async def execute(query: str, params: tuple = ()) -> None:
    """Execute a write query (INSERT, UPDATE, DELETE)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


async def fetch_one(query: str, params: tuple = ()) -> dict | None:
    """Fetch a single row as a dict. Returns None if no match."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    """Fetch all matching rows as a list of dictionaries."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# Session CRUD
async def create_session(
    session_id: str,
    candidate_name: str,
    role: str,
    resume_text: str,
    resume_skills: list[str],
) -> None:
    """Create a new interview session record."""
    await execute(
        """INSERT INTO sessions (id, candidate_name, role, resume_text, resume_skills, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            candidate_name,
            role,
            resume_text,
            json.dumps(resume_skills),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    logger.info(f"Session created: {session_id} (role={role}, candidate={candidate_name})")


async def get_session(session_id: str) -> dict | None:
    """Fetch a session by ID, parsing JSON fields."""
    row = await fetch_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if row and row.get("resume_skills"):
        try:
            row["resume_skills"] = json.loads(row["resume_skills"])
        except json.JSONDecodeError:
            row["resume_skills"] = []
    return row


async def update_session_status(session_id: str, status: str) -> None:
    """Update session status ('active' → 'completed')."""
    completed_at = datetime.now(timezone.utc).isoformat() if status == "completed" else None
    await execute(
        "UPDATE sessions SET status = ?, completed_at = ? WHERE id = ?",
        (status, completed_at, session_id),
    )


# Question CRUD
async def save_question(
    question_id: str,
    session_id: str,
    question_number: int,
    question_text: str,
    rag_context: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
) -> None:
    """Insert a generated interview question."""
    await execute(
        """INSERT INTO questions (id, session_id, question_number, question_text,
                                  rag_context, topic, difficulty)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (question_id, session_id, question_number, question_text, rag_context, topic, difficulty),
    )


async def get_questions_for_session(session_id: str) -> list[dict]:
    """Fetch all questions for a session, ordered by question_number."""
    return await fetch_all(
        "SELECT * FROM questions WHERE session_id = ? ORDER BY question_number",
        (session_id,),
    )


async def get_question_count(session_id: str) -> int:
    """Count questions generated for a session."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM questions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# Answer CRUD
async def save_answer(
    answer_id: str,
    session_id: str,
    question_id: str,
    answer_text: str,
    answer_mode: str = "text",
) -> None:
    """Insert a candidate's answer to a question."""
    await execute(
        """INSERT INTO answers (id, session_id, question_id, answer_text, answer_mode)
           VALUES (?, ?, ?, ?, ?)""",
        (answer_id, session_id, question_id, answer_text, answer_mode),
    )


async def get_answers_for_session(session_id: str) -> list[dict]:
    """Fetch all answers for a session, ordered by answered_at."""
    return await fetch_all(
        "SELECT * FROM answers WHERE session_id = ? ORDER BY answered_at",
        (session_id,),
    )


async def get_answer_for_question(question_id: str) -> dict | None:
    """Fetch the answer for a specific question."""
    return await fetch_one(
        "SELECT * FROM answers WHERE question_id = ?", (question_id,)
    )


# Composite queries
async def get_session_qa_pairs(session_id: str) -> list[dict]:
    """Fetch all question-answer pairs for a session as a merged dict."""
    return await fetch_all(
        """SELECT q.id as question_id, q.question_number, q.question_text,
                  q.topic, q.difficulty, q.rag_context,
                  a.answer_text, a.answer_mode, a.answered_at
           FROM questions q
           LEFT JOIN answers a ON q.id = a.question_id
           WHERE q.session_id = ?
           ORDER BY q.question_number""",
        (session_id,),
    )


# Voice Metrics CRUD
async def save_voice_metrics(
    metrics_id: str,
    answer_id: str,
    session_id: str,
    question_id: str,
    duration_seconds: float,
    response_latency: float,
    wpm: float,
    filler_count: int,
    filler_percentage: float,
    pause_count: int,
    silence_ratio: float,
    pitch_variance: float,
    pacing_consistency: float,
    naturalness_score: float,
    fluency_label: str,
    confidence_score: float,
    raw_metrics_json: str = "",
) -> None:
    """Insert voice metrics for an answer."""
    await execute(
        """INSERT INTO voice_metrics (
               id, answer_id, session_id, question_id,
               duration_seconds, response_latency, wpm,
               filler_count, filler_percentage,
               pause_count, silence_ratio, pitch_variance,
               pacing_consistency, naturalness_score,
               fluency_label, confidence_score, raw_metrics_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            metrics_id, answer_id, session_id, question_id,
            duration_seconds, response_latency, wpm,
            filler_count, filler_percentage,
            pause_count, silence_ratio, pitch_variance,
            pacing_consistency, naturalness_score,
            fluency_label, confidence_score, raw_metrics_json,
        ),
    )


async def get_voice_metrics_for_question(question_id: str) -> dict | None:
    """Fetch voice metrics for a specific question's answer."""
    return await fetch_one(
        "SELECT * FROM voice_metrics WHERE question_id = ?", (question_id,)
    )


async def get_voice_metrics_for_session(session_id: str) -> list[dict]:
    """Fetch all voice metrics for a session, ordered by creation."""
    return await fetch_all(
        "SELECT * FROM voice_metrics WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    )
