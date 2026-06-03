# LDIP Gap Audit — 2026-05-26

**Source**: Audit run against the best-practice claims in `AI-ML-INTERVIEW-ANSWERS.md` (50 questions, web-grounded 2024–2026). Original audit was Phase 1 only and presented fix sketches as if Phase-2-verified. They weren't. Phase 2 verification was run the same day (2026-05-26) and **both P1 fix sketches were refuted**. The corrected fix designs replace the original sketches inline; the meta-analysis of why the original sketches were wrong is in the final section.

**Correction surfaced during audit**: LDIP embeddings are **OpenAI `text-embedding-3-small`** (1536-dim, `backend/app/services/rag/embedder.py:36-38`), not Gemini. Gemini Flash is the contradiction *screener* (`comparator.py:660`); GPT-4o is the *adjudicator* (`comparator.py:748`). Voyage `voyage-law-2` A/B harness is wired (`config.py:42-60`) but not promoted.

**Phase 2 corrections at a glance** (see inline edits + final section):
- **P1 #1 (RAG faithfulness gate)**: per-sentence NLI rejected — repeats the pattern in BUGS.md:111-112 (inline shadow testing rejected for same Gemini-bucket starvation) and inherits the Item-14 (BUGS.md:482) NLI-deferred-for-Indian-legal-text concern. Replaced with whole-answer entailment + dedicated rate-limit bucket precondition.
- **P1 #2 (sync Supabase in async routes)**: exemplar was wrong (`bounding_boxes.py` uses `asyncio.to_thread`, not `run_in_threadpool`, and is itself a half-conversion). Cited offender `documents.py:1365` is already wrapped (line 1405). `scaling-bottleneck-ordering` memory ranks event-loop blocking outside top 4 — measure first. Route-layer wrapping IS the ARCH-001 fork the original audit warned against. Replaced with service-layer design + measure-first precondition.

---

## Phase 1 — System map

- **API tier**: FastAPI on Railway (`LDIP` service). Routes declared `async def` but use the **synchronous** Supabase client (`from supabase import Client` — `backend/app/services/chunk_service.py:16` + 13 route files), so DB calls block the event loop.
- **Worker tier**: `ldip-worker` runs two gevent Celery processes via `backend/start-worker.sh:61-84` — `fast@%h -Q default,llm` (40 greenlets) + `heavy@%h -Q heavy,low` (10 greenlets). Beat in restart loop (`start-worker.sh:45-56`). `worker_count=1` default → in-process rate limiter (`backend/app/core/config.py:324`, `llm_rate_limiter.py:639`).
- **LLM stack**: embeddings = OpenAI `text-embedding-3-small` 1536-dim; screening = Gemini Flash @ T=0.1; adjudication = GPT-4o @ T=0.1, `response_format=json_object`. Rate limiter is `asyncio.Semaphore` + min-delay, separate caps per provider (`llm_rate_limiter.py:60-71`).
- **Data**: Supabase Postgres single primary, ~100 migrations. `chunks` has HNSW(m=16, ef=64) cosine + GIN on entity/bbox arrays (`20260106000002_create_chunks_table.sql:41-49`); `llm_costs` indexed on matter/provider/op/doc/created_at (`20260122000003_create_llm_costs_table.sql:75-96`). **No table partitioning anywhere**. `MATERIALIZED VIEW` used only in `unit_economics_views` (2 files). Daily/monthly cost rollups are plain `VIEW`s (`llm_costs_table.sql:103-130`).
- **Architectural debts**: ARCH-001 (parallel small/chunked pipelines), ARCH-002 (mitigated by 2-process worker split), ARCH-003 (lock release at 14 call sites — explicitly NOT a "fix locally" target). N=1 scaling is intentional per `scaling-plumbed-not-pressurized` memory.

---

## Phase 2 — Gap audit

### REAL GAPS (P1)

#### [LLM Q8] No multi-signal hallucination detection on the user-facing RAG/Q&A path
- **LDIP today**: `backend/app/engines/rag/generator.py:5-9,179` says answers are "grounded" but the only post-hoc check is RAGAS faithfulness as an **offline evaluator** (`backend/app/services/evaluation/ragas_evaluator.py:96-103,194-235`, invoked from `evaluation_tasks.py:333` and admin endpoint `routes/evaluation.py:129` only). Live Q&A responses go out with no per-answer faithfulness / NLI-grounding / semantic-entropy gate. Soft "grounding rules" exist as prompt-level instructions only (`engines/rag/prompts.py:42`). Citation verification (`backend/app/engines/citation/verifier.py:138-186`) is for Act citations in case files, not RAG answer claims. Frontend renders the whole answer as one `ReactMarkdown` string (`frontend/src/components/features/chat/ChatMessage.tsx:113-115`) — no per-sentence DOM scaffold today.
- **Best practice**: stack SelfCheckGPT / semantic entropy / NLI against retrieved evidence / citation verification; ensemble, don't trust a solo judge.
- **Why it matters**: legal Q&A grounded on retrieved chunks is the highest-stakes user surface — a confidently wrong fabricated cite is the canonical liability incident.
- **Prior rejections / deferrals to honor** (surfaced by Phase 2):
  - **BUGS.md:111-112** explicitly REJECTED inline shadow testing on the screening path because hostile review found it doubles latency and starves the shared Gemini rate-limit bucket. Per-sentence NLI repeats that exact pattern at 6× cost.
  - **BUGS.md:482 (Item 14)** explicitly DEFERRED NLI integration on accuracy grounds for Indian legal text ("never seen legal phrasing"). An LLM-judge variant sidesteps the model-availability blocker but inherits the accuracy concern.
- **Survivable fix** (replaces the original "per-sentence NLI" sketch):
  1. **Whole-answer entailment, not per-sentence**: one extra Gemini Flash call per answer with `[full_answer, concatenated_retrieved_chunks]` returning `{verdict, unsupported_spans?}`. ~2× current per-answer Gemini load instead of 6–10×.
  2. **Dedicated rate-limit bucket as a precondition** — do NOT ship until ARCH-002 partitioning gives the verifier its own slot; otherwise it starves contradiction/summary tasks. This is a structural change that must land first.
  3. **New `operation=` name** for `llm_costs` (`rag_answer_verification`) so dashboards see it without polluting `rag_generation` metrics.
  4. **Banner-style UI**, reusing the existing `searchNotice` slot at `ChatMessage.tsx:189-199` — single "unsupported claim" warning, NOT per-sentence chips (no DOM scaffold for that today).
  5. **Calibration plan before auto-blocking**: log verdicts without gating answers for N weeks, label a sample, measure precision/recall against legal SMEs, then decide. Do not ship with auto-rejection until calibration data exists.
- **What changed from the original sketch**: original said "no new infra; one engine module + one prompt + one frontend chip." That was wrong on all three counts — needed rate-limit bucket (infra), distinct cost-tracking operation (more plumbing), and a wire-format / UI shape change since per-sentence rendering doesn't exist. Calibration was also missing.

#### [Python Q3 / Q10] Sync Supabase client inside `async def` FastAPI routes
- **LDIP today** (CORRECTED): routes declared `async def` but the actual wrap pattern in the repo is **`asyncio.to_thread`**, not `run_in_threadpool` (0 hits across `backend/app`). Wrapping is **inconsistent ad-hoc at call sites**, NOT centralized:
  - ~30 `asyncio.to_thread` sites total across `backend/app` (e.g. `engines/orchestrator/orchestrator.py:325,427`, `engines/contradiction/statement_query.py` (5×), `services/contradiction_list_service.py` (5+×)).
  - `bounding_boxes.py` is a HALF-conversion: line 355 wraps ONE sync Supabase call; lines 379 / 396 / and the other `async def` routes in the same file (`get_document_bounding_boxes`, `get_page_bounding_boxes`, `get_bboxes_by_ids`) call sync services unwrapped. Cannot be used as the canonical exemplar.
  - Originally-cited offender `documents.py:1365` is **already wrapped** at line 1405 (`await asyncio.to_thread(document_service.list_documents, ...)`). The real offender is `documents.py:1138` (`upload_document` — calls `storage_service.upload_file` + `document_service.create_document` sync at lines 1285, 1294), but it also does file I/O so threadpool helps less than expected.
  - `chunk_service.py` already has the dual-surface trap: `save_chunks` is `async def`, `get_chunks_for_document` is sync; workers call **both** surfaces (`engine_tasks.py:172,178`). This is the WPS-001-L5 / LLM-006 nested-asyncio failure shape already documented.
  - `supabase-py` `AsyncClient` is installed (2.27.0, `backend/pyproject.toml:34`) but **zero usages** in the repo.
- **Best practice**: async code must not call blocking I/O; wrap with `asyncio.to_thread`, or use an async DB driver.
- **Why it matters (CORRECTED severity)**: `scaling-bottleneck-ordering` memory ranks 10× bottlenecks as **Gemini quota → worker replicas → Supabase pool → API memory** — event-loop blocking is NOT in the top 4. The original audit's claim that this "sits before the documented Gemini-quota bottleneck" was wrong. Measure P95/P99 under realistic concurrency on Railway **before** any code change; if Gemini quota saturates first, this delivers no user-visible win and burns risk budget that should go to ARCH-002.
- **Survivable fix** (replaces the original "one PR at a time at the route layer" sketch — which was itself the ARCH-001 fork the audit warned about):
  1. **Measure first**. P95/P99 under load before touching code. If event-loop blocking isn't the bottleneck, defer entirely.
  2. **If real**: design lands first, not one-PR-at-a-time. Pick one of:
     - **Service-layer wrap** (recommended): convert hot service methods to `async def` that internally `await asyncio.to_thread(self._sync_impl, ...)`. Workers keep calling `_sync_impl` directly. Routes never wrap. Treat as a tracked debt with an explicit exit criterion ("done when all sync surfaces are private"). The dual-surface during migration is accepted as bounded transient state, not permanent fork.
     - **Adopt `AsyncClient`**: cleaner structural fix but introduces a third async stack (uvloop in API, gevent in workers, asyncio AsyncClient inside both). LLM-006 precedent says be very careful.
  3. **NEVER**: route-layer wrapping per-PR. That ships a P3 sticky-note ("every async route author must remember to wrap every Supabase call") + a P1 fork (same service called wrapped from routes, unwrapped from workers).
- **What changed from the original sketch**: original named the wrong primitive (`run_in_threadpool`), the wrong exemplar (`bounding_boxes.py` is a half-conversion, not a clean pattern), the wrong offender line (`:1365` is already wrapped), and the wrong cadence (per-PR at route layer = exact ARCH-001 fork the same paragraph warned against). It also overstated the severity by claiming this bottleneck fires before Gemini quota — `scaling-bottleneck-ordering` says otherwise.

### REAL GAPS (P2)

#### [SQL Q5] Cost-dashboard daily/monthly rollups are plain views, not matviews
- LDIP today: `llm_costs_daily` and `llm_costs_monthly` are `CREATE OR REPLACE VIEW` (`supabase/migrations/20260122000003_create_llm_costs_table.sql:103-130`); every dashboard hit re-aggregates the full `llm_costs` table.
- Fix sketch: convert monthly rollup to matview refreshed hourly by a beat task. Single migration + one beat entry. Cluster 4 (worker stability) gives a stable beat to hang this off.

#### [SQL Q9] `llm_costs`, `processing_jobs`, `chunks` will need range partitioning before scale
- LDIP today: zero migrations contain `PARTITION BY`. All hot append-only tables are monolithic.
- Fix sketch: not urgent at current volume (per `scaling-bottleneck-ordering` memory). Flag for when `llm_costs` crosses ~10M rows: monthly range-partition on `created_at` becomes the cheapest fix. Track as deferred; do not preempt per `scaling-plumbed-not-pressurized`.

#### [ML Q10] No embedding drift / contradiction-accuracy drift monitoring
- LDIP today: `services/evaluation/` has RAGAS + A/B + regression detector for **retrieval quality** under deliberate experiments (`baseline_service.py`, `regression_detector.py`), but nothing monitors **production input drift**. `cost_tracking.py` tracks $/op only.
- Fix sketch: piggyback on `llm_costs.metadata` ground-truth metadata already deployed for contradictions (the 2026-05-14 metadata-persist entry stored `comparison_result` / `confidence` / `reasoning_preview`). Daily beat task computes distribution of (screening_result × escalation_outcome), alerts on >25% drift week-over-week. No new tables; one new task.

#### [Python Q4 / Q6] gevent worker handles both LLM I/O (good) and OCR/Docling CPU work (bad)
- LDIP today: heavy worker is `--pool=gevent --concurrency=10` (`start-worker.sh:75-83`) and runs both OCR (HTTP-bound to Document AI — gevent-friendly) and Docling layout + chunking (CPU-bound under the GIL). Greenlets serialize on CPU.
- Fix sketch: split heavy queue further into `cpu` (prefork, concurrency=2) for Docling and `io` (gevent, concurrency=10) for OCR/embedding/LLM. Same `start-worker.sh` shape; one more process. Watch ARCH-002 — must ship the worker definition with the queue.

### REAL GAPS (P3)

#### [Python Q7] No profiling artifacts checked in, no on-demand profiler in admin
- LDIP today: `py-spy` / `cProfile` / `scalene` searched — only one `tracemalloc` reference in `backend/app/services/pdf_chunker.py`. Performance tuning is reactive (BUGS.md driven).
- Fix sketch: add `py-spy` to the worker Dockerfile (~5 MB), wire an admin endpoint that triggers `py-spy dump --pid` on worker and returns the flamegraph. One-time work; pays for itself on the first stuck-worker incident.

---

## JUSTIFIED DEVIATIONS — not gaps

- **LLM Q1–Q4, Q6, Q7, Q9 (LLM serving internals)** — N/A; LDIP uses API providers, doesn't self-host weights.
- **SQL Q3 (sharding)** — single Supabase primary at N=1 is documented in `scaling-plumbed-not-pressurized`.
- **SQL Q8 (Airflow/dbt/Feast/MLflow ML stack)** — LDIP is RAG-on-API, not a feature-store ML system. Calling this a gap would itself be an ARCH-PATTERNS P2 violation (parallel paths).
- **SQL Q4 (deadlocks)** — pipeline coordination uses Redis advisory locks + reconciler shape (ARCH-003), not row-level `FOR UPDATE`. No contention → no deadlock retries needed.
- **DL Q9 (T=0.1 on GPT-4o adjudication)** — low T is correct for deterministic adjudication where consistency matters more than diversity.
- **LLM Q5 (RAG vs fine-tune)** — LDIP is pure RAG; fine-tuning Indian-legal voice would be premature optimization.
- **LLM Q10 (embedding model — text-embedding-3-small)** — Voyage `voyage-law-2` upgrade path already built (`config.py:42-60`, migration `20260219000003`), just not promoted.

## NOT APPLICABLE

- LLM Q1 (KV cache), Q2 (MoE), Q3 (decode internals), Q4 (vLLM serving), Q6 (FlashAttention), Q7 (speculative), Q9 (quantization) — no self-hosted weights.
- ML Q1–Q9, DL Q1–Q8, Q10 — interview-trivia, no LDIP code surface.
- SQL Q2 (OLTP/OLAP), Q6 (CAP), Q7 (star schema), Q10 (Kafka streaming) — single OLTP store, no analytics warehouse, no streaming ingestion.
- Python Q1, Q2, Q5, Q8, Q9 — language-trivia, no LDIP-specific gap.

---

## Bottom line — top 3 to act on, in order (REVISED after Phase 2)

1. **Production drift monitoring on contradiction screening (ML Q10)** — now the cheapest win: mostly free given 2026-05-14 metadata persistence, one beat task, no LLM-cost increase, no architectural debt. Original audit ranked this #3; Phase 2 promoted it to #1 because both prior P1s have preconditions that must land first.
2. **Whole-answer RAG entailment gate (LLM Q8 — corrected design)** — still the highest-stakes correctness gap, BUT requires ARCH-002 rate-limit partitioning as a hard precondition (per BUGS.md:111-112 prior rejection) AND a calibration-before-auto-block plan (per BUGS.md:482 Item 14 deferral). Don't ship the inline gate until both are done.
3. **Measure-then-design for sync-Supabase async-route blocking (Python Q3 — corrected)** — run P95/P99 measurement first; if event-loop blocking isn't the actual bottleneck (per `scaling-bottleneck-ordering`), defer entirely. If real, the design (service-layer wrap with explicit exit criterion) lands as one PR before any route conversions.

Everything else (matviews, partitioning, profiler, CPU-pool split) is real but P2/P3 — wait behind Cluster-7 ARCH debts.

---

## Meta-analysis: why the original audit's P1 fix sketches were wrong

Both P1 sketches were refuted by Phase 2 the same day. The failure was not in *identifying* the gaps (the diagnostic part of the audit holds up) — it was in *proposing fixes* without doing Phase 2 work. Three concrete patterns:

### Pattern 1: "Fix sketch" lines smuggled Phase 2 deliverables into a Phase 1 doc

The audit template put a `**Fix sketch**:` line directly under each gap. That framing makes the sketch feel like part of the observation, but a fix sketch IS a Phase 2 design proposal — it requires re-reading the cited code, searching BUGS.md for prior rejections, and tracing the call chain. The audit agent did Phase 1 correctly but the fix-sketch lines were generic best-practice extrapolations ("inline NLI judge", "wrap in `run_in_threadpool`"), not LDIP-verified designs. As orchestrator I compounded this by presenting the audit as decision-ready without running Phase 2 myself.

### Pattern 2: Stale / hallucinated evidence in the sketches

- "An async wrapper pattern already exists in `bounding_boxes.py` using `run_in_threadpool`" — the file uses `asyncio.to_thread` (a different primitive) at exactly one site, and is itself a half-conversion. The exemplar was wrong on the primitive AND wrong on the cleanliness claim.
- "Routes declared `async def` (`documents.py:1138, 1365`)" — `:1365` is already wrapped (line 1405). The audit cited the line as an offender without re-reading it.

The first error looks like a memory hallucination from generic Python async best-practice (the FastAPI docs feature `run_in_threadpool`); the second looks like the audit agent grep'd for `async def` + sync Supabase imports without verifying each hit. Either way: the Trust Hierarchy from CLAUDE.md says the actual code wins over assumptions, and that step was skipped on the fix-sketch lines.

### Pattern 3: Didn't search BUGS.md / memory for prior rejections of the proposed shape

- BUGS.md:111-112 explicitly REJECTED inline shadow testing on the screening path for the same Gemini-bucket-starvation reason that applies to per-sentence NLI. Not found.
- BUGS.md:482 (Item 14) explicitly DEFERRED NLI integration on accuracy grounds for Indian legal text. Not found.
- `scaling-bottleneck-ordering` memory says event-loop blocking is not in the top-4 10× bottlenecks. The audit cited the opposite. Not consulted.

Each of these would have been found by one targeted search before writing the sketch. None were done.

### The shared root cause

Same shape as `verification-failures.md` (theory built from code reading, contradicted by data not consulted) and the Railway-2026-04-22 incident (generic cloud-cost advice that conflicted with existing architecture). The blast-radius SKILL.md was written specifically to prevent this and was followed for Phase 1 of the audit — but the "fix sketch" lines escaped the protocol because they weren't framed as a separate Phase 2 task.

### How to prevent recurrence

Any future audit must either:
- (a) Omit fix sketches entirely (deliver gap identification + severity only; leave fix design as a separate task), OR
- (b) Label each fix sketch as **"unverified — needs Phase 2"** and refuse to act on it until Phase 2 has been run against that specific sketch with BUGS.md + memory + live-code checks.

As orchestrator: never present an audit as decision-ready when the fix sketches haven't been Phase-2-verified. Spawn one Phase 2 agent per P1/P2 sketch before claiming the audit is actionable. This was the step skipped on 2026-05-26 morning.
