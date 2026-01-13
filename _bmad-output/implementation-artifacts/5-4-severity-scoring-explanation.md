# Story 5.4: Implement Severity Scoring and Explanation

Status: review

## Story

As an **attorney**,
I want **contradictions scored by severity with explanations**,
So that **I focus on the most critical issues first**.

## Acceptance Criteria

1. **Given** a contradiction is detected
   **When** severity scoring runs
   **Then** severity is assigned: high, medium, or low

2. **Given** a contradiction involves clear factual differences (dates, amounts)
   **When** scoring runs
   **Then** severity is "high"

3. **Given** a contradiction requires interpretation
   **When** scoring runs
   **Then** severity is "medium"

4. **Given** a contradiction is possible but uncertain
   **When** scoring runs
   **Then** severity is "low"

5. **Given** a contradiction is scored
   **When** it is displayed
   **Then** a natural language explanation is provided
   **And** evidence links show both statements with document sources

## Tasks / Subtasks

- [x] Task 1: Create severity scoring models and enums (AC: #1)
  - [x] 1.1: Add `SeverityLevel` enum: `HIGH`, `MEDIUM`, `LOW`
  - [x] 1.2: Create `ScoredContradiction` model extending ClassifiedContradiction with severity, severity_reasoning, explanation
  - [x] 1.3: Create `ScoringResult` model for API response with scoring metadata
  - [x] 1.4: Create `EvidenceLink` model for document source references (AC: #5)
  - [x] 1.5: Add models to `backend/app/models/contradiction.py`

- [x] Task 2: Implement severity scorer engine (AC: #1, #2, #3, #4)
  - [x] 2.1: Create `ContradictionScorer` in `backend/app/engines/contradiction/scorer.py`
  - [x] 2.2: Implement `score_contradiction()` - score a single ClassifiedContradiction
  - [x] 2.3: Implement rule-based scoring using ContradictionType
  - [x] 2.4: Implement confidence-based adjustment (low confidence → reduce severity)
  - [x] 2.5: Generate natural language explanation combining classification + severity

- [x] Task 3: Implement severity scoring rules (AC: #2, #3, #4)
  - [x] 3.1: HIGH severity: DATE_MISMATCH, AMOUNT_MISMATCH, FACTUAL_CONTRADICTION with confidence >= 0.8
  - [x] 3.2: MEDIUM severity: SEMANTIC_CONTRADICTION, or any type with 0.6 <= confidence < 0.8
  - [x] 3.3: LOW severity: Any type with confidence < 0.6, or SEMANTIC_CONTRADICTION with ambiguous reasoning
  - [x] 3.4: Handle edge cases: missing classification data defaults to MEDIUM

- [x] Task 4: Implement explanation generator (AC: #5)
  - [x] 4.1: Create `generate_explanation()` method
  - [x] 4.2: Combine contradiction type, severity, and extracted values into attorney-friendly text
  - [x] 4.3: Include document source references with page numbers
  - [x] 4.4: Generate EvidenceLink objects for both statements

- [x] Task 5: Update prompts for explanation enhancement (AC: #5)
  - [x] 5.1: N/A - Scorer is 100% rule-based per architecture (no LLM prompts needed)
  - [x] 5.2: Template-based explanation generation implemented in scorer.py
  - [x] 5.3: Format explanation for UI display (supports markdown)

- [x] Task 6: Integrate scorer into pipeline (AC: #1)
  - [x] 6.1: Scorer available via `score_all()` for post-classification processing
  - [x] 6.2: ScoredContradiction model includes `severity` and `severity_reasoning` fields
  - [x] 6.3: Scoring callable via `scorer.score_all(classifications, comparisons)` after classification batch
  - [x] 6.4: Store severity in `statement_comparisons` table via migration

- [x] Task 7: Update database schema (AC: #1)
  - [x] 7.1: Add `severity` column to `statement_comparisons` table (VARCHAR, CHECK constraint)
  - [x] 7.2: Add `severity_reasoning` column (TEXT)
  - [x] 7.3: Add `explanation` column (TEXT) for attorney-ready explanation
  - [x] 7.4: Create migration file: `supabase/migrations/20260114000006_add_severity_scoring.sql`

- [x] Task 8: Write comprehensive tests (AC: #1, #2, #3, #4, #5)
  - [x] 8.1: Unit tests for `ContradictionScorer` with mocked inputs
  - [x] 8.2: Test HIGH severity for date_mismatch with high confidence
  - [x] 8.3: Test HIGH severity for amount_mismatch with high confidence
  - [x] 8.4: Test MEDIUM severity for semantic_contradiction
  - [x] 8.5: Test LOW severity for low confidence contradictions
  - [x] 8.6: Test explanation generation includes document sources
  - [x] 8.7: Test matter isolation (CRITICAL - security test)
  - [x] 8.8: Integration tests verifying scorer works with classifier output

## Dev Notes

### Architecture Compliance

This story implements the **fourth and final stage** of the **Contradiction Engine** (Epic 5) pipeline:

```
STATEMENT QUERYING (5-1) ✅ → PAIR COMPARISON (5-2) ✅ → CLASSIFICATION (5-3) ✅ → SCORING (5-4) 👈
```

Follow the established engine/service/route pattern from Stories 5-1, 5-2, and 5-3.

### Critical Implementation Details

1. **Scoring Strategy: Rule-Based (100% - No LLM Required)**
   - ALL scoring is rule-based using ContradictionType and confidence
   - NO LLM calls needed - this is purely deterministic logic
   - Cost: $0 for all scoring operations
   - This story should be FAST and CHEAP

2. **Severity Scoring Rules (CRITICAL)**
   ```python
   # Rule-based severity determination
   def determine_severity(
       contradiction_type: ContradictionType,
       confidence: float
   ) -> SeverityLevel:
       # HIGH: Clear factual differences with high confidence
       if contradiction_type in [
           ContradictionType.DATE_MISMATCH,
           ContradictionType.AMOUNT_MISMATCH,
           ContradictionType.FACTUAL_CONTRADICTION
       ] and confidence >= 0.8:
           return SeverityLevel.HIGH

       # LOW: Low confidence regardless of type
       if confidence < 0.6:
           return SeverityLevel.LOW

       # MEDIUM: Everything else (semantic, or moderate confidence)
       return SeverityLevel.MEDIUM
   ```

3. **Explanation Generation Pattern**
   - NO LLM calls for explanation - use template-based generation
   - Combine existing data: contradiction_type, extracted_values, reasoning
   - Example output:
   ```
   HIGH SEVERITY: Date conflict detected between documents.

   Statement A (Loan Agreement, page 5): "The loan was disbursed on 15/01/2024"
   Statement B (Bank Statement, page 12): "Funds transferred on 15/06/2024"

   The documents disagree on the loan disbursement date by 5 months.
   This is a significant factual discrepancy that requires attorney review.
   ```

4. **Evidence Links Structure**
   ```python
   class EvidenceLink(BaseModel):
       statement_id: str       # chunk_id reference
       document_id: str        # source document UUID
       document_name: str      # filename for display
       page_number: int | None # page reference
       excerpt: str            # statement content (truncated)
       bbox_ids: list[str] = []  # bounding box references (future)
   ```

5. **Existing Code to Reuse (CRITICAL - DO NOT REINVENT)**

   | Component | Location | Purpose |
   |-----------|----------|---------|
   | `ContradictionType` enum | `app/models/contradiction.py` | Classification types |
   | `ClassifiedContradiction` | `app/models/contradiction.py` | Classification result |
   | `ClassificationResult` | `app/models/contradiction.py` | Input for scoring |
   | `ExtractedValues` | `app/models/contradiction.py` | Date/amount display |
   | `StatementPairComparison` | `app/models/contradiction.py` | Full comparison data |
   | `ContradictionClassifier` | `app/engines/contradiction/classifier.py` | Previous stage |
   | `get_contradiction_classifier` | `app/engines/contradiction/__init__.py` | Factory pattern |
   | `statement_comparisons` table | DB | Storage for results |

### File Structure Updates

Complete the contradiction engine structure:

```
backend/app/
├── engines/
│   └── contradiction/
│       ├── __init__.py           # Export new scorer
│       ├── statement_query.py    # Story 5-1 ✅
│       ├── comparator.py         # Story 5-2 ✅
│       ├── classifier.py         # Story 5-3 ✅
│       ├── prompts.py            # NO new prompts needed
│       └── scorer.py             # Story 5-4 (NEW)
├── models/
│   └── contradiction.py          # Add SeverityLevel, ScoredContradiction, EvidenceLink
└── tests/
    └── engines/
        └── contradiction/
            ├── test_classifier.py  # Story 5-3 ✅
            └── test_scorer.py      # Story 5-4 (NEW)
```

### Database Migration

**File: `supabase/migrations/20260114000006_add_severity_scoring.sql`**

```sql
-- Add severity scoring to statement_comparisons table
-- Story 5-4: Severity Scoring and Explanation

ALTER TABLE statement_comparisons
ADD COLUMN severity VARCHAR(10) CHECK (
    severity IN ('high', 'medium', 'low', NULL)
);

ALTER TABLE statement_comparisons
ADD COLUMN severity_reasoning TEXT;

ALTER TABLE statement_comparisons
ADD COLUMN explanation TEXT;

-- Index for attorney priority filtering (high severity first)
CREATE INDEX idx_statement_comparisons_severity
ON statement_comparisons(matter_id, severity)
WHERE result = 'contradiction';

-- Comment for documentation
COMMENT ON COLUMN statement_comparisons.severity IS
'Severity level: high (clear factual conflict), medium (interpretive conflict), low (uncertain conflict). NULL for non-contradictions.';

COMMENT ON COLUMN statement_comparisons.severity_reasoning IS
'Brief explanation of why this severity was assigned.';

COMMENT ON COLUMN statement_comparisons.explanation IS
'Attorney-ready natural language explanation of the contradiction with document references.';
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/` directory with `engines/`, `services/`, `security/`
- Use pytest-asyncio for async tests
- NO LLM mocking needed - all rule-based
- Include matter isolation test

**Test Files to Create:**
- `tests/engines/contradiction/test_scorer.py`

**Test Cases (minimum):**
```python
# HIGH severity: date mismatch with high confidence
@pytest.mark.asyncio
async def test_score_high_severity_date_mismatch():
    classified = ClassifiedContradiction(
        contradiction_type=ContradictionType.DATE_MISMATCH,
        # ... (from classifier output)
    )
    comparison = StatementPairComparison(
        result=ComparisonResult.CONTRADICTION,
        confidence=0.92,
        # ...
    )
    result = await scorer.score_contradiction(classified, comparison)
    assert result.scored_contradiction.severity == SeverityLevel.HIGH
    assert "date" in result.scored_contradiction.explanation.lower()

# HIGH severity: amount mismatch with high confidence
@pytest.mark.asyncio
async def test_score_high_severity_amount_mismatch():
    classified = ClassifiedContradiction(
        contradiction_type=ContradictionType.AMOUNT_MISMATCH,
        # ...
    )
    comparison = StatementPairComparison(
        result=ComparisonResult.CONTRADICTION,
        confidence=0.88,
        # ...
    )
    result = await scorer.score_contradiction(classified, comparison)
    assert result.scored_contradiction.severity == SeverityLevel.HIGH

# MEDIUM severity: semantic contradiction
@pytest.mark.asyncio
async def test_score_medium_severity_semantic():
    classified = ClassifiedContradiction(
        contradiction_type=ContradictionType.SEMANTIC_CONTRADICTION,
        # ...
    )
    comparison = StatementPairComparison(
        result=ComparisonResult.CONTRADICTION,
        confidence=0.75,
        # ...
    )
    result = await scorer.score_contradiction(classified, comparison)
    assert result.scored_contradiction.severity == SeverityLevel.MEDIUM

# LOW severity: low confidence
@pytest.mark.asyncio
async def test_score_low_severity_low_confidence():
    classified = ClassifiedContradiction(
        contradiction_type=ContradictionType.FACTUAL_CONTRADICTION,
        # ...
    )
    comparison = StatementPairComparison(
        result=ComparisonResult.CONTRADICTION,
        confidence=0.55,  # Below 0.6 threshold
        # ...
    )
    result = await scorer.score_contradiction(classified, comparison)
    assert result.scored_contradiction.severity == SeverityLevel.LOW

# Explanation includes document sources
@pytest.mark.asyncio
async def test_explanation_includes_document_sources():
    # ...
    result = await scorer.score_contradiction(classified, comparison)
    assert comparison.document_a_id in result.scored_contradiction.explanation or "Document" in result.scored_contradiction.explanation
    assert result.scored_contradiction.evidence_links is not None
    assert len(result.scored_contradiction.evidence_links) == 2
```

### Previous Story (5-3) Learnings

From the 5-3 implementation:

1. **ClassifiedContradiction is the input** - Use this model from classifier
2. **ExtractedValues already formatted** - Use for explanation display
3. **explanation field already exists** - Enhance it, don't replace
4. **Rule-based is preferred** - Story 5-4 should be 100% rule-based
5. **Factory pattern used** - Follow `get_contradiction_classifier()` pattern
6. **Cost tracking pattern** - Use dataclass for metrics (even though $0 cost)

### Git Commit Pattern

```
feat(contradiction): implement severity scoring and explanation (Story 5-4)
```

If code review requires fixes:
```
fix(review): address code review issues for Story 5-4
```

### Project Structure Notes

- Scorer logic goes in `engines/contradiction/scorer.py`
- New models in `models/contradiction.py`
- Migration in `supabase/migrations/`
- Tests in `tests/engines/contradiction/test_scorer.py`

### Integration with Story 5-3

The scorer integrates with the classifier:

```python
# Complete pipeline usage (all stages)
from app.engines.contradiction import (
    get_statement_query_engine,
    get_statement_comparator,
    get_contradiction_classifier,
    get_contradiction_scorer,  # NEW
)

# Stage 1: Query statements for entity
query_engine = get_statement_query_engine()
entity_statements = await query_engine.get_entity_statements(matter_id, entity_id)

# Stage 2: Compare statement pairs
comparator = get_statement_comparator()
comparisons = await comparator.compare_all_entity_statements(entity_statements)

# Stage 3: Classify contradictions
classifier = get_contradiction_classifier()
classifications = await classifier.classify_all(comparisons.comparisons)

# Stage 4: Score and explain contradictions
scorer = get_contradiction_scorer()  # NEW
scored = await scorer.score_all(classifications, comparisons.comparisons)

# Result: Full pipeline output with severity and explanations
for result in scored:
    print(f"{result.scored_contradiction.severity}: {result.scored_contradiction.explanation}")
```

### Severity Scoring Examples

**HIGH Severity Cases:**
```
- Date mismatch: "Loan disbursed 15/01/2024" vs "Loan disbursed 15/06/2024" (conf: 0.92)
  → HIGH: 5-month date discrepancy on same event

- Amount mismatch: "Loan amount Rs. 5 lakhs" vs "Loan amount Rs. 8 lakhs" (conf: 0.88)
  → HIGH: Rs. 3 lakh difference on same transaction

- Factual: "Mr. Sharma signed as witness" vs "Mr. Sharma was not present" (conf: 0.85)
  → HIGH: Direct factual conflict about witness
```

**MEDIUM Severity Cases:**
```
- Semantic: "The borrower was cooperative" vs "The borrower was uncooperative" (conf: 0.78)
  → MEDIUM: Semantic conflict, requires interpretation

- Date mismatch with lower confidence: Different dates (conf: 0.72)
  → MEDIUM: Clear conflict but lower confidence
```

**LOW Severity Cases:**
```
- Any type with low confidence: "Possibly mentioned different amounts" (conf: 0.52)
  → LOW: Uncertain analysis, needs attorney review

- Semantic with vague reasoning: "May imply different meanings" (conf: 0.58)
  → LOW: Too uncertain for action
```

### Explanation Template Patterns

Use these templates for generating explanations:

```python
EXPLANATION_TEMPLATES = {
    SeverityLevel.HIGH: {
        ContradictionType.DATE_MISMATCH: (
            "HIGH SEVERITY: Date conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "The documents show dates of '{date_a}' vs '{date_b}' - "
            "a {difference} discrepancy requiring immediate review."
        ),
        ContradictionType.AMOUNT_MISMATCH: (
            "HIGH SEVERITY: Amount conflict detected.\n\n"
            "Statement A ({doc_a}, page {page_a}): \"{excerpt_a}\"\n"
            "Statement B ({doc_b}, page {page_b}): \"{excerpt_b}\"\n\n"
            "The amounts of {amount_a} vs {amount_b} represent "
            "a significant financial discrepancy."
        ),
        # ... etc
    },
    SeverityLevel.MEDIUM: {
        # Similar templates with "MEDIUM SEVERITY" prefix
    },
    SeverityLevel.LOW: {
        # Similar templates with "LOW SEVERITY" prefix and "requires verification" language
    }
}
```

### Edge Cases to Handle

1. **Missing classification** - Default to MEDIUM severity
2. **Missing confidence** - Default to 0.7 (MEDIUM range)
3. **Missing document info** - Use "Unknown document" placeholder
4. **Missing page numbers** - Omit page reference from explanation
5. **Very long statement content** - Truncate excerpt to 200 chars

### Performance Considerations

- Scoring is O(n) where n = number of classifications
- No LLM calls = no latency concerns
- No external API calls = no rate limiting
- Batch processing via `score_all()` for efficiency

### References

- [Story 5-1 Implementation](./5-1-entity-grouped-statement-querying.md) - Statement models
- [Story 5-2 Implementation](./5-2-statement-pair-comparison-gpt4.md) - Comparator, evidence
- [Story 5-3 Implementation](./5-3-contradiction-type-classification.md) - Classifier, classification
- [Contradiction Models](../backend/app/models/contradiction.py) - Existing models
- [Classifier Engine](../backend/app/engines/contradiction/classifier.py) - Previous stage
- [Project Context](../project-context.md) - Implementation rules
- [Architecture: LLM Routing](../architecture.md) - Cost optimization (no LLM for scoring)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 38 unit tests pass in `tests/engines/contradiction/test_scorer.py`
- All 133 tests pass across the contradiction engine test suite

### Completion Notes List

1. **Task 1 Complete**: Added `SeverityLevel` enum, `EvidenceLink`, `ScoredContradiction`, `ScoringResult`, and `ScoringBatchResult` models to `backend/app/models/contradiction.py`

2. **Tasks 2-4 Complete**: Created `ContradictionScorer` engine in `backend/app/engines/contradiction/scorer.py` with:
   - `determine_severity()` - Rule-based severity scoring using ContradictionType and confidence
   - `score_contradiction()` - Score a single classified contradiction
   - `score_all()` - Batch scoring for post-classification processing
   - Template-based explanation generation with document references
   - Evidence link creation for both statements

3. **Task 5 Complete**: No LLM prompts needed - scorer is 100% rule-based per architecture. Template-based explanation generation implemented in `EXPLANATION_TEMPLATES` and `SEVERITY_REASONING` dictionaries.

4. **Task 6 Complete**: Updated `__init__.py` to export `ContradictionScorer` and `get_contradiction_scorer`. Complete pipeline now available:
   ```python
   from app.engines.contradiction import (
       get_statement_query_engine,
       get_statement_comparator,
       get_contradiction_classifier,
       get_contradiction_scorer,  # NEW
   )
   ```

5. **Task 7 Complete**: Created migration `supabase/migrations/20260114000006_add_severity_scoring.sql` with:
   - `severity` column (VARCHAR(10), CHECK constraint for high/medium/low)
   - `severity_reasoning` column (TEXT)
   - `explanation` column (TEXT)
   - Index for severity filtering on contradictions

6. **Task 8 Complete**: 38 comprehensive tests covering:
   - Severity determination rules (HIGH/MEDIUM/LOW thresholds)
   - Explanation generation with document sources
   - Evidence links creation
   - Batch scoring
   - Matter isolation security
   - Edge cases (truncation, missing data, boundary conditions)

### Change Log

- 2026-01-14: Story 5-4 implementation complete - Severity Scoring and Explanation

### File List

**New Files:**
- `backend/app/engines/contradiction/scorer.py` - ContradictionScorer engine (100% rule-based, $0 cost)
- `backend/tests/engines/contradiction/test_scorer.py` - 38 comprehensive tests
- `supabase/migrations/20260114000006_add_severity_scoring.sql` - Database schema updates

**Modified Files:**
- `backend/app/models/contradiction.py` - Added SeverityLevel, EvidenceLink, ScoredContradiction, ScoringResult, ScoringBatchResult models
- `backend/app/engines/contradiction/__init__.py` - Export ContradictionScorer and get_contradiction_scorer

## Manual Steps Required

### Migrations
- [ ] Run: `supabase/migrations/20260114000006_add_severity_scoring.sql`

### Environment Variables
No new environment variables required.

### Dashboard Configuration
No dashboard configuration required.

### Manual Tests
- [ ] Test HIGH severity scoring for date mismatch contradiction
- [ ] Test HIGH severity scoring for amount mismatch contradiction
- [ ] Test MEDIUM severity for semantic contradiction
- [ ] Test LOW severity for low-confidence contradictions
- [ ] Verify explanation includes document sources and page numbers
- [ ] Verify attorney can filter contradictions by severity level

## Architecture Notes

### Complete Contradiction Engine Pipeline

With Story 5-4, the Contradiction Engine is **COMPLETE**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONTRADICTION ENGINE (Epic 5)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Query    │ →  │ Compare  │ →  │ Classify │ →  │ Score    │      │
│  │ (5-1)    │    │ (5-2)    │    │ (5-3)    │    │ (5-4)    │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │             │
│   Statements     Comparisons     Classifications    Scored         │
│   by Entity      with Evidence   with Type         with Severity   │
│                                                                      │
│  Cost: $0        Cost: ~$0.03    Cost: ~$0.006     Cost: $0        │
│  (Rule-based)    (per pair)      (mostly rules)    (Rule-based)    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### API Endpoint Design Decision

**Note:** Story 5-4 implements the scorer engine but does NOT expose a dedicated API endpoint.
The complete pipeline will be exposed via Epic 6 (Engine Orchestrator).

Current usage pattern:
```python
# Programmatic usage (from orchestrator or tests):
scorer = get_contradiction_scorer()
scored = await scorer.score_all(classifications, comparisons)
```

A dedicated `/api/contradictions/{matter_id}/analyze` endpoint will be added in Epic 6
to expose the complete pipeline with all four stages.

### Data Flow to Database

The scorer updates the `statement_comparisons` table with:
- `severity`: HIGH/MEDIUM/LOW
- `severity_reasoning`: Brief justification
- `explanation`: Full attorney-ready text

This allows the frontend to:
1. Filter contradictions by severity
2. Sort by severity (HIGH first)
3. Display explanations with evidence links
