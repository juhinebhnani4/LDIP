# Contradiction Engine — Architecture Analysis & Long-Term Plan

> **Date:** 2026-02-06
> **Status:** Investigation complete — no critical bugs found; engine is the most mature of the three

---

## Part 1: Current Architecture

### Pipeline Overview

The contradiction engine detects conflicting statements about the same entity across documents. It uses a **4-stage pipeline**:

```
Stage 1: Statement Query (Story 5-1)
    → Retrieves all chunks mentioning an entity (+ aliases)
    → Groups by document source
    → Extracts dates/amounts from text
    ↓
Stage 2: Pairwise Comparison (Story 5-2)
    → Two-tier LLM routing: Gemini Flash screening → GPT-4 escalation
    → Gemini screens at ~$0.0001/comparison
    → Escalates "contradiction"/"uncertain" OR confidence < 0.85 to GPT-4 (~$0.025/comparison)
    → 60-80% cost savings vs GPT-4-only
    ↓
Stage 3: Classification (Story 5-3)
    → Types: date_mismatch, amount_mismatch, factual, semantic
    → Evidence extraction (value_a vs value_b)
    ↓
Stage 4: Severity Scoring (Story 5-4)
    → 100% rule-based (no LLM cost)
    → HIGH / MEDIUM / LOW based on contradiction type + confidence
    → High confidence threshold: 0.8, Low: 0.6
```

### Key Files

| File | Purpose | Story |
|------|---------|-------|
| `backend/app/engines/contradiction/statement_query.py` | Entity-grouped statement retrieval | 5-1 |
| `backend/app/engines/contradiction/comparator.py` | Two-tier Gemini/GPT-4 comparison | 5-2 |
| `backend/app/engines/contradiction/classifier.py` | Contradiction type classification | 5-3 |
| `backend/app/engines/contradiction/scorer.py` | Rule-based severity scoring | 5-4 |
| `backend/app/engines/contradiction/prompts.py` | System prompts + validation schemas | — |
| `backend/app/workers/tasks/document_tasks.py:5302-5581` | `detect_contradictions` Celery task | — |
| `backend/app/api/routes/contradiction.py` | 3 API endpoints | 14-2 |
| `backend/app/services/contradiction_list_service.py` | List/filter/paginate contradictions | — |

### API Endpoints

1. **GET** `/api/matters/{matter_id}/contradictions` — List all contradictions, grouped by entity. Filters: severity, type, entity, document. Pagination (default 20, max 100).
2. **GET** `/api/matters/{matter_id}/contradictions/entities/{entity_id}/statements` — Statements about an entity, grouped by document.
3. **POST** `/api/matters/{matter_id}/contradictions/entities/{entity_id}/compare` — Compare statement pairs. Max 200 pairs. Returns 422 if >100 statements (no async batch processing).

### Database: `statement_comparisons` Table

Key columns: `id`, `statement_a_id`, `statement_b_id`, `statement_a/b_content`, `result` (contradiction/consistent/uncertain/unrelated), `reasoning`, `confidence`, `evidence_type`, `evidence_value_a/b`, `document_a/b_id`, `page_a/b`, `entity_id`, `matter_id`, `contradiction_type`, `severity`, `created_at`.

RLS enabled. No explicit SQLAlchemy model — Supabase client used directly.

### Frontend Components

| Component | Purpose |
|-----------|---------|
| `ContradictionsContent.tsx` | Main list/grid view |
| `ContradictionsFilters.tsx` | Severity, type, entity, document filters |
| `ContradictionsPagination.tsx` | Pagination controls |
| `EntityContradictionGroup.tsx` | Groups by entity |
| `ContradictionCard.tsx` | Individual contradiction card |
| `ContradictionsRenderer.tsx` | Export rendering |
| `useContradictions.ts` | Data fetching hook |

### Celery Task Configuration

```
Task: detect_contradictions
Timeout: 6 minutes (hard), 5 minutes (soft warning)
Retries: 3 with exponential backoff (max 300s)
Retry on: ComparisonServiceError
Pipeline position: After citation extraction
Default batch: 5 pairs at a time
Max pairs: 50 (configurable up to 200 via API)
```

### Cost Profile

- ~$2/matter with two-tier routing (60-80% savings vs GPT-4-only)
- Gemini Flash screening: ~$0.0001/comparison
- GPT-4 escalation: ~$0.025/comparison
- Scorer: $0 (rule-based)
- Cost scales with O(n^2) comparisons — 10 statements = 45 pairs, 50 statements = 1,225 pairs

---

## Part 2: What Works Well

The contradiction engine is **the most complete and robust engine** in the system:

1. **All 4 stories complete** (5-1 through 5-4) with **136 passing tests**
2. **Two-tier LLM routing** is well-designed — screens cheap, escalates smart
3. **Scorer is rule-based** — no LLM cost, deterministic, fast
4. **Evidence extraction** captures specific conflicting values (dates, amounts)
5. **Entity alias integration** — comparisons include alias-resolved entity references
6. **Circuit breaker** — protects against LLM outages
7. **Cost tracking** — per-comparison cost recorded and aggregated
8. **Security boundaries** in prompts prevent prompt injection
9. **Frontend complete** — filtering, grouping, pagination, export all working

---

## Part 3: Known Gaps & Issues

### 3.1 No Async Batch Processing (Critical for Scale)

**Problem:** The compare endpoint returns HTTP 422 when >100 statements exist for an entity. The 6-minute task timeout caps processing at ~200 pairs.

**Impact:** Entities with many document mentions (common in complex litigation) can't be fully analyzed.

**Gap reference:** Not explicitly called out in gap analysis but implied by the 422 error handling in `contradiction.py:573-580`.

### 3.2 No Cross-Entity Contradiction Detection (Gap #49)

**Problem:** The engine only compares statements *about the same entity*. It cannot detect when Entity A's statements contradict Entity B's statements about the same event.

**Example:** Document 1 says "Nirav signed on Jan 15", Document 2 says "The company was not represented until Feb 1" — these contradict each other but involve different entities.

**Gap reference:** First-principles gap analysis #49, Epic 8 FR8.1.

### 3.3 No Cross-Engine Correlation (Gap #15)

**Problem:** Timeline events are not linked to contradictions. A user viewing a timeline event has no visibility into whether the parties/dates involved have known contradictions.

**Gap reference:** First-principles gap analysis #15, Epic 5 Story 5.3 (FR4.3).

### 3.4 No Exhaustive Contradiction Mode (Gap #23)

**Problem:** Current mode uses sampling (max 50-200 pairs). No option to run exhaustive all-pairs comparison for critical matters where completeness matters more than cost.

**Gap reference:** First-principles gap analysis #23, Backlog FR-BL3.

### 3.5 No Verification/Resolution Workflow

**Problem:** Detected contradictions have no attorney verification workflow. No way to mark a contradiction as "verified", "false positive", or "resolved". No feedback loop to improve detection.

**Partially addressed:** The Verification Tab has generic verify/reject for findings, but no contradiction-specific resolution (e.g., "resolved because Document B supersedes Document A").

### 3.6 Dedicated Contradictions Tab Deferred

**Problem:** Contradictions appear inside the Verification Tab filtered by type. The full dedicated tab with entity grouping, side-by-side comparison view, and severity-based filtering was deferred to Phase 2.

**Gap reference:** Phase-2-Backlog.md (Stories CT-1 through CT-4, estimated 2-3 weeks).

---

## Part 4: Future Phases — Pending Work

### From Phase-2 Backlog (Deferred from MVP)

| Story | Description | Effort |
|-------|-------------|--------|
| CT-1 | Dedicated Contradictions Tab | ~1 week |
| CT-2 | Entity grouping in dedicated tab | ~3 days |
| CT-3 | Side-by-side comparison view | ~1 week |
| CT-4 | Severity filtering in dedicated tab | ~2 days |

**Total estimated:** 2-3 weeks development.

**What users get in MVP vs what's deferred:**
- MVP: Entity-based detection, findings in Verification Tab, filter by type="Contradiction", verify/reject
- Deferred: Dedicated tab, side-by-side view, entity grouping, contradiction resolution workflow, export as standalone report

### From First-Principles Gap Analysis

| Gap # | Description | Priority Score | Phase |
|--------|-------------|---------------|-------|
| #15 | Cross-engine correlation (Timeline → Contradiction links) | — | Phase 4 |
| #23 | Exhaustive contradiction mode (vs sampling) | — | Backlog |
| #49 | Cross-entity contradiction detection | — | Phase 8 |

### From Epics Gap Remediation

| Reference | Description | Epic |
|-----------|-------------|------|
| FR4.3 | Cross-engine correlation — timeline to contradiction links | Epic 5: Operational Excellence |
| FR4.4 | Cross-engine consistency checking | Epic 5: Operational Excellence |
| FR8.1 | Cross-entity contradiction detection | Epic 8: Intelligence Improvements (optional for MVP) |
| FR-BL3 | Exhaustive contradiction mode | Backlog |

### Story 5.3 — Cross-Engine Correlation Links (from epics-gap-remediation.md)

```
As an associate attorney,
I want timeline events linked to related contradictions and entities,
So that I can see the full context of each event.

Acceptance Criteria:
- Given a timeline event involves "John Smith" on "Jan 15, 2024"
- When I view the event detail
- Then I see links to all contradictions involving John Smith
- And I see the entity's journey (all timeline events for that entity)
```

**Status:** Not started. Blocked by the entity linking issues documented in `entities-engine-and-cross-engine-plan.md`.

---

## Part 5: First-Principles Analysis & Long-Term Recommendations

### Phase 1: Quick Wins (1-2 weeks)

#### 1.1 Async Batch Processing for Large Entity Sets

Replace the synchronous 422 error with a Celery task that processes all pairs in the background:

```python
# In contradiction.py compare endpoint:
if statement_count > 100:
    # Instead of returning 422, queue async job
    task = detect_contradictions_for_entity.delay(
        matter_id=matter_id,
        entity_id=entity_id,
        max_pairs=max_pairs
    )
    return {"status": "processing", "task_id": task.id}
```

Add a polling endpoint or WebSocket notification when complete.

#### 1.2 Contradiction Resolution Metadata

Add columns to `statement_comparisons`:
- `resolution_status` — ENUM: unreviewed, verified, false_positive, resolved
- `resolution_note` — text (attorney explanation)
- `resolved_by` — user UUID
- `resolved_at` — timestamp

Frontend: Add resolve/dismiss actions to ContradictionCard. No LLM cost — pure CRUD.

#### 1.3 Cross-Engine Links (depends on entity linking fix)

Once `entities_involved` is populated in the events table (see `timeline-engine-overhaul-plan.md` Phase 1.3), add a query in `cross_engine_service.py` that joins:
- Timeline events where `entities_involved` contains entity X
- Contradictions where `entity_id` = entity X
- Return both in the entity journey response

### Phase 2: Medium-Term (2-4 weeks)

#### 2.1 Dedicated Contradictions Tab (CT-1 through CT-4)

Implement the deferred Phase-2 stories. The backend API already supports all needed operations — this is primarily frontend work:
- Entity-grouped layout with expandable sections
- Side-by-side document comparison view (highlight contradicting passages)
- Severity-based color coding and filtering
- Resolution workflow UI

#### 2.2 Cross-Entity Contradiction Detection (Gap #49)

**Current:** Only compares statements about Entity A with other statements about Entity A.

**New:** For each event/date, collect all statements from any entity about that event, then compare cross-entity:

```
Event: "Contract signed on Jan 15"
    Entity A says: "Signed on Jan 15, 2024"
    Entity B says: "Company was not involved until Feb 1, 2024"
    → Cross-entity contradiction detected
```

**Implementation:** New `cross_entity_comparator.py` that:
1. Groups statements by event/date (not entity)
2. Compares across entity boundaries
3. Uses the same two-tier routing
4. Stores with `cross_entity: true` flag in `statement_comparisons`

#### 2.3 Exhaustive Mode (Gap #23)

Add a `mode` parameter to the compare endpoint:
- `"sampling"` (default) — current behavior, max 200 pairs
- `"exhaustive"` — all pairs, async only, no limit

For exhaustive mode: chunk into batches of 50 pairs, process via Celery chain, aggregate results. Show progress bar on frontend. Estimated cost: ~$5-15 for 500 statements (12,500 pairs).

### Phase 3: Long-Term (1-3 months)

#### 3.1 Contradiction Chains

Detect chains where A contradicts B, B contradicts C, but A is consistent with C. This reveals "who is the outlier" — critical for legal analysis.

```
Contradiction Graph:
    Doc1 (Jan 15) ←→ Doc2 (Feb 1)    [date contradiction]
    Doc2 (Feb 1)  ←→ Doc3 (Jan 15)   [date contradiction]
    Doc1 (Jan 15) ←→ Doc3 (Jan 15)   [consistent]
    → Doc2 is the outlier
```

#### 3.2 Temporal Contradiction Resolution

Not all contradictions are equal — a later document may *intentionally* supersede an earlier one (e.g., amended filing). Add temporal awareness:
- If Doc B is dated after Doc A and explicitly references Doc A, classify as "supersession" not "contradiction"
- Requires document-date awareness from timeline engine

#### 3.3 Contradiction Impact Scoring

Current scorer uses rule-based severity. Enhance with:
- **Legal materiality:** Does this contradiction affect a key claim or is it peripheral?
- **Frequency:** How many documents support each side?
- **Recency:** More recent statements may carry more weight
- **Source authority:** Court order > affidavit > letter

#### 3.4 Attorney Feedback Loop

Use verified/false-positive labels from Phase 1.2 as training signal:
- Track false positive rate per contradiction type
- Adjust confidence thresholds per matter type
- Use verified contradictions as few-shot examples in prompts
- Goal: reduce false positive rate from ~20% to <5% over time

#### 3.5 Proactive Contradiction Alerts

When a new document is uploaded that contradicts existing verified facts:
- Run contradiction detection immediately after processing
- Push notification: "New document contradicts 3 previously verified facts"
- Highlight in document viewer alongside the contradicting passages

---

## Part 6: Comparison with Other Engines

| Dimension | Timeline Engine | Entities/MIG Engine | Contradiction Engine |
|-----------|----------------|--------------------|--------------------|
| **Stories complete** | Yes (4-1 to 4-3) | Yes (2C.1, 2C.2) | Yes (5-1 to 5-4) |
| **Critical bugs** | 4 (dedup, chunks, threshold, trigger) | 1 (relationships not saved) | 0 |
| **Test coverage** | Moderate | Moderate | High (136 tests) |
| **Cost efficiency** | Moderate (3 LLM calls/chunk) | Good (batch extraction) | Excellent (two-tier routing) |
| **Cross-engine links** | Broken (entities_involved NULL) | Broken (no HAS_ROLE/RELATED_TO edges) | Working but limited by other engines |
| **Long-term readiness** | Needs Phase 2 overhaul | Needs relationship persistence fix | Ready for incremental enhancement |

**Key insight:** The contradiction engine is the most production-ready, but its effectiveness is capped by the other two engines. Once entity linking and timeline events are fixed (see companion docs), contradiction detection will automatically improve because it can leverage richer entity graphs and event timelines.

---

## Part 7: Cost Optimization Opportunities

| Optimization | Current Cost | Projected Cost | Savings |
|-------------|-------------|---------------|---------|
| Two-tier routing (already done) | ~$10/matter | ~$2/matter | 80% |
| Cache repeat comparisons | ~$2/matter | ~$1.5/matter | 25% |
| Skip unrelated entity pairs | ~$2/matter | ~$1.2/matter | 40% |
| Batch Gemini calls | ~$2/matter | ~$1.5/matter | 25% |

**Combined potential:** From ~$2/matter to ~$0.80/matter (60% further reduction).

**Biggest wins:**
1. **Skip unrelated pairs:** Before comparing, check if two statements share any date/amount/topic keywords. Skip obvious non-contradictions without LLM.
2. **Cache repeat comparisons:** If the same two chunks are compared again (reprocessing), return cached result.
3. **Batch Gemini screening:** Send 5-10 pairs per Gemini call instead of 1.

---

## Summary

The contradiction engine is well-architected and production-ready. Unlike the timeline and entity engines which have critical pipeline bugs, the contradiction engine's issues are about **missing features** (cross-entity, exhaustive mode, resolution workflow) rather than **broken functionality**.

**Priority order for contradiction engine work:**
1. Async batch processing (unblocks large matters) — 3-5 days
2. Resolution metadata + UI (attorney workflow) — 3-5 days
3. Cross-engine links (after entity/timeline fixes) — 2-3 days
4. Dedicated Contradictions Tab (CT-1 to CT-4) — 2-3 weeks
5. Cross-entity detection (Gap #49) — 1-2 weeks
6. Exhaustive mode (Gap #23) — 1 week
7. Contradiction chains + temporal resolution — 2-4 weeks

**Critical dependency:** Items 3-7 all benefit from fixing the entity engine's relationship persistence bug and the timeline engine's entity linking. Those fixes (documented in companion analysis docs) should be prioritized first.
