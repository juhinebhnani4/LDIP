# Story 10D.3: Implement Documents Tab File List

Status: dev-complete

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to see all documents in my matter with status**,
So that **I can manage my document collection**.

## Acceptance Criteria

1. **Given** I open the Documents tab
   **When** the content loads
   **Then** I see a table with columns: document name, page count, date added, status (Indexed/Processing), type badge (case_file/act/annexure), action menu

2. **Given** documents are processing
   **When** the list loads
   **Then** processing documents show an inline progress bar
   **And** message: "Processing NEW DOCUMENTS: X files, Y%"

3. **Given** I click "+ ADD FILES"
   **When** the upload dialog opens
   **Then** I can drag-drop or browse files to add to the matter
   **And** message: "You can continue working while this processes"

## Tasks / Subtasks

- [x] Task 1: Create DocumentsContent container component (AC: #1)
  - [x] 1.1: Create `DocumentsContent.tsx` following Content component pattern
  - [x] 1.2: Create `DocumentsSkeleton` loading state component
  - [x] 1.3: Create `DocumentsError` error state component
  - [x] 1.4: Wire up to existing `DocumentList` component
  - [x] 1.5: Add header with title and "+ ADD FILES" button

- [x] Task 2: Create DocumentsHeader with statistics and processing banner (AC: #2)
  - [x] 2.1: Create `DocumentsHeader.tsx` component
  - [x] 2.2: Display total document count and breakdown by type
  - [x] 2.3: Show processing banner when documents are processing
  - [x] 2.4: Display progress indicator: "Processing NEW DOCUMENTS: X files, Y%"
  - [x] 2.5: Implement auto-refresh polling when processing active

- [x] Task 3: Update DocumentList columns per AC requirements (AC: #1)
  - [x] 3.1: Add page count column (currently missing from DocumentList)
  - [x] 3.2: Update status column to use "Indexed/Processing" labels per AC
  - [x] 3.3: Ensure type badge column displays correctly
  - [x] 3.4: Add action menu column (placeholder for Story 10D.4)
  - [x] 3.5: Verify all sorting works on new columns

- [x] Task 4: Create AddDocumentsDialog for in-matter uploads (AC: #3)
  - [x] 4.1: Create `AddDocumentsDialog.tsx` with Modal wrapper
  - [x] 4.2: Integrate existing `UploadDropzone` component
  - [x] 4.3: Show "You can continue working while this processes" message
  - [x] 4.4: Handle upload initiation and close dialog
  - [x] 4.5: Trigger background processing start notification

- [x] Task 5: Update documents page to use DocumentsContent (AC: All)
  - [x] 5.1: Update `app/(matter)/[matterId]/documents/page.tsx`
  - [x] 5.2: Replace placeholder with DocumentsContent component
  - [x] 5.3: Add proper accessibility attributes
  - [x] 5.4: Ensure matterId is passed correctly

- [x] Task 6: Write comprehensive tests (AC: All)
  - [x] 6.1: Create `DocumentsContent.test.tsx` with loading/error/data states
  - [x] 6.2: Create `DocumentsHeader.test.tsx` with processing banner tests
  - [x] 6.3: Add `AddDocumentsDialog.test.tsx` tests
  - [x] 6.4: Update `DocumentList.test.tsx` for new columns
  - [x] 6.5: Test processing status polling behavior
  - [x] 6.6: Test accessibility (ARIA labels, keyboard navigation)

- [x] Task 7: Run all tests and lint validation (AC: All)
  - [x] 7.1: Run `npm run test` - all document tests passing (176 tests pass)
  - [x] 7.2: Run `npm run lint` - no errors in new files
  - [x] 7.3: Run TypeScript compiler - no type errors
  - [x] 7.4: Verify total test count (176 tests)

## Dev Notes

### Critical Architecture Pattern: REUSE EXISTING COMPONENTS

**IMPORTANT: Significant infrastructure already exists from Epic 2A**

This story should build on existing components, NOT recreate them:

| Existing Component | Location | What to Reuse |
|-------------------|----------|---------------|
| `DocumentList` | `components/features/document/DocumentList.tsx` | **Core table with sorting, filtering, selection** |
| `DocumentTypeBadge` | `components/features/document/DocumentTypeBadge.tsx` | Type badge display |
| `DocumentProcessingStatus` | `components/features/document/DocumentProcessingStatus.tsx` | Processing status with polling |
| `OCRQualityBadge` | `components/features/document/OCRQualityBadge.tsx` | OCR quality indicator |
| `UploadDropzone` | `components/features/document/UploadDropzone.tsx` | File upload UI |
| `fetchDocuments` | `lib/api/documents.ts` | API client for document list |

### What Needs to Be Created

1. **DocumentsContent** - Container component (following VerificationContent pattern)
2. **DocumentsHeader** - Header with stats and processing banner
3. **AddDocumentsDialog** - Modal for in-matter uploads
4. **Page update** - Replace placeholder with real content

### Existing DocumentList Analysis

The existing `DocumentList.tsx` (lines 153-513) already provides:
- ✅ Paginated table display
- ✅ Sorting on filename, type, status, size, uploaded date
- ✅ Filtering by document type and status
- ✅ Bulk selection and type change
- ✅ Type badge with inline selector
- ✅ Processing status polling via `DocumentProcessingStatus`
- ✅ OCR quality badge display
- ✅ File size formatting
- ✅ Date formatting
- ⚠️ **Missing:** Page count column (needs backend update or type extension)
- ⚠️ **Missing:** Action menu column (Story 10D.4)

### Column Requirements vs Current Implementation

| AC Column | Current Status | Work Needed |
|-----------|---------------|-------------|
| Document name | ✅ Implemented (filename) | None |
| Page count | ❌ Not displayed | Add column - `pageCount` exists in type but may be null |
| Date added | ✅ Implemented (uploadedAt) | None |
| Status (Indexed/Processing) | ⚠️ Different labels | Map status values to "Indexed"/"Processing" |
| Type badge | ✅ Implemented | None |
| Action menu | ❌ Not implemented | Add for Story 10D.4 (placeholder for now) |

### Status Label Mapping

```typescript
// Current labels in DocumentList.tsx (lines 54-61)
const STATUS_LABELS: Record<DocumentStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  ocr_complete: 'OCR Complete',
  completed: 'Completed',     // AC says "Indexed"
  ocr_failed: 'OCR Failed',
  failed: 'Failed',
};

// AC requirement: "Indexed" and "Processing"
// Simplify to user-friendly terms:
// - completed, ocr_complete → "Indexed"
// - processing, pending → "Processing"
// - failed, ocr_failed → "Failed"
```

### Processing Banner Requirements (AC #2)

The processing banner should:
1. Only show when at least one document has status `processing` or `pending`
2. Display count and percentage: "Processing NEW DOCUMENTS: X files, Y%"
3. Auto-refresh via polling (existing DocumentProcessingStatus pattern)

**Implementation approach:**
```typescript
// In DocumentsHeader or DocumentsContent
const processingDocs = documents.filter(d =>
  d.status === 'processing' || d.status === 'pending'
);

const processingCount = processingDocs.length;
const totalDocs = documents.length;
const processingPercent = totalDocs > 0
  ? Math.round((processingDocs.length / totalDocs) * 100)
  : 0;

{processingCount > 0 && (
  <Alert>
    <Loader2 className="animate-spin" />
    <AlertDescription>
      Processing NEW DOCUMENTS: {processingCount} files, {processingPercent}%
    </AlertDescription>
  </Alert>
)}
```

### Add Files Dialog (AC #3)

The dialog should:
1. Use existing `UploadDropzone` component
2. Pass current `matterId` for uploads
3. Show informational message about background processing
4. Close after upload initiation
5. Optionally navigate to processing screen or stay on documents tab

**Integration with existing upload flow:**
- Epic 9 implemented full upload wizard for new matters
- For existing matters, we need a simpler "add more files" flow
- Reuse `uploadFiles` from `lib/api/documents.ts`

### Content Component Pattern (from VerificationContent)

```typescript
// Standard Content component structure
interface DocumentsContentProps {
  matterId: string;
  className?: string;
}

export function DocumentsContent({ matterId, className }: DocumentsContentProps) {
  // 1. Data fetching hooks
  const { documents, isLoading, error, refresh } = useDocuments(matterId);

  // 2. Local UI state
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  // 3. Derived state
  const processingDocs = useMemo(() =>
    documents.filter(d => d.status === 'processing' || d.status === 'pending'),
    [documents]
  );

  // 4. Callbacks
  const handleAddFiles = useCallback(() => setAddDialogOpen(true), []);
  const handleUploadComplete = useCallback(() => {
    setAddDialogOpen(false);
    refresh();
  }, [refresh]);

  // 5. Loading/error states
  if (isLoading) return <DocumentsSkeleton />;
  if (error) return <DocumentsError message={error} />;

  // 6. Render
  return (
    <div className={cn('space-y-6', className)}>
      <DocumentsHeader
        onAddFiles={handleAddFiles}
        processingCount={processingDocs.length}
        totalCount={documents.length}
      />
      <DocumentList
        matterId={matterId}
        onDocumentClick={handleDocumentClick}
      />
      <AddDocumentsDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        matterId={matterId}
        onComplete={handleUploadComplete}
      />
    </div>
  );
}
```

### TypeScript Types (Existing)

All types already exist in `types/document.ts`:
- `DocumentType`: 'case_file' | 'act' | 'annexure' | 'other'
- `DocumentStatus`: 'pending' | 'processing' | 'ocr_complete' | 'completed' | 'ocr_failed' | 'failed'
- `DocumentListItem`: Full interface with all fields
- `DocumentFilters`, `DocumentSort`: Filter and sort types

### API Endpoints (Existing)

| Endpoint | Function | Status |
|----------|----------|--------|
| `GET /api/matters/{matterId}/documents` | `fetchDocuments()` | ✅ Implemented |
| `GET /api/documents/{docId}` | `fetchDocument()` | ✅ Implemented |
| `PATCH /api/documents/{docId}` | `updateDocument()` | ✅ Implemented |
| `POST /api/documents/upload` | `uploadFile()` | ✅ Implemented |

### Zustand Store Pattern (MANDATORY)

```typescript
// CORRECT - Use selectors
const documents = useDocumentsStore((state) => state.documents);
const isLoading = useDocumentsStore((state) => state.isLoading);

// WRONG - Full store subscription (causes re-renders)
const { documents, isLoading, filters } = useDocumentsStore();
```

**Note:** A Zustand store may not be needed if using SWR/React Query pattern with `useCallback` for handlers (like existing `DocumentList` does internally).

### Project Structure Notes

```
frontend/src/
├── app/(matter)/[matterId]/
│   └── documents/
│       └── page.tsx              # UPDATE - Replace placeholder
├── components/features/document/
│   ├── DocumentList.tsx          # EXISTING - Main table (may need column updates)
│   ├── DocumentTypeBadge.tsx     # EXISTING - Type badge
│   ├── DocumentProcessingStatus.tsx # EXISTING - Status polling
│   ├── OCRQualityBadge.tsx       # EXISTING - OCR badge
│   ├── UploadDropzone.tsx        # EXISTING - Upload UI
│   ├── DocumentsContent.tsx      # NEW - Container component
│   ├── DocumentsHeader.tsx       # NEW - Header with stats/banner
│   ├── AddDocumentsDialog.tsx    # NEW - Upload dialog
│   ├── DocumentsContent.test.tsx # NEW - Tests
│   ├── DocumentsHeader.test.tsx  # NEW - Tests
│   ├── AddDocumentsDialog.test.tsx # NEW - Tests
│   └── index.ts                  # UPDATE - Add exports
└── hooks/
    └── useDocuments.ts           # NEW (optional) - If not using DocumentList internal state
```

### Previous Story Intelligence (Story 10D.2)

**Key Learnings:**
1. Content components follow consistent pattern across tabs
2. Use hooks for data fetching, not inline fetches
3. Skeleton components provide good loading UX
4. Tier badges can be clickable to apply filters
5. Test coverage should be comprehensive (111+ tests for verification)

### Git Commit Pattern

```
feat(documents): implement documents tab file list (Story 10D.3)
```

### Testing Checklist

- [ ] DocumentsContent renders loading skeleton
- [ ] DocumentsContent renders error state
- [ ] DocumentsContent renders document list
- [ ] DocumentsHeader displays correct counts
- [ ] Processing banner shows when documents processing
- [ ] Processing banner hidden when no processing
- [ ] Add Files button opens dialog
- [ ] AddDocumentsDialog renders dropzone
- [ ] AddDocumentsDialog shows informational message
- [ ] Upload triggers refresh on completion
- [ ] Page count column displays (or "—" if null)
- [ ] Status shows "Indexed" for completed documents
- [ ] Accessibility: ARIA labels present
- [ ] Accessibility: Keyboard navigation works

### References

- [Source: epics.md#Story-10D.5 - Acceptance Criteria (labeled as 10D.5 in epics file)]
- [Source: 10d-2-verification-statistics-filtering.md - Previous story patterns]
- [Source: DocumentList.tsx - Existing table implementation]
- [Source: VerificationContent.tsx - Content component pattern]
- [Source: lib/api/documents.ts - API client functions]
- [Source: types/document.ts - TypeScript types]
- [Source: project-context.md - Zustand selectors, naming conventions]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation completed successfully.

### Completion Notes List

1. Created `DocumentsContent.tsx` container component following VerificationContent pattern
2. Created `DocumentsHeader.tsx` with document count, type breakdown, and processing banner
3. Created `AddDocumentsDialog.tsx` for in-matter uploads with UploadDropzone integration
4. Updated `DocumentList.tsx` to add page count column, action menu placeholder, and user-friendly status labels
5. Created `useDocuments.ts` hook for document fetching with polling support
6. Updated `DocumentListItem` type to include `pageCount` field
7. Replaced placeholder documents page with DocumentsContent component
8. Created comprehensive tests: DocumentsContent.test.tsx, DocumentsHeader.test.tsx, AddDocumentsDialog.test.tsx, useDocuments.test.ts
9. Updated DocumentList.test.tsx for new columns (page count, action menu)
10. All 176 tests pass, TypeScript compiles with no errors

### File List

**New Files:**
- `frontend/src/components/features/document/DocumentsContent.tsx` - Container component
- `frontend/src/components/features/document/DocumentsHeader.tsx` - Header with stats/processing banner
- `frontend/src/components/features/document/AddDocumentsDialog.tsx` - Upload dialog
- `frontend/src/components/features/document/DocumentsContent.test.tsx` - Container tests
- `frontend/src/components/features/document/DocumentsHeader.test.tsx` - Header tests
- `frontend/src/components/features/document/AddDocumentsDialog.test.tsx` - Dialog tests
- `frontend/src/hooks/useDocuments.ts` - Document fetching hook
- `frontend/src/hooks/useDocuments.test.ts` - Hook tests

**Modified Files:**
- `frontend/src/components/features/document/DocumentList.tsx` - Added page count column, action menu, status labels
- `frontend/src/components/features/document/DocumentList.test.tsx` - Updated for new columns
- `frontend/src/components/features/document/index.ts` - Added exports
- `frontend/src/types/document.ts` - Added pageCount to DocumentListItem
- `frontend/src/app/(matter)/[matterId]/documents/page.tsx` - Replaced placeholder with DocumentsContent
