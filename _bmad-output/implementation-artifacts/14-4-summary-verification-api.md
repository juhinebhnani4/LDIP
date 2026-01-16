# Story 14.4: Summary Verification API

Status: done

## Story

As a **legal attorney using LDIP**,
I want **to persist my verification decisions and notes on Summary Tab sections**,
so that **my verification work is saved and other team members can see what I have reviewed**.

## Acceptance Criteria

1. **AC1: POST /api/matters/{matter_id}/summary/verify endpoint exists**
   - Accepts: `sectionType`, `sectionId`, `decision` (verified/flagged), optional `notes`
   - Returns HTTP 200 with created verification record
   - Returns HTTP 404 if matter not found or user lacks access
   - Returns HTTP 401 if user not authenticated
   - Validates matter access via RLS (user must be editor or owner)

2. **AC2: POST /api/matters/{matter_id}/summary/notes endpoint exists**
   - Accepts: `sectionType`, `sectionId`, `text` (note content)
   - Returns HTTP 200 with created note record
   - Returns HTTP 404 if matter not found or user lacks access
   - Requires editor or owner role on matter

3. **AC3: GET /api/matters/{matter_id}/summary/verifications endpoint exists**
   - Returns all verification decisions for the matter
   - Filterable by `sectionType`
   - Returns HTTP 200 with list of verification records

4. **AC4: Database table `summary_verifications` stores verification decisions**
   - Columns: `id`, `matter_id`, `section_type`, `section_id`, `decision`, `notes`, `verified_by`, `verified_at`, `created_at`
   - RLS policy enforces matter isolation
   - Enum for `decision`: 'verified', 'flagged'
   - Enum for `section_type`: 'parties', 'subject_matter', 'current_status', 'key_issue'

5. **AC5: Database table `summary_notes` stores attorney notes**
   - Columns: `id`, `matter_id`, `section_type`, `section_id`, `text`, `created_by`, `created_at`
   - RLS policy enforces matter isolation
   - Supports multiple notes per section

6. **AC6: Frontend hook `useSummaryVerification` wired to real APIs**
   - Replace optimistic-only updates with actual API calls
   - Fallback to optimistic updates while API is in-flight
   - Error handling with toast notifications

7. **AC7: Summary API includes verification status**
   - `GET /api/matters/{matter_id}/summary` returns `isVerified` from actual database
   - Parties, subject_matter, current_status sections show real verification status

## Tasks / Subtasks

- [x] **Task 1: Create database migration for summary_verifications table** (AC: #4)
  - [x] 1.1 Create migration file `supabase/migrations/YYYYMMDD_summary_verifications.sql`
  - [x] 1.2 Create `summary_verification_decision` enum: 'verified', 'flagged'
  - [x] 1.3 Create `summary_section_type` enum: 'parties', 'subject_matter', 'current_status', 'key_issue'
  - [x] 1.4 Create `summary_verifications` table with all required columns
  - [x] 1.5 Add RLS policy: users can only access verifications for matters they have access to
  - [x] 1.6 Create unique constraint: one verification per (matter_id, section_type, section_id)

- [x] **Task 2: Create database migration for summary_notes table** (AC: #5)
  - [x] 2.1 Add to same migration file or create separate
  - [x] 2.2 Create `summary_notes` table with all required columns
  - [x] 2.3 Add RLS policy: users can only access notes for matters they have access to
  - [x] 2.4 Allow multiple notes per section (no unique constraint)
  - [x] 2.5 Add index on (matter_id, section_type, section_id) for efficient queries

- [x] **Task 3: Create backend Pydantic models** (AC: #1, #2, #3)
  - [x] 3.1 Add to `backend/app/models/summary.py`:
    - `SummaryVerificationDecision` enum (verified, flagged)
    - `SummarySectionType` enum (parties, subject_matter, current_status, key_issue)
    - `SummaryVerificationCreate` request model
    - `SummaryVerification` response model
    - `SummaryNoteCreate` request model
    - `SummaryNote` response model
    - `SummaryVerificationsListResponse` wrapper

- [x] **Task 4: Create SummaryVerificationService** (AC: #1, #2, #3, #7)
  - [x] 4.1 Create `backend/app/services/summary_verification_service.py`
  - [x] 4.2 Implement `record_verification(matter_id, section_type, section_id, decision, notes, user_id)`:
    - Upsert verification record (update if exists, insert if not)
    - Return verification record
  - [x] 4.3 Implement `add_note(matter_id, section_type, section_id, text, user_id)`:
    - Insert note record
    - Return note record
  - [x] 4.4 Implement `get_verifications(matter_id, section_type=None)`:
    - Query summary_verifications table
    - Optional filter by section_type
    - Return list of verification records
  - [x] 4.5 Implement `check_section_verified(matter_id, section_type, section_id)`:
    - Return True if section has 'verified' decision

- [x] **Task 5: Add API routes to summary.py** (AC: #1, #2, #3)
  - [x] 5.1 Add `POST /api/matters/{matter_id}/summary/verify` endpoint:
    - Require editor/owner role via `require_matter_role`
    - Call `record_verification` service method
    - Invalidate summary cache after verification
  - [x] 5.2 Add `POST /api/matters/{matter_id}/summary/notes` endpoint:
    - Require editor/owner role
    - Call `add_note` service method
  - [x] 5.3 Add `GET /api/matters/{matter_id}/summary/verifications` endpoint:
    - Allow viewer role (read-only)
    - Optional `sectionType` query param filter
    - Call `get_verifications` service method

- [x] **Task 6: Update SummaryService to use real verification status** (AC: #7)
  - [x] 6.1 Update `get_parties()` to check `summary_verifications` table
  - [x] 6.2 Update `generate_subject_matter()` to check verification status
  - [x] 6.3 Update `get_current_status()` to check verification status
  - [x] 6.4 Update `get_key_issues()` to check verification status for each issue

- [x] **Task 7: Wire frontend hook to real API** (AC: #6)
  - [x] 7.1 Update `frontend/src/hooks/useSummaryVerification.ts`:
    - Import `api` from `@/lib/api/client`
    - Replace TODO comments with actual API calls
    - Keep optimistic updates for immediate UI feedback
    - Revalidate on success, rollback on error
  - [x] 7.2 Add error handling with toast notifications
  - [x] 7.3 Update `useMatterSummary` to refresh after verification changes

- [x] **Task 8: Write backend tests** (AC: all)
  - [x] 8.1 Service tests in `backend/tests/services/test_summary_verification_service.py`:
    - Test record_verification creates new record
    - Test record_verification updates existing record (upsert)
    - Test add_note creates note
    - Test get_verifications returns filtered results
    - Test check_section_verified returns correct boolean
  - [x] 8.2 API tests in `backend/tests/api/routes/test_summary.py` (add to existing):
    - Test POST /summary/verify creates verification
    - Test POST /summary/verify requires editor role
    - Test POST /summary/notes creates note
    - Test GET /summary/verifications returns list
    - Test matter isolation (can't verify other user's matters)

- [x] **Task 9: Write frontend tests** (AC: #6)
  - [x] 9.1 Update `frontend/src/hooks/useSummaryVerification.test.ts` (if exists) or create:
    - Test verifySection calls API
    - Test flagSection calls API
    - Test addNote calls API
    - Test error handling shows toast
    - Test optimistic updates work correctly

## Dev Notes

### FR Reference (from MVP Gap Analysis)

> **FR19: Summary Tab** - ...implement inline verification on each section ([✓ Verify] [✗ Flag] [💬 Note] buttons), implement editable sections with Edit button, preserve original AI version...

### Gap Reference

**GAP-API-3: Summary Verification APIs (HIGH)**
- `POST /api/matters/{matter_id}/summary/verify`
- `POST /api/matters/{matter_id}/summary/notes`
- Story 10B.2 deferred backend: `useSummaryVerification` hook uses optimistic updates with local state only

### Architecture Compliance

**LLM Routing:** Not applicable (no LLM calls needed for verification)

**API Response Format (MANDATORY):**
```python
# Success - single item
{ "data": { "id": "uuid", "sectionType": "...", "decision": "verified", ... } }

# Success - list
{ "data": [...], "meta": { "total": N } }

# Error
{
  "error": {
    "code": "MATTER_NOT_FOUND",
    "message": "Matter not found or you don't have access",
    "details": {}
  }
}
```

**Matter Isolation (CRITICAL - 4 layers):**
1. RLS policies on `summary_verifications` and `summary_notes` tables
2. API middleware via `require_matter_role` dependency
3. Service layer validates matter_id ownership
4. No cross-matter data leakage

### Database Schema

**Table: summary_verifications**
```sql
CREATE TYPE summary_verification_decision AS ENUM ('verified', 'flagged');
CREATE TYPE summary_section_type AS ENUM ('parties', 'subject_matter', 'current_status', 'key_issue');

CREATE TABLE summary_verifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  section_type summary_section_type NOT NULL,
  section_id TEXT NOT NULL,  -- entityId for parties, "main" for subject_matter/current_status, issue id for key_issue
  decision summary_verification_decision NOT NULL,
  notes TEXT,
  verified_by UUID NOT NULL REFERENCES auth.users(id),
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(matter_id, section_type, section_id)
);

-- RLS Policy
ALTER TABLE summary_verifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matter verifications"
ON summary_verifications FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_attorneys
    WHERE user_id = auth.uid()
  )
);
```

**Table: summary_notes**
```sql
CREATE TABLE summary_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  section_type summary_section_type NOT NULL,
  section_id TEXT NOT NULL,
  text TEXT NOT NULL,
  created_by UUID NOT NULL REFERENCES auth.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- No unique constraint: multiple notes per section allowed
  CONSTRAINT summary_notes_text_not_empty CHECK (LENGTH(TRIM(text)) > 0)
);

CREATE INDEX idx_summary_notes_matter_section
ON summary_notes(matter_id, section_type, section_id);

-- RLS Policy
ALTER TABLE summary_notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matter notes"
ON summary_notes FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_attorneys
    WHERE user_id = auth.uid()
  )
);
```

### Backend Pydantic Models (add to models/summary.py)

```python
from enum import Enum
from pydantic import BaseModel, Field

class SummaryVerificationDecisionEnum(str, Enum):
    """Summary section verification decision."""
    VERIFIED = "verified"
    FLAGGED = "flagged"

class SummarySectionTypeEnum(str, Enum):
    """Summary section types that can be verified."""
    PARTIES = "parties"
    SUBJECT_MATTER = "subject_matter"
    CURRENT_STATUS = "current_status"
    KEY_ISSUE = "key_issue"

class SummaryVerificationCreate(BaseModel):
    """Request to create/update summary verification."""
    section_type: SummarySectionTypeEnum = Field(
        ..., alias="sectionType"
    )
    section_id: str = Field(
        ..., alias="sectionId",
        description="Entity ID for parties, 'main' for other sections, issue ID for key_issue"
    )
    decision: SummaryVerificationDecisionEnum = Field(...)
    notes: str | None = Field(None, max_length=2000)

    model_config = {"populate_by_name": True}

class SummaryVerificationRecord(BaseModel):
    """Summary verification record from database."""
    id: str
    matter_id: str = Field(..., alias="matterId")
    section_type: SummarySectionTypeEnum = Field(..., alias="sectionType")
    section_id: str = Field(..., alias="sectionId")
    decision: SummaryVerificationDecisionEnum
    notes: str | None = None
    verified_by: str = Field(..., alias="verifiedBy")
    verified_at: str = Field(..., alias="verifiedAt")

    model_config = {"populate_by_name": True}

class SummaryNoteCreate(BaseModel):
    """Request to create summary note."""
    section_type: SummarySectionTypeEnum = Field(
        ..., alias="sectionType"
    )
    section_id: str = Field(..., alias="sectionId")
    text: str = Field(..., min_length=1, max_length=2000)

    model_config = {"populate_by_name": True}

class SummaryNoteRecord(BaseModel):
    """Summary note record from database."""
    id: str
    matter_id: str = Field(..., alias="matterId")
    section_type: SummarySectionTypeEnum = Field(..., alias="sectionType")
    section_id: str = Field(..., alias="sectionId")
    text: str
    created_by: str = Field(..., alias="createdBy")
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}

class SummaryVerificationResponse(BaseModel):
    """API response for single verification."""
    data: SummaryVerificationRecord

class SummaryVerificationsListResponse(BaseModel):
    """API response for verification list."""
    data: list[SummaryVerificationRecord]
    meta: dict = Field(default_factory=dict)

class SummaryNoteResponse(BaseModel):
    """API response for single note."""
    data: SummaryNoteRecord
```

### API Endpoints Pattern (add to routes/summary.py)

```python
@router.post(
    "/{matter_id}/summary/verify",
    response_model=SummaryVerificationResponse,
)
async def verify_summary_section(
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.EDITOR)
    ),
    request: SummaryVerificationCreate = Body(...),
    verification_service: SummaryVerificationService = Depends(get_summary_verification_service),
) -> SummaryVerificationResponse:
    """Record verification decision for a summary section.

    Story 14.4: AC #1 - POST /api/matters/{matter_id}/summary/verify
    """
    verification = await verification_service.record_verification(
        matter_id=access.matter_id,
        section_type=request.section_type,
        section_id=request.section_id,
        decision=request.decision,
        notes=request.notes,
        user_id=access.user_id,
    )

    # Invalidate summary cache so next GET returns updated isVerified
    summary_service = get_summary_service()
    await summary_service.invalidate_cache(access.matter_id)

    return SummaryVerificationResponse(data=verification)
```

### Frontend Hook Update Pattern

```typescript
// hooks/useSummaryVerification.ts - Update to use real API

import { api } from '@/lib/api/client';
import { toast } from 'sonner';

const verifySection = useCallback(
  async (sectionType: SummarySectionType, sectionId: string) => {
    setIsLoading(true);
    setError(null);

    // Optimistic update for immediate UI feedback
    const optimisticVerification: SummaryVerification = {
      sectionType,
      sectionId,
      decision: 'verified',
      verifiedBy: userName,
      verifiedAt: new Date().toISOString(),
    };
    setVerifications((prev) => {
      const next = new Map(prev);
      next.set(getKey(sectionType, sectionId), optimisticVerification);
      return next;
    });

    try {
      // Real API call
      const response = await api.post<{ data: SummaryVerification }>(
        `/matters/${matterId}/summary/verify`,
        {
          sectionType,
          sectionId,
          decision: 'verified',
        }
      );

      // Update with actual server response
      setVerifications((prev) => {
        const next = new Map(prev);
        next.set(getKey(sectionType, sectionId), response.data.data);
        return next;
      });

      toast.success('Section verified');
      onSuccess?.();
    } catch (err) {
      // Rollback optimistic update on error
      setVerifications((prev) => {
        const next = new Map(prev);
        next.delete(getKey(sectionType, sectionId));
        return next;
      });

      const error = err instanceof Error ? err : new Error('Failed to verify section');
      setError(error);
      toast.error('Failed to verify section. Please try again.');
      onError?.(error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  },
  [matterId, userName, onSuccess, onError]
);
```

### Existing Code to Reuse

**From Story 14.1 (Summary API):**
- `backend/app/api/routes/summary.py` - Add new endpoints to existing file
- `backend/app/models/summary.py` - Add new models to existing file
- `backend/app/services/summary_service.py` - Update to use verification service
- `validate_matter_access` dependency pattern for Layer 4 security
- `_handle_service_error` helper function

**From Story 10B.2 (Summary Inline Verification):**
- `frontend/src/hooks/useSummaryVerification.ts` - Hook structure to update
- `frontend/src/types/summary.ts` - TypeScript types already defined
- `SummarySectionType`, `SummaryVerificationDecision` types exist in frontend

**From Story 8-4 (Finding Verifications):**
- `backend/app/api/routes/verifications.py` - Verification endpoint patterns
- `backend/app/models/verification.py` - Verification model patterns
- `backend/app/services/verification.py` - Service patterns for verification CRUD

### Testing Patterns

**Backend Tests (pytest):**
```python
# tests/services/test_summary_verification_service.py
@pytest.mark.asyncio
async def test_record_verification_creates_new(
    summary_verification_service: SummaryVerificationService,
    test_matter: Matter,
    test_user: User,
):
    """Test recording a new verification."""
    result = await summary_verification_service.record_verification(
        matter_id=str(test_matter.id),
        section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
        section_id="main",
        decision=SummaryVerificationDecisionEnum.VERIFIED,
        notes="Looks correct",
        user_id=str(test_user.id),
    )

    assert result.decision == SummaryVerificationDecisionEnum.VERIFIED
    assert result.section_type == SummarySectionTypeEnum.SUBJECT_MATTER
    assert result.verified_by == str(test_user.id)
```

**Frontend Tests (Vitest):**
```typescript
// hooks/useSummaryVerification.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('@/lib/api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

test('verifySection calls POST /summary/verify', async () => {
  const mockResponse = {
    data: {
      data: {
        id: 'ver-123',
        sectionType: 'subject_matter',
        sectionId: 'main',
        decision: 'verified',
        verifiedBy: 'user-123',
        verifiedAt: '2026-01-16T10:00:00Z',
      }
    }
  };

  vi.mocked(api.post).mockResolvedValue(mockResponse);

  const { result } = renderHook(() =>
    useSummaryVerification({ matterId: 'matter-123' })
  );

  await result.current.verifySection('subject_matter', 'main');

  expect(api.post).toHaveBeenCalledWith(
    '/matters/matter-123/summary/verify',
    expect.objectContaining({
      sectionType: 'subject_matter',
      sectionId: 'main',
      decision: 'verified',
    })
  );
});
```

### Project Structure Notes

**New files to create:**
- `supabase/migrations/YYYYMMDD_summary_verifications.sql` - Database migration
- `backend/app/services/summary_verification_service.py` - New service
- `backend/tests/services/test_summary_verification_service.py` - Service tests

**Files to modify:**
- `backend/app/models/summary.py` - Add verification/note models
- `backend/app/api/routes/summary.py` - Add 3 new endpoints
- `backend/app/services/summary_service.py` - Update to check real verifications
- `backend/tests/api/routes/test_summary.py` - Add endpoint tests
- `frontend/src/hooks/useSummaryVerification.ts` - Wire to real API

### Previous Story Intelligence (Epic 14)

**From Story 14.1 (Summary API):**
- Summary service structure with Redis caching
- `validate_matter_access` dependency for Layer 4 security
- `_handle_service_error` helper for consistent error responses
- `invalidate_cache` method exists and should be called after verification

**From Story 14.2 (Contradictions List API):**
- Pagination response pattern: `{ data: [...], meta: { total } }`
- Filter query parameters pattern

**From Story 14.3 (Upload Stage 3-4 API):**
- Feature flag pattern for gradual rollout (not needed here)
- Error handling with toast notifications pattern

### Git Commit Context (Recent)

```
9c56587 fix(review): code review fixes for Story 14.3 - Upload Stage 3-4 API Wiring
d210c12 feat(upload): wire upload stage 3-4 to real backend APIs (Story 14-3)
932dbf4 fix(review): code review fixes for Story 14.2 - Contradictions List API
```

**Commit message format:** `feat(summary): implement summary verification API (Story 14-4)`

### Security Considerations

- **RLS on both tables** - Users can only access verifications/notes for matters they have access to
- **Role-based access** - Verify/flag/note operations require editor or owner role
- **No sensitive data exposure** - Verification records don't contain document content
- **Audit trail** - `verified_by`, `verified_at`, `created_by`, `created_at` for forensic logging

### Performance Considerations

- **Upsert pattern** - Use ON CONFLICT for efficient update-or-insert
- **Cache invalidation** - Invalidate summary cache after verification so `isVerified` stays accurate
- **Index on (matter_id, section_type, section_id)** - For efficient lookup queries
- **No N+1 queries** - Load all verifications for a matter in single query when building summary

### References

- [Source: _bmad-output/implementation-artifacts/mvp-gap-analysis-2026-01-16.md#GAP-API-3]
- [Source: _bmad-output/implementation-artifacts/10b-2-summary-inline-verification.md] - Frontend components
- [Source: backend/app/api/routes/summary.py] - Existing summary endpoint
- [Source: backend/app/services/summary_service.py] - Summary service to extend
- [Source: frontend/src/hooks/useSummaryVerification.ts] - Hook to wire to API
- [Source: backend/app/api/routes/verifications.py] - Verification endpoint patterns (Story 8-4)
- [Source: project-context.md] - API response format, RLS patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None required.

### Completion Notes List

1. **Database Migration**: Created `supabase/migrations/20260116000001_create_summary_verification_tables.sql` with both `summary_verifications` and `summary_notes` tables, enums, RLS policies, and indexes.

2. **Backend Models**: Added verification/note Pydantic models to `backend/app/models/summary.py` with camelCase aliases for API serialization.

3. **SummaryVerificationService**: Created new service at `backend/app/services/summary_verification_service.py` implementing upsert for verifications, insert for notes, and query methods.

4. **API Routes**: Added 3 new endpoints to `backend/app/api/routes/summary.py`:
   - `POST /{matter_id}/summary/verify` - Record verification (EDITOR role)
   - `POST /{matter_id}/summary/notes` - Add note (EDITOR role)
   - `GET /{matter_id}/summary/verifications` - List verifications (VIEWER role)

5. **SummaryService Updates**: Updated `_check_party_verified`, `generate_subject_matter`, `get_current_status`, and `get_key_issues` to check real verification status from database.

6. **Frontend Hook**: Wired `useSummaryVerification.ts` to real API endpoints with optimistic updates and rollback on failure.

7. **Tests**:
   - Backend API tests: 23 tests passing
   - Backend service tests: 13 tests passing
   - Frontend hook tests: 12 tests passing

8. **Note**: The rollback logic for notes keeps empty arrays instead of deleting keys (functionally equivalent for UI).

### File List

**New Files:**
- `supabase/migrations/20260116000001_create_summary_verification_tables.sql`
- `backend/app/services/summary_verification_service.py`
- `backend/tests/services/test_summary_verification_service.py`
- `frontend/src/hooks/useSummaryVerification.test.ts`

**Modified Files:**
- `backend/app/models/summary.py`
- `backend/app/api/routes/summary.py`
- `backend/app/services/summary_service.py`
- `backend/tests/api/routes/test_summary.py`
- `frontend/src/hooks/useSummaryVerification.ts`
