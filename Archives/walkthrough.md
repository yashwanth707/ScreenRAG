# ScreenRAG — Build Walkthrough

## Summary

Built a complete AI-powered technical interview platform from scratch across 11 phases, creating **35+ production-ready files** with real implementations (no scaffolding/placeholders).

## What Was Built

### Backend (14 files)
| File | Lines | Purpose |
|------|-------|---------|
| [config.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/config.py) | 35 | Pydantic settings from .env |
| [database.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/database.py) | 200 | SQLite layer with 3 tables, generic helpers |
| [models.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/models.py) | 100 | Pydantic request/response schemas |
| [main.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/main.py) | 140 | FastAPI entry with lifespan, CORS, routers |
| [llm_client.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/services/llm_client.py) | 230 | Ollama + Gemini dual backend |
| [resume_parser.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/services/resume_parser.py) | 180 | PDF → structured data via pdfplumber + LLM |
| [rag_engine.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/services/rag_engine.py) | 300 | ChromaDB ingestion + retrieval |
| [question_generator.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/services/question_generator.py) | 250 | Adaptive RAG-grounded question generation |
| [session_manager.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/services/session_manager.py) | 170 | Session lifecycle CRUD |
| [resume.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/routers/resume.py) | 100 | Upload endpoint |
| [interview.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/routers/interview.py) | 120 | Q&A endpoints |
| [summary.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/routers/summary.py) | 180 | Summary generation |
| [session.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/routers/session.py) | 50 | Session retrieval |
| [ingest.py](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/knowledge_base/ingest.py) | 100 | KB ingestion CLI |

### Frontend (20 files)
| File | Purpose |
|------|---------|
| [global.css](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/styles/global.css) | Design system (350 lines) |
| [SessionContext.jsx](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/context/SessionContext.jsx) | Global state + localStorage |
| [client.js](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/api/client.js) | Axios API client |
| [LandingPage.jsx](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/pages/LandingPage.jsx) | Upload + role selection |
| [InterviewPage.jsx](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/pages/InterviewPage.jsx) | Live Q&A with progress |
| [SummaryPage.jsx](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/src/pages/SummaryPage.jsx) | Results + download |
| 5 component directories | ResumeUpload, RoleSelector, InterviewChat, QuestionCard, SessionSummary |
| Each with `.jsx` + `.module.css` | Scoped styles per component |

### Infrastructure (4 files)
| File | Purpose |
|------|---------|
| [docker-compose.yml](file:///d:/Projects/ScreenRAG/pgagi-interview-system/docker-compose.yml) | 2-service orchestration |
| [Dockerfile (backend)](file:///d:/Projects/ScreenRAG/pgagi-interview-system/backend/Dockerfile) | Python 3.11-slim |
| [Dockerfile (frontend)](file:///d:/Projects/ScreenRAG/pgagi-interview-system/frontend/Dockerfile) | Node 20-alpine |
| [README.md](file:///d:/Projects/ScreenRAG/pgagi-interview-system/README.md) | Full documentation |

### Knowledge Base
| File | Purpose |
|------|---------|
| [PROJECT_KNOWLEDGE_BASE.md](file:///d:/Projects/ScreenRAG/pgagi-interview-system/PROJECT_KNOWLEDGE_BASE.md) | Complete project documentation with 17 sections |

## Bonus Features Implemented

| Feature | Implementation |
|---------|---------------|
| **Adaptive difficulty** | Answer < 30 words → lower difficulty; > 150 words → raise it |
| **Topic tracking** | 12-14 topics per role, cycles through uncovered ones first |
| **Confidence score** | Heuristic: avg answer length + keyword density → 0-10 |
| **Session resume** | localStorage persistence, auto-restore on page refresh |

## Key Architecture Decisions

1. **Ollama → Gemini silent fallback**: User never sees which backend is used
2. **Role-scoped ChromaDB collections**: No cross-contamination between knowledge bases
3. **CSS Modules over Tailwind**: Per spec, with premium glassmorphism design system
4. **useReducer over useState**: Cleaner state transitions for multi-field session data
5. **Idempotent ingestion**: `collection.count() > 0` → skip (no duplicate chunks)
6. **Resume deletion**: Files removed immediately after parsing for privacy

## Next Steps for User

1. **Start Ollama**: `ollama serve` then `ollama pull llama3`
2. **Install Python deps**: `cd backend && pip install -r requirements.txt`
3. **Start backend**: `uvicorn main:app --reload --port 8000`
4. **Start frontend**: `cd frontend && npm run dev`
5. **Optional**: Place ML textbook PDFs in `backend/knowledge_base/pdfs/` and run `python knowledge_base/ingest.py`
6. **Open**: http://localhost:5173
