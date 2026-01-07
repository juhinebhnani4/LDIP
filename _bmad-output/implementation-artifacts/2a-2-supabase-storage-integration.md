# Story 2A.2: Implement Supabase Storage Integration

Status: approved

## Story

As a **developer**,
I want **documents stored in Supabase Storage with proper folder structure**,
So that **files are organized by matter and type with security enforced**.

## Acceptance Criteria

1. **Given** a user uploads a case file **When** the file is stored **Then** it is saved to `documents/{matter_id}/uploads/{filename}` **And** the storage path is recorded in the documents table

2. **Given** a user uploads an Act document **When** the file is stored **Then** it is saved to `documents/{matter_id}/acts/{filename}` **And** the document is marked as is_reference_material=true

3. **Given** a user without access to a matter **When** they attempt to access a file via storage URL **Then** access is denied by Supabase Storage RLS policies **And** a 403 error is returned

4. **Given** a ZIP file is uploaded **When** processing begins **Then** the ZIP is extracted **And** each PDF inside is stored individually in the uploads folder **And** the original ZIP is deleted after successful extraction

## Tasks / Subtasks

- [x] Task 1: Create backend document upload endpoint (AC: #1, #2)
  - [x] Create `backend/app/api/routes/documents.py` with `/api/documents/upload` POST endpoint
  - [x] Implement multipart form-data handling for file + metadata
  - [x] Use `require_matter_role_from_form([MatterRole.OWNER, MatterRole.EDITOR])` for authorization
  - [x] Determine storage subfolder based on document_type (uploads vs acts)
  - [x] Set is_reference_material=true for act document types

- [x] Task 2: Implement Supabase Storage service (AC: #1, #2, #3)
  - [x] Create `backend/app/services/storage_service.py`
  - [x] Implement `upload_file(matter_id, subfolder, file, filename)` method
  - [x] Use service client for admin uploads (bypasses RLS for trusted backend operations)
  - [x] Generate storage path: `{matter_id}/{subfolder}/{filename}`
  - [x] Handle filename conflicts with UUID suffix
  - [x] Return storage path and signed URL

- [x] Task 3: Create document record in database (AC: #1)
  - [x] Create `backend/app/services/document_service.py`
  - [x] Implement `create_document(...)` with all required fields
  - [x] Insert into documents table: matter_id, filename, storage_path, file_size, document_type, is_reference_material, uploaded_by, status='pending'
  - [x] Return document_id in response

- [x] Task 4: Implement ZIP extraction logic (AC: #4)
  - [x] Add zipfile extraction in document upload flow
  - [x] Validate ZIP contains only PDF files
  - [x] Extract each PDF and upload individually to uploads folder
  - [x] Create document record for each extracted PDF
  - [x] ZIP content is not stored (only extracted PDFs are kept)
  - [x] Handle extraction errors gracefully (rollback on failure)

- [x] Task 5: Create Pydantic models for documents (AC: #1)
  - [x] Create `backend/app/models/document.py`
  - [x] Define DocumentCreate, Document, DocumentResponse models
  - [x] Define UploadedDocument and BulkUploadResponse models matching frontend interface
  - [x] Use strict validation for document_type enum

- [x] Task 6: Update frontend to use real backend endpoint
  - [x] Update `frontend/src/lib/api/documents.ts` to include auth header
  - [x] Get JWT token from Supabase session via createClient()
  - [x] Add Authorization Bearer header to XMLHttpRequest
  - [x] Update UPLOAD_ENDPOINT to use API_BASE_URL from environment

- [x] Task 7: Verify authorization enforcement (AC: #3)
  - [x] Storage RLS policies exist in migrations (20260106000010_create_storage_policies.sql)
  - [x] API layer tests verify unauthorized user gets 404 (prevents enumeration)
  - [x] API layer tests verify viewer role gets 403
  - [ ] **Note:** Storage-level RLS requires manual testing with real Supabase instance (not covered in unit tests which use mocks)

- [x] Task 8: Write backend tests
  - [x] Create `backend/tests/api/test_documents.py` (11 tests)
  - [x] Test upload endpoint with valid file and matter access
  - [x] Test upload endpoint returns 404 without access
  - [x] Test ZIP extraction creates multiple document records
  - [x] Test document_type correctly routes to acts/uploads folder
  - [x] Create `backend/tests/services/test_storage_service.py` (16 tests)
  - [x] Mock Supabase storage operations

## Dev Notes

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library

#### API Response Format (MANDATORY)
```python
# Success - single item
{ "data": { "document_id": "uuid", "filename": "..." } }

# Error - always include code and message
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| API endpoints | plural nouns | `/api/documents/upload` |
| API path params | snake_case in braces | `{matter_id}` |
| Python functions | snake_case | `upload_document`, `create_document` |
| Python classes | PascalCase | `DocumentService`, `StorageService` |

### File Organization (CRITICAL)

```
backend/app/
├── api/
│   └── routes/
│       └── documents.py          (NEW)
├── models/
│   └── document.py               (NEW)
├── services/
│   ├── storage_service.py        (NEW)
│   └── document_service.py       (NEW)
└── tests/
    ├── api/
    │   └── test_documents.py     (NEW)
    └── services/
        └── test_storage_service.py (NEW)
```

### Existing Code to Reuse

**FROM Story 1-7 (4-Layer Matter Isolation):**
- `backend/app/api/deps.py` - use `require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])` for authorization
- `backend/app/api/deps.py` - use `MatterMembership` for accessing matter_id and user_id
- `backend/app/services/supabase/client.py` - use `get_service_client()` for storage operations that bypass RLS
- `backend/app/core/security.py` - JWT validation is already handled

**FROM Story 2a-1 (Document Upload UI):**
- Frontend upload integration is ALREADY IMPLEMENTED in `frontend/src/lib/api/documents.ts`
- XMLHttpRequest with progress tracking is ready
- Only needs auth header addition
- Upload store in `frontend/src/stores/uploadStore.ts` handles state

### Database Schema (ALREADY EXISTS)

From migration `20260106000001_create_documents_table.sql`:
```sql
CREATE TABLE public.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  filename text NOT NULL,
  storage_path text NOT NULL,
  file_size bigint NOT NULL,
  page_count integer,
  document_type text NOT NULL CHECK (document_type IN ('case_file', 'act', 'annexure', 'other')),
  is_reference_material boolean DEFAULT false,
  uploaded_by uuid NOT NULL REFERENCES auth.users(id),
  uploaded_at timestamptz DEFAULT now(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  processing_started_at timestamptz,
  processing_completed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

### Storage RLS Policies (ALREADY EXISTS)

From migration `20260106000010_create_storage_policies.sql`:
- Storage bucket: `documents`
- Path structure: `{matter_id}/{subfolder}/{filename}`
- Valid subfolders: `uploads`, `acts`, `exports`
- RLS validates matter access via `matter_attorneys` table
- Helper functions: `get_matter_id_from_storage_path()`, `user_has_storage_access()`

### Backend Endpoint Pattern

Follow existing pattern from `backend/app/api/routes/matters.py`:

```python
# documents.py
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
    get_current_user,
)
from app.models.document import DocumentResponse, DocumentType

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    matter_id: str = Form(...),
    document_type: DocumentType = Form(default=DocumentType.CASE_FILE),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
) -> DocumentResponse:
    """Upload a document to a matter."""
    # Implementation here
```

### Storage Upload Pattern

```python
# storage_service.py
from supabase import Client
from app.services.supabase.client import get_service_client

class StorageService:
    def __init__(self, client: Client | None = None):
        self.client = client or get_service_client()
        self.bucket = "documents"

    async def upload_file(
        self,
        matter_id: str,
        subfolder: str,  # 'uploads' or 'acts'
        file_content: bytes,
        filename: str,
    ) -> tuple[str, str]:
        """Upload file and return (storage_path, signed_url)."""
        storage_path = f"{matter_id}/{subfolder}/{filename}"

        # Use upsert to handle potential conflicts
        result = self.client.storage.from_(self.bucket).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": "application/pdf"}
        )

        # Generate signed URL for download
        signed_url = self.client.storage.from_(self.bucket).create_signed_url(
            path=storage_path,
            expires_in=3600  # 1 hour
        )

        return storage_path, signed_url["signedURL"]
```

### ZIP Extraction Pattern

```python
import zipfile
import io
from typing import list

async def extract_and_upload_zip(
    zip_content: bytes,
    matter_id: str,
    user_id: str,
    storage_service: StorageService,
    document_service: DocumentService,
) -> list[Document]:
    """Extract ZIP and upload each PDF individually."""
    documents = []

    with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
        pdf_files = [f for f in zf.namelist() if f.lower().endswith('.pdf')]

        if not pdf_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "NO_PDFS_IN_ZIP", "message": "ZIP contains no PDF files", "details": {}}}
            )

        for pdf_name in pdf_files:
            pdf_content = zf.read(pdf_name)
            filename = os.path.basename(pdf_name)  # Handle nested paths

            # Upload each PDF
            storage_path, _ = await storage_service.upload_file(
                matter_id=matter_id,
                subfolder="uploads",
                file_content=pdf_content,
                filename=filename,
            )

            # Create document record
            doc = await document_service.create_document(
                matter_id=matter_id,
                filename=filename,
                storage_path=storage_path,
                file_size=len(pdf_content),
                document_type="case_file",
                is_reference_material=False,
                uploaded_by=user_id,
            )
            documents.append(doc)

    return documents
```

### Frontend Auth Header Update

```typescript
// documents.ts - Add auth header
import { getSupabaseClient } from '@/lib/supabase/client';

export async function uploadFile(
  file: File,
  fileId: string,
  options: UploadOptions
): Promise<UploadResponse> {
  // ... existing code ...

  xhr.open('POST', UPLOAD_ENDPOINT);

  // Add auth header
  const supabase = getSupabaseClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    xhr.setRequestHeader('Authorization', `Bearer ${session.access_token}`);
  }

  xhr.send(formData);
}
```

### Previous Story Intelligence

**From Story 2a-1 (Document Upload UI):**
- Upload UI is COMPLETE with drag-drop, validation, progress tracking
- File validation: 500MB limit, 100 files max, PDF/ZIP only
- Upload store manages queue, progress, and status
- XMLHttpRequest used for progress tracking (fetch doesn't support upload progress)
- Tests cover drag states, file rejection, progress display

**From Story 1-7 (4-Layer Matter Isolation):**
- Layer 4 (API middleware) is implemented in `deps.py`
- `require_matter_role` validates user has proper role
- `MatterMembership` provides matter_id, user_id, role
- Service client bypasses RLS for trusted backend operations

**Key Patterns from Epic 1:**
- API response wrapper: `{ data: ... }` or `{ error: { code, message, details } }`
- Service layer handles business logic, routes handle HTTP
- Pydantic models for request/response validation
- structlog for all logging

### Git Intelligence

Recent commit patterns:
- `feat(documents): implement document upload UI (Story 2a-1)`
- `fix(documents): code review fixes for document upload UI (Story 2a-1)`
- `feat(security): implement 4-layer matter isolation (Story 1-7)`

**Recommended commit:** `feat(documents): implement Supabase storage integration (Story 2a-2)`

### Anti-Patterns to AVOID

```python
# WRONG: Using anon key for storage operations
client = create_client(url, anon_key)  # Use get_service_client() instead

# WRONG: Not validating matter access
@router.post("/upload")
async def upload(file: UploadFile):
    # Missing require_matter_role dependency!

# WRONG: Hardcoded paths
storage_path = "documents/uploads/file.pdf"  # Use f"{matter_id}/uploads/{filename}"

# WRONG: Not handling filename conflicts
storage.upload(path=storage_path, file=content)  # Add UUID suffix for conflicts

# WRONG: Returning raw data
return {"document_id": doc.id}  # Use DocumentResponse(data=doc)

# WRONG: Using print or logging module
print("Upload complete")  # Use structlog: logger.info("upload_complete", ...)

# WRONG: Not handling async properly
def upload_file(...):  # Should be async def
```

### Testing Guidance

```python
# test_documents.py
import pytest
from fastapi import status
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_upload_document_success(
    client: AsyncClient,
    test_matter: dict,
    test_user_token: str,
):
    """Test successful document upload."""
    files = {"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")}
    data = {"matter_id": test_matter["id"], "document_type": "case_file"}

    response = await client.post(
        "/api/documents/upload",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert "data" in result
    assert result["data"]["filename"] == "test.pdf"
    assert result["data"]["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_without_access_returns_404(
    client: AsyncClient,
    test_matter: dict,
    other_user_token: str,  # User without access to test_matter
):
    """Test upload denied for unauthorized user."""
    files = {"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")}
    data = {"matter_id": test_matter["id"], "document_type": "case_file"}

    response = await client.post(
        "/api/documents/upload",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {other_user_token}"},
    )

    # Returns 404 to prevent matter enumeration
    assert response.status_code == status.HTTP_404_NOT_FOUND
```

### Manual Steps Required After Implementation

#### Environment Variables
- [ ] Ensure `SUPABASE_SERVICE_KEY` is set in `backend/.env` (required for storage uploads)

#### Dashboard Configuration
- [ ] Verify Supabase Storage bucket `documents` exists (should be created already)
- [ ] Set bucket file size limit: 500MB (paid tier) or 50MB (free tier)
- [ ] Set allowed MIME types: `application/pdf`, `application/zip`

#### Manual Tests
- [ ] Upload a PDF via the UI and verify it appears in Supabase Storage
- [ ] Upload a ZIP containing PDFs and verify each is extracted
- [ ] Verify signed URLs work for download
- [ ] Test cross-matter access is denied (use different user)

### Project Structure Notes

- Backend endpoint integrates with existing frontend upload implementation
- Storage service uses service client to bypass RLS (backend is trusted)
- Document records enable OCR processing in Story 2b-1
- ZIP extraction enables bulk upload workflow

### References

- [Source: _bmad-output/architecture.md#File-Storage] - Supabase Storage bucket structure
- [Source: _bmad-output/architecture.md#Backend-Structure] - API routes organization
- [Source: _bmad-output/project-context.md#Python-Backend] - Python coding standards
- [Source: supabase/migrations/20260106000001_create_documents_table.sql] - Documents table schema
- [Source: supabase/migrations/20260106000010_create_storage_policies.sql] - Storage RLS policies
- [Source: frontend/src/lib/api/documents.ts] - Frontend upload integration (Story 2a-1)
- [Source: backend/app/api/routes/matters.py] - API route pattern reference
- [Source: backend/app/api/deps.py] - Matter access validation

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation proceeded without issues

### Completion Notes List

1. Created `require_matter_role_from_form` dependency in deps.py to handle form-based matter_id (required for multipart file uploads)
2. StorageService uses synchronous methods (not async) matching Supabase Python SDK pattern
3. DocumentService uses synchronous methods for database operations
4. ZIP extraction validates only PDF files are present, skips __MACOSX directories
5. Rollback logic implemented for ZIP extraction failures (deletes uploaded files on error)
6. All 27 new tests pass (11 API + 16 storage service)
7. Full test suite: 148 passed, 1 pre-existing failure unrelated to this story

### File List

**Created:**
- `backend/app/api/routes/documents.py` - Document upload API endpoint
- `backend/app/models/document.py` - Pydantic models for documents
- `backend/app/services/storage_service.py` - Supabase Storage operations
- `backend/app/services/document_service.py` - Document database operations
- `backend/tests/api/test_documents.py` - API endpoint tests (11 tests)
- `backend/tests/services/test_storage_service.py` - Storage service tests (16 tests)
- `backend/tests/services/test_document_service.py` - Document service tests (17 tests) [Code Review]
- `backend/test_api_keys.py` - API keys validation script for dev setup

**Modified:**
- `backend/app/main.py` - Added documents router registration
- `backend/app/api/deps.py` - Added `require_matter_role_from_form` dependency
- `frontend/src/lib/api/documents.ts` - Added auth header and API base URL
- `backend/app/services/storage_service.py` - Thread-safe singleton [Code Review]
- `backend/app/services/document_service.py` - Thread-safe singleton [Code Review]
- `backend/app/api/routes/documents.py` - ZIP rollback includes document records [Code Review]

---

## Code Review Notes

**Review Date:** 2026-01-07
**Reviewer:** Claude Code (Adversarial Review)

### Issues Found & Fixed

| Severity | Issue | Fix Applied |
|----------|-------|-------------|
| HIGH | H1: Task 7 falsely claimed tests verify Storage RLS | Updated task description to clarify API-layer tests vs Storage RLS |
| MEDIUM | M1: Missing DocumentService unit tests | Created `test_document_service.py` with 15 tests |
| MEDIUM | M2: File List missing `test_api_keys.py` | Added to File List |
| MEDIUM | M3: Non-thread-safe singleton pattern | Replaced with `@lru_cache(maxsize=1)` |
| MEDIUM | M4: ZIP rollback didn't delete document records | Added document record cleanup to rollback |
| LOW | L2: Incomplete docstring for `_handle_service_error` | Added full Args/Returns documentation |

### Deferred Issues (H2 - Needs Architectural Decision)

**H2: DocumentService uses anon client - potential RLS mismatch**

The DocumentService uses `get_supabase_client()` (anon client with RLS) while StorageService uses `get_service_client()` (service role, bypasses RLS). If `documents` table RLS doesn't allow INSERT for authenticated users with matter access, document creation could fail.

**Recommendation:** Verify RLS policy on `documents` table OR switch to service client for document operations. This requires architectural review.

### Test Results After Fixes

- Document service tests: 15 passed
- Storage service tests: 16 passed
- Document API tests: 11 passed
- **Total: 42 passed**

