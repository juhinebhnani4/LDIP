# Cross-Engine Review — Missed Details, Consistency Check & Unified Plan

> **Date:** 2026-02-06
> **Scope:** Review of all 5 engine analysis docs against all project documentation

---

## Part 1: Missed Details from Project Docs

### 1.1 Security Layer Missing from ALL 5 Docs (Stories 8-1, 8-2, 8-3)

**None of the 5 analysis docs mention the comprehensive guardrail system.** This is a cross-cutting concern that affects every engine.

| Story | What It Does | Status |
|-------|-------------|--------|
| 8-1 | Regex fast-path guardrails — blocks legal advice requests in <5ms, 57 tests | Done |
| 8-2 | GPT-4o-mini violation detection — catches subtle violations regex misses | Done |
| 8-3 | Language policing — output sanitization preventing legal conclusions | Done |

Example: User asks "Should I file an appeal?" → Blocked by guardrail → Suggested rewrite: "What do the documents say about appeals?"

**Impact:** Every engine generates user-facing text that must pass through language policing. Citation verification explanations, contradiction reasoning, timeline descriptions, and RAG answers all need legal neutrality enforcement.

### 1.2 Verification Workflow Missing from ALL 5 Docs (Stories 8-4, 8-5)

**None of the 5 docs mention the attorney verification workflow**, despite it being critical for court-defensible output.

**ADR-004 Verification Tiers:**
- >90% confidence → GREEN badge, optional verification
- 70-90% confidence → YELLOW badge, suggested verification
- <70% confidence → RED badge, **required verification (blocks export)**

| Story | What | Status |
|-------|------|--------|
| 8-4 | `finding_verifications` table + `VerificationService` + export blocking logic | Done (52 tests) |
| 8-5 | Verification Queue DataTable + bulk actions + progress bar | Done (61 tests) |

**Impact:** Every engine produces findings. Unverified low-confidence findings block report export. This is NFR23 (court-defensible verification).

### 1.3 Acts Library Architecture — NEW Schema Not in Citation Doc

A new architectural design exists at `_bmad-output/docs/acts-library-architecture.md` (318 lines, designed 2026-02-06) that the citation doc doesn't reference:

**New tables (not yet implemented):**
- `library_sections` — Section-level text with **temporal versioning** (`valid_from`, `valid_to`)
- `library_act_aliases` — Maps Act name variations to canonical records
- `library_embeddings` — Replaceable embeddings tied to sections, not chunks

**Impact:** This directly addresses the citation doc's Year 1 vision (structured citation model, legislative history awareness). The architectural groundwork already exists — it's not just a future vision.

### 1.4 Contradictions List API Missing (GAP-API-2)

The contradiction doc states "all 4 stories complete" but the MVP gap analysis (`mvp-gap-analysis-2026-01-16.md`, GAP-API-2) shows a **missing endpoint**: `GET /api/matters/{id}/contradictions` (list all contradictions grouped by entity).

Current state: Only entity-specific endpoints exist (statements and compare). The contradiction list API (Story 14-2) was implemented later but this gap is worth noting for completeness.

### 1.5 Summary API / Upload Progress Missing (GAP-API-1, GAP-STORY-1)

Two critical MVP gaps not mentioned in the RAG doc:
- **GAP-API-1:** FR19 Summary Tab was using mock data initially (Summary API now exists via `summary_service.py`)
- **GAP-STORY-1:** Upload Stage 3-4 (live discovery panel during processing) is 0% complete — all 11 tasks unchecked

### 1.6 Downstream RAG Trigger (Story 17-7) Not in Pipeline Docs

After OCR completion on large documents, `chunk_document.delay()` automatically triggers re-chunking with bbox linking (batched at 500). This glue between OCR and RAG/engines is not documented in any of the 5 analysis docs.

### 1.7 Intent Classification Details (Story 6-1)

The RAG doc mentions the orchestrator but doesn't detail Story 6-1's implementation:
- GPT-3.5 Turbo for intent classification (not GPT-4 — cost savings)
- Fast-path regex patterns checked BEFORE LLM call (zero-cost for common queries)
- Intent types: CITATION, TIMELINE, CONTRADICTION, RAG_SEARCH, MULTI_ENGINE
- Low confidence (<0.7) triggers multi-engine fallback
- 41 tests passing

### 1.8 Database Schema Drift

Not mentioned in any doc:
- `identity_edges` DB columns: `source_node_id`/`target_node_id` vs code: `source_entity_id`/`target_entity_id` (aliased in queries)
- `events.event_date` is `date` in DB but `string` in frontend types
- `Anomaly` and `StatementPairComparison` models exist in backend but have NO frontend TypeScript types

### 1.9 Additional ADRs Not Referenced

| ADR | Decision | Impact |
|-----|----------|--------|
| ADR-002 | Hybrid LLM: Gemini Flash (ingestion) + GPT-4 (reasoning) | Cost: $13-14/matter vs $75-110 |
| ADR-003 | 3 MVP engines, not monolithic query handler | Court-defensible traceability |
| ADR-004 | Verification tiers with export as checkpoint | Blocks export for unverified <70% findings |
| ADR-005 | Act Discovery with user-driven resolution | User controls Act versions |

### 1.10 Session Memory is 7-Day Auto-Extending (Not 4-Hour)

The RAG doc doesn't specify memory TTL. From `Requirements-Baseline-v1.0.md`:
- Auto-extends on activity, max 30 days hard limit
- Survives lunch breaks, weekends, multi-day case prep
- Scope: `session:{matter_id}:{user_id}`

---

## Part 2: Cross-Analysis — Do the Docs Talk to Each Other?

### 2.1 Cross-References (Who Points to Whom?)

| From Doc | References | Missing References |
|----------|-----------|-------------------|
| Timeline | None of the other docs | Should reference entities doc (relationship persistence fix affects entity linking) |
| Entities | References timeline doc explicitly (companion doc link) | Good |
| Contradiction | References entities doc by filename (line 203, 374) | Good |
| Citation | References "companion analysis docs" (vague) | Should name entities + timeline docs explicitly |
| **RAG** | **References NONE of the companion docs** | Should reference all 4 (orchestrates all engines) |

**Finding: The RAG doc is completely isolated.** It's the most cross-engine-dependent doc (it orchestrates all other engines) but references none of them. The timeline doc is also isolated — it doesn't reference the entities doc despite entity linking being a shared concern.

### 2.2 Gap Numbers — Consistent Where They Appear

| Gap # | Appears In | Missing From |
|--------|-----------|-------------|
| #6 (Entity split) | Entities | Timeline, Contradiction, Citation, RAG |
| **#15 (Cross-engine correlation)** | Entities, Contradiction, Citation | **Timeline, RAG** (both need cross-engine!) |
| #23 (Exhaustive contradiction) | Contradiction | — |
| #29 (Completeness verification) | RAG | — |
| #30 (Citation granularity) | Citation, RAG | — |
| #49 (Cross-entity contradiction) | Entities, Contradiction | — |
| **#50 (Cross-engine consistency)** | Citation | **Timeline, RAG** (both affected) |

**Finding:** Gap #15 (cross-engine correlation) is the most cross-cutting gap and should be in all 5 docs but only appears in 3. Gap #50 (cross-engine consistency) only appears in citation doc but affects timeline and RAG too.

### 2.3 Story Counts — One Inconsistency

The comparison tables in contradiction, citation, and RAG docs disagree on entity story counts:

| Doc | Entity Stories Count |
|-----|---------------------|
| Contradiction doc | "Yes (2C.1, 2C.2)" — counts 2 |
| Citation doc | "4 (2C.1, 2C.2, 10C.1, 10C.2)" — counts 4 |
| RAG doc | "4" — counts 4 |
| Entities doc (source of truth) | Lists all 4 (2C.1, 2C.2, 10C.1, 10C.2) |

**Fix needed:** Contradiction doc should count 4 entity stories, not 2.

### 2.4 Citation Doc Internal Inconsistency

Stories 3-1 and 10C.3 are listed as "Review" status in the detailed table (Part 4) but the Summary claims "All 6 stories complete." Review ≠ Complete.

### 2.5 Cost Estimates — Mixed Currencies, No Unified Model

| Doc | Unit | Currency | Total |
|-----|------|----------|-------|
| Entities | Per document/month | INR (₹18,000/month) | Most comprehensive |
| Contradiction | Per matter | USD (~$2/matter) | — |
| Citation | Per matter | USD (~$0.50-1.50/matter) | — |
| RAG | Per query | Both (₹0.02-0.10 / $0.0003-0.0012) | — |
| Timeline | Qualitative only | — | "~1/3 Gemini cost" |

**Finding:** Nobody can answer "What does processing one matter cost end-to-end?" The entities doc comes closest but doesn't include contradiction or citation costs.

### 2.6 Unified Extraction — Proposed Twice Independently

**Timeline doc (Phase 2.1):** Merge 3 Celery tasks → 1 unified event extraction task with a new prompt.

**Entities doc (Part 4):** 2-pass unified extraction — Pass 1 (entities + events + citations + relationships from one Gemini call) + Pass 2 (cross-entity analysis).

**These overlap significantly but don't reference each other.** The entities doc is more ambitious (entities + events + citations in one call); the timeline doc is narrower (just events in one call). They need to be reconciled into a single plan.

---

## Part 3: What's Missing — The Big Gaps

### 3.1 No Unified Cross-Engine Dependency Diagram

The following dependency chain is implied across 5 separate docs but never drawn in one place:

```
Fix 1: Entity Engine — save HAS_ROLE/RELATED_TO edges (document_tasks.py:3954)
    ↓ unblocks
Fix 2: Timeline Engine — lower entity linking threshold to 0.70 + fix trigger
    ↓ unblocks
Fix 3: Cross-Engine Service — entity journey populates from events + contradictions
    ↓ unblocks
Fix 4: Contradiction Engine — cross-engine correlation (Gap #15)
Fix 5: Citation Engine — cross-engine consistency (Gap #50)
Fix 6: RAG Engine — contradiction-aware answers
```

**Without this diagram, a developer doesn't know the fix order.**

### 3.2 No Unified Priority Ordering

Each doc has its own roadmap. If you have 1 week, where do you start? Here's the correct cross-engine priority:

**Week 1 — Pipeline Fixes (highest impact, unblocks everything):**
1. Entity engine: Save relationships (1 day) — unblocks entity graph
2. Timeline dedup fix (1 day) — unblocks 2-3x more events
3. Timeline: process all chunks (30 min) — more events
4. Timeline: lower entity threshold 0.85→0.70 + fix trigger (2 hours) — populates entities_involved
5. RAG: fix bbox_ids in generator sources (30 min) — sources can highlight
6. RAG: filter sources to cited-only (1 day) — no irrelevant sources

**Week 2 — Cross-Engine Fixes:**
7. Cross-engine text search fallback (1 day) — entity journey shows data
8. RAG: enable Cohere Rerank (2 hours) — better search quality
9. RAG: real LLM streaming (1-2 days) — better UX
10. Citation: cost tracking in verification (2-3 hours) — visibility

**Week 3+ — New Features:**
11. Cross-engine consistency checking (Gap #50, 2 weeks)
12. Cross-engine correlation links (Gap #15, 2 weeks)
13. Contradiction async batch processing (3-5 days)
14. Contradiction resolution workflow (3-5 days)

### 3.3 No Unified Cost Model

**Estimated total cost per matter (combining all 5 docs):**

| Engine | Cost/Matter | Source |
|--------|-------------|--------|
| OCR + Chunking | ~₹1-3 ($0.01-0.04) | Gemini Flash |
| Embedding | ~₹5-15 ($0.06-0.18) | text-embedding-3-small |
| Entity extraction | ~₹0.10-0.50 ($0.001-0.006) | Gemini Flash mega-batch |
| Alias resolution | ~₹0-0.50 ($0-0.006) | Gemini (only for ambiguous) |
| Timeline extraction | ~₹0.10-0.50 ($0.001-0.006) | Gemini Flash per chunk |
| Citation extraction | ~₹0.10-0.50 ($0.001-0.006) | Gemini Flash + regex |
| Citation verification | ~₹0.50-2.00 ($0.006-0.024) | Gemini Flash per citation |
| Contradiction detection | ~₹5-15 ($0.06-0.18) | Gemini screening + GPT-4 |
| **Total per matter** | **~₹12-37 (~$0.15-0.45)** | — |
| **Per chat query** | **~₹0.02-0.10 ($0.0003-0.0012)** | Gemini Flash |
| **Executive summary** | **~₹2.50 ($0.03)** | GPT-4 (cached 1hr) |

**Monthly estimate (assuming ~50 matters):** ~₹600-1,850 processing + chat costs. The ₹18,000/month from the entities doc includes embedding costs which dominate.

### 3.4 No Document Processing Pipeline Diagram

The full pipeline from upload through all engines is never shown in one place. Piecing together from all docs:

```
Document Upload
    ↓
OCR (Google Document AI)
    ↓
Validation + Confidence Assessment (3-tier: Good/Fair/Poor)
    ↓
Chunking (parent: 1750 tokens, child: 550 tokens)
    ↓
Embedding (text-embedding-3-small, 1536 dims) + Bbox Linking
    ↓
┌─────────────────────────────── PARALLEL ──────────────────────────────┐
│                                                                        │
│  Entity Extraction (Gemini Flash, mega-batch 5 chunks)                │
│      ↓                                                                 │
│  Alias Resolution (3-phase: Jaro-Winkler > Gemini context > skip)    │
│      ↓                                                                 │
│  [BUG: Relationships counted but NOT SAVED]                           │
│                                                                        │
│  Citation Extraction (Gemini Flash + Regex, per chunk)                │
│      ↓                                                                 │
│  Act Resolution + Discovery Report                                    │
│                                                                        │
│  Date Extraction (Gemini Flash, per chunk)                            │
│      ↓                                                                 │
│  Event Classification (Gemini Flash, batch of 20)                     │
│      ↓                                                                 │
│  Entity Linking (pattern + optional Gemini, 0.85 threshold)           │
│      [BUG: Too strict, may not trigger, entities_involved NULL]       │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
    ↓
Contradiction Detection (Gemini screening + GPT-4 escalation)
    ↓
[User uploads Act] → Citation Verification (Gemini Flash)
    ↓
Summary Generation (GPT-4, cached 1hr)
    ↓
All data available for Ask Jaanch Q&A
```

### 3.5 Missing Cross-Engine Perspectives

| Perspective | Status |
|------------|--------|
| Security threat model across engines | Not documented — each doc mentions "XML boundaries" but no unified analysis |
| Performance/scalability under load | Not documented — what happens with 100+ docs per matter? |
| UX consistency across engines | Not documented — each engine has its own frontend patterns |
| Error handling / degradation | Not documented — what does the user see when 3 of 5 engines succeed? |
| Monitoring / observability | Not documented — no unified dashboard, logging, or alerting strategy |
| Testing infrastructure (Story 18-*) | Not documented — 10 testing stories exist but none of the 5 docs reference them |

---

## Part 4: Specific Corrections Needed

### Timeline Doc
- Add cross-reference to entities doc (entity linking depends on relationship persistence fix)
- Add Gap #15 (cross-engine correlation) — currently missing
- Note that anomaly detection requires manual API call (GAP-ORCH-1)

### Entities Doc
- Contradiction doc comparison table: fix entity story count from 2 to 4
- Note ADR-004 entity split data model (`merged_into_id` column preservation)
- Note FR8.6: entity resolver confidence scores are not stored — can't audit resolution quality

### Contradiction Doc
- Fix entity story count in comparison table (2 → 4)
- Note that the contradictions list API (Story 14-2) addresses GAP-API-2

### Citation Doc
- Fix internal inconsistency: stories 3-1 and 10C.3 are "Review", not "Complete"
- Add reference to acts-library-architecture.md as the concrete implementation plan for Year 1 vision
- Name companion docs explicitly instead of "companion analysis docs"

### RAG Doc
- Add cross-references to ALL 4 companion docs by filename
- Add Gap #15 and #50 — both affect RAG cross-engine integration
- Detail Story 6-1 intent classification (fast-path regex, GPT-3.5, 41 tests)
- Note session memory is 7-day auto-extending (from Requirements-Baseline)
- Mention Story 17-7 downstream RAG trigger (OCR → chunking → embedding)

### ALL 5 Docs
- Add "Security" section referencing Stories 8-1, 8-2, 8-3 (guardrails + language policing)
- Add "Verification Workflow" section referencing Stories 8-4, 8-5 (ADR-004 tiers, export blocking)
- Add "Testing" section referencing relevant Story 18-* tests

---

## Part 5: Recommended Actions

1. **Use this doc as the unified cross-engine reference.** It contains the dependency diagram, priority ordering, and cost model that the individual docs lack.

2. **Fix the 5 specific corrections** listed in Part 4 — these are factual errors and missing cross-references.

3. **The entity engine relationship fix is the single highest-priority item** across all 5 engines. It's 1 day of work and unblocks: entity graph, timeline entity linking, cross-engine journey, and eventually contradiction/citation cross-engine correlation.

4. **The RAG bbox + source filtering fix is the single highest-impact UX fix** — 1 day of work, directly addresses the user's original complaint about sources.

5. **Week 1 priority (from 3.2 above)** would fix 6 bugs across 3 engines and produce immediately visible improvements in the product.
