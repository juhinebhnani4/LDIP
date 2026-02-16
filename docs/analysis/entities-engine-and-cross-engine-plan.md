# Entities Engine Investigation & Cross-Engine Architecture Plan

> **Date:** 2026-02-06
> **Companion doc:** [timeline-engine-overhaul-plan.md](timeline-engine-overhaul-plan.md)

---

## Part 1: Why Relationships Show "(0)"

### The Smoking Gun

In `document_tasks.py` lines 3954-3955 and 4009-4010, extracted relationships are **counted but never saved**:

```python
# BOTH mega-batch and single-chunk paths do this:
if result.relationships:
    batch_relationships += len(result.relationships)  # Count for logging
    # ...that's it. No call to graph_service.save_edges()
```

Meanwhile, `graph_service.save_edges()` exists and works perfectly — it's used by `resolve_aliases` to save ALIAS_OF edges. The method accepts any `RelationshipType` (ALIAS_OF, HAS_ROLE, RELATED_TO). It's just never called for extracted relationships.

### What Gemini Actually Extracts

The extraction prompt (`backend/app/services/mig/prompts.py`) correctly asks for:
```json
"relationships": [
  {
    "source": "Sharma",
    "target": "ABC Pvt. Ltd.",
    "type": "HAS_ROLE",
    "description": "Director",
    "confidence": 0.95
  }
]
```

Gemini returns these. The extractor parses them into `ExtractedRelationship` objects. The pipeline counts them. Then they're garbage collected.

### What Currently EXISTS in identity_edges

Only `ALIAS_OF` edges — created by the `resolve_aliases` task after entity extraction. These work well (3-phase resolution with Jaro-Winkler + Gemini context analysis). But `HAS_ROLE` and `RELATED_TO` edges = 0 rows.

### The Fix Required

In `document_tasks.py`, after saving entities, resolve extracted relationship source/target names to entity IDs and call `graph_service.save_edges()`. The challenge: extracted relationships reference entity **names** (strings), not entity **IDs** (UUIDs). Need a name→ID resolution step.

---

## Part 2: Entity Engine Architecture — What Works, What Doesn't

### What Works Well

| Component | Status | Notes |
|-----------|--------|-------|
| Entity extraction (Gemini) | Good | Mega-batch optimization (5 chunks/call = 5x fewer API calls) |
| Entity types (Person/Org/Institution/Asset) | Good | Comprehensive for Indian legal |
| Alias resolution (3-phase) | Good | Phase 1: string similarity >0.85 (auto), Phase 2: Gemini context 0.60-0.85, Phase 3: skip <0.60 |
| Numbered role blocking | Good | "Respondent No. 2" never merges with "Respondent No. 3" |
| Transitive closure (Union-Find) | Good | A=B, B=C → A=C automatically |
| Entity mentions with bbox | Good | Precise document highlighting |
| Indian naming conventions | Good | Shri, Smt, Adv, Hon'ble, patronymics, initials |

### What Doesn't Work

| Problem | Root Cause | Impact |
|---------|-----------|--------|
| **Relationships (0)** | Extracted by Gemini but never saved to DB | No entity graph, no relationship view |
| **No role-based edges** | "Petitioner", "Advocate for Respondent" extracted as metadata, not as edges | Can't navigate "who represents whom" |
| **Cross-engine entity links empty** | Timeline entity linking depends on entities_involved (separate issue — see timeline plan) | Entity journey shows nothing |
| **Limited relationship types** | Only ALIAS_OF, HAS_ROLE, RELATED_TO — legal cases need more | Can't model legal relationships properly |

### What's Missing Entirely

1. **Legal role relationships** — "Advocate for", "Represented by", "Filed on behalf of" are extracted in entity metadata/roles but not modeled as edges
2. **Document-entity relationships** — Which entity authored/signed/is party to which document
3. **Temporal relationships** — Entity relationships change over time (was director, resigned, appointed)
4. **Entity grouping** — Which entities are on the same "side" of the case

---

## Part 3: First-Principles Analysis — What Would Sustain

### The Core Problem

The entity system treats entities as **isolated nodes with names and types**. But in legal cases, the value is in **relationships and roles**:
- Who is the advocate for whom?
- Who is the director of which company?
- Which entities are on the petitioner's side vs respondent's side?
- How did relationships change over time?

The current model has `identity_nodes` (entities) and `identity_edges` (relationships), which is the right structure. But the edges table is empty because the pipeline drops extracted relationships.

### What a 10-Year Architecture Looks Like

**1. Rich Relationship Taxonomy**

Current: `ALIAS_OF | HAS_ROLE | RELATED_TO` (too generic)

Needed:
```
ALIAS_OF          - Same entity, different names (keep)
ADVOCATE_FOR      - Legal representation
DIRECTOR_OF       - Corporate role
EMPLOYEE_OF       - Employment
PARTY_TO          - Party to a case/matter
WITNESS_IN        - Witness relationship
FILED_BY          - Filing relationship
SIGNED_BY         - Document execution
OWNS              - Ownership (property, shares)
GUARANTOR_FOR     - Financial guarantee
SUBSIDIARY_OF     - Corporate structure
SUPERSEDED_BY     - Entity succession
```

**2. Temporal Relationships**

Relationships have start/end dates:
```sql
ALTER TABLE identity_edges ADD COLUMN effective_from date;
ALTER TABLE identity_edges ADD COLUMN effective_until date;
```

"Was director from 2015 to 2023" vs "Is current director"

**3. Document-Sourced Relationships**

Every edge tracks which document it came from:
```sql
ALTER TABLE identity_edges ADD COLUMN source_document_id uuid REFERENCES documents(id);
ALTER TABLE identity_edges ADD COLUMN source_page integer;
```

**4. Entity Role Graph**

Instead of roles stored as metadata on the entity, roles should be first-class edges:
- "Shilpa Bhate & Associates" --ADVOCATE_FOR--> "Respondent No.1"
- "Respondent No.1" --PARTY_TO--> "This Matter"

**5. Side/Faction Detection**

Automatically cluster entities into sides:
- Petitioner side: Petitioner + their advocates + their witnesses
- Respondent side: Respondent + their advocates + their witnesses
- Neutral: Court, judges, government bodies

---

## Part 4: Cross-Engine Architecture — How Engines Should Work Together

### Current State: Engines Are Silos

```
Entity Engine → identity_nodes, identity_edges (ALIAS_OF only)
Timeline Engine → events table (entities_involved often empty)
Contradiction Engine → statement_comparisons (no entity context)
Citation Engine → act_citations (no entity context)
Chat/RAG Engine → vector search (reads everything, writes nothing)
```

Each engine extracts independently. The "cross-engine" service tries to bridge them after the fact, but the data isn't there.

### The Problem with Post-Hoc Linking

The current approach:
1. Entity engine extracts entities
2. Timeline engine extracts dates (separately)
3. Timeline engine tries to link entities to events (separate Gemini call)
4. Cross-engine service queries the links

This fails because:
- Entity linking in timeline is a separate step that may not run
- Entity names in events don't always match canonical names
- No shared context between engines during extraction

### The Right Architecture: Shared Extraction Context

**Principle:** Extract ONCE, link EVERYTHING, from the SAME LLM call.

Instead of 5 separate extraction passes over the same document chunks:

```
Current (5 passes):
  Pass 1: Entity extraction (Gemini)
  Pass 2: Date extraction (Gemini)
  Pass 3: Event classification (Gemini)
  Pass 4: Entity linking to events (Gemini)
  Pass 5: Citation extraction (Gemini)
```

**Proposed (2 passes):**
```
Pass 1: Unified Document Analysis (Gemini — larger prompt, one call per chunk)
  → Entities (names, types, roles, relationships)
  → Events (dates, types, descriptions, involved entities)
  → Citations (acts, sections, references)
  → All linked together at extraction time

Pass 2: Cross-Document Analysis (after all docs processed)
  → Alias resolution (entity dedup across documents)
  → Contradiction detection (cross-document comparison)
  → Causal chain detection (event sequence analysis)
  → Side/faction clustering
```

### Benefits of Unified Extraction

| Metric | Current (5 passes) | Proposed (2 passes) |
|--------|--------------------|--------------------|
| Gemini calls per chunk | 5 | 1-2 |
| Cost per document | ~₹1-2 (excl. embeddings) | ~₹0.50-0.80 |
| Entity linking accuracy | Low (separate context) | High (same context) |
| Event entity coverage | ~30% (separate step) | ~90% (inline) |
| Pipeline failure modes | 5 steps can fail | 2 steps can fail |
| Latency per document | 60-120s | 30-50s |

---

## Part 5: Cost Reduction Strategy

### Current Cost Breakdown (per document, excluding embeddings)

| Engine | Gemini Calls | Est. Cost |
|--------|-------------|-----------|
| Entity extraction | 1 per 5 chunks (mega-batch) | ₹0.10-0.50 |
| Alias resolution | 1 per 50 entities | ₹0.02-0.10 |
| Date extraction | 1 per chunk (5K char limit) | ₹0.01-0.05 |
| Event classification | 1 per 20 events | ₹0.01-0.05 |
| Entity linking (timeline) | 1 per 20 events | ₹0.01-0.05 |
| Citation extraction | 1 per 5 chunks | ₹0.10-0.30 |
| **Subtotal (extraction)** | **15-30 calls** | **₹0.25-1.05** |
| Contradiction screening | Gemini Flash per pair | ₹0.05-0.50 |
| Contradiction escalation | GPT-4 for uncertain | ₹0.50-5.00 |
| **Embeddings (dominant)** | 1 per 50 chunks | **₹5-15** |

### Cost Reduction Opportunities

**1. Unified Extraction (save 40-60% on extraction calls)**
Merge entity + date + citation extraction into one prompt per chunk. Goes from ~15-30 Gemini calls to ~5-10.

**2. Embedding Model Switch (save 50-70% on dominant cost)**
Current: OpenAI text-embedding-3-small ($0.02/1M tokens)
Alternative: Gemini text-embedding-004 (free tier or much cheaper) or open-source (e5-large, BGE)
This is the single biggest cost lever since embeddings are 65% of total spend.

**3. Smarter Contradiction Screening (save 20-30% on contradiction cost)**
Current: Compare every pair of statements
Better: Pre-filter using embedding similarity — only compare statements that are semantically related (cosine similarity > 0.5). Skip obviously unrelated pairs.

**4. Chunk-Level Caching (save 10-20% on reprocessing)**
When a document is reprocessed, only re-extract chunks that changed (detected via content hash). Currently `force_reprocess=True` re-does everything.

**5. Progressive Processing (save latency, not cost)**
Process high-signal chunks first (first/last pages, sections with dates) and stream partial results to UI. Process remaining chunks in background.

### Estimated Savings

| Strategy | Monthly Savings (est.) | Effort |
|----------|----------------------|--------|
| Unified extraction | ₹1,500-2,000 | Medium (prompt redesign) |
| Embedding model switch | ₹5,000-8,000 | Low (config change + validation) |
| Smarter contradiction pre-filter | ₹500-1,000 | Medium |
| Chunk-level caching | ₹1,000-2,000 | Low |
| **Total potential** | **₹8,000-13,000** | |
| **Current estimated monthly** | **₹18,000** | |
| **Reduction** | **44-72%** | |

---

## Implementation Plan

### Phase 1: Quick Wins (2-4 days)

**1.1 Save extracted relationships to identity_edges**

File: `backend/app/workers/tasks/document_tasks.py` (~lines 3947-3955, 4002-4010)

After `graph_service.save_entities()`, add:
```python
if result.relationships:
    edges_to_save = _resolve_relationship_names_to_ids(
        relationships=result.relationships,
        saved_entities=saved_entities_map,  # name → entity_id lookup
        matter_id=matter_id,
    )
    if edges_to_save:
        await graph_service.save_edges(matter_id=matter_id, edges=edges_to_save)
```

The helper `_resolve_relationship_names_to_ids` maps source/target entity names from the LLM response to the entity UUIDs that were just saved. Use fuzzy matching (existing `EntityResolver.calculate_name_similarity()`) with a 0.80 threshold.

**1.2 Expand relationship types**

File: `backend/app/models/entity.py` (RelationshipType enum)

Add: `ADVOCATE_FOR`, `DIRECTOR_OF`, `PARTY_TO`, `FILED_BY`

File: `backend/app/services/mig/prompts.py`

Update extraction prompt to ask for these specific relationship types instead of just HAS_ROLE/RELATED_TO.

**1.3 Add source_document_id to identity_edges**

Migration:
```sql
ALTER TABLE public.identity_edges ADD COLUMN source_document_id uuid REFERENCES public.documents(id);
ALTER TABLE public.identity_edges ADD COLUMN source_page integer;
```

Populate during save_edges with the current document being processed.

### Phase 2: Medium-Term (2-4 weeks)

**2.1 Unified extraction prompt**

Single Gemini call per chunk that returns:
```json
{
  "entities": [...],
  "relationships": [...],
  "events": [...],
  "citations": [...]
}
```

Feature-flagged, run alongside existing pipeline, validate quality before switching.

**2.2 Entity role graph**

Instead of storing roles as metadata, create edges:
- "Shilpa Bhate" --ADVOCATE_FOR--> "Respondent No.1"
- "Respondent No.1" --PARTY_TO--> matter

**2.3 Evaluate embedding model alternatives**

Test Gemini embeddings or open-source (e5-large-v2) against current OpenAI embeddings on legal document retrieval quality. If quality is comparable, switch.

### Phase 3: Long-Term (1-3 months)

**3.1 Temporal relationships** — Add effective_from/effective_until to edges
**3.2 Side/faction detection** — Auto-cluster entities by case side
**3.3 Cross-document entity correlation** — Same entity across matters
**3.4 Entity knowledge graph UI** — Visual graph explorer
**3.5 Incremental graph enrichment** — New documents enrich existing graph

---

## Verification

### Phase 1 Testing
1. Reprocess a document → check identity_edges table has HAS_ROLE/RELATED_TO rows
2. Open entity detail panel → "Relationships" section shows non-zero count
3. Verify ALIAS_OF edges still work (regression)
4. Check that relationship source/target names resolve to correct entity IDs

### Phase 2 Testing
- A/B: unified extraction vs current pipeline — compare entity count, relationship count, event count
- Cost comparison: measure Gemini API spend per document
- Embedding quality: recall@10 for legal document retrieval queries

---

## Part 6: What Existing Project Docs Already Planned for MIG

### Completed Stories

| Story | Status | What It Delivered |
|-------|--------|-------------------|
| **2C.1** (MIG Entity Extraction) | Done | Gemini extraction, identity_nodes/edges tables, mega-batch, dedup |
| **2C.2** (Alias Resolution) | Done | 3-phase resolution, transitive closure, manual merge/split corrections |
| **10C.1** (Entities Tab Graph) | Done | React Flow graph, Dagre layout, node selection, minimap, 148 tests |
| **10C.2** (Entities Detail+Merge) | Done | Detail panel, aliases, mentions, merge dialog, list/grid views, 39 tests |

### In-Progress / Ready for Dev

| Story | Status | What It Requires |
|-------|--------|------------------|
| **4.3** (Events Table + MIG Integration) | Dev-Complete but entity linking broken | `EventEntityLinker` class, entity journey API, timeline cache |
| **gap-5.3** (Cross-Engine Correlation Links) | Ready for Dev | Entity journey in detail panel, contradiction indicators on timeline, cross-tab navigation, 9 tasks all unchecked |

### From First-Principles Gap Analysis (2026-01-26)

The [first-principles-gap-analysis](../../_bmad-output/analysis/first-principles-gap-analysis-2026-01-26.md) identified these entity-related gaps using 20 analysis methods:

| Gap # | Description | Priority Score | Source Methods |
|-------|-------------|---------------|----------------|
| **#6** | No entity split (only merge) | **3.95** (3rd highest) | Pre-mortem, 5 Whys, ADR-004, SCAMPER |
| **#15** | No cross-engine correlation | High | First Principles, Comparative Analysis |
| **#47** | No entity resolver confidence tracking | Low | Mentor/Apprentice |
| **#49** | No cross-entity contradiction detection | High | Mentor/Apprentice |

**ADR-004 (Entity Split Data Model):** Decided on soft merge with `merged_into_id` FK on identity_nodes. Split = set FK to NULL. Original node preserved but filtered. Mentions retain original reference. Low complexity.

### From Gap Remediation Epics

The [epics-gap-remediation](../../_bmad-output/project-planning-artifacts/epics-gap-remediation.md) created concrete stories:

- **Story 3.3:** Add soft merge tracking (`merged_into_id`, `merged_at` columns on identity_nodes)
- **Story 3.4:** Entity split UI — undo incorrect merges via split button in detail panel
- **Story 4.3 (extended):** Cross-engine correlation — timeline↔contradiction links, entity journey
- **FR8.1:** Cross-entity contradiction detection — compare statements between different entities, not just within
- **FR8.6:** Entity resolver confidence tracking — store and display confidence scores

### From Phase 2 Backlog

The [Phase-2-Backlog](../../_bmad-output/project-planning-artifacts/Phase-2-Backlog.md) deferred:

- **Contradictions Tab** (dedicated view with entity-grouped display, side-by-side comparison)
- **Cross-Reference Map** (interactive graph of document relationships)
- **Process Chain Integrity Engine** (validates event sequences — requires process templates from Juhi)
- **Documentation Gap Engine** (detects missing documents — requires process templates)

### From Epics.md (Requirements)

| FR | Requirement | Status |
|----|-------------|--------|
| **FR14** (MIG) | Extract entities (PERSON, ORG, INSTITUTION, ASSET), store in identity_nodes/edges, resolve aliases | Done |
| **FR21** (Entities Tab) | MIG graph visualization, entity cards, detail panel, merge dialog, filter by type, entity statistics | Done |
| **NFR13** | Entity resolution accuracy > 95% | Not measured |
| **ADR-001** | PostgreSQL only for MIG (no Neo4j) — simpler security, adequate for query patterns | Decided |

### From Architecture.md

Key decision: **MIG queries are simple lookups** ("Get all aliases for entity X"), not complex graph traversals. PostgreSQL handles this with proper indexing. Neo4j rejected as overkill.

### Gaps Between Plans and Reality

| What Was Planned | What Actually Happened | Impact |
|-----------------|----------------------|--------|
| Story 2C.1 AC: "identity_edges contains HAS_ROLE, RELATED_TO, confidence" | Only ALIAS_OF edges saved; HAS_ROLE/RELATED_TO extracted but dropped | **Relationships (0)** |
| Story 4.3: Entity linking populates `entities_involved` | Entity linking runs but 0.85 threshold too strict; may not trigger at all | **Timeline Journey empty** |
| gap-5.3: Cross-engine correlation links | Backend service exists but depends on empty `entities_involved` column | **Cross-engine links broken** |
| FR14: "relationship connections" in entity cards | Graph shows ALIAS_OF edges only, no real relationships | **Incomplete entity graph** |
| NFR13: Entity resolution accuracy > 95% | No measurement infrastructure exists | **Unmeasured quality** |

---

## Key Files Reference

| File | What | Lines |
|------|------|-------|
| `backend/app/workers/tasks/document_tasks.py` | Pipeline — relationships counted but not saved | 3954-3955, 4009-4010 |
| `backend/app/services/mig/graph.py` | `save_edges()` — works but never called for HAS_ROLE | 750-807 |
| `backend/app/services/mig/graph.py` | `get_entity_relationships()` — queries identity_edges | 1035-1076 |
| `backend/app/services/mig/extractor.py` | Entity + relationship extraction from Gemini | All |
| `backend/app/services/mig/prompts.py` | Extraction prompt — already asks for relationships | All |
| `backend/app/services/mig/entity_resolver.py` | Alias resolution — 3-phase approach | All |
| `backend/app/models/entity.py` | RelationshipType enum, ExtractedRelationship model | 34-45, 242-251 |
| `backend/app/api/routes/entities.py` | Entity API — relationship queries | 352+ |
| `frontend/src/components/features/entities/EntitiesDetailPanel.tsx` | UI — shows Relationships (0) | 70-74 |
| `backend/app/core/cost_tracking.py` | LLM cost infrastructure | All |
