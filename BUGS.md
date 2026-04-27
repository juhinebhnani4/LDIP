# BUGS.md — Consolidated Bug Tracker

**Last updated**: 2026-04-22 (INF-011 updated with real Railway billing data — $34/month at idle, deep research on cost drivers and rejected fixes)
**Total bugs**: 67 | **Fixed**: 29 | **Open**: 34 | **Not Reproducible**: 2 | **Not a Bug**: 1 | **Resolved**: 1
**Sources**: 4 bug report files + 2 debugging sessions + 2 architectural reviews (2026-04-13) + 1 pipeline audit (2026-04-17) + 1 E2E verification (2026-04-17)

### Legend
| Field | Values |
|-------|--------|
| **Severity** | P0 (Critical), P1 (High), P2 (Medium), P3 (Low) |
| **Status** | OPEN, FIXED, NOT CURRENTLY REPRODUCIBLE, RESOLVED, NOT A BUG |
| **Source** | File or session where the bug was first reported |

---

## Priority Roadmap (2026-04-21)

> Sequenced from first principles after E2E verification (4 docs, 2 matters, both pipeline paths) + freemium competitive analysis (DraftBot Pro, Harvey, CaseMine, Indian legal tech market). Full research in [E2E-FINDINGS-2026-04-17.md](E2E-FINDINGS-2026-04-17.md).

### Why this order — the business context

**Goal**: Launch a freemium model — 3 documents/month free (full pipeline), ₹999/mo for 25 docs, ₹1,999/mo for unlimited. DraftBot Pro (102K+ lawyers, ₹999/mo) gives away legal research (zero-cost search) and charges for AI drafting. Jaanch's differentiator is **automated cross-document contradiction detection** — nobody else does this automatically, not Harvey, not CoCounsel. But it's also our most expensive feature.

**The aha moment for conversion**: Lawyer uploads 2-3 documents → Jaanch shows "Found 3 contradictions between Respondent's Affidavit and Rejoinder" → lawyer is hooked → document 4 requires upgrade. This only works if: (a) the pipeline is fast enough that they don't leave, (b) the product looks polished during those 3 docs, (c) the cost per free user is sustainable.

**Current per-document cost (from E2E, 4 real Indian legal documents)**:

| Stage | Cost/doc | % of total | Notes |
|---|---|---|---|
| OCR (Document AI) | $0.02-0.08 | ~3% | $1.50/1000 pages |
| Chunking + validation | ~$0.00 | 0% | CPU only |
| Embeddings (Voyage) | $0.01-0.03 | ~2% | Per-chunk |
| Entity extraction (Gemini) | $0.03-0.10 | ~5% | Per-chunk LLM |
| Citation extraction (Gemini) | $0.05-0.15 | ~7% | Per-chunk LLM |
| Date extraction (Gemini) | $0.02-0.08 | ~3% | Per-chunk LLM |
| **Contradiction detection** | **$0.33-1.48** | **60-75%** | O(n^2) pairs, Gemini Flash + GPT-4o |
| Summary (3x GPT-4o) | $0.05-0.15 | ~5% | 3 parallel calls |
| **TOTAL** | **$0.50-2.00** | 100% | Dominated by contradictions |

**The math**: 3 free docs/month at current cost = $1.50-6.00/user/month. At 1000 free users = $1,500-6,000/month. **Unsustainable.** After contradiction optimization (Tier 1 item #1): cost drops to $0.15-0.50/doc → 3 free docs = $0.50-1.50/user/month → 1000 users = $500-1,500/month. **Sustainable** if 5-10% convert at ₹999/mo (= ₹50K-100K/month revenue).

**Prerequisite chain**:
```
Tier 1 (speed + polish)  ───┐
Tier 2 (reliability)     ───┤──→ Free tier launch ──→ Revenue
Free tier gate (~1 day)  ───┘         ↓
                              ₹999/mo (25 docs)
                              ₹1,999/mo (unlimited)
                                      ↓
Tier 3 (structural)      ──→ Enables safe iteration at scale
Tier 4 (long-term)       ──→ After free tier is live + generating data
```

---

### Tier 1 — Speed + Polish (weeks 1-4, prerequisite for free tier)

All items are leaf-node changes — they don't touch the orchestration layer, worker topology, or state management. Safe, contained, highest user-visible impact.

#### 1. Contradiction detection optimization — REVISED after deep-dive (2026-04-21)

**Bug IDs**: E2E-004, E2E-005 | **Effort**: phased (see below) | **Files**: primarily `backend/app/engines/contradiction/comparator.py`, `backend/app/core/llm_rate_limiter.py`, `backend/app/core/config.py`

##### Live data from production (queried 2026-04-21)

| Metric | Value | Source |
|--------|-------|--------|
| Gemini screening calls | 6,323 | `llm_costs` table |
| GPT-4o analysis calls | 1,888 | `llm_costs` table |
| GPT-4-turbo calls (legacy) | 141 | `llm_costs` table |
| **Escalation rate** | **32.1%** (2,029 / 6,323) | derived |
| Contradictions found (stored) | 181 | `statement_comparisons` table |
| **GPT-4 → contradiction rate** | **8.9%** (181 / 2,029) | derived |
| **GPT-4 → NOT contradiction** | **91.1%** (1,848 wasted calls) | derived |
| Gemini screening cost | $3.05 ($0.000483/call) | `llm_costs` |
| GPT-4o cost | $12.42 ($0.006579/call) | `llm_costs` |
| GPT-4-turbo cost | $3.73 ($0.026487/call) | `llm_costs` |
| **Total contradiction cost** | **$19.21** | sum |
| **Wasted GPT-4 spend** | **~$11.30** (91.1% of $12.42) | derived |

**Key finding**: 65% of total contradiction cost is GPT-4o, and 91% of GPT-4o calls return "not a contradiction." The cost problem is escalation volume, not screening cost. Optimizing Gemini screening speed/cost saves ~$3; reducing wasted GPT-4o escalations saves ~$11.

##### Original plan vs revised plan

**REJECTED approaches** (with reasons from deep-dive analysis):

1. **~~Batch Gemini screening (10 pairs per call)~~** — REJECTED. Contradiction pairs for the same entity share overlapping text (same affidavit paragraphs, same witness statements). Batching causes context bleed: the model confuses statement A from pair 3 with statement B from pair 7. Errors become correlated instead of independent. Research on batched classification assumes independent items — contradiction pairs within the same entity are NOT independent. High-mention entities like "Nirav Jobalia" (15+ mentions = 105 pairs) would dominate batches, starving attention for other entities.

2. **~~Flash → Flash Lite for screening~~** — DEFERRED until shadow testing data exists. Flash Lite is less capable; if it escalates more pairs (confidence < threshold), net cost INCREASES because each escalation costs $0.0066 (GPT-4o). Worse: if Flash Lite says "consistent" at 0.6 confidence where Flash would have said "needs_review" at 0.4, a real contradiction slips through entirely. The product's core value is "we found what you missed" — a false negative kills conversion. No quality data exists for Flash Lite on legal contradiction screening.

3. **~~Embedding pre-filter at >0.98~~** — DEFERRED/HIGH RISK for the high-end filter. "Property valued at 50 lakhs" vs "property valued at 80 lakhs" could have cosine similarity 0.97-0.99 depending on chunk length. This is exactly the contradiction type that matters most in Indian legal documents (amount mismatches in affidavits). Low-end filter (<0.15) is safer but saves fewer pairs.

4. **~~Bump DEFAULT_BATCH_SIZE from 5 → 25~~** — UNSAFE AT SCALE without per-engine rate limiting. The Gemini rate limiter (`llm_rate_limiter.py:62`, `max_concurrent=10`) is a **global singleton** shared by ALL engines (entity extraction, citation extraction, date extraction, contradiction screening). Bumping to 25 concurrent for contradictions starves other engines when multiple documents process simultaneously. At 4 concurrent docs × 25 slots each = 100 greenlets needed, but the worker only has 50 (`--pool=gevent --concurrency=50`). This makes ARCH-002 (single worker) worse, not better. Requires per-engine semaphore partitioning before safe to increase.

**REVISED approach — phased, data-driven**:

**Phase 1: Ship immediately (zero risk, ~1 day)**
- **Skip 1-mention entities** in `_generate_statement_pairs()`. Can't form a pair with 1 statement. `itertools.combinations` already generates 0 pairs, but this skips the function call overhead and pair-generation loop entirely. ~5 lines of code. Zero quality risk.
- **Persist screening metadata to `llm_costs.metadata`**: Write `{"screening_result": "consistent", "screening_confidence": 0.62, "was_escalated": true}` for every screening call. Currently metadata is empty (`{}`) for all 6,323 screening records. This data is required to tune the confidence threshold — without it we're guessing. Worker logs rotate on Railway and the confidence distribution data is lost.

**Phase 2: Tune threshold (after Phase 1 data, ~1 day)**
- **Lower `confidence_threshold`** from 0.5 → TBD (likely 0.35) based on Phase 1 metadata. The `confidence_threshold` (`comparator.py:452-454`, `config.py`) controls when Gemini's "consistent/unrelated" verdict is trusted vs escalated to GPT-4o. At 0.5, we escalate 32% of pairs and 91% of those are wasted. If most wasted escalations are Gemini saying "consistent" at 0.45-0.49, lowering to 0.35 could cut GPT-4o calls by 30-50%. **This is potentially the single biggest lever — a config change that saves ~$5-6 of the $19.21 total.**

**Phase 3: Safe parallelism (after beat isolation, ~1 day)**
- **Reduce `min_delay_seconds`** from 0.2 → 0.05 in `llm_rate_limiter.py:63`. Mild speedup, no concurrency increase, safe at any scale.
- **Bump `DEFAULT_BATCH_SIZE`** from 5 → 10-12 (NOT 25). Stay within the global `max_concurrent=10` semaphore. Gets ~2x speed without starving other engines. Only safe AFTER beat process isolation (Tier 2 #5) so increased load can't starve the scheduler.

**Phase 4: Research (parallel, no code changes)**
- **GPT-4o replacement research**: The actual cost bottleneck is GPT-4o at $0.0066/call for full analysis. At scale (400 docs/month), this is $2,500-5,000/month — more than revenue from 50 paying users at ₹999. Research Claude Haiku ($0.00025/1K input), Gemini Pro, or fine-tuned smaller model as a replacement for the full analysis tier. This is the 10x lever; everything else is 2x at best.
- **Shadow test Flash Lite**: Run both Flash and Flash Lite on the same pairs, compare results without using Flash Lite results. Collect quality data before switching.

**Expected result (Phase 1+2+3)**: Pipeline time ~20 min → ~12-15 min. Per-doc cost reduction of 30-50% from threshold tuning alone. No quality risk.

##### Scaling analysis (2026-04-21)

At target scale (50 free + 10 paid users, ~400 docs/month, ~15/day):

| Component | Current (4 docs) | At scale (400 docs/mo) | Breaks at |
|-----------|-----------------|----------------------|-----------|
| Gemini RPM | ~30 | ~200 | ~4,000 (far away) |
| GPT-4o monthly cost | ~$5 | $2,500-5,000 | When cost > revenue |
| Worker greenlets | 5/50 used | 100/50 needed at batch_size=25 | 4 concurrent docs |
| DB connection pool | ~5 | ~100 concurrent | Pool size (~40) |

**The scaling wall is GPT-4o cost, not Gemini speed.** At 400 docs/month with current escalation rate, GPT-4o costs $2,500-5,000/month. Revenue from 50 paying users at ₹999/mo ≈ $600/month. Unit economics are upside down until either: (a) escalation rate drops significantly, (b) GPT-4o is replaced with a cheaper model, or (c) conversion rate exceeds ~15%.

##### PM perspective (documented 2026-04-21)

John (PM agent) raised: "Why optimize the engine before validating that the funnel works?" The product found 181 contradictions across 4 test documents — the detection capability exists. But we have zero evidence that lawyers convert after seeing contradictions. Suggestion: (a) user interviews with 5 lawyers before spending 1-2 weeks on optimization, (b) consider launching free tier at 1 doc/month instead of 3 (costs $2/user/month at current rates — possibly sustainable without optimization), (c) prioritize loading states and summary pre-generation for conversion impact.

**Architecture note**: All Phase 1-3 changes stay inside `comparator.py`, `config.py`, and `llm_rate_limiter.py`. None touch the pipeline orchestration layer. The per-engine semaphore partitioning needed for safe high-concurrency (Phase 3+) would be a rate limiter refactor — scope TBD.

---

#### 2. UX loading state cluster

**Bug IDs**: UX-003, UX-006, UX-008, UX-009, UX-010 | **Effort**: 3-5 days | **Files**: frontend only

All five bugs share the same shape: component renders with initial state that looks like an error, then data arrives and it corrects itself. During the free user's first 3 documents, they see every one of these flashes.

| Bug | What user sees | Fix |
|---|---|---|
| UX-003 | "Ready" badge while processing at 70% | Derive status from `processing_jobs.current_stage` |
| UX-006 | "Untitled Matter" for 1-2s on load | Show `<Skeleton>` instead of fallback string |
| UX-008 | "No statistics available" flash | Initialize `isStatsLoading = true` in store |
| UX-009 | "No Contradictions Found" during processing | Check processing status, show spinner if running |
| UX-010 | "Generating Summary... 0%" stuck forever | Detect when API returns content, transition state |

**What "done" looks like**: Upload a document, navigate between tabs during processing — no flash of wrong content at any point. Every tab shows either a loading skeleton or accurate state.

---

#### 3. Summary pre-generation

**Bug IDs**: E2E-001, UX-001 | **Effort**: 3-5 days | **Files**: `document_tasks.py` (dispatch), `summary_tasks.py`, `pipeline_chains.py`

**Current state**: Summary is generated on-demand when user clicks the Summary tab. Makes 3 parallel GPT-4o calls. Takes 3-5 min. Cached in Redis with 1-hour TTL (NOT persisted to DB). Every cache eviction = full re-generation.

**The problem**: User waits 15-25 min for pipeline. Pipeline completes. User clicks Summary. Waits 3-5 MORE minutes. This is where we lose them.

**What changes**: Add `generate_summary` as a pipeline stage after `detect_contradictions` (the terminal task). Summary is generated as part of processing, cached, and waiting when user arrives. Persist to DB (not just Redis) so it survives cache eviction.

**Architecture concern**: This adds a new stage to the pipeline chain. `detect_contradictions` currently calls `_mark_job_completed` as the terminal task. Adding summary after it means either: (a) summary becomes the new terminal task and calls `_mark_job_completed`, or (b) `detect_contradictions` still calls `_mark_job_completed` and summary runs in parallel as a fire-and-forget task. Option (b) is safer — summary failure shouldn't block pipeline completion.

**What "done" looks like**: Upload a document, wait for processing to complete, click Summary tab — summary is already there. No spinner, no wait.

---

#### 4. Q&A processing guard

**Bug IDs**: UX-002 | **Effort**: 2-3 days | **Files**: `backend/app/api/routes/chat.py`, frontend chat component

**Current state**: User asks a question while document is at 70% processing. Chat endpoint runs RAG query. No embeddings exist yet → vector search returns 0 results → "I couldn't find relevant information." User thinks the product is broken.

**What changes**: Add processing-status check at top of `stream_chat()`. If any document in the matter has active processing jobs (status IN PROCESSING, PENDING), prepend a warning: "Some documents are still being processed. Results may be incomplete." If NO chunks with embeddings exist yet, block the query entirely and show: "Documents are still being processed. Q&A will be available once processing completes."

**What "done" looks like**: Ask a question during processing → see a clear message about processing status, not a false "no results."

---

### Tier 2 — Reliability (weeks 3-5)

These prevent silent failures that erode trust. Less visible than Tier 1, but critical before exposing the product to free users at scale.

#### 5. Beat process isolation

**Bug IDs**: INF-010, E2E-006 | **Effort**: 2-3 days | **Files**: `railway.toml`, new `start-beat.sh`

**The problem**: RedBeat scheduler runs in the same process as the worker. When 4 concurrent documents saturate the worker (observed in E2E), beat's lock-extension tick gets starved → lock expires → `LockNotOwnedError` → beat crashes → **all 16 periodic tasks stop firing silently**. Recovery sweeps stop, stuck documents accumulate, no alert fires. This happened during E2E (confirmed in logs).

**What changes**: Run beat as its own lightweight Railway service. Tiny container (~100MB, no heavy imports). Consumes no task queues — only runs the scheduler. Independent restart if it crashes. This is the ARCH-002 wall: physical process isolation, not configuration.

**What "done" looks like**: Kill the worker service → beat keeps running. Saturate the worker with 10 concurrent documents → beat still fires all 16 periodic tasks on schedule.

---

#### 6. Non-converging sweep fix (tactical)

**Bug IDs**: E2E-007 | **Effort**: 1 day | **Files**: `backend/app/workers/tasks/maintenance_tasks.py`

**The problem**: `trigger_pending_merges` (every 5 min) and `recover_stuck_documents` (every 15 min) dispatch `finalize_chunked_document` for ACT documents that are COMPLETED with no `extracted_text`. Finalize detects the condition, logs `finalize_skipping_no_text`, returns. Next sweep: same thing. Forever. Infinite loop of wasted work.

**What changes**: Add precondition checks in both sweep tasks: skip documents where `document_type = 'act'` AND `extracted_text IS NULL`. Or more broadly: skip documents that are already in a terminal state (`status IN ('completed', 'failed', 'deleted')`).

**This is a sticky note fix, not a wall.** The wall (Tier 3 #11, ARCH-003 reconciler) replaces all 13 sweeps with a single state-deriving reconciler. This tactical fix stops the immediate waste while the wall is built.

---

#### 7. Library document cleanup

**Bug IDs**: E2E-003 | **Effort**: 1 day | **Files**: data fix (SQL), no code change

**The problem**: ~10 library documents have records in `library_documents` table but their PDFs don't exist in Supabase storage. Tasks fail with `storage_missing` on worker startup. Affected: `arbitration_and_conciliation_act_1996.pdf`, `indian_contract_act_1872.pdf`, `constitution_of_india_1950.pdf`, etc.

**Two options**: (a) Upload the missing PDFs to storage (they're publicly available Indian statutes). (b) Delete the orphan database records. Option (a) is better — these acts are used for citation verification.

---

#### 8. Escalation threshold audit — NOW BLOCKED on Tier 1 Phase 1 metadata

**Bug IDs**: E2E-005 | **Effort**: 1 day (after data) | **Files**: `config.py` (one float)

**Current state (verified 2026-04-21)**: `confidence_threshold = 0.5` (`comparator.py:452-454`). Gemini screens 6,323 pairs → escalates 32.1% to GPT-4o → 91.1% of escalated pairs return "not contradiction." But we can't see the confidence distribution because: (a) `statement_comparisons` only stores contradictions (line 5911: "Only store contradictions"), (b) `llm_costs.metadata` is empty `{}` for all screening calls, (c) worker logs rotate on Railway.

**Blocker**: Tier 1 #1 Phase 1 must ship first — it adds screening confidence to `llm_costs.metadata`. After the next batch of documents processes, we'll have the exact confidence distribution to tune the threshold with data instead of guessing. This is potentially the single biggest cost lever (~$5-6 savings per 4 documents, ~30% total cost reduction).

**What to do after data**: Query `SELECT metadata->>'screening_confidence' as conf, metadata->>'was_escalated' as esc, COUNT(*) FROM llm_costs WHERE operation='contradiction_screening' AND metadata != '{}' GROUP BY conf, esc ORDER BY conf`. Find the confidence range where Gemini says "consistent" but we still escalate. If most wasted escalations cluster at 0.40-0.49, lower threshold to 0.35.

---

### Tier 3 — Structural (weeks 5-10, enables safe iteration at scale)

These don't help users TODAY but make every future change safer and cheaper. They become urgent once the freemium model is live and we're iterating fast on features.

#### 9. LLM domain gateway (ARCH-004)

**Effort**: 3-4 weeks | **Files**: 14+ files that bypass `gemini_client.py`, new `backend/app/services/llm/` directory

**What changes**: Create domain-level LLM classes (`CitationLLM`, `ContradictionLLM`, `TimelineDateLLM`, `RAGGeneratorLLM`, etc.) under `services/llm/`. Each takes domain inputs (`extract_citations(text)`) and returns domain outputs. Inside each: model pinned, prompt owned, rate-limit bucket declared, cost logged, retries handled. Engines lose `from google.genai import types` entirely. 14 files that currently reach past the gateway get migrated.

**Why it matters for freemium**: Need per-user cost tracking (how much has this free user consumed?). Currently cost tracking is scattered across 14 call sites, each remembering to call `cost_tracker.log_cost()`. With the gateway, cost tracking happens in ONE place — every LLM call goes through it, cost is always tracked. No "remember to log cost" convention.

**Blast radius**: 14 files need their LLM calls migrated. Each migration is mechanical (move prompt + model + retry logic into domain class, replace call site with domain method). But 14 files means 14 potential regressions. Should be done incrementally — one engine at a time, tested after each.

---

#### 10. API type codegen (ARCH-006)

**Effort**: 1-2 weeks | **Files**: `frontend/package.json`, new `frontend/src/lib/api/types.generated.ts`, 36 existing `.ts` files in `frontend/src/lib/api/`

**What changes**: Add `openapi-typescript` as frontend dev dependency. Add npm script `gen:api-types` that fetches `/openapi.json` from the backend and generates TypeScript types. Hand-written API client functions keep their function bodies but import types from the generated file. Wire into CI so stale types fail the build.

**Why it matters now**: Every UX bug fix (Tier 1 #2) touches frontend API types. Without codegen, every fix risks introducing type drift — a field renamed in Pydantic produces zero TypeScript errors. With codegen, renaming a field becomes a compile error in seconds.

---

#### 11. Reconciler (ARCH-003)

**Effort**: 4-6 weeks | **Files**: new `backend/app/workers/tasks/reconciler.py`, replaces logic in `maintenance_tasks.py` (13 sweeps)

**What changes**: Replace 13 non-converging recovery sweeps with a single reconciler that derives document state from observed database reality: "do chunks exist? embeddings? entities? citations? contradictions?" → derive correct status. Documents transition to COMPLETED or NEEDS_REPROCESS based on what's actually in the database, not based on which task remembered to signal.

**Why it matters**: Every past pipeline post-mortem (finalize race, lock-not-released, admin retry not chaining, `_mark_job_completed` blowing up on `job_id=None`) is the same class of failure: someone forgot to signal correctly. The reconciler eliminates the entire category. 13 sweeps × every 5-30 min × unbounded DB scans → 1 reconciler × every 5 min × bounded query.

**E2E-007 is proof the current sweeps don't converge**: `trigger_pending_merges` dispatches finalize for ACT documents forever. A true reconciler would check "does this document have everything it needs?" and stop.

---

### Tier 4 — Long-term (after free tier is live and generating data)

| # | What | ARCH | Why deferred | When it becomes urgent |
|---|---|---|---|---|
| 12 | **Pipeline unification** | ARCH-001 | Both paths work (E2E proved it). 6,471 + 1,926 lines of code. Largest refactor. | When we need to add a new pipeline stage and have to do it twice. |
| 13 | **Full worker isolation** | ARCH-002 | Partially fixed (dual worker). Gevent timeout fiction (Layer 5) is low-impact at current scale. | When a single tenant's batch saturates the worker and blocks others. |
| 14 | **NLI model integration** | — | Needs 10K+ labeled pairs from `statement_comparisons`. LegalWiz showed hybrid (NLI+LLM) beats LLM-only: 89.5% vs 75.3% F1. But no NLI model exists for Indian legal text — mDeBERTa-xnli has 76.9% Hindi NLI accuracy on general text, never seen legal phrasing. | After accumulating training data + validating mDeBERTa on our domain. |
| 15 | **Postgres RPC versioning** | ARCH-005 | 11 migrations so far, all `CREATE OR REPLACE`, no version bumps. Currently stable — search RPCs haven't changed recently. | Next time we modify a search RPC signature. |

---

### Free tier gate (1 day, after Tier 1 complete)

Per-user usage tracking already exists at `backend/app/api/routes/usage.py` — the `/api/usage/summary` endpoint counts documents, pages, and queries per user, grouped by matter. Frontend has `/usage` page, `useUsageSummary` hook, and `useUsageDashboard` hook.

**What's needed for the gate**: (a) `user_plans` table (plan_type enum: 'free'/'pro'/'unlimited', docs_per_month limit, created_at). (b) Upload-time check in `backend/app/api/routes/documents.py`: count documents uploaded this calendar month by this user; if >= plan limit, return 403 with upgrade message. (c) Frontend: show usage bar ("2 of 3 free documents used this month") and upgrade CTA.

**Estimated effort**: 1 day. Migration + ~10-line check in upload endpoint + frontend usage bar.

---

### Cross-reference

- Full E2E results, cost data, and competitive analysis: [E2E-FINDINGS-2026-04-17.md](E2E-FINDINGS-2026-04-17.md)
- Architectural patterns catalog: [ARCH-PATTERNS.md](ARCH-PATTERNS.md)
- DPP-002 fix (Celery chain error handling): already FIXED, verified in E2E
- WPS-001 (worker queue starvation): Layers 1-3 FIXED, Layers 4-5 in Tier 4

---

## 0. Architectural Debt (Top-Level)

> These are not localized bugs — they are foundational design choices that have produced (and will keep producing) entire categories of P0/P1 incidents until refactored. Every new feature touching the document pipeline, worker fleet, or job state must be reviewed against these. See [.claude/skills/architecture-guard/SKILL.md](.claude/skills/architecture-guard/SKILL.md) for the enforcement checklist.

### ARCH-001: Two Parallel Document Pipelines (Small-Doc Chain vs Chunked Path)
| Field | Value |
|-------|-------|
| **Severity** | P0 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-13 (review) |
| **Source** | Architectural review (2026-04-13) |

**Description**: Documents >30 pages short-circuit out of `process_document` and hand off to `process_document_chunked`, which re-implements its own dispatch graph in `chunked_document_tasks.py` (1,926 lines) alongside the original chain in `document_tasks.py` (6,471 lines). Same logical pipeline, two physical implementations, branched on a single int.

**Why it's bad**: every pipeline change has to be made twice and stay in sync. History proves the cost — the chunked path "broke the chain" so downstream tasks never fired; `finalize_chunked_document` had a reorder bug leaving documents stuck at OCR_COMPLETE with 0 chunks; the admin retry endpoint had to learn to call `create_post_ocr_chain()` instead of dispatching standalone tasks. Three high-severity post-mortems in MEMORY.md, all rooted in this one fork. The same logical document takes two completely different code paths depending on a page count — untestable in any unified way.

**Target architecture**: one pipeline that always chunks (chunk size = 1 for small docs is fine), or a fan-out/fan-in chord that's identical regardless of size. The page-count optimization belongs *inside* a stage, not as a top-level branch in the orchestration layer.

**Files**: `backend/app/workers/tasks/document_tasks.py`, `backend/app/workers/tasks/chunked_document_tasks.py`, `backend/app/workers/tasks/pipeline_chains.py`

---

### ARCH-002: Single Worker Consuming All Queues — Routing Is Cosmetic
| Field | Value |
|-------|-------|
| **Severity** | P0 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-13 (review) |
| **Source** | Architectural review (2026-04-13); related to WPS-001 |

**Description**: `numReplicas=1` in `railway.toml`; one worker process running `-Q default,llm,heavy,low` with `--pool=gevent --concurrency=50`. Celery `task_routes` carefully sends `embed_chunks`/`extract_entities`/`resolve_aliases` → `llm`, `detect_contradictions` → `heavy`, etc. — but with one process draining everything, the routing is decoration.

**Why it's bad**: queue separation only buys isolation if separate worker processes consume separate queues. Gevent greenlets serialize on the GIL the moment work becomes CPU-bound or blocks on a sync HTTP client. Result: `entity_alias_resolution_batch` (30-min soft timeout) on one tenant freezes every other tenant's uploads. Architecture was designed multi-tenant; deployment is single-tenant. WPS-001 (P0) is the operational symptom; ARCH-002 is the underlying decision. Additional discovery (2026-04-16): `soft_time_limit` is **silently ignored** with gevent pool; `worker_max_tasks_per_child` and `worker_max_memory_per_child` are **no-ops**. Every Celery safety net for bounding task duration does not fire with gevent.

**Deeper failure mode — shared upstream API quota (added 2026-04-13)**: Even if separate workers are deployed per queue, every LLM-bound task (`extract_citations`, `resolve_aliases`, `extract_dates`, `extract_entities`, `detect_contradictions`, summary, RAG) ultimately calls the **same Google Gemini account**, which enforces a single per-minute request quota. When one heavy batch (typically `entity_alias_resolution_batch`) saturates that quota, every *other* worker doing LLM work starts getting `429 Too Many Requests` and either retries-with-backoff or fails. The bottleneck moves from "one Celery worker" to "one shared upstream rate limit" — which is invisible at the queue level and cannot be fixed by adding more workers.

This means the real fix has TWO parts: (a) physical worker isolation per queue, AND (b) **per-task-type Gemini budget partitioning** — either via separate Google Cloud projects (each with its own quota), or via an in-process token-bucket limiter that gives each task class a guaranteed slice of the shared quota so one task can't eat the whole pie. Without (b), (a) is a half-fix: the workers exist but they all stall on the same phone line.

**Target architecture**:
1. Minimum two Railway services from day one — a "fast lane" worker on `default,llm` and a "heavy lane" worker on `heavy,low`. Ideally a third "interactive" worker on `default` only, so user-facing operations are never blocked by background sweeps.
2. A shared-quota partitioner in front of the Gemini client that enforces per-task-class budgets (e.g. citations: 30%, aliases: 20%, dates: 20%, entities: 20%, RAG: 10% — numbers TBD). Or split into multiple GCP projects so each task class has its own quota at the source.

**E2E evidence (2026-04-17)**: (a) Beat process shares worker process — when 4 concurrent documents saturate workers, RedBeat's lock extension gets starved → `LockNotOwnedError` → all 16 periodic tasks die silently (E2E-006, INF-010). Physical isolation of beat is needed alongside queue isolation. (b) OpenAI is a **second unpartitioned upstream** not covered in the original P3b analysis. `detect_contradictions` calls GPT-4o via `AsyncOpenAI` with **no rate limiter** — relies solely on circuit breaker catching 429s. Gemini calls in the same engine ARE rate-limited via `get_rate_limiter(LLMProvider.GEMINI)`. Same system, two LLM providers, asymmetric enforcement. At 4-doc concurrency only 1 transient OpenAI retry observed (E2E-008) and zero Gemini 429s (paid tier has ample headroom), but the structural gap (asymmetric rate-limiter enforcement) will surface at higher load.

**Files**: `backend/railway.toml`, `backend/start-worker.sh`, `backend/app/workers/celery.py`, `backend/app/services/llm/` (wherever the Gemini client lives — verify before changing), `backend/app/engines/contradiction/comparator.py` (OpenAI bypass)

---

### ARCH-003: Pipeline Completion as "Remember to Signal" Convention Instead of Derived State
| Field | Value |
|-------|-------|
| **Severity** | P0 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-13 (review) |
| **Source** | Architectural review (2026-04-13) |

**Description**: A document is COMPLETED when `detect_contradictions` (the chosen terminal task) eventually calls `_mark_job_completed`. Every exit path of every task in the chain — including 0-chunk shortcuts, Act documents, rate-limit failures — is responsible for dispatching the next task and ultimately reaching the terminal one. State is encoded across **four** different surfaces: Celery chain shapes, idempotency flags inside tasks, `documents.status` in Postgres, and Redis pipeline locks. Lock release alone has **14 call sites**.

**Why it's bad**: distributed state machine with no central authority. MEMORY.md literally has the rule *"`extract_citations` MUST dispatch `detect_contradictions` from ALL exit paths"* — that's a tax on every future change, and it's already been violated. Every past pipeline post-mortem (finalize race, lock-not-released, idempotency-returns-early-with-0-chunks, admin retry not chaining, `_mark_job_completed` blowing up on `job_id=None`) is the same class of failure: someone forgot to signal correctly, or signaled out of order, and the orchestrator has no way to self-heal.

**Target architecture**: a reconciler / watchdog that derives status from observed state — *do chunks exist? embeddings? entities? citations? contradictions?* — and a periodic sweep that promotes documents to COMPLETED or REPROCESS based on what's actually in the database. Tasks become idempotent stage workers; the reconciler is the single source of truth. This is how Airflow, Temporal, and every mature workflow engine handle it. Celery alone was the wrong substrate for a pipeline this branchy.

**E2E evidence (2026-04-17) — maintenance task proliferation**: 13 of 16 beat tasks are recovery/reconciliation sweeps: `recover_stale_jobs`, `cleanup_stale_chunks`, `recover_stale_chunks`, `trigger_pending_merges`, `recover_skipped_large_documents`, `recover_stuck_documents`, `fix_missing_extracted_text`, `dispatch_stuck_queued_jobs`, `sync_stale_job_status`, `sync_missing_entity_ids`, `resume_stuck_pipelines`, `sync_act_resolutions_with_documents`, `sync_citation_statuses_with_resolutions`. Each exists because a different task somewhere in the pipeline sometimes fails to transition state correctly. These are compensating mechanisms for ARCH-003 — but they're **non-converging re-dispatchers**, not true reconcilers. Proof: `trigger_pending_merges` (every 5 min) and `recover_stuck_documents` (every 15 min) dispatch `finalize_chunked_document` for ACT documents that are COMPLETED with no `extracted_text`. Finalize detects the condition, logs `finalize_skipping_no_text`, returns. Next sweep: same thing. Forever (E2E-007). The "reconciler" never converges because it re-triggers work instead of deriving correct terminal state. **Operational cost of ARCH-003: 13 sweeps × every 5-30 min × unbounded DB scans with no task timeouts.**

**Files**: `backend/app/workers/tasks/document_tasks.py`, `backend/app/workers/tasks/chunked_document_tasks.py`, `backend/app/workers/tasks/pipeline_chains.py`, `backend/app/api/routes/admin/pipeline.py`, `backend/app/workers/tasks/maintenance_tasks.py` (13 recovery sweeps), `backend/app/workers/celery.py:144-275` (beat schedule)

---

### ARCH-004: Gemini "Gateway" Is a Wrapper, Not a Chokepoint
| Field | Value |
|-------|-------|
| **Severity** | P0 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-13 (second-pass review) |
| **Source** | Architectural review #2 (2026-04-13) |

**Description**: `backend/app/core/gemini_client.py` exists and is imported by ~15 files — so on paper there is a central LLM client. But **14 files reach past it** with `from google.genai import types` and construct their own request payloads, pick their own model names, and own their own retry/error logic. Confirmed callers that bypass the gateway: `engines/citation/extractor.py`, `engines/citation/verifier.py`, `engines/citation/validation.py`, `engines/contradiction/comparator.py`, `engines/timeline/event_classifier.py`, `engines/timeline/date_extractor.py`, `engines/timeline/entity_linker.py`, `engines/rag/generator.py`, `services/mig/extractor.py`, `services/mig/entity_resolver.py`, `services/rag/query_rewriter.py`, `services/memory/summarizer.py`, `services/security/injection_detector.py`, `services/ocr/gemini_validator.py`. Infrastructure that *should* be enforced centrally (`core/llm_rate_limiter.py`, `core/cost_tracking.py`, `core/circuit_breaker.py`) lives at `core/` level next to the client but is wired by convention from each call site.

**Why it's bad**: same shape as ARCH-003, but for outbound API calls instead of state mutations. Every new LLM-using code path carries a tax: "remember to honor the rate limiter, remember to log cost, remember to use the right model name, remember to handle the same Gemini error envelope, remember to declare your budget bucket." Nothing structural enforces any of it. This is the **structural reason ARCH-002b is hard to fix** — there is no single seam to drop a per-task token bucket into, because each engine builds its request shape independently. It is also the most likely root of the historical "LLM costs not tracked for operation X" bugs in MEMORY.md: not a bug in `cost_tracking.py`, but a call site that forgot to call it.

**Target architecture**: `backend/app/services/llm/` becomes a real subdirectory exposing one class per use case — `CitationLLM`, `ContradictionLLM`, `TimelineDateLLM`, `RAGGeneratorLLM`, `AliasResolutionLLM`, etc. Each one takes domain inputs (`extract_citations(text)`, not `generate_content(...)`) and returns domain outputs. Inside each class: model name pinned, prompt template owned, rate-limit bucket declared, cost logged, retries handled. Engines lose `from google.genai import types` entirely. Adding a new LLM-calling task class means writing a new domain method in `services/llm/` — there is nowhere else to put it. Forbidden #2b becomes mechanically enforceable.

**E2E evidence (2026-04-17) — OpenAI as a second unmanaged provider**: `engines/contradiction/comparator.py` calls GPT-4o via `AsyncOpenAI` directly — no gateway, no centralized rate limiter. The same file's Gemini calls DO go through `get_rate_limiter(LLMProvider.GEMINI)`. This asymmetry is ARCH-004 in action: the rate-limiter infrastructure exists, Gemini uses it by convention, OpenAI doesn't because the convention was never applied. The contradiction engine also owns its own model-routing logic (Gemini Flash screening → GPT-4o escalation at confidence threshold 0.65), its own retry behavior, and its own cost tracking — all of which would live inside a `ContradictionLLM` domain class in the target architecture. The escalation threshold (0.65, lowered from 0.80 per BUG-003) is a hardcoded number in the engine with no centralized configuration surface. Contradiction detection consumed 40-70% of total pipeline time in E2E (E2E-004), with up to 50 entities × 25 pairs = 1,250 LLM calls per document.

**Files**: `backend/app/core/gemini_client.py`, `backend/app/core/llm_rate_limiter.py`, `backend/app/core/cost_tracking.py`, plus all 14 bypass call sites listed above, plus `backend/app/engines/contradiction/comparator.py` (OpenAI direct calls, escalation logic). Also note: `.claude/skills/architecture-guard/SKILL.md` already references `backend/app/services/llm/` as a high-risk path — that path doesn't exist yet, but creating it is exactly the fix.

---

### ARCH-005: Postgres RPCs as Unversioned Cross-Repo API Contract
| Field | Value |
|-------|-------|
| **Severity** | P1 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-13 (second-pass review) |
| **Source** | Architectural review #2 (2026-04-13) |

**Description**: The search RPCs (`search_chunks`, `search_documents`, `hybrid_search` and friends) have been modified across **11 migrations** since they were introduced: `20260108000004_add_hybrid_search` → `20260117140001_fix_search_rpc_service_role` → `20260125000005_add_bbox_ids_to_search_functions` → `20260127000002_add_embedding_model_version` → `20260220000002_add_parent_chunk_id_to_search_functions` → `20260220100001_fix_multilingual_text_search` → `20260220200001_add_metadata_filters_to_search_functions` → `20260219000003_add_voyage_embedding_column` → `20260223000001_add_entity_filter_to_search` → `20260220400002_tune_hnsw_indexes` → `20260115000001_security_and_indexing_fixes`. Every one is `CREATE OR REPLACE FUNCTION` — the function signature is mutated in place with no version suffix, no `_v2`, and no rollback target. The Python side (`services/rag/`, `services/global_search_service.py`, etc.) calls these by name with positional/keyword args that must match the *current* signature exactly.

**Why it's bad**: a search RPC migration is a **distributed cross-repo deploy pretending to be a single function call**. If the Supabase migration applies before the API redeploys, the API breaks (signature mismatch). If the API redeploys first, it breaks (function still on the old signature). There is no rollback story — `git revert` on the migration file is meaningless because the function in production was already overwritten by `CREATE OR REPLACE`. The 11 migrations show this isn't theoretical: it has happened nine times already after the original `add_hybrid_search`, each one a "remember to update both sides simultaneously" coordination event. This is the same anti-pattern as ARCH-003 (vigilance not structure) but at the Postgres↔Python boundary. Every search-related production bug for the lifetime of the project has had this shape lurking under it.

**Target architecture**: version the RPCs explicitly. New signatures land as `search_chunks_v3` alongside the existing `search_chunks_v2`; both functions exist simultaneously; the Python client picks the version it expects via a config constant. Once the API has been deployed using `_v3` for some safe window, `_v2` is dropped in a separate, isolated migration. Migration deploy and API deploy fully decouple. This is the standard pattern for any RPC contract evolution (gRPC field deprecation, protobuf, Stripe API versioning, AWS API versioning). Costs: extra disk for duplicate function definitions during transitions; extra discipline to drop the old version.

**Files**: `supabase/migrations/*search*.sql` (11 files listed above), `backend/app/services/rag/pipeline_service.py`, `backend/app/services/global_search_service.py`, plus any other callers — grep for `.rpc('search_` and `.rpc('hybrid_` to enumerate

---

### ARCH-006: No Source-of-Truth for the Backend↔Frontend API Contract
| Field | Value |
|-------|-------|
| **Severity** | P1 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-13 (second-pass review) |
| **Source** | Architectural review #2 (2026-04-13) |

**Description**: `frontend/src/lib/api/` contains **36 hand-written `.ts` files** mirroring FastAPI route schemas. Six of them are admin-prefixed alone (`admin-queue.ts`, `admin-quota.ts`, `admin-maintenance.ts`, `admin-monitoring.ts`, `admin-pipeline.ts`, `admin-usage.ts`). A grep for `openapi|generate.*types|swagger` across the entire `frontend/` directory returns exactly one hit (`vercel.json`, unrelated). FastAPI emits a complete OpenAPI schema at `/openapi.json` automatically — and nothing in the frontend consumes it. Every TypeScript `interface` describing a backend response was typed by hand from a Pydantic model someone read in a different repo at a different time.

**Why it's bad**: same "vigilance not structure" anti-pattern as ARCH-003, but at the API contract layer. A field renamed in a Pydantic model produces zero TypeScript errors — the frontend silently keeps reading the old field name, gets `undefined`, and a UI bug appears days later. A new field added to the backend never reaches the frontend until someone notices and updates the matching `.ts` file by hand. Per-incident blast radius is smaller than ARCH-001/002/003 (a broken UI, not a stuck document) — but the *frequency* is high because every single PR that touches a route runs this risk, and "the frontend is showing wrong data" is exactly the kind of bug users see immediately. A non-trivial fraction of the open UX bugs in BUGS.md sections 4–9 likely have type drift somewhere upstream of them. This is the architectural reason "small frontend fixes" keep needing follow-ups.

**Target architecture**: add `openapi-typescript` as a frontend dev dependency (one package, generates pure types — does not generate clients, does not impose a framework). Add an npm script `gen:api-types` that fetches `https://jaanch-ai.up.railway.app/openapi.json` (or a local backend) and writes `frontend/src/lib/api/types.generated.ts`. Wire it into the frontend build so the file is regenerated on every CI run and stale types fail the build. Hand-written API client functions in `lib/api/*.ts` keep their *function bodies* (the request shape, error handling, etc.) but import their *types* from the generated file. Renaming a Pydantic field becomes a TypeScript compile error in seconds, not a UI bug in days.

**Files**: 36 files in `frontend/src/lib/api/`, `frontend/package.json`, `backend/app/main.py` (FastAPI app — already emits OpenAPI, just needs to be consumed)

---

**Common thread across all six**: implicit coordination through convention instead of explicit coordination through structure. Two pipelines that "should" stay in sync (ARCH-001), four queues that "should" be isolated (ARCH-002), a chain that "should" reach its terminal task (ARCH-003), 14 LLM call sites that "should" honor the rate limiter (ARCH-004), a Postgres function that "should" stay signature-compatible across two repos (ARCH-005), 36 TypeScript files that "should" mirror Pydantic models exactly (ARCH-006). None are enforced by the architecture, all have been violated in production, and each violation has cost a debugging session — sometimes a multi-day one. The fix in every case is the same shape: **make the right thing the only possible thing.** Structure beats vigilance.

---

## 1. Security

### SEC-001: Cross-User Data Leakage on Login
| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **Status** | FIXED (2026-02-27) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-001) |

**Description**: Logging in as User B after logging out from User A shows User A's matters, notifications, admin menu, and activity feed. Frontend caches (React Query, Zustand, localStorage) were not cleared on logout.

**Root Cause**: Logout only called `supabase.signOut()` but left all application state intact — Zustand stores, localStorage keys, SWR cache, and the cached Supabase client singleton.

**Fix Applied** (3 layers of defense):
1. **Centralized cleanup** (`frontend/src/lib/auth/logout-cleanup.ts`): Clears API session cache, cached Supabase client, all `ldip-*`/`ldip:*` localStorage keys, and global SWR cache.
2. **All logout handlers** (`LogoutButton.tsx`, `UserProfileDropdown.tsx`, `useAuth.ts`): Now call `cleanupOnLogout()` + hard redirect (`window.location.href` instead of `router.push`).
3. **Auth state listener** (`useAuth.ts:43-53`): Detects `SIGNED_OUT` events and user ID changes → triggers `cleanupOnLogout()`.

**Files**: `frontend/src/lib/auth/logout-cleanup.ts`, `frontend/src/components/features/auth/LogoutButton.tsx`, `frontend/src/components/features/dashboard/UserProfileDropdown.tsx`, `frontend/src/hooks/useAuth.ts`, `frontend/src/lib/api/client.ts`

---

## 2. Worker & Pipeline Scalability

### WPS-001: Worker Queue Starvation — 5 Compounding Layers
| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **Status** | PARTIALLY FIXED (2026-04-17) — Layers 1-3 fixed, Layers 4-5 open |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-002) |

**Description**: One large matter's `entity_alias_resolution_batch` blocks ALL other users' document processing. Not a single root cause — five layers compound:

**Layer 1 — Prefetch hoarding (config)**: `prefetch_multiplier=4` × `concurrency=50` = 200 tasks buffered. New user's tasks can't be picked up until buffer drains. **FIXED** (commit `47ef182`): set `worker_prefetch_multiplier=1`.

**Layer 2 — No physical queue isolation (deployment)**: One process consuming `-Q default,llm,heavy,low`. Four queues, zero isolation. `resolve_aliases` (30 min) competes directly with `process_document` (5 sec). **FIXED** (commit `3c07996`): WPS-001 Phase 2 — dual worker deployment. `ldip-worker` handles default+llm (fast pipeline tasks), `ldip-worker-slow` handles heavy+low (O(n^2) tasks + maintenance). Separate Railway services, separate processes, true physical isolation.

**Layer 3 — Gemini bottleneck (the actual ceiling)**: Global rate limit `max_concurrent=1`, `min_delay=6.0s`, `max_rpm=10` (free tier). ALL LLM tasks share this single 10 RPM quota. **FIXED** (commit `3581bdd`): upgraded to Gemini Paid Tier 1 (1000 RPM). Rate limiter config updated from 10 RPM → 1000 RPM, min_delay 6.0s → 0.06s, max_concurrent 1 → 10.

**Layer 4 — Monolithic task design**: `resolve_aliases` is a single Celery task holding 1 greenlet for up to 30 minutes. Internally batches (10 pairs, 3-way semaphore) but Celery can't preempt or interleave. **OPEN**: Fix is fan-out/fan-in decomposition into 2-min chunks.

**Layer 5 — Gevent timeout fiction**: `soft_time_limit` is silently ignored with gevent pool. `worker_max_tasks_per_child` and `worker_max_memory_per_child` are no-ops. Every safety net Celery advertises for bounding task duration does not fire with gevent. **OPEN**: Fix is switching to prefork pool or adding manual timeout enforcement.

**Interaction with INF-009 (FIXED)**: Ghost document recovery loop was dispatching 14 pipeline tasks every 15 min for already-deleted documents, wasting greenlets and Gemini quota that real users needed.

**Detailed engineering plan**: See [BUG-002-WORKER-QUEUE-STARVATION.md](BUG-002-WORKER-QUEUE-STARVATION.md) — covers Phases 1-5 (config tuning, dual worker, per-matter cap, dispatch updates, task decomposition).

**Files**: `backend/railway.toml`, `backend/start-worker.sh`, `backend/app/workers/celery.py`, `backend/app/services/mig/entity_resolver.py`, `backend/app/core/llm_rate_limiter.py`

---

### WPS-002: Tasks Not Routed to llm/heavy/low Queues
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #13) |

**Description**: Queue routing configuration exists (`default`, `llm`, `heavy`, `low`) but `apply_async()` calls use `queue="default"`. Originally appeared that routing was decorative.

**Root Cause (original)**: Hardcoded `queue="default"` in dispatch calls.

**Fix Applied**: Celery's `task_routes` configuration at `celery.py:79-107` centrally routes all tasks to correct queues, overriding the `queue=` parameter in `apply_async()`. This is the correct Celery pattern — centralized routing via `task_routes` is the single source of truth. Verified mappings: `embed_chunks`, `extract_entities`, `extract_citations`, `resolve_aliases`, `extract_dates` → `llm`; `detect_contradictions` → `heavy`; `maintenance_tasks.*`, `act_validation_tasks.*`, `evaluation_tasks.*` → `low`. Note: with a single worker consuming all queues, routing provides logical separation but not physical isolation until multi-worker is deployed.

**Files**: `backend/app/workers/celery.py:79-107`

---

### WPS-003: Rate Limiter Bottleneck — Citations + Aliases Share Same Gemini Limit
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #10) |

**Description**: `extract_citations` and `resolve_aliases` run in parallel but both use Gemini LLM calls sharing the same distributed rate limiter (`provider=gemini`, `max_rpm=10`). When both tasks fire simultaneously, they saturate the 10 RPM limit and trigger ~2s waits per hit.

**Root Cause**: Single Gemini rate limit bucket (`max_concurrent=1`, `min_delay=6.0s`, `max_rpm=10`) shared by all operations. This is intentional for Gemini free tier (10 RPM). Config is at `backend/app/core/llm_rate_limiter.py:60-71` and is configurable via env vars (`GEMINI_MAX_CONCURRENT_REQUESTS`, `GEMINI_MIN_REQUEST_DELAY`, `GEMINI_REQUESTS_PER_MINUTE` in `config.py:134-136`).

**Fix**: Upgrade to paid Gemini tier (1000+ RPM) to remove bottleneck, or split operations across different LLM providers. The infrastructure (distributed rate limiter with Redis coordination for multi-worker) is already in place. **Note**: This is also WPS-001 Layer 3 — the Gemini rate limit is the actual throughput ceiling for the entire system, not just citations+aliases. Dual workers (WPS-001 Phase 2) buy greenlet isolation but not upstream isolation.

**Files**: `backend/app/core/llm_rate_limiter.py:60-71`, `backend/app/core/config.py:134-136`

---

## 3. Document Processing Pipeline

### DPP-001: Retry Fails on DuplicateChunkError
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #1) |

**Description**: When retrying a failed document, old `document_ocr_chunks` from the previous attempt are not cleaned up. The retry `process_document` task attempts to insert OCR chunks and hits a unique constraint conflict → `DuplicateChunkError`.

**Root Cause**: The retry endpoint did not delete existing `document_ocr_chunks` before re-triggering `process_document`.

**Fix Applied**: Admin retry endpoint now runs `_cleanup_for_full_reprocess()` before re-triggering. This deletes OCR chunks, RAG chunks, resets document status, fails stale `PROCESSING` jobs, and releases the pipeline lock. Verified: document `ab947f17` retried via admin endpoint → full chain ran → status=completed automatically.

**Files**: `backend/app/api/routes/admin/pipeline.py`

---

### DPP-002: Celery Chain Continues After Task Failure
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-04-17) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #2) |

**Description**: When a chained task fails, it returned a dict like `{"status": "chunking_failed", ...}` instead of raising. Celery only understands exceptions as failures — returned dicts are "success." The chain continued running all downstream tasks on bad data.

**Root Cause (deep — P7/P8/P9 patterns)**: Three-layer problem: (1) Tasks return dicts instead of raising exceptions (P7 — signaling failure in a language the framework doesn't speak), (2) Downstream tasks manually check and skip (dead code), (3) No chain-level error handling. Blast radius: 16 tasks affected, 28 cleanup call sites, 3 tasks with inconsistent cleanup (P8).

**Fix Applied** (commits `ef129e2`, `81b3207`):
1. NEW: `pipeline_errors.py` — `PipelineTaskError` and `LibraryPipelineTaskError` exception classes
2. All 5 chained tasks (`validate_ocr`, `calculate_confidence`, `chunk_document`, `embed_chunks`, `extract_entities`) now raise `PipelineTaskError` on terminal failure instead of returning dicts
3. P8 consistency fixes: `calculate_confidence` was missing `_release_pipeline_lock_safe`; `embed_chunks` and `extract_entities` were missing `_mark_job_failed`
4. `on_chain_error` safety-net callback wired via `link_error` on the chain — centralized cleanup (P8 wall)
5. Library pipeline: `chunk_library_document` and `embed_library_chunks` raise `LibraryPipelineTaskError`; `on_library_chain_error` callback wired
6. All chain entry points (`create_post_ocr_chain`, `process_library_document`, `ocr_and_process_library_document`) have `link_error`

**Architectural patterns documented**: P7, P8, P9 added to `ARCH-PATTERNS.md`

**Files**: `backend/app/workers/tasks/pipeline_errors.py` (NEW), `backend/app/workers/tasks/pipeline_chains.py`, `backend/app/workers/tasks/document_tasks.py`, `backend/app/workers/tasks/library_tasks.py`, `ARCH-PATTERNS.md`

---

### DPP-003: No Automatic Cleanup on Retry
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #3) |

**Description**: When a user clicks "Retry All" or "Retry Processing" in the admin UI, the system does NOT clean up stale data from the previous failed attempt. Manual SQL was required to delete stale `document_ocr_chunks`, reset document `status`, and delete failed `processing_jobs` and `job_stage_history`.

**Root Cause**: The retry endpoint lacked cleanup logic.

**Fix Applied**: Same fix as DPP-001. Admin retry endpoint now runs `_cleanup_for_full_reprocess()` which: (1) deletes `document_ocr_chunks`, (2) deletes RAG `chunks`, (3) resets document status to `pending`, (4) marks stale `PROCESSING` jobs as `FAILED`, (5) releases `PipelineLock`.

**Files**: `backend/app/api/routes/admin/pipeline.py`

---

### DPP-004: OCR Doesn't Re-Run on Retry
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #4) |

**Description**: After manual cleanup and retry, the pipeline ran but Document AI OCR was completely skipped. The document had no `extracted_text`, so every downstream stage found nothing to process. Also failed with `validate_ocr_skipped_pipeline_locked` indicating the concurrent processing lock was not released.

**Root Cause**: The retry path created a new processing job but did not re-trigger Document AI OCR. The pipeline lock was not cleared on retry.

**Fix Applied**: Two fixes: (1) `_cleanup_for_full_reprocess()` now releases `PipelineLock` before retry. (2) Admin retry now uses `create_post_ocr_chain()` for full chain dispatch (validate→chunk→embed→entities) instead of standalone task dispatch. For `failed`/`error` status, `process_document` is chained with full post-OCR chain to re-trigger OCR from scratch.

**Files**: `backend/app/api/routes/admin/pipeline.py`, `backend/app/workers/tasks/pipeline_chains.py`

---

### DPP-005: Processing Jobs Stuck in PROCESSING Status
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | NOT CURRENTLY REPRODUCIBLE |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #5) |

**Description**: When document processing fails, `processing_jobs` entries remain in `PROCESSING` status indefinitely instead of being marked `FAILED`.

**Verified** (2026-03-18): `SELECT status, COUNT(*) FROM processing_jobs GROUP BY status` → COMPLETED: 88, FAILED: 15, PROCESSING: 0. Zero stuck jobs currently. However, the root cause (task error handlers not reliably updating status) has not been verified as fixed in code — this may recur during next processing run.

**Fix Needed**: If it recurs, error handlers must reliably update job status. Consider a periodic cleanup job.

**Files**: `backend/app/workers/tasks/document_tasks.py`

---

### DPP-006: Old Document Chain Missing extract_tables
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-4) |

**Description**: Zero `chunk_type='table'` chunks across all 14 documents despite Docling being installed. The initial upload path used a hardcoded chain missing `extract_tables`, while the re-process path used the factory function that included it.

**Root Cause**: `_queue_ocr_task()` in `documents.py` had a hardcoded chain that skipped `extract_tables`. The factory `create_post_ocr_chain()` correctly included it.

**Fix Applied**: Replaced hardcoded chain with `create_post_ocr_chain()` factory call in both `_queue_ocr_task()` and the full retry path. Existing documents need re-processing.

**Files**: `backend/app/api/routes/documents.py`, `backend/app/workers/tasks/pipeline_chains.py`

---

### DPP-007: broadcast_timeline_discovery_failed — Date Not JSON Serializable
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #7) |

**Description**: After `extract_dates_from_document` creates 27 timeline events, the Supabase Realtime broadcast fails because the payload includes a Python `datetime.date` object which is not JSON serializable. The dates are still saved to DB; only the realtime broadcast fails.

**Fix Applied**: Added `.isoformat()` conversion at `engine_tasks.py:467-468` before passing dates to `broadcast_timeline_discovery()`:
```python
date_range_start = sorted_dates[0].isoformat() if sorted_dates else None
date_range_end = sorted_dates[-1].isoformat() if sorted_dates else None
```

**Files**: `backend/app/workers/tasks/engine_tasks.py:467-468`

---

### DPP-008: upsert_act_resolution RPC Returns 400
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #8) |

**Description**: After saving citations, the `upsert_act_resolution` Supabase RPC consistently returns HTTP 400 Bad Request. A fallback path (direct `POST` to `act_resolutions` with `on_conflict`) succeeds, but produces noisy logs on every citation batch.

**Root Cause**: The RPC function has `SECURITY DEFINER` set with an `auth.uid()` check inside it (`supabase/migrations/20260106000007_create_act_resolutions_table.sql:135-167`). When called by the service role (which bypasses RLS), `auth.uid()` returns NULL → the auth check fails → 400 Bad Request. The parameters themselves match correctly (`p_matter_id`, `p_act_name_normalized`).

**Fix Needed**: Remove the `auth.uid()` check inside the RPC (since service role calls bypass RLS anyway), or remove the RPC and use the direct upsert as the primary method.

**Files**: `backend/app/engines/citation/storage.py:623-632`, `supabase/migrations/20260106000007_create_act_resolutions_table.sql:135-167`

---

### DPP-009: classify_events_for_document Finds 0 raw_date Events
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | NOT CURRENTLY REPRODUCIBLE |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #9) |

**Description**: After `extract_dates_from_document` creates 27 events, `classify_events_for_document` queries for events with `event_type=raw_date` and finds 0.

**Verified** (2026-03-18): `SELECT event_type, COUNT(*) FROM events GROUP BY event_type` shows 30 `raw_date` events exist alongside 8,364 classified events (document: 2456, order: 2056, notice: 1602, filing: 813, etc.). Both extraction and classification are working for most documents.

**Was likely a one-time timing/race condition** during a specific processing run, not a persistent bug. If it recurs, add logging to dump all event_types before the raw_date filter.

**Files**: `backend/app/workers/tasks/engine_tasks.py:494`, `backend/app/services/timeline_service.py:868-873`

---

### DPP-010: 3 Stale Processing Jobs Permanently Failed
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | RESOLVED |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-6) |

**Description**: The recovery task found 3 stale jobs stuck in `PROCESSING` status exceeding max recovery attempts (3).

**Verified RESOLVED** (2026-03-18): All 3 jobs now show `status=FAILED`: `09b9da2e` (FAILED), `a6c028bf` (FAILED), `89c44098` (FAILED). Recovery task moved them to terminal state. Documents may still need reprocessing but the stuck-job issue is resolved.

---

### DPP-011: No Table Chunks Despite Docling Installed
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (same as DPP-006) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-8) |

**Description**: Direct consequence of DPP-006. All documents used the old hardcoded chain without `extract_tables`. Fixed by DPP-006.

---

## 4. LLM & AI Services

### LLM-001: RAG Engine Timeout (45s)
| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **Status** | FIXED |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-1) |

**Description**: RAG engine timed out at 45s limit. Total execution took 53s due to cold starts on OpenAI embedding (~26s), Cohere rerank (~10s), and Gemini generation (~11s, killed by timeout).

**Root Cause**: 45s timeout at `executor.py:41` was too tight for cold-start scenarios (first request after deploy).

**Fix Applied**: RAG timeout increased to 75s at `executor.py:41`: `"rag": 75.0` with comment noting cold start can take 26s+ for embeddings.

**Files**: `backend/app/engines/orchestrator/executor.py:41`

---

### LLM-002: Subtle Detector LLM Timeout — 45s Wasted
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-2) |

**Description**: Safety LLM "subtle violation detector" failed 3 retry attempts with 10s timeouts each, burning ~45s before the query even reached the RAG pipeline. Total query time was 189s (3+ minutes).

**Root Cause**: 3 retries × (10s timeout + backoff) = ~45s. Ran sequentially before RAG.

**Fix Applied**: `MAX_RETRIES` reduced from 3 to 2 at `subtle_detector.py:42`. Worst-case now 2 × 10s = 20s (down from 45s).

**Files**: `backend/app/services/safety/subtle_detector.py:42`, `backend/app/core/config.py:90`

---

### LLM-003: RAGAS Scores All 0.0 — Tracer Incompatibility
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-10) |

**Description**: Every batch evaluation produces all-zero scores. `faithfulness` and `context_recall` return `None`, `answer_relevancy` returns `0.0`.

**Root Cause**: RAGAS 0.4.3's legacy `evaluate()` function internally calls `asyncio.run()` with a `RagasTracer` that doesn't implement `on_chat_model_start`. Caused nested event loop + silent tracer crash.

**Fix Applied**: Rewrote evaluator to use RAGAS collections API with direct `await metric.ascore()` calls (`ragas_evaluator.py:211-249`) instead of the legacy `evaluate()` function. No nested event loops, no tracer dependency. This also fixes LLM-006 (uvloop nested async).

**Files**: `backend/app/services/evaluation/ragas_evaluator.py`

---

### LLM-004: Gemini Screening — Occasional None Response
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | OPEN (low impact) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #11) |

**Description**: During contradiction screening, Gemini occasionally returns `None` instead of valid JSON.

**Original claim was WRONG**: Bug report said "falls back to GPT-4o (15x more expensive)". **Live DB disproves this**: `SELECT provider, COUNT(*) FROM llm_costs WHERE operation='contradiction_screening' GROUP BY provider` → `gemini-2.5-flash: 5,561 calls (100%)`, GPT-4o: 0 calls. Screening NEVER falls back to GPT-4. The 1,287 GPT-4o calls in `contradiction_comparison` are a DIFFERENT operation that intentionally uses GPT-4 for deep analysis.

**Actual impact**: When Gemini returns None, the screening retries on Gemini (not GPT-4). Impact is minor latency, not cost.

**Fix Needed**: Add explicit null-check before `json.loads()` at `comparator.py:644-647` to avoid noisy exception logs.

**Files**: `backend/app/engines/contradiction/comparator.py:644-647`

---

### LLM-005: Citation Extraction LLM Costs NOT Tracked in DB
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-03-19, awaiting runtime verification) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #12) |

**Description**: `citation_extraction_batch` Gemini calls are logged via `llm_cost_tracked` structlog events but NOT inserted into the `llm_costs` DB table. The `llm_costs` table has **zero** rows with any citation-related operation name.

**Root Cause**: The pipeline uses `extract_from_batch_sync()` (called from `document_tasks.py:5444`). At `extractor.py:483`, this function calls `cost_tracker.log_cost()` only — **no `persist_cost_sync()` call**. The async path `extract_from_text()` at line 760 correctly calls `await persist_cost()`, but that path is NOT used by the Celery pipeline. The single-chunk sync path at line 864 correctly calls `persist_cost_sync()`, but the pipeline uses the batch path.

**Verified against live DB** (2026-03-18): Query of `llm_costs` grouped by operation shows:
- `entity_alias_resolution_batch`: 25,719 requests, $86.39 ✅ (working)
- `entity_extraction_batch`: 385 requests, $6.58 ✅ (working)
- Citation extraction: **0 rows** ❌ (confirmed missing)

**Previous misdiagnosis corrected**: Bug A ("cost service silently fails to initialize") was **disproven** — the cost service IS properly initialized, as evidenced by $420+ in tracked costs across all other operations.

**Fix Applied**: Added `persist_cost_sync(cost_tracker)` after `cost_tracker.log_cost()` in `extract_from_batch_sync()` at `extractor.py:484`. Code deployed — will produce `llm_costs` rows when next document with citations is processed.

**Files**: `backend/app/engines/citation/extractor.py:483-484`

---

### LLM-006: Evaluation Endpoint uvloop Nested Async
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-7) |

**Description**: RAGAS 0.4.3's sync `evaluate()` internally calls `asyncio.run()` which conflicts with uvloop (FastAPI's event loop). Throws `Cannot execute nested async code with uvloop`.

**Fix Applied**: Rewrote evaluator to use RAGAS collections API with direct `await metric.ascore()` calls (lines 211-249) instead of the legacy `evaluate()` function. Purely async — no nested event loops, works correctly in both FastAPI (uvloop) and Celery gevent workers. See also LLM-003.

**Files**: `backend/app/services/evaluation/ragas_evaluator.py:133-249`

---

## 5. Frontend UX

### UX-001: Summary Generation Fails Validation
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-003) |

**Description**: After processing a 1-page PDF, Summary tab shows red error: "Generated summary failed validation checks". First thing a new user sees — very bad first impression.

**Root Cause**: Validation thresholds at `summary_service.py:2041-2067` are too strict for small documents. `subject_matter_ok` requires `len(description) > 50` and `key_issues_ok` requires `len(key_issues) > 0`. Small PDFs may not produce enough content.

**Fix Needed**: Relax validation for small documents (<5 pages), or show partial summary with "limited data" warning.

**Files**: `backend/app/services/summary_service.py:2041-2067`, `backend/app/workers/tasks/summary_tasks.py:118-120`

---

### UX-002: Q&A Returns Empty Results During Processing
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-004) |

**Description**: While document is processing (70%), Q&A returns "I couldn't find relevant information" with no indication that processing is still in progress. User thinks the app doesn't work.

**Root Cause**: Chat endpoint at `chat.py:105-219` has zero processing-status checks before querying RAG. At 70%, embeddings aren't computed yet so vector search returns 0 matches.

**Fix Needed**: Add processing-status check at top of `stream_chat()`. If any document has active processing jobs, prepend a warning or disable Q&A until embeddings are ready.

**Files**: `backend/app/api/routes/chat.py:105-219`, `backend/app/services/tab_stats_service.py:437-480`

---

### UX-003: Dashboard Shows "Ready" While Processing at 70%
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-005) |

**Description**: Matter card shows green "Ready" badge with 0% Verified while processing is at 70%. Only inside the matter page does it show the processing bar.

**Root Cause (corrected)**: Original report claimed "CITATION_EXTRACTION, CONTRADICTION_DETECTION, VERIFICATION_PROCESSING job types not mapped." **This is wrong** — those job types DON'T EXIST in the DB. Verified: `SELECT DISTINCT job_type FROM processing_jobs` → only ANOMALY_DETECTION, DOCUMENT_PROCESSING, ENTITY_LINKING, EVENT_CLASSIFICATION, SUMMARY_GENERATION. Citations/contradictions run as subtasks within DOCUMENT_PROCESSING, not as separate job types. The proposed fix (add mappings to JOB_TYPE_TO_TAB) would have NO effect.

**Real Fix Needed**: Derive matter processing status from active Celery task state or from `processing_jobs.current_stage`/`progress_pct` rather than expecting separate job types that are never created.

**Files**: `backend/app/services/tab_stats_service.py:36-54`, `backend/app/workers/tasks/document_tasks.py`

---

### UX-004: Activity Feed — Limited to Processing Events Only
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (core), OPEN (feature gap) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-006) |

**Description**: Dashboard activity feed was originally empty. Now shows processing events but no other activity types.

**Verified** (2026-03-18): Playwright shows activity feed with 10+ real entries grouped by date (Today, Yesterday, Feb 28, Feb 25). DB has 82 activities (53 `processing_complete` + 29 `processing_failed`). The feed is NOT "always empty" — the original bug is FIXED.

**Remaining feature gap**: Only 2 activity types exist (processing_complete/failed). No upload, query, summary, or other events are tracked. `chunked_document_tasks.py` may also be missing `create_activity()` calls.

**Files**: `backend/app/services/activity_service.py`, `backend/app/workers/tasks/document_tasks.py:622,974`

---

### UX-005: "Last opened: Never opened" After Opening Matter
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-007) |

**Description**: Matter card always shows "Last opened: Never opened" because the `lastOpened` timestamp is never updated anywhere.

**Verified** (2026-03-18): Playwright confirms all 11 matter cards show "Last opened: Never opened".

**Root Cause (corrected)**: The `matters` table has NO `last_opened` or `last_opened_at` column — verified via `SELECT column_name FROM information_schema.columns WHERE table_name='matters' AND column_name LIKE '%open%'` → 0 results. This is deeper than "never updated" — the entire feature is unimplemented: no DB column, no migration, no endpoint, no frontend logic.

**Fix Needed**: 1) Migration to add `last_opened_at` column to `matters`, 2) PATCH endpoint, 3) Frontend `useEffect` on matter page mount.

**Files**: `supabase/migrations/` (new), `backend/app/api/routes/matters.py`, `frontend/src/components/features/dashboard/MatterCard.tsx:219`

---

### UX-006: Matter Name Flash — "Untitled Matter" on Load
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-008) |

**Description**: Briefly flashes "Untitled Matter" for ~1-2s before loading the real name. No loading skeleton.

**Root Cause**: `EditableMatterName.tsx:65` renders `matter?.title ?? 'Untitled Matter'` while `fetchMatter()` is async. Component mounts with `null` matter → shows fallback → fetch completes → real name appears.

**Fix Needed**: Show a `<Skeleton>` when `matter` is null instead of the fallback string.

**Files**: `frontend/src/components/features/matter/EditableMatterName.tsx:65`, `frontend/src/stores/matterStore.ts`

---

### UX-007: Processing Status "0 completed, 0 queued" is Confusing
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-009) |

**Description**: Shows "Processing 1 document - 70% complete" AND "0 completed, 0 queued" simultaneously — contradictory.

**Root Cause**: Stats and active job counts are fetched in parallel via `Promise.all` but may be out of sync.

**Fix Needed**: Fetch stats and jobs atomically, or derive "in progress" count from active jobs.

**Files**: `frontend/src/components/features/processing/ProcessingStatusBanner.tsx`, `frontend/src/hooks/useProcessingStatus.ts`

---

### UX-008: Dashboard "No statistics available" Flash
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-010) |

**Description**: Briefly shows "No statistics available" before loading actual stats.

**Root Cause**: Initial store state has `isStatsLoading = false` and `stats = null`, triggering the empty message on first render before `fetchStats()` fires.

**Fix Needed**: Initialize `isStatsLoading = true` in the store, or show skeleton unconditionally before first fetch.

**Files**: `frontend/src/components/features/dashboard/QuickStats.tsx:157-162`, `frontend/src/stores/activityStore.ts`

---

### UX-009: Contradictions Tab Empty, No Loading State
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-011) |

**Description**: Shows "No Contradictions Found" with hedging message during processing. Cannot distinguish "truly empty" from "not yet processed."

**Root Cause**: Component has no access to processing status. Doesn't check if contradiction detection tasks are queued/running.

**Fix Needed**: Integrate with processing status. Show spinner if contradiction detection is still running.

**Files**: `frontend/src/components/features/contradiction/ContradictionsContent.tsx:114-125`

---

### UX-010: Summary Page Stuck at "Generating Summary... 0%"
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #14) |

**Description**: Summary tab shows "Generating Summary... Waiting in queue... 0% complete" indefinitely, even though the API returns complete 200 OK summary data. A full page reload resolves the issue.

**Root Cause**: Frontend SSE/polling mechanism does not properly transition from "generating" state to "ready" state when data arrives mid-session.

**Fix Needed**: Frontend must detect when summary API returns actual content and transition out of the loading state.

**Files**: Frontend summary page component, summary data fetching hook, SSE/polling state management

---

### UX-011: Sort/Filter Dropdowns Flash Empty on Dashboard
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-015) |

**Description**: Dropdowns appear empty for ~2-3s before values populate due to SSR/hydration mismatch.

**Fix Needed**: Set `defaultValue` on `<Select>` components matching store defaults.

**Files**: `frontend/src/components/features/dashboard/MatterFilters.tsx:57,77`, `frontend/src/stores/matterStore.ts:170-171`

---

### UX-012: Signup — No Resend Verification Option
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-016) |

**Description**: After signup, shows "Check your email" with only a "Back to Login" button. No "Resend" option if email doesn't arrive, no "check spam folder" guidance.

**Fix Needed**: Add "Resend verification email" button (calling `supabase.auth.resend()`) with rate limiting (disabled 60s after click). Add helper text.

**Files**: `frontend/src/components/features/auth/SignupForm.tsx:146-166`

---

## 6. Infrastructure

### INF-001: Worker Redis Connection Dead — All Celery Tasks Blocked
| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-1) |

**Description**: Upstash Redis closes idle connections after 5-10 min. Celery had no reconnection settings → all tasks blocked indefinitely.

**Fix Applied**: Added `broker_connection_retry_on_startup=True`, `broker_connection_retry=True`, `broker_connection_max_retries=None`, and `socket_keepalive=True` to Celery config.

**Files**: `backend/app/workers/celery.py:108-125`

---

### INF-002: socket_keepalive_options Causes Error 22 on Linux
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-9) |

**Description**: After INF-001 fix, `socket_keepalive_options` used macOS-specific TCP constants (1,2,3) that map to different constants on Linux (4,5,6). Caused `EINVAL` on Railway's Docker containers.

**Fix Applied**: Removed `socket_keepalive_options` entirely. `socket_keepalive=True` alone is sufficient.

**Files**: `backend/app/workers/celery.py`

---

### INF-003: CORS Errors on 12+ API Endpoints
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-3) |

**Description**: 33 console CORS errors across 12+ endpoints. Responses missing `Access-Control-Allow-Origin` headers.

**Verified FIXED** (2026-03-18): Live curl tests with `Origin: https://www.jaanch-ai.in` confirm CORS headers present on all response types:
- Success (200 /api/health): `Access-Control-Allow-Origin: https://www.jaanch-ai.in` ✓
- Error (401 /api/matters/bad-uuid/summary): CORS headers present ✓
- Not Found (404 /api/jobs/invalid/stats): CORS headers present ✓
- Preflight (OPTIONS): `Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT` ✓

**Files**: `backend/app/main.py:311-339`, CORS middleware at `main.py:234-241`

---

### INF-004: WebSocket Connection Fails with 502
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-4) |

**Description**: WebSocket connection to `wss://jaanch-ai.up.railway.app/api/ws/{matter_id}` fails with 502 Bad Gateway.

**Verified FIXED** (2026-03-18): Live curl with WebSocket upgrade headers returns `HTTP/1.1 101 Switching Protocols` with `Sec-Websocket-Accept` header. Railway proxy supports WS upgrade.

---

### INF-005: Celery Health Check Reports "No Workers"
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-5) |

**Description**: Every Celery health check returns `celery_health_check_no_workers` despite the worker successfully processing tasks (maintenance tasks completing).

**Root Cause**: Health endpoint uses `celery_app.control.inspect(timeout=5.0).ping()` at `health.py:343`. The 5s timeout (previously 2s, already increased) may still be insufficient for Upstash Redis latency through Railway's network, or the API service's Celery app uses a different broker URL than the worker.

**Fix Needed**: Verify broker URL consistency between API and worker. Consider an alternative health mechanism (e.g., Redis-based heartbeat written by worker, read by API).

**Files**: `backend/app/api/routes/health.py:343`

---

### INF-006: Network Request Failures (ERR_ABORTED)
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | OPEN |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-012) |

**Description**: Multiple `GET /api/jobs/.../stats => [FAILED] net::ERR_ABORTED` during processing page polling. No `AbortController` for overlapping poll requests.

**Root Cause**: `useProcessingStatus.ts` uses `setTimeout`-based polling with no abort logic. If a poll response is slow and the next poll fires, the browser aborts the stale request.

**Fix Needed**: Add `AbortController` that cancels previous fetch before starting new one.

**Files**: `frontend/src/hooks/useProcessingStatus.ts:339-353`

---

### INF-007: "Contact Support" Link Points to Placeholder URL
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-013) |

**Description**: Help Center "Contact support" links to `https://github.com/your-org/ldip/issues/new?template=question.md` — a placeholder.

**Fix Applied**: Replaced GitHub URL with `mailto:support@jaanch.ai` in both HelpPanel.tsx and FeedbackButton.tsx. Verified via Playwright: Help Center "Contact support" link shows `mailto:support@jaanch.ai`.

**Files**: `frontend/src/components/features/help/HelpPanel.tsx:168`, `frontend/src/components/features/help/FeedbackButton.tsx:27`

---

### INF-008: Console Warning — Missing aria-description
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-014) |

**Description**: Help Center dialog triggers `Warning: Missing Description or aria-...` because no `<SheetDescription>` component is used.

**Fix Applied**: Added `<SheetDescription className="sr-only">Browse help topics and documentation</SheetDescription>` inside the `<SheetHeader>`. Verified via Playwright: 0 console warnings.

**Files**: `frontend/src/components/features/help/HelpPanel.tsx:104`

---

### INF-009: Ghost Document Recovery Loop — Deleted Docs Re-Triggered Every 15 Minutes
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-04-16) |
| **Date Found** | 2026-04-16 |
| **Source** | Production log review (Railway CLI) |

**Description**: `recover_stuck_documents` (runs every 15 min) finds 14 documents stuck at `ocr_complete` and re-dispatches their pipeline chains. But these documents were already permanently deleted by `hard_delete_expired_documents`. Each cycle: recovery dispatches `finalize_chunked_document` / `validate_ocr` / `chunk_document` / `embed_chunks` → each fails with `DocumentNotFoundError` → 15 min later, recovery finds them again → infinite loop.

**Impact**: Wasted CPU, Redis commands, and log volume. Railway hit 500 logs/sec rate limit during one of these bursts. The worker has been running this loop for ~1 month with zero real work.

**Root Cause**: Soft-delete set `deleted_at` but left `status` unchanged (e.g. `ocr_complete`). `cascade_soft_delete_related_data` also deleted chunks immediately, creating documents with `status='ocr_complete'` + 0 chunks — exactly the pattern recovery tasks look for. Four recovery/maintenance queries (`recover_stuck_documents`, `resume_stuck_pipelines`, `fix_missing_extracted_text`, `sync_act_resolutions_with_documents`) all queried documents by status without filtering `deleted_at`. This is P4 from ARCH-PATTERNS.md: `deleted_at` is a helper column that can be checked but isn't required to be.

**Fix Applied (wall version)**: (1) Added `DELETED = "deleted"` to `DocumentStatus` enum. (2) `soft_delete_document()` now atomically sets `status='deleted'` alongside `deleted_at` — every existing status-based query structurally excludes deleted docs. (3) Added `.is_("deleted_at", "null")` to all 4 recovery queries as defense-in-depth.

**Files**: `backend/app/models/document.py`, `backend/app/services/document_service.py`, `backend/app/workers/tasks/maintenance_tasks.py`

**Evidence**: Logs show `recover_stuck_documents_found stuck_count=14` → `recover_stuck_document_triggered` for all 14 → `DocumentNotFoundError` for each. Same 14 doc IDs every cycle. All belong to matter `91a4a4db-bc3d-40df-8dcc-49179ac49108`.

---

### INF-010: RedBeat Lock Lost — Beat Scheduler Crashes
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | OPEN |
| **Date Found** | 2026-04-16 |
| **Source** | Production log review (Railway CLI) |

**Description**: RedBeat scheduler crashes with `redis.exceptions.LockNotOwnedError: Cannot extend a lock that's no longer owned`. The lock expired before beat could extend it, likely because the worker process was too busy (or the Redis connection dropped momentarily). Beat dies and does not auto-restart — no more periodic tasks fire until the entire worker service restarts.

**Impact**: When beat dies, all 16 scheduled maintenance tasks stop running. No recovery of stuck documents, no cleanup, no quota monitoring. Silent failure — nothing alerts that beat is dead.

**Evidence**: `[2026-04-16 12:30:44] CRITICAL/MainProcess: beat raised exception <class 'redis.exceptions.LockNotOwnedError'>`

**Fix Direction**: (a) Wrap beat's `tick()` in a retry loop so lock-loss is transient, not fatal. (b) Or run beat as a separate process that restarts independently of the worker. (c) `redbeat_lock_timeout` is currently 300s (5 min) — may need to be increased, or beat needs a health check that triggers Railway restart.

---

### INF-011: Railway Costs ~$34/month at Idle — RAM Is 99% of Spend
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | MITIGATED |
| **Date Found** | 2026-04-16 |
| **Updated** | 2026-04-27 (verified savings after 5 days of worker scale-to-zero) |
| **Source** | Railway dashboard metrics + usage billing screenshots |

**Description**: Both Railway services run 24/7 consuming significant RAM even with near-zero traffic (~4 req/hour, ~0 documents processed). RAM is 99% of the $5.03 bill accumulated in just 5 days (Apr 16-21). Estimated monthly: **$33.86**.

**Cost breakdown (from Railway billing, Apr 16-21)**:

| Service | RAM (GB-min) | RAM Cost | CPU Cost | Total |
|---|---|---|---|---|
| ldip-worker | 14,669.76 | $3.40 (67%) | $0.01 | $3.42 |
| LDIP (API) | 6,874.98 | $1.59 (32%) | $0.02 | $1.62 |
| **Total** | **21,544.74** | **$4.99** | **$0.04** | **$5.03** |

**Why the RAM is high** (verified via Phase 1+2 deep research):
- **ldip-worker runs 3 processes**: Celery beat + fast worker (40 greenlets, default+llm queues) + heavy worker (10 greenlets, heavy+low queues). Both workers eagerly import all 14 task modules (celery.py:292-327) which pull in ~30 service modules. Average ~2 GB.
- **LDIP API runs 4 uvicorn workers** (Dockerfile CMD `--workers 4`). Each imports route handlers → `documents.py` imports `document_tasks.py` → full service chain. Average ~1 GB.
- Docling/torch are installed (~900 MB on disk) but lazy-loaded (not imported at startup). RAM is from Python + google-cloud + openai + celery + supabase + pydantic + 30 other packages × multiple processes.

**Why this can't be cheaply fixed**:
- Celery workers are pull-based (poll Redis). They can't auto-sleep — no platform can detect idle or wake them via HTTP.
- The two worker processes exist for ARCH-002 compliance (physical queue isolation, WPS-001 Phase 2). Merging them reverts a hard-won fix.
- Reducing gevent greenlets (40→10) saves ~240 KB — negligible. The cost is per-process, not per-greenlet.
- Reducing uvicorn workers 4→2 saves ~$4/month — helpful but not transformative.
- Render/Fly.io don't solve this: Render's Standard tier (2 GB) costs $25/month for the worker alone. Fly.io can't auto-stop a Redis-polling worker either.

**Fix applied (2026-04-22)**:
1. **Scaled worker to 0 replicas** via `railway scale -s ldip-worker --us-west2 0`. Worker repo disconnected from GitHub to prevent auto-deploy from respawning it.
2. Uvicorn worker reduction (4→2) not yet applied — savings are modest (~$4/month).
3. **Long-term**: If/when the product needs always-on processing, the cost is a cost of doing business (~$34/month). The architecture is correct — the pricing model just doesn't suit a dormant app.

**Verified savings (2026-04-27, 5 days after fix)**:

| Metric | Before (Apr 22, day 6) | After (Apr 27, day 11) | Change |
|---|---|---|---|
| Current usage | $5.03 | $7.83 | +$2.80 in 5 days (~$0.47/day) |
| Estimated monthly | $33.86 | **$14.28** | **-58%** |
| Daily burn rate | ~$1.00/day | ~$0.47/day | **-53%** |

The $14.28 estimate includes the first 6 days at full burn ($5.03). A full month with only the API running should be ~$10-12/month.

**To restore worker**: `railway scale -s ldip-worker --us-west2 1` (and reconnect GitHub repo in Railway dashboard → Settings → Source).

**Rejected approaches (with reasons from deep research)**:
1. ~~Combine API + worker into one service~~ — Violates ARCH-002 (physical isolation).
2. ~~Merge fast + heavy workers~~ — Reverts WPS-001 Phase 2.
3. ~~Railway auto-sleep for worker~~ — Worker doesn't receive HTTP; Railway can't detect idle or wake it.
4. ~~Break API import chain (send_task instead of direct import)~~ — 15+ call sites, moderate blast radius, and docling/torch are already lazy-loaded so savings are modest.
5. ~~Migrate to Render free tier~~ — Free tier has no background workers. Paid Render Standard ($25/month for 2 GB worker) is more expensive than Railway.

---

## 7. Other

### OTH-001: A/B Duplicate Run Prevention Not Working
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-2) |

**Description**: Triggering A/B comparison with an existing pending run created a new run instead of returning 409.

**Fix Applied**: Added duplicate check in API endpoint before `create_run()`.

**Files**: `backend/app/api/routes/ab_testing.py:94-113`

---

### OTH-002: Re-Promoting Same Job Creates New Baseline
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-3) |

**Description**: Promoting the same `job_id` twice created two baseline records. No idempotency check on `promoted_from_job_id`.

**Fix Applied**: Added check for existing baseline with same `promoted_from_job_id` before creating.

**Files**: `backend/app/services/evaluation/baseline_service.py`

---

### OTH-003: Empty String matter_id Returns 500
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-02-25) |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-6) |

**Description**: `POST /api/ab-testing/compare` with `{"matter_id": ""}` returned 500 instead of 422.

**Fix Applied**: Added Pydantic `@field_validator` to validate `matter_id` as UUID.

**Files**: `backend/app/api/routes/ab_testing.py`

---

### OTH-004: Batch Eval Only Evaluates 4 of 8 — NOT A BUG
| Field | Value |
|-------|-------|
| **Severity** | N/A |
| **Status** | NOT A BUG |
| **Date Found** | 2026-02-25 |
| **Source** | LIVE-TEST-BUGS.md (BUG-5) |

**Description**: Historical batch runs evaluated 4 items because only 4 golden items existed at that time. The other 4 were created during the testing session. New batch run correctly evaluated all 8.

---

## 8. Pipeline Completion (discovered during fix session)

### DPP-012: extract_citations Breaks Pipeline Completion Chain
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-03-19) |
| **Date Found** | 2026-03-19 |
| **Source** | Session (Mar 19 — discovered while debugging DPP-001/003/004) |

**Description**: Documents that completed OCR and chunking would get stuck at `ocr_complete` or never transition to `completed` status. Root cause: `extract_citations` has three exit paths (0 chunks, Act documents, normal) — two of them returned early WITHOUT dispatching `detect_contradictions`, the terminal task that calls `_mark_job_completed()` to set document status to `completed`.

Additionally, `_mark_job_completed()` returned early when `job_id=None` (which happens on all admin retries since they don't create `processing_jobs` rows), BEFORE updating document status.

**Root Cause**: Two issues:
1. `extract_citations` 0-chunks path and Act-document path returned without dispatching `detect_contradictions` → pipeline never completed
2. `_mark_job_completed` checked `if not job_id: return` before updating document status → admin retries never marked documents as completed

**Fix Applied**:
1. `extract_citations` now dispatches `detect_contradictions` from ALL exit paths (0 chunks at line 5414, Act documents at line 5372, normal path already worked)
2. `_mark_job_completed` now updates document status BEFORE the `if not job_id` early return

**Verified**: Document `ab947f17` went from `ocr_complete` → `completed` automatically via admin retry. Zero `ocr_complete` documents remain in DB.

**Files**: `backend/app/workers/tasks/document_tasks.py:5372-5460` (extract_citations), `backend/app/workers/tasks/document_tasks.py` (_mark_job_completed)

---

## 9. Observations (Not Bugs)

### OBS-001: Test PDFs Contain Real Case Data
Test files (`test-doc-1.pdf` through `test-doc-5-contradiction.pdf`) contain names like "Nirav Jobalia", "ABC Corp" that overlap with real user data. Should use entirely fictional names.

### OBS-002: Entity Graph Extracted "ABC Co" vs PDF says "ABC Corp"
Minor extraction accuracy issue — entity extraction produced "ABC Co" when PDF text says "ABC Corp".

### OBS-003: No Onboarding / Product Tour for New Users
New user lands on empty dashboard with no guidance. "Restart Product Tour" exists in Help but doesn't auto-trigger for first-time users.

### OBS-004: Admin Endpoint Returns 200 for Non-Admin Users
**Original claim**: `GET /api/admin/status` returns HTTP 200 for non-admin users.
**Verified** (2026-03-18): Unauthenticated request to `/api/admin/status` now returns 401 UNAUTHORIZED: `{"error":{"code":"UNAUTHORIZED","message":"Missing authentication token"}}`. Behavior may have changed since original report. Needs testing with authenticated non-admin user to fully verify.

---

## Summary Statistics

*Verified against live production data on 2026-03-19 (DB queries + API tests + Playwright)*

| Category | Total | Fixed/Resolved | Open | Not Reproducible | Not a Bug |
|----------|-------|----------------|------|-----------------|-----------|
| Security | 1 | 1 | 0 | 0 | 0 |
| Worker & Pipeline Scalability | 3 | 1 | 2 | 0 | 0 |
| Document Processing Pipeline | 12 | 8 | 2 | 2 | 0 |
| LLM & AI Services | 6 | 5 | 1 | 0 | 0 |
| Frontend UX | 12 | 1 | 10 | 0 | 0 |
| Infrastructure | 11 | 7 | 4 | 0 | 0 |
| Other | 4 | 3 | 0 | 0 | 1 |
| **Total** | **49** | **26** | **19** | **2** | **1** |

### Corrections from Live Data Verification

**Round 1 corrections** (code reading only — some were wrong):
| Bug | Original | After Code Review | What changed |
|-----|----------|-------------------|-------------|
| WPS-002 | OPEN | FIXED | `task_routes` in `celery.py:79-107` routes tasks |
| LLM-001 | OPEN | FIXED | RAG timeout increased to 75s |
| LLM-002 | OPEN | FIXED | `MAX_RETRIES` reduced from 3 to 2 |
| LLM-003 | OPEN | FIXED | Rewrote to use `await metric.ascore()` |
| LLM-005 | OPEN | OPEN (2 bugs) | Theorized "Bug A: cost service fails silently" — **WRONG** |

**Round 2 corrections** (live DB + API + Playwright):
| Bug | After Round 1 | After Live Data | What changed |
|-----|---------------|-----------------|-------------|
| LLM-005 | OPEN (2 bugs) | OPEN (1 bug) | Bug A disproven — DB has $420+ in tracked costs. Only citation batch path is missing |
| LLM-004 | OPEN (GPT-4 fallback) | OPEN (low impact) | DB proves screening is 100% Gemini — zero GPT-4 fallback. Severity P2→P3 |
| INF-003 | OPEN | FIXED | curl confirms CORS headers on 200, 401, 404 responses |
| INF-004 | OPEN | FIXED | curl gets 101 Switching Protocols — WebSocket works |
| UX-004 | PARTIALLY FIXED | FIXED (core) | Playwright shows 10+ activities. DB has 82 entries |
| UX-003 | OPEN (wrong root cause) | OPEN (corrected) | Claimed job types don't exist in DB — root cause was wrong |
| UX-005 | OPEN (wrong root cause) | OPEN (corrected) | DB column doesn't exist, not just "never updated" |
| DPP-005 | OPEN | NOT REPRODUCIBLE | 0 stuck jobs in DB — may recur |
| DPP-009 | OPEN | NOT REPRODUCIBLE | 30 raw_date events exist — was likely timing issue |
| DPP-010 | OPEN | RESOLVED | All 3 jobs now FAILED status |
| OBS-004 | 200 for non-admin | 401 unauthenticated | Behavior changed |

**Round 3 fixes** (2026-03-19 — deployed + verified against live production):
| Bug | Before | After | What changed |
|-----|--------|-------|-------------|
| DPP-001 | OPEN | FIXED | Admin retry now runs `_cleanup_for_full_reprocess()` |
| DPP-003 | OPEN | FIXED | Same cleanup fix as DPP-001 |
| DPP-004 | OPEN | FIXED | Admin retry uses `create_post_ocr_chain()` + pipeline lock released |
| DPP-007 | OPEN | FIXED | `.isoformat()` conversion before broadcast |
| DPP-012 | NEW | FIXED | `extract_citations` dispatches `detect_contradictions` from all exit paths |
| LLM-005 | OPEN | FIXED | `persist_cost_sync()` added to batch path |
| INF-007 | OPEN | FIXED | `mailto:support@jaanch.ai` replaces placeholder URL |
| INF-008 | OPEN | FIXED | `<SheetDescription>` added for accessibility |

### Process Failures & Lessons Learned
See [full post-mortem](../../../.claude/projects/E--Career-coaching-100x-LDIP/memory/verification-failures.md)

**Rules derived from mistakes:**
1. For "X is not working" bugs → query the live system FIRST
2. Bug reports describe symptoms; root causes are hypotheses — verify independently
3. When a theory predicts "nothing works" but some things DO → theory is wrong
4. Check if claimed DB entities (columns, job types, tables) actually exist before writing root causes
5. Distinguish RESOLVED (root cause fixed) from NOT REPRODUCIBLE (no current data, may recur)
6. For API/infra bugs, a single curl/fetch command gives definitive answers in seconds
7. Don't copy root causes from bug reports — verify them independently
8. Don't patch a wrong answer 5 times — restart from data after the first challenge

---

## 6. First-Principles Pipeline Audit (2026-04-17)

> Findings from a first-principles review of the pipeline architecture during DPP-002 validation.
> These are not new regressions — they're pre-existing structural observations, cataloged for future work.

### DPP-013: Chain is sequential where tasks could be parallel
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | OPEN — optimization, not a correctness bug |
| **Pattern** | Suboptimal orchestration topology |

**Observation**: The post-OCR chain (`validate_ocr → calculate_confidence → chunk_document → extract_tables → embed_chunks → extract_entities`) is fully sequential. But `validate_ocr` and `calculate_confidence` don't produce anything that `chunk_document` needs — all three only read OCR text. Similarly, `embed_chunks` and `extract_entities` both only need chunks and could run in parallel.

**Current cost**: ~2-5 seconds wasted per document from unnecessary serialization.

**Wall fix**: Refactor chain into a DAG:
```
group(validate_ocr, calculate_confidence, chunk_document)
  → extract_tables
    → group(embed_chunks, extract_entities)
```

**Why not now**: DPP-002 just made the chain fail-safe. Restructuring into a DAG is a separate story. The chain is correct, just suboptimal.

---

### DPP-014: `extract_citations` dispatch failure silently orphans document
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-04-17) |
| **Pattern** | P1 ("remember to signal") — silent failure in dispatch |

**Root cause**: In `_dispatch_post_entity_tasks()` (document_tasks.py:4786-4802), if `send_task("extract_citations")` throws, the exception is caught and swallowed — appended to a `failed_tasks` list and logged, but no `_mark_job_failed()` and no `_mark_job_completed()`. The document stays stuck in PROCESSING forever.

**Safety net**: `resume_stuck_pipelines` reconciler catches this within 15-30 min. Not immediate.

**Fix applied**: If `extract_citations` dispatch fails, `_mark_job_failed(job_id, ...)` + `_release_pipeline_lock_safe(document_id)` called immediately. Document gets FAILED status instead of stuck PROCESSING.

**Wall fix (big, ARCH-003)**: Database-driven reconciler that derives completion from observed state ("all chunks have embeddings AND entities AND citations") rather than depending on the signal chain.

---

### DPP-015: `extract_citations → detect_contradictions` completion chain is a sticky note
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — already patched in DPP-012, reconciler covers gaps |
| **Status** | OPEN — structural debt, not an active bug |
| **Pattern** | P1 ("remember to signal") — ARCH-003 instance |

**Observation**: `extract_citations` MUST dispatch `detect_contradictions` from every exit path because `detect_contradictions` is the terminal task that calls `_mark_job_completed()`. This was fixed in DPP-012 (all known exit paths now dispatch it), but the structure remains P1 — any new exit path added to `extract_citations` must remember to dispatch `detect_contradictions`, or the document gets stuck.

**Current safety nets**: DPP-012 fix + `resume_stuck_pipelines` reconciler (every 15 min).

**Wall fix**: Same as DPP-014 big fix — derive completion from observed database state, not from task signals. This eliminates the entire "remember to signal" category.

**Relationship**: DPP-014 and DPP-015 share the same wall fix (ARCH-003 reconciler). They're listed separately because they have different symptoms and different interim mitigations.

---

### DPP-016: `ocr_and_process_library_document` failure not tracked
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — library documents are low-volume, admin-uploaded |
| **Status** | OPEN |
| **Pattern** | Silent failure |

**Observation**: If OCR produces empty text (line 591) or max retries are exceeded (line 654), `ocr_and_process_library_document` returns a failure dict. Since this is the orchestrator task (not in a chain), the failure is correct behavior — but it's not broadcast or tracked anywhere visible to the admin.

**Fix**: Add logging/status update so admin dashboard can surface library document failures. Low priority.

---

## 7. E2E Verification Findings (2026-04-17)

> 4 documents uploaded across 2 matters by 2 users. Both pipeline paths (small-doc chain + chunked chord) tested concurrently. All 4 completed successfully. Zero chain errors.

### E2E Results Summary

| Doc | Pages | Path | Total Time | Chunks | Entities | Dates | Contradictions | Cost (contradictions) |
|-----|-------|------|-----------|--------|----------|-------|----------------|----------------------|
| Nirav Respo 2 | 16 | small | 16.2 min | 15 | 59 | 8 | 2 | $0.33 |
| Nirav Rejoinder | 33 | chunked | 24.5 min | 31 | 98 | 20 | 20 | $0.87 |
| Rejoinder JHM | 54 | chunked | 22.8 min | 63 | 267 | 51 | 23 | $1.48 |
| Custodian | 25 | small | 18.6 min | 23 | 101 | 33 | 20 | $1.26 |

### DPP-002 / WPS-001 / DPP-014 Verification: PASSED
- Zero `pipeline_chain_error` events
- Zero `PipelineTaskError` raises
- All pipeline stages fired in correct order for both paths
- `_mark_job_completed` fired for all 4 docs
- No queue starvation — concurrent processing worked across 2 matters

---

### E2E-001: Summary generation too slow (UX)
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — user-facing, affects perceived speed |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |

**Observation**: After documents complete processing, navigating to the Summary tab shows "Generating Summary... Waiting in queue... 0% complete" with a spinner. Users expect immediate gratification after waiting 15-25 min for document processing. The summary is generated on-demand via LLM call, adding more wait time on top of an already long pipeline.

**Impact**: User perceives the system as slow even though document processing completed. The summary tab is often the first thing users click after completion.

**Possible fixes**:
1. **Pre-generate summary** as part of the pipeline (add after `detect_contradictions`) — summary is ready when user arrives
2. **Stream the summary** so users see partial results immediately instead of a spinner
3. **Cache summary** after first generation so subsequent views are instant
4. **Show a preview** with already-extracted data (entities, dates, contradictions count) while full summary generates

---

### E2E-002: Document AI OCR cold start (252s for 16-page doc)
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — intermittent, only affects first doc after deploy |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |

**Observation**: Doc 1 (16 pages) took 252s for OCR, while Doc 4 (25 pages) took only 14s. Both use the same Document AI service. The 18x difference suggests a cold start penalty on the first Document AI call after a deploy or idle period.

**Impact**: First document uploaded after deploy appears stuck at OCR for ~4 minutes.

**Possible fix**: Send a health-check/warmup request to Document AI during worker startup or deploy.

---

### E2E-003: Library documents missing from storage
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — library feature broken for these acts |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |

**Observation**: ~10 `ocr_and_process_library_document` tasks failed with `storage_missing` errors on worker startup. Affected acts: `arbitration_and_conciliation_act_1996.pdf`, `indian_contract_act_1872.pdf`, `constitution_of_india_1950.pdf`, `provincial_insolvency_act_1920.pdf`, `income_tax_act_1961.pdf`, `companies_act_2013.pdf`. These PDFs are referenced in the `library_documents` table but don't exist in Supabase storage.

**Impact**: These acts can't be used for citation verification. Note: the task sets status to FAILED with `quality_flags=["storage_missing"]` on first failure, and `resume_stuck_pipelines` only queries `status IN ('pending', 'processing')` — so these do NOT retry indefinitely. This was a one-time burst from documents that were PENDING when the worker started.

**Fix**: Clean up orphan `library_documents` records (delete rows where storage file doesn't exist), or upload the missing PDFs to storage.

---

### E2E-004: Contradiction detection is the pipeline bottleneck
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — performance, not correctness |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |

**Observation**: Contradiction detection consumed 40-70% of total processing time:
- Doc 1 (16p, 26 entities): ~5 min of 16 min total
- Doc 3 (54p, 50 entities): 683s (11.4 min) of 22.8 min total — 317 pairs compared
- Doc 4 (25p, 44 entities): ~8 min of 18.6 min total — 204 pairs compared

The stage is O(n²) on entity count and makes individual LLM calls for each pair. Most entities with `screening_confidence=0.8-0.9` escalate from Gemini Flash to GPT-4o, adding ~$0.007/pair.

**Possible optimizations**:
1. **Raise escalation threshold** — currently 0.8-0.9 triggers GPT-4o. Raising to 0.7 would cut expensive calls
2. **Batch screening calls** — send multiple pairs in one Gemini call instead of one-by-one
3. **Skip low-mention entities** — entities mentioned in only 1-2 chunks can't meaningfully contradict
4. **Parallelize entity comparisons** — currently sequential within the task
5. **Cap pairs per entity** — already capped at 25 but some entities hit this ceiling

---

### E2E-005: Excessive GPT-4o escalation in contradiction screening
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — cost optimization |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |

**Observation**: Almost every entity comparison with `screening_confidence=0.8-0.9` from Gemini Flash escalates to GPT-4o for confirmation. Most escalations result in "consistent" or "unrelated" — the GPT-4o call was wasted. Total contradiction detection costs: $0.33 + $0.87 + $1.48 + $1.26 = **$3.94 for 4 documents**.

**Fix**: Analyze escalation outcomes — if >80% of escalated pairs are "consistent/unrelated", raise the threshold or trust Gemini Flash more.

---

### E2E-006: Redis beat scheduler lock extension warning (ARCH-002 instance)
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — upgraded: kills all 16 periodic tasks silently |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |
| **Arch pattern** | ARCH-002 (P3 — routing without process isolation) |

**Observation**: `Cannot extend a lock that's no longer owned` warning from RedBeat scheduler's Redis lock (`redbeat_lock_timeout=300`). Causes Railway to hit 500 logs/sec rate limit and drop messages (43 dropped in one burst). Related to INF-010.

**Why this is ARCH-002**: Beat runs in the same process as the worker. When heavy tasks (4 concurrent documents during E2E) saturate the worker, beat's lock-extension tick gets starved → lock expires → `LockNotOwnedError` → beat crashes → **all 16 periodic tasks stop firing** → recovery sweeps stop → stuck documents accumulate silently. Additionally, 13 of 16 maintenance tasks have **no timeout decorators** — unbounded DB scans can block the event loop indefinitely.

**Fix (tactical)**: Increase `redbeat_lock_timeout` from 300s, add `soft_time_limit` to all maintenance tasks. **Fix (structural)**: Run beat as its own lightweight Railway service, physically isolated from workers (ARCH-002 target architecture).

---

### E2E-007: Finalize runs on act documents with no OCR text (ARCH-003 instance)
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — wasted worker time |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |
| **Arch pattern** | ARCH-003 (non-converging recovery sweep) |

**Observation**: Multiple `finalize_chunked_document` tasks fire for act-type documents that have `status=completed` but no `extracted_text`. Each logs `finalize_skipping_no_text` and returns. Three independent dispatchers exist: (1) chord callback (primary path), (2) `trigger_pending_merges` every 5 min, (3) `recover_stuck_documents` every 15 min. The beat tasks find these documents, dispatch finalize, finalize skips, beat finds them again next cycle. Forever.

**Why this is ARCH-003**: The beat tasks observe state (documents with status X) but don't derive correct terminal state — they just re-trigger the same task. A true reconciler would check "does this document have extracted_text AND OCR chunks? If not, transition to a terminal state that stops future dispatches."

**Fix (tactical)**: Add document_type and extracted_text precondition checks in `trigger_pending_merges` and `recover_stuck_documents` before dispatching finalize. **Fix (structural)**: Replace non-converging re-dispatchers with a single reconciler that derives state from observation (ARCH-003 target architecture).

---

### E2E-008: OpenAI calls in contradiction detection bypass rate limiter (ARCH-004 instance)
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — structural gap, not yet causing failures at current scale |
| **Status** | OPEN |
| **Source** | E2E verification (2026-04-17) |
| **Arch pattern** | ARCH-004 (gateway bypass — asymmetric rate-limiter enforcement) |

**Observation**: During peak contradiction detection (4 docs simultaneously), exactly **1 transient OpenAI retry** observed (`Retrying request to /chat/completions in 0.47s`). Gemini hit **zero 429s** (paid tier 1000 RPM has ample headroom). Railway metrics confirmed: 0% API error rate, worker peaked at 3 vCPU / 3 GB RAM / 500 MB network egress. System handled 4 concurrent docs cleanly.

**Structural note (ARCH-004)**: OpenAI calls in `comparator.py` use `AsyncOpenAI` directly with no rate limiter — relies on circuit breaker catching 429s reactively. Gemini calls in the same file DO go through `get_rate_limiter(LLMProvider.GEMINI)`. Same system, two providers, asymmetric enforcement. Not a problem at 4-doc concurrency, but the gap will surface at higher load. This is P4 (infrastructure exists but using it is optional).

**Fix (tactical)**: Wire OpenAI calls through `get_rate_limiter(LLMProvider.OPENAI)` in `comparator.py`. **Fix (structural)**: Move all LLM calls into domain classes under `services/llm/` where rate limiting is enforced by construction (ARCH-004 target architecture).
