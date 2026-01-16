# Code Review Findings: Document Upload & Storage (Epic 2a)

**Review Status**: :white_check_mark: **PASS** (All issues fixed)
**Scope**: Full Epic 2a (Stories 2A.1 - 2A.3) with Forensic Analysis of Storage & Upload Logic
**Last Review**: 2026-01-16

## Summary

All 6 critical/high/medium issues from the original review have been **FIXED**. Additionally, 3 new issues found during adversarial review have been addressed.

---

## Original Issues - ALL FIXED

### 1. Denial of Service (DoS) / Memory Exhaustion
- **Severity**: CRITICAL (Showstopper)
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Refactored to use `SpooledTemporaryFile` for streaming uploads (backend/app/api/routes/documents.py:268-317)
- **How it works**: Small files (<10MB) stay in memory, large files automatically spill to disk. Size validation happens during streaming.

### 2. Security Architecture Mismatch (RLS vs Service Role)
- **Severity**: CRITICAL
- **Status**: :white_check_mark: **ADDRESSED**
- **Fix**: Added comprehensive documentation in migration explaining the architecture (supabase/migrations/20260106000010_create_storage_policies.sql:39-53)
- **Explanation**: RLS policies are kept as defense-in-depth. The Service Role proxy pattern is intentional, with access validated at API layer via `require_matter_role()`.

### 3. Mock Data in Production Code
- **Severity**: High (Functional Deception)
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Mock data gated behind explicit dev flags (frontend/src/components/features/upload/UploadWizard.tsx:33-35)
- **Guard**: `process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_ENABLE_ACT_DISCOVERY_MOCK === 'true'`

### 4. Rollback Logic Flaw (Silent Failure)
- **Severity**: High
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Rollback failures are now tracked, logged at CRITICAL level, and exposed in error response (backend/app/api/routes/documents.py:569-628)

### 5. Manual Infrastructure Dependency
- **Severity**: Medium
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Added `backend/scripts/setup_storage_bucket.py` for automated bucket creation
- **Usage**: `python scripts/setup_storage_bucket.py` or `npm run setup:storage`

### 6. Missing ZIP Bomb Protection
- **Severity**: Medium
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Added `_check_zip_bomb()` function with compression ratio, total size, and file count limits (backend/app/api/routes/documents.py:372-441)
- **Limits**: 100:1 max compression ratio, 2GB max total extracted, 500 max files

---

## Additional Fixes (Follow-up Review 2026-01-16)

### 7. Test Failures: Celery Tasks Not Mocked
- **Severity**: High (Tests blocking)
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Added `patch("app.api.routes.documents._queue_ocr_task")` in test fixture (backend/tests/api/test_documents.py:161-162)
- **Result**: All 26 document tests now pass

### 8. Filename Path Traversal Validation
- **Severity**: Medium (Security)
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Added explicit validation rejecting filenames with `..`, `/`, or `\` (backend/app/api/routes/documents.py:512-521)

### 9. API URL Fallback in Production
- **Severity**: Low
- **Status**: :white_check_mark: **FIXED**
- **Fix**: Throws error if `NEXT_PUBLIC_API_URL` not set in production (frontend/src/lib/api/documents.ts:27-33)

---

## Test Results

```
26 passed, 0 failed in 0.64s
```

All document API tests pass including:
- PDF upload with role validation
- ZIP extraction with PDF handling
- Document listing with pagination and filters
- Document update with type changes
- Bulk update operations

---

## Remaining Known Issues (Not Fixed - Low Priority)

### Memory: ZIP Content Still Fully Loaded
- **Severity**: LOW (Edge case optimization)
- **Impact**: 500MB ZIP still needs 500MB+ RAM during extraction
- **Recommendation**: For MVP, this is acceptable. Optimize if memory pressure becomes an issue.
- **Future Fix**: Refactor `_extract_and_upload_zip` to accept file-like object and stream extraction

### PDF Magic Bytes Verification
- **Severity**: LOW (Defense in depth)
- **Impact**: Files named `.pdf` but not actually PDF could be uploaded
- **Recommendation**: OCR pipeline would fail, but could add magic bytes check for earlier validation

---

**Reviewed by**: Claude (AI Code Review)
**Date**: 2026-01-16
