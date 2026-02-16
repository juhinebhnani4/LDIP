# Fix Plan: RAG Pipeline + RAGAS Evaluation + Evaluation Features

**Created:** 2026-02-15
**Source:** Code review of full RAG pipeline (~30K lines) + RAGAS evaluation framework (~2K lines) + Phase-2 Backlog evaluation stories
**Total Estimated Effort:** 30-38 hours across all groups

---

## Group A: Delete Dead Code (30 min total)

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| A1 | Delete frontend evaluation API client | `frontend/src/lib/api/evaluation.ts` (368 lines) | Imported nowhere in the app. Dead code. Can rebuild in 30 min when needed. | 5 min |
| A2 | Remove unused `BackgroundTasks` param | `backend/app/api/routes/evaluation.py:170` | Parameter is injected but never used — Celery handles the async work. Misleading. | 5 min |
| A3 | Remove `'use client'` directive | `frontend/src/lib/api/evaluation.ts:1` | Only matters if we rebuild — this is a data-fetching utility, not a React component. | 1 min |

---

## Group B: Fix Broken Code — Will Crash at Runtime (2-3 hours total)

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| B1 | Fix Celery batch eval task — wrong column names | `backend/app/workers/tasks/evaluation_tasks.py:133-147` | Inserts `generated_answer` (should be `answer`), `scores` as JSON (should be individual float columns), `latency_ms` and `job_id` (don't exist in table). Will crash on any batch evaluation. | 45 min |
| B2 | Fix Celery auto-eval task — same column mismatches | `backend/app/workers/tasks/evaluation_tasks.py:288-299` | Inserts `generated_answer`, `scores`, `latency_ms`, `chat_message_id`, `is_auto_evaluation` — none exist in `evaluation_results` schema. Will crash on any auto-eval trigger. | 30 min |
| B3 | Fix `eval_result.latency_ms` reference | `backend/app/workers/tasks/evaluation_tasks.py:142,295` | `EvaluationResult` model has no `latency_ms` field. `AttributeError` at runtime. Either add field to model or remove references. | 15 min |
| B4 | Fix `count_items()` to accept tag filter | `backend/app/services/evaluation/golden_dataset.py:320-345` | `get_golden_dataset` route filters items by tags but `count_items(matter_id)` counts ALL items. Pagination metadata (total, totalPages) is wrong when filtering. | 30 min |

**DB schema reference (what columns actually exist in `evaluation_results`):**
```
id, matter_id, golden_item_id, question, answer, contexts,
context_recall, faithfulness, answer_relevancy, overall_score,
evaluated_at, triggered_by
```

---

## Group C: Fix RAG Pipeline — Security & Correctness (4-5 hours total)

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| C1 | Use `wrap_user_query()` for XML escaping | `backend/app/engines/rag/prompts.py:14,145` | Function is imported but never called. User query containing `</user_query>` could break XML security boundary, enabling prompt injection via crafted queries. | 30 min |
| C2 | Verify + fix embedding model version filter in hybrid search SQL | `supabase/migrations/20260108000004_add_hybrid_search.sql:224` + `20260127000002_add_embedding_model_version.sql` | Semantic CTE in hybrid search doesn't filter by `embedding_model_version`. Python passes `filter_model_version` but SQL doesn't use it. Old embeddings from different model would pollute results. Check if later migration fixed this. | 45 min |
| C3 | Fix match_count default mismatch (SQL=20, Python=50) | `hybrid_search.sql:163` vs `hybrid_search.py:33` | Python sends `match_count=50` for better recall, but SQL function default is 20. Anyone calling SQL directly gets fewer candidates. Align defaults. | 15 min |
| C4 | Fix double embedding call in `search_with_library` | `backend/app/services/rag/hybrid_search.py:973-982` | Generates embedding at line 973, then `self.search()` at line 976 generates it AGAIN internally. 2x OpenAI API calls per library search = 2x cost. Pass pre-computed embedding. | 45 min |
| C5 | Switch `websearch_to_tsquery` to `plainto_tsquery` in BM25 | `supabase/migrations/20260108000004_add_hybrid_search.sql:73,79` | `websearch_to_tsquery` interprets `-` as NOT operator. Legal terms like "Section 138 - NI Act" or "pre-trial" silently drop results. `plainto_tsquery` treats all text as literal. | 1 hour |
| C6 | Convert `RAGAnswerResult` to Pydantic model | `backend/app/engines/rag/generator.py:80-105` | Only model in entire codebase that's a hand-rolled class with manual `to_dict()`. Every other model uses Pydantic or dataclass. Loses validation. | 30 min |

---

## Group D: Performance & Cost Improvements (7-9 hours total)

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| D1 | Add rate limit / daily cost cap for RAGAS evaluation | `backend/app/api/routes/evaluation.py` + `backend/app/core/config.py` | Each eval costs $0.035+ via GPT-4. Batch of 100 = $3.50. Auto-eval on every chat = unbounded cost. No guardrails exist. Add daily eval limit in config. | 2 hours |
| D2 | Switch to real Gemini streaming | `backend/app/engines/orchestrator/streaming.py:42-46` + `backend/app/engines/rag/generator.py` | Current "streaming" generates full answer, then chops into 3-char chunks with 5ms delays. Users wait for entire generation before seeing ANY text. Real streaming cuts perceived latency 3-5x. | 3-4 hours |
| D3 | Add query length validation at search layer | `backend/app/services/rag/hybrid_search.py:324` | No limit on query length. User pasting entire document as query → expensive embedding ($) + bloated BM25 query. Add max query length (e.g., 2000 chars). | 30 min |
| D4 | Improve Gemini cost tracking accuracy | `backend/app/engines/rag/generator.py:261` | Uses `estimate_tokens()` because "Gemini doesn't expose token counts". Cost tracking drifts over time. Gemini API does return `usage_metadata` — extract actual tokens from response. | 1 hour |
| D5 | Fix blocking RAGAS `evaluate()` in async route handler | `backend/app/services/evaluation/ragas_evaluator.py:164` | `ragas.evaluate()` is a synchronous blocking call (makes HTTP calls to OpenAI internally) but called inside an `async` function. Blocks the FastAPI event loop during evaluation. Wrap in `asyncio.to_thread()` or use Celery for all evaluations. | 1 hour |
| D6 | Add concurrency to batch evaluation | `backend/app/services/evaluation/ragas_evaluator.py:226-260` | `evaluate_batch` processes items sequentially in a for loop. 100 golden items = 30+ minutes. Use `asyncio.gather` with concurrency limit (e.g., 5) for significant speedup. | 1.5 hours |

---

## Group E: Code Quality (5-6 hours total)

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| E1 | Make evaluation response types strict | `backend/app/models/evaluation.py:85-117` | `EvaluateResponse.data` is `Any`, response lists are `list[dict[str, Any]]`. Lose all Pydantic validation benefit. API docs (Swagger) show nothing useful. Replace with actual typed models. | 1 hour |
| E2 | Make `GoldenDatasetService` a singleton | `backend/app/api/routes/evaluation.py:296,342,385,425,473` | New instance + new Supabase client created per request. `RAGASEvaluator` already uses singleton pattern. Apply same pattern here. | 30 min |
| E3 | Use `None` for fallback `relevance_score` instead of fake scores | `backend/app/services/rag/reranker.py:371` | When Cohere fails, fallback assigns `1.0 - (i * 0.1)` as fake scores. Downstream consumers checking `relevance_score > 0.8` would be misled. Use `None` like hybrid search fallback does. | 30 min |
| E4 | Consolidate `SearchResult` / `RerankedSearchResultItem` duplication | `backend/app/services/rag/hybrid_search.py:66-158` | 12 of 13 fields are identical. Fallback at lines 885-903 manually copies every field. Use inheritance or composition. | 1 hour |
| E5 | Switch reranker from sync `cohere.Client` to `cohere.AsyncClient` | `backend/app/services/rag/reranker.py:163,342` | Currently wraps sync client in `asyncio.to_thread()`. Cohere provides async client natively. Removes thread pool overhead. | 45 min |
| E6 | Switch Redis embedding cache from JSON to binary format | `backend/app/services/rag/embedder.py:138-143` | Each 1536-float embedding is ~12KB as JSON. Binary (msgpack) would be ~6KB. ~50% memory reduction for cached vectors at scale. | 1 hour |
| E7 | Remove redundant dual snake/camel case handling in evaluation.ts | `frontend/src/lib/api/evaluation.ts:94-122` | Every transform does `(item.snake_case ?? item.camelCase)`. Backend always returns snake_case via Pydantic `model_dump()`. Dual handling adds noise and masks real bugs (if camelCase arrives, something is wrong — you want to know). | 30 min |
| E8 | Make `RAGASEvaluator` singleton resettable for testing | `backend/app/services/evaluation/ragas_evaluator.py:263-270` | `@lru_cache(maxsize=1)` on `get_ragas_evaluator()` means config changes (e.g., switching evaluation model) require process restart. Fine for production, blocks unit testing. Add `cache_clear()` helper or use module-level instance pattern like `EmbeddingService`. | 30 min |
| E9 | Remove unused `TYPE_CHECKING` import | `backend/app/services/chunking/parent_child_chunker.py:28` | Imports `LayoutBlock` under `TYPE_CHECKING` but it's unused. Minor lint issue. | 5 min |

---

## Group F: New Features — Evaluation Framework Completion (8-12 days total)

These are the Phase-2 Backlog stories (EF-1 through EF-5) that complete the evaluation system. The backend plumbing (EF-3: golden_dataset table, EF-4: RAGAS metrics) is already built. These are the missing pieces.

### F1: Extract QA Pairs from Research Docs (Story EF-1)

| ID | What | Why | Effort |
|----|------|-----|--------|
| F1 | Extract ~55-80 questions from deep research documents (Parts 1-8) into a structured list | These are REAL questions from actual case analysis — better than LLM-generated synthetic questions. They become the seed questions for lawyer verification sessions. Sources: engine-specific questions (timeline, consistency, citation), user workflow questions from UX analysis, stress test scenarios. | 1-2 days |

**Input:** Deep research documents already in codebase
**Output:** JSON/CSV list of questions with tags (citation, timeline, contradiction, entity, general)
**Dependency:** None — can start immediately

### F2: Lawyer Verification UI (Story EF-2)

| ID | What | Why | Effort |
|----|------|-----|--------|
| F2 | Build frontend interface where lawyer sees a question, the RAG-generated answer, and marks it as Correct / Wrong / Partial / Hallucinated | This is THE missing piece that makes the entire evaluation framework useful. Without it, golden dataset stays empty. The planned flow: system shows question → runs it through RAG pipeline → displays answer with sources → lawyer reviews and rates → correct answers automatically become golden dataset ground truth. | 3-5 days |

**What the UI needs:**
- List of pending questions (from F1 extraction)
- "Run through RAG" button that calls the chat/search API for each question
- Display: question, RAG answer, source chunks, source documents
- Rating buttons: Correct / Wrong / Partial / Hallucinated
- On "Correct": auto-save as golden dataset item via existing `POST /golden-dataset` API
- On "Wrong/Partial": optional field for lawyer to write the correct answer, then save
- Progress indicator (X of Y questions reviewed)
- Tag filtering (review only citation questions, only timeline questions, etc.)

**Backend changes needed:**
- New field on `golden_dataset` table: `verification_status` (correct/wrong/partial/hallucinated)
- New field: `generated_answer` (what RAG produced, for comparison)
- Update `GoldenDatasetItem` model and service accordingly
- Endpoint to run a question through RAG and return answer + sources (may reuse existing chat API)

**Frontend components needed:**
- `EvaluationQueue` page/panel
- `QuestionReviewCard` component (question + answer + rating buttons)
- `GoldenDatasetManager` component (view/filter/manage verified pairs)
- New frontend API client (replaces deleted A1, built to match actual needs)

**Dependency:** F1 (need questions to review), B1-B4 (fix broken backend code first)

### F3: Evaluation Dashboard (Story EF-5)

| ID | What | Why | Effort |
|----|------|-----|--------|
| F3 | Build dashboard showing RAG quality metrics over time | Lets you track whether RAG answers are getting better or worse after code changes. Shows: overall score trend, per-metric breakdown (faithfulness, relevancy, recall), low-scoring questions that need attention, comparison between evaluation runs. | 2-3 days |

**What the dashboard needs:**
- Score trend chart (overall score over time, per batch run)
- Per-metric breakdown (faithfulness vs relevancy vs recall)
- "Worst performers" table (questions with lowest scores)
- Filter by tag, date range, triggered_by (manual/auto/batch)
- Summary stats: total golden items, total evaluations, average score

**Dependency:** F2 (need golden dataset with 30+ verified pairs before metrics are meaningful), B1-B2 (batch eval must work)

---

## Priority Matrix

### Phase 1 — Do Now (Group A + B): ~3 hours
Broken code and dead code. Everything here either crashes at runtime or wastes space.

### Phase 2 — Do This Week (Group C): ~4 hours
Security and correctness in the core RAG pipeline. C1 (XML injection), C4 (double embedding cost), C5 (BM25 hyphen bug) are highest impact. C2 needs investigation first.

### Phase 3 — Do Before Lawyer Sessions (Group D: D1, D5, D6 + Group F: F1, F2): ~7 days
- D1 (cost cap) prevents surprise bills during evaluation sessions
- D5 (blocking eval) will freeze the API during manual evaluation
- D6 (concurrent batch) makes batch evaluation practical (minutes not hours)
- F1 (extract questions) provides the seed data for lawyer sessions
- F2 (verification UI) is the interface the lawyer will actually use

### Phase 4 — Do After First Evaluation Round (Group D: D2, D3, D4 + Group F: F3): ~4 days
- D2 (real streaming) is biggest UX win but independent of evaluation
- D3 (query length) and D4 (cost accuracy) are quick wins
- F3 (dashboard) only useful after golden dataset has 30+ verified pairs

### Phase 5 — Do When You Have Spare Time (Group E): ~5 hours
Clean-up. Nothing breaks without them. E1 and E3 improve API reliability. E4-E6 are refactoring. E7-E9 are minor polish.

---

## Dependency Graph

```
A1-A3 (delete dead code)     → no dependencies
B1-B4 (fix broken code)      → no dependencies
C1-C6 (RAG fixes)            → no dependencies
D1 (cost cap)                → before enabling auto_evaluation_enabled
D2 (real streaming)          → independent
D3 (query length)            → independent
D4 (cost tracking)           → independent
D5 (blocking eval fix)       → before any manual evaluation via API
D6 (concurrent batch)        → depends on D5
E1-E9 (code quality)         → no dependencies
F1 (extract questions)       → no dependencies, can start immediately
F2 (verification UI)         → depends on F1, B1-B4
F3 (evaluation dashboard)    → depends on F2, B1-B2 (needs 30+ golden items)
```

---

## Complete Findings Count

| Source | Findings | In Plan |
|--------|----------|---------|
| RAGAS Evaluation Code Review | 13 findings | 13 (A1-A3, B1-B4, D1, D5, D6, E1, E2, E7, E8) |
| RAG Pipeline Code Review | 14 findings | 14 (C1-C6, D2-D4, E3-E6, E9) |
| Phase-2 Backlog Evaluation Stories | 3 features | 3 (F1, F2, F3) |
| **Total** | **30 items** | **30 — nothing dropped** |

---

## Detailed Findings — RAGAS Evaluation Code Review

Code reviewed: `frontend/src/lib/api/evaluation.ts` (368 lines), `backend/app/api/routes/evaluation.py` (495 lines), `backend/app/services/evaluation/` (4 files, ~700 lines), `backend/app/workers/tasks/evaluation_tasks.py` (327 lines), `backend/app/models/evaluation.py` (118 lines), `supabase/migrations/20260122000002_create_evaluation_tables.sql` (138 lines)

### P0 — Bugs / Will Break at Runtime

**Finding 1 (→ B1): Celery batch task inserts wrong column names**
- File: `backend/app/workers/tasks/evaluation_tasks.py:133-147`
- The batch task inserts columns that don't exist in the migration: `generated_answer` (table has `answer`), `expected_answer` (doesn't exist), `scores` as JSON (table has individual float columns), `latency_ms` (doesn't exist), `job_id` (doesn't exist)
- The single-eval route (`evaluation.py:134-144`) uses the CORRECT column names — only the Celery tasks are broken

**Finding 2 (→ B2): Celery auto-eval task has same column mismatches**
- File: `backend/app/workers/tasks/evaluation_tasks.py:288-299`
- Inserts `generated_answer`, `scores`, `latency_ms`, `chat_message_id`, `is_auto_evaluation` — none exist in `evaluation_results` schema

**Finding 3 (→ B3): `latency_ms` doesn't exist on `EvaluationResult` model**
- File: `backend/app/workers/tasks/evaluation_tasks.py:142,295`
- Code accesses `eval_result.latency_ms` but `EvaluationResult` in `models.py:58-66` has no `latency_ms` field — will throw `AttributeError`

**Finding 4 (→ potential P0): Frontend `evaluateQAPair` may read wrong response shape**
- File: `frontend/src/lib/api/evaluation.ts:150-151`
- API returns `EvaluateResponse(data=result)`. Frontend does `response.data` then `.scores`. Depends on how the `api` client unwraps — if it already unwraps `data`, this goes one level too deep. Needs verification against api client implementation. (Moot if A1 deletes the file.)

### P1 — Correctness Issues

**Finding 5 (→ B4): `count_items` doesn't respect tag filter**
- File: `backend/app/services/evaluation/golden_dataset.py:320-345`
- `get_golden_dataset` route fetches items with tag filtering but `count_items(matter_id)` counts ALL items. Pagination metadata wrong when filtering by tags.

**Finding 6 (→ E2): `GoldenDatasetService` instantiated per-request**
- File: `backend/app/api/routes/evaluation.py:296,342,385,425,473`
- Every endpoint creates `GoldenDatasetService()`, creating new instance + lazy Supabase client. `RAGASEvaluator` uses singleton. Wasteful.

**Finding 7 (→ A2): `BackgroundTasks` parameter unused**
- File: `backend/app/api/routes/evaluation.py:170`
- `background_tasks: BackgroundTasks` injected but dispatch uses Celery. Dead parameter.

### P2 — Type Safety / API Contract Issues

**Finding 8 (→ E1): Loose response typing**
- File: `backend/app/models/evaluation.py:85-117`
- `EvaluateResponse.data` is `Any`, `EvaluationResultsResponse.data` is `list[dict[str, Any]]`. Loses Pydantic validation benefit, API docs show nothing.

**Finding 9 (→ E7): Redundant dual snake/camel case handling**
- File: `frontend/src/lib/api/evaluation.ts:94-122`
- Every field does `(item.snake_case ?? item.camelCase)`. Backend always returns snake_case. Dual handling adds noise, masks real bugs.

**Finding 10 (→ A3): `'use client'` on API utility file**
- File: `frontend/src/lib/api/evaluation.ts:1`
- Pure API functions, not React components. Unnecessary directive.

### P3 — Trade-offs & Concerns

**Finding 11 (→ D1): No cost caps for evaluation**
- Each eval costs ~$0.035 via GPT-4. Batch of 100 = $3.50. Auto-eval if enabled = unbounded. No rate limiting or budget cap.

**Finding 12 (→ D5): RAGAS `evaluate()` is synchronous blocking**
- File: `backend/app/services/evaluation/ragas_evaluator.py:164`
- Called inside async function but blocks event loop. Celery tasks use `run_async()` wrapper, but direct `/evaluate` endpoint doesn't protect.

**Finding 13 (→ D6): Sequential batch evaluation, no concurrency**
- File: `backend/app/services/evaluation/ragas_evaluator.py:226-260`
- For loop processes items one by one. 100 items = 30+ min. `asyncio.gather` with concurrency limits would help.

**Finding 14 (→ E8): `lru_cache` singleton not resettable**
- File: `backend/app/services/evaluation/ragas_evaluator.py:263-270`
- Config changes require process restart. Blocks unit testing.

---

## Detailed Findings — RAG Pipeline Code Review

Code reviewed: `backend/app/services/rag/hybrid_search.py` (1,091 lines), `backend/app/services/rag/embedder.py` (413 lines), `backend/app/services/rag/reranker.py` (409 lines), `backend/app/services/rag/namespace.py` (379 lines), `backend/app/engines/rag/generator.py` (369 lines), `backend/app/engines/rag/prompts.py` (228 lines), `backend/app/engines/rag/query_profile.py` (201 lines), `backend/app/api/routes/chat.py` (461 lines), `backend/app/engines/orchestrator/streaming.py` (468 lines), `supabase/migrations/20260108000004_add_hybrid_search.sql` (260 lines), `backend/app/services/chunking/parent_child_chunker.py` (584 lines)

### What's Done Well (not bugs — genuinely good)

- **4-layer matter isolation** — API validation, namespace UUID checks, SQL `SECURITY DEFINER` + `auth.uid()`, post-query result validation. Production-grade for legal.
- **Graceful degradation chain** — OpenAI fails → circuit breaker → BM25 fallback. Cohere fails → RRF fallback. Embeddings incomplete → optimistic BM25. Every external dependency has a fallback.
- **Hybrid search SQL** — Correct RRF with `FULL OUTER JOIN`. Weighted. Industry standard `k=60`.
- **Query Profile system** — Adaptive parameters per query type. Frozen dataclass. Thread-safe.
- **Prompt security** — XML boundaries, explicit "never follow document instructions", keyword sanitization.

### P0 — Bugs

**Finding 1 (→ C3): match_count default mismatch**
- SQL function default: `match_count integer DEFAULT 20` (`hybrid_search.sql:163`)
- Python constant: `DEFAULT_HYBRID_LIMIT = 50` (`hybrid_search.py:33`)
- Comment says increased to 50 for better recall but SQL wasn't updated. Direct SQL callers get 20.

**Finding 2 (→ C2): No embedding model version filter in hybrid search SQL**
- File: `supabase/migrations/20260108000004_add_hybrid_search.sql:224`
- Semantic CTE doesn't filter by `embedding_model_version`. Python passes `filter_model_version` but SQL ignores it. Later migration may have fixed — needs verification.

### P1 — Correctness Concerns

**Finding 3 (→ D2): Simulated token streaming, not real LLM streaming**
- File: `backend/app/engines/orchestrator/streaming.py:42-46`
- `TOKEN_STREAM_DELAY_MS = 5`, `TOKEN_BATCH_SIZE = 3`. Answer generated in full, then chopped into 3-char chunks with 5ms delays. User waits for full generation before seeing ANY tokens. Cosmetic streaming only.

**Finding 4 (→ C1): `wrap_user_query()` imported but never called**
- File: `backend/app/engines/rag/prompts.py:14,145`
- Imported from `prompt_boundaries` but template uses raw `{query}` in `<user_query>` tags. If query contains `</user_query>`, XML boundary breaks → prompt injection possible.

**Finding 5 (→ D4): Cost estimation is rough**
- File: `backend/app/engines/rag/generator.py:261`
- `estimate_tokens(user_prompt)` used because "Gemini doesn't expose token counts". Gemini API actually returns `usage_metadata` — this should be extracted for accurate cost tracking.

**Finding 6 (→ C4): Double embedding call in `search_with_library`**
- File: `backend/app/services/rag/hybrid_search.py:973-982`
- `query_embedding` generated at line 973, then `self.search()` at line 976 generates it AGAIN. 2x OpenAI cost per library search query.

### P2 — Design Issues

**Finding 7 (→ C6): `RAGAnswerResult` is plain class, not Pydantic/dataclass**
- File: `backend/app/engines/rag/generator.py:80-105`
- Hand-rolled class with manual `to_dict()`. Every other model uses Pydantic or dataclass. Inconsistent, loses validation.

**Finding 8 (→ E4): `SearchResult` and `RerankedSearchResultItem` near-identical**
- File: `backend/app/services/rag/hybrid_search.py:66-158`
- 12 of 13 fields identical. `RerankedSearchResultItem` adds only `relevance_score`. Fallback mapping manually copies every field.

**Finding 9 (→ E5): Sync Cohere client wrapped in `asyncio.to_thread`**
- File: `backend/app/services/rag/reranker.py:163,342`
- `cohere.Client` (sync) + `asyncio.to_thread()`. Cohere has `AsyncClient` natively.

**Finding 10 (→ E3): Fake `relevance_score` in fallback**
- File: `backend/app/services/rag/reranker.py:371`
- Fallback assigns `1.0 - (i * 0.1)` as synthetic scores. Could mislead downstream consumers. Should use `None`.

**Finding 11 (→ E6): JSON embedding cache in Redis**
- File: `backend/app/services/rag/embedder.py:138-143`
- Each 1536-float embedding ~12KB as JSON. Binary format (msgpack) would be ~6KB. ~50% memory savings.

### P3 — Minor

**Finding 12 (→ E9): Unused `TYPE_CHECKING` import**
- File: `backend/app/services/chunking/parent_child_chunker.py:28`
- `LayoutBlock` imported under `TYPE_CHECKING` but unused.

**Finding 13 (→ C5): `websearch_to_tsquery` interprets operators in user input**
- File: `supabase/migrations/20260108000004_add_hybrid_search.sql:73,79`
- `-` treated as NOT, `OR` as boolean. Legal terms "Section 138 - NI Act" silently break. `plainto_tsquery` safer.

**Finding 14 (→ D3): No query length validation**
- File: `backend/app/services/rag/hybrid_search.py:324`
- Unlimited query length. Pasting entire document → expensive embedding + bloated BM25.

---

## Documentation & Planning Sources Referenced

| Document | Path | What It Told Us |
|----------|------|-----------------|
| Phase-2 Backlog | `_bmad-output/project-planning-artifacts/Phase-2-Backlog.md:305-368` | Original "Judge-as-you-go" evaluation strategy: lawyer reviews RAG answers, verified answers become golden dataset. Stories EF-1 through EF-5. Dependencies: stable RAG pipeline, lawyer available, need to validate changes. |
| Tech Spec: RAG Production Gaps | `_bmad-output/implementation-artifacts/tech-spec-rag-production-gaps.md` | Feature 2 spec. Decided RAGAS over DeepEval. Golden dataset management. Batch evaluation via Celery. In-scope: RAGAS metrics, golden dataset, manual/batch eval. Out-of-scope: real-time eval during chat, historical dashboards. |
| MVP Complete Specification | `_bmad-output/project-planning-artifacts/LDIP-MVP-Complete-Specification.md:1577-1592` | "Human Feedback Loop — Lawyer marks finding as incorrect, system learns". Anti-hallucination target: 95% citation accuracy, <10% hallucination rate. |
| Ask Jaanch RAG Engine Analysis | `docs/analysis/ask-jaanch-rag-engine-analysis.md` | RAGAS described as "Built and operational". Cost: ~₹2.92 ($0.035) per QA pair. Lists evaluation as ready for dev. |
| First Principles Gap Analysis | `_bmad-output/analysis/first-principles-gap-analysis-2026-01-26.md:83,118-119` | Identified: "No human-in-loop for 70-80% matches", "No uncertainty UX", "No workflow modes". Recommended: configurable verification gates, batch verification UI with keyboard shortcuts. |
| Analysis.md (root) | `analysis.md:225-244` | Priority 1 gap: "No RAGAS integration, No golden dataset, No continuous evaluation". Impact: HIGH — cannot measure improvement from changes. |
| Brainstorming Session | `_bmad-output/analysis/brainstorming-session-2026-01-25.md:489` | Observation O-37: "Missing query feedback — no user satisfaction tracking". |
| Moltbot Recommendations | `_bmad-output/analysis/moltbot-inspired-recommendations.md` | User research validation approach. Survey 50+ lawyers before building features. Human verification essential. |
| DB Migration | `supabase/migrations/20260122000002_create_evaluation_tables.sql` | `golden_dataset` + `evaluation_results` tables with RLS, indexes, score constraints, update triggers. Schema is well-designed. |
| Backend Config | `backend/app/core/config.py:207-214` | `auto_evaluation_enabled: bool = False`, `openai_evaluation_model: str = "gpt-4"`, `evaluation_batch_size: int = 10`. |
| Backend Dependencies | `backend/pyproject.toml:50-59` | `ragas>=0.2.0` in optional `[ml]` extras (installed separately due to PyTorch overhead). |
| Streaming Integration | `backend/app/engines/orchestrator/streaming.py:453-461` | Auto-eval hook IS wired up: `evaluate_chat_response.delay()` fires after chat response, gated by `auto_evaluation_enabled` config. |

---

## Files Reviewed (Complete List)

### RAGAS Evaluation
- `frontend/src/lib/api/evaluation.ts` — Frontend API client (368 lines, dead code)
- `backend/app/api/routes/evaluation.py` — API routes (495 lines)
- `backend/app/services/evaluation/__init__.py` — Module exports (71 lines)
- `backend/app/services/evaluation/ragas_evaluator.py` — RAGAS service (271 lines)
- `backend/app/services/evaluation/golden_dataset.py` — Golden dataset CRUD (346 lines)
- `backend/app/services/evaluation/models.py` — Service models (102 lines)
- `backend/app/models/evaluation.py` — API request/response models (118 lines)
- `backend/app/workers/tasks/evaluation_tasks.py` — Celery tasks (327 lines)
- `supabase/migrations/20260122000002_create_evaluation_tables.sql` — DB schema (138 lines)
- `backend/app/core/config.py:207-214` — Evaluation config

### RAG Pipeline
- `backend/app/services/rag/hybrid_search.py` — Hybrid search with RRF (1,091 lines)
- `backend/app/services/rag/embedder.py` — OpenAI embeddings with caching (413 lines)
- `backend/app/services/rag/reranker.py` — Cohere Rerank v3.5 (409 lines)
- `backend/app/services/rag/namespace.py` — Matter isolation layer (379 lines)
- `backend/app/engines/rag/generator.py` — Gemini answer generation (369 lines)
- `backend/app/engines/rag/prompts.py` — System prompts with XML boundaries (228 lines)
- `backend/app/engines/rag/query_profile.py` — Adaptive retrieval parameters (201 lines)
- `backend/app/api/routes/chat.py` — Chat SSE endpoint (461 lines)
- `backend/app/engines/orchestrator/streaming.py` — Streaming orchestrator (468 lines)
- `backend/app/services/chunking/parent_child_chunker.py` — Hierarchical chunking (584 lines)
- `supabase/migrations/20260108000004_add_hybrid_search.sql` — Search SQL functions (260 lines)
- `supabase/migrations/20260127000002_add_embedding_model_version.sql` — Model version filter
- `supabase/migrations/20260125000005_add_bbox_ids_to_search_functions.sql` — Bbox search update
- `supabase/migrations/20260117140001_fix_search_rpc_service_role.sql` — Service role fix
- `supabase/migrations/20260115000001_security_and_indexing_fixes.sql` — Security fixes
