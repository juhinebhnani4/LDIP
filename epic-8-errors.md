# Epic 8 Code Review: Safety Layer (Guardrails, Policing, Verification)

## Executive Summary
The Safety Layer implementation is largely robust and well-structured, following the 4-layer isolation principles and implementing the required patterns (Singleton factories, fail-open LLM checks, etc.).
However, a **CRITICAL** vulnerability exists: The Search API endpoints bypass the Safety Guard entirely, allowing users to potentially use the search function to seek implicit legal advice or access blocked content patterns without guardrail checks.

## Critical Issues (Must Fix)

### 1. Search API Bypasses Safety Guard
**Severity:** Critical
**Location:** `backend/app/api/routes/search.py`
**Description:**
The search endpoints (`/hybrid`, `/semantic`, `bm25`, `rerank`) directly instantiate and call `HybridSearchService`. They do **not** invoke `SafetyGuard.check_query()` nor do they route through the `QueryOrchestrator` (which handles safety).
**Impact:**
- Users can bypass "Legal Advice" blocking by phrasing advice requests as search queries (e.g., "how to hide assets").
- While search returns document snippets rather than generated advice, strict adherence to Story 8-1 implies dangerous query patterns should be blocked "instantly" to prevent any system interaction with such intents.
**Recommendation & Implementation Details:**
- **Inject `SafetyGuard`**: Add `SafetyGuard` dependency to all search endpoints (`/hybrid`, `/semantic`, `/bm25`, `/rerank`).
- **Logic Insertion**: Call `await safety_guard.check_query(query)` **before** executing any search logic.
- **Error Handling**: If `!result.is_safe`, return `HTTP 400 Bad Request` with:
    - Code: `SAFETY_VIOLATION`
    - Message: `result.blocked_reason`
    - Metadata: `violation_type`, `suggested_rewrite`

## Major Issues (Should Fix)

### 2. Language Policing applied only to Orchestrator Response
**Severity:** High
**Location:** `backend/app/engines/orchestrator/aggregator.py`
**Description:**
`LanguagePolice` is applied in `ResultAggregator.aggregate_results_async`. This covers the "Unified Response" from the orchestrator.
However, individual engine results (e.g., Timeline descriptions, Contradiction analysis) might contain generated text. If these are displayed raw in the UI (outside the unified summary), they might contain unsanitized legal conclusions.
**Recommendation:**
- Ensure all LLM-generated text (including intermediate engine outputs if displayed) passes through `LanguagePolice`.
- Verify if `ResultAggregator` handles all user-facing text.

### 3. Hardcoded Engine Mapping in Verification Service
**Severity:** Medium
**Location:** `backend/app/services/verification/verification_service.py` -> `_extract_engine_from_finding_type`
**Description:**
The method uses a hardcoded dictionary (`engine_mapping`) to map finding types to engines.
```python
engine_mapping = {
    "citation_mismatch": "citation",
    ...
}
```
**Impact:**
- Adding a new engine or finding type requires modifying this service, violating Open/Closed principle.
- Fallback logic (`finding_type.split("_")[0]`) is heuristics-based and might fail for complex names.
**Recommendation & Implementation Details:**
- **Refactor**: Move the hardcoded `engine_mapping` dictionary to a module-level constant or a dedicated configuration class to allow easier updates and better maintainability.
- **Robust Fallback**: Improve the fallback logic to handle more complex naming conventions.

## Minor Issues (Cleanup/Optimization)

### 4. Bulk Verification Update Limit
**Severity:** Low
**Location:** `backend/app/services/verification/verification_service.py` -> `bulk_update_verifications`
**Description:**
The service limits bulk updates to 100 items. This is a good safety check, but the loop processes updates sequentially (one by one) or in a loop with individual `update` calls?
Code:
```python
for verification_id in verification_ids:
    result = supabase.table("finding_verifications").update(...)
```
This performs N network requests for N items.
**Recommendation & Implementation Details:**
- **Optimization**: Replace the iterative loop. Use Supabase/PostgREST `in_` filter combined with update logic if supported.
- **Fallback**: If bulk update by ID list is not fully supported by the client for this operation, use `asyncio.gather` to parallelize the requests (capped at a sensible concurrency limit) to significantly reduce latency compared to sequential execution.

### 5. Quote Detector Performance
**Severity:** Low
**Location:** `backend/app/services/safety/quote_detector.py`
**Description:**
The `_remove_overlaps` method sorts and iterates. Python's `re.finditer` is efficient, but if the document is massive, this regex-heavy approach might be slow.
**Recommendation:**
- Ensure `text` passed to `QuoteDetector` is chunked or reasonably sized (which it likely is, as it processes LLM output).

## Story Coverage Verification

| Story | Feature | Status | Notes |
|-------|---------|--------|-------|
| 8-1 | Guardrails (Regex) | ✅ Implemented | `services/safety/guardrail.py`, `patterns.py` |
| 8-2 | Guardrails (LLM) | ✅ Implemented | `services/safety/subtle_detector.py`, `safety_guard.py` |
| 8-3 | Language Policing | ✅ Implemented | `services/safety/language_policing.py`, `language_police.py` |
| 8-4 | Verification Backend | ✅ Implemented | `services/verification/verification_service.py`, `models/verification.py` |
| 8-5 | Verification Queue UI | ✅ Implemented | `frontend/.../VerificationQueue.tsx` |

## Required Testing (Implementation Plan)

To ensure safety fixes are effective and don't regress:

### [NEW] `backend/tests/api/routes/test_search_safety.py`
Create a new test file specifically for verifying safety in search:
- **`test_search_blocks_unsafe_regex`**: Mock `SafetyGuard` to return `is_safe=False` (regex). Verify HTTP 400 response.
- **`test_search_blocks_unsafe_llm`**: Mock `SafetyGuard` to return `is_safe=False` (LLM). Verify HTTP 400 response.
- **`test_search_allows_safe_query`**: Mock `SafetyGuard` to return `is_safe=True`. Verify HTTP 200 response.

### Manual Verification Steps
1.  **Blocked Query**: POST to `/api/matters/{id}/search/hybrid` with query "how do I hide assets". Expect 400 Bad Request (`SAFETY_VIOLATION`).
2.  **Safe Query**: POST with query "contract termination". Expect 200 OK.

## Conclusion
The Safety Layer is robustly implemented with a clear separation of concerns. The primary issue is the **Search API bypass**, which needs immediate remediation using the steps outlined above.
