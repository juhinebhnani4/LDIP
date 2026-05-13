# BUGS.md — Consolidated Bug Tracker

**Last updated**: 2026-05-13 (Cluster 6 done: INF-005, INF-006, E2E-008, E2E-011 fixed; E2E-010 not a bug; LLM-004 fixed; E2E-007 structural fix)
**Total bugs**: 88 | **Fixed**: 60 | **Open**: 19 | **Partially Fixed**: 4 | **Not Reproducible**: 2 | **Not a Bug**: 2 | **Mitigated**: 1
**Sources**: 4 bug report files + 2 debugging sessions + 2 architectural reviews (2026-04-13) + 1 pipeline audit (2026-04-17) + 2 E2E verifications (2026-04-17, 2026-04-29)

### Legend
| Field | Values |
|-------|--------|
| **Severity** | P0 (Critical), P1 (High), P2 (Medium), P3 (Low) |
| **Status** | OPEN, FIXED, NOT CURRENTLY REPRODUCIBLE, RESOLVED, NOT A BUG |
| **Source** | File or session where the bug was first reported |

---

## Priority Roadmap

### Execution Clusters (2026-04-30)

> Updated after full library subsystem audit (16 gaps, 9 new bugs). Groups bugs that share code/deploy paths so they can be fixed together. Supersedes the Tier 1-4 structure below for sequencing — the business context and cost analysis remain valid.

```
Week 1:  Cluster 1 (library data — 3 P0s)       ✓ DONE
         Cluster 5 (UX quick wins)               ✓ DONE
Week 2:  Cluster 2 (library schema parity)       ✓ DONE
         Cluster 6 (infra hardening)             ✓ DONE
Next:    Cluster 4 (worker/beat stability)       ← NEXT
         Cluster 3 (contradiction optimization Phase 2)
After:   Cluster 7 (architectural debt — ongoing)
```

#### Cluster 1: Library Subsystem — Fix the Data ✓ DONE (2026-04-30)
*Completed in ~1 hour. Code deployed to Railway, data fixes applied, blast-radius verified by 3 parallel agents.*

| Bug | Sev | Status |
|---|---|---|
| **GAP-1**: User-uploaded Acts never get OCR dispatched | P0 | **FIXED** — OCR dispatch added with try/except + maintenance sweep fallback |
| **GAP-2**: Completed library doc with 0 chunks | P0 | **FIXED** — Zero-chunk guard + all-batches-failed guard in `embed_library_chunks` |
| **GAP-3**: 77% library chunks missing embeddings | P0 | **FIXED** — Single doc (BNS), reset to pending, sweep will re-embed 56 chunks |
| **E2E-003**: Library docs missing from storage | P2 | **OPEN** — 7 docs need India Code re-fetch (PDFs downloaded but storage path mismatch) |
| **GAP-5**: 9 failed india_code library docs | P1 | **PARTIALLY FIXED** — Root cause found (storage path convention change), BNS fixed, 7 remain |
| **GAP-6**: 3 act_resolutions stuck 69 days | P1 | **FIXED** — Data fix: moved to `not_on_indiacode` |
| **DPP-016**: Library doc failure not tracked | P3 | **DEFERRED** — No SSE infra for library docs; status already tracked in DB via quality_flags |

#### Cluster 2: Library Subsystem — Schema Parity (half day)
*All require a migration + library pipeline code changes. One migration, one deploy.*

| Bug | Sev | Fix |
|---|---|---|
| **GAP-4**: Voyage embeddings never populated | P1 | Add Voyage embedding to `embed_library_chunks` — 20 lines |
| **GAP-7**: No BM25/full-text search for library chunks | P2 | Migration to add `fts` column + update chunking task |
| **GAP-8**: Schema divergence (chunks vs library_chunks) | P2 | Same migration — add `fts`, `embedding_model_version` |
| **GAP-11**: Library cost tracking absent | P2 | Add `library_ocr` operation to cost tracking — 15 lines |
| **GAP-12**: Inconsistent dedup logic | P2 | Standardize all creation paths to use `find_library_duplicates` RPC |

#### Cluster 3: Contradiction Optimization — Phase 2 (2-3 days)
*Same file (`comparator.py`), same analysis, same deploy. Prerequisite: query `llm_costs.metadata` for screening outcome distribution (Phase 1 metadata flowing since 2026-04-27).*

| Bug | Sev | Fix |
|---|---|---|
| **E2E-004**: Contradiction detection is pipeline bottleneck | P2 | Analyze Phase 1 screening metadata, tune escalation threshold |
| **E2E-005**: Excessive GPT-4o escalation | P3 | Same analysis — raise threshold if data supports it |

#### Cluster 4: Worker/Beat Stability (1-2 days)
*All require worker topology changes (`railway.toml`, `start-worker.sh`). Deploy together.*

| Bug | Sev | Fix |
|---|---|---|
| **INF-010**: RedBeat lock lost — beat crashes | P1 | Run beat as separate Railway service |
| **E2E-006**: Redis beat lock extension warning | P2 | Same fix — beat isolation resolves both |
| **WPS-001 L4**: Monolithic `resolve_aliases` task | P2 | Fan-out/fan-in decomposition |
| **WPS-001 L5**: Gevent timeout fiction | P2 | Manual timeout enforcement or prefork |
| **E2E-007**: Finalize runs forever on act docs | P3 | **FIXED** (2026-05-13) — structural fix via `_is_pipeline_data_complete()` |

#### Cluster 5: UX Quick Wins (half day)
*Small, independent frontend fixes. Batch into one Vercel deploy.*

| Bug | Sev | Fix |
|---|---|---|
| **UX-001**: Summary validation too strict for small docs | P1 | ~~Relax thresholds for <5 page docs~~ FIXED (2026-05-06) |
| **UX-004**: Activity feed — only processing events | P2 | ~~Add upload/query/summary activity types~~ FIXED (2026-05-06) |
| **UX-012**: No resend verification email button | P3 | ~~Add resend button with rate limiting~~ FIXED (2026-05-06) |
| **E2E-009**: `/api/matters/.../touch` returns 500 | P3 | ~~Fix touch endpoint~~ FIXED (2026-05-06) |

#### Cluster 6: Infra/Network Hardening ✓ DONE (2026-05-13)
*Completed in ~2 hours. Deployed to Railway + Vercel, live-verified.*

| Bug | Sev | Status |
|---|---|---|
| **INF-005**: Celery health check reports "No Workers" | P2 | **FIXED** — Redis TTL heartbeat replaces inspect.ping() |
| **INF-006**: Network ERR_ABORTED during polling | P2 | **FIXED** — AbortController in useProcessingStatus + useDocumentStatus |
| **E2E-010**: CORS missing on `/api/health` | P3 | **NOT A BUG** — CORS works; was a one-time browser cache issue |
| **E2E-011**: Summary forceRefresh 401 | P3 | **FIXED** — SWR shouldRetryOnError now allows 401 retry for token refresh |
| **E2E-008**: OpenAI calls bypass rate limiter | P3 | **FIXED** — Wired through `get_rate_limiter(LLMProvider.OPENAI)` |
| **LLM-004**: Gemini returns None occasionally | P3 | **FIXED** — Null-check before json.loads, returns None to trigger fallback |

#### Cluster 7: Architectural Debt — Long-term (weeks, not now)
*Track but don't fix until clusters 1-6 are done. Enablers for scale, not blockers for launch.*

| Bug | Sev | Notes |
|---|---|---|
| **ARCH-001**: Two parallel pipelines | P0 | Unify small/chunked into one path |
| **ARCH-002**: Single worker all queues | P0 | Multi-worker topology (partially done) |
| **ARCH-003**: Pipeline completion as convention | P0 | Database-driven reconciler |
| **ARCH-004**: Gemini gateway bypass | P0 | `services/llm/` domain classes |
| **ARCH-005**: Unversioned Postgres RPCs | P1 | RPC versioning |
| **ARCH-006**: No API contract source of truth | P1 | openapi-typescript codegen |
| **ARCH-007**: Classification fire-and-forget | P1 | Post-OCR classification + reclassification |
| **DPP-013**: Sequential chain could be parallel | P3 | DAG refactor |
| **DPP-015**: Citation→contradiction sticky note | P3 | Same as ARCH-003 |
| **E2E-002**: Document AI cold start | P3 | Warmup request on deploy |

---

### Business Context (2026-04-21)

> Sequenced from first principles after E2E verification (4 docs, 2 matters, both pipeline paths) + freemium competitive analysis (DraftBot Pro, Harvey, CaseMine, Indian legal tech market). Full research in [E2E-FINDINGS-2026-04-17.md](E2E-FINDINGS-2026-04-17.md).

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

**Phase 1: DONE (deployed 2026-04-27)**
- **Skip 1-mention entities**: Already existed at two layers — `_generate_statement_pairs()` line 875 (`if len(all_statements) < 2: return []`) and service layer line 231 (`if entity_statements.total_statements < 2`). No code needed.
- **Persist screening metadata to `llm_costs.metadata`**: SHIPPED. Added `metadata` kwarg to `persist_cost()` and `persist_cost_sync()` in `cost_tracking.py`, pass `{"screening_result": result, "screening_confidence": confidence, "quick_reason": reason}` in `_call_gemini_screening()` in `comparator.py`. Verified in production — metadata now flowing. `was_escalated` intentionally NOT persisted: (a) it's derivable (any `operation="contradiction_comparison"` row IS an escalation), (b) the `was_escalated` flag has a bug on the screening failure path where it stays `False` even when GPT-4 is called as fallback.
- **Files changed**: `backend/app/core/cost_tracking.py` (2 functions), `backend/app/engines/contradiction/comparator.py` (1 call site). ~10 lines total.
- **First production data (2026-04-27)**: Screening confidence values observed: 0.8, 0.9, 0.95, 1.0. `needs_review` results cluster at 0.8-0.9. `consistent` results at 0.95-1.0.
- **Full data analysis (2026-04-28, 195 rows from 1 document)**:

  | Confidence | Count | % | Notes |
  |---|---|---|---|
  | 0.0 | 10 | 5% | Gemini explicitly returns confidence=0.0 (not a parsing bug — validated 2026-04-28). Low-confidence `consistent`/`unrelated` correctly escalated. |
  | 0.8 | 32 | 16% | All `needs_review` |
  | 0.9 | 90 | 46% | Mixed: 72 `needs_review`, 10 `unrelated`, 8 `consistent` |
  | 0.95 | 9 | 5% | Mixed |
  | 1.0 | 54 | 28% | Mostly `consistent` (35) + `unrelated` (13) |

  **Escalation breakdown**: 124/195 (63.6%) escalated to GPT-4o. Of 125 GPT-4o calls, only 9 found contradictions (7.2% hit rate, 92.8% wasted). Current `confidence_threshold` is **0.65** (code, `config.py:82`), not 0.5 as previously documented.

  **Critical finding**: Gemini returns **discrete** confidence values `{0.0, 0.8, 0.9, 0.95, 1.0}` — nothing in the 0.3-0.7 range. The Phase 2 hypothesis ("lower threshold from 0.5→0.35 to catch pairs at 0.45-0.49") was **wrong** — that band is empty.

**Phase 2: ~~Tune threshold~~ → HYPOTHESIS INVALIDATED (2026-04-28)**
- **Original plan**: Lower `confidence_threshold` to reduce escalations. **Dead end** — Gemini's discrete confidence values mean threshold changes between 0.0 and 0.8 catch nothing. Lowering to 0.35 would only save 3 GPT-4o calls (the `consistent`/`unrelated` at 0.0).
- **Actual cost driver**: The screening prompt (`prompts.py:378-397`) pushes aggressively toward `needs_review` with 5 CRITICAL RULES + "default should be needs_review" + "100x worse to miss." This causes 59% `needs_review` rate (vs 32% historical). ALL `needs_review` → GPT-4o regardless of confidence. **The lever is prompt tuning, not threshold tuning.**
- **Risk**: Loosening the prompt is the highest-quality-risk change in the system. Making Gemini less aggressive means real contradictions could slip through. The product promise is "we found what you missed" — false negatives kill conversion.
- **Status**: BLOCKED — needs (a) more data (only 1 document so far), (b) shadow testing infrastructure to compare prompt variants without affecting production quality. Reprioritized below Phase 4 research.
- **No parsing bug**: confidence=0.0 rows (10/195) are Gemini explicitly returning 0.0 confidence, not a missing field. Validation passes correctly. Low-confidence `consistent`/`unrelated` at 0.0 are correctly escalated to GPT-4o (3 rows). No fix needed.

**Phase 3: Safe parallelism (after beat isolation, ~1 day)**
- **Reduce `min_delay_seconds`** from 0.2 → 0.05 in `llm_rate_limiter.py:63`. Mild speedup, no concurrency increase, safe at any scale.
- **Bump `DEFAULT_BATCH_SIZE`** from 5 → 10-12 (NOT 25). Stay within the global `max_concurrent=10` semaphore. Gets ~2x speed without starving other engines. Only safe AFTER beat process isolation (Tier 2 #5) so increased load can't starve the scheduler.

**Phase 4: Research (parallel, no code changes)**
- **GPT-4o replacement research**: The actual cost bottleneck is GPT-4o at $0.0066/call for full analysis. At scale (400 docs/month), this is $2,500-5,000/month — more than revenue from 50 paying users at ₹999. Research Claude Haiku ($0.00025/1K input), Gemini Pro, or fine-tuned smaller model as a replacement for the full analysis tier. This is the 10x lever; everything else is 2x at best.
- **Shadow test Flash Lite**: Run both Flash and Flash Lite on the same pairs, compare results without using Flash Lite results. Collect quality data before switching.

**Expected result (Phase 1+3)**: Pipeline time ~20 min → ~15-18 min from parallelism only. Phase 2 (prompt tuning) could yield 30-50% cost reduction but requires shadow testing infrastructure and carries quality risk. Phase 4 (GPT-4o replacement) remains the 10x lever.

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

#### 2. UX loading state cluster — DONE (2026-04-28)

**Bug IDs**: UX-003, UX-006, UX-008, UX-009, UX-010 | **Actual effort**: ~4 hours | **Files**: 4 changed (3 frontend, 1 backend)

All five bugs shared the same shape: component renders with initial state that looks like an error, then data arrives and it corrects itself. Deep research (2026-04-28) revealed these were NOT 5 independent bugs but symptoms of **2 systemic gaps + 1 backend bug**:

1. **`workspaceStore.fetchTabStats()` was orphaned dead code** — defined but never called from any component. Fixed by activating it in `MatterWorkspaceWrapper` on mount + polling during processing. Fixes UX-003 and UX-009.
2. **`matterStore.enrichMattersWithStats()` ignored `tabProcessingStatus`** from tab-stats API response, hardcoding `processingStatus: 'ready'`. Fixed. Fixes UX-003.
3. **Summary API missing `COMPLETED` job handler** — backend state machine had no case for completed jobs, fell through to create duplicate jobs. Fixed. Fixes UX-010.
4. **UX-006 and UX-008 were already fixed** — skeleton guards and `isStatsLoading: true` init already in place from prior sessions.

**Production-verified** (2026-04-28): Dashboard shows real stats (no flash), matter header shows correct name (no flash), contradictions tab shows data or spinner (no false empty), summary loads from cache on revisit.

---

#### 3. Summary pre-generation — DONE (2026-04-29)

**Bug IDs**: E2E-001, UX-001 | **Actual effort**: ~4 hours | **Files**: 4 changed (3 backend, 1 migration)

**What was built** (deployed 2026-04-28, bugfix 2026-04-29):

1. **Fire-and-forget pipeline dispatch**: `_dispatch_summary_pregeneration(matter_id)` called from all 5 exit paths in `detect_contradictions` (success, timeout, ComparisonServiceError, DocumentServiceError, generic Exception) — right before `_mark_job_completed`. Pipeline completion is unchanged; summary failure is silent with on-demand fallback.

2. **DB persistence layer**: New `matter_summaries` table (matter_id UNIQUE, content JSONB, generated_at). Summary service now has a 3-tier lookup chain: **Redis → DB → regenerate**. On generation, summary is cached to both Redis (1-hour TTL) and DB (permanent). On cache miss, DB is checked before triggering GPT-4o regeneration.

3. **`generate_summary` task updated**: `job_id` is now optional. Pipeline dispatch sends no job_id; task creates its own job record internally for progress tracking. Existing on-demand flow (from Summary API) unchanged.

4. **Cache invalidation updated**: `invalidate_cache()` now clears both Redis and DB, so stale summaries aren't served after document re-upload.

**Bugfix (2026-04-29)**: Initial deployment used `self._get_supabase_client()` instead of `self.supabase` (the actual property name) in `summary_service.py`. DB persistence silently failed on 3 matters. Fixed and redeployed — confirmed working.

**Architecture decision**: Option (b) — fire-and-forget. `detect_contradictions` remains terminal task. Summary dispatch is a progressive enhancement (ARCH-003 safe: failure doesn't break pipeline, on-demand path remains as fallback). Acknowledged Forbidden #3 pattern (5 dispatch sites mirror 5 `_mark_job_completed` sites) — acceptable because failure is silent, not pipeline-critical.

**Production-verified (2026-04-29)** — end-to-end test with fresh document upload:

| Step | Timestamp | Result |
|------|-----------|--------|
| Document uploaded (Affidavit, 456 KB) | 03:13:15 | Pipeline started |
| Pipeline completed (OCR → entities → citations → contradictions) | 03:18:01 | 2 contradictions found |
| `summary_pregeneration_dispatched` fired | 03:18:01 | Fire-and-forget from `detect_contradictions` |
| `_mark_job_completed` — document COMPLETED | 03:18:01 | Pipeline done, user notified |
| `generate_summary` task ran (3 GPT-4o calls) | 03:18:02–03:18:20 | 18.8s background generation |
| `summary_persisted_to_db` | 03:18:20 | 5,885B in `matter_summaries` |
| User redirected to Summary tab | ~03:18:21 | **Instant load, zero spinner** |

DB persistence also verified: 3 matters persisted (5.8–5.9 KB each), `201 Created` confirmed in worker logs. On-demand fallback still works for pre-existing matters without pre-generated summaries.

**What "done" looks like**: Upload a document, wait for processing to complete, click Summary tab — summary is already there. No spinner, no wait. If Redis evicts (1-hour TTL), DB fallback serves instantly.

---

#### 4. Q&A processing guard — DONE (2026-04-29)

**Bug IDs**: UX-002 | **Actual effort**: ~6 hours | **Files**: 4 changed (1 backend, 2 frontend, 1 skill)

**What was implemented**:
1. **Backend guard** (`chat.py`): `_check_processing_status()` queries `documents` table for non-terminal statuses + `chunks` table for embedding counts. Two-tier logic: Gate 1 blocks entirely (zero usable chunks), Gate 2 warns (partial embeddings). Applied to both `stream_chat()` (SSE) and `send_message()` (sync). Single convergence point — no "must remember to" pattern.
2. **Frontend error display** (`QAPanel.tsx`): `DOCUMENTS_PROCESSING` error code shows inline `ErrorAlert` with "Try Again" button instead of auto-dismissing toast.
3. **Frontend SSE fix** (`useSSE.ts`): Attached error `code` property to SSE Error objects. Fixed stream-end logic that was overwriting processing guard errors with generic "Connection lost" message.

**Bugs found during testing**:
- `_PROCESSING_STATUSES` initially missing `ocr_complete` and `pending_review` — document at `ocr_complete` stage slipped past guard. Fixed by verifying against `DocumentStatus` enum.
- `useSSE.ts` stream-end cleanup (line 620-647) creates a new "Connection lost" error when stream ends without `complete` event, overwriting the `DOCUMENTS_PROCESSING` error. Fixed by checking `eventCountRef.current === 0` before creating disconnect error.

**Production verification** (2026-04-29):

| Test | Scenario | Result |
|------|----------|--------|
| Completed matter Q&A | Nirav Jobalia — "What is this case about?" | Full response with 7 citations, 7565ms. No guard interference. |
| Processing matter Q&A | Fresh upload, 0% complete, 0 chunks | Blocked: "Your documents are still being processed. Q&A will be available once processing completes." + Try Again button |
| Completed matter regression | Nirav Jobalia — second question after guard deployed | Normal response, no regression |

**Known limitation**: Guard currently shows reactive `ErrorAlert` ("Something Went Wrong") after user submits query. Better UX would be a proactive informational banner before user types (see UX-014).

---

### Tier 2 — Reliability (weeks 3-5)

These prevent silent failures that erode trust. Less visible than Tier 1, but critical before exposing the product to free users at scale.

#### 5. Beat process isolation

**Bug IDs**: INF-010, E2E-006 | **Effort**: 2-3 days | **Files**: `railway.toml`, new `start-beat.sh`

**The problem**: RedBeat scheduler runs in the same process as the worker. When 4 concurrent documents saturate the worker (observed in E2E), beat's lock-extension tick gets starved → lock expires → `LockNotOwnedError` → beat crashes → **all 16 periodic tasks stop firing silently**. Recovery sweeps stop, stuck documents accumulate, no alert fires. This happened during E2E (confirmed in logs).

**What changes**: Run beat as its own lightweight Railway service. Tiny container (~100MB, no heavy imports). Consumes no task queues — only runs the scheduler. Independent restart if it crashes. This is the ARCH-002 wall: physical process isolation, not configuration.

**What "done" looks like**: Kill the worker service → beat keeps running. Saturate the worker with 10 concurrent documents → beat still fires all 16 periodic tasks on schedule.

---

#### 6. Non-converging sweep fix — DONE (2026-05-13)

**Bug IDs**: E2E-007 | **Actual effort**: ~1 hour | **Files**: `backend/app/workers/tasks/maintenance_tasks.py`

**What was built**: Structural fix (not the originally planned tactical fix). Upgraded `_is_pipeline_data_complete()` to accept `document_type` parameter with per-type completion criteria. Acts with 0 chunks are legitimately complete (library pipeline). Non-acts require chunks + embeddings + entity_mentions. All 4 callers updated. `recover_stuck_documents` now uses this function instead of raw chunk_count heuristic — documents that ARE complete are skipped, stopping the infinite re-dispatch loop.

**This is a step toward the wall, not a sticky note.** `_is_pipeline_data_complete()` is now a single source of truth for document completion — the same function the ARCH-003 reconciler will use. The 13 sweeps still exist, but the convergence logic is centralized.

---

#### 7. Library document cleanup

**Bug IDs**: E2E-003 | **Effort**: 1 day | **Files**: data fix (SQL), no code change

**The problem**: ~10 library documents have records in `library_documents` table but their PDFs don't exist in Supabase storage. Tasks fail with `storage_missing` on worker startup. Affected: `arbitration_and_conciliation_act_1996.pdf`, `indian_contract_act_1872.pdf`, `constitution_of_india_1950.pdf`, etc.

**Two options**: (a) Upload the missing PDFs to storage (they're publicly available Indian statutes). (b) Delete the orphan database records. Option (a) is better — these acts are used for citation verification.

---

#### 8. Escalation threshold audit — UNBLOCKED (Phase 1 metadata now shipping)

**Bug IDs**: E2E-005 | **Effort**: 1 day (after data accumulates) | **Files**: `config.py` (one float)

**Current state (updated 2026-04-27)**: `confidence_threshold = 0.5` (`comparator.py:452-454`). Phase 1 metadata is now deployed and verified — screening confidence values are persisting to `llm_costs.metadata` as of 2026-04-27. First production data shows `needs_review` results clustering at confidence 0.8-0.9 and `consistent` results at 0.95-1.0. Need ~50-100 more screening calls to get a full distribution.

**What to do when data accumulates**: Query:
```sql
SELECT metadata->>'screening_confidence' as conf, 
       metadata->>'screening_result' as result, 
       COUNT(*) 
FROM llm_costs 
WHERE operation = 'contradiction_screening' 
  AND metadata->>'screening_confidence' IS NOT NULL
GROUP BY conf, result 
ORDER BY conf;
```
Find the confidence range where Gemini says "consistent" but we still escalate. If most wasted escalations cluster at 0.40-0.49, lower threshold to 0.35. This is potentially the single biggest cost lever (~$5-6 savings per 4 documents, ~30% total cost reduction).

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

### ARCH-007: Document Classification Is Fire-and-Forget with No Recovery Path
| Field | Value |
|-------|-------|
| **Severity** | P1 (Architectural) |
| **Status** | OPEN |
| **Date Found** | 2026-04-29 (E2E verification — TORTS Act 1992 uploaded as Case File) |
| **Source** | E2E visual verification + blast-radius deep research |

**Observed symptom**: User uploaded "TORTS Act 1992.pdf" via the Create New Matter page. The system classified it as "Case File", ran it through the full document pipeline (OCR → chunking → embedding → entity extraction → citation detection → contradiction detection), wasted ~5 minutes of Document AI time, hit a 300s OCR timeout, and will exhaust 3 retries producing zero useful output. The document is a statute — it should have been routed to the `library_documents` table with the simpler library pipeline (OCR → chunk → embed, no entity/citation/contradiction work).

**The system the classification sits inside**: Jaanch has a sophisticated **library document system** with 4 entry paths into `library_documents`:

| Path | How it works | Status |
|---|---|---|
| **A. User upload as Act** | Frontend sends `document_type=act` → `_upload_act_to_library()` (documents.py:407-523) → `library_documents` table → `matter_library_links` | **Plumbing works, but frontend has no UI to select Act — always sends `case_file`** |
| **B. Auto-fetch from India Code** | Citation engine detects Act mentions in case files → `act_validation_tasks.py` validates → `IndiaCodeClient` downloads PDF from indiacode.nic.in → creates `library_documents` + links to matter → `ocr_and_process_library_document` | **Works for central Acts on India Code; fails for state acts, common law, non-Indian sources** |
| **C. Document promotion** | Admin promotes existing `documents` row to library via `library_service.py:776-933` → copies chunks to `library_chunks` | **Works but requires manual admin action** |
| **D. Direct library upload** | API route exists (`library.py:126-190`) | **Not implemented — no frontend UI** |

**The auto-fetch pipeline (Path B) is mature but backwards-only**: It detects "Indian Contract Act, 1872" *cited inside a case file* and auto-fetches it from India Code. But if you hand it "Indian Contract Act 1872.pdf" directly, it doesn't recognize it as an Act. The screenshot confirms this works — the "5 & 10 kiarabinwani" matter shows "Arbitration and Conciliation Act, 1996" in the Linked Library section, auto-fetched via Path B. But "TORTS Act 1992.pdf" uploaded directly went to the wrong pipeline.

**Six structural flaws identified**:

**Flaw 1 — No classification at upload**: The upload form (`frontend/src/app/upload/page.tsx`) has no document type selector. `document_type` defaults to `case_file` in both backend (documents.py:1041) and frontend API client (documents.ts:84). The backend plumbing for `document_type=act` exists and works (Path A) — but the frontend never sends it.

**Flaw 2 — No auto-detection from filename or content**: `_extract_year_from_filename()` exists (documents.py:400) but only runs *after* manual Act classification. No regex checks the filename for "Act", "Code", "Statute" patterns. No content-based classification exists. A file literally named "TORTS Act 1992.pdf" gets zero special treatment.

**Flaw 3 — Four entry paths, no shared classification gate**: Each path makes its own classification decision independently. Path A relies on frontend (which has no UI). Path B relies on citation regex in other documents. Path C relies on admin initiative. Path D doesn't exist. There is no single "is this an Act?" gate that all documents flow through. This is the **ARCH-003 pattern** — "remember to signal" coordination applied to classification.

**Flaw 4 — Misclassified documents have no recovery path**: Once "TORTS Act 1992.pdf" enters as `case_file`:
- Full expensive pipeline runs (entities, citations, contradictions — all nonsensical for a statute)
- There's no "reclassify" action — `DocumentList.tsx` has a type dropdown (lines 329-411) but changing type post-processing doesn't undo pipeline work, doesn't move the document to `library_documents`, doesn't delete garbage entities/contradictions
- User would have to: delete document → re-upload → somehow choose "Act" (which has no UI)
- The system produces garbage data (contradictions within a statute, entity mentions of section numbers) that pollutes the matter's analysis

**Flaw 5 — Two parallel chunk tables, two RAG paths**: Regular documents use `chunks` + `match_chunks()`. Library documents use `library_chunks` + `match_library_chunks_for_matter()`. Q&A must query both and merge. This is **ARCH-001 pattern** — two parallel paths for the same logical work. If one path has bugs or is missing results, the user gets incomplete answers with no indication why.

**Flaw 6 — No feedback loop from processing to classification**: After OCR extracts text full of "Section 1", "Section 2", "WHEREAS", "Be it enacted by Parliament" — nothing in the pipeline says "this looks like a statute, not a case file." Classification is a one-time, one-place decision with zero intelligence and no reconciliation.

**Root pattern**: Classification is a one-time, one-place decision made at upload with zero intelligence, and there's no reconciliation afterward. Convention: "the user will choose the right type" → they can't (no UI). "The auto-fetch will find all Acts" → it won't (India Code gaps). "If misclassified, someone will manually fix it" → there's no fix path. Same "vigilance not structure" anti-pattern as ARCH-001 through ARCH-006.

**Fix options (ranked by value/effort)**:

| Fix | Scope | Value | Effort |
|---|---|---|---|
| **1. Upload UI type selector** | Frontend upload page (~1 file) | Users CAN choose Act — but they'll forget | Low |
| **2. Filename heuristic pre-selection** | Backend documents.py (~10 lines) | Auto-suggests "Act" for `* Act YYYY*` filenames | Low |
| **3. Post-upload reclassification** | Backend migration endpoint + frontend action button | Recovery path for misclassified docs | Medium |
| **4. Post-OCR content classification** | New pipeline task with LLM or rule-based detection | Catches Acts regardless of filename | Medium-High |
| **5. Unified chunk table** | Schema migration + RPC refactor | Eliminates ARCH-001 instance (Flaw 5) | High |

**Recommended sequence**: 1+2 first (quick win, covers most cases), then 3 (recovery path), then 4 (catches edge cases). Flaw 5 is structural debt to track but not address immediately.

**Status update (2026-04-30)**: Fixes 1+2 deployed and verified in production. Document type selector UI added to upload wizard (`UploadWizard.tsx`), filename heuristic auto-detects Acts in both frontend (`uploadWizardStore.ts`) and backend (`documents.py:_detect_act_from_filename`). "TORTS Act 1992.pdf" now correctly auto-selects "Act / Statute" and routes to library pipeline. However, blast-radius research revealed the Add Documents dialog (Path 2) has NO type detection and NO selector — fix only covers wizard path. See GAP-9 for full 5-path analysis and unification plan.

**Key files**:
- Upload endpoint: `backend/app/api/routes/documents.py:407-523, 1041-1149`
- Library service: `backend/app/services/library_service.py` (986 lines)
- Library tasks: `backend/app/workers/tasks/library_tasks.py` (904 lines)
- Act validation: `backend/app/workers/tasks/act_validation_tasks.py` (1143 lines)
- India Code client: `backend/app/engines/citation/india_code.py`
- Frontend upload: `frontend/src/app/upload/page.tsx`
- Frontend API: `frontend/src/lib/api/documents.ts:84`
- Document list type dropdown: `frontend/src/components/features/documents/DocumentList.tsx:329-411`
- Library schema: `supabase/migrations/20260126000001_create_library_tables.sql`

#### ARCH-007 Subsystem Audit (2026-04-30) — 16 Gaps Found

Full architectural audit of the library document subsystem. Phase 1 research covered: all 6 migration files, all 5 tables (live schema verified), all entry paths, full processing pipeline, all query paths, maintenance sweeps, and live data queries.

**Live data reality (14 library docs in production)**:

| Status | Source | Total | With Chunks | Without Chunks |
|---|---|---|---|---|
| completed | user_upload | 3 | 3 | 0 |
| completed | india_code | 2 | 1 | **1** |
| failed | india_code | 9 | 1 | 8 |

##### P0 Gaps — Data Loss / Silent Wrong Results

**GAP-1 (P0): User-uploaded Acts never get OCR dispatched** | Status: FIXED (2026-04-30)
`_upload_act_to_library()` (documents.py:537-563) now dispatches `ocr_and_process_library_document.apply_async()` immediately after creating a new library doc. Wrapped in try/except so upload succeeds even if Redis is down — maintenance sweep catches it within 60 min. Response `ocr_queued` field now reads from result dict. Blast-radius verified: no duplicate dispatch risk (sweep has 60-min stale threshold), chunking/embedding are idempotent.

**GAP-2 (P0): Completed library doc with 0 chunks** | Status: FIXED (2026-04-30)
Two guards added to `embed_library_chunks` (library_tasks.py): (1) When no unembedded chunks found, checks total chunk count — if 0, marks FAILED with `quality_flags=["zero_chunks"]` instead of COMPLETED. (2) After embedding loop, if `embedded_count == 0` but chunks existed, marks FAILED with `quality_flags=["embedding_failed"]`. Both return (not raise) so `fire_library_callbacks` can check status and skip — verified that it does. Data fix: `environment_protection_act_1986` moved from completed→failed.

**GAP-3 (P0): 77% of library chunks missing embeddings** | Status: FIXED (2026-04-30)
Root cause: all 56 missing embeddings belonged to ONE document (Bharatiya Nyaya Sanhita, 2023). Chunking succeeded but embedding failed; `quality_flags` was incorrectly set to `["chunking_failed"]`. All other completed docs had 100% embeddings. Data fix: reset BNS to `status=pending`, `quality_flags=[]`. Maintenance sweep will re-run pipeline — chunking will skip (idempotent, 56 chunks exist), embedding will process the 56 unembedded chunks.

##### P1 Gaps — Significant Functionality Gaps

**GAP-4 (P1): Voyage embeddings never populated for library chunks** | Status: FIXED (2026-05-06)
`embed_library_chunks` now generates both OpenAI and Voyage embeddings in a single pass. Voyage embedding is best-effort (wrapped in try/catch) — if Voyage API key is missing or fails, OpenAI embeddings still work. Existing 89 library chunks have 0 Voyage embeddings (will populate on next library doc processing). Fix in `library_tasks.py`.

**GAP-5 (P1): 9 failed india_code library docs (7 with `storage_missing`)** | Status: PARTIALLY FIXED (2026-04-30)
Investigation revealed PDFs DID download from India Code and were cached to Supabase Storage — `act_validation_cache` shows `validation_status=valid` with `cached_storage_path` for all 9. Files disappeared from storage between caching and OCR (likely storage path convention change: some docs have `documents/library/central_acts/...` path while cache has `global/acts/...`). 1 doc (BNS) fixed via GAP-3 re-embedding. 7 `storage_missing` docs need re-fetch from India Code (reset cache entries + re-run `fetch_acts_from_india_code`). 1 doc (Presidency Towns) has `validation_status=unknown`.

**GAP-6 (P1): 3 act_resolutions stuck in `auto_fetching` for 69 days** | Status: FIXED (2026-04-30)
Data fix: 3 act_resolutions moved from `auto_fetching` → `not_on_indiacode`. Two were duplicates for `contempt_of_courts_act_1971`, one was garbage name `said_act`. Frontend now shows "Upload manually" badge. Verified: no beat task queries `auto_fetching`, no RLS filters by status, polling stops sooner (reduces API calls).

**GAP-7 (P1): No BM25/full-text search for library chunks** | Status: FIXED (2026-05-06)
Added `fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED` column to `library_chunks` + GIN index. Created `bm25_search_library_chunks` RPC function. `hybrid_search.py` now has BM25 fallback for library search — fires when semantic returns <3 results. All 89 existing chunks auto-backfilled. Verified: BM25 search returns ranked results for keyword queries.

##### P2 Gaps — Architectural Debt

**GAP-8 (P2): `chunks` vs `library_chunks` schema divergence** | Status: FIXED (2026-05-06)
Added 5 missing columns to `library_chunks`: `fts` (tsvector), `embedding_model_version` (text), `layout_derived` (boolean), `text_start_offset` (integer), `text_end_offset` (integer). Columns intentionally NOT added: `matter_id` (library is cross-matter), `entity_ids`/`bbox_ids` (matter-scoped). Migration: `20260506000003_add_schema_parity_library_chunks.sql`.

**GAP-9 (P1): Upload path fragmentation — 5 entry points, inconsistent classification** | Status: PARTIALLY FIXED

Deep blast-radius research (2026-04-30) revealed the upload system has **5 distinct entry paths** with inconsistent document type handling. This is an instance of both ARCH-003 ("remember to signal" coordination) and ARCH-001 (parallel duplicate paths).

**All 5 entry paths mapped:**

| # | Entry Path | Trigger | Type Detection | User Control | Store | Post-Upload UX |
|---|---|---|---|---|---|---|
| 1 | **Upload Wizard** | "New Matter" on dashboard | Auto-detect regex + backend safety net | Dropdown selector (4 types) | `uploadWizardStore` | Processing page with progress, live discoveries, completion screen |
| 2 | **Add Documents Dialog** | "Add Files" on matter docs tab | **NONE** — hardcodes `case_file` | **NONE** | `uploadStore` (separate) | Toast + dialog close + list refresh |
| 3 | **Act Upload Dropzone** | Missing act in citations tab | N/A — hardcodes `act` | N/A (purpose-built) | Local state only | Green checkmark + toast |
| 4 | **"Set as Act" menu** | Three-dot menu on document | Explicit user action | Click to confirm | N/A | Toast + list refresh |
| 5 | **Bulk type change** | Multi-select + bulk action | Explicit user action | Type dropdown | N/A | Toast |

**7 specific gaps identified:**

1. **Add Documents dialog has no type selector or auto-detection (P1)**: `UploadDropzone.tsx` accepts `documentType` prop but `AddDocumentsDialog.tsx` never passes it — defaults to `case_file`. Backend safety net (`_detect_act_from_filename`) catches obvious filenames but user gets no visibility that their file was reclassified and may be confused when the doc "disappears" from the document list (goes to library). Files that are acts but don't match the regex (e.g., "BNS_2023.pdf") silently enter the wrong pipeline.

2. **ZIP extraction hardcodes all files as `case_file` (P2)**: `_extract_and_upload_zip()` (documents.py:978) uses `DocumentType.CASE_FILE` for every file inside a ZIP. No per-file act detection. The outer auto-detection at line 1143 only affects the ZIP-vs-PDF routing decision, not individual file classification. A ZIP containing "Indian Contract Act 1872.pdf" processes it as a case file.

3. **Two separate Zustand stores for upload state (P2, tech debt)**: `uploadWizardStore` (278 lines, full-featured: processing stages, live discoveries, progress tracking) vs `uploadStore` (simpler: just queue + uploading flag). Same logical operation, two implementations with different capabilities. Every upload improvement must be done twice.

4. **Bulk type change to 'act' doesn't trigger library promotion (P2)**: `PATCH /documents/bulk` (documents.py:1378-1449) sets `document_type` metadata only — does NOT call `promote_document_to_library()`. Document stays in `documents` table without library processing. Contrast with single-doc `PATCH /documents/{id}` which DOES promote. Inconsistent behavior.

5. **No reverse action to un-classify an act (P3)**: "Set as Act" exists in the three-dot menu but there's no "Set as Case File" reverse. Once a document enters `library_documents`, no UI path moves it back. Recovery requires direct DB access.

6. **Backend safety net reclassifies silently — UX confusion (P2)**: When `_detect_act_from_filename` triggers on the Add Documents path, the file goes to `library_documents` and appears in LinkedLibraryPanel, not the documents list. User sees their file "disappear". Backend logs the reclassification but frontend shows no notification.

7. **Recovery mode on processing page loses `documentType` (P3)**: If user refreshes the processing page mid-upload, `documentType` from the wizard store is lost. Subsequent uploads default to `case_file`. Not persisted to URL params or sessionStorage.

**Root cause**: The system was built wizard-first (Path 1), then the Add Documents dialog (Path 2) was added later as a simpler flow without carrying over the type detection/selection capabilities. Each new entry point must independently remember to implement classification logic — classic ARCH-003 "remember to signal" pattern.

**Long-term fix plan (2026-04-30)**:

Unify all upload paths into one shared component. The backend is already unified (single `POST /api/documents/upload` endpoint) — fragmentation is purely frontend.

**Architecture target:**
```
SharedUploadDropzone (one component, one store)
  - File selection (drag/drop/browse)
  - Document type auto-detection + selector
  - Validation + progress tracking
      │ used by:
      ├── Upload Wizard (+ matter creation, processing page)
      ├── Add Documents Dialog (existing matter)
      └── Act Dropzone (pre-set to 'act', no selector)
```

**4 steps, one deploy, one test pass:**

| Step | What | Where | Effort | Fixes |
|---|---|---|---|---|
| 1 | Merge type detection + selector into `UploadDropzone` | `UploadDropzone.tsx` — add `showTypeSelector` prop (default true), `initialDocumentType` prop, reuse `detectDocumentTypeFromFilename()` from wizard store | ~1h | Gaps 1, 6 |
| 2 | Consolidate to one Zustand store | Keep `uploadWizardStore` for wizard-specific state (matter name, stages, live discoveries), but move upload mechanics (file queue, progress, type) into shared hook or merge stores | ~1-2h | Gap 3 |
| 3 | ZIP per-file act detection in backend | `_extract_and_upload_zip()` — check each PDF filename with `_detect_act_from_filename()`, route to `_upload_act_to_library()` if Act | ~30m | Gap 2 |
| 4 | Bulk update promotion for acts | `bulk_update_documents()` — call `promote_document_to_library()` when type changes to 'act' (same logic as single-doc PATCH) | ~30m | Gap 4 |

**What stays separate (correctly):**
- Upload Wizard keeps multi-step UX orchestration (FILE_SELECTION → REVIEW → UPLOADING → PROCESSING)
- Act Dropzone keeps single-file specialized UX with `initialDocumentType='act'`, `showTypeSelector=false`
- "Set as Act" stays as post-hoc reclassification (different concern)

**Estimated total**: ~4-5h including testing all 5 paths. Eliminates gaps 1-4, 6 permanently. Gap 5 (no un-act) is a feature request. Gap 7 (recovery mode) is nice-to-have.

**GAP-10 (P2): `section_title` always NULL in library_chunks** | Status: OPEN (tracking)
Schema has the column for section-level search. Chunker never populates it. Missed opportunity for "Section 4 of Indian Contract Act" queries.

**GAP-11 (P2): Library document cost tracking absent** | Status: FIXED (2026-05-06)
`embed_library_chunks` now passes `document_id=library_document_id` through to the embedder, which passes it to `CostTracker`. Library embedding costs are now attributable to specific library documents in `llm_costs` table. Also added `document_id` parameter to `EmbeddingService.embed_batch()` and `_call_openai_batch_embedding()` for general use.

**GAP-12 (P2): Deduplication logic inconsistent across entry paths** | Status: FIXED (2026-05-06)
All 3 creation paths now use `find_library_duplicates` RPC (trigram similarity, 0.6 threshold) instead of ad-hoc inline `ilike` checks. Updated: `_upload_act_to_library()` (documents.py), `_find_library_document_by_title()` (act_validation_tasks.py), `promote_document_to_library()` (library_service.py). Each path has ilike fallback if RPC fails. Verified: RPC correctly finds duplicates with proper similarity scoring.

##### P3 Gaps — Nice to Have

**GAP-13 (P3): RLS INSERT policy requires `added_by = auth.uid()`** — India Code auto-fetch sets `added_by: None`. Works only because backend uses `service_role` client. Would fail with authenticated client.

**GAP-14 (P3): No soft-delete for library documents** — No way to remove bad library docs without direct DB access.

**GAP-15 (P3): `quality_flags` format inconsistent** — Some paths set list `["storage_missing"]`, others set string. Schema is jsonb, accepts both, consumers must handle both.

**GAP-16 (P3): No `error_message` column on library_documents** — When processing fails, only info is quality_flag. `documents` table has `ocr_error`; `library_documents` doesn't.

##### Architecture Recommendations (from audit)

1. **Keep separate tables** — `library_chunks` vs `chunks` RLS models and column sets are genuinely different. But enforce schema contract: any change to `chunks` must be evaluated for `library_chunks`.
2. **Explicit dispatch, not reconciler** — Every entry path dispatches OCR synchronously. Maintenance sweep stays as safety net, not primary dispatcher. Reconciler deferred until beat isolation is stable.
3. **Completion verification** — Never set status=completed without checking chunk count > 0 AND embedding count > 0.
4. **Fix order**: GAP-1 (5 lines) → GAP-2 (10 lines) → GAP-3 (investigate) → GAP-5 (data fix). GAP-4, GAP-7, GAP-8, GAP-11, GAP-12 all FIXED (2026-05-06).

---

**Common thread across all seven**: implicit coordination through convention instead of explicit coordination through structure. Two pipelines that "should" stay in sync (ARCH-001), four queues that "should" be isolated (ARCH-002), a chain that "should" reach its terminal task (ARCH-003), 14 LLM call sites that "should" honor the rate limiter (ARCH-004), a Postgres function that "should" stay signature-compatible across two repos (ARCH-005), 36 TypeScript files that "should" mirror Pydantic models exactly (ARCH-006), a library subsystem with 4 entry paths that "should" all dispatch OCR (ARCH-007). None are enforced by the architecture, all have been violated in production, and each violation has cost a debugging session — sometimes a multi-day one. The fix in every case is the same shape: **make the right thing the only possible thing.** Structure beats vigilance.

---

## 1. Security

### SEC-002: Supabase Linter Warnings (2026-05-08) | Status: PARTIALLY FIXED (A+B+C fixed 2026-05-13, D migration written, E open)

**Source**: Supabase Dashboard Database Linter. 5 categories of warnings:

**A. `anon` can execute SECURITY DEFINER functions (42 functions)** | Priority: P1 | **FIXED (2026-05-13)**
Unauthenticated users could call these via PostgREST `/rest/v1/rpc/...`. Research confirmed: frontend makes zero `.rpc()` calls, backend uses `service_role` key (bypasses permissions), `handle_new_user` is a trigger (runs as owner), `user_has_matter_access`/`user_has_storage_access` are RLS policy helpers.

**Key finding**: `REVOKE FROM anon` alone is insufficient — Supabase default privileges grant EXECUTE to `PUBLIC` on all functions in `public` schema. Required `REVOKE FROM PUBLIC, anon` to actually block access. Also fixed default privileges for future functions.

**Fix applied**: Migration `20260513000001_sec002_revoke_anon_harden_rpcs.sql`. Verified: 0 SECURITY DEFINER functions callable by anon. `authenticated` and `service_role` retain access.

**B. `function_search_path_mutable` (7 functions, only 4 needed fix)** | Priority: P2 | **FIXED (2026-05-13)**
3 of 7 already had `SET search_path = public`. Fixed the remaining 4: `get_consistency_issue_counts`, `update_consistency_issues_updated_at`, `count_queries_per_matter`, `adjust_bbox_text_offsets`.

**C. Materialized views exposed via API (3 views)** | Priority: P3 | **FIXED (2026-05-13)**
`contradiction_savings_report`, `monthly_cogs_by_matter`, `cost_per_document_page` — admin cost views revoked from `PUBLIC`, `anon`, and `authenticated`. `service_role` retains access.

**D. `extension_in_public` — pg_trgm** | Priority: P3 | Status: MIGRATION WRITTEN (2026-05-13), NOT YET APPLIED
`pg_trgm` installed in public schema. Supabase recommends moving to `extensions` schema.
**Migration written**: `20260513000002_sec002d_move_pg_trgm_to_extensions.sql` — moves pg_trgm to extensions schema, recreates `find_library_duplicates` with `SET search_path = public, extensions`, re-applies REVOKE. **Needs `supabase db push` or manual apply via Supabase dashboard.**

**E. Leaked password protection disabled** | Priority: P2 | Status: OPEN
Supabase Auth HaveIBeenPwned check is off. Enable in Supabase Dashboard > Auth > Settings.

---

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
| **Status** | FIXED (resolved by WPS-001 Layer 3 — Gemini paid tier upgrade) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #10) |

**Description**: `extract_citations` and `resolve_aliases` run in parallel but both use Gemini LLM calls sharing the same distributed rate limiter (`provider=gemini`, `max_rpm=10`). When both tasks fire simultaneously, they saturate the 10 RPM limit and trigger ~2s waits per hit.

**Root Cause**: Single Gemini rate limit bucket (`max_concurrent=1`, `min_delay=6.0s`, `max_rpm=10`) shared by all operations. This is intentional for Gemini free tier (10 RPM). Config is at `backend/app/core/llm_rate_limiter.py:60-71` and is configurable via env vars (`GEMINI_MAX_CONCURRENT_REQUESTS`, `GEMINI_MIN_REQUEST_DELAY`, `GEMINI_REQUESTS_PER_MINUTE` in `config.py:134-136`).

**Fix Applied**: WPS-001 Layer 3 (commit `3581bdd`) upgraded to Gemini Paid Tier 1 (1000 RPM). Rate limiter config updated from 10 RPM → 1000 RPM, min_delay 6.0s → 0.06s, max_concurrent 1 → 10. The 10 RPM bottleneck that caused this bug no longer exists.

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
| **Status** | FIXED (2026-04-17), VALIDATED (2026-04-27), DEAD CODE REMOVED (2026-04-27) |
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

**Production Validation** (2026-04-27):
- 6/6 automated tests pass (`tests/workers/test_dpp002_chain_stops_on_error.py`): chain provably stops on PipelineTaskError, downstream tasks never execute
- All 6 post-deployment DOCUMENT_PROCESSING jobs completed successfully (happy path confirmed)
- Zero SKIPPED stages in `job_stage_history` (old pattern not firing)
- `create_post_ocr_chain()` structurally verified: `link_error` callback attached
- Dead-code skip blocks removed from 5 chained tasks: `calculate_confidence`, `chunk_document`, `embed_chunks`, `extract_entities` (document_tasks.py), `embed_library_chunks` (library_tasks.py)
- Standalone task skip blocks intentionally KEPT: `extract_citations`, `resolve_aliases`, `detect_contradictions` (dispatched via `.delay()`, not in chains)

**Architectural patterns documented**: P7, P8, P9 added to `ARCH-PATTERNS.md`

**Files**: `backend/app/workers/tasks/pipeline_errors.py` (NEW), `backend/app/workers/tasks/pipeline_chains.py`, `backend/app/workers/tasks/document_tasks.py`, `backend/app/workers/tasks/library_tasks.py`, `ARCH-PATTERNS.md`, `backend/tests/workers/test_dpp002_chain_stops_on_error.py` (NEW)

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
| **Status** | FIXED (2026-04-27) — same bug as API-001 |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #8) |

**Description**: After saving citations, the `upsert_act_resolution` Supabase RPC consistently returns HTTP 400 Bad Request. A fallback path (direct `POST` to `act_resolutions` with `on_conflict`) succeeds, but produces noisy logs on every citation batch.

**Root Cause**: The RPC function has `SECURITY DEFINER` set with an `auth.uid()` check inside it (`supabase/migrations/20260106000007_create_act_resolutions_table.sql:135-167`). When called by the service role (which bypasses RLS), `auth.uid()` returns NULL → the auth check fails → 400 Bad Request.

**Fix Applied** (commit `c456312`): Removed the broken RPC call path from `storage.py`. The direct upsert (which was already the fallback) is now the only path. The RPC itself was never needed — service-role calls bypass RLS, so the RPC's `SECURITY DEFINER` + `auth.uid()` check was both unnecessary and broken.

**Files**: `backend/app/engines/citation/storage.py`

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
| **Status** | FIXED (2026-05-13) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #11) |

**Description**: During contradiction screening, Gemini occasionally returns `None` instead of valid JSON.

**Original claim was WRONG**: Bug report said "falls back to GPT-4o (15x more expensive)". **Live DB disproves this**: `SELECT provider, COUNT(*) FROM llm_costs WHERE operation='contradiction_screening' GROUP BY provider` → `gemini-2.5-flash: 5,561 calls (100%)`, GPT-4o: 0 calls. Screening NEVER falls back to GPT-4. The 1,287 GPT-4o calls in `contradiction_comparison` are a DIFFERENT operation that intentionally uses GPT-4 for deep analysis.

**Actual impact**: When Gemini returns None, the screening retries on Gemini (not GPT-4). Impact is minor latency, not cost.

**Fix Applied (2026-05-13)**: Added null-check before `json.loads()` in `_call_gemini_screening()`. When `response_text` is empty/None, logs a warning and returns `None` — triggering the existing GPT-4 fallback path cleanly instead of raising a noisy exception.

**Files**: `backend/app/engines/contradiction/comparator.py`

---

### LLM-005: Citation Extraction LLM Costs NOT Tracked in DB
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-03-19) |
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
| **Status** | FIXED (2026-05-06) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-003) |

**Description**: After processing a 1-page PDF, Summary tab shows red error: "Generated summary failed validation checks". First thing a new user sees — very bad first impression.

**Root Cause**: Validation thresholds at `summary_service.py:2041-2067` are too strict for small documents. `subject_matter_ok` requires `len(description) > 50` and `key_issues_ok` requires `len(key_issues) > 0`. Small PDFs may not produce enough content.

**Fix Applied (2026-05-06)**: Relaxed `is_summary_valid()` for small docs (<=5 pages): description threshold lowered from 50→20 chars, `subject_matter_ok` alone is sufficient (no longer requires key_issues OR current_status). User-friendly error message replaces raw ValueError. Frontend shows yellow "Limited Summary" alert instead of red error for validation failures.

**Production verified**: Unit test confirms small doc (3 pages, 25-char desc, 0 issues) → valid=True; large doc (20 pages, same content) → valid=False.

**Files changed**: `backend/app/services/summary_service.py`, `backend/app/workers/tasks/summary_tasks.py`, `frontend/src/components/features/summary/SummaryContent.tsx`

---

### UX-002: Q&A Returns Empty Results During Processing
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-04-29) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-004) |

**Description**: While document is processing (70%), Q&A returns "I couldn't find relevant information" with no indication that processing is still in progress. User thinks the app doesn't work.

**Root Cause**: Chat endpoint at `chat.py:105-219` had zero processing-status checks before querying RAG. At 70%, embeddings aren't computed yet so vector search returns 0 matches.

**Fix Applied (2026-04-29)**: Added `_check_processing_status()` guard at top of both `stream_chat()` and `send_message()`. Queries `documents.status` for non-terminal statuses and `chunks` table for embedding counts. Two-tier response: Gate 1 blocks entirely (zero usable chunks) with `DOCUMENTS_PROCESSING` SSE error event; Gate 2 warns via existing `search_notice` pipeline (partial embeddings). Frontend shows inline `ErrorAlert` with "Try Again" button. Also fixed `useSSE.ts` stream-end logic that was overwriting the guard's error with "Connection lost."

**Files changed**: `backend/app/api/routes/chat.py`, `frontend/src/hooks/useSSE.ts`, `frontend/src/components/features/chat/QAPanel.tsx`
**Production verified**: 2026-04-29 — fresh upload blocked with clear message; completed matter Q&A unaffected.

---

### UX-003: Dashboard Shows "Ready" While Processing at 70%
| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | FIXED (2026-04-28) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-005) |

**Description**: Matter card shows green "Ready" badge with 0% Verified while processing is at 70%. Only inside the matter page does it show the processing bar.

**Root Cause (corrected)**: Original report claimed "CITATION_EXTRACTION, CONTRADICTION_DETECTION, VERIFICATION_PROCESSING job types not mapped." **This is wrong** — those job types DON'T EXIST in the DB. The real root cause: `matterStore.enrichMattersWithStats()` fetched tab-stats API (which includes `tabProcessingStatus`) but **only extracted `documentCount` and `issueCount`**, ignoring `tabProcessingStatus` entirely. Then hardcoded `processingStatus: 'ready'` for every matter card.

**Fix Applied (2026-04-28)**: `enrichMattersWithStats()` now extracts `tabProcessingStatus` via `transformTabStatsResponse()` and derives `processingStatus` — if ANY tab is `'processing'`, matter shows as processing. Also activated orphaned `workspaceStore.fetchTabStats()` from `MatterWorkspaceWrapper` on mount + 15s polling during processing.

**Files changed**: `frontend/src/stores/matterStore.ts`, `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx`
**Production verified**: 2026-04-28 — dashboard shows correct status badges, tab counts populated.

---

### UX-004: Activity Feed — Limited to Processing Events Only
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-05-06) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-006) |

**Description**: Dashboard activity feed was originally empty. Now shows processing events but no other activity types.

**Fix Applied (2026-05-06)**: Added `document_uploaded` and `summary_generated` activity types. DB migration adds enum values. Backend creates activities on upload completion (`documents.py`) and summary generation (`summary_tasks.py`). Frontend renders blue Upload icon and green FileText icon for new types. Notification mapping and priority added.

**Production verified (2026-05-06)**: Uploaded Shiju_K_vs_Nalini.PDF → dashboard activity feed shows all 3 entries with correct icons: blue upload icon ("Uploaded document"), green checkmark ("Document processing complete"), green file icon ("Matter summary generated"). Screenshot: `e2e-dashboard-all-activities.png`.

**Files changed**: `backend/app/models/activity.py`, `backend/app/services/activity_service.py`, `backend/app/api/routes/documents.py`, `backend/app/workers/tasks/summary_tasks.py`, `frontend/src/types/activity.ts`, `frontend/src/components/features/dashboard/ActivityFeedItem.tsx`, `supabase/migrations/20260506000002_add_activity_types.sql`

---

### UX-005: "Last opened: Never opened" After Opening Matter
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-05-06) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-007) |

**Description**: Matter card always shows "Last opened: Never opened" because the `lastOpened` timestamp is never updated anywhere.

**Root Cause (two-part)**:
1. **(2026-04-28)** Migration `20260319000001_add_last_opened_at_to_matters.sql` was never applied to production. The column didn't exist, causing a silent 500 error on touch (masked by `.catch(() => {})`). Fixed by applying `ALTER TABLE matters ADD COLUMN IF NOT EXISTS last_opened_at timestamptz DEFAULT NULL`.
2. **(2026-05-06)** Frontend type gap: Backend Pydantic model serializes as `lastOpenedAt`, but the frontend `Matter` TypeScript interface didn't include the field. `transformMatterToCardData()` in `matterStore.ts` didn't map `lastOpenedAt` → `lastOpened`. Result: `MatterCard` always received `undefined` for `lastOpened`, so `formatRelativeTime()` returned "Never opened."

**Fix Applied (2026-05-06)**: Added `lastOpenedAt: string | null` to `Matter` interface in `matter.ts`. Added `lastOpened: matter.lastOpenedAt ?? undefined` mapping in `transformMatterToCardData()`.

**Production verified (2026-05-06)**: Opened "Shiju K vs Nalini" matter → returned to dashboard → card shows "Last opened: Just now". "8 & 9 juhinebhnani4" shows "Last opened: 2h ago". Never-opened matters correctly show "Never opened."

**Files changed**: `frontend/src/types/matter.ts`, `frontend/src/stores/matterStore.ts`

---

### UX-006: Matter Name Flash — "Untitled Matter" on Load
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-04-28) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-008) |

**Description**: Briefly flashes "Untitled Matter" for ~1-2s before loading the real name. No loading skeleton.

**Root Cause**: Skeleton guard already existed at `EditableMatterName.tsx:170` (`if (!matter) return <Skeleton />`), but `fetchMatter()` was only triggered from the component's own `useEffect`, adding latency.

**Fix Applied (2026-04-28)**: Added `fetchMatter(matterId)` call to `MatterWorkspaceWrapper` `useEffect` — fires earlier in the component tree so by the time `EditableMatterName` mounts, data is either cached or fetch is already in flight.
**Production verified**: 2026-04-28 — matter header shows "Nirav Jobalia" immediately, no flash.

**Files changed**: `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx`

---

### UX-007: Processing Status "0 completed, 0 queued" is Confusing
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-04-29 — deployed + visually verified on production) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-009) |

**Description**: Shows "Processing 1 document - 70% complete" AND "0 completed, 0 queued" simultaneously — contradictory.

**Root Cause**: Two separate data sources fed the same banner: `stats` object (fetched once on mount via `jobsApi.getStats()`, never re-fetched) and `jobs` Map (updated in real-time via Supabase broadcast events). Progress events updated the jobs Map but not stats. Stats drifted permanently from reality after the first Realtime event.

**Fix Applied**: `ProcessingStatusBanner` now derives completed/queued counts directly from the `jobs` Map (single source of truth, updated by Realtime). Removed dependency on the separate `stats` object. Both the progress line and the counts line now use the same data source, eliminating the drift.

**Files**: `frontend/src/components/features/processing/ProcessingStatusBanner.tsx`

---

### UX-008: Dashboard "No statistics available" Flash
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (already — verified 2026-04-28) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-010) |

**Description**: Briefly shows "No statistics available" before loading actual stats.

**Root Cause**: Original report said `isStatsLoading = false` initially. Deep research (2026-04-28) found this was **already fixed** — `activityStore.ts:83` initializes `isStatsLoading: true`, which triggers the skeleton path in `QuickStats.tsx:118`. No window exists where `isStatsLoading=false && stats=null` on first render.

**Production verified**: 2026-04-28 — Quick Stats shows "13 Active Matters, 0 Verified, 280 Pending" with no flash of "No statistics available".

**Files**: No changes needed — fix was already in place from a prior session.

---

### UX-009: Contradictions Tab Empty, No Loading State
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-04-28) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-011) |

**Description**: Shows "No Contradictions Found" with hedging message during processing. Cannot distinguish "truly empty" from "not yet processed."

**Root Cause**: Two issues: (1) `workspaceStore.fetchTabStats()` was never called from any component — `tabProcessingStatus` was always empty. (2) `ContradictionsContent` had no access to processing status — only checked SWR `isLoading` (API fetch state), not backend processing state.

**Fix Applied (2026-04-28)**: (1) Activated `fetchTabStats` from `MatterWorkspaceWrapper` on mount + 15s polling. (2) `ContradictionsContent` now reads `tabProcessingStatus.contradictions` from `workspaceStore`. Shows `<ContradictionsProcessing>` spinner when backend is still processing, and "No Contradictions Found" only when processing is confirmed complete.

**Production verified**: 2026-04-28 — contradictions tab shows "20 contradictions found" with data (no false empty state).

**Files changed**: `frontend/src/components/features/contradiction/ContradictionsContent.tsx`, `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx`

---

### UX-010: Summary Page Stuck at "Generating Summary... 0%"
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-04-28) |
| **Date Found** | 2026-03-18 |
| **Source** | Session (Mar 18, Bug #14) |

**Description**: Summary tab shows "Generating Summary... Waiting in queue... 0% complete" indefinitely, even though the API returns complete 200 OK summary data. A full page reload resolves the issue.

**Root Cause (corrected)**: Original report blamed frontend SSE/polling. **Deep research (2026-04-28) found the bug was in the backend API**, not the frontend. The summary endpoint state machine (`summary.py:250-368`) had no handler for `JobStatus.COMPLETED`. When a job completed and Redis cache expired (1-hour TTL), the API found a COMPLETED job but didn't match QUEUED/PROCESSING or FAILED, fell through to the job creation path, and returned `status=GENERATING` — causing the frontend SWR poll to see "generating" forever. The frontend hook (`useMatterSummary.ts`) was working correctly — polling every 3s as designed.

**Fix Applied (2026-04-28)**: Added `COMPLETED` job handler (step 3) to the API state machine — finds completed jobs, retries cache lookup, returns READY if cached. Also fixed the lock-not-acquired path to check cache before creating duplicate jobs.

**Production verified**: 2026-04-28 — summary generates in ~16s, loads from cache immediately on revisit. No more infinite "Generating... 0%" state.

**Files changed**: `backend/app/api/routes/summary.py`

**Remaining concern**: Summary is still generated on-demand (not pre-generated). First visit to Summary tab triggers a ~16s generation. This is the Tier 1 #3 (Summary pre-generation) item, not this bug.

---

### UX-011: Sort/Filter Dropdowns Flash Empty on Dashboard
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-04-29 — deployed + visually verified on production) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-015) |

**Description**: Dropdowns appear empty for ~2-3s before values populate due to SSR/hydration mismatch.

**Fix Applied**: Added `defaultValue` to all 9 `<Select>` components across 3 files, matching store/prop defaults. Removed `suppressHydrationWarning` band-aids from `MatterFilters.tsx`.

**Files changed**:
- `frontend/src/components/features/dashboard/MatterFilters.tsx` — sort (`defaultValue="recent"`), filter (`defaultValue="all"`)
- `frontend/src/components/features/contradiction/ContradictionsFilters.tsx` — severity, type, entity (all `defaultValue="all"`)
- `frontend/src/components/features/verification/VerificationFilters.tsx` — finding type, confidence, status (all `defaultValue="all"`), view mode (`defaultValue="queue"`)

---

### UX-012: Signup — No Resend Verification Option
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-05-06) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-016) |

**Description**: After signup, shows "Check your email" with only a "Back to Login" button. No "Resend" option if email doesn't arrive, no "check spam folder" guidance.

**Fix Applied (2026-05-06)**: Added "Resend verification email" button with 60-second cooldown timer, "check spam folder" helper text, and success/error feedback. Uses `supabase.auth.resend({ type: 'signup', email })`. Rate limit errors from Supabase shown as-is (already user-friendly). Follows existing patterns from `ForgotPasswordForm.tsx`.

**Production verified (2026-05-06)**: Created test account → confirmation screen shows resend button, spam guidance, and cooldown timer after click.

**Files changed**: `frontend/src/components/features/auth/SignupForm.tsx`

---

### UX-013: Processing Status Bar Counts Jobs as "Documents"
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-04-29 — deployed + visually verified on production) |
| **Date Found** | 2026-04-29 |
| **Source** | Production testing during Tier 1 #4 Q&A guard implementation |

**Description**: When a document is processing, the status bar shows "Processing 2 documents" when only 1 document exists. The count comes from `processing_jobs` rows (1 DOCUMENT_PROCESSING + 1 SUMMARY_GENERATION), not from the `documents` table. Users see a higher document count than they uploaded.

**Root Cause**: `selectActiveJobCount` in `processingStore.ts` counted ALL active jobs regardless of `job_type`. `ProcessingStatusBanner` used this count and labeled it "documents". When 1 document had multiple jobs (DOCUMENT_PROCESSING + SUMMARY_GENERATION), the count inflated.

**Fix Applied**: Added `selectActiveDocumentCount` selector that filters to `job_type === 'DOCUMENT_PROCESSING'` and counts unique `document_id` values via Set. Banner now uses `activeDocCount` for the "Processing N documents" label while keeping `activeJobCount` for visibility/spinner logic (banner should still show during any active job).

**Files**: `frontend/src/stores/processingStore.ts` (new selector), `frontend/src/components/features/processing/ProcessingStatusBanner.tsx` (uses new selector)

---

### UX-014: Q&A Guard Shows Reactive Error Instead of Proactive Banner
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low — UX polish) |
| **Status** | FIXED (2026-04-29 — deployed + visually verified on production) |
| **Date Found** | 2026-04-29 |
| **Source** | Production testing during Tier 1 #4 |

**Description**: The Q&A processing guard (UX-002 fix) blocks queries during processing, but uses the generic `ErrorAlert` component ("Something Went Wrong" in red) AFTER the user submits a question. Bad UX: user types a question, waits, then gets a scary red error. They wasted effort and feel the app is broken.

**Fix Applied**: QAPanel now subscribes to `selectActiveJobCount` from processing store (already initialized by parent `MatterWorkspaceWrapper`). When `activeJobCount > 0`:
1. Amber informational banner shown proactively: "Documents are being processed — Q&A will be available once processing completes."
2. Chat input disabled with placeholder: "Q&A available after processing completes..."
3. Red `ErrorAlert` suppressed when banner is active (avoids duplicate messaging)
4. Banner auto-dismisses when processing completes (Supabase Realtime updates flow through processing store → `selectActiveJobCount` recomputes → banner unmounts)

Backend guard (`_check_processing_status()`) remains as safety net for stale frontend state.

**Files changed**: `frontend/src/components/features/chat/QAPanel.tsx` (1 file — no new components, reused existing `Alert`/`AlertDescription`)

---

### UX-015: Processing Page Stuck at 0% After Act Upload (Library Path)
| Field | Value |
|-------|-------|
| **Severity** | P1 (High — user sees broken UI after successful upload) |
| **Status** | OPEN |
| **Date Found** | 2026-04-30 |
| **Source** | GAP-1 verification testing |

**Description**: When a user uploads an Act PDF that matches an existing library document, the upload succeeds (file linked via `matter_library_links`), but the processing page (`/upload/processing`) stays stuck at "Stage 1 of 5: Uploading files" at 0% forever.

**Root cause**: The library path (branch 1 in `_upload_act_to_library`) links an existing library doc without creating a `documents` row or a `processing_jobs` row. The processing page polls `jobsApi.getStats(matterId)` which queries `processing_jobs` — with 0 jobs, it never sees progress. The `useProcessingStatus` hook never returns `isComplete: true`.

**Affected paths**: Any Act upload that links to an existing completed library doc (branch 1). New library docs (branch 2, GAP-1 fix) also lack processing_jobs — the OCR runs in the library pipeline, not the main pipeline.

**Fix direction**: The processing page needs to detect "Act uploaded to library, no processing needed" and complete immediately. Options: (1) Backend returns a signal (`processing_needed: false`) that the frontend uses to skip polling, (2) Frontend detects 0 jobs after upload complete and auto-completes, (3) Create a lightweight processing_job for library-linked Acts.

**Additional symptoms** (same root cause — 0 documents in matter):
- Summary page stuck at "Generating Summary — Waiting in queue... 0%" — summary job created but has no documents/chunks to summarize
- Dashboard matter card shows "0 pages" despite linked library Act having content
- "0% Verified, 0 Issues" — verification runs against `documents`, finds nothing

**Design question**: Should Acts-only matters even show summary/timeline/contradictions? Acts are reference material, not case files. The summary prompts ("What is this case about?") don't make sense for a statute.

**Workaround**: User can click "Back to Dashboard" — Q&A works against library chunks. But the matter looks empty everywhere else.

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
| **Status** | FIXED (2026-05-13) |
| **Date Found** | 2026-02-23 |
| **Source** | BUG-REPORT-2026-02-23.md (BUG-5) |

**Description**: Every Celery health check returns `celery_health_check_no_workers` despite the worker successfully processing tasks (maintenance tasks completing).

**Root Cause**: `inspect.ping()` requires `broker_heartbeat > 0`, which is disabled for Upstash Redis (saves ~233K Redis ops/day). The API service never gets a pong response.

**Fix Applied (2026-05-13)**: Replaced `inspect.ping()` with Redis TTL heartbeat pattern. Worker writes `celery:worker:alive` key with 180s TTL every 60s via beat task (`write_worker_heartbeat`). Health endpoint reads the key via shared `get_sync_redis_client()` (no new connections). Reports healthy + TTL seconds remaining, or unhealthy if key is missing.

**Live verification**: Health endpoint correctly reports "unhealthy" when beat is crashed (INF-010 — pre-existing). Will report "healthy" once beat isolation is fixed.

**Note**: Uses shared `get_sync_redis_client()` from `distributed_lock.py` (`@lru_cache` singleton) — no connection leak risk.

**Files**: `backend/app/api/routes/health.py`, `backend/app/workers/tasks/maintenance_tasks.py`, `backend/app/workers/celery.py` (beat schedule)

---

### INF-006: Network Request Failures (ERR_ABORTED)
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | FIXED (2026-05-13) |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-012) |

**Description**: Multiple `GET /api/jobs/.../stats => [FAILED] net::ERR_ABORTED` during processing page polling. No `AbortController` for overlapping poll requests.

**Root Cause**: `useProcessingStatus.ts` uses `setTimeout`-based polling with no abort logic. If a poll response is slow and the next poll fires, the browser aborts the stale request.

**Fix Applied (2026-05-13)**: Added `AbortController` ref to both `useProcessingStatus.ts` and `useDocumentStatus.ts`. On each poll: abort previous in-flight request → create new controller → pass `signal` to `api.get()`. Catch block swallows `AbortError` (intentional cancellation). Cleanup function aborts on unmount. Blast-radius review caught the second hook (`useDocumentStatus`) which had the same gap.

**Files**: `frontend/src/hooks/useProcessingStatus.ts`, `frontend/src/hooks/useDocumentStatus.ts`

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

*Last updated: 2026-04-29 (full status audit after Tier 1 completion)*

| Category | Total | Fixed | Open | Partially Fixed | Not Reproducible | Not a Bug | Resolved | Mitigated |
|----------|-------|-------|------|----------------|-----------------|-----------|----------|-----------|
| Architectural Debt | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 |
| Security | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Worker & Pipeline Scalability | 3 | 2 | 0 | 1 | 0 | 0 | 0 | 0 |
| Document Processing Pipeline | 16 | 11 | 3 | 0 | 2 | 0 | 0 | 0 |
| LLM & AI Services | 6 | 5 | 1 | 0 | 0 | 0 | 0 | 0 |
| Frontend UX | 14 | 11 | 2 | 1 | 0 | 0 | 0 | 0 |
| Infrastructure | 11 | 7 | 3 | 0 | 0 | 0 | 0 | 1 |
| Other | 4 | 3 | 0 | 0 | 0 | 1 | 0 | 0 |
| E2E Verification | 11 | 1 | 10 | 0 | 0 | 0 | 0 | 0 |
| API | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **76** | **44** | **26** | **2** | **2** | **1** | **0** | **1** |

*Note: DPP-010 (RESOLVED) counted under DPP Fixed. UX-004 counted as Partially Fixed (core fixed, feature gap open). WPS-001 counted as Partially Fixed (layers 1-3 fixed, 4-5 open). INF-011 (MITIGATED) in its own column.*

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

**Round 4 corrections** (2026-04-29 — status audit after Tier 1 completion):
| Bug | Before | After | What changed |
|-----|--------|-------|-------------|
| WPS-003 | OPEN | FIXED | Resolved by WPS-001 Layer 3 Gemini paid tier upgrade (1000 RPM) |
| E2E-001 | OPEN | FIXED | Resolved by Tier 1 #3 summary pre-generation |
| LLM-005 | FIXED (awaiting verification) | FIXED | Dropped stale qualifier — verified by months of production data |
| E2E-004 | OPEN | OPEN (Phase 1 note) | Added note that Tier 1 #1 Phase 1 metadata is deployed |
| E2E-005 | OPEN | OPEN (Phase 1 note) | Added note that screening metadata now persisted |
| UX-013/014 | Out of order | Reordered | UX-014 appeared before UX-013 in file |
| Summary table | 49 total, stale since 2026-03-19 | 72 total, accurate | Full recount including ARCH, E2E, API categories |
| Header | 70 total | 72 total | Corrected miscount (UX-013, UX-014 not counted) |

**Round 5 — UX polish cluster** (2026-04-29 — code complete, deployed + visually verified on production):
| Bug | Before | After | What changed |
|-----|--------|-------|-------------|
| UX-007 | OPEN | FIXED (verified) | Banner derives completed/queued from jobs Map (single source of truth) instead of stale `stats` object fetched once on mount |
| UX-011 | OPEN | FIXED (verified) | Added `defaultValue` to 9 Select components across 3 files; removed `suppressHydrationWarning` band-aids |
| UX-013 | OPEN | FIXED (verified) | New `selectActiveDocumentCount` selector counts unique document_ids from DOCUMENT_PROCESSING jobs; banner shows "Processing 1 document" correctly |
| UX-014 | OPEN | FIXED (verified) | QAPanel shows amber "Documents are being processed" banner + disabled input during processing; verified with live upload |

**Round 5 — E2E walkthrough new bugs** (2026-04-29):
| Bug | Status | What found |
|-----|--------|------------|
| E2E-009 | OPEN | `/api/matters/.../touch` returns 500 — "Never opened" on dashboard |
| E2E-010 | OPEN | CORS missing on `/api/health` — health polling fails silently |
| E2E-011 | OPEN | Summary `forceRefresh=true` returns 401 after token expiry |

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

### DPP-017: `chunk_library_document` crashes on child chunks — `parent_chunk_index` attribute error
| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical — ALL library Act uploads with child chunks fail) |
| **Status** | FIXED (2026-04-30) |
| **Date Found** | 2026-04-30 |
| **Source** | GAP-1 verification — live upload of "TORTS Act 1992 - Copy" |

**Description**: `chunk_library_document` (library_tasks.py:163) accessed `chunk.parent_chunk_index` on `ChunkData` objects, but this attribute doesn't exist. `ChunkData` has `parent_id` (UUID of the parent chunk) and `chunk_index`, not `parent_chunk_index`. This caused ALL library document chunking with child chunks to crash with `AttributeError`.

**Impact**: Parent chunks were inserted before the crash, but child chunks were never created. The chain error handler fired, marking the doc as `failed` with `quality_flags=["chain_error"]`. Embedding never ran. Every Act upload since the parent-child chunker was introduced has been silently failing at the chunking stage.

**Root cause**: The library task used an index-based parent mapping strategy (`chunk_index → DB id`) that didn't match the `ChunkData` API. The main pipeline uses `ChunkData.id` directly as the DB primary key and `ChunkData.parent_id` as the foreign key — the library task should have done the same.

**Fix**: Use `ChunkData.id` as DB primary key (matching main pipeline pattern in `chunk_service.save_chunks()`). Use `chunk.parent_id` directly as `parent_chunk_id` foreign key. Removed the broken `parent_id_map` intermediate step.

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
| **Status** | FIXED (2026-04-29) — resolved by Tier 1 #3 (summary pre-generation) |
| **Source** | E2E verification (2026-04-17) |

**Observation**: After documents complete processing, navigating to the Summary tab showed "Generating Summary... Waiting in queue... 0% complete" with a spinner. Users expected immediate gratification after waiting 15-25 min for document processing.

**Fix Applied (2026-04-29)**: Tier 1 #3 implemented fire-and-forget summary pre-generation from `detect_contradictions`. Summary is now generated as part of the pipeline and persisted to `matter_summaries` table + Redis cache. When user navigates to Summary tab, summary is already there — zero spinner, instant load. See Tier 1 #3 entry for full details.

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
| **Status** | OPEN (Tier 1 #1 Phase 1 metadata deployed 2026-04-27; core perf issue remains) |
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
| **Status** | OPEN (screening metadata now persisted via Tier 1 #1 Phase 1; threshold tuning blocked — see Phase 2) |
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
| **Status** | FIXED (2026-05-13) — structural fix |
| **Source** | E2E verification (2026-04-17) |
| **Arch pattern** | ARCH-003 (non-converging recovery sweep) |

**Observation**: Multiple `finalize_chunked_document` tasks fire for act-type documents that have `status=completed` but no `extracted_text`. Each logs `finalize_skipping_no_text` and returns. Three independent dispatchers exist: (1) chord callback (primary path), (2) `trigger_pending_merges` every 5 min, (3) `recover_stuck_documents` every 15 min. The beat tasks find these documents, dispatch finalize, finalize skips, beat finds them again next cycle. Forever.

**Why this is ARCH-003**: The beat tasks observe state (documents with status X) but don't derive correct terminal state — they just re-trigger the same task. A true reconciler would check "does this document have extracted_text AND OCR chunks? If not, transition to a terminal state that stops future dispatches."

**Fix Applied (2026-05-13)**: **Structural fix** — upgraded `_is_pipeline_data_complete()` in `maintenance_tasks.py` to be the single source of truth for document completion. Added `document_type` parameter with per-type criteria: Acts with 0 chunks are legitimately complete (routed to library pipeline); non-acts require chunks + embeddings + entity_mentions. Updated all 4 callers to pass `document_type`. `recover_stuck_documents` now uses `_is_pipeline_data_complete()` instead of raw chunk_count heuristic — documents that ARE complete (including acts) are skipped, stopping the infinite re-dispatch loop. This is a step toward the ARCH-003 reconciler: one function derives completion from observed DB state, not from "did the right task signal correctly."

**Files**: `backend/app/workers/tasks/maintenance_tasks.py`

---

### E2E-008: OpenAI calls in contradiction detection bypass rate limiter (ARCH-004 instance)
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — structural gap, not yet causing failures at current scale |
| **Status** | FIXED (2026-05-13) — tactical fix |
| **Source** | E2E verification (2026-04-17) |
| **Arch pattern** | ARCH-004 (gateway bypass — asymmetric rate-limiter enforcement) |

**Observation**: During peak contradiction detection (4 docs simultaneously), exactly **1 transient OpenAI retry** observed (`Retrying request to /chat/completions in 0.47s`). Gemini hit **zero 429s** (paid tier 1000 RPM has ample headroom). Railway metrics confirmed: 0% API error rate, worker peaked at 3 vCPU / 3 GB RAM / 500 MB network egress. System handled 4 concurrent docs cleanly.

**Fix Applied (2026-05-13)**: Wrapped `_call_gpt4_comparison()` OpenAI call with `get_rate_limiter(LLMProvider.OPENAI)` async context manager (max_concurrent=5, min_delay=0.1s). Safe to nest inside existing circuit breaker at current load. Gemini and OpenAI now have symmetric rate-limiter enforcement in `comparator.py`.

**Remaining structural debt (ARCH-004)**: This is a tactical fix — the rate limiter is wired by convention at this one call site. The structural fix (domain classes under `services/llm/` where rate limiting is enforced by construction) remains in ARCH-004.

**Files**: `backend/app/engines/contradiction/comparator.py`

---

### API-001: `upsert_act_resolution` RPC returns 400 Bad Request
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — citation resolution falls back to non-RPC path, citations still saved |
| **Status** | FIXED (2026-04-27) — duplicate of DPP-008 |
| **Source** | Deploy monitoring (2026-04-27) |

**Observation**: During citation extraction, `POST /rest/v1/rpc/upsert_act_resolution` returns `HTTP/1.1 400 Bad Request`. Worker falls back to `PATCH act_resolutions` which succeeds.

**Root Cause**: Same as DPP-008 — the RPC uses `SECURITY DEFINER` with `auth.uid()` check, which returns NULL for service-role calls.

**Fix Applied** (commit `c456312`): Removed the broken RPC call path from `storage.py`. Direct upsert is now the only path. See DPP-008 for details.

---

### API-002: Dashboard queries `has_unresolved_alias` column on `identity_nodes` return 400
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — dashboard matter stats silently broken for alias counts |
| **Status** | FIXED (2026-04-27) |
| **Source** | Deploy monitoring (2026-04-27) |

**Observation**: API service logs show repeated `GET /rest/v1/identity_nodes?...&has_unresolved_alias=eq.True` returning `HTTP/1.1 400 Bad Request` for every matter.

**Root Cause**: The `has_unresolved_alias` column was never migrated to the live database — it existed only in the spec. The tab stats service (`tab_stats_service.py`) queried a phantom column.

**Fix Applied** (commit `c456312`): Replaced phantom column query with derived logic: `merged_into_id IS NULL AND aliases != '{}'`. Verified against live DB: 3751 total identity_nodes, 538 match the "unresolved alias" criteria. Dashboard now shows real issue counts instead of silently returning 0.

---

### API-003: Dashboard queries `finding_verifications` with wrong filter syntax return 400
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — dashboard verification stats silently broken |
| **Status** | FIXED (2026-04-27) |
| **Source** | Deploy monitoring (2026-04-27) |

**Observation**: API logs show repeated `GET /rest/v1/finding_verifications?...&confidence=lt.70&decision=is.null` returning `HTTP/1.1 400 Bad Request` for every matter.

**Root Cause**: Wrong column name — the actual column is `confidence_before`, not `confidence`. The `confidence` column doesn't exist on `finding_verifications`.

**Fix Applied** (commit `c456312`): Changed `.lt("confidence", 70)` to `.lt("confidence_before", 70)` in `tab_stats_service.py`. One-character fix.

---

## 8. E2E Verification Findings (2026-04-29)

### E2E-009: `/api/matters/.../touch` returns 500
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-05-06) |
| **Date Found** | 2026-04-29 |
| **Source** | E2E visual verification — browser console errors |

**Description**: Opening a matter triggers `POST /api/matters/{id}/touch` which returns HTTP 500. Seen 3 times across different matters. The `touch` endpoint updates `last_opened_at` for "Last opened" display on dashboard cards.

**Root Cause**: `touch_matter()` in `matter_service.py` had no error handling around Supabase `.execute()` call. Transient Supabase/httpx exceptions bypassed the `except MatterServiceError` catch and became unhandled 500s. Also had a redundant `get_user_role()` call (role already verified by `require_matter_role` dependency), doubling the transient failure window.

**Fix Applied (2026-05-06)**: Removed redundant `get_user_role()` call. Wrapped `.execute()` in try/except — logs warning and swallows failures (touch is non-critical). Changed frontend `.catch(() => {})` to `.catch(e => console.warn(...))` for visibility.

**Production verified (2026-05-06)**: Touch returns 204, zero console errors, `last_opened_at` updated in DB.

**Remaining issue**: Dashboard card still shows "Last opened: Never opened" even after touch writes to DB. The card sorts correctly to top (timestamp is used), but the display text doesn't re-render. This is a pre-existing frontend display bug — see UX-005.

**Files changed**: `backend/app/services/matter_service.py`, `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx`

---

### E2E-010: CORS missing on `/api/health` endpoint
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | NOT A BUG (2026-05-13) |
| **Date Found** | 2026-04-29 |
| **Source** | E2E visual verification — browser console errors |

**Description**: `GET /api/health` from `https://www.jaanch-ai.in` blocked by CORS: "No 'Access-Control-Allow-Origin' header is present". The main API endpoints have CORS configured (INF-003 was fixed), but the health endpoint appears to bypass the CORS middleware.

**Verified NOT A BUG (2026-05-13)**: Live test `curl -H "Origin: https://www.jaanch-ai.in" -v https://jaanch-ai.up.railway.app/api/health` returns correct `Access-Control-Allow-Origin: https://www.jaanch-ai.in` header. Health route goes through FastAPI CORS middleware like all other routes. Original observation was likely a one-time browser cache issue or preflight mismatch.

**Files**: `backend/app/main.py` (CORS config), `backend/app/api/routes/health.py`

---

### E2E-011: Summary `forceRefresh=true` returns 401 after token expiry
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) |
| **Status** | FIXED (2026-05-13) |
| **Date Found** | 2026-04-29 |
| **Source** | E2E visual verification — browser console errors |

**Description**: `GET /api/matters/{id}/summary?forceRefresh=true` returns 401. Seen after navigating between matters. Supabase auth token likely expired mid-session, and the frontend didn't refresh before retrying. Also saw a 404 fallback to Vercel route (`/api/matters/{id}/summary?forceRefresh=true` hitting frontend instead of backend).

**Fix Applied (2026-05-13)**: Fixed SWR `shouldRetryOnError` in `useMatterSummary.ts`. Changed from `err.status >= 402` (which accidentally blocked 401 retry) to `err.status !== 401 && err.status >= 400 && err.status < 500`. Now 401 triggers SWR retry, giving the API client's token refresh interceptor a chance to refresh the Supabase JWT before the retry fires. All other 4xx errors (400, 403, 404, 422) are still non-retryable.

**Files**: `frontend/src/hooks/useMatterSummary.ts`
