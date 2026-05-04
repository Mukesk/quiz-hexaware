# 📚Quiz Auto-Evaluation Backend

> **AI-powered adaptive quiz evaluation platform built for Learning & Development program**

## 🧭 Overview

The **Quiz Auto-Evaluation Backend** is a production-ready, asynchronous REST API built with **FastAPI** that powers an intelligent quiz engine for Hexaware's internal training platform. It dynamically generates questions using GPT-4o-mini, adapts difficulty in real-time based on student performance, computes scores deterministically (never via LLM), and provides rich PDF score reports stored in PostgreSQL.

## 🏗️ Architecture

The project strictly follows a layered **Router → Service → Repository → Model** pattern:

```
app/
├── routers/          # HTTP layer: Route definitions, request parsing, response formatting
│   ├── questions.py  # CRUD + AI generation endpoints
│   ├── quiz.py       # Quiz session lifecycle endpoints
│   └── reports.py    # Question report + AI agent review endpoints
├── services/         # Business logic layer (pure Python, no DB calls)
│   ├── ai_gen_service.py     # GPT-4o-mini question generation
│   ├── evaluation_service.py # Adaptive answer evaluation logic
│   ├── question_service.py   # Question fetching (Redis → DB → AI fallback)
│   ├── score_service.py      # Score computation and caching
│   ├── report_service.py     # Report submission (non-blocking) + human override
│   └── review_agent.py       # LangChain agent with 3 tools for claim verification
├── repositories/     # Database access layer (SQLAlchemy async queries)
│   ├── answer_repo.py
│   ├── question_repo.py
│   ├── report_repo.py
│   └── session_repo.py
├── models/           # SQLAlchemy ORM models (DB schema)
│   ├── user.py
│   ├── question.py
│   ├── quiz_session.py   # Also contains AIGenLog
│   ├── question_report.py
│   ├── course.py
│   └── week.py
├── schemas/          # Pydantic v2 schemas (request/response validation)
├── tasks/            # FastAPI BackgroundTasks (async, no separate worker)
│   ├── pdf_task.py       # PDF report generation → stored in PostgreSQL
│   ├── feedback_task.py  # AI feedback generation via GPT-4o-mini
│   └── review_task.py    # LangChain agent review + DB replace/edit/reject
├── auth/             # JWT authentication + RBAC
│   └── dependencies.py
├── utils/            # Pure utility functions
│   ├── adaptive.py   # Adaptive difficulty rule engine
│   └── metrics.py    # Accuracy computation (Python, not LLM)
├── config.py         # Pydantic Settings (env var loading)
├── database.py       # Async SQLAlchemy engine + session factory
├── redis_client.py   # Async Redis client
└── main.py           # FastAPI app factory + middleware
```

## ⚙️ Technology Stack

| Layer | Technology |
|---|---|
| **Web Framework** | FastAPI 0.115 |
| **Database** | PostgreSQL (via asyncpg) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Schema Migrations** | Alembic (async-compatible) |
| **Caching** | Redis (aioredis) |
| **AI - Generation** | OpenAI GPT-4o-mini (direct) |
| **AI - Agent Review** | LangChain 0.3 + ChatOpenAI |
| **LLM Observability** | LangSmith (traces all AI calls) |
| **Authentication** | JWT (python-jose) |
| **Password Hashing** | Passlib + Bcrypt |
| **PDF Generation** | ReportLab |
| **Validation** | Pydantic v2 |
| **Background Tasks** | FastAPI `BackgroundTasks` |
| **Testing** | pytest + pytest-asyncio + httpx |
| **Runtime** | Python 3.12 (via uv) |

## 🗄️ Database Schema

```
users
├── id (UUID PK)
├── email (unique)
├── name
├── role            → "student" | "instructor" | "admin"
└── level           → "Basic" | "Intermediate" | "Advanced"

courses
├── id (UUID PK)
├── name, code, description
└── created_at

weeks
├── id (UUID PK)
├── course_id (FK → courses)
├── title, week_number
└── learning_objectives (JSONB)

questions
├── id (UUID PK)
├── topic, subtopic
├── difficulty      → Basic | Easy | Intermediate | Advanced | VeryDifficult
├── type            → mcq | true_false | fill_blank | descriptive | coding | scenario
├── question_text
├── options (JSONB) → [{id, text, is_correct, explanation}]
├── correct_answer
├── blooms_level    → Apply | Remember | Understand | Analyze | Evaluate | Create
├── ai_generated    → bool
├── reviewed        → bool
└── deleted_at      (soft delete)

quiz_sessions
├── id (UUID PK)
├── user_id (FK), course_id (FK), week_id (FK)
├── topic, subtopic
├── status          → pending | active | completed
├── current_q_index, total_q, correct
├── score_pct       → Numeric(5,2)
├── difficulty      → current adaptive difficulty level
├── ai_feedback     → AI-generated feedback text
├── report_pdf      → LargeBinary (PDF bytes stored in PostgreSQL)
├── config (JSONB)
├── started_at, completed_at

user_answers
├── id (UUID PK)
├── session_id (FK), question_id (FK)
├── selected_option
├── is_correct
├── time_taken_s
├── bookmarked
└── created_at

ai_gen_log
├── id (UUID PK)
├── question_id (FK), user_id (FK)
├── prompt_used, raw_response
├── tokens_used, cost_usd
└── created_at

question_reports                      ← NEW (Module 4)
├── id (UUID PK)
├── question_id (FK → questions)
├── session_id  (FK → quiz_sessions)
├── reported_by (FK → users)
├── reason          → wrong_answer | wrong_question | ambiguous | outdated | other
├── student_note
├── status          → pending | agent_reviewing | valid_replaced | valid_edited | rejected | human_override
├── agent_verdict   → agent's reasoning text
├── agent_confidence → Numeric(4,2) — 0.00 to 1.00
├── replacement_q_id (FK → questions) → set when agent replaces
├── reviewed_by (FK → users)
├── reviewer_note
├── created_at, resolved_at
```

> **`questions` table additions (Module 4)**
> - `is_active BOOLEAN DEFAULT true` — `False` when a question is archived after replacement
> - `replaced_by UUID` — FK to the new question that replaced this one
> - `report_count INT DEFAULT 0` — incremented each time a student flags the question

## 🔐 Authentication & RBAC

All routes are protected by **JWT Bearer tokens**. The `require_role()` dependency factory enforces Role-Based Access Control at the router layer.

| Role | Permissions |
|---|---|
| `student` | Start/continue quiz, submit answers, view own results, **report questions** |
| `instructor` | CRUD questions, generate AI questions, view all results, view/override reports |
| `admin` | Full access including report stats |
| `reviewer` | Review and approve AI-generated questions |

## 🔄 Quiz Lifecycle

```
1. POST /quiz/start          → Creates a QuizSession, returns first question
2. GET  /quiz/question/:id   → Get next question (Redis cache → DB → AI fallback)
3. POST /quiz/answer         → Submit answer (evaluated deterministically in Python)
4. POST /quiz/submit         → Finalize session, compute score
                               → Triggers background PDF + AI feedback generation
5. GET  /quiz/result/:id     → Fetch ScoreReport (from Redis cache or compute)
6. GET  /quiz/report/:id/pdf → Download PDF report (stored in PostgreSQL BYTEA)
```

## 🤖 Adaptive Difficulty Engine

The system tracks performance **per subtopic** using a sliding window of 5 answers:

| Accuracy Threshold | Action |
|---|---|
| ≥ 80% | Advance difficulty (e.g. Basic → Intermediate) |
| ≤ 50% | Drop difficulty (e.g. Intermediate → Basic) |
| 51–79% | Maintain current difficulty |

Accuracy is always computed in Python — **LLMs are never used for scoring**.

## 📊 Scoring Rules

- `score_pct = (correct / total_q) × 100`
- `PASS` if `score_pct >= 60`, else `FAIL`
- Topic breakdown grouped by `question.subtopic`
- Strong/weak areas computed by subtopic accuracy
- Score reports cached in Redis permanently to avoid recomputation

## 🤖 AI Integration (GPT-4o-mini)

### Question Generation
- Called via `POST /questions/generate`
- Prompt enforces structured JSON output
- Response validated by Pydantic before being saved to DB
- All AI calls traced via **LangSmith** for observability
- Rate limited: max **20 requests per user per hour** (enforced via Redis)

### AI Feedback Generation
- Triggered as a **background task** after quiz submission
- Uses GPT-4o-mini to write 3 sentences of coaching feedback
- Feedback stored back to the `quiz_sessions.ai_feedback` column

## 📁 API Endpoints

### Questions API (`/questions`)
| Method | Endpoint | Role | Description |
|---|---|---|---|
| `POST` | `/questions/` | instructor | Create a question manually |
| `GET` | `/questions/{id}` | all | Get a single question |
| `PUT` | `/questions/{id}` | instructor | Update a question |
| `DELETE` | `/questions/{id}` | instructor | Soft delete a question |
| `GET` | `/questions/bank/list` | instructor | Paginated question bank |
| `POST` | `/questions/generate` | instructor | AI-generate a question |
| `PATCH` | `/questions/{id}/review` | reviewer | Approve AI question |

### Quiz API (`/quiz`)
| Method | Endpoint | Role | Description |
|---|---|---|---|
| `POST` | `/quiz/start` | student | Start a new quiz session |
| `GET` | `/quiz/question/{session_id}` | student | Get next question |
| `POST` | `/quiz/answer` | student | Submit an answer |
| `POST` | `/quiz/submit` | student | Finalize quiz + get score |
| `GET` | `/quiz/result/{session_id}` | student/instructor | Get score report |
| `GET` | `/quiz/report/{session_id}/pdf` | student/instructor | Download PDF report |
| `POST` | `/quiz/report` | student | 🆕 Flag a question as wrong/unclear |
| `GET` | `/quiz/report/my` | student | 🆕 View own submitted reports |

### Question Reports API (`/questions/reports`) — NEW
| Method | Endpoint | Role | Description |
|---|---|---|---|
| `GET` | `/questions/reports` | instructor/admin | List all reports (filterable by status) |
| `GET` | `/questions/reports/{id}` | instructor/admin | Single report detail |
| `PATCH` | `/questions/reports/{id}/override` | instructor/admin | Human reviewer override |
| `GET` | `/questions/{id}/reports` | instructor/admin | All reports for a question |
| `GET` | `/questions/reports/stats` | admin | Aggregate stats by reason/status |

### Health
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server health check |

## 🚀 Local Setup & Running

### Prerequisites
- Python 3.12+ (via `uv`)
- PostgreSQL (running locally)
- Redis (running locally)

### 1. Create virtual environment and install dependencies
```bash
cd quiz_backend
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Configure environment variables
```bash
# quiz_backend/.env
DATABASE_URL=postgresql+asyncpg://localhost:5432/quiz_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-super-secret-key
OPENAI_API_KEY=sk-proj-...
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT="quiz-intern-project"
LANGSMITH_TRACING=true
PASS_THRESHOLD_PCT=60
ADVANCE_THRESHOLD_PCT=80
DROP_THRESHOLD_PCT=50
ADAPTIVE_WINDOW_Q=5
```

### 3. Create database and run migrations
```bash
createdb quiz_db
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### 4. Seed test users
```bash
python seed_users.py
```
This creates `student@test.com`, `instructor@test.com`, `admin@test.com` and prints JWT tokens for each.

### 5. Start the server
```bash
uvicorn app.main:app --reload
```

### 6. Open interactive docs
```
http://127.0.0.1:8000/docs
```
Click **Authorize** and paste any JWT token from `seed_users.py` to test role-specific endpoints.

## 🧪 Testing

```bash
pytest tests/ -v
```

## 🐳 Docker (Optional)

```bash
# Start PostgreSQL + Redis + API
docker-compose up --build -d

# Run migrations inside container
docker-compose exec api alembic upgrade head
```

## 🔑 Key Design Decisions

| Decision | Rationale |
|---|---|
| **LLMs only for unstructured content** | Scores, accuracy, and pass/fail are computed deterministically in Python to prevent hallucinations |
| **Idempotent answer upserts** | `ON CONFLICT` ensures re-submitted answers (network retries) don't inflate correct counts |
| **Redis caching for score reports** | Avoids expensive recomputation; cached permanently after first computation |
| **PDF stored in PostgreSQL BYTEA** | Eliminates AWS S3 dependency; keeps the stack self-contained |
| **FastAPI BackgroundTasks over Celery** | Simpler deployment with no worker process; runs in the same async event loop |
| **Adaptive difficulty per subtopic** | More granular than session-level difficulty; prevents one weak topic from skewing difficulty for strong areas |
| **`is_active` filter on all question queries** | Single filter ensures replaced/archived questions are never served to any student without touching any other logic |
| **Agent confidence threshold of 0.75** | Rejects borderline cases — LLM is only trusted when highly confident, human reviewer can always override |
| **Non-blocking report pipeline** | `POST /quiz/report` returns 200 in < 500ms; agent runs in background so quiz session is never interrupted |

## 📂 Project Structure (Full)

```
quiz_backend/
├── app/
│   ├── auth/
│   │   └── dependencies.py
│   ├── models/
│   │   ├── course.py
│   │   ├── question.py
│   │   ├── question_report.py        ← NEW
│   │   ├── quiz_session.py   (+ AIGenLog)
│   │   ├── user.py
│   │   └── week.py
│   ├── repositories/
│   │   ├── answer_repo.py
│   │   ├── question_repo.py
│   │   ├── report_repo.py            ← NEW
│   │   └── session_repo.py
│   ├── routers/
│   │   ├── questions.py
│   │   ├── quiz.py
│   │   └── reports.py               ← NEW
│   ├── schemas/
│   │   ├── question.py
│   │   ├── quiz.py
│   │   ├── report.py                ← NEW
│   │   └── score.py
│   ├── services/
│   │   ├── ai_gen_service.py
│   │   ├── evaluation_service.py
│   │   ├── question_service.py
│   │   ├── report_service.py        ← NEW
│   │   ├── review_agent.py          ← NEW
│   │   └── score_service.py
│   ├── tasks/
│   │   ├── feedback_task.py
│   │   ├── pdf_task.py
│   │   └── review_task.py           ← NEW
│   ├── utils/
│   │   ├── adaptive.py
│   │   └── metrics.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   └── redis_client.py
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── ce9032ddd241_initial_schema.py
│       └── 073ada4209be_add_question_reports.py  ← NEW
├── tests/
│   ├── unit/
│   │   └── test_review_agent.py     ← NEW
│   ├── integration/
│   │   └── test_report_flow.py      ← NEW
│   └── conftest.py
├── seed_users.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env

---

## 🤖 Module 4 — Question Report & AI Agent Review

### Overview
Students can flag questions as wrong, ambiguous, or outdated during a live quiz. A **LangChain AI agent** autonomously verifies the report, decides whether to edit/replace/reject the question, and updates the database — all **without blocking the student's quiz session**.

### End-to-End Flow
```
1. POST /quiz/report         → Student flags question (returns 200 immediately)
2. BackgroundTask fires      → review_question_report(report_id, redis) starts async
3. Agent fetches Q + report  → Sets status to 'agent_reviewing'
4. Agent verifies claim      → verify_claim tool (confidence 0–1)
5. Agent decides:
   ├── confidence >= 0.75 + wrong_answer  → edit_question_fields   → 'valid_edited'
   ├── confidence >= 0.75 + broken Q      → generate_replacement   → 'valid_replaced'
   └── confidence < 0.75  or baseless     → reject                 → 'rejected'
6. If replaced: old Q archived (is_active=False), new Q inserted, Redis cache cleared
7. Student's next question fetch gets new Q transparently
8. Human reviewer can always override via PATCH /questions/reports/{id}/override
```

### LangChain Agent Tools
| Tool | Purpose |
|---|---|
| `verify_claim` | Analyses whether the student's complaint is factually valid |
| `generate_replacement_question` | Creates a corrected replacement (preserves topic/difficulty/type) |
| `edit_question_fields` | Patches specific fields in-place (for minor fixes like wrong `correct_answer`) |

### Agent Decision Matrix
| Scenario | Action | DB Effect |
|---|---|---|
| `wrong_answer` + confidence ≥ 0.75 | `edit` | Fix `correct_answer` + `explanation` in place |
| `wrong_question` + confidence ≥ 0.75 | `replace` | Archive original, insert new, clear Redis cache |
| `ambiguous` + confidence ≥ 0.75 | `replace` | Generate clearer question on same topic |
| Any reason + confidence < 0.75 | `reject` | Question unchanged; human can still override |
| Agent parse error | `rejected` | Error logged; report marked rejected |

### Key Invariant
> Every `get_by_id()` and `get_bank_ids()` filters `is_active=True`. This single condition ensures replaced/archived questions are **never served to any student, in any session**, with no additional logic changes anywhere else in the codebase.
```
