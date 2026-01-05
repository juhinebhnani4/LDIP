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

### Alembic (optional)

This project scaffolds Alembic, but migrations are expected to be managed
primarily via Supabase for the MVP.

To run Alembic locally, set `DATABASE_URL` (example):

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
uv run alembic upgrade head
```

