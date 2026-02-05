## LDIP Backend (FastAPI)

### Prerequisites

- Python **3.12+** (see `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) installed

### Setup

```bash
cd backend
cp .env.example .env
uv sync --dev
```

### Run the API (dev)

```bash
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health endpoints:
- `GET /api/health`
- `GET /api/health/ready`
- `GET /api/health/live`

### Run tests

```bash
cd backend
uv run pytest
```

### Lint + typecheck

```bash
cd backend
uv run ruff check .
uv run mypy .
```

### Run Celery Worker

**Windows (recommended):**
```bash
cd backend
uv run celery -A app.workers.celery worker --pool=solo -Q default,ocr,entity_extraction,citation_extraction,date_extraction -l INFO
```

**Linux/macOS (production):**
```bash
cd backend
uv run celery -A app.workers.celery worker --pool=gevent -c 50 -Q default,ocr,entity_extraction,citation_extraction,date_extraction -l INFO
```

> **Note:** On Windows, use `--pool=solo` to avoid gevent monkey-patching issues with asyncio. Solo pool processes one task at a time, but API rate limits are the actual bottleneck, so concurrency doesn't matter much.

### Run Celery Beat (scheduler)

```bash
cd backend
uv run celery -A app.workers.celery beat -l INFO --pidfile= --schedule=/tmp/celerybeat-schedule
```

### Alembic (optional)

This project scaffolds Alembic, but migrations are expected to be managed
primarily via Supabase for the MVP.

To run Alembic locally, set `DATABASE_URL` (example):

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
uv run alembic upgrade head
```







