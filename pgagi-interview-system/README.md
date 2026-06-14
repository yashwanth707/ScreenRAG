# ScreenRAG — AI-Powered Technical Interview Platform

An intelligent interview system that generates personalized, RAG-grounded technical questions based on a candidate's resume and target role.

## 🎯 What It Does

1. **Upload Resume** — Candidate uploads their PDF resume
2. **Select Role** — Choose from AI/ML Engineer, Backend Engineer, or Data Scientist
3. **AI Interview** — System generates 7 personalized questions grounded in ML textbook content
4. **Voice-First Chat** — Answer questions using your microphone, featuring real-time waveforms, silence auto-submit, and latency tracking.
5. **Smart Summary** — AI-generated analysis with strengths, improvements, confidence score, and **Voice Analytics** (WPM, naturalness, pauses).

## 🏗️ Architecture

```
Frontend (React 18 + Vite)
    ↓ HTTP
Backend (FastAPI + Python 3.11)
    ├── Ollama (llama3) → primary LLM
    ├── Gemini API → fallback LLM
    ├── ChromaDB → vector store (RAG)
    ├── SentenceTransformers → embeddings
    └── SQLite → session persistence
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/download) with `llama3` model pulled

```bash
# Pull the LLM model
ollama pull llama3
ollama serve  # Start Ollama server
```

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Edit .env and set your GEMINI_API_KEY (optional, for fallback)

# (Optional) Ingest knowledge base PDFs
# Place PDF textbooks in knowledge_base/pdfs/ first
python knowledge_base/ingest.py

# Start the server
uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Access

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Docker (Alternative)

```bash
docker-compose up --build
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/resume/upload` | Upload PDF resume + role → create session |
| `POST` | `/interview/next-question` | Generate next interview question |
| `POST` | `/interview/answer` | Submit text answer to a question |
| `POST` | `/interview/answer-voice` | Submit audio answer for transcription and voice analytics |
| `GET` | `/session/{id}` | Get session with all Q&A |
| `GET` | `/summary/{id}` | Generate AI interview summary |
| `GET` | `/health` | System health check |

## 🧠 Knowledge Base

Place ML textbook PDFs in `backend/knowledge_base/pdfs/`:

| Role | Expected Files |
|------|---------------|
| AI/ML | `ml_absolute_beginners.pdf`, `ai_ml_dl.pdf` |
| Data Science | `intro_ml_python.pdf`, `ai_ml_dl.pdf` |
| Backend | `ml_absolute_beginners.pdf` |

Then run:
```bash
cd backend
python knowledge_base/ingest.py
```

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Voice Processing | openai-whisper, pydub, FFmpeg |
| LLM (primary) | Ollama — llama3 |
| LLM (fallback) | Google Gemini 2.5 Flash |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | ChromaDB (persistent, file-based) |
| PDF Parsing | pdfplumber |
| Database | SQLite via aiosqlite |
| Frontend | React 18 + Vite, CSS Modules, Web Audio API |
| Containerization | Docker Compose |

## 📁 Project Structure

```
pgagi-interview-system/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings from .env
│   ├── database.py              # SQLite layer
│   ├── models.py                # Pydantic schemas
│   ├── routers/                 # API route handlers
│   │   ├── resume.py
│   │   ├── session.py
│   │   ├── interview.py
│   │   └── summary.py
│   ├── services/                # Business logic
│   │   ├── llm_client.py        # Ollama + Gemini dual backend
│   │   ├── resume_parser.py     # PDF → structured data
│   │   ├── rag_engine.py        # ChromaDB ingestion + retrieval
│   │   ├── question_generator.py # RAG-grounded questions
│   │   └── session_manager.py   # Session state machine
│   └── knowledge_base/
│       ├── ingest.py            # PDF → ChromaDB script
│       └── pdfs/                # Place textbooks here
├── frontend/
│   ├── src/
│   │   ├── pages/               # LandingPage, InterviewPage, SummaryPage
│   │   ├── components/          # ResumeUpload, RoleSelector, InterviewChat, etc.
│   │   ├── context/             # SessionContext (global state)
│   │   ├── api/                 # Axios client
│   │   └── styles/              # Global CSS design system
│   └── index.html
├── docker-compose.yml
└── README.md
```

## License

MIT
