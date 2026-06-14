"""Pydantic request/response models for all API endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


# Request models
class NextQuestionRequest(BaseModel):
    """Request body for POST /interview/next-question."""
    session_id: str = Field(..., description="UUID of the active session")


class AnswerRequest(BaseModel):
    """Request body for POST /interview/answer."""
    session_id: str = Field(..., description="UUID of the active session")
    question_id: str = Field(..., description="UUID of the question being answered")
    answer_text: str = Field(..., min_length=1, description="Candidate's answer text")


# Voice metrics
class VoiceMetrics(BaseModel):
    """Per-answer voice analytics from the audio processing pipeline."""
    duration_seconds: float = Field(0.0, description="How long the candidate spoke")
    response_latency: float = Field(0.0, description="Seconds before first word")
    wpm: float = Field(0.0, description="Words per minute")
    filler_count: int = Field(0, description="Number of filler words detected")
    filler_percentage: float = Field(0.0, description="Filler words as % of total")
    pause_count: int = Field(0, description="Number of significant pauses")
    silence_ratio: float = Field(0.0, description="Ratio of silence to total duration")
    pitch_variance: float = Field(0.0, description="Voice modulation (low = monotone)")
    pacing_consistency: float = Field(0.0, description="Sentence pacing score (0-10)")
    naturalness_score: float = Field(5.0, description="Reading vs natural speech (0-10)")
    fluency_label: str = Field("Optimal", description="Slow | Optimal | Fast")
    confidence_score: float = Field(5.0, description="Voice confidence score (0-10)")


class VoiceAnswerResponse(BaseModel):
    saved: bool = Field(True, description="Whether the answer was saved")
    question_number: int = Field(..., description="The question number that was answered")
    transcript: str = Field("", description="Transcribed answer text")
    voice_metrics: VoiceMetrics = Field(default_factory=VoiceMetrics)


# Response models
class ResumeUploadResponse(BaseModel):
    session_id: str = Field(..., description="UUID of the created session")
    candidate_name: str = Field(..., description="Extracted candidate name")
    skills: list[str] = Field(default_factory=list, description="Extracted skills list")
    experience_level: str = Field(..., description="Inferred experience level")
    role: str = Field(..., description="Selected interview role")


class QuestionResponse(BaseModel):
    question_id: str = Field(..., description="UUID of the generated question")
    question_text: str = Field(..., description="The interview question")
    question_number: int = Field(..., description="Current question number (1-indexed)")
    total_questions: int = Field(..., description="Total questions in the session")
    topic: Optional[str] = Field(None, description="Question topic area")
    difficulty: Optional[str] = Field(None, description="Question difficulty level")
    done: bool = Field(False, description="True if interview is complete")


class AnswerResponse(BaseModel):
    saved: bool = Field(True, description="Whether the answer was saved")
    question_number: int = Field(..., description="The question number that was answered")


class QAPair(BaseModel):
    question_id: str
    question_number: int
    question_text: str
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    answer_text: Optional[str] = None
    answer_mode: Optional[str] = Field("text", description="'text' or 'voice'")
    answered_at: Optional[str] = None
    voice_metrics: Optional[VoiceMetrics] = None


class SessionResponse(BaseModel):
    session_id: str
    candidate_name: Optional[str] = None
    role: str
    status: str
    questions_count: int
    created_at: Optional[str] = None
    qa_pairs: list[QAPair] = Field(default_factory=list)


class VoiceAggregate(BaseModel):
    """Aggregate voice analytics across all voice answers in a session."""
    avg_response_latency: float = Field(0.0, description="Avg seconds before first word")
    avg_naturalness: float = Field(0.0, description="Avg reading vs natural score")
    avg_wpm: float = Field(0.0, description="Avg words per minute")
    total_fillers: int = Field(0, description="Total filler words across all answers")
    avg_confidence: float = Field(0.0, description="Avg voice confidence score")
    voice_answers_count: int = Field(0, description="Number of answers via voice")


class SummaryAnalysis(BaseModel):
    topics_covered: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)
    overall_assessment: str = Field("", description="1-2 sentence overall note")
    confidence_score: float = Field(0.0, description="Heuristic confidence score out of 10")
    voice_aggregate: Optional[VoiceAggregate] = None


class SummaryResponse(BaseModel):
    session_id: str
    candidate_name: Optional[str] = None
    role: str
    questions_asked: int
    answers_given: int
    qa_pairs: list[QAPair] = Field(default_factory=list)
    analysis: SummaryAnalysis


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system status")
    ollama: bool = Field(False, description="Ollama reachable")
    chroma: bool = Field(False, description="ChromaDB available")
    db: bool = Field(False, description="SQLite accessible")
