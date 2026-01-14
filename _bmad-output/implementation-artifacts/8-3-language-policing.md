# Story 8.3: Implement Language Policing

Status: dev-complete

## Story

As an **attorney**,
I want **all LLM outputs sanitized of legal conclusions**,
So that **I never see unprofessional language in LDIP responses**.

## Acceptance Criteria

1. **Given** LLM output contains "violated Section X"
   **When** policing runs
   **Then** it is replaced with "affected by Section X"

2. **Given** LLM output contains "defendant is guilty"
   **When** policing runs
   **Then** it is replaced with "defendant's liability regarding"

3. **Given** LLM output contains "the court will rule"
   **When** policing runs
   **Then** it is replaced with "the court may consider"

4. **Given** LLM output contains "proves that"
   **When** policing runs
   **Then** it is replaced with "suggests that"

5. **Given** regex replacements complete
   **When** subtle policing runs via GPT-4o-mini
   **Then** remaining conclusions are removed or rephrased
   **And** the final output is 100% sanitized

6. **Given** text is a direct quote from a source document (indicated by quotation marks or explicit citation reference)
   **When** language policing runs
   **Then** the original quoted text is preserved verbatim
   **And** a note indicates "Direct quote from [document name, page X]"
   **And** no sanitization is applied to the quoted content

## Tasks / Subtasks

- [x] Task 1: Extend Safety Models (AC: #1-5)
  - [x] 1.1: Add `LanguagePolicingResult` model to `backend/app/models/safety.py` with fields: original_text, sanitized_text, replacements_made, llm_policing_applied, quotes_preserved, sanitization_time_ms, llm_cost_usd
  - [x] 1.2: Add `ReplacementRecord` model with fields: original_phrase, replacement_phrase, position_start, position_end, rule_id
  - [x] 1.3: Add `QuotePreservation` model with fields: quoted_text, source_document, page_number, start_pos, end_pos

- [x] Task 2: Create Regex Replacement Patterns (AC: #1-4)
  - [x] 2.1: Create `backend/app/services/safety/policing_patterns.py`
  - [x] 2.2: Implement conclusion patterns: "violated Section X" → "affected by Section X"
  - [x] 2.3: Implement guilt patterns: "defendant is guilty" → "defendant's liability regarding"
  - [x] 2.4: Implement prediction patterns: "the court will rule/decide/hold" → "the court may consider"
  - [x] 2.5: Implement proof patterns: "proves that" → "suggests that", "establishes that" → "indicates that"
  - [x] 2.6: Implement definitive patterns: "clearly shows" → "appears to show", "demonstrates" → "may indicate"
  - [x] 2.7: Implement liability patterns: "is liable for" → "regarding potential liability for", "is responsible for" → "regarding responsibility for"
  - [x] 2.8: Add pattern metadata (rule_id, explanation for audit)

- [x] Task 3: Create Quote Detection Logic (AC: #6)
  - [x] 3.1: Create `backend/app/services/safety/quote_detector.py`
  - [x] 3.2: Implement `detect_quotes()` to find quoted text (text in "quotes" or 'single quotes')
  - [x] 3.3: Implement `detect_citations()` to find explicit citation references ("...as stated in [Document, p. X]")
  - [x] 3.4: Implement `mark_protected_regions()` to exclude quotes from sanitization
  - [x] 3.5: Implement `format_quote_attribution()` for preserved quote notes

- [x] Task 4: Create LanguagePolicingService (AC: #1-4)
  - [x] 4.1: Create `backend/app/services/safety/language_policing.py`
  - [x] 4.2: Implement `LanguagePolicingService` class with lazy initialization
  - [x] 4.3: Implement `sanitize_text()` method - fast-path regex replacements
  - [x] 4.4: Implement `_apply_regex_replacements()` - apply all patterns, track replacements
  - [x] 4.5: Implement `_preserve_quotes()` - exclude quoted text from sanitization
  - [x] 4.6: Return LanguagePolicingResult with timing metrics

- [x] Task 5: Create GPT-4o-mini Subtle Policing (AC: #5)
  - [x] 5.1: Add `SUBTLE_POLICING_SYSTEM_PROMPT` to `backend/app/services/safety/prompts.py`
  - [x] 5.2: Add `SUBTLE_POLICING_USER_PROMPT` template for output text analysis
  - [x] 5.3: Implement `subtle_polish()` in LanguagePolicingService - call GPT-4o-mini for remaining conclusions
  - [x] 5.4: Ensure LLM removes/rephrases subtle legal conclusions missed by regex
  - [x] 5.5: Track LLM cost for policing operations

- [x] Task 6: Create Combined LanguagePolice Service (AC: #1-6)
  - [x] 6.1: Create `backend/app/services/safety/language_police.py`
  - [x] 6.2: Implement `LanguagePolice` class combining regex + LLM policing
  - [x] 6.3: Implement `police_output()` pipeline: preserve quotes → regex → LLM polish
  - [x] 6.4: Return comprehensive LanguagePolicingResult
  - [x] 6.5: Implement singleton factory `get_language_police()`

- [x] Task 7: Integrate with Engine Outputs (AC: #1-6)
  - [x] 7.1: Import LanguagePolice into `backend/app/engines/orchestrator/aggregator.py`
  - [x] 7.2: Add LanguagePolice as aggregator dependency
  - [x] 7.3: Call `language_police.police_output()` on EVERY engine synthesis response BEFORE returning to user
  - [x] 7.4: Log sanitization metrics to audit trail

- [x] Task 8: Add Configuration Settings (AC: #1-6)
  - [x] 8.1: Add `language_policing_enabled: bool = True` to `backend/app/core/config.py`
  - [x] 8.2: Add `policing_llm_enabled: bool = True` for subtle policing feature flag
  - [x] 8.3: Add `policing_llm_timeout: float = 10.0` timeout setting

- [x] Task 9: Create Unit Tests (AC: #1-4)
  - [x] 9.1: Create `backend/tests/services/safety/test_policing_patterns.py`
  - [x] 9.2: Test "violated Section 138" → "affected by Section 138"
  - [x] 9.3: Test "defendant is guilty" → "defendant's liability regarding"
  - [x] 9.4: Test "the court will rule" → "the court may consider"
  - [x] 9.5: Test "proves that the contract" → "suggests that the contract"
  - [x] 9.6: Test multiple replacements in single text
  - [x] 9.7: Test case insensitivity
  - [x] 9.8: Test performance (< 5ms for regex policing)

- [x] Task 10: Create Quote Preservation Tests (AC: #6)
  - [x] 10.1: Create `backend/tests/services/safety/test_quote_preservation.py`
  - [x] 10.2: Test quoted text preserved: `"The defendant violated the agreement"` stays unchanged
  - [x] 10.3: Test citation reference preserved: `As stated in Exhibit A, page 5`
  - [x] 10.4: Test non-quoted text still sanitized around quotes
  - [x] 10.5: Test nested quotes handling
  - [x] 10.6: Test quote attribution formatting

- [x] Task 11: Create LLM Policing Tests (AC: #5)
  - [x] 11.1: Create `backend/tests/services/safety/test_language_police.py`
  - [x] 11.2: Test subtle conclusion removal (mock LLM response)
  - [x] 11.3: Test regex → LLM pipeline (regex first, LLM polish)
  - [x] 11.4: Test LLM timeout handling (fail gracefully, use regex-only result)
  - [x] 11.5: Test cost tracking accuracy
  - [x] 11.6: Test feature flag disabling LLM policing

- [x] Task 12: Create Integration Tests (AC: #1-6)
  - [x] 12.1: Create `backend/tests/engines/orchestrator/test_aggregator_policing.py`
  - [x] 12.2: Test full pipeline: quote detection → regex → LLM → final output
  - [x] 12.3: Test engine output sanitization in aggregator
  - [x] 12.4: Test 100% sanitization requirement (no legal conclusions escape)

- [x] Task 13: Update Module Exports
  - [x] 13.1: Update `backend/app/services/safety/__init__.py` with new exports
  - [x] 13.2: Export LanguagePolicingService, LanguagePolice, get_language_police
  - [x] 13.3: Export new models from safety module

## Dev Notes

### Architecture Compliance

This story implements **Language Policing** - the OUTPUT sanitization layer of the Safety Layer (Epic 8):

```
USER QUERY → [REGEX CHECK] → [GPT-4o-mini CHECK] → ORCHESTRATOR → ENGINES → [LANGUAGE POLICING] → RESPONSE
              ^^^^^^^^^^^    ^^^^^^^^^^^^^^^^^^                               ^^^^^^^^^^^^^^^^^^^^^
              Story 8-1      Story 8-2                                        Story 8-3 (this)
```

Two-phase output sanitization design:
- **Phase 1**: Fast regex patterns replace obvious legal conclusions (< 5ms)
- **Phase 2**: GPT-4o-mini catches/rewrites subtle conclusions missed by regex

This satisfies:
- **FR9**: Language Policing - Sanitize ALL engine outputs before user display
- **NFR22**: 0 legal conclusions escape language policing (100% sanitized)
- **Architecture Decision**: Safety Layer wraps all engine outputs before user display

### Critical Implementation Details

1. **GPT-4o-mini Model Selection (Same as Story 8-2)**

   Per LLM routing rules, use GPT-4o-mini for safety/policing tasks:
   ```python
   # Story 8-3: Policing is a text transformation task
   # GPT-4o-mini is sufficient - cheaper than GPT-4, fast, capable
   MODEL_NAME = "gpt-4o-mini"  # NOT gpt-4
   ```

   **Cost comparison (same as Story 8-2):**
   - GPT-4o-mini: ~$0.00015/1K input tokens, ~$0.0006/1K output tokens
   - GPT-4: ~$0.03/1K input tokens, ~$0.06/1K output tokens
   - **200x cheaper for input, 100x cheaper for output**

2. **Regex Pattern Categories for Language Policing**

   ```python
   # Category 1: Legal Conclusion Patterns
   CONCLUSION_PATTERNS = [
       # "violated Section X" → "affected by Section X"
       (r"violated\s+(section|act|rule|regulation|clause)\s+(\d+)", r"affected by \1 \2"),
       # "breached the contract" → "regarding the contract terms"
       (r"breached\s+(the\s+)?(contract|agreement)", r"regarding \1\2 terms"),
   ]

   # Category 2: Guilt/Liability Patterns
   GUILT_PATTERNS = [
       # "defendant is guilty" → "defendant's liability regarding"
       (r"(defendant|accused|respondent)\s+is\s+guilty", r"\1's liability regarding"),
       # "plaintiff is entitled" → "plaintiff's potential entitlement"
       (r"(plaintiff|petitioner)\s+is\s+entitled", r"\1's potential entitlement"),
   ]

   # Category 3: Prediction Patterns
   PREDICTION_PATTERNS = [
       # "the court will rule/decide/hold" → "the court may consider"
       (r"(the\s+)?court\s+will\s+(rule|decide|hold|find|grant|deny)", r"\1court may consider"),
       # "judge will likely" → "judge may"
       (r"judge\s+will\s+likely", r"judge may"),
   ]

   # Category 4: Proof/Evidence Patterns
   PROOF_PATTERNS = [
       # "proves that" → "suggests that"
       (r"proves\s+that", r"suggests that"),
       # "establishes that" → "indicates that"
       (r"establishes\s+that", r"indicates that"),
       # "demonstrates that" → "may indicate that"
       (r"demonstrates\s+that", r"may indicate that"),
       # "clearly shows" → "appears to show"
       (r"clearly\s+shows", r"appears to show"),
   ]

   # Category 5: Definitive Statement Patterns
   DEFINITIVE_PATTERNS = [
       # "is liable for" → "regarding potential liability for"
       (r"is\s+liable\s+for", r"regarding potential liability for"),
       # "is responsible for" → "regarding responsibility for"
       (r"is\s+responsible\s+for", r"regarding responsibility for"),
       # "must pay" → "may be required to pay"
       (r"must\s+pay", r"may be required to pay"),
   ]
   ```

3. **Quote Detection and Preservation**

   ```python
   import re
   from typing import NamedTuple

   class ProtectedRegion(NamedTuple):
       """Region of text protected from sanitization."""
       start: int
       end: int
       text: str
       source: str | None  # Document attribution if available
       page: int | None

   class QuoteDetector:
       """Detect and protect quoted text from sanitization.

       Story 8-3: AC #6 - Preserve direct quotes from documents.

       Patterns detected:
       - Double-quoted text: "exact quote from document"
       - Single-quoted text: 'exact quote'
       - Citation references: As stated in [Document, p. X]
       """

       # Quote patterns
       DOUBLE_QUOTE_PATTERN = re.compile(r'"([^"]+)"')
       SINGLE_QUOTE_PATTERN = re.compile(r"'([^']+)'")
       CITATION_PATTERN = re.compile(
           r'(?:as\s+stated\s+in|according\s+to|per|see)\s+'
           r'(?:\[([^\]]+)\]|\(([^)]+)\)|([A-Z][^,]+),?\s*(?:p(?:age)?\.?\s*(\d+)))',
           re.IGNORECASE
       )

       def detect_protected_regions(self, text: str) -> list[ProtectedRegion]:
           """Find all regions that should be protected from sanitization.

           Args:
               text: Full text to analyze.

           Returns:
               List of ProtectedRegion objects marking quote boundaries.
           """
           regions = []

           # Find double-quoted text
           for match in self.DOUBLE_QUOTE_PATTERN.finditer(text):
               regions.append(ProtectedRegion(
                   start=match.start(),
                   end=match.end(),
                   text=match.group(0),
                   source=None,
                   page=None,
               ))

           # Find citation references with context
           for match in self.CITATION_PATTERN.finditer(text):
               source = match.group(1) or match.group(2) or match.group(3)
               page = int(match.group(4)) if match.group(4) else None
               regions.append(ProtectedRegion(
                   start=match.start(),
                   end=match.end(),
                   text=match.group(0),
                   source=source,
                   page=page,
               ))

           return sorted(regions, key=lambda r: r.start)
   ```

4. **LanguagePolicingService Pattern**

   Follow the pattern from `GuardrailService` (Story 8-1) and `SubtleViolationDetector` (Story 8-2):

   ```python
   import re
   import time
   import threading

   import structlog

   from app.models.safety import LanguagePolicingResult, ReplacementRecord
   from app.services.safety.policing_patterns import get_policing_patterns
   from app.services.safety.quote_detector import QuoteDetector, ProtectedRegion

   logger = structlog.get_logger(__name__)


   class LanguagePolicingService:
       """Regex-based language policing for LLM outputs.

       Story 8-3: Fast-path regex replacement of legal conclusions.

       This is Phase 1 of output sanitization:
       1. Detect and mark protected regions (quotes)
       2. Apply regex replacements to unprotected text
       3. Combine with protected regions
       4. Return sanitized text with replacement records

       Example:
           >>> service = get_language_policing_service()
           >>> result = service.sanitize_text(
           ...     "The evidence proves that defendant violated Section 138."
           ... )
           >>> result.sanitized_text
           "The evidence suggests that defendant affected by Section 138."
       """

       def __init__(self) -> None:
           """Initialize language policing service."""
           self._patterns = []
           self._quote_detector = QuoteDetector()
           self._load_patterns()
           logger.info(
               "language_policing_service_initialized",
               pattern_count=len(self._patterns),
           )

       def _load_patterns(self) -> None:
           """Load compiled regex patterns."""
           self._patterns = get_policing_patterns()

       def sanitize_text(self, text: str) -> LanguagePolicingResult:
           """Apply regex sanitization to text.

           Story 8-3: AC #1-4 - Regex replacements.

           Args:
               text: LLM output text to sanitize.

           Returns:
               LanguagePolicingResult with sanitized text and metadata.
           """
           start_time = time.perf_counter()

           # Step 1: Detect protected regions (quotes)
           protected_regions = self._quote_detector.detect_protected_regions(text)

           # Step 2: Apply replacements to unprotected text
           sanitized_text, replacements = self._apply_replacements(
               text, protected_regions
           )

           check_time_ms = (time.perf_counter() - start_time) * 1000

           return LanguagePolicingResult(
               original_text=text,
               sanitized_text=sanitized_text,
               replacements_made=replacements,
               quotes_preserved=[r.text for r in protected_regions],
               llm_policing_applied=False,
               sanitization_time_ms=check_time_ms,
           )

       def _apply_replacements(
           self,
           text: str,
           protected_regions: list[ProtectedRegion],
       ) -> tuple[str, list[ReplacementRecord]]:
           """Apply regex replacements avoiding protected regions.

           Args:
               text: Original text.
               protected_regions: Regions to skip.

           Returns:
               Tuple of (sanitized_text, replacement_records).
           """
           replacements = []

           # Build mask of protected positions
           protected_positions = set()
           for region in protected_regions:
               for i in range(region.start, region.end):
                   protected_positions.add(i)

           # Apply each pattern
           result_text = text
           offset = 0  # Track position shifts from replacements

           for pattern_obj in self._patterns:
               for match in pattern_obj.regex.finditer(text):
                   # Skip if match overlaps protected region
                   if any(i in protected_positions for i in range(match.start(), match.end())):
                       continue

                   # Calculate adjusted position
                   adj_start = match.start() + offset
                   adj_end = match.end() + offset

                   # Get replacement text
                   replacement = pattern_obj.regex.sub(
                       pattern_obj.replacement,
                       match.group(0),
                   )

                   # Apply replacement
                   result_text = (
                       result_text[:adj_start] +
                       replacement +
                       result_text[adj_end:]
                   )

                   # Track replacement
                   replacements.append(ReplacementRecord(
                       original_phrase=match.group(0),
                       replacement_phrase=replacement,
                       position_start=match.start(),
                       position_end=match.end(),
                       rule_id=pattern_obj.rule_id,
                   ))

                   # Update offset
                   offset += len(replacement) - (match.end() - match.start())

           return result_text, replacements
   ```

5. **Subtle Policing System Prompt**

   ```python
   SUBTLE_POLICING_SYSTEM_PROMPT = """You are a legal language editor for LDIP (Legal Document Intelligence Platform).

   Your task is to identify and rephrase any remaining legal conclusions in the text that were not caught by automated regex patterns.

   CRITICAL RULES:
   1. LDIP can ONLY present factual observations from documents
   2. LDIP CANNOT make legal conclusions, predictions, or advice
   3. ALL definitive legal language must be softened

   TRANSFORM these patterns:
   - Definitive statements → Observations ("is guilty" → "may face liability regarding")
   - Predictions → Possibilities ("will win" → "may have grounds for")
   - Conclusions → Suggestions ("this proves" → "this may indicate")
   - Advice → Information ("you should" → "options include")

   PRESERVE:
   - Direct quotes (text in quotation marks)
   - Citation references
   - Factual statements without legal conclusions
   - Numerical data and dates

   Respond with JSON:
   {
       "sanitized_text": "The fully sanitized text",
       "changes_made": ["list of specific changes"],
       "confidence": 0.0-1.0
   }

   If text is already properly sanitized, return it unchanged with empty changes_made array.
   """

   SUBTLE_POLICING_USER_PROMPT = """Review and sanitize this text for any remaining legal conclusions:

   Text: "{text}"

   Respond with JSON containing the sanitized version."""
   ```

6. **LanguagePolice Combined Service**

   ```python
   class LanguagePolice:
       """Combined language police with regex + LLM polishing.

       Story 8-3: Full output sanitization pipeline.

       Pipeline:
       1. Quote detection and protection
       2. Fast regex replacements (< 5ms)
       3. If enabled, LLM polish for subtle conclusions (~500-2000ms)

       Example:
           >>> police = get_language_police()
           >>> result = await police.police_output(
           ...     "The evidence proves defendant is guilty of violating Section 138."
           ... )
           >>> result.sanitized_text
           "The evidence suggests defendant may face liability regarding Section 138."
       """

       def __init__(
           self,
           policing_service: LanguagePolicingService | None = None,
           subtle_polisher: SubtlePolicingService | None = None,
       ) -> None:
           """Initialize language police."""
           self._policing_service = policing_service or get_language_policing_service()
           self._subtle_polisher = subtle_polisher
           self._llm_enabled = get_settings().policing_llm_enabled

       async def police_output(self, text: str) -> LanguagePolicingResult:
           """Apply full language policing pipeline.

           Story 8-3: AC #1-6 - Complete sanitization.

           Args:
               text: LLM output to sanitize.

           Returns:
               LanguagePolicingResult with fully sanitized text.
           """
           # Phase 1: Fast regex policing
           result = self._policing_service.sanitize_text(text)

           # Phase 2: LLM polish if enabled
           if not self._llm_enabled:
               return result

           try:
               polished = await self._subtle_polisher.polish_text(
                   result.sanitized_text
               )
               return LanguagePolicingResult(
                   original_text=text,
                   sanitized_text=polished.text,
                   replacements_made=result.replacements_made + polished.changes,
                   quotes_preserved=result.quotes_preserved,
                   llm_policing_applied=True,
                   sanitization_time_ms=result.sanitization_time_ms + polished.time_ms,
                   llm_cost_usd=polished.cost_usd,
               )
           except Exception as e:
               # LLM failures should NOT break output - use regex-only result
               logger.warning(
                   "policing_llm_failed",
                   error=str(e),
                   fallback="regex_only",
               )
               return result
   ```

7. **Integration with ResultAggregator**

   ```python
   # In aggregator.py - aggregate_results method
   async def aggregate_results(
       self,
       engine_results: list[EngineResult],
       intent: IntentAnalysisResult,
   ) -> OrchestratorResult:
       """Aggregate engine results into unified response.

       Story 6-2: Result aggregation.
       Story 8-3: Language policing on synthesized output.
       """
       # ... existing aggregation logic ...

       # Synthesize response text
       synthesis = await self._synthesize_response(engine_results, intent)

       # Story 8-3: Apply language policing BEFORE returning to user
       policing_result = await self._language_police.police_output(synthesis.text)

       return OrchestratorResult(
           # ... other fields ...
           synthesis=policing_result.sanitized_text,  # SANITIZED, not raw
           policing_metadata={
               "replacements_count": len(policing_result.replacements_made),
               "quotes_preserved": len(policing_result.quotes_preserved),
               "llm_policing_applied": policing_result.llm_policing_applied,
               "sanitization_time_ms": policing_result.sanitization_time_ms,
           },
       )
   ```

### Existing Code to Reuse (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `GuardrailService` | `services/safety/guardrail.py` | Pattern for regex-based service (Story 8-1) |
| `SubtleViolationDetector` | `services/safety/subtle_detector.py` | Pattern for LLM-based service (Story 8-2) |
| `SafetyGuard` | `services/safety/safety_guard.py` | Pattern for combined regex+LLM service |
| `SUBTLE_DETECTION_*` | `services/safety/prompts.py` | Pattern for LLM prompts |
| `ViolationType` | `models/safety.py` | Existing violation types |
| `AsyncOpenAI` | `openai` | Async OpenAI client |
| `get_settings()` | `core/config.py` | Configuration access |
| `structlog` | All modules | Structured logging |
| `ResultAggregator` | `engines/orchestrator/aggregator.py` | Integration point |

### Previous Story (8-2) Learnings

From Story 8-2 implementation and code review:

1. **Singleton Factory Pattern**: Use `threading.Lock()` for thread-safe initialization with double-check locking
2. **Timing Metrics**: Use `time.perf_counter()` for sub-millisecond accuracy
3. **Story References**: Include Story reference in all docstrings
4. **LLM Retry Logic**: MAX_RETRIES=3, exponential backoff (0.5s initial, 10s max)
5. **Cost Tracking**: Track input/output tokens, calculate USD cost
6. **Fail Open**: LLM failures should NOT block output - fall back to regex-only
7. **Query Sanitization**: Sanitize inputs before sending to LLM to prevent injection
8. **Global Statement**: Use `# noqa: PLW0603` for global variable assignments
9. **Response Validation**: Validate LLM JSON responses against expected schema

### File Structure

Extend safety service:

```
backend/app/
├── core/
│   └── config.py                     # ADD: language_policing_enabled, policing_llm_enabled, policing_llm_timeout
├── models/
│   └── safety.py                     # ADD: LanguagePolicingResult, ReplacementRecord, QuotePreservation
├── services/
│   └── safety/
│       ├── __init__.py               # UPDATE: Add new exports
│       ├── patterns.py               # EXISTING (Story 8-1)
│       ├── guardrail.py              # EXISTING (Story 8-1)
│       ├── prompts.py                # UPDATE: Add policing prompts
│       ├── subtle_detector.py        # EXISTING (Story 8-2)
│       ├── safety_guard.py           # EXISTING (Story 8-2)
│       ├── policing_patterns.py      # NEW: Regex patterns for output sanitization
│       ├── quote_detector.py         # NEW: Quote detection and protection
│       ├── language_policing.py      # NEW: LanguagePolicingService (regex)
│       └── language_police.py        # NEW: Combined LanguagePolice service
├── engines/
│   └── orchestrator/
│       └── aggregator.py             # UPDATE: Integrate language policing
└── tests/
    └── services/
        └── safety/
            ├── test_patterns.py      # EXISTING (Story 8-1)
            ├── test_guardrail.py     # EXISTING (Story 8-1)
            ├── test_subtle_detector.py   # EXISTING (Story 8-2)
            ├── test_safety_guard.py      # EXISTING (Story 8-2)
            ├── test_policing_patterns.py # NEW: Regex pattern tests
            ├── test_quote_detector.py    # NEW: Quote detection tests
            ├── test_language_policing.py # NEW: Regex policing tests
            └── test_language_police.py   # NEW: Combined service tests
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/safety/` directory
- Use pytest-asyncio for async tests
- **Mock ALL OpenAI calls** - never hit real API in tests
- Include cost tracking validation

**Minimum Test Cases:**

```python
# test_policing_patterns.py

import pytest

class TestConclusionPatterns:
    """Test legal conclusion replacement patterns."""

    def test_violated_section_replaced(self, policing_service):
        """'violated Section 138' → 'affected by Section 138'"""
        result = policing_service.sanitize_text(
            "The defendant violated Section 138 of NI Act."
        )
        assert "affected by Section 138" in result.sanitized_text
        assert "violated" not in result.sanitized_text

    def test_breached_contract_replaced(self, policing_service):
        """'breached the contract' → 'regarding the contract terms'"""
        result = policing_service.sanitize_text(
            "Evidence shows they breached the contract."
        )
        assert "regarding the contract terms" in result.sanitized_text


class TestGuiltPatterns:
    """Test guilt/liability replacement patterns."""

    def test_defendant_guilty_replaced(self, policing_service):
        """'defendant is guilty' → 'defendant's liability regarding'"""
        result = policing_service.sanitize_text(
            "The defendant is guilty of fraud."
        )
        assert "defendant's liability regarding" in result.sanitized_text


class TestPredictionPatterns:
    """Test prediction replacement patterns."""

    def test_court_will_rule_replaced(self, policing_service):
        """'the court will rule' → 'the court may consider'"""
        result = policing_service.sanitize_text(
            "The court will rule in favor of the plaintiff."
        )
        assert "court may consider" in result.sanitized_text


class TestProofPatterns:
    """Test proof/evidence replacement patterns."""

    def test_proves_that_replaced(self, policing_service):
        """'proves that' → 'suggests that'"""
        result = policing_service.sanitize_text(
            "This document proves that the agreement was valid."
        )
        assert "suggests that" in result.sanitized_text


# test_quote_detector.py

class TestQuoteDetection:
    """Test quote detection and preservation."""

    def test_double_quotes_detected(self, quote_detector):
        """Double-quoted text should be detected."""
        text = 'The witness stated "defendant violated the agreement" in testimony.'
        regions = quote_detector.detect_protected_regions(text)
        assert len(regions) == 1
        assert "defendant violated the agreement" in regions[0].text

    def test_quoted_text_preserved(self, policing_service):
        """Quoted text should NOT be sanitized."""
        text = 'As stated: "The defendant is guilty of violating Section 138"'
        result = policing_service.sanitize_text(text)
        # Original quote preserved
        assert '"The defendant is guilty of violating Section 138"' in result.sanitized_text


# test_language_police.py

@pytest.mark.asyncio
class TestLanguagePolice:
    """Test combined regex + LLM policing."""

    async def test_regex_policing_first(self, language_police):
        """Regex policing should run before LLM."""
        result = await language_police.police_output(
            "The evidence proves defendant violated Section 138."
        )
        assert "suggests" in result.sanitized_text
        assert "affected by" in result.sanitized_text

    async def test_llm_polish_subtle(self, language_police, mock_openai):
        """LLM should catch subtle conclusions missed by regex."""
        result = await language_police.police_output(
            "Based on the facts, it is clear the defendant must lose."
        )
        # LLM should have removed "must lose" conclusion
        assert "must lose" not in result.sanitized_text
        assert result.llm_policing_applied is True

    async def test_llm_failure_uses_regex(self, language_police):
        """LLM failure should fall back to regex-only result."""
        with patch.object(
            language_police._subtle_polisher,
            "polish_text",
            side_effect=Exception("LLM Error")
        ):
            result = await language_police.police_output(
                "The evidence proves defendant violated Section 138."
            )
            # Regex replacements still applied
            assert "suggests" in result.sanitized_text
            assert result.llm_policing_applied is False

    async def test_performance_regex_under_5ms(self, language_police):
        """Regex policing should complete in < 5ms."""
        # Disable LLM for this test
        language_police._llm_enabled = False
        result = await language_police.police_output("Short test text.")
        assert result.sanitization_time_ms < 5.0
```

### Git Intelligence

Recent commit patterns:
- `feat(safety): implement GPT-4o-mini subtle violation detection (Story 8-2)`
- `fix(review): code review fixes for Story 8-2`
- `feat(safety): implement regex pattern detection guardrails (Story 8-1)`

Use: `feat(safety): implement language policing output sanitization (Story 8-3)`

### Security Considerations

1. **Fail Graceful**: LLM failures should NOT prevent output - use regex-only fallback
2. **No Content Logging**: Don't log full output text in production (contains case info)
3. **Quote Preservation**: Ensure quoted text is never modified (legal requirement)
4. **Cost Monitoring**: Track LLM costs to prevent runaway spending
5. **Timeout**: Hard timeout of 10s prevents hanging requests

### Environment Variables

Add to `backend/.env`:
```
# Story 8-3: Language Policing
# LANGUAGE_POLICING_ENABLED=true  # Default in config.py
# POLICING_LLM_ENABLED=true  # Default in config.py
# POLICING_LLM_TIMEOUT=10.0  # Default in config.py
```

### Integration Points

1. **ResultAggregator (Epic 6)**: Calls LanguagePolice.police_output() on synthesized response
2. **Story 8-1**: Pattern registry design reused for policing patterns
3. **Story 8-2**: LLM service pattern reused for subtle polishing
4. **Story 6-3**: Policing metrics should be logged to audit trail

### Dependencies

This story depends on:
- **Story 8-1**: GuardrailService pattern (DONE)
- **Story 8-2**: SubtleViolationDetector pattern (DONE)

This story blocks:
- **Story 8-4**: Finding Verifications Table (may need policing on findings)

### Critical NFR Compliance

**NFR22: 0 legal conclusions escape language policing (100% sanitized)**

To achieve 100% sanitization:
1. Comprehensive regex patterns cover common legal conclusions
2. GPT-4o-mini polish catches subtle conclusions missed by regex
3. All engine outputs pass through policing BEFORE user display
4. Protected regions (quotes) are clearly marked as verbatim
5. Audit trail records all sanitization operations

### Project Structure Notes

- Extend existing `services/safety/` directory
- Add new models to existing `models/safety.py`
- Update aggregator to integrate language policing
- **No database migrations needed** - pure service implementation

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Safety Layer](_bmad-output/architecture.md#safety-layer-mandatory) - Safety requirements
- [Story 8-1: Regex Detection](8-1-regex-pattern-detection.md) - Pattern service pattern
- [Story 8-2: Subtle Detection](8-2-gpt4o-mini-violation-detection.md) - LLM service pattern
- [FR9 Requirement](_bmad-output/project-planning-artifacts/epics.md) - Language Policing specification
- [NFR22 Requirement](_bmad-output/project-planning-artifacts/epics.md) - 100% sanitization requirement

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 80 tests pass (34 policing patterns + 21 quote preservation + 16 language police + 9 aggregator integration)
- Two-phase sanitization implemented: fast regex (< 5ms) + optional LLM polish
- Quote preservation protects direct document quotes from sanitization
- Fail-open behavior ensures LLM errors never block output
- Async `aggregate_results_async()` method added for language policing integration

### File List

**New Files:**
- `backend/app/services/safety/policing_patterns.py` - Regex replacement pattern registry (6 categories, 20+ patterns)
- `backend/app/services/safety/quote_detector.py` - Quote/citation detection and protection
- `backend/app/services/safety/language_policing.py` - Regex-only policing service
- `backend/app/services/safety/language_police.py` - Combined regex + LLM policing service
- `backend/tests/services/safety/test_policing_patterns.py` - 34 pattern replacement tests
- `backend/tests/services/safety/test_quote_preservation.py` - 21 quote detection tests
- `backend/tests/services/safety/test_language_police.py` - 16 combined service tests
- `backend/tests/engines/orchestrator/test_aggregator_policing.py` - 9 integration tests

**Modified Files:**
- `backend/app/models/safety.py` - Added ReplacementRecord, QuotePreservation, LanguagePolicingResult
- `backend/app/models/__init__.py` - Added Story 8-3 model exports
- `backend/app/services/safety/__init__.py` - Added Story 8-3 service exports
- `backend/app/services/safety/prompts.py` - Added SUBTLE_POLICING_* prompts
- `backend/app/engines/orchestrator/aggregator.py` - Added async aggregation with policing
- `backend/app/models/orchestrator.py` - Added policing_metadata field
- `backend/app/core/config.py` - Added language_policing_enabled, policing_llm_enabled, policing_llm_timeout

## Change Log

- 2026-01-14: Story 8-3 created by create-story workflow - ready-for-dev
- 2026-01-14: Story 8-3 implementation complete - all 80 tests passing - dev-complete
