# Tech-Spec: Epic 9 - Intelligence Improvements

**Created:** 2026-01-28
**Status:** Ready for Development
**Epic:** 9 - Intelligence Improvements (Phase 8, Week 15-16)
**Gaps Addressed:** #29, #30, #31, #47, #48, #49

---

## Overview

### Problem Statement

LDIP's intelligence engines operate in silos with limited cross-engine correlation:

1. **Contradiction detection is single-entity only** - Can't compare what Plaintiff says vs Defendant says
2. **Search has no synonym expansion** - Users miss results because they search "breach" but document says "default"
3. **Unknown timeline participants are dropped** - Valuable context lost when entities can't be resolved
4. **Citations lack sentence-level granularity** - Only chunk-level positions stored
5. **No extraction visibility** - Users can't see what was extracted or confidence levels
6. **Entity confidence hidden** - Resolution confidence exists but not surfaced to users

### Solution

Implement 6 lightweight intelligence features with **zero new LLM costs** by leveraging existing infrastructure:

| Category | Stories | Approach |
|----------|---------|----------|
| **Cross-Engine** | 9.1 | DB-level pair filtering + existing comparator |
| **Search** | 9.2 | Static synonym dictionary + index-time expansion |
| **Timeline** | 9.3 | Flag unknown participants for manual resolution |
| **Citations** | 9.4 | Regex sentence detection + character offsets |
| **Visibility** | 9.5, 9.6 | Surface existing data via API |

### Scope

**In Scope:**
- Cross-entity contradiction detection (FR8.1)
- Synonym expansion in search (FR8.2)
- Flag unknown timeline participants (FR8.3)
- Citation sentence-level granularity (FR8.4)
- Extraction summary with confidence (FR8.5 - simplified)
- Entity resolver confidence display (FR8.6)

**Out of Scope:**
- ML-based completeness models
- Real-time LLM query expansion
- New NLP dependencies (spaCy, etc.)
- Cross-matter intelligence

### Design Constraints (from User Requirements)

| Constraint | Target | Approach |
|------------|--------|----------|
| **Latency** | <100ms added | Static lookups, DB queries, no LLM |
| **Cost** | $0 new LLM | Reuse existing pipelines |
| **Validation** | Pre-user-testing | Keep simple, iterate based on feedback |

---

## Context for Development

### Codebase Patterns

**Contradiction Engine Pattern:**
```python
# Two-tier routing already exists - reuse it
# File: backend/app/engines/contradiction/comparator.py
async def compare_statement_pair(
    statement_a: Statement,
    statement_b: Statement,
) -> ComparisonResult:
    # Tier 1: Gemini Flash screening (~$0.0001)
    # Tier 2: GPT-4 for uncertain cases (~$0.025)
```

**Entity Resolution Pattern:**
```python
# File: backend/app/services/mig/entity_resolver.py
# Confidence already calculated and stored
confidence = (name_similarity + context_confidence) / 2
metadata = {"auto_linked": True, "name_similarity": 0.87}
```

**Search Pattern:**
```python
# File: backend/app/services/rag/hybrid_search.py
# BM25 uses tsvector - can add synonyms at index time
search_vector = to_tsvector('english', content)
```

### Files to Reference

| File | Purpose | Stories |
|------|---------|---------|
| `backend/app/engines/contradiction/comparator.py` | Statement comparison | 9.1 |
| `backend/app/services/rag/hybrid_search.py` | Search service | 9.2 |
| `backend/app/engines/timeline/entity_linker.py` | Timeline entity linking | 9.3 |
| `backend/app/engines/citation/extractor.py` | Citation extraction | 9.4 |
| `backend/app/engines/citation/storage.py` | Citation storage | 9.4 |
| `backend/app/services/mig/entity_resolver.py` | Entity confidence | 9.6 |
| `backend/app/core/data_quality.py` | Extraction metrics | 9.5 |

### Technical Decisions (ADRs from Elicitation)

**ADR-011: Synonym Expansion Strategy**
- **Decision:** Static dictionary + index-time expansion
- **Rationale:** Query-time expansion adds latency; index-time is O(1) at search

**ADR-012: Cross-Entity Pair Generation**
- **Decision:** DB-level filtering by value conflicts before LLM
- **Rationale:** Reduces pairs from O(n²) to O(tens), 90% cost reduction

**ADR-013: Completeness Verification**
- **Decision:** Simplify to "Extraction Summary" - counts + confidence
- **Rationale:** Users unclear on completeness value; summary is actionable

---

## Implementation Plan

### Story 9.1: Cross-Entity Contradiction Detection (FR8.1)

**Goal:** Compare statements across different entities (e.g., Plaintiff vs Defendant)

**Task 9.1.1:** Add cross-entity pair generation query
- File: `backend/app/engines/contradiction/pair_generator.py` (new)
- SQL query to find cross-entity pairs with value conflicts
- Cap at 50 pairs per matter to control costs

```sql
-- Generate cross-entity candidate pairs
SELECT s1.id as statement_a_id, s2.id as statement_b_id,
       s1.entity_id as entity_a, s2.entity_id as entity_b
FROM statements s1
JOIN statements s2 ON s1.matter_id = s2.matter_id
WHERE s1.entity_id != s2.entity_id
  AND s1.id < s2.id  -- Avoid duplicate pairs
  AND (
    -- Date conflict
    (s1.extracted_date IS NOT NULL AND s2.extracted_date IS NOT NULL
     AND s1.extracted_date != s2.extracted_date)
    OR
    -- Amount conflict
    (s1.extracted_amount IS NOT NULL AND s2.extracted_amount IS NOT NULL
     AND ABS(s1.extracted_amount - s2.extracted_amount) > 0.01)
    OR
    -- Topic overlap (same subject matter)
    (s1.topic_hash = s2.topic_hash)
  )
ORDER BY
  CASE WHEN s1.extracted_date != s2.extracted_date THEN 0 ELSE 1 END,
  CASE WHEN s1.extracted_amount != s2.extracted_amount THEN 0 ELSE 1 END
LIMIT 50;
```

**Task 9.1.2:** Add `topic_hash` column to statements table
- Migration: `backend/supabase/migrations/YYYYMMDD_statement_topic_hash.sql`
- Compute hash from key terms in statement for topic clustering

**Task 9.1.3:** Extend comparator to handle cross-entity pairs
- File: `backend/app/engines/contradiction/comparator.py`
- Add `is_cross_entity` flag to comparison result
- Include both entity names in explanation

**Task 9.1.4:** Add cross-entity contradictions to UI
- File: `frontend/src/components/features/contradiction/`
- Filter: "Show cross-entity only" toggle
- Display: "Plaintiff (John) vs Defendant (ABC Corp)"

**Acceptance Criteria:**
- [ ] Given statements from Plaintiff saying "Contract signed Jan 15" and Defendant saying "Contract signed Jan 20"
- [ ] When cross-entity contradiction detection runs
- [ ] Then a contradiction is detected with `is_cross_entity: true`
- [ ] And the UI shows "Cross-entity: Plaintiff vs Defendant - Date Mismatch"

---

### Story 9.2: Synonym Expansion in Search (FR8.2)

**Goal:** Expand search queries with legal synonyms to improve recall

**Task 9.2.1:** Create legal synonym dictionary
- File: `backend/app/services/rag/legal_synonyms.py` (new)
- ~200 curated legal term mappings
- Bidirectional expansion

```python
LEGAL_SYNONYMS: dict[str, list[str]] = {
    # Contract terms
    "breach": ["violation", "default", "non-compliance", "infringement"],
    "contract": ["agreement", "deed", "covenant", "instrument"],
    "terminate": ["cancel", "rescind", "revoke", "annul"],

    # Party terms
    "plaintiff": ["petitioner", "complainant", "claimant", "applicant"],
    "defendant": ["respondent", "accused", "opposite party"],

    # Legal acts (Indian)
    "NI Act": ["Negotiable Instruments Act", "N.I. Act"],
    "CPC": ["Code of Civil Procedure", "Civil Procedure Code"],
    "IPC": ["Indian Penal Code", "Penal Code"],
    "CrPC": ["Code of Criminal Procedure", "Criminal Procedure Code"],

    # Actions
    "file": ["lodge", "submit", "present", "institute"],
    "appeal": ["revision", "review", "challenge"],

    # ... ~200 total entries
}

def expand_query(query: str) -> list[str]:
    """Return original + all synonym variations."""
    terms = query.lower().split()
    expanded = [query]
    for term in terms:
        if term in LEGAL_SYNONYMS:
            for synonym in LEGAL_SYNONYMS[term]:
                expanded.append(query.replace(term, synonym))
    return list(set(expanded))[:10]  # Cap expansions
```

**Task 9.2.2:** Add synonym expansion to hybrid search
- File: `backend/app/services/rag/hybrid_search.py`
- Expand query terms before BM25 search
- Combine results from all expansions

**Task 9.2.3:** Add synonym expansion indicator to search response
- Return `synonyms_used: ["breach → violation", "contract → agreement"]`
- Frontend shows "Also searched for: violation, agreement"

**Task 9.2.4:** Index-time synonym injection (optional optimization)
- File: `backend/app/services/chunk_service.py`
- Add synonyms to tsvector during chunk ingestion
- Improves search latency (expansion at index, not query)

**Acceptance Criteria:**
- [ ] Given a user searches for "breach of contract"
- [ ] When the search executes
- [ ] Then results include documents containing "violation of agreement"
- [ ] And the response shows `synonyms_used: ["breach → violation"]`
- [ ] And total latency increase is <10ms

---

### Story 9.3: Flag Unknown Timeline Participants (FR8.3)

**Goal:** Track mentions that couldn't be linked to known entities

**Task 9.3.1:** Add unknown participant tracking to timeline events
- File: `backend/app/engines/timeline/entity_linker.py`
- Instead of dropping unlinked mentions, store them

```python
@dataclass
class UnknownParticipant:
    mention_text: str           # "the said party"
    mention_context: str        # Surrounding 100 chars
    source_page: int | None
    confidence: float           # How confident we are this IS an entity
    suggested_entity_id: str | None  # Best guess if any
```

**Task 9.3.2:** Add `unknown_participants` column to timeline_events
- Migration: `backend/supabase/migrations/YYYYMMDD_unknown_participants.sql`
- JSONB array of UnknownParticipant objects

**Task 9.3.3:** Create manual resolution UI
- File: `frontend/src/components/features/timeline/UnknownParticipantResolver.tsx`
- Show list of unknown mentions with context
- Dropdown to link to existing entity or create new

**Task 9.3.4:** Add resolution API endpoint
- File: `backend/app/api/routes/timeline.py`
- `POST /timeline/events/{id}/resolve-participant`
- Links unknown participant to entity, updates event

**Acceptance Criteria:**
- [ ] Given a timeline event mentions "the said party" that can't be resolved
- [ ] When entity linking completes
- [ ] Then the event stores `unknown_participants: [{mention_text: "the said party", ...}]`
- [ ] And the UI shows a "Resolve" button next to unknown mentions
- [ ] And users can link the mention to an existing entity

---

### Story 9.4: Citation Sentence-Level Granularity (FR8.4)

**Goal:** Store sentence boundaries for precise citation highlighting

**Task 9.4.1:** Add sentence position fields to citations table
- Migration: `backend/supabase/migrations/YYYYMMDD_citation_positions.sql`
- Add: `start_char`, `end_char`, `sentence_text`

```sql
ALTER TABLE citations ADD COLUMN start_char INTEGER;
ALTER TABLE citations ADD COLUMN end_char INTEGER;
ALTER TABLE citations ADD COLUMN sentence_text TEXT;
```

**Task 9.4.2:** Create sentence boundary detector
- File: `backend/app/engines/citation/sentence_detector.py` (new)
- Regex-based sentence splitting (no NLP dependency)

```python
import re

SENTENCE_PATTERN = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z])|'  # Standard sentence end
    r'(?<=\d\.)\s+(?=[A-Z])|'   # After numbered list
    r'(?<=\)\.)\s+',            # After citation like "Act, 1872)."
    re.MULTILINE
)

def find_sentence_boundaries(text: str, citation_start: int) -> tuple[int, int]:
    """Find sentence containing the citation."""
    sentences = SENTENCE_PATTERN.split(text)
    char_pos = 0
    for sentence in sentences:
        sentence_end = char_pos + len(sentence)
        if char_pos <= citation_start < sentence_end:
            return char_pos, sentence_end
        char_pos = sentence_end + 1  # +1 for space
    return 0, len(text)  # Fallback to full text
```

**Task 9.4.3:** Update citation extraction to capture positions
- File: `backend/app/engines/citation/extractor.py`
- After regex match, calculate sentence boundaries
- Store positions in extraction result

**Task 9.4.4:** Update citation storage to persist positions
- File: `backend/app/engines/citation/storage.py`
- Save `start_char`, `end_char`, `sentence_text`

**Task 9.4.5:** Update frontend highlighting
- File: `frontend/src/components/features/citation/CitationHighlight.tsx`
- Use sentence boundaries for precise highlighting

**Acceptance Criteria:**
- [ ] Given a citation "Section 138 of NI Act" appears mid-paragraph
- [ ] When extraction completes
- [ ] Then the citation record includes `sentence_text: "The cheque was dishonoured under Section 138 of NI Act."`
- [ ] And `start_char` and `end_char` mark the sentence boundaries
- [ ] And the UI highlights only that sentence, not the whole chunk

---

### Story 9.5: Extraction Summary with Confidence (FR8.5)

**Goal:** Show users what was extracted and confidence levels per engine

**Task 9.5.1:** Create extraction summary service
- File: `backend/app/services/extraction_summary_service.py` (new)
- Aggregate counts and confidence per engine

```python
@dataclass
class EngineSummary:
    engine: str
    count: int
    avg_confidence: float
    low_confidence_count: int  # Below 0.70

@dataclass
class ExtractionSummary:
    matter_id: str
    document_id: str | None  # None for matter-level
    engines: list[EngineSummary]
    overall_confidence: float
    flag_for_review: bool  # True if any avg < 0.70

async def get_extraction_summary(
    matter_id: str,
    document_id: str | None = None
) -> ExtractionSummary:
    citations = await get_citation_stats(matter_id, document_id)
    entities = await get_entity_stats(matter_id)
    events = await get_event_stats(matter_id, document_id)

    engines = [
        EngineSummary("citations", citations.count, citations.avg_confidence, ...),
        EngineSummary("entities", entities.count, entities.avg_confidence, ...),
        EngineSummary("events", events.count, events.avg_confidence, ...),
    ]

    overall = sum(e.avg_confidence for e in engines) / len(engines)
    flag = any(e.avg_confidence < 0.70 for e in engines)

    return ExtractionSummary(matter_id, document_id, engines, overall, flag)
```

**Task 9.5.2:** Add summary API endpoint
- File: `backend/app/api/routes/matters.py`
- `GET /matters/{id}/extraction-summary`
- Optional `document_id` query param for document-level

**Task 9.5.3:** Create extraction summary widget
- File: `frontend/src/components/features/matter/ExtractionSummaryWidget.tsx`
- Display counts per engine with confidence bars
- Yellow warning if `flag_for_review: true`

**Acceptance Criteria:**
- [ ] Given a matter with 15 citations (82% avg), 8 entities (78% avg), 23 events (85% avg)
- [ ] When user views the matter dashboard
- [ ] Then they see "Citations: 15 (82%), Entities: 8 (78%), Events: 23 (85%)"
- [ ] And overall confidence shows "82%"
- [ ] And no review flag is shown (all above 70%)

---

### Story 9.6: Entity Resolver Confidence Display (FR8.6)

**Goal:** Surface existing entity resolution confidence to users

**Task 9.6.1:** Add confidence to entity API response
- File: `backend/app/api/routes/entities.py`
- Include `resolution_confidence` and `resolution_method` in response

```python
class EntityResponse(BaseModel):
    id: str
    canonical_name: str
    entity_type: EntityType
    aliases: list[str]
    mention_count: int
    # New fields
    resolution_confidence: float | None  # 0.0-1.0
    resolution_method: str | None  # "auto_linked" | "context_analyzed" | "manual"
    confidence_factors: dict | None  # {"name_similarity": 0.87, "context": 0.75}
```

**Task 9.6.2:** Query confidence from entity_edges
- File: `backend/app/services/mig/entity_service.py`
- Join with edges to get confidence metadata

```python
async def get_entity_with_confidence(entity_id: str) -> EntityWithConfidence:
    entity = await get_entity(entity_id)

    # Get resolution edge if this entity was merged
    edge = await db.table("entity_edges")\
        .select("confidence, metadata")\
        .eq("target_entity_id", entity_id)\
        .eq("relationship_type", "ALIAS_OF")\
        .single()

    if edge:
        return EntityWithConfidence(
            **entity.dict(),
            resolution_confidence=edge.confidence,
            resolution_method=edge.metadata.get("method", "unknown"),
            confidence_factors=edge.metadata,
        )
    return EntityWithConfidence(**entity.dict())
```

**Task 9.6.3:** Display confidence in entity UI
- File: `frontend/src/components/features/entity/EntityCard.tsx`
- Show confidence badge: "High (92%)" / "Medium (75%)" / "Low (58%)"
- Tooltip shows factors: "Name similarity: 87%, Context: 75%"

**Task 9.6.4:** Add confidence filter to entity list
- File: `frontend/src/components/features/entity/EntityList.tsx`
- Filter: "Show low confidence only" for review workflow

**Acceptance Criteria:**
- [ ] Given an entity "N.D. Jobalia" was auto-linked with 87% name similarity
- [ ] When user views the entity detail
- [ ] Then they see "Confidence: High (87%)"
- [ ] And tooltip shows "Name similarity: 87%"
- [ ] And users can filter entity list by "Low confidence" to review

---

## Additional Context

### Dependencies

| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| No new dependencies | - | All features use existing stack | ✅ |

### Testing Strategy

**Unit Tests:**
- `test_cross_entity_pairs.py` - Verify pair generation query
- `test_legal_synonyms.py` - Verify expansion coverage
- `test_sentence_detector.py` - Verify boundary detection
- `test_extraction_summary.py` - Verify aggregation logic

**Integration Tests:**
- Cross-entity contradiction with real statement data
- Search with synonym expansion enabled/disabled comparison
- End-to-end unknown participant resolution

**Performance Tests:**
- Measure latency impact of synonym expansion
- Verify cross-entity query stays under 100ms

### Database Migrations

```sql
-- Migration 1: Statement topic hash
ALTER TABLE statements ADD COLUMN topic_hash TEXT;
CREATE INDEX idx_statements_topic_hash ON statements(matter_id, topic_hash);

-- Migration 2: Unknown participants
ALTER TABLE timeline_events ADD COLUMN unknown_participants JSONB DEFAULT '[]';

-- Migration 3: Citation positions
ALTER TABLE citations ADD COLUMN start_char INTEGER;
ALTER TABLE citations ADD COLUMN end_char INTEGER;
ALTER TABLE citations ADD COLUMN sentence_text TEXT;

-- No RLS changes needed - all tables already have matter_id policies
```

### Configuration Changes

```python
# Add to backend/app/core/config.py

# Story 9.1: Cross-entity limits
cross_entity_max_pairs: int = 50
cross_entity_value_conflict_only: bool = True

# Story 9.2: Synonym expansion
synonym_expansion_enabled: bool = True
synonym_max_expansions: int = 10

# Story 9.5: Confidence thresholds
low_confidence_threshold: float = 0.70
flag_for_review_threshold: float = 0.70
```

### New Files Summary

| File | Purpose |
|------|---------|
| `backend/app/engines/contradiction/pair_generator.py` | Cross-entity pair SQL |
| `backend/app/services/rag/legal_synonyms.py` | Synonym dictionary |
| `backend/app/engines/citation/sentence_detector.py` | Regex sentence boundaries |
| `backend/app/services/extraction_summary_service.py` | Aggregation service |
| `frontend/src/components/features/timeline/UnknownParticipantResolver.tsx` | Resolution UI |
| `frontend/src/components/features/matter/ExtractionSummaryWidget.tsx` | Summary widget |

### Notes

- **No LLM costs** - All features use existing pipelines or algorithmic approaches
- **Latency budget** - Total <100ms across all features
- **Pre-validation** - Keep implementations simple, iterate based on user feedback
- **Backward compatible** - All new columns are nullable, existing data unaffected

### Egress Optimization Pattern (CRITICAL)

**All new database queries MUST follow the selective column pattern:**

```python
# BAD - causes excessive egress
.select("*")

# GOOD - use predefined column lists
CITATION_LIST_COLUMNS = "id, matter_id, act_name, section, ..."
.select(CITATION_LIST_COLUMNS)
```

**Story 9.4 (Citation granularity):** Use existing `CITATION_LIST_COLUMNS` from `storage.py`. Add new position columns (`start_char`, `end_char`, `sentence_text`) to the column constant.

**Story 9.5 (Extraction summary):** Create `*_STATS_COLUMNS` constants for aggregation queries (e.g., `ENTITY_STATS_COLUMNS`, `EVENT_STATS_COLUMNS`).

**Reference:** See `backend/app/engines/citation/storage.py` lines 52-63 for column constants.

---

## Story Priority Order

| Priority | Story | Reason |
|----------|-------|--------|
| P0 | 9.1 | "Game changer" per user focus group |
| P0 | 9.2 | "Daily pain point" - highest frequency need |
| P1 | 9.3 | "Hours saved" - paralegal workflow |
| P1 | 9.4 | Improves citation UX precision |
| P1 | 9.5 | Visibility into extraction quality |
| P1 | 9.6 | Already computed, just surface it |

---

*Generated by BMAD Create Tech-Spec Workflow*
