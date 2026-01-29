# ज Jaanch — Legal Document Intelligence

<p align="center">
  <img src=".playwright-mcp/landing-hero.png" alt="Jaanch — Lawyers miss what matters. We don't." width="700">
</p>

<p align="center">
  <strong>Verify, don't trust.</strong>
</p>

<p align="center">
  <a href="https://jaanch.ai"><img src="https://img.shields.io/badge/Website-jaanch.ai-1a2744?style=for-the-badge" alt="Website"></a>
  <a href="https://app.jaanch.com"><img src="https://img.shields.io/badge/App-app.jaanch.com-c9a227?style=for-the-badge" alt="App"></a>
</p>

**Jaanch** is an *AI-powered legal document intelligence platform* built for Indian lawyers. It reads every page of your case files — 700 pages, 2000 pages, doesn't matter — and finds what humans miss: contradictions, misquoted laws, timeline gaps, and missing documents. Every finding is cited to the exact page and line. No hallucinations. No trust required.

The name "jaanch" (जाँच) is Hindi for *investigation* or *examination*. The product is the investigation — 4 specialized AI engines running in parallel, each doing what a junior associate does at midnight, except it catches everything.

If you want a legal document analysis tool that verifies instead of summarizes, cites instead of guesses, and says "I don't know" instead of making things up — this is it.

[Website](https://jaanch-ai.vercel.app/) · [Backend Docs](./backend/README.md)

## Quick start

Runtime: **Node >= 18** (frontend), **Python >= 3.12** (backend).

```bash
git clone https://github.com/your-org/jaanch.git
cd jaanch

# Frontend
cd frontend
npm install
npm run dev

# Backend (separate terminal)
cd backend
pip install -e .
uvicorn app.main:app --reload
```

Environment variables required for Supabase, OpenAI, Google Cloud, Redis, and Celery. See [Backend README](./backend/README.md) for full setup.

```bash
# Start Celery workers (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Start Celery beat scheduler
celery -A app.workers.celery_app beat --loglevel=info
```

## Why Jaanch (not ChatGPT)?

|  | ChatGPT | Jaanch |
|--|---------|--------|
| **Approach** | Summarizes | Verifies |
| **Citations** | None | Exact page & line |
| **Confidence** | Always high (even when wrong) | Says "I don't know" when unsure |
| **Domain** | Generic | Indian legal documents |
| **Hallucinations** | Prone to them | Evidence-bound only |
| **Act verification** | Not supported | Validates against actual statutes |
| **Documents** | Clean text only | Scanned PDFs, handwritten, multilingual |

## The 4 engines

| Engine | What it does |
|--------|-------------|
| **⏱️ Timeline** | Extracts dates, builds chronology, detects temporal gaps and impossibilities, validates legal sequence ordering |
| **👥 Entities** | Maps people, companies, relationships — resolves aliases, generates relationship graphs, supports entity merging |
| **📜 Citations** | Finds every Act reference, parses India Code format (§123(4)), validates against statute database, discovers missing acts |
| **⚔️ Contradictions** | Spots conflicting statements across documents, classifies contradiction types, scores confidence, ranks by severity |

Each engine runs independently on every document and cross-references results via the **cross-engine correlation service**.

## How it works

```
                    Upload (PDF/ZIP)
                         │
                         ▼
              ┌─────────────────────┐
              │    OCR Pipeline     │
              │  (Document AI +     │
              │   Gemini Validator) │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Chunking Pipeline  │
              │  (Parent-Child +    │
              │   BBox Linking)     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Embedding Pipeline  │
              │  (OpenAI + Vector   │
              │   Store Upload)     │
              └──────────┬──────────┘
                         │
            ┌────────────┼────────────┐────────────┐
            ▼            ▼            ▼            ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
      │ Timeline │ │ Entities │ │ Citations│ │Contradict│
      │  Engine  │ │  Engine  │ │  Engine  │ │  Engine  │
      └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
           │             │            │            │
           └─────────────┼────────────┘────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Cross-Engine       │
              │  Correlation        │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Summary Generation │
              │  (GPT-4)            │
              └──────────┬──────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
     ┌───────────┐ ┌──────────┐ ┌──────────┐
     │ WebSocket │ │  REST    │ │  Export  │
     │ (live)    │ │  API     │ │  (PDF/   │
     │           │ │          │ │  DOCX)   │
     └───────────┘ └──────────┘ └──────────┘
```

## Everything we built so far

### Core platform

- **FastAPI REST API** with 31 endpoint groups: documents, matters, search, chat, citations, contradictions, entities, timeline, verification, summary, anomalies, exports, jobs, dashboard, activity, notifications, library, health, WebSocket, and more.
- **Celery worker system** with 13 task modules: document processing, engine extraction, chunking, verification, evaluation, table extraction, act validation, email, library indexing, maintenance, reasoning archival, embedding migration, quota monitoring.
- **Job tracking system** with progress persistence, stage history, ETA calculation, partial progress for resumable processing, and automatic failure recovery.
- **Real-time WebSocket layer** for matter-level subscriptions: document status changes, job progress, citation extraction progress, feature availability broadcasts, with heartbeats and reconnection support.

### Document processing pipeline

- **OCR pipeline**: Google Document AI → Gemini-based validation → pattern correction → confidence scoring → bounding box extraction.
- **Chunking pipeline**: PDF format detection and routing → parent-child hierarchical chunking → bounding box linking → section indexing → token counting.
- **Embedding pipeline**: text preparation → OpenAI text-embedding-3-small → vector store upload (Pinecone hybrid indexes).
- **Table extraction**: detect and extract structured tables from documents.
- **Document handling**: scanned PDFs, handwritten notes, mixed Hindi/English, ZIP file extraction, bulk uploads.

### AI engines

- **Timeline engine**: date extraction → event classification (8+ legal event types) → entity linking → anomaly detection → legal sequence validation.
- **Entity engine**: named entity extraction → relationship extraction → alias generation → entity consolidation → relationship graph building → correction learning from manual fixes.
- **Citation engine**: citation pattern matching → India Code format parsing → act index lookup → abbreviation resolution → act validation → cross-reference verification → missing act discovery.
- **Contradiction engine**: statement extraction → statement comparison → semantic similarity scoring → conflict classification (4+ types) → evidence confidence scoring → severity ranking.
- **Cross-engine correlation**: links entities to timeline events, verifies citation consistency, checks for contradictions in cited material, detects multi-engine consistency issues.
- **Summary generation**: GPT-4 powered executive summaries with subject matter, key issues, current status, parties information, and content safety policing.

### RAG & search

- **Hybrid search**: BM25 (keyword) + semantic vector search with Reciprocal Rank Fusion (RRF).
- **Reranking**: Cohere Rerank v3.5 for precision.
- **Global search**: cross-matter search across all user documents.
- **Alias-expanded search**: automatically expands entity aliases in queries.
- **Query caching**: semantic query normalization + Redis-backed result caching.
- **Safety**: prompt injection prevention and SafeGuard integration.

### AI/ML integrations

- **GPT-4o**: main reasoning, user-facing chat, accuracy-critical tasks.
- **Gemini 2.0 Flash**: fast inference, OCR validation, screening.
- **OpenAI Embeddings**: text-embedding-3-small for vector search.
- **Cohere Rerank v3.5**: search result reranking.
- **Multi-model failover**: automatic provider switching on failure.

### Frontend application

- **Next.js 16 + React 19** SPA with App Router.
- **16 Zustand stores**: matter, chat, Q&A panel, upload, upload wizard, workspace, verification, processing, background processing, notifications, activity, split view, PDF split view, features, library, inspector.
- **370+ components** across: authentication, document management, upload wizard, citations browser, contradiction explorer, entity graph (XY Flow + Dagre), timeline visualization (list + horizontal + multi-track), summary editor, verification workflow, chat/Q&A with streaming, PDF viewer with bounding box overlay, export builder with drag-to-reorder, dashboard, admin panel, settings, help system, onboarding wizard.
- **Export system**: PDF, DOCX, HTML with template selection, custom section ordering, live preview, and section-specific renderers (summary, findings, timeline, entities, citations, contradictions).
- **PDF viewer**: split-view, fullscreen, bounding box overlay for citation highlighting.
- **Entity graph**: interactive force-directed graph with XY Flow, Dagre layout, entity merging, and merge suggestions.

### Infrastructure & operations

- **Circuit breakers** (per-service): OpenAI, Gemini, Cohere, Document AI — exponential backoff with jitter, graceful degradation, correlation ID tracking.
- **Rate limiting** (5 tiers): CRITICAL (30/min), SEARCH (60/min), STANDARD (100/min), READONLY (120/min), HEALTH (300/min) — per-user with IP fallback, Redis-backed for distributed deployments.
- **Health checks**: liveness (`/health`), readiness (`/health/ready`), circuit breaker status, rate limit status, dependency health monitoring.
- **Caching**: Redis connection pooling, query result caching, session management, matter metadata caching, summary caching (1-hour TTL).
- **Distributed locking**: Redis-backed locks with expiration for deduplication and rate limit enforcement.
- **Cost tracking**: per-request LLM cost calculation, provider-level tracking (OpenAI, Gemini, Cohere, Claude), matter-level rollup, batch aggregation, admin dashboard.
- **Email**: Resend API integration, async Celery-based delivery, HTML templates.
- **Observability**: structlog structured logging, correlation IDs, SSE error tracking, WebSocket connection metrics, processing stage history.
- **Security**: JWT authentication, matter-level RBAC, WebSocket auth, Supabase RLS multi-tenant isolation.

### Testing

- **E2E tests** (Playwright): 9 spec files covering authentication, matter creation, document management, chat/Q&A, quick workspace, search navigation, workspace tabs, email notifications, security foundations. 11 page objects with fixtures.
- **Unit + integration tests** (pytest): 161 test files covering API routes, engine tests (citation, contradiction, timeline, orchestrator), service tests (chunking, RAG, OCR, safety, memory, MIG), integration tests, security tests, and benchmarks.

## Project structure

```
jaanch/
├── frontend/                # Next.js application
│   ├── src/
│   │   ├── app/                # App Router pages (auth, dashboard, matter workspace)
│   │   ├── components/
│   │   │   ├── ui/             # 48 base UI components (Radix + Tailwind)
│   │   │   └── features/       # 322 feature components across 26 modules
│   │   ├── stores/             # 16 Zustand stores
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # Utilities, API client, constants
│   │   └── types/              # TypeScript type definitions
│   └── tests/
│       └── e2e/                # Playwright E2E tests (9 specs + 11 page objects)
│
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/         # 31 API endpoint groups
│   │   ├── core/               # Config, security, rate limiting, circuit breakers
│   │   ├── engines/            # 4 AI engines (timeline, citation, contradiction, cross-engine)
│   │   ├── services/           # 107 services (RAG, OCR, chunking, entities, etc.)
│   │   ├── models/             # Pydantic models
│   │   └── workers/
│   │       └── tasks/          # 13 Celery task modules
│   └── tests/                  # pytest test suite (161 test files)
│
└── docs/                    # Documentation and planning
```

## Team

Jaanch was built by **Juhi Nebhnani** and **Siddhi Maheshwari**.

Part of the [100xEngineers](https://100xengineers.com) program.

- [jaanch.ai](https://jaanch-ai.vercel.app/)
