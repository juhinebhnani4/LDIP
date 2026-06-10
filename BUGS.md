# BUGS.md — Consolidated Bug Tracker

**Last updated**: 2026-06-04 (GAP-24 FIXED — verifier reaches `library_chunks` section content, Constitution Art 21 flips 0→48 verified; GAP-26 new — Companies-1956 mis-resolved sections false-verify against 2013 Act; beat-reconciler WATCH item. See GAP-24/GAP-26 below.)
**Total bugs**: 122 | **Fixed**: 76 | **Open**: 37 | **Partially Fixed**: 2 | **Not Reproducible**: 2 | **Not a Bug**: 2 | **Mitigated**: 2
**Architectural debts (§0)**: 11 OPEN (ARCH-001..007 backend + FE-ARCH-01..04 frontend)
**Sources**: 4 bug report files + 2 debugging sessions + 2 architectural reviews (2026-04-13) + 1 pipeline audit (2026-04-17) + 2 E2E verifications (2026-04-17, 2026-04-29) + 1 frontend audit + 4-agent code census (2026-05-20) + 1 static×live cross-validation audit (2026-06-01)
**Frontend audit (2026-05-20)**: architectural debts FE-ARCH-01..04 in §0 below; symptoms FE-001..022 in §10 below; evidence (screenshots, repro, console captures) in [`FRONTEND-AUDIT-2026-05-20.md`](FRONTEND-AUDIT-2026-05-20.md).

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
         Cluster 4 (worker/beat stability)       ✓ DONE
         Cluster 3 (contradiction optimization Phase 2+3)  ← Phase 3 DEPLOYED, Phase 2 decision deferred
After:   Cluster 7 (architectural debt — ongoing)
         Cluster 8 (frontend audit 2026-05-20: FE-ARCH-01..04 + 22 symptoms FE-001..022)
```

#### Cluster 1: Library Subsystem — Fix the Data ✓ DONE (2026-04-30)
*Completed in ~1 hour. Code deployed to Railway, data fixes applied, blast-radius verified by 3 parallel agents.*

| Bug | Sev | Status |
|---|---|---|
| **GAP-1**: User-uploaded Acts never get OCR dispatched | P0 | **FIXED** — OCR dispatch added with try/except + maintenance sweep fallback |
| **GAP-2**: Completed library doc with 0 chunks | P0 | **FIXED** — Zero-chunk guard + all-batches-failed guard in `embed_library_chunks` |
| **GAP-3**: 77% library chunks missing embeddings | P0 | **FIXED** — Single doc (BNS), reset to pending, sweep will re-embed 56 chunks |
| **E2E-003**: Library docs missing from storage | P2 | **FIXED** (2026-05-14) — GAP-19+20 fixed. 8 acts processed: 5,031 chunks, 466 section titles, embeddings flowing. 4/8 completed, 4 embedding in progress. BNS embedded (56/56). |
| **GAP-5**: 9 failed india_code library docs | P1 | **FIXED** (2026-05-20) — Previous cleanup fixed 8/9. Last 1 (`environment_protection_act_1986`) reset + OCR re-triggered. 3 stale resolutions cleaned. |
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

#### Cluster 3: Contradiction Optimization — Phase 2+3 (Phase 3 DEPLOYED 2026-05-20, Phase 2 decision deferred)
*Phase 3 (safe parallelism) deployed 2026-05-20: ~2.5x screening speedup. Phase 2 (prompt tuning) investigated 2026-05-14: hit model capability ceiling, decision deferred pending more data.*

| Bug | Sev | Status |
|---|---|---|
| **E2E-004**: Contradiction detection is pipeline bottleneck | P2 | INVESTIGATED — prompt tuning saves 30% GPT-4o but loses subtle contradictions. No safe prompt found yet. |
| **E2E-005**: Excessive GPT-4o escalation | P3 | INVESTIGATED — 94% of GPT-4o calls are wasted. Metadata change deployed to collect ground truth (2026-05-14). |

**Investigation summary (2026-05-14)**:

Queried production data (804 screened pairs since Phase 1 deploy). Full funnel:
```
804 pairs screened (Gemini Flash)        — $0.38
 ↓ 61% marked "needs_review"
473 escalated to GPT-4o                  — $2.96
 ↓ only 6.1% are actual contradictions
 29 real contradictions stored
444 false positives (93.9%)              — $2.78 WASTED
```

**Shadow tested 3 prompt variants** against 181 pairs (29 known contradictions + 152 sampled non-contradictions). Results:

| Metric | V1 (current) | V2 (aggressive) | V3 (balanced) |
|---|---|---|---|
| Contradictions caught | 28/31 (90%) | 23/31 (74%) | 24/31 (77%) |
| Non-contradictions escalated | 97/150 (65%) | 24/150 (16%) | 68/150 (45%) |
| Projected GPT-4o calls/batch | ~519 | ~128 | ~364 |
| Projected savings vs V1 | — | ~$2.45/batch | ~$0.97/batch |
| Safe to deploy? | (baseline) | **NO** (26% miss) | **NO** (23% miss) |

**Root cause of misses**: 5 of the 7 V3 misses are pairs ALL 3 prompts miss — Gemini Flash sees "same facts, complementary details" but GPT-4o finds subtle legal conflicts (e.g., one statement draws a different conclusion from agreed facts, or a witness's deposition differs from what another witness claims they said). This is a **model capability ceiling**, not a prompt issue.

**The 7 missed pairs are all**:
- `severity: medium`, `contradiction_type: semantic_contradiction`
- Legal interpretation differences, not factual conflicts (no date/amount mismatches)
- Entities: PW1 (3), Nalini (1), K. Parameshwar (1), PW-2 (1), High Court (1)

**The 24 caught pairs include ALL high-value contradictions**:
- Address mismatches (Nirav Jobalia — different addresses across documents)
- Witness testimony conflicts (PW-2 says didn't see crime vs prosecution claims PW-2 reported it)
- Age discrepancies (PW-2: 7 vs 10 years old)

**What was deployed (2026-05-14)**:
- GPT-4o comparison result metadata now persisted to `llm_costs.metadata` (`comparison_result`, `confidence`, `reasoning_preview`). This gives ongoing ground truth for any future optimization.
- Code change: moved cost persistence from `_call_gpt4_comparison` to `_compare_statements` (after parsing) so parsed result is available for metadata.

**Decision deferred — options on the table**:
1. **Keep V1** — $6.40/month at current volume, not urgent. Wait for more metadata.
2. **Deploy V3** — save ~$1.70/month, accept 4 more missed interpretive contradictions as known debt.
3. **Phase 4 (model swap)** — replace GPT-4o with cheaper model. The 10x lever but unproven: no data on whether Haiku/Gemini Pro can match GPT-4o quality on Indian legal contradiction analysis. Not currently in the system (would require new SDK + API key).

**REJECTED during this investigation**:
- Threshold tuning (Phase 2 original plan) — confirmed dead: Gemini returns discrete values, threshold between 0.0 and 0.8 catches nothing.
- Inline shadow testing — hostile review found it doubles screening latency and starves rate limiter. Offline script created instead.

**Files created**: `backend/shadow_test_screening.py` (reusable), `backend/shadow_test_results.json` (V1+V2 raw data), `backend/shadow_test_results_v3.json` (V3 raw data), `backend/shadow_test_report_v2.txt`, `backend/shadow_test_report_v3.txt`.

#### Cluster 4: Worker/Beat Stability ✓ DONE (2026-05-14)
*Completed in phases: beat stability (2026-05-13), fan-out decomposition + coroutine fix (2026-05-14). Hostile review pre-implementation found 7 bugs, 4 risks — all addressed.*

| Bug | Sev | Fix |
|---|---|---|
| **INF-010**: RedBeat lock lost — beat crashes | P1 | **FIXED** (2026-05-13) — removed RedBeat, default scheduler + restart loop |
| **E2E-006**: Redis beat lock extension warning | P2 | **FIXED** (2026-05-13) — same fix, no more Redis lock |
| **WPS-001 L4**: Monolithic `resolve_aliases` task | P2 | **FIXED** (2026-05-14) — 3-phase fan-out: Phase 1 (CPU pairs), Phase 2 (LLM batches ×20 pairs), Phase 3 (persist). Redis counter completion tracking. |
| **WPS-001 L5**: Gevent timeout fiction | P2 | **FIXED** (2026-05-14) — coroutine cancellation in `_run_async` + explicit `TimeoutError` catch. Benefits all ~80 call sites. |
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

**Phase 2: Prompt tuning → INVESTIGATED, HIT MODEL CEILING (2026-05-14)**
- **Original plan**: Lower `confidence_threshold` to reduce escalations. **Dead end** — Gemini's discrete confidence values mean threshold changes between 0.0 and 0.8 catch nothing.
- **Actual cost driver**: The screening prompt (`prompts.py:378-397`) pushes aggressively toward `needs_review` with 5 CRITICAL RULES + "default should be needs_review" + "100x worse to miss." This causes 61% `needs_review` rate. ALL `needs_review` → GPT-4o regardless of confidence. **The lever is prompt tuning, not threshold tuning.**
- **Shadow testing (2026-05-14)**: Built offline shadow test infrastructure (`shadow_test_screening.py`). Tested 3 prompt variants against 181 pairs (31 known contradictions + 150 non-contradictions):
  - **V1 (current)**: 90% catch, 65% false escalation — baseline
  - **V2 (aggressive)**: 74% catch, 16% false escalation — too many misses
  - **V3 (balanced)**: 77% catch, 45% false escalation — still too many misses
- **Finding**: 5 of 7 V3 misses are pairs ALL prompts miss — Gemini Flash cannot distinguish "complementary legal details" from "subtly conflicting legal analysis." This is a model capability ceiling, not a prompt problem. The missed pairs are all medium-severity semantic contradictions (legal interpretation, not factual mismatches). All high-value contradictions (address mismatches, witness testimony conflicts, age discrepancies) are caught by all 3 variants.
- **Deployed**: GPT-4o comparison outcome metadata — every comparison now stores result/confidence/reasoning in `llm_costs.metadata`. Builds ground truth for future optimization.
- **Status**: DECISION DEFERRED — no prompt change is both safe (>90% catch) and effective (<40% escalation). Options: accept status quo, accept V3 debt, or pursue Phase 4 model swap (unproven).
- **No parsing bug**: confidence=0.0 rows are Gemini explicitly returning 0.0 confidence, not a missing field. Low-confidence `consistent`/`unrelated` at 0.0 are correctly escalated to GPT-4o.

**Phase 3: Safe parallelism — DEPLOYED (2026-05-20)**
- **`gemini_min_request_delay`** 0.2 → 0.05 (`config.py:136`, `llm_rate_limiter.py:63` DEFAULT_CONFIGS fallback aligned). Tighter burst stagger, well within 1000 RPM target. InProcessRateLimiter (1000 RPM sliding window) is the binding constraint.
- **`DEFAULT_BATCH_SIZE`** 5 → 10 (`comparator.py:62`). Doubles per-entity throughput. 3 batches of 10 instead of 5 batches of 5 for a 25-pair entity. Stays within `max_concurrent=10` Gemini semaphore.
- **`CONTRADICTION_CONCURRENCY_LIMIT`** 3 → 5 (`document_tasks.py:6187`). Allows 5 entities to process in parallel instead of 3. The Gemini semaphore(10) is the real throttle — entity-level parallelism just reduces idle time between batches.
- **Prerequisites verified**: Beat isolation DONE (2026-05-13), OpenAI rate limiter wired (E2E-008).
- **Hostile review**: 0 bugs found. 3 risks (all pre-existing): RPM burst theoretical ~1200 RPM but capped by InProcessRateLimiter at 1000; SIGTERM during 50 pairs (pre-existing, timeout handler marks job complete); stale comment fixed.
- **Expected speedup**: ~2.5x on screening phase. Pipeline time ~20 min → ~12-15 min. Pending live verification on next document upload.
- **Files changed**: `config.py` (1 line), `llm_rate_limiter.py` (1 line), `comparator.py` (1 line), `document_tasks.py` (2 lines), `test_document_tasks.py` (1 line).

**Phase 4: Research (parallel, no code changes)**
- **GPT-4o replacement research**: The actual cost bottleneck is GPT-4o at $0.0066/call for full analysis. At scale (400 docs/month), this is $2,500-5,000/month — more than revenue from 50 paying users at ₹999. Research Claude Haiku ($0.00025/1K input), Gemini Pro, or fine-tuned smaller model as a replacement for the full analysis tier. This is the 10x lever; everything else is 2x at best.
- **Shadow test Flash Lite**: Run both Flash and Flash Lite on the same pairs, compare results without using Flash Lite results. Collect quality data before switching.

**Expected result (Phase 1+3, both deployed)**: Pipeline time ~20 min → ~12-15 min from parallelism (Phase 3) + skip-1-mention (Phase 1). Phase 2 (prompt tuning) hit model ceiling — decision deferred. Phase 4 (GPT-4o replacement) remains the 10x cost lever.

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

#### 5. Beat scheduler stability — DONE (2026-05-13)

**Bug IDs**: INF-010, E2E-006 | **Actual effort**: ~3 hours (research + implementation + deploy + verification)

**What was built**: Removed RedBeat entirely (speculative dependency for multi-replica leader election that was never needed). Returned to Celery's default `PersistentScheduler`. Added restart loop in `start-worker.sh` so beat auto-recovers from any crash in 10s. Added `CELERY_BEAT_ONLY=true` lean mode that skips heavy task module imports (~1GB RAM savings). Live verified: beat healthy, heartbeat firing, zero `LockNotOwnedError`.

**Why not a separate service**: Research showed beat isolation as a separate Railway service is premature at current scale (1 user, 1 replica). The root cause was RedBeat's distributed lock — not CPU starvation from shared container. Removing RedBeat eliminates the crash mode entirely. A separate service can be extracted later if needed (the lean beat entry point already exists).

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

#### 8. Escalation threshold audit — COMPLETED, threshold is irrelevant (2026-05-14)

**Bug IDs**: E2E-005 | **Status**: INVESTIGATED — threshold tuning is a dead end

**Finding (2026-05-14)**: With 804 screened pairs of metadata, the escalation threshold (0.65) is irrelevant because:
1. Gemini returns only discrete confidence values: {0.0, 0.7, 0.8, 0.9, 0.95, 1.0}
2. `needs_review` (61% of all pairs) always escalates regardless of confidence
3. Only 6 pairs across all data were `consistent`/`unrelated` with conf < 0.65 (at 0.0)
4. The lever is the screening PROMPT, not the threshold — but prompt tuning hit a model ceiling (see Phase 2 above)

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

**Stepping stone deployed (2026-05-14)**: Forensic hunt revealed 10 of 13 document statuses were invisible to ALL 13 sweeps. Only `ocr_complete` and `completed` were queried. `resume_stuck_pipelines` Part A now queries `status NOT IN ('completed', 'failed', 'deleted')` — catching ALL non-terminal docs. `_is_pipeline_data_complete()` is the decision maker. Live verified: first sweep caught 3 stuck docs (pending, ocr_failed, searchable) that no sweep had ever seen. This is the reconciler's WHERE clause — the remaining Tier 3 work is replacing task-side status signaling with derived state.

---

### Tier 4 — Long-term (after free tier is live and generating data)

| # | What | ARCH | Why deferred | When it becomes urgent |
|---|---|---|---|---|
| 12 | **Pipeline unification** | ARCH-001 | Both paths work (E2E proved it). 6,471 + 1,926 lines of code. Largest refactor. | When we need to add a new pipeline stage and have to do it twice. |
| 13 | **Full worker isolation** | ARCH-002 | Partially fixed (dual worker + fan-out). Gevent timeout fiction fixed (L5). `resolve_aliases` fan-out fixed (L4). Remaining: per-engine Gemini quota partitioning. | When per-engine quota contention blocks other tenants. |
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
- WPS-001 (worker queue starvation): ALL 5 LAYERS FIXED (L1-3: 2026-04-17, L4-5: 2026-05-14)

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
test -f backend/app/workers/tasks/document_tasks.py && test -f backend/app/workers/tasks/chunked_document_tasks.py && echo "BOTH PIPELINES EXIST = debt OPEN"
wc -l backend/app/workers/tasks/document_tasks.py backend/app/workers/tasks/chunked_document_tasks.py
```
Current: ~6,471 + ~1,926 = ~8,397 lines split across two pipelines. Wall arrives when one file is deleted (or the two merge into one parameterized path) — the optimization for small docs lives *inside* a stage, not as a top-level fork.

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
rg -n "numReplicas|--pool|--concurrency|-Q " backend/railway.toml backend/start-worker.sh
```
Current: `numReplicas = 1` and one process draining `-Q default,llm,heavy,low` with `--pool=gevent --concurrency=50`. Wall arrives when ≥2 worker services consume disjoint queue sets in `railway.toml`. Sub-detector for the deeper ARCH-002b (shared Gemini quota): `rg -n "get_rate_limiter|TokenBucket" backend/app/services backend/app/engines` should show per-task-class bucket usage uniformly, not asymmetric coverage.

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
rg -c "_release_pipeline_lock_safe|_mark_job_completed|_dispatch_post_entity_tasks" backend/app/workers backend/app/api
rg -c "^def (recover_|cleanup_|sync_|trigger_|fix_|dispatch_|resume_)" backend/app/workers/tasks/maintenance_tasks.py
```
Current: 14 call sites of `_release_pipeline_lock_safe` + 13 recovery/reconciliation sweeps compensating for the missing convergence point. Wall arrives when state is derived from observed DB by a single reconciler — and the lock-release / mark-completed call-site count drops to ≤1 (a single `try/finally` or decorator).

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
rg -l "from google.genai import types" backend/app/engines backend/app/services 2>/dev/null | grep -v "core/gemini_client" | wc -l
rg -l "AsyncOpenAI|from openai" backend/app/engines backend/app/services 2>/dev/null | grep -v "core/" | wc -l
```
Current: 14 files reach past `gemini_client.py` with raw `from google.genai import types` (mostly engines/ and services/); plus `engines/contradiction/comparator.py` uses `AsyncOpenAI` directly. Wall arrives at **0** for both — all LLM calls go through `backend/app/services/llm/` domain classes (`CitationLLM`, `ContradictionLLM`, etc.) that own model selection, rate limiting, cost logging, and retry behavior internally.

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
grep -l "CREATE OR REPLACE FUNCTION \(search_\|hybrid_search\)" supabase/migrations/*.sql 2>/dev/null | wc -l
grep -lE "CREATE OR REPLACE FUNCTION (search_|hybrid_)[a-z_]+_v[0-9]+" supabase/migrations/*.sql 2>/dev/null | wc -l
```
Current: 11 unversioned `CREATE OR REPLACE FUNCTION` mutations of `search_chunks` / `search_documents` / `hybrid_search`; **0** versioned. Wall arrives when (a) any new migration introducing a new signature uses `_v[0-9]+` suffix, (b) old versions are dropped only in separate migrations after the API has cut over. (GUARDRAIL-BACKLOG.md B1.5 is the smart-sticky-note that fences new instances.)

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
find frontend/src/lib/api -name "*.ts" -not -name "*.test.ts" -not -name "*.generated.ts" 2>/dev/null | wc -l
ls frontend/src/lib/api/*.generated.ts 2>/dev/null && echo "codegen present" || echo "codegen ABSENT"
```
Current: 36 hand-written `.ts` files mirroring FastAPI Pydantic models; **0** generated files. Wall arrives when `types.generated.ts` (produced by `openapi-typescript` against `/openapi.json`) is the source of truth and the 36 hand-written files become thin wrappers that import generated types — see GUARDRAIL-BACKLOG.md B1.6.

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

**Detector** (run from repo root, retrofitted 2026-05-26 per B4.4):
```
rg -ln "document_type\s*[=:]\s*['\"]?(act|case_file|statute)" backend/app/services backend/app/workers backend/app/api
ls backend/app/services/classification/ 2>/dev/null && echo "classification dir exists" || echo "no shared classifier"
rg -n "_detect_act_from_filename|classify_document" backend/app/api/routes/documents.py
```
Current: 4–5 entry paths each make their own classification decision; no shared `classify_document()` gate; filename heuristic (`_detect_act_from_filename`) exists for the upload wizard path only. Wall arrives when (a) ONE function fronts all entry paths, (b) post-OCR reconciliation can flip a misclassified document to the correct pipeline AND clean up wasted entities/contradictions, (c) the Add Documents dialog (Path 2 per the 2026-04-30 audit) gains the same selector + heuristic.

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

**GAP-5 (P1): 9 failed india_code library docs (7 with `storage_missing`)** | Status: FIXED (2026-05-20)
Investigation revealed PDFs DID download from India Code and were cached to Supabase Storage — `act_validation_cache` shows `validation_status=valid` with `cached_storage_path` for all 9. Files disappeared from storage between caching and OCR (likely storage path convention change: some docs have `documents/library/central_acts/...` path while cache has `global/acts/...`). 1 doc (BNS) fixed via GAP-3 re-embedding. 2026-05-14 cleanup deleted old rows and re-fetched 8 acts successfully (13/14 library docs completed). **Final fix (2026-05-20)**: 1 remaining failed doc (`environment_protection_act_1986`, `quality_flags=["zero_chunks"]`) — PDF was in storage but OCR produced 0 chunks. Reset to `pending`, OCR re-triggered via Upstash Redis LPUSH to `low` queue. **Verified**: status=`completed`, 19 chunks, all 19 with embeddings, resolution moved to `auto_fetched`. **14/14 library documents now completed.** Also cleaned 3 stale `auto_fetching` resolutions: `presidency_towns_insolvency_act_1909` → `not_on_indiacode`, `spatialmappertest` + `testtabledocument` (test artifacts) → `not_on_indiacode`. 3 orphan cache entries (`sale_of_goods_act_1930`, `specific_relief_act_1963`, `transfer_of_property_act_1882`) have cached PDFs but no matching `act_resolutions` — no action needed unless matters reference them.

**GAP-6 (P1): 3 act_resolutions stuck in `auto_fetching` for 69 days** | Status: FIXED (2026-04-30)
Data fix: 3 act_resolutions moved from `auto_fetching` → `not_on_indiacode`. Two were duplicates for `contempt_of_courts_act_1971`, one was garbage name `said_act`. Frontend now shows "Upload manually" badge. Verified: no beat task queries `auto_fetching`, no RLS filters by status, polling stops sooner (reduces API calls).

**GAP-7 (P1): No BM25/full-text search for library chunks** | Status: FIXED (2026-05-06)
Added `fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED` column to `library_chunks` + GIN index. Created `bm25_search_library_chunks` RPC function. `hybrid_search.py` now has BM25 fallback for library search — fires when semantic returns <3 results. All 89 existing chunks auto-backfilled. Verified: BM25 search returns ranked results for keyword queries.

##### P2 Gaps — Architectural Debt

**GAP-8 (P2): `chunks` vs `library_chunks` schema divergence** | Status: FIXED (2026-05-06)
Added 5 missing columns to `library_chunks`: `fts` (tsvector), `embedding_model_version` (text), `layout_derived` (boolean), `text_start_offset` (integer), `text_end_offset` (integer). Columns intentionally NOT added: `matter_id` (library is cross-matter), `entity_ids`/`bbox_ids` (matter-scoped). Migration: `20260506000003_add_schema_parity_library_chunks.sql`.

**GAP-9 (P1): Upload path fragmentation — 5 entry points, inconsistent classification** | Status: MOSTLY FIXED (Gaps 1-6 fixed 2026-05-20; live-tested 2026-05-25; Gaps 5 UI + 7 remain)

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

1. **~~Add Documents dialog has no type selector or auto-detection (P1)~~**: **FIXED (2026-05-20)** — Added document type selector (4 options: Case File, Act/Statute, Annexure, Other) to `AddDocumentsDialog.tsx` above the dropzone, matching the Upload Wizard's pattern. Passes selected type to `UploadDropzone` via existing `documentType` prop. Shows "Acts are stored in the shared library" hint when act is selected. Option B chosen over Option A (modifying UploadDropzone) after 6-criteria blast-radius evaluation — avoids creating a third selector pattern and touching shared components. Also partially fixes Gap 6 (user now explicitly chooses type, reducing silent reclassification surprise).

2. **~~ZIP extraction hardcodes all files as `case_file` (P2)~~**: **FIXED (2026-05-20)** — `_extract_and_upload_zip()` now accepts `library_service` and `document_type` params. Per-file act detection via `_detect_act_from_filename()` routes statute PDFs to `_upload_act_to_library()`. If user explicitly selected "Act / Statute", all ZIP contents go to library. Falls through to normal case_file upload on act-upload failure (continue-on-failure for rollback safety). Call site passes `get_library_service()` and the outer `document_type`.

3. **~~Two separate Zustand stores for upload state (P2, tech debt)~~**: **PARTIALLY FIXED (2026-05-20)** — Root cause was `documents.ts::uploadFile()` importing `uploadStore` directly via `getState()` at 7+ sites, coupling transport to UI state. Fixed by adding `UploadCallbacks` interface: `onProgress`, `onStatus`, `onCompression`, `onUploading`. When callbacks are provided, store is not updated. Both stores remain (correctly — they serve different UX flows), but the transport layer is now decoupled. Future callers (e.g. wizard path) can pass different callbacks without touching the store.

4. **~~Bulk type change to 'act' doesn't trigger library promotion (P2)~~**: **FIXED (2026-05-20)** — `bulk_update_documents` now collects doc objects in `docs_by_id` dict during validation loop, then post-write iterates: calls `promote_document_to_library()` + dispatches `promote_chunks_to_library` for each doc transitioning to act (per-doc try/except, log-but-don't-fail). Also handles the reverse: bulk demotion from act clears `migrated_to_library`/`library_document_id` and unlinks from `matter_library_links`. Write order: clear fields first, unlink second (hostile-review D2 fix — prevents invisible-document state on partial failure).

5. **~~No reverse action to un-classify an act (P3)~~**: **BACKEND FIXED (2026-05-25), UI PARTIALLY FIXED (2026-05-25) — "Set as Case File" menu item added but UNREACHABLE in normal UI flow.** Backend demotion works: `PATCH /documents/{id}` and bulk `PATCH /documents/bulk` handle ACT→non-ACT transitions symmetrically. Bug fix 2026-05-25: `document_service._client` → `document_service.client`. **Frontend "Set as Case File" added to `DocumentActionMenu.tsx`** — menu item shows when `canEdit && isAct`, mirrors "Set as Act" pattern exactly (same handler shape, no confirmation dialog). **But live testing (2026-05-25) revealed a design gap**: when a doc is promoted to Act, `migrated_to_library=True` causes it to be filtered OUT of the document list (`document_service.py:311`). The document vanishes from the table, so the three-dot menu (and the new "Set as Case File" item) is unreachable. The inline type dropdown has the same problem — the row doesn't exist to click on. **The only working demotion paths are**: (a) inline dropdown change in the brief window between API response and list refresh (race condition), (b) bulk select if you catch the doc before refresh. **Actual fix needed (P2)**: Either show promoted acts in the document list with a visual "Promoted to Library" indicator (change the filter), or add a "Remove from Library" / "Demote" action in the `LinkedLibraryPanel` where promoted docs DO appear. The current `DocumentActionMenu` approach is architecturally correct but the document list filter makes it dead UX.

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

**Hostile-review tracked risks (2026-05-20):**

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| HR-A2 | No `link_error` on `promote_chunks_to_library.apply_async` in bulk or single PATCH. Worker crash leaves `migrated_to_library=True` with zero library chunks — library doc permanently incomplete. | P3 (ARCH-003 shape) | Pre-existing pattern (single-doc PATCH has same). Proper fix: reconciler that checks `library_documents.status != 'completed'` with zero `library_chunks` and re-dispatches. |
| HR-A3 | `_upload_act_to_library` in ZIP: if `create_document` succeeds but `link_to_matter` fails, orphaned `library_documents` row persists. | P4 (low probability) | Continue-on-failure design means file falls through to case_file upload. Orphan is harmless (global, no FK violations). Future maintenance sweep could clean library docs with zero `matter_library_links` and `source='user_upload'`. |
| HR-C3 | Two acts with same title in one bulk request can race past `find_duplicates` TOCTOU window and both insert into `library_documents`. No DB unique constraint on title. | P4 (pre-existing) | Pre-existing in `promote_document_to_library`. Fix: add unique constraint on `library_documents(normalized_title)` or similar. Low priority — duplicate library docs are annoying but not data-corrupting. |

**GAP-10 (P2): `section_title` always NULL in library_chunks** | Status: FIXED + VERIFIED (2026-05-14) — 466 section titles populated across 5,031 chunks
Regex-based section title extraction added to `chunk_library_document` (`library_tasks.py`). Detects patterns: Section/Sec./Article/Rule/Order/Schedule/Chapter at start of line. Parent chunks extract section title; children inherit parent's section or extract their own. `SearchResult` and `RerankedSearchResultItem` in `hybrid_search.py` now carry `section_title` through all 5 mapping paths (semantic, BM25, Cohere rerank, 2 fallback-to-RRF). Schema column already existed; RPCs already SELECT it. No migration needed. 12/12 regex unit tests passed. Live verification blocked by GAP-19 (OCR tasks dying before chunks are created).

**GAP-11 (P2): Library document cost tracking absent** | Status: FIXED (2026-05-25) — deployed, not yet exercised in production (needs scanned PDF to trigger Document AI path) — **2026-06-01 re-check: `llm_costs.library_document_id` still NULL on all ~50k rows, no `library_*` operation; confirm on next library ingest before trusting attribution (see §0 Static×Live audit).**
Previous "fix" (2026-05-06) was broken — passed `library_document_id` as `document_id`, which violated the FK constraint on `llm_costs.document_id → documents(id)`. Both OCR AND embedding costs were silently lost (the `persist_cost` catch swallowed the FK error).
**Fix (2026-05-25)**: Added `library_document_id UUID REFERENCES library_documents(id)` column to `llm_costs` (migration `20260525000001`). Added `library_document_id` field to `CostTracker` dataclass. Both `persist_cost()` and `persist_cost_sync()` conditionally include it (only when non-None — deploy-order-safe per hostile review P0 finding). Updated `processor.py` (OCR) and `embedder.py` (embedding) to accept and pass `library_document_id`. Updated `library_tasks.py` to pass `library_document_id=` instead of the incorrect `document_id=` at 2 call sites. **Hostile review caught P1 bug**: recursive `process_document()` call in `processor.py:324` used positional args, passing `enable_image_quality_scores` (bool) as `library_document_id` (UUID) — fixed to keyword args. **Not yet exercised**: Test uploads used pypdf (free, no cost row) and produced 0 chunks (no embedding). The `library_document_id` write path fires only for scanned PDFs (Document AI) or docs with enough content to chunk+embed. Code verified by hostile review + 40+ existing `CostTracker` callers confirmed backward-compatible.

**GAP-12 (P2): Deduplication logic inconsistent across entry paths** | Status: FIXED (2026-05-06)
All 3 creation paths now use `find_library_duplicates` RPC (trigram similarity, 0.6 threshold) instead of ad-hoc inline `ilike` checks. Updated: `_upload_act_to_library()` (documents.py), `_find_library_document_by_title()` (act_validation_tasks.py), `promote_document_to_library()` (library_service.py). Each path has ilike fallback if RPC fails. Verified: RPC correctly finds duplicates with proper similarity scoring.

##### P3 Gaps — Nice to Have

**GAP-13 (P3): RLS INSERT policy requires `added_by = auth.uid()`** — India Code auto-fetch sets `added_by: None`. Works only because backend uses `service_role` client. Would fail with authenticated client.

**GAP-14 (P3): No soft-delete for library documents** — No way to remove bad library docs without direct DB access.

**GAP-15 (P3): `quality_flags` format inconsistent** — Some paths set list `["storage_missing"]`, others set string. Schema is jsonb, accepts both, consumers must handle both.

**GAP-16 (P3): No `error_message` column on library_documents** — When processing fails, only info is quality_flag. `documents` table has `ocr_error`; `library_documents` doesn't.

**GAP-17 (P2): Library doc status-update-on-failure silently swallowed** | Status: MITIGATED (2026-05-25) — observability added, sweep is primary recovery
**Original issue**: 3 `except Exception: pass` blocks in `library_tasks.py` silently swallowed failures when setting status=FAILED during error handling. If Supabase was down, documents stayed at `processing` indefinitely with zero log evidence.
**Fix (2026-05-25)**: Replaced 4 bare `except Exception: pass` blocks with `except Exception as e: logger.error(...)` at lines ~248 (chunk failure), ~524 (embed failure), ~847 (OCR max retries), ~1062 (promote OCR fallback dispatch). Phase 2 research found a 4th block (line 1062) that Phase 1 missed — swallows failed OCR fallback dispatch, not a status update. Each log includes structured event name (`status_update_on_failure_swallowed` or `ocr_fallback_dispatch_swallowed`), the original error, and the library_document_id. **Control flow unchanged** — the `pass` behavior is the same, only observability is added.
**Recovery**: `resume_stuck_pipelines` sweep (GAP-18 fix, 2026-05-14) catches all 4 scenarios within 15-75 minutes. The sweep is effectively the primary authority (ARCH-003 reconciler stepping stone). Task-side status writes are belt-and-suspenders.
**Not triggered in production** (2026-05-25) — requires Supabase outage during library task failure. Worker logs show clean task execution with the new code deployed. Related: DPP-016, GAP-16.

**GAP-18 (P1): `resume_stuck_pipelines` early return skips library recovery** | Status: FIXED (2026-05-14)
`maintenance_tasks.py:1185` had `return results` when no regular `documents` were stuck — this returned BEFORE reaching the library_documents recovery at line 1462. Library recovery was **dead code** whenever no regular docs were stuck (the common case). This is why E2E-003 docs were never auto-recovered. **Fix**: removed early return, added `or []` guards on `stuck_docs.data`. The sweep now correctly falls through to the library check. Verified in production: sweep at 08:25 found and dispatched 4 library docs (`resumed=4`). Related: GAP-17, E2E-003.

**GAP-19 (P1): Library OCR tasks silently die on large PDFs — no timeout, gevent blocking IO** | Status: FIXED (2026-05-14)
Discovered 2026-05-14. `ocr_and_process_library_document` has no `soft_time_limit`/`time_limit` — inherits global 55min/60min from `celery.py`. For large statutes (Constitution of India = 400+ pages → 27 Document AI chunks; Income Tax Act = 900+ pages → 60 chunks), OCR takes 27-60+ minutes of blocking gRPC calls. Three compounding issues:
1. **No per-request timeout on Document AI**: `processor.py:_call_document_ai()` calls `self.client.process_document(request=request)` with no timeout. gRPC call blocks the gevent greenlet indefinitely.
2. **Gevent + blocking IO**: synchronous gRPC call doesn't yield to gevent hub. SIGTERM (soft timeout) can't interrupt a blocked syscall — greenlet never processes it. At 60min, SIGKILL fires and greenlet dies with no error logged.
3. **Memory pressure**: 6 concurrent large PDFs × ~50MB each = 300MB+ raw content, on 10-greenlet heavy worker with no explicit memory limit. OOM kills silently.
Evidence: 6 tasks dispatched at 08:10-08:12, logged `ocr_library_document_started`, then zero output for 30+ min. No error, no completion, no retry. Indian Contract Act (~200 pages) should finish in <10 min but didn't.
**Root cause**: India Code PDFs are digitally generated with embedded text — they don't need OCR at all. pypdf extracts 880 pages in 39 seconds for $0, vs Document AI at ~59 minutes for ~$8.80 (guaranteed timeout kill).
**Fix (2026-05-14)**: 4-part change in `library_tasks.py` + `maintenance_tasks.py`:
1. **pypdf-first extraction**: `ocr_and_process_library_document` tries `pypdf.extract_text()` first (free, fast). Falls back to Document AI only if avg chars/page < 100 (scanned PDFs). Tested: Constitution (256pg/10s), Income Tax Act (880pg/39s), Arbitration Act (60pg/1s).
2. **Inline chunking**: Chunking called directly instead of via Celery chain. The chain serialized 1-3MB text through Redis — hit Upstash's 100MB per-key limit (GAP-20). Inline chunking keeps text in memory.
3. **Idempotency guard**: If `library_chunks` already exist, skip OCR entirely, dispatch `embed_library_chunks` directly. Prevents the duplicate-OCR storm observed during initial deploy.
4. **Smart recovery sweep**: Checks chunk count before dispatching. Chunks exist → `embed_library_chunks` only. No chunks → full `ocr_and_process_library_document`.
Also removed `process_library_document` task (dead code, parallel path) and updated `library_service.trigger_processing` to use `ocr_and_process_library_document`.
**Hostile review findings (accepted risks)**: (a) `autoretry_for=(ConnectionError,)` broken when chunking called inline — parent task retries whole flow, wasteful but functional. (b) No pypdf text quality check beyond char count — garbage Unicode from bad font encoding could slip through. (c) pdf_bytes held in memory during chunking (~15MB peak per large doc). (d) Duplicate embed dispatches from idempotency guard + normal flow — embed is idempotent, wastes API cost but no corruption.
Related: GAP-17, GAP-18, GAP-20.

**GAP-20 (P1): Upstash Redis 100MB per-key record limit breaks Celery chains with large payloads** | Status: FIXED (2026-05-14)
Discovered when `ocr_and_process_library_document` dispatched `chunk_library_document.s(id, extracted_text)` via Celery chain. The extracted text for large Acts (Companies Act=1.28MB, Income Tax Act=3MB) was serialized into Redis as a task argument. When duplicate OCR tasks accumulated (from the recovery sweep storm), the `default` queue key exceeded Upstash's 100MB single-record limit: `OperationalError: max single record size exceeded. Key: 'default', Limit: 104857600 bytes, Usage: 104878741 bytes`. All chunking tasks silently failed — OCR succeeded but chunks were never created. **Fix**: inline chunking (call `chunk_library_document()` directly, keep text in memory) and dispatch only `embed_library_chunks` via Celery (small message — just the UUID). Also removed `process_library_document` task which had the same vulnerability. Related: GAP-19.

##### Architecture Recommendations (from audit)

1. **Keep separate tables** — `library_chunks` vs `chunks` RLS models and column sets are genuinely different. But enforce schema contract: any change to `chunks` must be evaluated for `library_chunks`.
2. **Explicit dispatch, not reconciler** — Every entry path dispatches OCR synchronously. Maintenance sweep stays as safety net, not primary dispatcher. Reconciler deferred until beat isolation is stable.
3. **Completion verification** — Never set status=completed without checking chunk count > 0 AND embedding count > 0.
4. **Fix order**: GAP-1 (5 lines) → GAP-2 (10 lines) → GAP-3 (investigate) → GAP-5 (data fix). GAP-4, GAP-7, GAP-8, GAP-11, GAP-12 all FIXED (2026-05-06).

---

#### Static×Live Cross-Validation Audit (2026-06-01) — AST graph × live DB, 3 new findings + 3 live corroborations

> Method: two-lens sweep — static structure (`ldip-arch-map/GRAPH_REPORT.md`, 11k nodes, 36% inferred edges treated as hypotheses) cross-validated against **live prod DB** (Supabase MCP) and **Redis** (Upstash MCP). DB was quiescent at audit time (0 stuck docs, 0 active jobs, 0 orphan rows, 0 orphan locks), so this surfaces *latent/structural* and *masked-by-status* faults, not load-time races. **Every finding is [verified-in-code/DB]; none rests on an inferred-only edge.** Scope did NOT cover: logic/correctness quality, security/RLS, performance/scale, frontend runtime behavior, RAG retrieval quality — those need separate audits.

**GAP-21 (P1): Library doc marked `completed` with PARTIAL embeddings — completion guard only catches all-or-nothing** | Status: **FIXED (2026-06-03, pending `ldip-worker` deploy)** — chosen via blast-radius-research + choose-solution (L2) + architecture-guard (clean, reduces ARCH-003)
- **Both lenses.** `embed_library_chunks` ([library_tasks.py:471-492](backend/app/workers/tasks/library_tasks.py#L471)) blocks completion only when `embedded_count == 0` (ALL batches failed). A **partial** failure (some batches embed, some don't) still sets `status=COMPLETED`, leaving NULL-embedding chunks behind. The re-embed query at [library_tasks.py:325](backend/app/workers/tasks/library_tasks.py#L325) (`.is_("embedding","null")`) *would* fix it on re-run — but `resume_stuck_pipelines` keys off `status`, and `status='completed'` is now invisible to recovery. **Classic ARCH-003: completion-by-convention masks the doc from the reconciler.**
- **Live evidence (2026-06-01):** `library_documents` "Income Tax Act 1961" = `completed`, 2422 chunks, **1422 (59%) with `embedding IS NULL`**. (id `9f60ba8b-…`, embedded 2026-05-14.)
- **Severity correction (2026-06-03):** NOT "silently unsearchable" — all 1422 NULL chunks **have `fts` populated**, and library retrieval is hybrid (vector + `bm25_search_library_chunks`). They are **excluded from semantic/vector recall but reachable by BM25 keyword match**. Real degradation (conceptual queries miss 59% of the statute), not total invisibility.
- **Actual root cause (2026-06-03):** exactly **1000/2422 embedded** = the PostgREST ~1000-row default-response cap. The NULL-chunks fetch ([library_tasks.py:325](backend/app/workers/tasks/library_tasks.py#L325)) had no `.range()`/`.limit()`, so it silently saw only the first 1000 chunks, embedded them, and the old guard marked COMPLETED. Not batch failures.
- **Fix (Option 1 / L2 — derived state, not a count invariant):** (1) **paginate** the NULL-chunks fetch with `.range()` so one run sees all unembedded chunks (kills the truncation root cause); (2) **guard re-queries the true remaining-NULL count** (`count="exact"`, accurate beyond 1000) and only marks COMPLETED when zero remain — partial → leaves `processing`, no-progress → `failed` (anti-thrash convergence backstop); (3) **`resume_stuck_pipelines` library recovery is now a derived-state reconciler** ([maintenance_tasks.py](backend/app/workers/tasks/maintenance_tasks.py)) — finds any non-`failed` library doc with `library_chunks WHERE embedding IS NULL` regardless of status and re-dispatches embed-only, healing the already-`completed` Income Tax Act and backstopping any future partial. Converges via the embed task's COMPLETED/FAILED terminal states (no E2E-007-style infinite loop). **Income Tax Act heals automatically on the first beat sweep after deploy.** Related: GAP-2, GAP-3, HR-A2, ARCH-003.
- **Hostile review (2026-06-03):** convergence verified in all 3 cases (transient→FAILED in 1 sweep, permanent-bad-chunk→FAILED in 2, healthy doc never re-dispatched). Fixed BUG-1 (dead `if embeddings is None` guard — `embed_batch` returns all-`None` lists, never `None`; corrected to `all(e is None ...)` so the failed-batch warning fires). **Reverted an over-reach**: an early draft skipped `fire_library_callbacks` on `partial`, which would have permanently dropped citation verification (`trigger_verification_on_act_upload`) for reconciler-healed Acts (callbacks are transient chain state, not persisted — can't be re-fired). Reverted to preserve prior verification behavior.
- **Follow-up risks — RISK-3 & RISK-2 FIXED (2026-06-03), RISK-1 OPEN (next pass):**
  - **RISK-3 (FIXED, 2026-06-03):** transient OpenAI throttle on the first batch no longer FAILs the doc. `embed_library_chunks` ([library_tasks.py](backend/app/workers/tasks/library_tasks.py)) now distinguishes a transient throttle (a batch with non-empty inputs returning all-`None` — circuit-open/rate-limit, since the all-empty path is impossible when inputs are non-empty) from genuine-empty content, **without changing `embed_batch`'s shared contract**. On a zero-progress run: transient → bounded `self.retry()` (Celery's native `max_retries=3`, worker freed between attempts) → on exhaustion FAILED with distinct flag `embedding_throttle_exhausted`; genuine-empty → FAILED `embedding_failed` immediately. FAILED stays reachable (E2E-007-safe); the maintenance reconciler is the outer safety net.
  - **RISK-2 (FIXED, 2026-06-03):** `embed_library_chunks` now takes `PipelineLock(library_document_id)` (the existing main-pipeline primitive, reused) at the single convergence point both dispatch sources flow through, released in one `finally`. Concurrent chain-embed + reconciler-embed for the same doc → the second returns `skipped_locked` (no duplicate OpenAI calls / `llm_costs` rows). Also tightened `fire_library_callbacks` to fire only on `embedding_complete` (so a `skipped_locked`/`partial` result can no longer trigger verification on incomplete embeddings).
  - **RISK-1 (FIXED, 2026-06-04, commit `0581482`):** verification is now **derived from persisted state**. `sync_citation_statuses_with_resolutions` (existing 15-min beat reconciler) selects auto_fetched/available resolutions whose Act doc is fully embedded (status=completed + ≥1 chunk + 0 NULL embeddings — the GAP-21 gate) and that still have non-terminal citations, and fires the SAME convergence task the upload callback uses (`trigger_verification_on_act_upload`). The transient callback is demoted to a fast path; the reconciler is the authority (GAP-18/GAP-21 pattern). Convergence: `get_citations_for_act(exclude_verified=True)` now excludes the FULL terminal set `{verified, mismatch, section_not_found}` (was only verified+mismatch), so once every citation is terminal the verify task is a 0-Gemini no-op and the reconciler stops selecting the Act. Budget bucket GEMINI_FLASH, existing rate limiter, no new queue/worker. **Live-verified 2026-06-04**: Income Tax Act healed by GAP-21 → reconciler auto-fired its verification with no manual trigger. (Surfaced GAP-23, below, which was the real persistence blocker.)

**GAP-23 (P1): `citations.verification_status` enum/constraint drift — `section_not_found` writes silently rejected for months** | Status: **FIXED (2026-06-04, commit `48f2440`, migration `20260604000001` live)**
- **Root cause.** The `citations_verification_status_check` CHECK constraint allowed legacy `'not_found'`, but the app enum `VerificationStatus` ([app/models/citation.py:32](backend/app/models/citation.py#L32)) emits `'section_not_found'`. They diverged (edited in different PRs; nothing re-checked parity). Every section-not-found verification write was rejected by Postgres (**SQLSTATE 23514**) and lost. This is why the live table only ever held `pending`/`verified`/`act_unavailable`, and why citations that resolve to "section not found" sat in `pending` indefinitely — a large fraction of the long-standing "stranded pending citations" symptom was THIS, not just missing dispatch.
- **Why invisible for months.** `_verify_citations_batch_async` ([verification_tasks.py:117](backend/app/workers/tasks/verification_tasks.py#L117)) discarded the return of `update_citation_verification` and counted the verification VERDICT (`result.status`), not the DB-write outcome — so it logged `not_found=N, errors=0` and `verification_task_complete` while persisting **zero** rows. `update_citation_verification` swallows its own exception and returns `None` ([storage.py:1055](backend/app/engines/citation/storage.py#L1055)). Classic GAP-11 silent-success shape, recurred. NOT RLS (service_role has `BYPASSRLS=true`; the worker writes other RLS tables fine — confirmed empirically before the constraint was found).
- **Found by.** RISK-1 post-deploy verification: logs said "18 verifications dispatched, tasks complete" but a live-DB read showed `updated_since_deploy=0`. The contradiction (logs vs DB) forced reading `update_citation_verification_failed` in worker logs, which carried the 23514 error.
- **Fix.** (1) Migration aligns the constraint to the enum `{pending,verified,mismatch,section_not_found,act_unavailable}` — safe widening, 0 rows used `not_found`. Live-verified: `section_not_found` 0→781, `pending` 1315→534 within the first sweeps. (2) **Guard**: hardened the batch loop so a `None` return (exception or 0-row match) counts as an error and leaves the citation non-terminal — silent write-loss of this class can't hide again. Skills updated: `blast-radius-research` §2.6 (enum/constraint parity), `hostile-review` §M (counter honesty / activation blast radius) + DB-first post-deploy gate, CLAUDE.md Verify-Before-Acting. Related: GAP-11 (silent-swallow), ARCH-003.

**GAP-25 (P3, RESOLVED — legacy test data): false `section_not_found` flood from one body-incomplete Act doc + a backronym test alias** | Status: FIXED (2026-06-04, commit `86e78a5` + data fix)
- **Surfaced by** GAP-23 (once `section_not_found` could persist, ~781 appeared; ~636/867 against ONE doc). **Investigation outcome: legacy TEST data, not a live product bug.**
- **Doc.** `library_documents.id=a65f4b17-…` = real IndiaCode fetch of *Special Court (Trial of Offences Relating to Transactions in Securities) Act, 1992*, but `quality_flags=['chunking_failed']`, **3 chunks of a 9-page act**, wrongly left `status='completed'` by the **pre-hardening March chunker (GAP-19 era)**. Current code marks chunking_failed docs `FAILED`+raises, so this state is no longer producible — a legacy anomaly.
- **Name mapping.** `"TORTS Act 1992"→`Securities Act is a **deliberate backronym alias** in [abbreviations.py:251-263](backend/app/engines/citation/abbreviations.py#L251) ("TORTS = **T**rial **o**f offences **R**elating to **T**ransactions in **S**ecurities") — test scaffolding. No codified Indian Torts Act exists → zero real-data reach. Left in place.
- **Blast radius.** 867/1112 `section_not_found` from this one doc; 92% in test/demo matters ("Nirav Jobalia" + "TORTS Act 1992"/"trial" matters). a65f4b17 is the only chunking-impaired doc producing false negatives.
- **Fix.** (A) Data: marked a65f4b17's 5 `auto_fetched` resolutions `invalid` (removes it from the RISK-1 reconciler's `available_resolutions` set → churn-safe) + relabeled its 867 `section_not_found`→`act_unavailable`. **Churn trap caught by hostile-review §M2:** `act_unavailable` is NON-terminal in `sync_citation_statuses_with_resolutions` (`_NON_TERMINAL=["act_unavailable","pending"]`), and a65f4b17 passed `_act_doc_fully_embedded` (that gate checks embeddings, not chunk-completeness) — relabel WITHOUT invalidating the resolutions would have caused an infinite pending↔act_unavailable loop. (B) Guard: [act_indexer.py](backend/app/engines/citation/act_indexer.py) `index_act_document` refuses to index a doc whose `library_documents.quality_flags` ∈ `ACT_BODY_INCOMPLETE_FLAGS` (chunking_failed/zero_chunks/ocr_empty_text/ocr_failed/storage_missing/chain_error), raising `ActIndexerError` → verify_citation's existing `ACT_UNAVAILABLE` path (no verifier change). Defense-in-depth. Did NOT touch the RISK-1 reconciler, verifier verdict logic, or the constraint.
- **Residual.** Re-processing a TORTS *test* doc could recreate a `missing` resolution → auto-fetch → re-link a65f4b17 → restart churn. Confined to known test matters.

**GAP-24 (P1): citation verification ~100% false-negative against REAL IndiaCode Acts — section CONTENT-LOAD read the wrong chunk table** | Status: **FIXED (2026-06-04, commit `1e2d9ee`, both services deployed + live-verified)**
- **Observation (verified-in-DB 2026-06-04).** Every fully-chunked real Act had **0 verified / 100% `section_not_found`**: Constitution `0/125` (622 ch), Companies 2013 `0/175` (879 ch), Arbitration `0/28` (129 ch), Contract `0/12` (134 ch), Income Tax `0/7` (2422 ch), Environment `0/2` (19 ch). **Constitution Article 21 cited 50× and "not found" every time** → FALSE negatives. Visible only after GAP-23 made `section_not_found` writable.
- **Phase-1 corrected the original hypotheses.** The 4-chunk "TORTS" fixture's **771 verified were STALE** (all written `2026-02-27 05:13`, when that content still lived in `chunks`); run today it fails too. There was **no working control** — retrieval was 100% broken for *every* library Act. Of the prompt's three theories: (#1 wrong-table) TRUE but only the *secondary* path; (#2 20-chunk cap) moot — the table is wrong before the cap matters; (#3 regex format) mostly FALSE — the Constitution's arrangement lines `21. …` *do* match pattern #2, so section "21" **was** indexed.
- **Actual single root cause.** The index is correctly built over `library_chunks` (the `library_chunks` fallback at [act_indexer.py:244-256](backend/app/engines/citation/act_indexer.py#L244) already existed), but the two **content-load** steps then re-fetched by id from the **`chunks`-only** `get_chunk` ([act_indexer.py get_section_chunks](backend/app/engines/citation/act_indexer.py)) and `get_chunks_for_document` ([verifier.py fallback](backend/app/engines/citation/verifier.py)). Library-chunk ids aren't in `chunks` → `ChunkNotFoundError` swallowed → `[]` → `None` → `section_not_found`. **The table decision was being re-derived at each load site instead of once at index-build.** Canonical "parallel tables — improvement to A not remembered for B" shape (1.5E / GAP-21 sibling).
- **Fix (L2 — kills the shape).** `ActIndex` now retains the `ChunkWithContent` it already loaded at index time (`chunks_by_id`); `get_section_chunks` and the verifier's LLM fallback (via new `get_indexed_chunks`) serve from that map — one table decision, made once where the `library_chunks` fallback lives. No new parallel/semantic path (semantic search rejected: matter-scoped, can't target a section, ARCH-001). No new Gemini calls — fallback now fires less. Also normalized `39-A`→`39A` in `_normalize_section` (both index+lookup) so Constitution Art 39A (cited `39-A` ×15) matches text form `39A`.
- **Live result (re-ran 395 reset `section_not_found`→`pending` via the RISK-1 reconciler).** Constitution **Art 21: 48 verified** (was 0/50), 39-A: 15 ✅, 19/12/14/136/142/39A all ✅; Arbitration/Contract/IT/Environment real sections ✅. The core product value is restored. (Tail of ~136 drains on subsequent reconciler ticks.)
- **Honest caveat → see GAP-26.** Companies "205-family" (`205A`/`205`/`205(C)`/`206A`) also flipped to verified — **likely FALSE positives** via the *pre-existing* partial-match leniency + upstream act mis-resolution, NOT this retrieval fix.

**GAP-26 (P2): citation verifier marks mis-resolved Companies-1956 sections `verified` against the 2013 Act** | Status: **L2 FIXED (2026-06-10, pending `ldip-worker`+`LDIP` deploy + post-deploy data-fix)** — chosen via blast-radius-research (Phase-1 live data rewrote the root cause) + choose-solution (L2) + architecture-guard (clean, no forbidden pattern)
- **Live data rewrote the root cause (2026-06-10).** **213/226 (94%)** of `verified`-vs-Companies-2013 citations are provably false (their own `raw_citation_text`/`act_name_original` name a 1956 provision: `205A`/`205(C)`/`206A` or the year `1956`/"Indian Companies Act"). **Three compounding mechanisms**, not the two originally guessed: (1) **fuzzy section match** — `get_section_chunks` fallback let `205A` match a bare `205` key [174 rows]; (2) **section-only = auto-100%-`verified`** with no text compared — ALL 226 Companies + **1,157 system-wide** verified rows have `quoted_text IS NULL` (`verifier.py:259-263`); (3) **vintage-blind binding** — 0 Companies-1956 docs exist, yet 1956 citations bind to the only-present 2013 doc. They compound: wrong doc → same-number section → 100% with no text read.
- **L2 shipped (this fix).** (1) **`act_indexer._section_core`** replaces the `startswith` fallback with section-IDENTITY matching: an alpha suffix (`205A`) or alpha paren-clause (`205(C)`→`205C`) is a DISTINCT section and must match exactly; a NUMERIC subsection (`205(1)`→`205`, `138(2)`→`138`) still drills down. Kills the 174-row fuzzy class; **GAP-24's exact wins are untouched** (Constitution Art 21=48, 39A=21 are exact, not suffix-fuzzy — unit-verified). (2) **Churn-safe data fix** `backend/fix_gap26_reverify_companies.py` (dry-run=165 rows) resets the wrong Companies-2013 verifies to `pending` so the RISK-1 reconciler re-derives them through the fixed indexer → `205A`→`section_not_found` (terminal, in the `get_citations_for_act` exclude set `storage.py:1165` → 0-Gemini no-op, **no GAP-25 churn loop**). **Ordering: deploy worker FIRST, then `--apply`.** (3) **Watchman** `verified_citation_vintage_mismatch` in `system_invariants.py` (INF-012 catalog) — flags any `verified` citation whose ORIGINAL claim (`act_name_original`+`raw_citation_text`, NOT the post-resolution `act_name`) names a year ≠ the target doc's year. Live baseline = **40** (general: also caught an Arbitration `1940`→`1996` mismatch). Conservative (explicit-year-only, no cry-wolf).
- **L3 deliberately DEFERRED (vintage-safe resolver binding).** Mechanism (3) — a bare-section 1956 citation re-verifying against 2013's real §205 — is the residual L2 cannot structurally prevent; it stays flagged by the watchman. **The watchman IS the L3 trigger** (do L3 when its count grows / leaves demo matters / a real 1956 doc is loaded) AND L3's spec (the logged examples) AND L3's final exam (count→0 when L3 ships). L3 touches the resolver → needs architecture-guard. See choose-solution L2→L3 plan.
- **Deployed + live-verified (2026-06-10, both services).** Final production state for the 2013 Companies doc (`4f2a53e4`): **205A-family 144 → `section_not_found`** (the fuzzy-match class killed in prod), **provably-wrong-verified 213 → 59** (72% cut), **0 stranded pending**, watchman **40 → 32**. GAP-24 wins intact (Art 21=48, 39A=21, Arbitration §2=27). The 59 residual = bare-section vintage/extraction-collapsed rows (stored `section="205"` is a *valid* 2013 section) = the deferred-L3 class; watchman flags the explicit-year subset (32).
- **Data-fix gotcha found + fixed the hard way (2026-06-10).** The first `fix_gap26_reverify_companies.py` reset wrong rows to `pending` assuming the RISK-1 reconciler would re-derive them — **WRONG for these rows.** They are bound to a LIBRARY Act via `citations.target_act_document_id`, but the matter's `act_resolution` for the same Act has `act_document_id=NULL` (status `missing`/`not_on_indiacode`). `sync_citation_statuses_with_resolutions` only selects resolutions WHERE `act_document_id IS NOT NULL`, so it never re-derived them → 165 stranded in `pending`. **Remedy:** re-triggered `verify_citations_for_act` per (matter, act_name, doc) tuple directly (drives 205A→`section_not_found`). Script corrected to reset+re-trigger (not lean on the reconciler). **Architectural note (latent):** the RISK-1 reconciler has a *library-binding coverage gap* — it cannot reconcile citations bound to a library Act when the resolution row's `act_document_id` is NULL. Candidate follow-up (reconcile by `citations.target_act_document_id`, not only via resolutions).
- **Verified.** Unit: `_section_core` 9/9 + match table (`205A`↛`205`, `205(C)`↛`205`, `39A`→`39A`, `21(1)`→`21`, `138`→`138(1)`). Live: 205A-family→section_not_found in prod; GAP-24 unchanged; watchman=32. hostile-review caught two real bugs pre-deploy/in-flight: (1) field-boundary — watchman first read `act_name` (post-resolution, carried the wrong year and masked the mismatch → 0 violations) → fixed to `act_name_original`+`raw_citation_text` (→ 40); (2) the reconciler-vs-library-binding stranding above.

**WATCH (infra, not a bug yet): RISK-1 beat reconciler tick occasionally starved when schedules align** — `sync_citation_statuses_with_resolutions` was *sent* by beat at 05:36:04 (a 30-min boundary where ~12 maintenance tasks co-fire) but produced no completion/dispatch; the 05:06 and 05:51 ticks ran clean. Self-healing (next tick recovers; ≤15-min delay, no data loss). **Leading hypothesis only (thundering-herd starvation), not root-caused.** If it recurs: confirm cause, then L1 = stagger the beat schedules off the 30-min boundary (small/low-risk). Skip dedicated-worker isolation unless chronic. See celery.py `beat_schedule`.

**GAP-27 (P3): two divergent section indexes + the verification index is ephemeral (un-auditable)** | Status: **L1 SHIPPED (2026-06-10, audit tool); L2/L3 DEFERRED** — surfaced while auditing GAP-26's 144 `section_not_found`
- **The shape (GAP-8 / ARCH-PATTERNS P5 — hand-mirrored representations).** The same logical data (section_number → location in an Act) is built TWICE by different code from different sources that DIVERGE:
  - **`section_index` TABLE** — written by `index_act_sections` task → `SectionIndexService` ([section_index_service.py](backend/app/services/section_index_service.py)) from **`bounding_boxes`**, keyed to **`documents.id` (matter docs only)**, read **only** by the split-view UI route ([citations.py](backend/app/api/routes/citations.py) `GET /citations/{id}/split-view`). Its `_normalize_section` does **NOT** collapse `39-A`→`39A`. Live: 446 rows, 2 matter docs, **0 library Acts** (FK can't reference `library_documents`).
  - **in-memory `ActIndex`** — built by `ActIndexer.index_act_document` from **`chunks`/`library_chunks`**, for ANY Act, used by the **verifier**, **does** collapse `39-A`→`39A` (GAP-24). Cached per-worker-process (`@lru_cache` singleton), **ephemeral** (lost on restart, not shared across workers, never persisted).
- **Two real problems, ranked.** (1) **Auditability** [the felt pain] — the verification index can't be opened, so "what sections does the verifier think this Act has?" was unanswerable when auditing GAP-26. (2) **Divergence** [latent, low-severity] — the table vs ActIndex disagree (e.g. `39-A`), so split-view can show a wrong/missing page for such sections. (3) **Cold-start rebuild** [weak] — per-worker per-Act on restart/autoscale; cached otherwise, so NOT per-query.
- **L1 SHIPPED (2026-06-10): read-only audit tool** `backend/audit_act_index.py` — rebuilds the verifier's exact index on demand and prints the sections + checks one section. **Closed the GAP-26 caveat live:** 2013 Companies Act index has §205 but **NO §205A** (→ the 144 `section_not_found` are provably correct); Constitution §21 PRESENT (10 chunks). Zero regression (read-only, reuses the build path).
- **L2 DEFERRED (persist the verifier's index)** — give `ActIndex` a persistent store keyed by `library_document_id`/`document_id`, written by the SAME extraction code (must keep the GAP-24 `39-A` normalization), verifier read-through + in-memory fallback. Buys warm restarts + persistent auditability. **Rejected for now:** justified mainly by performance (weak at 19 Acts/modest traffic) and would add a THIRD representation unless it also subsumes the table. **Trigger:** worker cold-start rebuild measurably hurts (many autoscaled workers / frequent deploys / much larger Acts).
- **L3 DEFERRED (unify the two indexes)** — one builder, one persistent store, BOTH the verifier and split-view read it; retire `SectionIndexService`'s separate bbox-based builder. Kills the GAP-8 divergence for section indexes. **Rejected for now:** rewrites a working UI feature + the bbox/page path (the verification index has no `bbox_id`) for a latent, low-severity, unreported navigation bug; grandiose at N=19. **Trigger:** a *reported* split-view wrong-page bug from the `39-A`-style divergence, OR ingesting a large corpus (case law) where one store must serve both. **Note:** persisting this index does NOT help the GAP-26 vintage fix (L3 resolver) — they are independent (an earlier claim to the contrary was wrong).
- **Related:** GAP-8 (chunks vs library_chunks schema divergence — same parallel-tables shape), GAP-24 (the `39-A` normalization that the table lacks), ARCH-001.

**GAP-28 (P1): citation EXTRACTION corrupts section + act_name (the master root under GAP-26)** | Status: **L2 FIXED + DEPLOYED + E2E-VERIFIED + BACKFILLED (2026-06-10)** — found by a live E2E upload; blast-radius + choose-solution (L2) + architecture-guard (clean) + hostile-review (clean)
- **Root cause.** `extractor.py` `CITATION_PATTERNS` captured the section as **digits-only** (`\d+(...(\d+))?(...([a-z]))?`), so `"Section 205A of the Companies Act, 1956"` → `section="205"` (the `A` dropped) + `act_name="A of the Companies Act"` (the stray `A` bled into the act name). The post-parse re-truncated to `\d+`. Uppercase paren-clauses (`205(C)`) were also dropped. **Deterministic** on the regex path; the parallel Gemini path (correct prompt) made it LOOK non-deterministic via the merge (ARCH-001 shape — same raw text stored under 2 act_names).
- **Why it's the master root.** It is upstream of verification, so it **defeats the GAP-26 verifier fix**: a `205(C)`/`205A` citation stored as bare `205` (a real 2013 section) verifies `verified` against the 2013 Act. **Live E2E (2026-06-10) reproduced a fresh false-positive** (`"Section 205(C)…"` → `verified`) that BOTH the GAP-26 fix and the year-watchman missed. Live prevalence: **125** section-corruptions + **146** verified-with-corrupted-section + ~150 fragment act_names.
- **L2 fix (shipped, code).** (1) `CITATION_PATTERNS` now capture the full section token via `_SECTION_TOKEN` (`\d+[A-Za-z]?(\([A-Za-z0-9]+\))*`) — the alpha suffix can no longer bleed into act_name. (2) `canonicalize_section()` splits a token into identity/subsection/clause with the rule **uppercase folds into the section** (`205(C)`→`205C`, distinct lettered section) **but numeric/lowercase split off** (`138(1)`→sub, `138(a)`→clause) — aligned with `ActIndexer._section_core`, so `205(C)` no longer collapses to `205`. (3) **Fail-open repair chokepoint** `repair_citation_in_place()` at `storage.save_citations` — both engines converge there; it re-derives the section from `raw_citation_text` and strips `"<letter> of the"` act-name fragments. Any error leaves the citation as-extracted (no drop, no pipeline block). (4) **Watchman** `verified_section_token_mismatch` (system_invariants) flags `verified` citations whose stored section ≠ their raw-text section — the complement of the year-watchman; live baseline **146**. Does NOT flag `Article` citations (no GAP-24 regression).
- **Verified end-to-end on production (2026-06-10).** **Fresh Playwright E2E** re-uploaded the exact doc that caused the capstone false-positive → all 14 Companies citations stored faithfully (`205A`, `205C`, `205A(8)`→`205A`+sub) with clean act_name `"Companies Act"`, and **14/14 `section_not_found`** (was: false `verified`). **Backfill** `backfill_gap28_repair_sections.py --apply` repaired 136 old rows + re-verified 67 → the GAP-26 matter's 205-family is now **184 `section_not_found`** / 2 verified. **Watchman** `verified_section_token_mismatch` driven 146→76 (identity fix)→9 (all-tokens fix)→**2 genuine** (test-matter extraction oddities); GAP-24 wins intact (Art 21 = 48). hostile-review clean (no greedy-suffix regression; pydantic mutable; consumer parity holds). **Deferred L3** (regex = span-detection only, LLM owns structure) if the repair ever has to fix a high rate of regex output. Under-extraction (8 vs 149) is a SEPARATE open item (Gemini `max_output_tokens=8192` truncation, no retry). See `docs/PROD-FINDINGS-2026-06-10.md`.

**GAP-22 (P2): Voyage dual-embedding is a dead parallel retrieval path — `embedding_voyage` ~empty system-wide, but twin RPCs + provider switch remain (GAP-4 regression)** | Status: OPEN
- **Both lenses.** `embedding_voyage` is **NULL on 100% of `library_chunks` (5178/5178)** and **99% of `chunks` (3386/3424)** [verified-in-DB 2026-06-01]. The library Voyage writer is best-effort and swallowed in try/except ([library_tasks.py:424-454](backend/app/workers/tasks/library_tasks.py#L424)). Yet retrieval keeps **twin RPCs** (`match_library_chunks_for_matter` vs `…_voyage`) gated on `embedding_provider` ([hybrid_search.py:1217/1339/1632](backend/app/services/rag/hybrid_search.py#L1217)) plus a whole subsystem (`voyage_embedding_tasks.py`, `embedding_migration.py`). **Flipping `embedding_provider="voyage"` → near-empty retrieval with no error.** Latent config-bomb + ARCH-001 (parallel duplicate path) + ARCH-005 (RPC/schema divergence).
- **GAP-4** ("Voyage embeddings never populated") was marked FIXED (2026-05-06) — this is a **regression / never-actually-populated**; GAP-4 should be reopened or superseded by GAP-22.

**FE-023 (P3): Real import cycle `tabStats.ts ↔ workspaceStore.ts`** | Status: FIXED (2026-06-01)
- **Lens A** ([GRAPH_REPORT.md:801]). The other 3 two-file cycles are benign barrel re-exports (`page → index.ts → page`); this one is a genuine API-layer↔store circular dependency (`frontend/src/lib/api/tabStats.ts` ↔ `frontend/src/stores/workspaceStore.ts`). Works today via hoisting; a load-order/refactor change can surface `undefined`-at-import. Related: FE-ARCH cluster.
- **Fix (2026-06-01)**: Extracted the three shared tab types (`TabId`, `TabStats`, `TabProcessingStatus`) into a dependency-free leaf module `frontend/src/stores/workspaceStore.types.ts`; `tabStats.ts` now imports them from there (severing the back-edge) and `workspaceStore.ts` re-exports them so `@/stores/workspaceStore` consumers are unchanged. **Root-cause fix, not a suppression.** Also enabled `import/no-cycle` (`error`) in `frontend/eslint.config.mjs` so any new cycle fails lint — turning this one-time graph finding into a continuous structural guard (wall, not sticky-note). Doing so surfaced a **second, previously-"benign"-labelled cycle**: `summary/SummaryContent.tsx` imported its siblings through its own barrel (`./index`), which re-exports `SummaryContent`; fixed by importing the 6 siblings directly. Verified: `tsc --noEmit` clean, `import/no-cycle` reports **0 cycles** across `src` (was 2).

**FE-024 (P3): `npm run lint` is not green — 2 errors + 52 warnings, pre-existing** | Status: FIXED (2026-06-03) — `eslint src` is fully green: **0 errors, 0 warnings** (tsc `--noEmit` also clean)
- Surfaced 2026-06-01 while wiring the FE-023 `no-cycle` guard (full `eslint src` run). **Independent of that work** — these predate it. Recorded because if/when lint is made a blocking CI gate, the **2 errors** will fail the build.
- **2 errors** (`react-hooks/set-state-in-effect` — synchronous `setState` in an effect body → cascading re-renders, React 19): `frontend/src/components/features/entities/EntitiesContent.tsx:83` and `frontend/src/components/features/pdf/PdfViewerModal.tsx:73`.
- **52 warnings**: 43 × `@typescript-eslint/no-unused-vars`, 5 × `react-hooks/exhaustive-deps` (can hide stale-closure bugs — worth a look, not just noise), 3 × stale `eslint-disable` directives (now no-ops, e.g. `OnboardingWizard.tsx:156`), 1 × `jsx-a11y/role-supports-aria-props`. 3 are `--fix`-able automatically.
- **Fix (2026-06-03) — chosen via the `choose-solution` skill (L2, not local-patch, not full-rewrite):** A blast-radius sweep showed the 2 errors are instances of two recurring *shapes*, not 2 isolated bugs:
  - **Transient-flag shape** (`setX(true); setTimeout(() => setX(false), N)`) — 5+ copy-pasted sites, one of which (`EntitiesContent.tsx:236`, focus pulse in a handler) **leaked its timer**. Extracted a single reusable hook `frontend/src/hooks/useTransientValue.ts` (owns timer cleanup) and applied it to `ContactSupport`, `ProfileSection`, `FailedJobCard`, and both `EntitiesContent` focus pulses. Kills the leak class + dedups. Deep-link initial focus preserved via the hook's `initialValue` param (no behavior change).
  - **Sync-state-from-input shape** (the rule's target) — the codebase already has a convention: suppress-with-justification when the sync is genuine (~10 sites: `useWebSocket`, `useCrossTabNavigation`, `countdown-timer`, etc.). The 2 errors were the 2 that *missed* it. Brought them in line with a justified `eslint-disable` (consistency over forking the convention for 2 sites). The `set-state-in-effect` rule (error) remains the guard for new sites.
  - **Deliberately NOT done (L3):** converting the ~10 working suppressed sites to a `usePrevious`/`useSyncedState` primitive — rejected as premature for N=1 UI scale and high regression surface. Revisit if the suppressed population keeps growing.
  - Verified: `tsc --noEmit` clean; 0 `set-state-in-effect` errors on the changed files.
- **Warnings cleared (2026-06-03) — the 52 warnings split into two shapes, treated differently:**
  - **Group B — 6 correctness-sensitive (triaged individually, never blind-fixed):**
    - `CitationsContent.tsx:230` — **real stale-data bug.** The "close split view if the current citation is no longer in the filtered list" effect read `filteredCitations` in its body but depended on `citations`, so changing the filter (its own comment's scenario) never re-ran it. Fix: depend on `filteredCitations` (the value actually used), not `citations`. No loop — guard short-circuits after close.
    - `MatterSettingsDialog.tsx:144` — **not benign** (the "setState setters are stable" assumption was wrong here): `setIsOpen = controlledOnOpenChange ?? setUncontrolledOpen` (line 85), so in controlled mode it's a parent-supplied prop, a genuine dep. Added `setIsOpen` to the `useCallback` deps. Safe — it's an event handler, not an effect, so a changing identity can't loop/refetch.
    - `useMatterCosts.ts:67` — justified suppression. Cleanup does `requestIdRef.current++` to invalidate in-flight requests; the rule's suggested "snapshot `.current` into a variable" fix would *break* the staleness guard. `// eslint-disable-next-line ... -- reason` (matches the ~10-site convention).
    - `useTimeline.ts:176` (×2) — perf. `data?.data ?? []` made a fresh array every render, forcing two downstream `useMemo`s to recompute each render. Wrapped `events` in its own `useMemo` keyed on `data?.data`.
    - `MatterCard.tsx:295` — `aria-selected` is invalid on `role="article"` (AT ignores it); selection is already conveyed by the `Checkbox`. Removed the attribute (changing the role would require a `listbox`/`grid` parent — out of scope, would create a new violation).
  - **Group A — 46 cosmetic, two sub-shapes:**
    - **`_`-prefix sub-shape (3): config, not deletion.** `_minSize`/`_maxSize` (resizable mock) are destructure-to-omit — deleting them would spread `minSize`/`maxSize` onto the DOM div (React prop warnings); `_parseSSELine` is explicitly annotated "kept for future SSE format changes." All three signal intent via `_`, but `eslint.config.mjs` lacked the option to honor it. Added `argsIgnorePattern`/`varsIgnorePattern`/`caughtErrorsIgnorePattern: '^_'` to `@typescript-eslint/no-unused-vars`. Can only silence *unused* `_`-prefixed names — never hides a used one. (Catch bindings and 2 zustand-`StateStorage` signature params were renamed to `_`/optional-catch to use this.)
    - **dead imports/vars (~40) + 3 stale `eslint-disable` directives:** removed per-file, each symbol grep-verified as a string across the repo first (none were dynamically referenced). 3 self-induced cascades (deleting `displayPct`/`colorClass`/`focusedIndex` orphaned a downstream const/import) were caught by scoped re-lint and cleaned up.
  - **Verified:** `tsc --noEmit` clean (exit 0); full `eslint src` → **0 errors, 0 warnings**.
  - **Deliberately NOT done:** rewriting `useMatterCosts`' hand-rolled request-ID guard as an `AbortController` (L3 rewrite of a working hook — unwarranted), and converting the ~10 suppressed `set-state-in-effect` sites to a primitive (already deferred above).

**Live corroborations of existing debts (no new ID — evidence attached here):**
- **ARCH-003 / DPP-015** (doc `completed` while terminal contradiction task FAILED): **Live — `9. Affidavit … Nirav D Jobalia … pdf`** (case_file, id `6dfbf73d-…`) marked `completed` 2026-02-17 21:07 (16 chunks, 334 entities) but its DOCUMENT_PROCESSING job FAILED 23:16 with `error_code=CONTRADICTION_FAILED`. Two contradictory truths, no reconciliation. Notable: this is the very doc cited as the contradiction-detection "aha-moment" demo (§Business Context) — its contradictions may be missing while the UI reads "done."
- **ARCH-007** (classification fire-and-forget, no recovery): **Live — `2. APPLICATION IN MA NO 10 OF 2023 … VOL-ll.pdf`** (id `967d5a0d-…`) is typed `document_type='act'` — a litigation application mislabelled as a statute/reference, liable to be excluded from contradiction detection and mis-routed in RAG. Same doc also shows the ARCH-003 two-truths (job FAILED `UNEXPECTED_ERROR`, doc `completed`).
- **GAP-11** (library cost tracking): code now passes `library_document_id` ([library_tasks.py:396](backend/app/workers/tasks/library_tasks.py#L396)), but **`llm_costs.library_document_id` is NULL on all ~50k rows and there is no `library_*` operation type** [verified-in-DB 2026-06-01]. Most likely *fixed-but-unexercised* (no library ingest since the 2026-05-25 column-add). **Verify on next library ingest before trusting cost attribution.**

---

### FE-ARCH-01: Matter Workspace Has No Convergence Point — 7 Feature Panels Each Fetch, Judge, and Fail Alone
| Field | Value |
|-------|-------|
| **Severity** | P1 (Architectural — frontend) |
| **Status** | OPEN |
| **Date Found** | 2026-05-20 |
| **Source** | Frontend audit + 4-agent code census (2026-05-20). Evidence: `FRONTEND-AUDIT-2026-05-20.md` §3. |

**Description**: Opening a matter renders the workspace shell unconditionally, then **~29 API calls fan out** from **7 feature panels** (Summary 1, Documents 1, Timeline 7, Citations 6, Contradictions 2, Entities 9, Verification 3 independent fetch hooks). Nothing decides "does this matter exist / may this user see it" *once, before* the panels render. On a 404, `matterStore.fetchMatter()` catches the error and fabricates a `{ title: 'Untitled Matter' }` placeholder — swallowing the failure so the shell renders happily while every panel independently 404s (18 console errors observed in audit). `MatterProcessingStatus` (`types/matter.ts:197`) is typed `'processing' | 'ready' | 'needs_attention'` but `'needs_attention'` is never set; there is no `'failed'` state, so a matter whose only document failed processing renders as "Ready" on the dashboard. `ApiErrorBoundary` (`components/ui/api-error-boundary.tsx`) is fully implemented but has **zero usages**.

**Why it's bad**: distributed not-found / authorization / error handling with no central authority — every panel must *remember* to handle 404/empty/auth, and they each implement their own error UI (5 explicit `*Error` components + 2 inline, inconsistent contracts). The placeholder fabrication actively hides the failure from the shell, which is why FE-003 surfaces as 18 console errors instead of a clean "matter not found" page. Same root cause across FE-003, FE-007 (wrong "Ready" badge), FE-011 (stuck spinner) — and amplifies FE-022's 503 storm because every retry re-runs 29 independent fetches.

**Target architecture**: one matter-existence/authorization gate in `matter/[matterId]/layout.tsx` (or server check + `not-found.tsx`) that resolves *once*; panels render only behind it. Add `'failed'` to `MatterProcessingStatus`. Delete the placeholder-fabrication path (let the error propagate). Wire `ApiErrorBoundary` around the panel region.

**ARCH-PATTERNS map**: P1 (every panel must remember to handle 404/empty/auth — no convergence point), P4 (`ApiErrorBoundary` built but not required), P7 (placeholder fabrication is signaling failure in a language the framework doesn't speak), P8 (7 sibling panels with inconsistent error contracts).

**Detector** (run from repo root):
```
rg -n "Untitled Matter" frontend/src/stores/matterStore.ts
rg -n "MatterProcessingStatus" frontend/src/types/matter.ts
rg -n "ApiErrorBoundary|withApiErrorBoundary" frontend/src
find frontend/src/app -name "error.tsx" -o -name "not-found.tsx" -o -name "loading.tsx"
```

**Census (2026-05-20)**: 29 independent fetch hooks · 0/29 route segments with `not-found.tsx` · 3/29 with `error.tsx` · `ApiErrorBoundary` 0 uses.

**Files**: `frontend/src/stores/matterStore.ts:276-300`, `frontend/src/types/matter.ts:197`, `frontend/src/components/ui/api-error-boundary.tsx:41-103`, `frontend/src/app/matter/[matterId]/layout.tsx`, `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx`, plus 7 feature panels under `frontend/src/components/features/{summary,document,timeline,citation,contradiction,entities,verification}/*Content.tsx`.

---

### FE-ARCH-02: No Layout/Responsive System — Responsiveness Is a Per-Component Convention
| Field | Value |
|-------|-------|
| **Severity** | P1 (Architectural — frontend) |
| **Status** | OPEN |
| **Date Found** | 2026-05-20 |
| **Source** | Frontend audit + 4-agent code census (2026-05-20). Evidence: `FRONTEND-AUDIT-2026-05-20.md` §3. |

**Description**: There is **no `useMediaQuery` / `useBreakpoint` / `useViewport` primitive** anywhere in `frontend/src` (verified: zero matches). Responsiveness is **68 files hand-adding raw Tailwind `sm:`/`md:`/`lg:` classes**, 140 total occurrences. The matter two-pane layout (`WorkspaceContentArea.tsx` + `qaPanelStore.ts`) supports four panel positions (right/bottom/float/hidden) but **none is selected by viewport** — the position is hardcoded and only the user can change it, so on mobile the "Ask jaanch" panel stays side-by-side. No `scrollbar-gutter` anywhere — causes the content re-centering observed in FE-022.

**Why it's bad**: "be responsive" is an instruction every component is trusted to follow individually. Nothing *owns* the question "what does the layout do below 768px?" — so the matter shell simply never got an answer, and no structure or test catches that it didn't. Generates the entire mobile-broken cluster (FE-001, FE-002, FE-005, FE-006) and contributes to FE-022.

**Target architecture**: a `useBreakpoint` hook + a workspace layout component that *structurally* collapses the Q&A panel to a drawer below the tablet breakpoint. "Mobile" then becomes one decision in one place, not 68. Add `scrollbar-gutter: stable` to globals.

**ARCH-PATTERNS map**: P4-shaped (the structural primitive that should exist and be mandatory simply doesn't; no exact catalog match — this is a new frontend variant of the wall-vs-sticky-note frame).

**Detector** (run from repo root):
```
rg -n "useMediaQuery|useBreakpoint|useViewport|matchMedia" frontend/src   # expect ~0
rg -l "(sm|md|lg|xl|2xl):" -g "*.tsx" frontend/src                       # 68 files
rg -ln "ResizablePanelGroup" -g "*.tsx" frontend/src                      # 4 non-collapsing splits
rg -n "scrollbar-gutter" frontend/src                                     # expect 0
```

**Census (2026-05-20)**: 0 responsive primitives · 68 files / 140 raw breakpoint usages · 4 non-collapsing split layouts · 0 `scrollbar-gutter`.

**Files**: `frontend/src/components/features/matter/WorkspaceContentArea.tsx`, `frontend/src/stores/qaPanelStore.ts`, `frontend/src/components/features/export/ExportBuilder.tsx:320`, `frontend/src/components/features/pdf/PDFSplitView.tsx:133`, `frontend/src/app/globals.css`, `frontend/tailwind.config.ts`, plus 68 files with raw breakpoint classes (regenerable via detector).

---

### FE-ARCH-03: Loading Skeletons Are a Parallel Hand-Synced Copy of the Real UI
| Field | Value |
|-------|-------|
| **Severity** | P2 (Architectural — frontend) |
| **Status** | OPEN |
| **Date Found** | 2026-05-20 |
| **Source** | Frontend audit + 4-agent code census (2026-05-20). Evidence: `FRONTEND-AUDIT-2026-05-20.md` §3. |

**Description**: `components/ui/skeleton.tsx` is a generic pulsing `<div>` accepting arbitrary `className`. Every feature skeleton (**~47 definitions**, **335 `<Skeleton>` uses**) is a separate, hand-authored component with hardcoded `h-`/`w-` dimensions that do not derive from the real component. Two implementations of the same UI, kept dimensionally in sync by hand. When a real component's layout changes, its skeleton silently drifts → content jumps when real data replaces the skeleton (contributes to FE-022's CLS 0.1138).

**Why it's bad**: same disease as ARCH-006 (hand-mirrored types across boundaries), at the skeleton↔real-component boundary. Drift is invisible — no compile error when skeleton and real component disagree about dimensions, only a visible layout shift at runtime.

**Target architecture**: a skeleton should be the *real* component rendered in a "skeleton" mode (same DOM, same dimensions, shimmer instead of content) — one source of truth, so the skeleton cannot drift. One architectural change retires all ~47 instances.

**ARCH-PATTERNS map**: P5 (hand-mirrored representations, drift invisible — the wall is codegen / derive-one-from-the-other; same shape as ARCH-006 at a different boundary), P2 (two implementations of the same logical UI).

**Detector** (run from repo root):
```
rg -n "(function|const|export)\s+\w*Skeleton" -g "*.tsx" -g "!*.test.tsx" frontend/src
rg -c "<Skeleton" -g "*.tsx" frontend/src
```

**Census (2026-05-20)**: ~47 skeleton definitions across ~42 files · 335 `<Skeleton>` uses · 0 codegen / shared skeleton-mode mechanism.

**Files**: `frontend/src/components/ui/skeleton.tsx` (primitive), `frontend/src/components/features/processing/ProcessingSkeleton.tsx` (8 hand-authored skeletons at lines 15,40,59,91,119,154,197,220), plus ~40 additional files (regenerable via detector).

---

### FE-ARCH-04: No Presentation/Format Layer — Dates, Counts, and Status Formatted Ad Hoc at Every Call Site
| Field | Value |
|-------|-------|
| **Severity** | P2 (Architectural — frontend) |
| **Status** | OPEN |
| **Date Found** | 2026-05-20 |
| **Source** | Frontend audit + 4-agent code census (2026-05-20). Evidence: `FRONTEND-AUDIT-2026-05-20.md` §3. |

**Description**: `frontend/src/lib/utils.ts` contains exactly one helper (`cn()`). There is no shared formatter. Census: **8 separate `formatDate()` implementations** across 8 files (each producing a different output), **55 `toLocaleDateString` / `toLocaleString` / `toLocaleTimeString` call sites** (varying locale/options), **16 `date-fns` `format()` calls** isolated to the timeline module (a second date library), **0 `pluralize()` helper**, **87 ad-hoc count strings** (83 hand-written `=== 1 ?` ternaries + **4 hardcoded plurals** that render "1 documents" / "1 pages"). The same logical operation reimplemented N times; representations drift. The one partial exception — `utils/formatRelativeTime.ts`, used in 4 places — proves the model works when a shared util exists.

**Why it's bad**: ARCH-006 again, this time inside the frontend repo. Eight reimplementations of date-formatting drift; pluralization-by-convention guarantees "1 documents" / "1 citations" bugs reappear. Generates FE-013 / FE-014 / FE-015 / FE-016 / FE-017 / FE-018.

**Target architecture**: a `frontend/src/lib/format/` layer — `formatDate` / `formatDateTime` / `formatRelative`, `pluralize` / `formatCount` — built on one date library, plus an ESLint rule banning raw `toLocaleDateString` in components (the helper becomes the only way). Migrate the ~71 date call sites and 87 count strings incrementally.

**ARCH-PATTERNS map**: P4 (helper-that-should-be-only-API simply doesn't exist; the wall is the layer + ESLint ban), P2 (8 reimplementations of `formatDate`).

**Detector** (run from repo root):
```
rg -n "(function|const)\s+(formatDate|formatDateTime|formatDateRange)" -g "!*.test.*" frontend/src
rg -nc "toLocaleDateString|toLocaleString|toLocaleTimeString|Intl\.DateTimeFormat" -g "!*.test.*" frontend/src
rg -n "\bformat\(" -g "!*.test.*" frontend/src        # filter to date-fns
rg -n "(=== 1 \?|!== 1 \?)" -g "!*.test.*" frontend/src
```

**Census (2026-05-20)**: 8 `formatDate` impls · 55 `Intl` call sites · 16 `date-fns` calls · 87 count strings · 4 hardcoded plural bugs.

**Files**: `frontend/src/lib/utils.ts` (the gap); 8 `formatDate` definitions in `StatementSection.tsx:43`, `DocumentList.tsx:115`, `TimelineRenderer.tsx:32`, `CurrentStatusSection.tsx:51`, `VerificationBadge.tsx:36`, `TimelineHeader.tsx:47`, `LiveDiscoveriesPanel.tsx:90`, `formatRelativeTime.ts:108`; the 4 acute plural bugs: `MatterCard.tsx:169`, `MatterCard.tsx:217`, `OCRQualityDetail.tsx:141`, `lib/utils/citationGrouping.ts:158`.

---

**Common thread across all eleven**: implicit coordination through convention instead of explicit coordination through structure. Backend: two pipelines that "should" stay in sync (ARCH-001), four queues that "should" be isolated (ARCH-002), a chain that "should" reach its terminal task (ARCH-003), 14 LLM call sites that "should" honor the rate limiter (ARCH-004), a Postgres function that "should" stay signature-compatible across two repos (ARCH-005), 36 TypeScript files that "should" mirror Pydantic models exactly (ARCH-006), a library subsystem with 4 entry paths that "should" all dispatch OCR (ARCH-007). Frontend: 7 matter panels that "should" each handle 404/empty/auth (FE-ARCH-01), 68 files that "should" each remember their own breakpoints (FE-ARCH-02), ~47 skeletons that "should" stay dimensionally in sync with their real components by hand (FE-ARCH-03), and 87 count-strings + 8 `formatDate` impls that "should" agree on format (FE-ARCH-04). None are enforced by the architecture, all have been violated in production, and each violation has cost a debugging session — sometimes a multi-day one. The fix in every case is the same shape: **make the right thing the only possible thing.** Structure beats vigilance.

---

## 1. Security

### SEC-002: Supabase Linter Warnings (2026-05-08) | Status: PARTIALLY FIXED (A+B+C+D fixed 2026-05-13, E requires Pro plan)

**Source**: Supabase Dashboard Database Linter. 5 categories of warnings:

**A. `anon` can execute SECURITY DEFINER functions (42 functions)** | Priority: P1 | **FIXED (2026-05-13)**
Unauthenticated users could call these via PostgREST `/rest/v1/rpc/...`. Research confirmed: frontend makes zero `.rpc()` calls, backend uses `service_role` key (bypasses permissions), `handle_new_user` is a trigger (runs as owner), `user_has_matter_access`/`user_has_storage_access` are RLS policy helpers.

**Key finding**: `REVOKE FROM anon` alone is insufficient — Supabase default privileges grant EXECUTE to `PUBLIC` on all functions in `public` schema. Required `REVOKE FROM PUBLIC, anon` to actually block access. Also fixed default privileges for future functions.

**Fix applied**: Migration `20260513000001_sec002_revoke_anon_harden_rpcs.sql`. Verified: 0 SECURITY DEFINER functions callable by anon. `authenticated` and `service_role` retain access.

**B. `function_search_path_mutable` (7 functions, only 4 needed fix)** | Priority: P2 | **FIXED (2026-05-13)**
3 of 7 already had `SET search_path = public`. Fixed the remaining 4: `get_consistency_issue_counts`, `update_consistency_issues_updated_at`, `count_queries_per_matter`, `adjust_bbox_text_offsets`.

**C. Materialized views exposed via API (3 views)** | Priority: P3 | **FIXED (2026-05-13)**
`contradiction_savings_report`, `monthly_cogs_by_matter`, `cost_per_document_page` — admin cost views revoked from `PUBLIC`, `anon`, and `authenticated`. `service_role` retains access.

**D. `extension_in_public` — pg_trgm** | Priority: P3 | **FIXED (2026-05-13)**
`pg_trgm` moved from `public` to `extensions` schema. `find_library_duplicates` recreated with `SET search_path = public, extensions`. REVOKE re-applied. Verified: pg_trgm in extensions, anon blocked, function executes correctly.

**E. Leaked password protection disabled** | Priority: P2 | Status: DEFERRED (requires Supabase Pro plan)
Supabase Auth HaveIBeenPwned check is off. Requires Pro plan to enable.

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
| **Status** | FIXED (2026-05-14) — All 5 layers fixed. L1-3 (2026-04-17), L4-5 (2026-05-14). |
| **Date Found** | 2026-02-27 |
| **Source** | PRODUCTION-BUGS-2026-02-27.md (BUG-002) |

**Description**: One large matter's `entity_alias_resolution_batch` blocks ALL other users' document processing. Not a single root cause — five layers compound:

**Layer 1 — Prefetch hoarding (config)**: `prefetch_multiplier=4` × `concurrency=50` = 200 tasks buffered. New user's tasks can't be picked up until buffer drains. **FIXED** (commit `47ef182`): set `worker_prefetch_multiplier=1`.

**Layer 2 — No physical queue isolation (deployment)**: One process consuming `-Q default,llm,heavy,low`. Four queues, zero isolation. `resolve_aliases` (30 min) competes directly with `process_document` (5 sec). **FIXED** (commit `3c07996`): WPS-001 Phase 2 — dual worker deployment. `ldip-worker` handles default+llm (fast pipeline tasks), `ldip-worker-slow` handles heavy+low (O(n^2) tasks + maintenance). Separate Railway services, separate processes, true physical isolation.

**Layer 3 — Gemini bottleneck (the actual ceiling)**: Global rate limit `max_concurrent=1`, `min_delay=6.0s`, `max_rpm=10` (free tier). ALL LLM tasks share this single 10 RPM quota. **FIXED** (commit `3581bdd`): upgraded to Gemini Paid Tier 1 (1000 RPM). Rate limiter config updated from 10 RPM → 1000 RPM, min_delay 6.0s → 0.06s, max_concurrent 1 → 10.

**Layer 4 — Monolithic task design**: `resolve_aliases` is a single Celery task holding 1 greenlet for up to 30 minutes. Internally batches (10 pairs, 3-way semaphore) but Celery can't preempt or interleave. **FIXED** (2026-05-14): 3-phase fan-out decomposition. Phase 1 (CPU, ~10s): fetches entities with pagination (fixes 1000-entity cap), finds high/medium pairs, creates high-confidence edges inline, dispatches Phase 2 batches. Phase 2 (LLM, ~30-120s each): `resolve_aliases_batch` analyzes ~20 pairs via Gemini per task, stores results in Redis, last batch triggers Phase 3 via Redis INCR counter. Phase 3 (CPU, ~30s): `resolve_aliases_finalize` applies transitive closure, persists all edges via UPSERT, updates alias arrays from a single convergence point (fixes read-modify-write race in `add_alias_to_entity`). All 3 phases routed to `low` queue → heavy worker (10 greenlets). Redis dedup lock prevents concurrent runs for same document. Additional fixes: removed `queue="default"` overrides in `_dispatch_post_entity_tasks` (all 3 dispatches), entity context capped at 2000 chars/entity.

**Layer 5 — Gevent timeout fiction**: `soft_time_limit` is silently ignored with gevent pool. `worker_max_tasks_per_child` and `worker_max_memory_per_child` are no-ops. Every safety net Celery advertises for bounding task duration does not fire with gevent. **FIXED** (2026-05-14): Added coroutine cancellation in `_run_in_thread()` (`utils.py`). When `future.result(timeout=N)` fires `TimeoutError`, `future.cancel()` is called to cancel the coroutine on the shared event loop, preventing orphaned coroutines from leaking Gemini API calls and rate limiter slots. Added explicit `(TimeoutError, SoftTimeLimitExceeded)` catch in `resolve_aliases` so timeouts are logged as "TIMEOUT" instead of "UNEXPECTED_ERROR". This fix benefits all ~80 `run_async` call sites system-wide, not just alias resolution. **Timeout alignment (same day)**: The coroutine cancellation exposed that `embed_chunks` (soft_time_limit=900s), `extract_entities` (600s), and `extract_citations` (600s) all used the default `_run_async` timeout of 300s — half their soft limit. Previously invisible because leaked coroutines finished the work silently. Fixed: `_run_async` timeout now set to `soft_time_limit - 60s` for each. Live evidence: `extract_entities` on a 326-page doc timed out at 300s on first deploy; succeeded after timeout alignment.

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
| **Severity** | P2 (Medium — downgraded from P1: summary job unsticks page in ~5-10s without fix) |
| **Status** | FIXED (2026-05-25) |
| **Date Found** | 2026-04-30 |
| **Source** | GAP-1 verification testing |

**Description**: When a user uploads an Act PDF via the Upload Wizard, the processing page (`/upload/processing`) showed slow progress because the library path creates no `processing_jobs` for document pipeline stages. Originally documented as "stuck at 0% forever" — but live testing (2026-05-25) revealed the summary pre-generation job creates a `processing_jobs` row, so the page would unstick in ~5-10s without the fix. Severity downgraded from P1 to P2.

**Root cause**: The library path (both branches of `_upload_act_to_library`) creates no `documents` row and no document-pipeline `processing_jobs`. The processing page polls `jobsApi.getStats(matterId)` and checks `total > 0`. The summary job provides `total=1`, but only after ~5-10s of the user staring at "Stage 1 of 5: Uploading files" at 0%.

**Fix Applied (2026-05-25)**: Frontend-only (Option C from blast-radius research). When `documentType === 'act'` and all uploads complete, the processing page sets `actUploadComplete = true`, which short-circuits `isProcessingComplete` to `true`. The page shows the completion screen immediately and redirects to the matter workspace. No backend changes, no polling changes, no timer heuristics. The `uploadWizardStore` already had `documentType` from the user's type selector.

**Live-tested (2026-05-25)**: Uploaded `test-doc-1.pdf` as Act → processing page auto-completed instantly → redirected to `/matter/.../summary`. Confirmed the page no longer waits for the summary job.

**Additional symptoms** (still present for act-only matters — separate from UX-015):
- Dashboard matter card shows "0 pages" despite linked library Act having content
- "0% Verified, 0 Issues" — verification runs against `documents`, finds nothing
- These are display issues for act-only matters, not processing page bugs.

**Design question** (unchanged): Should Acts-only matters even show summary/timeline/contradictions? Acts are reference material, not case files.

**Files changed**: `frontend/src/app/(dashboard)/upload/processing/page.tsx`

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
| **Status** | FIXED (2026-05-13) |
| **Date Found** | 2026-04-16 |
| **Source** | Production log review (Railway CLI) |

**Description**: RedBeat scheduler crashes with `redis.exceptions.LockNotOwnedError: Cannot extend a lock that's no longer owned`. The lock expired before beat could extend it, likely because the worker process was too busy (or the Redis connection dropped momentarily). Beat dies and does not auto-restart — no more periodic tasks fire until the entire worker service restarts.

**Root Cause**: RedBeat was added speculatively (commit `5d5237d`, 2026-02-25) for multi-replica leader election that never materialized — Railway Hobby plan supports 1 replica. Before RedBeat, beat used Celery's default `PersistentScheduler` with no Redis lock and no crash mode. RedBeat's distributed lock was the sole source of the fatal `LockNotOwnedError`.

**Fix Applied (2026-05-13)**: Three changes:
1. **Removed `celery-redbeat` entirely** — dropped dependency from `pyproject.toml`, removed all `redbeat_*` config from `celery.py`. Returned to Celery's default `PersistentScheduler` (local shelve file at `/tmp/celerybeat-schedule`). Schedule is static config — file loss on container restart is harmless.
2. **Added restart loop** in `start-worker.sh` — beat runs in a `while true` subshell with `trap 'exit 0' TERM` for clean SIGTERM handling. If beat crashes for any reason, it auto-recovers in 10 seconds.
3. **Added lean beat mode** — `CELERY_BEAT_ONLY=true` env var skips heavy task module imports in `celery.py` (14 modules pulling PyTorch, Docling, Google Cloud, etc.). Beat only needs task name strings + schedule config. Saves ~1GB RAM.

**Live verified (2026-05-13)**: Beat started with `celery_beat_only_mode`, using `PersistentScheduler`. Heartbeat task dispatched and succeeded within 60s. `/api/health/celery` reports `{"status": "healthy", "heartbeat_ttl_seconds": 136}`. Zero `LockNotOwnedError`. Stale `redbeat:schedule` and `redbeat:statics` Redis keys cleaned up.

**Files**: `backend/app/workers/celery.py`, `backend/start-worker.sh`, `backend/pyproject.toml`, `backend/uv.lock`

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

### INF-012: Silent-Failure Detection — `system_health` Invariant Audit (the "watchman")
| Field | Value |
|-------|-------|
| **Severity** | P1 (observability gap — these silent failures cost months of invisibility) |
| **Status** | DEPLOYED + VERIFIED (2026-06-04) — worker+API live; migration applied; 9/9 tests pass; first prod audit ran end-to-end against live data, all 3 invariants `ok=true` (0/0/0 baseline), `GET /health/invariants` returns `status:healthy`. Beat re-runs every 30 min. |
| **Date Found** | 2026-06-04 |
| **Source** | Pattern across GAP-2, GAP-3, LLM-005 (GAP-11), GAP-23, GAP-24 |

**The shape**: every P0/P1 in LDIP's history is *a claimed terminal/success state not backed by the data it promises* — the inverse of ARCH-003. `documents.status='completed'`+0 chunks (GAP-2); library doc 'embedded'+NULL embeddings (GAP-3); cost "tracked"+0 `llm_costs` rows (LLM-005); citation write "ok"+CHECK-rejected (GAP-23); Act pipeline "complete"+0% verified (GAP-24). Each sat **invisible for months** because the status lied and nothing asserted the backing data existed.

**Fix**: one continuous, **read-only** beat task (`audit_system_invariants`, every 30 min, `low` queue) runs a declarative catalog of invariants asserting `claimed_state ⟹ required_data_exists` and **REPORTS** to a new `system_health` table (one upserted row per invariant — single convergence point). It never heals — that complements the silent-healing reconcilers (recover_stuck_documents, sync_citation_statuses_with_resolutions) which fix-and-forget and so hide drift. Read via `GET /health/invariants` (surfaces `healthy`/`violations`/`stale`/`unknown`; `stale` = the auditor itself stopped).

**Seed invariants** (extensible — new shape = new catalog entry, never a new code path): `completed_docs_zero_chunks` [GAP-2], `embedded_library_docs_null_embeddings` [GAP-3], flagship `acts_resolved_embedded_zero_verified` [GAP-24]. All measured clean at baseline (0/0/0) on 2026-06-04, so any future >0 is a real signal.

**Key design decisions** (verified live, not guessed):
- **All-Python checks, not SQL strings.** The flagship's citation→Act join needs `normalize_act_name` (abbreviation/backronym resolution); a `lower/trim` SQL approximation matched **ZERO** rows live — i.e. it would be a dead guard that always reports "healthy". And there is no clean raw-SQL path in the app (no `exec_sql` RPC — a generic one contradicts SEC-002 hardening — and `DATABASE_URL` is not in config). The only DB-access path is the Supabase/postgrest client, so every invariant runs through it.
- **Known-good carve-outs are mandatory** or the guard cries wolf: the flagship excludes `act_unavailable` citations (legitimate when an Act is not uploaded — e.g. doc `a65f4b17`, whose 867 citations are correctly `act_unavailable`), requires the Act to be fully embedded (shared `act_doc_fully_embedded` gate, extracted to `app/services/act_verification_state.py` so the auditor and the RISK-1 reconciler use ONE definition), and only counts `pending` citations older than a 60-min grace window.
- **The watchman's own test proves it isn't a dead battery**: it must FLAG the GAP-24 shape and must NOT flag the `a65f4b17` carve-out.

**Files**: `supabase/migrations/20260604000002_create_system_health_table.sql`, `backend/app/services/system_invariants.py`, `backend/app/services/act_verification_state.py`, `backend/app/workers/tasks/maintenance_tasks.py` (`audit_system_invariants`), `backend/app/workers/celery.py` (beat entry), `backend/app/api/routes/health.py` (`GET /health/invariants`), `backend/tests/services/test_system_invariants.py` (9 tests). See memory `silent-failure-detection-handoff`.

**Layers note**: the watchman catches silent **data**-state failures in prod (layer 1). CI catches silent **code** regressions pre-deploy (layer 2 — see INF-013). Skills catch known **shapes** for human investigation (layer 3). This entry is layer 1; INF-013 is the layer-2 gap.

---

### INF-013: CI Is Configured But Not Actually Green — 517 Pre-Existing `ruff` Errors
| Field | Value |
|-------|-------|
| **Severity** | P2 (CI is decoration until it can pass + block merges) |
| **Status** | IN PROGRESS (2026-06-04: lint + format green & regression-verified across 7 commits; pytest-green + branch-protection still pending — see **Progress** below) |
| **Date Found** | 2026-06-04 |
| **Source** | Silent-failure detection session (INF-012) |

**Description**: `.github/workflows/ci-backend.yml` runs `uv run ruff check .` over the whole backend. On 2026-06-04 that step fails with **517 errors** in pre-existing committed code (config selects `E,F,I,UP,B,SIM`; local ruff 0.14.7 ≈ CI's pinned ≥0.14.10). So CI either has **never run green** (workflows added recently in Story 13.5; they only trigger on push to `main`/`develop`, and work happens on feature branches) or its failures are ignored. **A red CI that doesn't block merges is not a guard.**

**Breakdown** (auto-fixable marked *): I001 unsorted-imports 140*, F401 unused-import 77*, B904 raise-without-from 67, UP017 datetime-utc 50*, F541 f-string-no-placeholder 37*, E402 import-not-at-top 27, F841 unused-var 21, B023 loop-var-in-closure 15, F821 undefined-name 7, plus assorted SIM/UP nits. ~334 of 517 fix with `ruff check --fix`.

**F821 "undefined name" investigation (2026-06-04)** — all 7 checked; **none are active production bugs**:
- `app/core/llm_rate_limiter.py:292,296,348` `threading` — quoted string annotations (never evaluated); `threading` imported locally where actually used. **False positive.**
- `app/engines/orchestrator/adapters.py:781,782` `RerankedSearchResult` — quoted annotations pointing at an unimported name. Broken type-hint only, no runtime path. **Cosmetic.**
- `app/workers/tasks/evaluation_tasks.py:1103` `e` — exception var referenced in a nested closure that is *called inside* the same `except` block (before Python auto-`del`s `e`). **Works today; fragile** (breaks only if the call is ever deferred).
- `scripts/reextract_timeline_events.py:344` `timeline_service` — out-of-scope reference (assigned at line 132 in a different scope); would `NameError` if that branch runs. **Real defect, but in a manual one-off script, not the live app.**

**Recommended path** (not yet done — deferred as out-of-scope for INF-012): (1) `ruff check --fix` the ~334 safe fixes in a dedicated cleanup PR; (2) hand-review B904/E402/B023; (3) fix the one real defect (`reextract_timeline_events.py:344`); (4) get CI green; (5) **turn on branch protection so a red CI blocks merges** — only then is CI a real layer-2 guard.

**Progress (2026-06-04, branch `ci-hardening-inf013`):**

Re-confirmed with CI's pinned ruff 0.14.10: the real count was **676 errors / 416 auto-fixable** (the 517/0.14.7 figure undercounted). Also discovered two deeper "CI is decoration" facts the original entry missed:
- **CI never *ran* at all.** `ci-backend.yml` triggered only on `main`/`develop`, which **don't exist** (default branch is `master`). Fixed first (commit 1) — keystone, since branch protection can't gate a check that never executes.
- **`master` was 21 commits stale** vs the work branch; fast-forwarded `master` to current (incl. the INF-012 watchman) so the cleanup PRs have the right base.

Seven commits land the cleanup (all behavior-preserving except #4):
1. `ci:` wire `ci-backend.yml` to `master`.
2. `chore:` `ruff --fix` 463 safe auto-fixes (160 files).
3. `chore:` hand-fix the 260 non-auto-fixable — B904 `from e`/`from None`; per-case F841 (kept every side-effecting call, e.g. `_verify_document_access`; noqa+TODO on latent `storage_path`/`year` stubs); B023 default-arg binding (all verified same-iteration → no late-binding bug); SIM105/102/108 rewrites or noqa; B007 `_`-rename; **scoped** noqa for E402 load-order + the 6 F821 false-positives (NOT the reextract one).
4. `fix:` the one real F821 defect — `reextract_timeline_events.py` entity-linking branch never created `timeline_service`; now does.
5. `test:` unblock pytest **collection** — two pre-existing aborts: `hypothesis` never declared as a dep (added + relocked), and `test_ocr_chunk_service.py` imported the removed `STALE_CHUNK_THRESHOLD_SECONDS` constant (Story 4.3 made it config-driven; test rewritten to assert `settings.chunk_stale_threshold_seconds == 90`).
6. `style:` big-bang `ruff format .` (415 files, semantically null) — makes the `ruff format --check` gate green.
7. `chore:` `.git-blame-ignore-revs` for #6.

`ruff check .` and `ruff format --check .` are now **clean**. **Regression-verified** against `master` using a throwaway local redis container (Docker) + CI's placeholder env: identical invocations on both branches yield **identical failure sets (196 = 196), 0 branch-only failures** → the cleanup introduced no behavior change any test detects.

**NEW BLOCKER for step (4) "get CI green":** that 196 is a separate, pre-existing problem — **196 tests fail in a CI-like env** (placeholder Supabase/API keys) with `getaddrinfo`/`ConnectError`/`missing-api-key`. They fail **identically on `master`**, so they're not from this cleanup, but they will likely keep CI's **pytest** step red even after lint/format are green. Unknown whether they pass on CI's Linux env (could be Windows-local mock-patching quirks) — **the next step is to open a PR `ci-hardening-inf013` → `master` so CI actually runs and tells us the truth**, then decide whether the 196 are a real CI blocker (separate work item: proper Supabase/LLM mocking) before step (5) branch protection. Do **not** enable branch protection until CI's full job (lint + format + pytest + security-tests) is actually green.

**CI run confirmed (2026-06-04, PR #60, run 26946760147):** opening the PR triggered backend CI for the first time ever. Results:
- ✅ **`ruff check .` GREEN on Linux.** ✅ **`ruff format --check .` GREEN on Linux.** (Lint/format half of INF-013 = done.)
- Surfaced a **third undeclared-dep gap**: `pytest-cov` was used by the CI command (`--cov=app`) but never declared → `unrecognized arguments: --cov`, pytest aborted at exit 4. Fixed (commit 9: add `pytest-cov`, relock).
- ❌ **pytest: 2955 passed / 236 failed** on CI. The 236 are the pre-existing env/mock-dependent failures — **confirmed real on Linux**, spanning Supabase + OpenAI + Gemini + Cohere mock gaps across many test files. NOT caused by this cleanup (master-diff proved 0 branch-only failures).

**Net:** INF-013's lint/format/deps work is **complete and CI-verified green**. The remaining blocker to a *fully* green merge-gate is the **236 pre-existing pytest failures** — a distinct test-suite-health work item (proper external-service mocking; candidate for `forensic-hunt` to find shared root-cause SHAPEs). Branch protection on the **full** `lint-and-test` job must wait for that. **Option to get a partial real guard now:** split `ci-backend.yml` into separate `lint` (ruff+format, already green) and `test` (pytest) jobs, and make only `lint` merge-blocking until the 236 are fixed.

---

### INF-014: 236 Pre-Existing pytest Failures — Test Suite Rotted While CI Never Ran
| Field | Value |
|-------|-------|
| **Severity** | P2 (blocks the `test` CI job from becoming merge-blocking; **test-only — no prod impact**) |
| **Status** | OPEN (discovered 2026-06-04 via INF-013's first-ever real CI run) |
| **Date Found** | 2026-06-04 |
| **Source** | INF-013 — first real CI execution (PR #60, run `26946760147`) |

**Description**: The first time backend CI ever actually ran (after INF-013 fixed the branch triggers, the 676 lint errors, the format gate, and three undeclared deps — `hypothesis`/`pytest-cov`), the `pytest` step reported **2955 passed / 236 failed** on CI (ubuntu-latest + redis 7-alpine + placeholder Supabase/LLM creds). These 236 are **pre-existing and NOT caused by the INF-013 lint cleanup** — proven by an apples-to-apples branch-vs-`master` diff (identical failure sets, **0 branch-only failures**) run against a throwaway local redis container. They reproduce identically Windows-local and Linux-CI.

**Meta-cause (the important part)**: this is the **same disease as INF-013, one layer down**. Because CI never executed for months (wrong triggers + missing deps), nothing forced tests to stay in sync with code. The suite **drifted** — production signatures, return shapes, constants, enums and class internals changed while tests kept asserting the old contract. A CI that doesn't run doesn't just miss lint; it lets the entire test suite rot silently. (The INF-013 `STALE_CHUNK_THRESHOLD_SECONDS` collection error was the first visible symptom of this rot.)

**Root-cause taxonomy** (from sampling representative failures across the largest clusters; per-line evidence captured 2026-06-04 with redis-container + the placeholder env from INF-013's notes):

1. **Test↔code contract drift** (largest, structural — tests assert a stale API):
   - *Signature drift* — `engines/citation/test_storage.py`: `TypeError: get_citations_by_document() missing 1 required positional argument: 'matter_id'` (matter-isolation param added to the method; tests never updated). ~6.
   - *Return-shape drift* — `services/memory/test_query_cache.py`: `KeyError: 'count'` (cache-stats dict shape changed). ~10.
   - *Constant drift* — `services/rag/test_reranker.py::test_default_top_n`: `assert 5 == 3` (default `top_n` changed 3→5). Same shape as the `STALE_CHUNK` constant test.
   - *Renamed-internal drift* — `services/ocr/test_gemini_validator.py`: `AttributeError: ... does not have the attribute '_model'` (test `patch.object(..., '_model')`s a renamed attribute). ~10.
   - *Behavior drift* — `engines/orchestrator/test_intent_analyzer.py`: `assert <QueryIntent multi_engine> == <citation>` (classifier routing changed; also nudged by placeholder `GOOGLE_API_KEY` → LLM path falls back to `multi_engine`). ~23 (largest single cluster).

2. **Unmocked external-service calls** (env-dependent) — tests hit real network: `ConnectError(gaierror(11001, 'getaddrinfo failed'))` resolving `placeholder.supabase.co` / LLM endpoints. Seen in `library_service`, `api/routes/test_entities`, `engines/timeline/test_date_extractor`, `services/test_global_search_service`, `engines/citation/test_extractor`, `workers/test_document_tasks`. They call the **real** client because nothing patches it → need a conftest-level Supabase + httpx mock.

3. **Rate-limiter (slowapi) unit-call incompatibility** — `api/routes/test_summary.py` (~18, 2nd-largest): `Exception: parameter 'request' must be an instance of starlette.requests.Request`. Endpoints decorated with `@limiter.limit(...)` can't be called as plain functions without a real `Request`; the tests predate the decorator.

4. **Auth dependency not overridden** — `api/test_users.py` (~9): `assert 401 == 200` — the test client never overrides/mocks `get_current_user`, so auth returns 401.

5. **Invalid test fixtures** — `workers/test_document_tasks.py`, `services/ocr/*`: `pypdf.errors.PdfStreamError: Stream has ended unexpectedly` (fake PDF byte fixtures aren't parseable PDFs).

6. **Test-isolation / state pollution** (NOT a code or contract bug) — `services/test_chunking_logging.py` (16): **passes 18/18 in isolation**, fails only inside the full suite → an earlier test mutates shared global state (structlog config / a singleton). Flaky-ordering, fixable independently. (This is exactly what made the first branch-vs-`master` comparison falsely report "16 regressions" before re-running apples-to-apples.)

**Top failing files** (local full-suite run, 212 of the 236; CI's +24 are coverage-context / suite-order deltas):

| count | file | dominant category |
|------:|------|-------------------|
| 23 | `engines/orchestrator/test_intent_analyzer.py` | behavior drift (1) |
| 18 | `api/routes/test_summary.py` | slowapi rate-limit (3) |
| 16 | `services/test_chunking_logging.py` | test-isolation (6) |
| 11 | `workers/test_engine_tasks_anomaly_trigger.py` | unmocked / drift (2/1) |
| 11 | `engines/timeline/test_date_extractor.py` | unmocked LLM (2) |
| 10 | `services/ocr/test_gemini_validator.py` | renamed-internal (1) |
| 10 | `services/memory/test_query_cache.py` | return-shape (1) |
| 9 | `api/test_users.py` | auth not mocked (4) |
| 8 | `workers/test_document_tasks.py` | invalid PDF + unmocked (5/2) |
| 6 | `services/test_global_search_service.py` · `engines/citation/test_storage.py` · `engines/timeline/test_event_classifier.py` · `engines/rag/test_query_profile.py` · `workers/test_chunked_document_tasks.py` | mixed (1/2/5) |
| 5 | `services/table_extraction/test_extractor.py` · `engines/orchestrator/test_adapters.py` | drift/unmocked |
| ≤4 | ~25 more files (orchestrator_safety, aggregator, maintenance_tasks, summary_service, subtle_detector, reranker, hybrid_search, search, documents, …) | mixed |

**Reproduce**: `docker run -d --rm -p 6379:6379 redis:latest`, then from `backend/` with the CI placeholder env (`SUPABASE_URL=https://placeholder.supabase.co`, placeholder keys, `REDIS_URL=redis://localhost:6379/0`): `uv run pytest --ignore=tests/integration -q -rfE`. Two files also need pre-existing fixes already landed on the branch (`hypothesis` dep; the `STALE_CHUNK` test) to even collect.

**Remediation (separate work item — do NOT fold into INF-013):**
1. Run `forensic-hunt` on cluster "pre-existing pytest failures" to confirm the shared SHAPEs above and surface any missed.
2. Fix by category, highest-leverage first:
   - **Conftest autouse fixture** mocking the Supabase client + outbound httpx for unit tests → clears category 2 broadly in one move.
   - FastAPI `app.dependency_overrides` for auth (4) and a Request-bearing/override harness for rate-limited endpoints (3).
   - Update drifted assertions/signatures/constants/patched-names to the **current** contract (1) — mechanical but per-test; each must reflect intended current behavior, not just be forced green.
   - Real minimal PDF fixture (5).
   - Find and fix the global-state mutator behind the `test_chunking_logging` ordering pollution (6).
3. Only after `uv run pytest` is green in the CI env, promote the `test` job to a **required** status check (alongside `lint`, already required) — completing INF-013 step (5).

**Guard value**: each of these 236 is a test that *would* have caught a real regression but silently didn't, because CI never ran. Fixing them converts the `test` job from decoration into a real layer-2 guard — the entire point of INF-013/INF-014.

---

#### INF-014 — forensic-hunt findings (2026-06-04, evidence-backed)

Ran the `forensic-hunt` protocol on this cluster. Reproduced the full suite (placeholder env + redis 7-alpine): **212 failed / 2846 passed / 4 skipped** locally — the local-vs-CI gap (212 vs 236) is the predicted `--cov` + `tests/integration` suite-order delta. Then captured one-line tracebacks for every failing file and grouped by **error signature** (not by file). Raw signature histogram and per-file evidence are in the session log.

**Key correction to the framing above.** The earlier note implied a single shared SHAPE (a conftest boundary) would clear most failures. **The signature evidence falsifies that.** The 212 split into **three** shapes, and the structural one is the *minority*:

| Shape | Count | % | Nature | Fix |
|------|------:|---:|--------|-----|
| **A — harness-boundary** (slowapi direct-call 18 · auth not overridden 9 · unmocked network · **state-pollution 16**) | **41** | **19%** | Structural: `conftest.py` is a *sticky-note-where-a-wall-belongs* (ARCH-PATTERNS P4/P1). It never established the test boundary, so every author improvised. | One `conftest` wall clears the whole class |
| **B — contract/mock drift** (signature · return-shape · constant · renamed-internal · routing · mock-shape) | **167** | **79%** | Production legitimately changed; tests assert the old contract. **Not** structurally fixable. | Per-test mechanical repair to the *current* contract |
| **C — bad PDF fixtures** | **4** | **2%** | Fake byte fixtures aren't parseable PDFs. | One real minimal-PDF fixture |

Representative confirmed signatures: `TypeError: '>' not supported between 'MagicMock' and 'int'` (mock-shape drift, `test_intent_analyzer`); `SearchResult.__init__() missing 'bbox_ids'` (signature drift, `test_search`); `get_citations_by_document() missing 'matter_id'` (signature drift); `assert 401 == 200` (auth, `test_users`); `parameter 'request' must be ... starlette.Request` (slowapi, `test_summary`); `KeyError: 'count'` (return-shape, `test_query_cache`); `Failed to read PDF page count: Stream has ended` (bad fixture). The 16 state-pollution failures (`test_chunking_logging`) **pass in isolation and only fail in full-suite order** — proven by re-running the 11 densest files together (125 expected → 109 failed / 182 passed, the missing 16 being exactly that file).

**Honesty caveats:** ~40 of the Shape-B failures landed in a coarse `other assert` bucket — confirmed drift, but the fine sub-type (constant vs return-shape vs routing) isn't resolvable from a one-line traceback. And the A/B/C percentages use denominator 212 (the 16 pollution failures folded into A); the per-signature run only classifies 196 because the 16 are invisible outside the full suite.

**Meta-lesson (the durable one):** an unenforced gate doesn't just miss what it checks — it removes the back-pressure that keeps the whole layer honest. INF-013 was lint rot; INF-014 is the same disease one layer down (test rot). Two *different* kinds of rot accumulated invisibly for months behind one broken CI trigger.

**Revised prosecution plan (supersedes the 3-step remediation above; ordered by leverage, not size):**
1. **① Quarantine + enforce (highest leverage, smallest effort).** Apply `xfail(strict=True, reason="INF-014")` to the known-failing set via a **single central quarantine list + one `conftest` `pytest_collection_modifyitems` hook** — NOT 212 scattered decorators (that would be the ARCH-003 sticky-note shape). Then flip the `test` CI job to a **required** status check. This makes the gate a real wall *today* for the 2846 passing tests: any new drift to currently-green code blocks merge. `strict=True` is self-cleaning — a repaired test XPASSes and is *forced* off the list. The quarantine list must be built from the **authoritative CI failure set** (CI runs `--cov` and includes `tests/integration`), not the local 212.
2. **② Build the Shape-A wall** (~41 tests, one focused PR): autouse Supabase + outbound-httpx mock; a canonical authed-client factory using `app.dependency_overrides[get_current_user]` + a real `Request`; an autouse global-state reset (kills the 16 pollution failures). Through `architecture-guard` before code, `hostile-review` after. As tests go green, their xfail entries self-remove.
3. **③ Mechanical drift sweep for Shape B** (~167, the grind; parallelizes by file). Each fix must reflect intended current behavior, not be force-greened.
4. **④ Real minimal-PDF fixture** for Shape C (~4).
5. **⑤ Regression sentinel:** the now-required `test` job + the `xfail(strict=True)` self-cleaning quarantine is the sentinel — the suite can no longer rot silently, because new drift turns the required job red and fixed tests are forced off the list.

#### INF-014 ② — SHIPPED 2026-06-04 (the Shape-A wall) + bugs uncovered

**What shipped:** one conftest wall (`backend/tests/conftest.py`) — autouse structlog cache-off + contextvars reset, autouse real-httpx-egress block, a canonical `authed_client` via `app.dependency_overrides[get_current_user]`, and a `mock_request` (real `starlette.Request` + scoped limiter disable). Quarantine trimmed **218 → 190** (removed 28 that pass for the right reason ON CI: chunking_logging 16, test_users auth 9, summary get_verifications 2, dpp002 chain 1). Required `test` job green on CI (PR #62).

**⚠️ LESSON — local `.env` masks CI failures (cost me a red CI run).** I first removed 32, but 4 timeline tests (`test_event_classifier` mocked_gemini ×2 + network_timeout, `test_date_extractor::test_extract_with_mocked_gemini`) passed locally and FAILED on CI with `GeminiClientError: Gemini API key not configured`. They construct `EventClassifier()`/`DateExtractor()` (which require `GEMINI_API_KEY`) *before* the `_model` mock applies; my local `.env` supplies `GEMINI_API_KEY`, CI does not (ci-backend.yml sets OPENAI/GOOGLE/COHERE placeholders but NOT GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT_ID, or GOOGLE_DOCUMENT_AI_PROCESSOR_ID). SAME masking hit the OCR test. **Faithful local CI-parity REQUIRES emptying every key CI doesn't set** (`GEMINI_API_KEY= GOOGLE_CLOUD_PROJECT_ID= GOOGLE_DOCUMENT_AI_PROCESSOR_ID=`), not just setting placeholders for the ones it does. The 4 were re-quarantined (they're genuine CI failures). NOTE: a follow-up investigation (finding #6 below) showed a `GEMINI_API_KEY: placeholder` CI-env fix does NOT cleanly resolve them — 3 of the 4 are broken mocks that make real Gemini calls — so that idea was investigated and dropped; they belong to ③.

**⚠️ strict=FALSE caveat (deviates from the ⑤ plan above).** ① shipped `strict=False`, NOT `strict=True`. Consequence: the quarantine is **NOT self-cleaning** — a fixed test silently XPASSes and stays on the list until a human prunes it (as ② did manually). The "self-cleaning sentinel" promised in ⑤ does not exist. Pruning pressure is a periodic `-rX` report only. If ③ stalls, the 190 become permanent dead tests behind a green badge — the exact rot INF-014 set out to kill, now blessed by a required green check. **This is the central honesty risk of the whole initiative; see CI-INTEGRITY note below.**

**✅ RESOLVED 2026-06-10 — strict=True self-cleaning quarantine shipped (closes the caveat above).** The conftest hook now applies `xfail(strict=True)` per entry, so a fixed test's XPASS **fails the required `test` job** and forces the fixer to delete its line — self-cleaning is now structural, not a "remember to prune" convention. The original `strict=False` rationale (a flaky XPASS would red the required check and block ALL merges) is preserved as a **narrow, declared escape hatch**, not a blanket weakening: append `  # flaky` to a single line in `inf014_quarantine.txt` and the parser (`_parse_quarantine`) reverts THAT entry to strict=False. Flakiness is declared in the data, so the deterministic majority stays self-cleaning while a genuinely non-deterministic test is explicitly exempt. **Safe to flip with zero pruning:** a full CI-parity unit run (redis up, masking keys emptied per the LESSON above) reported **2882 passed / 183 xfailed / 0 XPASS** — no quarantined test currently passes, so the flip ships green and the list will only shrink as ③ lands. The mechanism is self-verifying: `tests/test_inf014_quarantine.py` pins both the strict-by-default rule and the `# flaky` exemption, so a future edit can't silently weaken either. (First-activation note: local-vs-CI platform drift could in theory surface a CI-only XPASS the local run missed; if so the required job goes red on that exact test and the one-line prune is the mechanism working as intended, not a regression.)

**✅ FIXED 2026-06-10 — hardware-fragile `test_timeout_at_60_seconds` benchmark de-flaked (the "Minor" follow-up).** `tests/benchmarks/test_bbox_linking_performance.py::TestTimeout::test_timeout_at_60_seconds` raced a real `0.001s` wall-clock deadline against iteration speed: on a fast host the 2,000 trivial bbox iterations finished in under a millisecond, no `TimeoutError` fired, and `pytest.raises` failed (a false red on the required `test` job, since CI runs benchmarks — there is no `-m "not benchmark"` filter). Fix: `MockBboxLinker` now takes an injectable `clock` (defaulting to the real `time.perf_counter`, so the other 11 benchmarks are unchanged); the timeout test drives it with a fake clock advancing a fixed `0.1s` per tick, so a `1.0s` deadline trips on exactly the 11th tick = 10 bboxes processed, **on every machine**. Asserts the deterministic partial-progress message (`Processed 10/2000`). No wall-clock dependence remains.

**Bugs UNCOVERED during ② (each is a test that *would* have caught a real problem):**

1. **PROD BUG — 4 summary endpoints 500 on every call** (`verify_summary_section`, `add_summary_note`, `save_section_edit`, `regenerate_section` in `app/api/routes/summary.py`). Each declares its rate-limiter param as `http_request` but ALSO has a body param named `request`. slowapi (`extension.py:709`) finds its Request param **by the literal name `"request"`**, grabs the body model, fails `isinstance(_, starlette.Request)`, and raises → HTTP 500. Verified by replicating FastAPI's all-kwargs call convention. **FIXED in PR #64 (merged to master + deployed to API and worker 2026-06-04):** renamed the limiter param to `request` and the body param to `payload` (+ updated body refs) in all 4 handlers, un-quarantined their 7 tests, and added a **structural guard** (`tests/api/test_rate_limit_request_param.py`) asserting every `Request`-typed route param is named `request` app-wide — converting the slowapi naming requirement from an ARCH-003 "remember to name it right" convention into a build-breaking invariant (`summary.py` was the only offender). Pre-activation safety (hostile-review M2 — this write path had NEVER run in prod, it 500'd before reaching the services): queried the live DB and confirmed `summary_verifications`/`summary_notes` exist, the upsert `on_conflict` matches the UNIQUE constraint, and `section_type`/`decision` enum labels match the app `.value` strings byte-for-byte. Post-deploy verification: all 4 endpoints now return **401** (auth) instead of **500** in production. (The `get_matter_summary` Shape-A test-harness failures stay quarantined for ③ — they were never the prod bug.)

2. **LATENT PROD FRAGILITY — DB-backed pricing silently zeroes all LLM cost.** `app/core/pricing_loader.py`: `initialize_pricing()` runs at app startup; if `load_pricing_from_db()` returns an **empty-but-non-None** dict, `get_provider_pricing()` returns it as authoritative and `get_pricing()` falls to the **zero-cost default** for every model → all LLM cost computes as **$0**, process-wide, with no error. Triggered in tests by a MagicMock client (iterates as empty); triggerable in PROD if the `llm_pricing` table is empty or the query returns `[]`. Recommend: treat empty as a load FAILURE (fall back to hardcoded `PROVIDER_PRICING`) rather than caching `{}` as truth.

3. **STALE TESTS mislabeled as "flaky state pollution".** The worker cluster (`test_engine_tasks_anomaly_trigger` 11, `test_maintenance_tasks` 3, `test_timeline_phase1_fixes` 1) was recorded in ① as Shape-A order-dependent pollution the wall would fix. **It is not** — it fails **deterministically in isolation** (Shape-B mock/contract drift, e.g. `sync_citation_statuses_with_resolutions` returns `citations_updated=0` because the mock query chain no longer matches the code). Stays quarantined for ③. Note: `sync_citation_statuses` is RISK-1's citation-verification authority, so its stale tests are a real blind spot. The genuine state-pollution cluster was `test_chunking_logging` (fixed by the wall).

4. **STALE TESTS — summary `get_matter_summary` group (Shape B).** Tests mock `get_summary`; the endpoint now calls `get_cached_summary` + a job-dispatch flow. Side effect: `test_service_error_returns_500` / `test_openai_not_configured_returns_503` can no longer distinguish error codes (all paths funnel to `INTERNAL_ERROR`). For ③.

5. **TEST BUG + CI BLIND SPOT — Document AI never exercised in CI.** `OCRProcessor(project_id="")` does `project_id or settings.google_cloud_project_id`, so an empty arg falls through to settings. `test_raises_configuration_error_when_not_configured` only passes because CI has **no** `GOOGLE_CLOUD_PROJECT_ID` (hits the unconfigured branch); locally with a real `.env` it makes a live gRPC call and fails. Implication: the **configured** Document AI path has zero CI coverage.

**Further findings 2026-06-04 (investigated the GEMINI_API_KEY-placeholder idea; do NOT adopt it as-is):**

6. **BROKEN MOCKS — 3 "mocked-Gemini" tests make REAL Gemini API calls.** `test_event_classifier.py::TestClassificationWithMockedGemini::{test_classify_with_mocked_gemini, test_batch_classify_with_mocked_gemini}` and `test_date_extractor.py::TestDateExtractorExtraction::test_extract_with_mocked_gemini` set `classifier._model = MagicMock(...)`, but the production code resolves the client through the `model` **property**, which re-creates a **real** genai client — so the mock never intercepts. Proof: with `GEMINI_API_KEY=placeholder` they fail with a live `400 INVALID_ARGUMENT … API_KEY_INVALID` from `generativelanguage.googleapis.com`. They only "passed locally" because a dev `.env` supplies a **real** key and the real call returns a real classification. **They must NOT be un-quarantined until the mock targets the actual call path** (mock the `model` property / `generate_content_async` on the real attribute) — otherwise they need a live, billable Gemini call in CI. This SUPERSEDES the "just add `GEMINI_API_KEY: placeholder`" idea floated in the LESSON above: a placeholder greens only the (weak) `test_network_timeout_handling` and would make CI fire real failing calls for these broken-mock tests. **Update (PR #65, 2026-06-09):** with the hardened wall (#7) these now raise the wall's `RuntimeError` — fast and **offline** — instead of a real billable `400`, so they're no longer a network/cost hazard. They remain BROKEN MOCKS and stay quarantined for ③ until the mock targets the real call path. (The Gemini calls go over **aiohttp**, not grpc — see #7's correction.) For ③.

7. **WALL GAP — the conftest network block was httpx-only — FIXED in PR #65 (merged 2026-06-09).** `tests/conftest.py::_block_external_network` patched only `httpx.HTTPTransport`/`AsyncHTTPTransport`, so finding #6's real calls reached Google *despite* the wall, and the Document AI test (#5) did too. **Correction to the original wording here:** the leak is NOT "google-genai (grpc)" — empirical probing (2026-06-09) showed it's **two different transports**: google-genai's **async** path uses **aiohttp** (NOT httpx — this is the actual #6 leak), while **grpc** is google-cloud-documentai (Document AI). grpc does its socket I/O in C, *below* Python's `socket` module, so no socket patch can catch it — only blocking channel creation. **Fix (#65):** the wall now blocks each transport family at its single chokepoint — httpx (existing) + `aiohttp.ClientSession._request` + `grpc[.aio]` channel factories + a `socket.socket.connect` backstop for requests/urllib/raw (loopback ALLOWED so the test Redis/Celery broker still works). `tests/test_network_wall.py` (6 tests) asserts each layer holds, so the wall is self-verifying. A session-scoped pre-warm of tiktoken's `cl100k_base`/`p50k_base` vocab (before the wall) keeps the chunking tests offline — the wall had exposed that they silently downloaded the vocab from the net on every cold CI run. Net effect: finding #6's broken-mock tests now fail **fast and offline** (caught by the wall) instead of via real, billable, flaky calls.

8. **WEAK TEST — `test_network_timeout_handling` can't fail for the right reason.** It asserts `event_type == UNCLASSIFIED` after a mocked `TimeoutError`, but the classifier funnels *any* error (including the real `API_KEY_INVALID` from #6) to `UNCLASSIFIED`. So it passes whether or not its mock works, and whether or not a real call happens. Low diagnostic value; revisit with #6/#7. For ③.

#### CI-INTEGRITY note (2026-06-04, in response to a direct owner question)

Honest scope of what the green `test` check means today — NOT "all tests pass":

- **190 unit tests are suppressed** (xfail). They gate nothing. If the code they cover regresses, CI stays green. Green = "the ~2872 non-quarantined unit tests still pass + known-broken ones are tracked."
- **`tests/integration/*` is excluded entirely** (`--ignore`). No integration coverage in CI at all. A dedicated integration job with real creds is an un-started follow-up.
- **Placeholder credentials.** No real Supabase / LLM / GCP. So real DB CHECK-constraint/enum mismatches (cf. the `section_not_found` incident), real Document AI, and real LLM behavior are **not exercised**. Bugs of that class cannot be caught here.
- **No coverage threshold gate** — `--cov` reports but does not fail on low coverage.
- **We have NOT** deleted tests or weakened assertions to manufacture green. ② specifically REFUSED to: it left the Shape-B `get_matter_summary` group quarantined, refused to fake the 4 prod-bug endpoints green, and REMOVED an autouse Supabase mock once it was found to fabricate empty-but-successful query results (which silently zeroed LLM cost). Removals were earned by real fixes, verified to pass for the right reason.
- **The standing risk** is the `strict=False` quarantine: it is comfortable green now in exchange for a promise (③) to fix 186 tests. If that promise isn't kept, the green badge permanently overstates health. The mitigation is to actually run ③ and to keep the list strictly shrinking.

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

*Note: DPP-010 (RESOLVED) counted under DPP Fixed. UX-004 counted as Partially Fixed (core fixed, feature gap open). WPS-001 counted as Fixed (all 5 layers fixed). INF-011 (MITIGATED) in its own column.*

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
| E2E-004 | OPEN | INVESTIGATED (2026-05-14) | Shadow tested 3 prompts. Model ceiling found. Metadata deployed. Decision deferred. |
| E2E-005 | OPEN | INVESTIGATED (2026-05-14) | 93.9% GPT-4o waste confirmed. Prompt tuning saves 30% but loses 23% contradictions. Decision deferred. |
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
> **Live instance (2026-06-01):** Nirav Jobalia affidavit `completed` while contradiction job FAILED (`CONTRADICTION_FAILED`) — see "Static×Live Cross-Validation Audit (2026-06-01)" in §0.
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

**Fix**: Add logging/status update so admin dashboard can surface library document failures. Low priority. Related: GAP-17 (status-update-on-failure silently swallowed when DB is down).

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
| **Status** | IN PROGRESS — re-fetch triggered, 6/8 acts processing (2026-05-14) |
| **Source** | E2E verification (2026-04-17) |

**Root cause** (identified 2026-05-14): The Jan 23 batch was bulk-seeded data (7 rows at identical microsecond timestamp, `added_by=NULL`), not pipeline-created. Storage paths pointed to files that were never durably stored. Not a pipeline bug — later pipeline-created docs work fine (proved by `TORTS Act 1992` and `Special Court` completions).

**Data cleanup** (2026-05-14): 12 failed `library_documents` deleted, 9 `act_validation_cache` entries reset (`cached_storage_path=NULL`). Beat task `process_pending_validations` re-fetched 6 acts from India Code at 06:00 UTC: Code of Civil Procedure 1908, Constitution of India 1950, Companies Act 2013, Indian Contract Act 1872, Income Tax Act 1961, Arbitration and Conciliation Act 1996. All set to `processing` status.

**Complication 1 — Supabase outage** (06:00-06:45 UTC): Re-fetch coincided with Supabase ap-southeast-1 scheduled maintenance (522 errors). OCR tasks hit `Server disconnected` errors, exhausted max retries (2), status-update-to-FAILED also failed silently (GAP-17). All 6 stuck at `processing`.

**Complication 2 — recovery sweep dead code** (GAP-18): `resume_stuck_pipelines` had an early return at line 1185 that skipped the library_documents check. Library recovery was dead code. **Fixed 2026-05-14** — removed early return. Verified: sweep at 08:25 UTC found and dispatched 4 library docs.

**Complication 3 — OCR tasks silently dying** (GAP-19): After the sweep fix, 6 OCR tasks dispatched but all silently died. Root cause: large PDFs (Constitution = 400+ pages, Income Tax = 900+ pages) hit the global 60-min Celery task_time_limit. Document AI gRPC calls block the gevent greenlet — SIGTERM can't interrupt, SIGKILL fires with no error logged. Tasks vanish.

**Complication 4 — Upstash Redis 100MB limit** (GAP-20): After GAP-19 fix deployed, pypdf extraction succeeded (all page counts populated) but chunking tasks never executed. Root cause: the Celery chain serialized 1-3MB extracted text through Redis, exceeding Upstash's 100MB per-key limit. Fix: inline chunking (keep text in memory, don't serialize through Redis).

**RESOLVED** (2026-05-14 12:23 UTC): All fixes deployed and verified. Recovery sweep fired at 12:22 UTC, pypdf extracted text for all 8 docs, inline chunking produced 5,031 chunks with 466 section titles (GAP-10 verified). Embedding in progress — 4/8 docs already completed (Indian Contract Act 134ch, Arbitration Act 129ch, BNS 56ch, TORTS Copy 17ch). Remaining 4 (Income Tax 2422ch, Companies 879ch, CPC 739ch, Constitution 622ch) embedding at ~50 chunks/min. Total: 89→5,031 chunks, 33→1,686+ embeddings, 0→466 section titles.

**Remaining**: 2 acts still `pending`. 1 act (`presidency_towns_insolvency_act_1909`) has `validation_status=unknown`, won't auto-fetch.

---

### E2E-004: Contradiction detection is the pipeline bottleneck
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — performance, not correctness |
| **Status** | INVESTIGATED (2026-05-14) — prompt tuning hit model ceiling; metadata deployed for ongoing ground truth |
| **Source** | E2E verification (2026-04-17) |

**Observation**: Contradiction detection consumed 40-70% of total processing time:
- Doc 1 (16p, 26 entities): ~5 min of 16 min total
- Doc 3 (54p, 50 entities): 683s (11.4 min) of 22.8 min total — 317 pairs compared
- Doc 4 (25p, 44 entities): ~8 min of 18.6 min total — 204 pairs compared

The stage is O(n²) on entity count and makes individual LLM calls for each pair. Most entities with `screening_confidence=0.8-0.9` escalate from Gemini Flash to GPT-4o, adding ~$0.007/pair.

**Investigation results (2026-05-14)**: Shadow tested 3 prompt variants against 181 pairs. No prompt achieves both >90% catch rate AND <40% escalation rate. The bottleneck is Gemini Flash's inability to distinguish subtle legal contradictions from complementary legal reasoning — a model capability limit, not a prompt issue. See Cluster 3 entry for full data.

**Possible optimizations** (updated 2026-05-14):
1. ~~**Raise escalation threshold**~~ — DEAD END. Gemini returns discrete values {0.0, 0.8, 0.9, 0.95, 1.0}. Threshold between 0.0 and 0.8 catches nothing.
2. ~~**Batch screening calls**~~ — REJECTED. Context bleed on same-entity pairs.
3. **Skip low-mention entities** — already exists at two layers (no code needed)
4. **Parallelize entity comparisons** — currently sequential within the task
5. **Cap pairs per entity** — already capped at 25 but some entities hit this ceiling
6. **Prompt tuning** — INVESTIGATED, hit model ceiling. Best candidate (V3) saves 30% calls but misses 23% of contradictions. All misses are medium-severity semantic contradictions, not factual ones. Decision deferred.
7. **Model swap (Phase 4)** — replace GPT-4o with cheaper model. Unproven, needs shadow test with new model. The 10x cost lever if quality holds.

---

### E2E-005: Excessive GPT-4o escalation in contradiction screening
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low) — cost optimization |
| **Status** | INVESTIGATED (2026-05-14) — 93.9% GPT-4o waste confirmed with data. Metadata deployed. Prompt tuning hit ceiling. |
| **Source** | E2E verification (2026-04-17) |

**Observation**: Almost every entity comparison with `screening_confidence=0.8-0.9` from Gemini Flash escalates to GPT-4o for confirmation. Most escalations result in "consistent" or "unrelated" — the GPT-4o call was wasted. Total contradiction detection costs: $0.33 + $0.87 + $1.48 + $1.26 = **$3.94 for 4 documents**.

**Production data (2026-05-14, 804 pairs with metadata)**:
- 93.9% of GPT-4o calls return non-contradiction (444/473 wasted)
- Only 29 real contradictions found from 804 screenings (3.6% yield)
- Monthly cost at current volume: ~$6.40/month ($2.96 screening + $3.34 comparison)
- Wasted GPT-4o spend: ~$2.78/batch

**What was tried**: 3 prompt variants shadow-tested. Best candidate (V3) reduces escalation from 65% to 45% but misses 7 of 31 known contradictions. None of the 3 are safe to deploy — see Cluster 3 for full data.

**What was deployed**: GPT-4o comparison outcomes now persisted in `llm_costs.metadata` (2026-05-14). Every new comparison stores `{comparison_result, confidence, reasoning_preview}`. This builds the ground truth needed for any future optimization.

**Fix**: Decision deferred. Options: (a) accept V1 status quo at $6.40/month, (b) deploy V3 with known debt (4 missed interpretive contradictions), (c) Phase 4 model swap (unproven). See Cluster 3 for full analysis.

---

### E2E-006: Redis beat scheduler lock extension warning (ARCH-002 instance)
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) — upgraded: kills all 16 periodic tasks silently |
| **Status** | FIXED (2026-05-13) — resolved by INF-010 fix |
| **Source** | E2E verification (2026-04-17) |
| **Arch pattern** | ARCH-002 (P3 — routing without process isolation) |

**Observation**: `Cannot extend a lock that's no longer owned` warning from RedBeat scheduler's Redis lock (`redbeat_lock_timeout=300`). Causes Railway to hit 500 logs/sec rate limit and drop messages (43 dropped in one burst). Related to INF-010.

**Fix Applied (2026-05-13)**: RedBeat removed entirely (see INF-010). No more Redis lock = no more `LockNotOwnedError` = no more log spam. Beat uses Celery's default `PersistentScheduler` which has no distributed locking mechanism. Beat still shares the worker container but now self-heals via restart loop if it crashes for any reason.

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

---

## 10. Frontend Audit Findings (2026-05-20)

> Symptoms surfaced by a Playwright-driven frontend audit on 2026-05-20. Evidence (screenshots, viewport measurements, console captures, repro steps, suggested fixes) lives in `FRONTEND-AUDIT-2026-05-20.md`. Architectural root causes are tracked as **FE-ARCH-01..04** in §0 above. Each row's **Parent** column points at the FE-ARCH-NN debt the symptom is generated by — closing that debt is the durable fix.

| ID | Sev | Status | Title | Parent |
|----|-----|--------|-------|--------|
| **FE-001** | P1 | OPEN | "Ask jaanch" panel never collapses on mobile (matter workspace unusable on phones) | FE-ARCH-02 |
| **FE-002** | P1 | OPEN | Matter header buttons (Export, More) clipped off-screen at 390 | FE-ARCH-02 |
| **FE-003** | P1 | OPEN | Invalid matter URL renders broken "Untitled Matter" shell with 18 console errors | FE-ARCH-01 |
| **FE-004** | P2 | OPEN | Dashboard horizontal scroll at 320 + truncated stat labels ("Active Ma…", "Veri…") | FE-ARCH-02 |
| **FE-005** | P2 | OPEN | Matter "Documents" tab label cut off on mobile | FE-ARCH-02 |
| **FE-006** | P2 | OPEN | Verification table 1470px wide inside a squeezed mobile column | FE-ARCH-02 (compounds with FE-001) |
| **FE-007** | P2 | OPEN | Dashboard shows "Ready" for a matter whose only document failed processing | FE-ARCH-01 |
| **FE-008** | P2 | OPEN | Search snippets polluted with matter name repeated 2–3× | — |
| **FE-009** | P2 | OPEN | Search returns the same document page multiple times (no dedup) | — |
| **FE-010** | P2 | OPEN | No custom 404 page — bare Next.js default | FE-ARCH-01 |
| **FE-011** | P2 | OPEN | "Generating Summary / Waiting in queue" spinner stuck for 20+ days | FE-ARCH-01 |
| **FE-022** | P2 | OPEN | Page content shifts/re-centers during load (CLS 0.1138, intermittent — 503+retry triggered) | FE-ARCH-02, FE-ARCH-03 |
| **FE-012** | P3 | OPEN | `touch` endpoint console warning on every matter open (`.json()` on empty body) | — |
| **FE-013** | P3 | OPEN | Search result duplicates matter name (title = subtitle) | FE-ARCH-04 |
| **FE-014** | P3 | OPEN | Generic "Document (Page N)" search labels (no filename in title) | — |
| **FE-015** | P3 | OPEN | Pluralization not handled ("1 documents", "1 citations", "1 pages") | FE-ARCH-04 |
| **FE-016** | P3 | OPEN | Inconsistent date formats — 7 distinct formats live simultaneously | FE-ARCH-04 |
| **FE-017** | P3 | OPEN | Inconsistent matter-card metric ("3 documents" vs "0 pages") | FE-ARCH-04 |
| **FE-018** | P3 | OPEN | "items need attention" count differs across views (23 vs 22) | FE-ARCH-04 |
| **FE-019** | P3 | OPEN | Internal/technical controls exposed to end users (Embedding model dropdown, "1 worker") | — |
| **FE-020** | P3 | OPEN | `href="#"` on source/citation links (middle-click produces dead tabs) | — |
| **FE-021** | P3 | OPEN | Redundant filename shown twice in document viewer toolbar | — |
| **FE-025** | P2 | OPEN | Citations UI shows "pending · available" while DB status is `act_unavailable` during the verify window — status vocabulary diverges from backend enum, misleads on a mid-window glance (E2E#3, 2026-06-10) | FE-ARCH-01 |
| **FE-026** | P3 | OPEN | Summary loading skeletons misaligned after the upload→matter auto-redirect (stray bar + mismatched cards → visible shift when data lands) (E2E#3, user-flagged) | FE-ARCH-03, FE-022 |
| **FE-027** | P3 | OPEN | Section+subsection rendered with a literal dot: "Section 205A.(8)" (E2E#3) | FE-ARCH-04 |
| **PROD-INF-1** | P3 | OPEN | `recover_stuck_document` + `finalize_chunked_document` (`has_chunk_results=False`) fire for a doc that processes & completes normally — recovery sweep firing on a healthy in-flight doc; watch for double-processing (E2E#3, 2026-06-10) | — |

> E2E #3 (2026-06-10) full-stack observation — frontend/Railway/DB — recorded in `docs/PROD-FINDINGS-2026-06-10.md`. Confirms GAP-28 L2 end-to-end (faithful `205A`/`205C` in DB + UI, 14/14 `section_not_found`, 0 errors); the FE-025/026/027 + PROD-INF-1 rows above are the non-blocking findings it surfaced. FE-012 (touch console warning) re-confirmed reproducing.

**PROD-004 (P2): background readers don't respect the matter soft-delete window — "zombie" reads** | Status: PART B FIXED+DEPLOYED+VERIFIED 2026-06-10 (commit 0c46f77; LDIP 51120d03 + ldip-worker 003d1519 both SUCCESS; /health/invariants live clean, counts unchanged, 0 deleted-matter ids in samples). **Part A SHIPPED 2026-06-10 with PROD-005** (delete_matter stamps documents).
- **Symptom (original).** Deleting matters sets `matters.deleted_at`; the confirm dialog promises *"This will delete all documents, citations, and timeline events…"* but documents keep `deleted_at=NULL` and citations stay live. Live at discovery: 3 deleted matters → 3 live docs, 36 live citations (29 `section_not_found` + 7 `act_unavailable`, **0 verified**).
- **REFRAME (blast-radius + live DB, 2026-06-10).** This is NOT a missing-cascade bug. **Every** child table has `ON DELETE CASCADE` from `matters` (verified live; only `audit_logs`/`llm_costs` are `SET NULL` by design), and `hard_delete_expired_matters` fires that CASCADE after 30 days. So the model is a deliberate **30-day trash window** (no restore endpoint exists), and the data is *supposed* to live until then. The real defect: **background readers keyed on `matter_id` don't exclude soft-deleted matters during that window.** Downgraded P1→P2: the two `verified_*` watchmen gate on `verification_status='verified'` and there are **0** such rows under deleted matters, so they were NOT actually over-counting (my earlier "over-count by 36" claim was wrong on the live numbers); the matter also leaves the user's list on delete, so the docs/citations are unreachable in the UI and the promise is effectively honored there.
- **Active harm.** The RISK-1 reconciler (`sync_citation_statuses_with_resolutions`) and the 3 watchman invariants iterate per-matter without a liveness gate → reconciler could re-dispatch verification for deleted matters (Gemini waste + status churn); watchmen would over-count the moment any deleted-matter citation flips to `verified`. Preventative more than active (resolutions-now-skipped = 0 at fix time).
- **Shape.** Two divergent delete semantics (GAP-8 parallel paths): document soft-delete hard-cascades children (`document_service.py:751`); matter soft-delete is flag-only. And the read side is the ARCH-003 "remember to filter deleted matters" variant — ~4 background readers honor nothing (citations have no `deleted_at`/`status` column to filter at all).
- **FIX — Part B (the load-bearing, dangerous-shape half) — SHIPPED.** New single shared `get_deleted_matter_ids(client)` in `app/services/act_verification_state.py` (the module whose charter is "one definition shared by reconciler + auditor, to avoid ARCH-001"). Liveness is now **derived from observed DB state** (the ARCH-003 *allowed* alternative), fail-open (error → empty set, never excludes a live matter). Applied at 4 readers: the reconciler (skips deleted matters when building `matters_map`), `_check_acts_resolved_embedded_zero_verified` (skips at `by_matter` build), and `_check_verified_citation_vintage_mismatch` + `_check_verified_section_token_mismatch` (skip per-citation by `matter_id`). Verified live: helper returns the 3 deleted matters; `import app` clean. **Deploy: both LDIP + ldip-worker.**
- **Part A (stamp the matter's documents on delete) — SHIPPED 2026-06-10 (with PROD-005).** `matter_service.delete_matter` now stamps the matter's documents `deleted_at`+`status='deleted'` (the `soft_delete_document` convention) at the single chokepoint, ordered AFTER the authoritative matter soft-delete, best-effort (transient failure → pre-PROD-004 baseline, never stamps docs for a live matter). Flag-only — DB CASCADE reclaims children at the 30d hard-delete.
- **Guard (honest).** Documents: liveness derived by the existing `deleted_at` filter (structural). Citations: no lint-level guard stops a *future* background citation-reader from forgetting the helper — mitigation is the helper being the single obvious named tool in the shared module + this entry. (A "no deleted-matter citation re-dispatched" watchman would be checking-the-checker — deferred.)

**PROD-005 (P2): `soft_delete_document` writes `status='deleted'`, REJECTED by the live CHECK constraint → single-document delete 500s** | Status: FIXED 2026-06-10 (migration applied to live + write path verified; code committed). Deploy: both LDIP + ldip-worker.
- **Evidence.** `documents_status_check` allowed only `{pending, processing, ocr_complete, ocr_failed, pending_review, chunking, chunking_failed, embedding, embedding_failed, searchable, completed, failed}` — **no `'deleted'`**. `document_service.soft_delete_document` (`document_service.py:663-677`) updates `{deleted_at, status:'deleted'}` atomically → Postgres rejected with 23514 → the generic `except` re-raised as `DocumentServiceError` (500). The cascade hard-delete runs *after* the update, so it never fired (citations/chunks preserved, no data loss — but the document was NOT deleted). Live: **0 documents** had `status='deleted'` or `deleted_at` set, consistent with the write never succeeding.
- **Root cause (blast-radius Phase 1).** The whole codebase already ASSUMED `'deleted'` was valid — `DocumentStatus.DELETED` enum (`models/document.py:70`), `soft_delete_document`, `maintenance_tasks._TERMINAL_STATUSES`, and the `20260416 backfill_deleted_status` migration. But **no migration ever altered the CHECK constraint** to allow it (the 20260416 backfill matched 0 rows since no doc ever reached `deleted_at`, so the gap stayed invisible). The `20260220 add_auto_fetching_status` migration was a red herring — it targets `act_resolutions`, not `documents`.
- **FIX — SHIPPED.** (1) Additive migration `20260610000001_add_deleted_to_documents_status_check.sql` — applied to live Supabase, verified `pg_get_constraintdef` now lists `'deleted'`; reversible. (2) Write path proven live via a `BEGIN; UPDATE … status='deleted' …; ROLLBACK;` (succeeded where it previously raised 23514; rolled back → 0 rows persisted). (3) Folded in **PROD-004 Part A** (see above). (4) **Activation guard** (hostile-review M2): `dispatch_stuck_queued_jobs` (`maintenance_tasks.py:348`) now closes out stuck QUEUED jobs for `status in ('completed','deleted')` instead of only `'completed'` — Part A can leave a QUEUED job whose doc is now `'deleted'` (flag-only, job not cascaded until 30d), and re-dispatching it would re-process a deleted matter's doc (Gemini cost + status churn). `resume_stuck_pipelines` was already safe (filters `_TERMINAL_STATUSES` ⊇ `'deleted'` + `deleted_at IS NULL`).
- **Deferred (tracked).** Frontend `DocumentStatus` union + `STATUS_LABELS`/color arrays (`frontend/src/types/document.ts`, `DocumentList.tsx`) lack `'deleted'` — **unreachable via UI**: every document-list endpoint filters `deleted_at IS NULL`, so a `'deleted'` doc never reaches the list. Only a direct detail fetch of a deleted doc could surface it (post-delete the user has navigated away). Low; fold into a frontend pass. Related: feedback-soft-delete-status memory, INF-009, GAP-8.

**Coverage gaps from this audit** (also in `FRONTEND-AUDIT-2026-05-20.md` §8): logged-out landing page not audited (would have required logging out); upload end-to-end not exercised (no file submitted, avoided throwaway matter); auth flows, settings/usage, dark mode, Firefox/Safari/iOS, real devices, network throttling all uncovered.

---

## 10. Production Findings (2026-05-25 live testing session)

> Found during live testing of GAP-9/11/17/UX-015 fixes. These are pre-existing issues, not regressions from this session's changes.

### PROD-001: `identity_nodes.document_id` column does not exist
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low — logged warning, doesn't block operation) |
| **Status** | OPEN |
| **Date Found** | 2026-05-25 |
| **Source** | Railway API logs during "Set as Act" promotion |

**Error**: `document_features_check_failed: column identity_nodes.document_id does not exist` (code 42703). Fires during `PATCH /documents/{id}` when changing type to act. The feature-check query references `identity_nodes.document_id` which doesn't exist in the live schema.
**Impact**: Warning logged, promotion completes successfully. The feature check fails silently — document still promoted, library linked.
**Fix**: Find the query in `documents.py` that references `identity_nodes.document_id` and update to the correct column name (likely `entity_mentions.document_id` or similar).

### PROD-002: `act_resolutions.act_document_id` FK orphan
| Field | Value |
|-------|-------|
| **Severity** | P3 (Low — maintenance task handles it, logs warning) |
| **Status** | OPEN |
| **Date Found** | 2026-05-25 |
| **Source** | Railway worker logs, `sync_act_resolutions_with_documents` task |

**Error**: `insert or update on table "act_resolutions" violates foreign key constraint "act_resolutions_act_document_id_fkey"`. Key `(act_document_id)=(c01a7910-67c9-463a-99b2-cfe1354baa11)` is not present in `library_documents`. Fires in matter `91a4a4db-bc3d-40df-8dcc-49179ac49108`.
**Root cause**: An `act_resolutions` row references a `library_documents` row that was deleted (likely during the 2026-05-14 cleanup of failed library docs). The sync task tries to update the resolution but the FK prevents it.
**Fix**: Data fix — delete the orphaned `act_resolutions` row, or set `act_document_id=NULL`.

### PROD-003: "Set as Case File" menu item unreachable — promoted acts filtered from document list
| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium — demotion UI is dead code) |
| **Status** | OPEN |
| **Date Found** | 2026-05-25 |
| **Source** | Live testing of GAP-9 Gap 5 fix |

**Description**: "Set as Case File" was added to `DocumentActionMenu.tsx` (2026-05-25) to enable act→case_file demotion via the three-dot menu. The code is correct and deployed. **But the menu item is unreachable**: when a doc is promoted to Act, `migrated_to_library=True` causes the document list query to filter it out (`document_service.py:311`). The row disappears from the table, so the three-dot menu can never be opened on an act document.
**Root cause**: The `migrated_to_library` filter is correct for normal document list behavior — promoted acts should appear in the Linked Library panel, not the document list. But this makes ALL document-list actions (including type change, rename, delete, and the new "Set as Case File") unreachable for promoted docs.
**Fix options**: (1) Add a "Show promoted" toggle/filter to the document list. (2) Add demotion action to `LinkedLibraryPanel` where promoted docs DO appear. (3) Show promoted acts in document list with a visual badge but keep them in both panels. Option 2 is simplest — the panel already shows each linked doc with an unlink button.
**Workaround**: The inline type dropdown can catch the doc in the brief window between API response and list refresh. Bulk select can also work if the user is fast enough. Neither is a real UX path.
