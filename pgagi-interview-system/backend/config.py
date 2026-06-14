"""
ScreenRAG — Configuration Module

Loads all application settings from environment variables with sensible defaults.
Uses pydantic-settings for type-safe configuration with .env file support.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from .env file and environment variables.
    
    All fields have sensible defaults so the system can start with minimal
    configuration. Only GEMINI_API_KEY needs to be explicitly set if Ollama
    is unavailable.
    """

    # --- LLM Configuration ---
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_TIMEOUT: float = 600.0  # seconds — LLM can be slow on CPU

    # --- Embedding Configuration ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- Storage Configuration ---
    CHROMA_PERSIST_DIR: str = "./chroma_store"
    DB_PATH: str = "./data/interview.db"
    UPLOAD_DIR: str = "./uploads"

    # --- Interview Configuration ---
    MAX_QUESTIONS: int = 7

    # --- Voice/Audio Configuration (VocalGauge Integration) ---
    WHISPER_MODEL: str = "base"
    MIN_ANSWER_DURATION: float = 3.0    # seconds — below this, answer is too short
    MAX_ANSWER_DURATION: float = 300.0  # 5 minutes max per answer
    SILENCE_AUTO_STOP: float = 5.0      # seconds of silence before auto-submit
    AUDIO_UPLOAD_DIR: str = "./audio_uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton settings instance — import this everywhere
settings = Settings()
