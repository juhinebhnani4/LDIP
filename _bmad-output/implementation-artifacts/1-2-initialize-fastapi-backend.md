# Story 1.2: Initialize FastAPI Backend Project

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a properly configured FastAPI backend project with Python 3.12+, Pydantic v2, and SQLAlchemy 2.0**,
So that **I have a production-ready foundation for building the LDIP API**.

## Acceptance Criteria

1. **Given** the backend directory is empty, **When** I run `uv init` and configure the project, **Then** a FastAPI project is created with Python 3.12+ configured
2. **And** Pydantic v2 is installed for request/response validation
3. **And** SQLAlchemy 2.0 is installed with async support (but Supabase client is primary for DB operations per architecture)
4. **And** alembic is configured for database migrations (optional, migrations primarily via Supabase)
5. **And** the project structure follows FastAPI best practices (routers, services, models directories) AND matches the architecture document exactly
6. **And** pytest is configured for testing with pytest-asyncio and httpx
7. **And** the server runs successfully with `uvicorn app.main:app --reload`
8. **And** the project includes all required dependencies per architecture: supabase, celery, redis, structlog

## Tasks / Subtasks

- [x] Task 1: Initialize Python project with uv (AC: #1)
  - [x] Create `backend/` directory in project root
  - [x] Run `uv init` to create pyproject.toml with Python 3.12+ requirement
  - [x] Set project name to "ldip-backend"
  - [x] Configure .python-version file for Python 3.12

- [x] Task 2: Install core dependencies (AC: #1, #2, #3, #8)
  - [x] Run `uv add fastapi uvicorn[standard]` for web framework
  - [x] Run `uv add pydantic pydantic-settings` for validation and config
  - [x] Run `uv add supabase python-dotenv` for database and env
  - [x] Run `uv add sqlalchemy[asyncio] alembic` for ORM/migrations (secondary to Supabase)
  - [x] Run `uv add celery redis` for background jobs
  - [x] Run `uv add structlog` for structured logging

- [x] Task 3: Install AI/ML dependencies (AC: #8)
  - [x] Run `uv add openai google-generativeai` for LLM clients
  - [x] Run `uv add google-cloud-documentai` for OCR

- [x] Task 4: Install dev dependencies (AC: #6)
  - [x] Run `uv add --dev pytest pytest-asyncio httpx` for testing
  - [x] Run `uv add --dev ruff mypy` for linting and type checking

- [x] Task 5: Create project directory structure (AC: #5)
  - [x] Create app/__init__.py
  - [x] Create app/main.py with FastAPI app entry point
  - [x] Create app/api/__init__.py
  - [x] Create app/api/deps.py for dependency injection
  - [x] Create app/api/routes/__init__.py
  - [x] Create app/api/routes/health.py for health check endpoint
  - [x] Create app/core/__init__.py
  - [x] Create app/core/config.py with Pydantic Settings
  - [x] Create app/core/security.py (placeholder for Supabase JWT validation)
  - [x] Create app/core/exceptions.py with AppException classes
  - [x] Create app/core/logging.py with structlog config
  - [x] Create app/engines/__init__.py (placeholder for AI engines)
  - [x] Create app/engines/base.py with abstract EngineBase class
  - [x] Create app/services/__init__.py
  - [x] Create app/services/supabase/__init__.py
  - [x] Create app/services/supabase/client.py (Supabase admin client)
  - [x] Create app/models/__init__.py
  - [x] Create app/workers/__init__.py
  - [x] Create app/workers/celery.py with Celery app config

- [x] Task 6: Create tests directory structure (AC: #6)
  - [x] Create tests/__init__.py
  - [x] Create tests/conftest.py with pytest fixtures
  - [x] Create tests/api/__init__.py
  - [x] Create tests/api/test_health.py

- [x] Task 7: Create environment configuration (AC: #7)
  - [x] Create .env.example with required variables
  - [x] Add SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY placeholders
  - [x] Add OPENAI_API_KEY, GOOGLE_API_KEY placeholders
  - [x] Add REDIS_URL placeholder
  - [x] Add CELERY_BROKER_URL placeholder
  - [x] Create .gitignore for Python/backend

- [x] Task 8: Configure alembic for migrations (AC: #4)
  - [x] Run `alembic init migrations` (or skip if using Supabase migrations only)
  - [x] Configure alembic.ini with async support

- [x] Task 9: Create Dockerfile (AC: #7)
  - [x] Create Dockerfile with Python 3.12 base
  - [x] Configure multi-stage build for production
  - [x] Set up uvicorn as CMD

- [x] Task 10: Verify project runs (AC: #7)
  - [x] Run `uv sync` to install all dependencies
  - [x] Run `uvicorn app.main:app --reload`
  - [x] Verify health endpoint returns 200
  - [x] Run `pytest` to verify test setup works
  - [x] Verify no linting errors with `ruff check .`

### Review Follow-ups (AI)

- [ ] [AI-Review][MEDIUM] Add JWT validation and RLS behavior smoke tests - current tests limited to health/wiring (Story 1-7 or Epic 13 scope)
- [ ] [AI-Review][MEDIUM] Add migration health check test or step to verify Alembic migrations run in each environment (Epic 13 scope)

## Dev Notes

### Critical Architecture Constraints

**FROM ARCHITECTURE DOCUMENT - MUST FOLLOW EXACTLY:**

#### Backend Project Structure (REQUIRED)
```
backend/                              # FastAPI Python Application
├── pyproject.toml
├── uv.lock                          # Generated by uv
├── Dockerfile
├── .env.example
├── alembic.ini                      # DB migrations (optional)
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                  # Dependency injection
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py            # Health check endpoints
│   │       ├── matters.py           # /api/matters/* (future)
│   │       ├── documents.py         # /api/documents/* (future)
│   │       ├── engines.py           # /api/engines/* (future)
│   │       ├── findings.py          # /api/findings/* (future)
│   │       ├── entities.py          # /api/entities/* (MIG, future)
│   │       └── chat.py              # /api/chat/* (streaming, future)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings
│   │   ├── security.py              # Supabase JWT validation
│   │   ├── exceptions.py            # AppException classes
│   │   └── logging.py               # Structlog config
│   ├── engines/                     # 3 MVP AI engines + orchestrator
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract EngineBase class
│   │   ├── orchestrator.py          # Query router + engine selector
│   │   ├── citation/                # MVP Engine
│   │   ├── timeline/                # MVP Engine
│   │   └── contradiction/           # MVP Engine
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm/                     # LLM orchestration (future)
│   │   ├── rag/                     # RAG pipeline (future)
│   │   ├── mig/                     # Matter Intelligence Graph (future)
│   │   ├── ocr/                     # Google Document AI (future)
│   │   ├── memory/                  # 3-layer memory (future)
│   │   └── supabase/
│   │       ├── __init__.py
│   │       ├── client.py            # Supabase admin client
│   │       └── storage.py           # File upload/download (future)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── matter.py                # Pydantic models for Matter (future)
│   │   ├── document.py              # (future)
│   │   └── finding.py               # (future)
│   └── workers/
│       ├── __init__.py
│       ├── celery.py                # Celery app config
│       └── tasks/                   # (future)
│           ├── __init__.py
│           ├── document_tasks.py    # OCR, chunking, embedding
│           └── engine_tasks.py      # Async engine execution
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── api/
│   │   ├── test_health.py
│   │   └── test_matters.py          # (future)
│   └── security/
│       ├── test_cross_matter_isolation.py  # CRITICAL security test (future)
│       └── test_prompt_injection.py        # (future)
└── scripts/
    └── test_llm_connection.py       # Verify API keys (future)
```

#### Python Naming Conventions (CRITICAL - Must Follow)
| Element | Convention | Example |
|---------|------------|---------|
| Functions | snake_case | `get_matter`, `process_document` |
| Variables | snake_case | `matter_id`, `is_verified` |
| Classes | PascalCase | `MatterService`, `CitationEngine` |
| Constants | SCREAMING_SNAKE | `MAX_RETRIES`, `LLM_TIMEOUT` |
| Modules/files | snake_case | `citation_engine.py`, `matter_service.py` |

#### Python Code Rules (MANDATORY)
- **Type hints on ALL functions** - both parameters and return types
- **Use `|` union syntax** instead of `Union[]` (Python 3.10+)
- **Use `match` statements** for multi-branch conditionals
- **Async functions** for I/O-bound operations (DB, API calls)
- **Use `structlog`** not standard logging library
- **Pydantic v2 syntax** - `model_validator` not `validator`

```python
# CORRECT
async def get_matter(matter_id: str) -> Matter | None:
    match status:
        case 'active': ...
        case 'archived': ...

# WRONG
def get_matter(matter_id) -> Union[Matter, None]:
    if status == 'active': ...
```

#### FastAPI Rules (MANDATORY)
- **Dependency injection via `Depends()`** for all shared logic
- **Use Pydantic models** for request/response - never raw dicts
- **Path parameters** for resources: `/matters/{matter_id}`
- **Query parameters** for filtering: `?page=1&status=active`
- **Use `HTTPException`** from custom exceptions module
- **Background tasks** via Celery, not FastAPI BackgroundTasks (for long operations)

```python
# CORRECT
@router.get("/matters/{matter_id}")
async def get_matter(
    matter_id: str,
    current_user: User = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
) -> MatterResponse:
    ...

# WRONG
@router.get("/matters")
def get_matter(request: Request):  # Don't use raw Request
    matter_id = request.query_params.get("id")  # Use path params
```

#### API Response Format (MANDATORY)
```python
# Success - single item
{"data": {"id": "uuid", "title": "Matter"}}

# Success - list with pagination
{
  "data": [...],
  "meta": {"total": 150, "page": 1, "per_page": 20, "total_pages": 8}
}

# Error - always include code and message
{
  "error": {
    "code": "MATTER_NOT_FOUND",
    "message": "Matter with ID xyz not found",
    "details": {}
  }
}
```

### Technology Stack Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Python | 3.12+ | Use modern syntax (match statements, type hints) |
| FastAPI | 0.115+ | Async endpoints where beneficial |
| Pydantic | v2.x | `model_validator`, NOT `validator` (v1 syntax) |
| SQLAlchemy | 2.0 | Async support (secondary to Supabase client) |
| Celery | Latest | With Redis broker, priority queues |
| structlog | Latest | For structured JSON logging |
| uv | Latest | Package manager (replaces pip/poetry) |

### Initialization Commands (Use uv NOT pip/poetry)

```bash
# Step 1: Create backend directory
mkdir backend && cd backend

# Step 2: Initialize project with uv
uv init --app
# This creates pyproject.toml, .python-version, README.md, etc.

# Step 3: Add dependencies
uv add fastapi uvicorn[standard] supabase python-dotenv pydantic-settings
uv add celery redis structlog
uv add sqlalchemy[asyncio] alembic
uv add openai google-generativeai google-cloud-documentai

# Step 4: Add dev dependencies
uv add --dev pytest pytest-asyncio httpx ruff mypy

# Step 5: Sync and run
uv sync
uvicorn app.main:app --reload
```

### Previous Story Intelligence (Story 1-1)

**Key Learnings from Story 1-1 Implementation:**
- Frontend successfully initialized with Next.js 16.1.1
- Strict TypeScript configuration applied (`strict: true`, `noUncheckedIndexedAccess`)
- Project runs on localhost:3000
- Environment configuration pattern established (.env.example + .env.local)
- ESLint uses new flat config format (eslint.config.mjs)

**Pattern to Follow from Frontend:**
- Clear separation of concerns (routes, components, lib, stores)
- Environment variables with `.example` template
- Comprehensive .gitignore
- README with setup instructions

**Integration Points with Frontend:**
- Backend will run on localhost:8000 (per architecture)
- Frontend's `NEXT_PUBLIC_API_URL` points to backend
- CORS configuration needed for frontend origin (localhost:3000)
- Both share Supabase credentials (same project)

### Git Intelligence

**Last Commit:** `214cd41 feat: Initialize LDIP project with Next.js frontend`

**Pattern Established:**
- Conventional commit messages (`feat:`, `fix:`, etc.)
- Feature branch workflow expected

### Web Research - Latest Technical Specifics

**FastAPI 0.115+ Best Practices (2025):**
- Use `uv` for package management (10-100x faster than pip)
- Domain/feature-based structure recommended for larger apps
- Service layer for business logic (not in endpoints)
- Async for I/O-bound, sync for CPU-bound operations
- Dependency caching is automatic per request scope

**uv Package Manager:**
- `uv init --app` creates application scaffold
- `uv add` creates venv automatically on first run
- `uv sync` installs all locked dependencies
- Generates `uv.lock` for reproducible builds

Sources:
- [FastAPI Best Practices (GitHub)](https://github.com/zhanymkanov/fastapi-best-practices)
- [Managing Python Projects With uv (Real Python)](https://realpython.com/python-uv/)
- [uv Official Documentation](https://docs.astral.sh/uv/)

### Project Structure Notes

- Backend root is `backend/` at same level as `frontend/`
- Main entry point is `app/main.py`
- All API routes under `app/api/routes/`
- Business logic in `app/services/`
- AI engines in `app/engines/` (empty stubs for now)
- Pydantic models in `app/models/`
- Background workers in `app/workers/`

### Dependencies Reference

**Core (production):**
```toml
[project]
requires-python = ">=3.12"

[project.dependencies]
fastapi = ">=0.115.0"
uvicorn = {extras = ["standard"], version = ">=0.34.0"}
pydantic = ">=2.0.0"
pydantic-settings = ">=2.0.0"
supabase = ">=2.0.0"
python-dotenv = ">=1.0.0"
celery = ">=5.4.0"
redis = ">=5.0.0"
structlog = ">=24.0.0"
sqlalchemy = {extras = ["asyncio"], version = ">=2.0.0"}
alembic = ">=1.14.0"
openai = ">=1.0.0"
google-generativeai = ">=0.8.0"
google-cloud-documentai = ">=2.0.0"
```

**Dev dependencies:**
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.14.0"
]
```

### Anti-Patterns to AVOID

```python
# WRONG: Using any type (TypeScript-equivalent problem)
def get_matter(matter_id):  # Missing type hints
    pass

# WRONG: Using Union instead of |
from typing import Union
def get_matter(matter_id: str) -> Union[Matter, None]:
    pass

# WRONG: Using standard logging
import logging
logger = logging.getLogger(__name__)

# WRONG: Raw dict responses
@router.get("/matters/{matter_id}")
async def get_matter(matter_id: str):
    return {"id": matter_id}  # Should use Pydantic model

# WRONG: Blocking sync code in async context
@router.get("/matters")
async def list_matters():
    # Don't do sync DB calls in async endpoints
    matters = db.execute("SELECT * FROM matters")

# WRONG: Business logic in endpoints
@router.post("/matters")
async def create_matter(data: MatterCreate):
    # Complex logic should be in service layer
    validated = validate_matter(data)
    enriched = enrich_with_metadata(validated)
    saved = save_to_database(enriched)
    return saved
```

### References

- [Source: _bmad-output/architecture.md#Backend-Structure]
- [Source: _bmad-output/architecture.md#Starter-Template-Evaluation]
- [Source: _bmad-output/architecture.md#Naming-Patterns]
- [Source: _bmad-output/architecture.md#API-Response-Patterns]
- [Source: _bmad-output/project-context.md#Python-Backend]
- [Source: _bmad-output/project-context.md#FastAPI-Rules]
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-1.2]

### IMPORTANT: Always Check These Files
- **PRD/Requirements:** `_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md`
- **UX Decisions:** `_bmad-output/project-planning-artifacts/UX-Decisions-Log.md`
- **Architecture:** `_bmad-output/architecture.md`
- **Project Context:** `_bmad-output/project-context.md`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- None required - all tasks completed successfully

### Completion Notes List

- **Task 1**: Initialized Python 3.12 project with uv (`uv init --app --name ldip-backend`)
- **Task 2**: Installed core dependencies: FastAPI 0.128+, uvicorn, Pydantic v2.12+, pydantic-settings, Supabase 2.27+, SQLAlchemy 2.0+, alembic, Celery 5.6+, Redis 7.1+, structlog 25.5+
- **Task 3**: Installed AI/ML dependencies: OpenAI 2.14+, google-generativeai 0.8+, google-cloud-documentai 3.7+
- **Task 4**: Installed dev dependencies: pytest 9.0+, pytest-asyncio 1.3+, httpx 0.28+, ruff 0.14+, mypy 1.19+
- **Task 5**: Created complete project structure matching architecture: app/api/routes/, app/core/, app/engines/, app/services/supabase/, app/models/, app/workers/
- **Task 6**: Created tests directory with conftest.py fixtures and 4 health check tests
- **Task 7**: Created .env.example with all required environment variables and comprehensive .gitignore
- **Task 8**: Initialized alembic with `alembic init migrations`
- **Task 9**: Created multi-stage Dockerfile with Python 3.12, uv package manager, non-root user, and health check
- **Task 10**: Verified: all 4 tests pass, ruff check passes, app imports successfully

### Change Log

- 2026-01-03: Story 1-2 completed - FastAPI backend project initialized with full architecture-compliant structure
- 2026-01-03: Senior Developer Review (AI) - Fixed reproducibility + Celery task wiring + Alembic usability gaps; updated backend README

### Senior Developer Review (AI)

**Reviewer:** Juhi  
**Date:** 2026-01-03  
**Outcome:** Changes applied (fixed HIGH/MEDIUM issues)

#### Issues Found (and fixed)

1. **HIGH** - `backend/uv.lock` and `backend/.python-version` were created but ignored by `backend/.gitignore`, making installs non-reproducible and contradicting the story’s File List.  
   - **Fix**: Updated `backend/.gitignore` to allow tracking these files.

2. **HIGH** - Celery routes referenced task modules that did not exist (`document_tasks`, `engine_tasks`), so routing/autodiscovery was broken by default.  
   - **Fix**: Added minimal placeholder task modules and aligned Celery queue naming.

3. **MEDIUM** - Alembic was scaffolded but not practically usable (placeholder DB URL, no baseline revision, no env override).  
   - **Fix**: Added `DATABASE_URL` override support, conditional async support, and a baseline empty migration.

4. **MEDIUM** - `backend/README.md` was empty (no run/test instructions).  
   - **Fix**: Added setup/run/test/lint/typecheck instructions and Alembic notes.

### File List

**New Files Created:**
- backend/.python-version
- backend/pyproject.toml
- backend/uv.lock
- backend/README.md
- backend/Dockerfile
- backend/.env.example
- backend/.gitignore
- backend/alembic.ini
- backend/migrations/env.py
- backend/migrations/README
- backend/migrations/script.py.mako
- backend/migrations/versions/ (directory)
- backend/migrations/versions/0001_initial.py
- backend/app/__init__.py
- backend/app/main.py
- backend/app/api/__init__.py
- backend/app/api/deps.py
- backend/app/api/routes/__init__.py
- backend/app/api/routes/health.py
- backend/app/core/__init__.py
- backend/app/core/config.py
- backend/app/core/security.py
- backend/app/core/exceptions.py
- backend/app/core/logging.py
- backend/app/engines/__init__.py
- backend/app/engines/base.py
- backend/app/services/__init__.py
- backend/app/services/supabase/__init__.py
- backend/app/services/supabase/client.py
- backend/app/models/__init__.py
- backend/app/workers/__init__.py
- backend/app/workers/celery.py
- backend/app/workers/tasks/__init__.py
- backend/app/workers/tasks/document_tasks.py
- backend/app/workers/tasks/engine_tasks.py
- backend/tests/__init__.py
- backend/tests/conftest.py
- backend/tests/api/__init__.py
- backend/tests/api/test_health.py
- backend/tests/security/__init__.py
