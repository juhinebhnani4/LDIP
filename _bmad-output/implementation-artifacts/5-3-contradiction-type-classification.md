# Story 5.3: Implement Contradiction Type Classification

Status: done

## Story

As an **attorney**,
I want **contradictions classified by type**,
So that **I can prioritize factual contradictions over semantic ones**.

## Acceptance Criteria

1. **Given** a contradiction is detected
   **When** classification runs
   **Then** it is assigned a type: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch

2. **Given** two statements disagree on a date
   **When** classification runs
   **Then** the type is "date_mismatch"
   **And** both dates are extracted and displayed

3. **Given** two statements disagree on an amount (loan, payment, etc.)
   **When** classification runs
   **Then** the type is "amount_mismatch"
   **And** both amounts are extracted and displayed

4. **Given** statements conflict in meaning but not on specific facts
   **When** classification runs
   **Then** the type is "semantic_contradiction"
   **And** the explanation highlights the semantic conflict

## Tasks / Subtasks

- [x] Task 1: Create classification models and enums (AC: #1)
  - [x] 1.1: Add `ContradictionType` enum: `semantic_contradiction`, `factual_contradiction`, `date_mismatch`, `amount_mismatch`
  - [x] 1.2: Create `ClassifiedContradiction` model with comparison reference, contradiction_type, extracted_values, explanation
  - [x] 1.3: Create `ClassificationResult` model for API response with classification metadata
  - [x] 1.4: Add models to `backend/app/models/contradiction.py`

- [x] Task 2: Implement classifier engine (AC: #1, #2, #3, #4)
  - [x] 2.1: Create `ContradictionClassifier` in `backend/app/engines/contradiction/classifier.py`
  - [x] 2.2: Implement `classify_contradiction()` - classify a single StatementPairComparison
  - [x] 2.3: Implement rule-based pre-classification using EvidenceType from comparator
  - [x] 2.4: Implement GPT-4 fallback for semantic classification when rule-based is uncertain
  - [x] 2.5: Extract and structure conflicting values (dates, amounts) for display

- [x] Task 3: Implement rule-based classification logic (AC: #2, #3)
  - [x] 3.1: Map EvidenceType.DATE_MISMATCH → ContradictionType.DATE_MISMATCH
  - [x] 3.2: Map EvidenceType.AMOUNT_MISMATCH → ContradictionType.AMOUNT_MISMATCH
  - [x] 3.3: Map EvidenceType.FACTUAL_CONFLICT → ContradictionType.FACTUAL_CONTRADICTION
  - [x] 3.4: Map EvidenceType.SEMANTIC_CONFLICT → ContradictionType.SEMANTIC_CONTRADICTION
  - [x] 3.5: Handle edge cases where evidence type doesn't directly map (use reasoning analysis)

- [x] Task 4: Update prompts for classification enhancement (AC: #4)
  - [x] 4.1: Add `CLASSIFICATION_ENHANCEMENT_PROMPT` to `prompts.py` for semantic analysis
  - [x] 4.2: Prompt must extract semantic conflict explanation when type is semantic
  - [x] 4.3: Ensure extracted values are formatted for attorney display

- [x] Task 5: Integrate classifier into comparison pipeline (AC: #1)
  - [x] 5.1: Classifier available via `classify_all()` for post-processing comparisons (Option A per Dev Notes)
  - [x] 5.2: Add `contradiction_type` field to `StatementPairComparison` model
  - [x] 5.3: Classification callable via `classifier.classify_all(comparisons)` after comparison batch
  - [x] 5.4: Store classification in `statement_comparisons` table via migration

- [x] Task 6: Update database schema (AC: #1, #2, #3)
  - [x] 6.1: Add `contradiction_type` column to `statement_comparisons` table
  - [x] 6.2: Add `extracted_values` JSONB column for structured date/amount display
  - [x] 6.3: Create migration file: `supabase/migrations/20260114000005_add_contradiction_classification.sql`

- [x] Task 7: Write comprehensive tests (AC: #1, #2, #3, #4)
  - [x] 7.1: Unit tests for `ContradictionClassifier` with mocked inputs
  - [x] 7.2: Test date_mismatch classification with Indian date formats
  - [x] 7.3: Test amount_mismatch classification with Indian amount formats (lakhs, crores)
  - [x] 7.4: Test semantic_contradiction classification
  - [x] 7.5: Test factual_contradiction classification
  - [x] 7.6: Integration tests verifying classifier works with comparator output
  - [x] 7.7: Test matter isolation (CRITICAL - security test)

## Dev Notes

### Architecture Compliance

This story implements the third stage of the **Contradiction Engine** (Epic 5) pipeline:

```
STATEMENT QUERYING (5-1) ✅ → PAIR COMPARISON (5-2) ✅ → CLASSIFICATION (5-3) 👈 → SCORING (5-4)
```

Follow the established engine/service/route pattern from Stories 5-1 and 5-2.

### Critical Implementation Details

1. **Classification Strategy: Rule-Based First, LLM Fallback**
   - PREFER rule-based classification from existing `EvidenceType` (already extracted in 5-2)
   - EvidenceType → ContradictionType mapping is direct and cost-free
   - Only use GPT-4 for ambiguous cases (e.g., EvidenceType.NONE but result is contradiction)
   - This follows cost optimization rules: rule-based where possible

2. **EvidenceType to ContradictionType Mapping**
   ```python
   CLASSIFICATION_MAP = {
       EvidenceType.DATE_MISMATCH: ContradictionType.DATE_MISMATCH,
       EvidenceType.AMOUNT_MISMATCH: ContradictionType.AMOUNT_MISMATCH,
       EvidenceType.FACTUAL_CONFLICT: ContradictionType.FACTUAL_CONTRADICTION,
       EvidenceType.SEMANTIC_CONFLICT: ContradictionType.SEMANTIC_CONTRADICTION,
   }
   ```

3. **Existing Evidence Data from Story 5-2**
   - `StatementPairComparison.evidence` already contains:
     - `type`: EvidenceType enum (date_mismatch, amount_mismatch, etc.)
     - `value_a`: Extracted value from statement A
     - `value_b`: Extracted value from statement B
   - Reuse this data - DO NOT re-extract values

4. **When to Use LLM Classification**
   - If `evidence.type == EvidenceType.NONE` but `result == ComparisonResult.CONTRADICTION`
   - If reasoning suggests a contradiction type not captured by evidence type
   - Use GPT-4 with targeted prompt to determine classification

5. **Extracted Values Display Format**
   - Dates: Show both original format AND normalized ISO format
   - Amounts: Show both original format AND normalized numeric value
   - Example:
   ```json
   {
     "date_a": {"original": "15/01/2024", "normalized": "2024-01-15"},
     "date_b": {"original": "15/06/2024", "normalized": "2024-06-15"}
   }
   ```

### LLM Routing Rules (CRITICAL)

**MINIMIZE LLM usage in this story.** Most classification should be rule-based:

| Scenario | Approach | Cost |
|----------|----------|------|
| Evidence type matches contradiction type | Rule-based mapping | $0 |
| Evidence type is NONE but contradiction detected | GPT-4 classification | ~$0.03 |
| Semantic conflict needs explanation | GPT-4 enhancement | ~$0.03 |

Expected: 80%+ rule-based, <20% LLM calls.

### Existing Code to Reuse (CRITICAL - DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `EvidenceType` enum | `app/models/contradiction.py` | Already defines date_mismatch, amount_mismatch, etc. |
| `ContradictionEvidence` | `app/models/contradiction.py` | Has value_a, value_b extracted |
| `StatementPairComparison` | `app/models/contradiction.py` | Contains evidence and result |
| `ComparisonResult` enum | `app/models/contradiction.py` | CONTRADICTION, CONSISTENT, etc. |
| `StatementComparator` | `app/engines/contradiction/comparator.py` | Returns comparisons with evidence |
| Comparison prompts | `app/engines/contradiction/prompts.py` | Existing prompt patterns |
| `statement_comparisons` table | DB | Already stores comparison results |

### File Structure Updates

Extend the contradiction engine structure:

```
backend/app/
├── engines/
│   └── contradiction/
│       ├── __init__.py           # Export new classifier
│       ├── statement_query.py    # Story 5-1 ✅
│       ├── comparator.py         # Story 5-2 ✅
│       ├── prompts.py            # Add classification prompt
│       ├── classifier.py         # Story 5-3 (NEW)
│       └── scorer.py             # Story 5-4 (future)
├── models/
│   └── contradiction.py          # Add ContradictionType enum, ClassifiedContradiction
└── tests/
    └── engines/
        └── contradiction/
            └── test_classifier.py  # Story 5-3 tests (NEW)
```

### Database Migration

**File: `supabase/migrations/20260114000005_add_contradiction_classification.sql`**

```sql
-- Add contradiction type to statement_comparisons table
ALTER TABLE statement_comparisons
ADD COLUMN contradiction_type VARCHAR(30) CHECK (
    contradiction_type IN (
        'semantic_contradiction',
        'factual_contradiction',
        'date_mismatch',
        'amount_mismatch',
        NULL
    )
);

-- Add extracted values for attorney display
ALTER TABLE statement_comparisons
ADD COLUMN extracted_values JSONB DEFAULT '{}'::jsonb;

-- Index for filtering by type (attorney prioritization use case)
CREATE INDEX idx_statement_comparisons_type
ON statement_comparisons(matter_id, contradiction_type)
WHERE result = 'contradiction';

-- Comment for documentation
COMMENT ON COLUMN statement_comparisons.contradiction_type IS
'Classification of contradiction: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch. NULL for non-contradictions.';

COMMENT ON COLUMN statement_comparisons.extracted_values IS
'Structured values for attorney display. Format: {"value_a": {"original": "15/01/2024", "normalized": "2024-01-15"}, "value_b": {...}}';
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/` directory with `engines/`, `services/`, `security/`
- Use pytest-asyncio for async tests
- Mock GPT-4 if LLM fallback is invoked (never call real API in tests)
- Include matter isolation test

**Test Files to Create:**
- `tests/engines/contradiction/test_classifier.py`

**Test Cases (minimum):**
```python
# Date mismatch classification
@pytest.mark.asyncio
async def test_classify_date_mismatch():
    comparison = StatementPairComparison(
        evidence=ContradictionEvidence(
            type=EvidenceType.DATE_MISMATCH,
            value_a="15/01/2024",
            value_b="15/06/2024"
        ),
        result=ComparisonResult.CONTRADICTION,
        ...
    )
    result = await classifier.classify_contradiction(comparison)
    assert result.contradiction_type == ContradictionType.DATE_MISMATCH
    assert result.extracted_values["value_a"]["original"] == "15/01/2024"

# Amount mismatch with Indian formats
@pytest.mark.asyncio
async def test_classify_amount_mismatch_lakhs():
    comparison = StatementPairComparison(
        evidence=ContradictionEvidence(
            type=EvidenceType.AMOUNT_MISMATCH,
            value_a="5 lakhs",
            value_b="8 lakhs"
        ),
        result=ComparisonResult.CONTRADICTION,
        ...
    )
    result = await classifier.classify_contradiction(comparison)
    assert result.contradiction_type == ContradictionType.AMOUNT_MISMATCH
    assert result.extracted_values["value_a"]["normalized"] == "500000"

# Semantic classification (no explicit values)
@pytest.mark.asyncio
async def test_classify_semantic_contradiction():
    comparison = StatementPairComparison(
        evidence=ContradictionEvidence(
            type=EvidenceType.SEMANTIC_CONFLICT,
            value_a=None,
            value_b=None
        ),
        result=ComparisonResult.CONTRADICTION,
        ...
    )
    result = await classifier.classify_contradiction(comparison)
    assert result.contradiction_type == ContradictionType.SEMANTIC_CONTRADICTION
```

### Previous Story (5-2) Learnings

From the 5-2 implementation:

1. **EvidenceType already extracted** - Don't re-extract, reuse from comparison result
2. **value_a/value_b already present** - Use ContradictionEvidence fields directly
3. **Reasoning captured** - Chain-of-thought reasoning can inform classification
4. **44 tests pattern** - Maintain similar comprehensive test coverage
5. **AsyncMock for async methods** - Use proper async mocking patterns
6. **Cost tracking** - Only track LLM costs if LLM fallback is used

### Git Commit Pattern

```
feat(contradiction): implement contradiction type classification (Story 5-3)
```

If code review requires fixes:
```
fix(review): address code review issues for Story 5-3
```

### Project Structure Notes

- Classification logic goes in `engines/contradiction/classifier.py`
- New enum and models in `models/contradiction.py`
- Migration in `supabase/migrations/`
- Tests in `tests/engines/contradiction/test_classifier.py`

### Integration with Story 5-2

The classifier integrates with the existing comparator:

```python
# Option A: Post-process comparisons (recommended for this story)
comparisons = await comparator.compare_all_entity_statements(entity_statements)
classified = [classifier.classify_contradiction(c) for c in comparisons.comparisons
              if c.result == ComparisonResult.CONTRADICTION]

# Option B: Integrate into comparator._parse_comparison_response()
# This adds classification inline during comparison parsing
```

**Recommendation:** Start with Option A (post-processing) for cleaner separation.
Can integrate into comparator in future optimization if needed.

### Edge Cases to Handle

1. **EvidenceType.NONE with contradiction** - Analyze reasoning to determine type
2. **Multiple potential types** - Prioritize: date_mismatch > amount_mismatch > factual > semantic
3. **Inconsistent evidence** - e.g., reasoning says date but evidence says amount → trust evidence type
4. **Non-contradiction results** - Skip classification, return None for contradiction_type

### References

- [Story 5-1 Implementation](./5-1-entity-grouped-statement-querying.md) - Statement models
- [Story 5-2 Implementation](./5-2-statement-pair-comparison-gpt4.md) - Comparator, evidence extraction
- [Contradiction Models](../backend/app/models/contradiction.py) - Existing models
- [Comparator Engine](../backend/app/engines/contradiction/comparator.py) - Evidence extraction
- [Project Context](../project-context.md) - Implementation rules
- [Architecture: LLM Routing](../architecture.md) - Cost optimization rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passing

### Completion Notes List

- Implemented rule-based classification mapping EvidenceType to ContradictionType (80%+ of cases)
- Added GPT-4 fallback for ambiguous cases (EvidenceType.NONE)
- Created comprehensive Indian format normalization (dates: DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY; amounts: lakhs, crores, Rs.)
- All 37 new classifier tests pass + 56 existing tests = 93 total tests
- Matter isolation verified through security test
- LLM cost optimization: rule-based = $0, LLM fallback ~$0.03 per call

### File List

**Created:**
- `backend/app/engines/contradiction/classifier.py` - ContradictionClassifier engine (~450 lines)
- `backend/tests/engines/contradiction/test_classifier.py` - Comprehensive tests (37 tests)
- `supabase/migrations/20260114000005_add_contradiction_classification.sql` - Database migration

**Modified:**
- `backend/app/models/contradiction.py` - Added ContradictionType enum, ExtractedValue, ExtractedValues, ClassifiedContradiction, ClassificationResult models + contradiction_type/extracted_values fields to StatementPairComparison
- `backend/app/engines/contradiction/__init__.py` - Export ContradictionClassifier, get_contradiction_classifier
- `backend/app/engines/contradiction/prompts.py` - Added CLASSIFICATION_ENHANCEMENT_SYSTEM_PROMPT, CLASSIFICATION_ENHANCEMENT_USER_PROMPT, format_classification_prompt(), validate_classification_response()

## Manual Steps Required

### Migrations
- [ ] Run: `supabase/migrations/20260114000005_add_contradiction_classification.sql`

### Environment Variables
No new environment variables required.

### Dashboard Configuration
No dashboard configuration required.

### Manual Tests
- [ ] Test classification with date mismatch contradiction (DD/MM/YYYY format)
- [ ] Test classification with amount mismatch contradiction (lakhs/crores format)
- [ ] Test semantic contradiction classification
- [ ] Verify attorney can filter contradictions by type

## Architecture Notes

### API Endpoint Design Decision
**Note:** Story 5-3 implements the classifier engine but does NOT expose a dedicated API endpoint.
Classification is designed to be called programmatically after comparisons:

```python
# Usage pattern (from application code):
comparisons = await comparator.compare_all_entity_statements(entity_statements)
classifier = get_contradiction_classifier()
classified = await classifier.classify_all(comparisons.comparisons)
```

A dedicated `/api/contradictions/classify` endpoint may be added in Story 5-4 (Severity Scoring)
or as part of the orchestration layer (Epic 6) when the full contradiction pipeline is exposed.

### Integration Path
The classification data flows into the database via the `statement_comparisons` table columns:
- `contradiction_type`: Classification result
- `extracted_values`: Structured date/amount values for attorney display

This allows attorneys to filter contradictions by type without a dedicated classification API.
