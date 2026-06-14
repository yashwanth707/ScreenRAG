"""App configuration via pydantic-settings. Loads from .env with sensible defaults."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # LLM
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_TIMEOUT: float = 600.0  # can be slow on CPU

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Storage
    CHROMA_PERSIST_DIR: str = "./chroma_store"
    DB_PATH: str = "./data/interview.db"
    UPLOAD_DIR: str = "./uploads"

    # Interview
    MAX_QUESTIONS: int = 7

    # Voice / audio
    WHISPER_MODEL: str = "base"
    MIN_ANSWER_DURATION: float = 3.0
    MAX_ANSWER_DURATION: float = 300.0  # 5 min max
    SILENCE_AUTO_STOP: float = 5.0
    AUDIO_UPLOAD_DIR: str = "./audio_uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
