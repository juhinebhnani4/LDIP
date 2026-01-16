# Code Review Findings: OCR & Document Pipeline (Epic 2b)

**Review Status**: ✅ **ALL ISSUES RESOLVED**
**Scope**: Epic 2b (Stories 2b.1 - 2b.7) - OCR, Chunking, Search, and RAG Pipeline
**Last Updated**: 2026-01-16

## Summary

| # | Finding | Original Severity | Status |
|---|---------|-------------------|--------|
| 1 | RLS Bypass in Backend Services | CRITICAL | ✅ **BY DESIGN** - Documented architecture |
| 2 | IDOR in Human Review Submission | CRITICAL | ✅ **FIXED** - `authorized_matter_id` validation added |
| 3 | Audit Log Mutability | HIGH | ✅ **FIXED** - Changed to SELECT-only policy |
| 4 | Hardcoded English Indexing | MEDIUM | ✅ **FIXED** - Changed to 'simple' tokenizer |
| 5 | Search Fallback Logic Weakness | LOW | ✅ **FIXED** - Increased limit to 50 |
| 6 | Missing matter_id in get_reviews_by_document | HIGH | ✅ **FIXED** - Added `authorized_matter_id` parameter |
| 7 | Gemini API Key Logging Risk | MEDIUM | ✅ **FIXED** - Sanitized error messages |
| 8 | Missing Input Length Validation | MEDIUM | ✅ **FIXED** - Added MAX_TEXT_LENGTH check |
| 9 | Unbounded Pagination Rate Limit | MEDIUM | ✅ **FIXED** - Added READONLY_RATE_LIMIT |

---

## Detailed Fix Log

### Issue 1: RLS Bypass in Backend Services ✅ BY DESIGN
- **Status**: Intentional architecture - documented in `client.py:1-20`
- **Rationale**: Backend uses service key to bypass RLS (Layer 1) because Layer 4 (Application Authorization) handles access control. Celery workers need service-level access without user JWT context.

### Issue 2: IDOR in Human Review Submission ✅ FIXED
- **File**: `backend/app/services/ocr/human_review_service.py:264-319`
- **Fix**: Added `authorized_matter_id` parameter to `submit_correction()` with validation check and IDOR attempt logging.

### Issue 3: Audit Log Mutability ✅ FIXED
- **File**: `supabase/migrations/20260108000001_create_ocr_validation_tables.sql:38-52`
- **Fix**: Changed `FOR ALL` policy to `FOR SELECT` only. Audit logs are now immutable per 7-year compliance requirement.

### Issue 4: Hardcoded English Indexing ✅ FIXED
- **File**: `supabase/migrations/20260106000003_create_bounding_boxes_table.sql:36-40`
- **Fix**: Changed `to_tsvector('english', text)` to `to_tsvector('simple', text)` for language-agnostic search (supports English, Hindi, Gujarati).

### Issue 5: Search Fallback Logic Weakness ✅ FIXED
- **File**: `backend/app/services/rag/hybrid_search.py:26-31`
- **Fix**: Increased `DEFAULT_HYBRID_LIMIT` from 20 to 50 with documentation explaining the change.

### Issue 6: Missing matter_id in get_reviews_by_document ✅ FIXED (NEW)
- **File**: `backend/app/services/ocr/human_review_service.py:202-239`
- **Fix**: Added `authorized_matter_id` parameter to `get_reviews_by_document()` with filter enforcement.

### Issue 7: Gemini API Key Logging Risk ✅ FIXED (NEW)
- **File**: `backend/app/services/ocr/gemini_validator.py:140-147`
- **Fix**: Changed error logging to only log error type, not message which may contain sensitive data.

### Issue 8: Missing Input Length Validation ✅ FIXED (NEW)
- **File**: `backend/app/services/ocr/pattern_corrector.py:178-210`
- **Fix**: Added `MAX_TEXT_LENGTH = 10000` check to prevent ReDoS attacks with very long strings.

### Issue 9: Unbounded Pagination Rate Limit ✅ FIXED (NEW)
- **File**: `backend/app/api/routes/ocr_validation.py:219-234`
- **Fix**: Added `@limiter.limit(READONLY_RATE_LIMIT)` (120 requests/minute) to `get_validation_log` endpoint.
