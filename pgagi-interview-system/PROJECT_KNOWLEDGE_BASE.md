# ScreenRAG — Project Knowledge Base & Development Log

> **Last Updated:** 2026-06-12
> **Version:** 1.0.0
> **Author:** ScreenRAG Team
> **Status:** Initial Build Complete

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack & Dependencies](#2-tech-stack--dependencies)
3. [Architecture Deep Dive](#3-architecture-deep-dive)
4. [File Map & Module Reference](#4-file-map--module-reference)
5. [Database Schema](#5-database-schema)
6. [Environment Variables](#6-environment-variables)
7. [API Endpoints Reference](#7-api-endpoints-reference)
8. [RAG Engine Documentation](#8-rag-engine-documentation)
9. [LLM Client & Prompt Engineering](#9-llm-client--prompt-engineering)
10. [Question Generation Logic](#10-question-generation-logic)
11. [Frontend Component Architecture](#11-frontend-component-architecture)
12. [Commands Reference](#12-commands-reference)
13. [Docker Setup](#13-docker-setup)
14. [Troubleshooting & Common Issues](#14-troubleshooting--common-issues)
15. [Known Limitations](#15-known-limitations)
16. [Future Roadmap](#16-future-roadmap)
17. [Development Log](#17-development-log)

---

## 1. Project Overview

**ScreenRAG** is an AI-powered technical interview platform that combines Resume Parsing, Retrieval-Augmented Generation (RAG), and dual-LLM backends to deliver personalized, context-grounded interview experiences.

### What it does:
1. Candidate uploads a PDF resume
2. Selects a target role (AI/ML Engineer, Backend Engineer, Data Scientist)
3. System parses the resume and extracts structured data (name, skills, experience level)
4. RAG engine retrieves relevant chunks from role-specific ML textbook collections
5. LLM generates 7 personalized interview questions grounded in both resume context and textbook material
6. Candidate answers questions using their voice (via microphone), or text fallback
7. Audio is processed via VocalGauge engine for transcription, latency, pacing, and naturalness
8. System produces a structured session summary with AI-generated analysis and Voice Analytics

### Key Design Principles:
- **RAG-grounded questions:** Every question is informed by retrieved textbook content, not generic LLM knowledge
- **Dual LLM fallback:** Ollama (local) first, Gemini (cloud) as silent fallback — user never sees the switch
- **Adaptive difficulty:** Question difficulty adjusts based on answer length and quality
- **Topic diversity:** Ensures questions span ≥4 distinct topics across a session
- **Privacy-first:** Uploaded resumes are deleted from disk immediately after parsing
- **Idempotent ingestion:** Knowledge base re-ingestion never duplicates chunks

### VocalGauge Patterns Reused:
- FastAPI lifespan pattern for DB initialization and directory setup
- aiosqlite with Row factory for async database access
- httpx AsyncClient for Ollama API communication
- JSON extraction with markdown fence stripping (extract_json)
- CORS configuration for Vite dev server
- Background-safe error handling patterns

---

## 2. Tech Stack & Dependencies

### Backend (Python 3.11+)
| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.111.0 | Web framework / API server |
| Uvicorn | 0.29.0 | ASGI server with hot-reload |
| python-multipart | 0.0.9 | File upload handling |
| pdfplumber | 0.11.0 | PDF text extraction (resume + textbooks) |
| sentence-transformers | 2.7.0 | Embedding model (all-MiniLM-L6-v2) |
| chromadb | 0.5.0 | Persistent vector database |
| aiosqlite | 0.20.0 | Async SQLite database access |
| httpx | 0.27.0 | Async HTTP client (Ollama API) |
| google-generativeai | 0.7.0 | Gemini API SDK (fallback LLM) |
| pydantic-settings | 2.2.1 | Type-safe configuration from .env |
| python-dotenv | 1.0.1 | .env file loading |
| openai-whisper | 20250625 | Speech-to-text for voice answers |
| pydub | 0.25.1 | Audio waveform processing (pauses, volume) |

### Frontend (Node.js 18+)
| Package | Version | Purpose |
|---------|---------|---------|
| React | 18.3.1 | UI framework |
| React DOM | 18.3.1 | React rendering |
| react-router-dom | 6.23.1 | Client-side routing |
| axios | 1.7.2 | HTTP client for API calls |
| Vite | 5.3.1 | Build tool & dev server |
| @vitejs/plugin-react | 4.3.1 | React support for Vite |

### External Requirements
| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.11+ | Backend runtime | [python.org](https://python.org) |
| Node.js 18+ | Frontend runtime | [nodejs.org](https://nodejs.org) |
| Ollama | Local LLM server | [ollama.com](https://ollama.com/download) |
| llama3 model | Primary LLM | `ollama pull llama3` |

---

## 3. Architecture Deep Dive

### Data Flow Pipeline

```
PDF Resume Upload
      │
      ▼
┌─────────────────────────────┐
│  1. Resume Parsing           │  services/resume_parser.py
│  - pdfplumber text extraction│  
│  - LLM structured extraction│  → {name, skills, experience_level}
│  - File deleted after parse  │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  2. Session Creation         │  services/session_manager.py
│  - UUID generated            │  database.py
│  - Stored in SQLite          │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  3. Question Generation      │  services/question_generator.py
│  (repeated 7 times)         │
│                              │
│  a. Determine difficulty     │  Adaptive based on prev answers
│  b. Build retrieval query    │  Skills + uncovered topics
│  c. RAG retrieval            │  services/rag_engine.py → ChromaDB
│  d. LLM prompt + generate   │  services/llm_client.py
│  e. Save question to DB     │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  4. Voice Answer Processing  │  routers/interview.py
│  - Validate session/question │  services/audio_service.py (VocalGauge)
│  - Extract audio metrics     │  → latency, pitch, WPM, pauses
│  - Transcribe via Whisper    │
│  - Calculate Naturalness     │  → reading vs natural detection
│  - Save transcript & metrics │  database.py
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  5. Summary Generation       │  routers/summary.py
│  - Fetch all Q&A pairs       │
│  - Build interview transcript│
│  - LLM analysis generation   │  → topics, strengths, improvements
│  - Confidence score heuristic│
│  - Mark session completed    │
└─────────────────────────────┘
```

### LLM Fallback Chain

```
User Request
    │
    ▼
┌─────────────┐     Success     ┌──────────────────┐
│   Ollama    │ ──────────────→ │  Return Response  │
│  (llama3)   │                 └──────────────────┘
└─────┬───────┘
      │ Failure (ConnectionError, Timeout, HTTP error)
      ▼
┌─────────────┐     Success     ┌──────────────────┐
│   Gemini    │ ──────────────→ │  Return Response  │
│  (2.5-flash) │                 └──────────────────┘
└─────┬───────┘
      │ Failure
      ▼
┌──────────────────┐
│  HTTPException   │
│  503 Service     │
│  Unavailable     │
└──────────────────┘
```

### RAG Pipeline

```
Query (skills + topic + role)
    │
    ▼
┌─────────────────────────────┐
│  1. Embed Query              │  SentenceTransformer (all-MiniLM-L6-v2)
│  → 384-dim vector            │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  2. ChromaDB Similarity      │  Role-scoped collection
│  Search                      │  (ai_ml_kb, backend_kb, data_science_kb)
│  → Top 5 chunks             │  Cosine similarity
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  3. Context Assembly         │  Concatenate retrieved chunks
│  → Passed to LLM prompt     │  Used to ground questions
└─────────────────────────────┘
```

---

## 4. File Map & Module Reference

### Project Structure

```
pgagi-interview-system/
├── backend/
│   ├── main.py                     # FastAPI app, CORS, router registration, lifespan
│   ├── config.py                   # Pydantic Settings from .env
│   ├── database.py                 # SQLite init, CRUD, parameterized queries
│   ├── models.py                   # Pydantic request/response schemas
│   ├── .env                        # Environment configuration
│   ├── requirements.txt            # Python dependencies (pinned)
│   ├── Dockerfile                  # Python 3.11-slim container
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── resume.py               # POST /resume/upload
│   │   ├── session.py              # GET /session/{id}
│   │   ├── interview.py            # POST /interview/next-question, /answer
│   │   └── summary.py             # GET /summary/{session_id}
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_client.py          # Ollama + Gemini dual backend
│   │   ├── resume_parser.py       # PDF → structured dict
│   │   ├── rag_engine.py          # ChromaDB ingestion + retrieval
│   │   ├── question_generator.py  # Adaptive question generation
│   │   ├── session_manager.py     # Session lifecycle CRUD
│   │   └── audio_service.py       # VocalGauge audio processing pipeline
│   ├── knowledge_base/
│   │   ├── ingest.py              # Standalone PDF → ChromaDB script
│   │   └── pdfs/                  # ML textbook PDFs (user-provided)
│   ├── data/                      # SQLite DB (auto-created)
│   ├── chroma_store/              # ChromaDB persistence (auto-created)
│   └── uploads/                   # Temp resume storage (auto-deleted)
│
├── frontend/
│   ├── index.html                 # Entry HTML with SEO meta, Google Fonts
│   ├── vite.config.js             # Vite + React plugin, API proxy
│   ├── package.json               # React 18, axios, react-router-dom
│   ├── Dockerfile                 # Node 20-alpine container
│   └── src/
│       ├── main.jsx               # React entry with Router + Provider
│       ├── App.jsx                # Route definitions (3 pages)
│       ├── api/
│       │   └── client.js          # Axios instance + all API functions
│       ├── context/
│       │   └── SessionContext.jsx # Global state (useReducer + localStorage)
│       ├── pages/
│       │   ├── LandingPage.jsx    # Upload + role selection
│       │   ├── LandingPage.module.css
│       │   ├── InterviewPage.jsx  # Live Q&A chat
│       │   ├── InterviewPage.module.css
│       │   ├── SummaryPage.jsx    # Results + download
│       │   └── SummaryPage.module.css
│       ├── components/
│       │   ├── ResumeUpload/      # Drag-and-drop PDF upload zone
│       │   ├── RoleSelector/      # 3-card role picker
│       │   ├── InterviewChat/     # Chat message list + input
│       │   ├── QuestionCard/      # AI question bubble
│       │   └── SessionSummary/    # Analysis + Q&A transcript display
│       └── styles/
│           └── global.css         # Design system (tokens, animations, components)
│
├── docker-compose.yml             # 2-service orchestration
├── README.md                      # User-facing documentation
└── PROJECT_KNOWLEDGE_BASE.md      # THIS FILE
```

### Module Details

#### `backend/main.py` — API Server
- FastAPI app with lifespan management (DB init, directory creation)
- CORS middleware (localhost:5173, :3000, 127.0.0.1:5173)
- 4 routers registered: resume, session, interview, summary
- `/health` endpoint with Ollama/ChromaDB/SQLite checks
- Root `/` returns API info

#### `backend/config.py` — Configuration
- `Settings` class via pydantic-settings
- All fields have defaults; only `GEMINI_API_KEY` needs explicit configuration
- Singleton `settings` instance imported throughout the codebase

#### `backend/database.py` — SQLite Layer (~200 lines)
- `init_db()` — creates 3 tables via executescript
- Generic helpers: `execute()`, `fetch_one()`, `fetch_all()`
- Session CRUD: create, get (with JSON parsing), update status
- Question CRUD: save, list by session, count
- Answer CRUD: save, get by question
- Composite: `get_session_qa_pairs()` — JOIN questions with answers

#### `backend/services/llm_client.py` — Dual LLM (~230 lines)
- `generate(prompt, system)` — try Ollama, fall back to Gemini
- `generate_json(prompt, system, retries)` — generate + parse JSON with retry
- `extract_json_from_response(raw)` — strip fences, find JSON object
- `check_ollama_health()` — model availability check
- Lazy Gemini initialization to avoid import-time errors
- 600s timeout for Ollama (CPU inference can be slow)

#### `backend/services/resume_parser.py` — Resume Parsing (~180 lines)
- `parse_resume_pdf(file_path)` — pdfplumber + LLM extraction
- Extracts: name, skills, technologies, projects_summary, experience_level
- Fallback keyword extraction if LLM fails
- Truncates long resumes to 6000 chars for LLM context

#### `backend/services/rag_engine.py` — RAG Engine (~300 lines)
- `ingest_documents(pdf_paths, collection, role)` — full ingestion pipeline
- `retrieve_context(query, role, n_results)` — similarity search
- `chunk_text(text, max_tokens, overlap)` — sliding window chunking
- `check_chroma_health()` — collection stats
- Sentence-boundary splitting (regex-based)
- Token estimation: words × 1.33

#### `backend/services/question_generator.py` — Question Gen (~250 lines)
- `generate_question(session_data, previous_qa, question_num)` — main entry
- Adaptive difficulty: adjusts based on answer length + question progression
- Topic tracking: cycles through role-specific topic pools
- Per-role topic lists: 12-14 topics each for ai_ml, backend, data_science
- Fallback question if LLM fails

#### `backend/services/session_manager.py` — Session Manager (~170 lines)
- `start_session(role, resume_data)` — creates DB session, returns UUID
- `get_session(session_id)` — full session with Q&A pairs
- `save_question()`, `save_answer()` — CRUD wrappers
- `complete_session()`, `is_session_complete()` — lifecycle
- `get_previous_qa()` — formatted for question generator

#### `backend/services/audio_service.py` — Audio Processing (~600 lines)
- VocalGauge integration for Voice Analytics
- `validate_and_preprocess()` — FFmpeg/pydub to format as 16kHz mono WAV
- `extract_audio_metrics()` — latency, silence ratio, and pitch variance
- `transcribe_audio()` — Whisper local transcription
- `compute_naturalness_score()` — reading vs natural speech heuristic
- `compute_voice_confidence()` — 7-signal composite score

---

## 5. Database Schema

**File:** `data/interview.db` (SQLite, auto-created on startup)

### Table: `sessions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `candidate_name` | TEXT | — | Extracted from resume |
| `role` | TEXT | NOT NULL | 'ai_ml', 'backend', 'data_science' |
| `resume_text` | TEXT | — | Full extracted resume text |
| `resume_skills` | TEXT | — | JSON array of skills |
| `status` | TEXT | DEFAULT 'active' | 'active' or 'completed' |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Session start time |
| `completed_at` | TIMESTAMP | — | Set when status → completed |

### Table: `questions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `session_id` | TEXT | NOT NULL, FK → sessions | Parent session |
| `question_number` | INTEGER | NOT NULL | 1-indexed sequence |
| `question_text` | TEXT | NOT NULL | The interview question |
| `rag_context` | TEXT | — | Retrieved chunks (truncated) |
| `topic` | TEXT | — | e.g., 'neural_networks' |
| `difficulty` | TEXT | — | 'basic', 'intermediate', 'advanced' |
| `generated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Generation time |

### Table: `answers`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `session_id` | TEXT | NOT NULL, FK → sessions | Parent session |
| `question_id` | TEXT | NOT NULL, FK → questions | Answered question |
| `answer_text` | TEXT | NOT NULL | Candidate's response |
| `answer_mode` | TEXT | DEFAULT 'text' | 'text' or 'voice' |
| `answered_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Answer time |

### Table: `voice_metrics`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `answer_id` | TEXT | NOT NULL, FK → answers | Associated answer |
| `duration_seconds`| REAL | — | Audio length |
| `response_latency`| REAL | — | Delay before speaking |
| `wpm` | REAL | — | Words per minute |
| `filler_count` | INTEGER | — | um, uh, etc. |
| `naturalness_score`| REAL | — | 0-10 reading vs natural |
| `confidence_score` | REAL | — | 0-10 composite |

---

## 6. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | `""` | Google Gemini API key (fallback LLM) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3` | Ollama model name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `CHROMA_PERSIST_DIR` | `./chroma_store` | ChromaDB storage path |
| `DB_PATH` | `./data/interview.db` | SQLite database path |
| `MAX_QUESTIONS` | `7` | Questions per interview session |
| `UPLOAD_DIR` | `./uploads` | Temporary upload directory |

---

## 7. API Endpoints Reference

### `POST /resume/upload`
Upload a PDF resume and create an interview session.

| Field | Type | Description |
|-------|------|-------------|
| `file` | File (multipart) | PDF resume file |
| `role` | string (form) | 'ai_ml', 'backend', 'data_science' |
| **Response** | JSON | `{session_id, candidate_name, skills, experience_level, role}` |

### `POST /interview/next-question`
Generate the next interview question.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string (body) | Session UUID |
| **Response** | JSON | `{question_id, question_text, question_number, total_questions, topic, difficulty, done}` |

### `POST /interview/answer`
Submit an answer to a question.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string (body) | Session UUID |
| `question_id` | string (body) | Question UUID |
| `answer_text` | string (body) | Candidate's answer |
| **Response** | JSON | `{saved: true, question_number}` |

### `GET /session/{session_id}`
Get full session with Q&A data.

| **Response** | JSON | `{session_id, candidate_name, role, status, questions_count, qa_pairs}` |

### `GET /summary/{session_id}`
Generate interview summary with AI analysis.

| **Response** | JSON | `{session_id, candidate_name, role, questions_asked, answers_given, qa_pairs, analysis}` |
| `analysis` includes | — | `{topics_covered, strengths, areas_for_improvement, overall_assessment, confidence_score}` |

### `GET /health`
System health check.

| **Response** | JSON | `{status, ollama: bool, chroma: bool, db: bool}` |

---

## 8. RAG Engine Documentation

### Chunking Strategy

- **Method:** Sliding window with sentence boundaries
- **Max tokens per chunk:** 800 (~600 words)
- **Overlap:** 150 tokens (~112 words)
- **Splitting:** Regex sentence detection (`(?<=[.!?])\s+(?=[A-Z])`)
- **Token estimation:** `word_count × 1.33`

### Collections

| Role | Collection Name | Source PDFs |
|------|----------------|-------------|
| AI/ML Engineer | `ai_ml_kb` | ml_absolute_beginners.pdf, ai_ml_dl.pdf |
| Data Scientist | `data_science_kb` | intro_ml_python.pdf, ai_ml_dl.pdf |
| Backend Engineer | `backend_kb` | ml_absolute_beginners.pdf |

### Embedding Model

- **Model:** `all-MiniLM-L6-v2` (sentence-transformers)
- **Dimensions:** 384
- **Similarity:** Cosine (configured in ChromaDB via `hnsw:space`)
- **Lazy loading:** Model initialized on first use

### Idempotency

Re-running `ingest.py` will NOT duplicate chunks. The ingestion script checks `collection.count()` before processing. If documents already exist, ingestion is skipped.

---

## 9. LLM Client & Prompt Engineering

### Dual Backend Architecture

1. **Primary: Ollama** — Local inference via HTTP API at `localhost:11434/api/generate`
   - Model: `llama3` (configurable)
   - Timeout: 600 seconds (CPU inference)
   - Context window: 8192 tokens
   - Temperature: 0.3

2. **Fallback: Gemini** — Google cloud API via `google-generativeai` SDK
   - Model: `gemini-2.5-flash`
   - Lazy initialization (only if Ollama fails)
   - Temperature: 0.3
   - Max output tokens: 4096

### JSON Extraction

All LLM prompts instruct the model to return JSON only. Responses are cleaned:
1. Strip markdown code fences (`\`\`\`json ... \`\`\``)
2. Find outermost `{...}` object
3. `json.loads()` with retry on parse failure
4. Second attempt uses stricter "JSON only" system prompt

### Prompt Templates

- **Resume extraction:** Asks for name, skills, technologies, projects, experience_level, education
- **Question generation:** Includes RAG context, candidate profile, previous topics, difficulty instructions
- **Summary analysis:** Includes full Q&A transcript, asks for topics, strengths, improvements, assessment

---

## 10. Question Generation Logic

### Adaptive Difficulty

| Condition | Effect |
|-----------|--------|
| Last answer < 30 words | Lower difficulty by 1 level |
| Last answer > 150 words | Raise difficulty by 1 level |
| Question 5-7 | Shift toward higher difficulty |
| Question 1-2 | Keep at baseline |

Levels: `basic` → `intermediate` → `advanced`
Baseline determined by experience level: junior=basic, mid=intermediate, senior=advanced

### Topic Tracking

Each role has a pool of 12-14 topics. The generator:
1. Tracks which topics have been covered via `previous_qa`
2. Selects from uncovered topics first
3. If all topics covered, cycles back with deeper focus
4. Ensures diversity: questions span ≥4 distinct topics

### Retrieval Query Construction

```
query = "{target_topic} {top_5_skills} {role_display_name}"
```
The query combines the next uncovered topic with the candidate's skills to retrieve maximally relevant chunks.

---

## 11. Frontend Component Architecture

### App Flow (React Router)

```
BrowserRouter
  └── SessionProvider (Context)
      └── Routes
          ├── /           → LandingPage
          ├── /interview  → InterviewPage (guarded: requires sessionId)
          ├── /summary    → SummaryPage (guarded: requires sessionId)
          └── *           → Redirect to /
```

### State Management

- **SessionContext** uses `useReducer` with actions: SET_SESSION, SET_STEP, RESET, RESTORE
- **Steps enum:** UPLOAD → INTERVIEW → SUMMARY
- **localStorage persistence:** Session state saved on change, restored on mount
- On "Start New Interview": clears localStorage + resets reducer

### Component Tree

```
LandingPage
  ├── ResumeUpload (drag-and-drop PDF zone)
  ├── RoleSelector (3 gradient cards)
  └── "Start Interview" button

InterviewPage
  ├── Header (role, name, progress)
  ├── Progress bar
  └── InterviewChat
      ├── QuestionCard (AI bubbles)
      ├── Answer bubbles
      ├── Typing indicator
      └── Textarea + Submit button

SummaryPage
  └── SessionSummary
      ├── Info card (name, role, questions, score)
      ├── Analysis (topics, strengths, improvements)
      ├── Q&A transcript cards
      └── Download + Restart buttons
```

### Design System (global.css)

- **Theme:** Premium dark with glassmorphism
- **Background:** `#0a0e1a` with radial gradient overlays (violet, cyan, emerald)
- **Cards:** `rgba(26, 32, 53, 0.75)` with `backdrop-filter: blur(16px)`
- **Font:** Inter (sans), JetBrains Mono (mono)
- **Accent palette:** Violet (#8b5cf6), Cyan (#06b6d4), Emerald (#10b981), Amber (#f59e0b), Rose (#f43f5e), Blue (#3b82f6)
- **Animations:** fadeInUp, slideInLeft/Right, typing-dot, pulse, bounce, shimmer, spin
- **CSS Modules:** Each component has scoped styles via `.module.css` files

---

## 12. Commands Reference

### First-Time Setup

```bash
# 1. Install Ollama and pull llama3
ollama pull llama3

# 2. Backend setup
cd pgagi-interview-system/backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 3. (Optional) Ingest knowledge base
python knowledge_base/ingest.py

# 4. Frontend setup
cd ../frontend
npm install
```

### Running the Application

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — Backend
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend
npm run dev
```

**Access:** http://localhost:5173 (frontend) | http://localhost:8000/docs (API docs)

### Useful Commands

```bash
# Health check
curl http://localhost:8000/health

# Knowledge base ingestion
cd backend && python knowledge_base/ingest.py

# SQLite queries
sqlite3 data/interview.db "SELECT * FROM sessions;"
sqlite3 data/interview.db "SELECT COUNT(*) FROM questions;"

# Docker
docker-compose up --build
docker-compose down
```

---

## 13. Docker Setup

### Services

| Service | Port | Image | Volumes |
|---------|------|-------|---------|
| backend | 8000 | Python 3.11-slim | data/, chroma_store/, uploads/, pdfs/ |
| frontend | 5173 | Node 20-alpine | — |

### Running

```bash
docker-compose up --build   # First time
docker-compose up           # Subsequent runs
docker-compose down         # Stop
```

> **Note:** Ollama must run on the host machine (not in Docker). The backend connects to `host.docker.internal:11434` or `localhost:11434` depending on your Docker setup.

---

## 14. Troubleshooting & Common Issues

### "Ollama not reachable"
```
Fix:
  1. Run: ollama serve
  2. Verify: curl http://localhost:11434/api/tags
  3. Check OLLAMA_BASE_URL in .env
```

### "Both LLM backends unavailable (503)"
```
Fix:
  1. Start Ollama: ollama serve && ollama pull llama3
  2. OR set a valid GEMINI_API_KEY in .env
  3. At least one backend must be available
```

### "No text extracted from PDF"
```
Cause: PDF is scanned/image-based (no selectable text)
Fix: Use a PDF with selectable text, not a scanned image
```

### "Question generation slow"
```
Cause: Ollama CPU inference can take 30-60 seconds per question
Fix:
  - Use a GPU for Ollama inference
  - Use Gemini as primary (faster, but cloud-based)
  - Use a smaller model: ollama pull llama3.2:1b
```

### "ChromaDB collection empty"
```
Fix:
  1. Place PDF textbooks in backend/knowledge_base/pdfs/
  2. Run: python knowledge_base/ingest.py
  3. Questions will still generate without RAG context (less grounded)
```

### "CORS error in browser"
```
Fix:
  - Ensure backend CORS allows http://localhost:5173
  - Check main.py CORS middleware origins
  - Try http://127.0.0.1:5173 as alternative
```

---

## 15. Known Limitations

1. **No audio/video:** Text-only interview — no webcam or mic support
2. **No answer evaluation:** Individual answers are not scored or graded in real-time
3. **Scanned PDFs:** pdfplumber cannot extract text from image-based PDFs
4. **Single concurrent session:** No multi-user authentication or session isolation
5. **Embedding model size:** First download of all-MiniLM-L6-v2 is ~80MB
6. **ChromaDB in-process:** Runs in the same process as FastAPI (no separate server)
7. **No streaming:** LLM responses are generated fully before displaying (no token streaming)
8. **Confidence score is heuristic:** Based on answer length + keyword matching, not a validated metric

---

## 16. Future Roadmap

- [ ] **Real-time answer evaluation:** Score each answer against the retrieved RAG context
- [ ] **Streaming responses:** Stream LLM tokens to show typing effect in real-time
- [ ] **Multi-language support:** Resume parsing and questions in non-English languages
- [ ] **Audio interviews:** Add speech-to-text for verbal responses
- [ ] **Webcam integration:** Video recording for non-verbal cue analysis
- [ ] **Admin dashboard:** Review all sessions, export analytics
- [ ] **Authentication:** Multi-user support with JWT tokens
- [ ] **Custom role definitions:** Allow admins to define custom interview roles
- [ ] **PDF export:** Generate professional PDF interview reports
- [ ] **Benchmark scoring:** Compare candidate performance against role-specific benchmarks

---

## 17. Development Log

### 2026-06-12 — Initial Build (v1.0.0)

**Phase 1: Configuration & Foundation**
- Created `config.py` with pydantic-settings, `.env` template, `requirements.txt`
- All settings have sensible defaults, GEMINI_API_KEY optional

**Phase 2: Database Layer**
- Created `database.py` with 3 tables (sessions, questions, answers)
- Generic helpers (execute, fetch_one, fetch_all) for DRY access
- All queries use parameterized `?` placeholders — no SQL injection risk

**Phase 3: LLM Client**
- Created `services/llm_client.py` with Ollama-first, Gemini-fallback pattern
- JSON extraction with markdown fence stripping
- Retry logic: on parse failure, re-prompts with stricter JSON-only instruction
- Lazy Gemini initialization avoids import-time API key validation

**Phase 4: Resume Parser**
- Created `services/resume_parser.py`
- pdfplumber page-by-page extraction → LLM structured extraction
- Fallback keyword matching if LLM extraction fails
- Returns: name, skills, technologies, projects_summary, experience_level

**Phase 5: RAG Engine**
- Created `services/rag_engine.py` — ChromaDB ingestion + retrieval
- Sliding window chunking: 800 tokens, 150 overlap, sentence boundaries
- Role-scoped collections: ai_ml_kb, backend_kb, data_science_kb
- Idempotent ingestion — re-running skips populated collections
- Created `knowledge_base/ingest.py` — standalone CLI script

**Phase 6: Question Generator**
- Created `services/question_generator.py`
- Adaptive difficulty based on answer length and question progression
- Topic tracking across 12-14 role-specific topics
- RAG context retrieval for each question
- Fallback question if LLM fails

**Phase 7: Session Manager**
- Created `services/session_manager.py`
- Full session lifecycle: create → get → save Q&A → complete
- Previous Q&A retrieval formatted for question generator

**Phase 8: API Models**
- Created `models.py` with all Pydantic request/response schemas
- Request models: NextQuestionRequest, AnswerRequest
- Response models: ResumeUploadResponse, QuestionResponse, AnswerResponse, SessionResponse, SummaryResponse, HealthResponse

**Phase 9: API Routers & Main App**
- Created 4 routers: resume, session, interview, summary
- Resume router: upload → parse → create session → delete file
- Interview router: next-question generation + answer validation
- Summary router: LLM analysis generation + confidence score heuristic
- Created `main.py` with lifespan, CORS, router registration, health check

**Phase 10: Frontend**
- Created React 18 + Vite project with CSS Modules (no Tailwind)
- SessionContext: useReducer + localStorage persistence for page-refresh resilience
- API client: axios with 2-min timeout for LLM calls
- LandingPage: drag-and-drop upload + 3 role cards + start button
- InterviewPage: chat-style UI with auto-scroll, typing indicator, progress bar
- SummaryPage: AI analysis display, Q&A transcript, download as .txt
- Premium dark theme with glassmorphism, gradient accents, micro-animations

**Phase 11: Docker & Documentation**
- Created Dockerfiles for backend (Python 3.11-slim) and frontend (Node 20-alpine)
- docker-compose.yml with persistent volumes for data, chroma, uploads, PDFs
- README.md with setup instructions, API docs, tech stack
- PROJECT_KNOWLEDGE_BASE.md (this file)

**Bonus Features Implemented:**
- ✅ Adaptive difficulty (answer length + question progression)
- ✅ Topic tracking (≥4 distinct topics across session)
- ✅ Confidence score heuristic (answer length + keyword density)
- ✅ Session resume (localStorage persistence on page refresh)

### 2026-06-12 — VocalGauge & Voice-First UX Update (v1.1.0)

**Voice Analytics Integration**
- Ported the VocalGauge pipeline into `services/audio_service.py` to support audio answers.
- Implemented `openai-whisper` for local speech-to-text transcription.
- Implemented `pydub.silence.detect_nonsilent` for high-precision latency measurement (delay before the candidate starts speaking).
- Added `voice_metrics` SQLite table to store WPM, naturalness score, pitch variance, and pause ratios.

**Frontend UX & Bug Fixes**
- Added a Voice-First microphone interface in `InterviewChat.jsx` with real-time waveform visualization.
- **Smart Reading Timer:** The microphone now dynamically delays turning on based on the generated question's word count (~3 words/second), displaying a "Reading time..." UI to prevent cutting off the user while reading.
- **Concurrency Fix:** Fixed a React 18 StrictMode bug where `fetchNextQuestion` fired twice on mount, causing duplicate questions (e.g., two "Q1"s) to be saved to the database. Prevented with an `isFetchingRef` lock.

**LLM Maintenance**
- Updated the Gemini fallback model reference from the deprecated `gemini-1.5-flash` to the active `gemini-2.5-flash` model to restore cloud fallback capability.
