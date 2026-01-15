# Story 10D.4: Implement Documents Tab File Actions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to manage individual documents**,
So that **I can rename, reclassify, or remove documents**.

## Acceptance Criteria

1. **Given** I click the action menu on a document
   **When** the menu opens
   **Then** I see options: View, Rename, Set as Act, Delete

2. **Given** I select "View"
   **When** the action executes
   **Then** the PDF viewer opens to display the document

3. **Given** I select "Rename"
   **When** the dialog opens
   **Then** I can enter a new name
   **And** the document is renamed

4. **Given** I select "Set as Act"
   **When** the action executes
   **Then** the document is moved to the acts folder
   **And** is_reference_material is set to true
   **And** citations can be verified against it

5. **Given** I select "Delete"
   **When** the confirmation appears
   **Then** I must confirm deletion
   **And** the document is soft-deleted (30-day retention)

## Tasks / Subtasks

- [x] Task 1: Create DocumentActionMenu dropdown component (AC: #1)
  - [x] 1.1: Create `DocumentActionMenu.tsx` with DropdownMenu structure
  - [x] 1.2: Add View, Rename, Set as Act, Delete menu items
  - [x] 1.3: Add icons for each action (Eye, Pencil, FileText, Trash2)
  - [x] 1.4: Apply destructive styling to Delete option
  - [x] 1.5: Add role-based visibility (Delete for OWNER only)
  - [x] 1.6: Wire up event handlers (onView, onRename, onSetAsAct, onDelete)

- [x] Task 2: Implement View action with PDF viewer (AC: #2)
  - [x] 2.1: Add `handleViewDocument` function to fetch signed URL
  - [x] 2.2: Open document in new browser tab with signed URL
  - [x] 2.3: Show loading state while fetching URL
  - [x] 2.4: Handle fetch errors with toast notification

- [x] Task 3: Create RenameDocumentDialog component (AC: #3)
  - [x] 3.1: Create `RenameDocumentDialog.tsx` with Dialog wrapper
  - [x] 3.2: Add input field with current filename as default
  - [x] 3.3: Implement filename validation (1-255 chars, no special chars)
  - [x] 3.4: Add Cancel and Rename buttons
  - [x] 3.5: Handle submission with loading state
  - [x] 3.6: Close dialog and refresh list on success

- [x] Task 4: Add backend rename support (AC: #3)
  - [x] 4.1: Add `filename` field to `DocumentUpdateRequest` Pydantic model
  - [x] 4.2: Update `update_document()` service method to handle filename
  - [x] 4.3: Add validation for filename uniqueness in matter (optional)
  - [x] 4.4: Add frontend `renameDocument()` API function
  - [x] 4.5: Add TypeScript type for updated DocumentUpdateRequest

- [x] Task 5: Implement Set as Act action (AC: #4)
  - [x] 5.1: Add `handleSetAsAct` function using existing `updateDocument()`
  - [x] 5.2: Set documentType='act' and isReferenceMaterial=true
  - [x] 5.3: Show confirmation toast with type badge update
  - [x] 5.4: Refresh document list to reflect change
  - [x] 5.5: Handle documents already marked as Act (disable option or show info)

- [x] Task 6: Create DeleteDocumentDialog component (AC: #5)
  - [x] 6.1: Create `DeleteDocumentDialog.tsx` with AlertDialog wrapper
  - [x] 6.2: Show document filename in confirmation message
  - [x] 6.3: Display 30-day soft-delete retention info
  - [x] 6.4: Add Cancel and Delete buttons (Delete with destructive styling)
  - [x] 6.5: Handle deletion with loading state
  - [x] 6.6: Close dialog and remove from list on success

- [x] Task 7: Add backend delete endpoint (AC: #5)
  - [x] 7.1: Create DELETE `/api/documents/{document_id}` endpoint
  - [x] 7.2: Implement soft-delete: set `deleted_at` timestamp, retain 30 days
  - [x] 7.3: Add OWNER-only role check (or EDITOR if decided)
  - [x] 7.4: Return cascade info (chunks, embeddings affected)
  - [x] 7.5: Add frontend `deleteDocument()` API function

- [x] Task 8: Integrate action menu in DocumentList (AC: All)
  - [x] 8.1: Replace disabled placeholder button with DocumentActionMenu
  - [x] 8.2: Pass document data and handlers to menu component
  - [x] 8.3: Add dialog state management (renameDialogOpen, deleteDialogOpen)
  - [x] 8.4: Track selectedDocument for dialog context
  - [x] 8.5: Wire up refresh callback after successful actions

- [x] Task 9: Write comprehensive tests (AC: All)
  - [x] 9.1: Create `DocumentActionMenu.test.tsx` with all action tests
  - [x] 9.2: Create `RenameDocumentDialog.test.tsx` with validation tests
  - [x] 9.3: Create `DeleteDocumentDialog.test.tsx` with confirmation tests
  - [x] 9.4: Add API mock tests for deleteDocument, renameDocument
  - [x] 9.5: Test role-based action visibility
  - [x] 9.6: Test loading and error states
  - [x] 9.7: Test keyboard navigation and accessibility

- [x] Task 10: Run all tests and lint validation (AC: All)
  - [x] 10.1: Run `npm run test` - all document tests passing
  - [x] 10.2: Run `npm run lint` - no errors in new files
  - [x] 10.3: Run TypeScript compiler - no type errors
  - [x] 10.4: Run backend tests `pytest tests/api/test_documents.py`
  - [x] 10.5: Run backend linter `ruff check`

## Dev Notes

### Critical Architecture Pattern: REUSE EXISTING COMPONENTS

**IMPORTANT: Significant infrastructure already exists**

| Existing Component | Location | What to Reuse |
|-------------------|----------|---------------|
| `DocumentList` | `components/features/document/DocumentList.tsx` | Action menu placeholder at line 512-530 |
| `updateDocument()` | `lib/api/documents.ts:327` | For Set as Act action |
| `fetchDocument()` | `lib/api/documents.ts:292` | Returns signed_url for View |
| `ManualReviewDialog` | `components/features/document/ManualReviewDialog.tsx` | Dialog pattern reference |
| `DropdownMenu` | `components/ui/dropdown-menu.tsx` | Full action menu UI |
| `AlertDialog` | `components/ui/alert-dialog.tsx` | Delete confirmation |

### What Needs to Be Created

**Frontend:**
1. **DocumentActionMenu.tsx** - Dropdown with View/Rename/Set as Act/Delete
2. **RenameDocumentDialog.tsx** - Modal for entering new filename
3. **DeleteDocumentDialog.tsx** - Confirmation dialog with soft-delete info
4. **API functions** - `deleteDocument()`, `renameDocument()` in documents.ts

**Backend:**
1. **DELETE endpoint** - `/api/documents/{document_id}` in documents.py
2. **Filename field** - Add to `DocumentUpdateRequest` Pydantic model
3. **Service update** - Handle filename in `update_document()`

### Current Action Menu Placeholder (DocumentList.tsx:512-530)

```tsx
{/* Action menu - placeholder for Story 10D.4 */}
<TableCell onClick={(e) => e.stopPropagation()}>
  <Tooltip>
    <TooltipTrigger asChild>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label={`Actions for ${doc.filename}`}
        disabled  // REMOVE THIS - enable for 10D.4
      >
        <MoreVertical className="h-4 w-4" />
      </Button>
    </TooltipTrigger>
    <TooltipContent>
      <p>Actions coming in Story 10D.4</p>  {/* REPLACE WITH ACTUAL MENU */}
    </TooltipContent>
  </Tooltip>
</TableCell>
```

### Action Menu Implementation Pattern

```tsx
// DocumentActionMenu.tsx
interface DocumentActionMenuProps {
  document: DocumentListItem;
  onView: () => void;
  onRename: () => void;
  onSetAsAct: () => void;
  onDelete: () => void;
  userRole?: MatterRole;
  disabled?: boolean;
}

export function DocumentActionMenu({
  document,
  onView,
  onRename,
  onSetAsAct,
  onDelete,
  userRole = MatterRole.EDITOR,
  disabled = false,
}: DocumentActionMenuProps) {
  const isAct = document.documentType === 'act';
  const canDelete = userRole === MatterRole.OWNER;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label={`Actions for ${document.filename}`}
          disabled={disabled}
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={onView}>
          <Eye className="mr-2 h-4 w-4" />
          View
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onRename}>
          <Pencil className="mr-2 h-4 w-4" />
          Rename
        </DropdownMenuItem>
        {!isAct && (
          <DropdownMenuItem onClick={onSetAsAct}>
            <FileText className="mr-2 h-4 w-4" />
            Set as Act
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        {canDelete && (
          <DropdownMenuItem
            onClick={onDelete}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

### View Action Implementation

```typescript
// In DocumentsContent or DocumentList
const handleViewDocument = async (document: DocumentListItem) => {
  try {
    const result = await fetchDocument(document.id);
    if (result.data?.signedUrl) {
      window.open(result.data.signedUrl, '_blank');
    }
  } catch (error) {
    toast.error('Failed to open document');
  }
};
```

### Rename Dialog Implementation Pattern

```tsx
// RenameDocumentDialog.tsx
interface RenameDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  document: DocumentListItem;
  onRename: (newFilename: string) => Promise<void>;
}

export function RenameDocumentDialog({
  open,
  onOpenChange,
  document,
  onRename,
}: RenameDocumentDialogProps) {
  const [filename, setFilename] = useState(document.filename);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateFilename = (name: string): string | null => {
    if (name.length < 1) return 'Filename is required';
    if (name.length > 255) return 'Filename must be 255 characters or less';
    if (/[<>:"/\\|?*]/.test(name)) return 'Filename contains invalid characters';
    return null;
  };

  const handleSubmit = async () => {
    const validationError = validateFilename(filename);
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSubmitting(true);
    try {
      await onRename(filename);
      onOpenChange(false);
    } catch (err) {
      setError('Failed to rename document');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rename Document</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Input
            value={filename}
            onChange={(e) => {
              setFilename(e.target.value);
              setError(null);
            }}
            placeholder="Enter new filename"
            aria-label="New filename"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Renaming...' : 'Rename'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

### Delete Dialog Implementation Pattern

```tsx
// DeleteDocumentDialog.tsx
interface DeleteDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  document: DocumentListItem;
  onDelete: () => Promise<void>;
}

export function DeleteDocumentDialog({
  open,
  onOpenChange,
  document,
  onDelete,
}: DeleteDocumentDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete();
      onOpenChange(false);
    } catch (error) {
      // Error handled by parent
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Document</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{document.filename}"?
            <br />
            <span className="text-muted-foreground">
              The document will be retained for 30 days before permanent deletion.
            </span>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

### Backend Delete Endpoint

```python
# In documents.py router
@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
) -> DocumentDeleteResponse:
    """
    Soft-delete a document (30-day retention).

    Requires OWNER role on the matter.
    """
    # Get document
    doc = await document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify OWNER access
    _verify_matter_access(
        matter_id=doc.matter_id,
        user_id=current_user.id,
        matter_service=matter_service,
        allowed_roles=[MatterRole.OWNER],
    )

    # Soft delete
    result = await document_service.soft_delete_document(document_id)

    return DocumentDeleteResponse(
        success=True,
        message=f"Document will be permanently deleted after 30 days",
        deleted_at=result.deleted_at,
    )
```

### Backend Filename Update

```python
# In models/document.py - update DocumentUpdateRequest
class DocumentUpdateRequest(BaseModel):
    document_type: DocumentType | None = None
    is_reference_material: bool | None = None
    filename: str | None = Field(None, min_length=1, max_length=255)  # NEW
```

```python
# In document_service.py - update update_document method
async def update_document(
    self,
    document_id: str,
    update: DocumentUpdateRequest,
) -> Document:
    updates = {}

    if update.document_type is not None:
        updates['document_type'] = update.document_type
        if update.document_type == 'act':
            updates['is_reference_material'] = True

    if update.is_reference_material is not None:
        updates['is_reference_material'] = update.is_reference_material

    if update.filename is not None:  # NEW
        updates['filename'] = update.filename

    # ... rest of update logic
```

### Frontend API Functions

```typescript
// In lib/api/documents.ts

/**
 * Delete a document (soft-delete with 30-day retention)
 */
export async function deleteDocument(documentId: string): Promise<APIResponse<{ message: string }>> {
  const response = await fetch(`${API_BASE}/api/documents/${documentId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  return response.json();
}

/**
 * Rename a document
 */
export async function renameDocument(
  documentId: string,
  filename: string
): Promise<APIResponse<Document>> {
  return updateDocument(documentId, { filename });
}
```

### TypeScript Type Updates

```typescript
// In types/document.ts - update DocumentUpdateRequest
export interface DocumentUpdateRequest {
  documentType?: DocumentType;
  isReferenceMaterial?: boolean;
  filename?: string;  // NEW
}
```

### Role-Based Action Visibility

| Action | VIEWER | EDITOR | OWNER |
|--------|--------|--------|-------|
| View | ✓ | ✓ | ✓ |
| Rename | ✗ | ✓ | ✓ |
| Set as Act | ✗ | ✓ | ✓ |
| Delete | ✗ | ✗ | ✓ |

**Note:** Consider whether EDITOR should be able to delete. AC says "soft-deleted" which is recoverable, so EDITOR might be appropriate. Final decision TBD.

### Soft-Delete Implementation

Documents table needs `deleted_at` column:
```sql
-- If not already present
ALTER TABLE documents ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;

-- Soft delete sets timestamp
UPDATE documents SET deleted_at = NOW() WHERE id = $1;

-- List excludes soft-deleted
SELECT * FROM documents WHERE deleted_at IS NULL AND matter_id = $1;

-- Cleanup job (runs daily)
DELETE FROM documents WHERE deleted_at < NOW() - INTERVAL '30 days';
```

### Project Structure Notes

```
frontend/src/
├── components/features/document/
│   ├── DocumentList.tsx              # UPDATE - Replace placeholder with DocumentActionMenu
│   ├── DocumentActionMenu.tsx        # NEW - Action dropdown component
│   ├── RenameDocumentDialog.tsx      # NEW - Rename modal
│   ├── DeleteDocumentDialog.tsx      # NEW - Delete confirmation
│   ├── DocumentActionMenu.test.tsx   # NEW - Tests
│   ├── RenameDocumentDialog.test.tsx # NEW - Tests
│   ├── DeleteDocumentDialog.test.tsx # NEW - Tests
│   └── index.ts                      # UPDATE - Add exports
├── lib/api/
│   └── documents.ts                  # UPDATE - Add deleteDocument, renameDocument
└── types/
    └── document.ts                   # UPDATE - Add filename to DocumentUpdateRequest

backend/app/
├── api/routes/
│   └── documents.py                  # UPDATE - Add DELETE endpoint
├── models/
│   └── document.py                   # UPDATE - Add filename to DocumentUpdateRequest
└── services/
    └── document_service.py           # UPDATE - Handle filename, add soft_delete_document
```

### Previous Story Intelligence (Story 10D.3)

**Key Learnings:**
1. Content components follow consistent pattern across tabs
2. DocumentList already has action menu placeholder ready to replace
3. Dialog patterns from ManualReviewDialog and AddDocumentsDialog work well
4. useDocuments hook provides refresh callback for list updates
5. Processing status already handled by existing components
6. Toast notifications for success/error feedback
7. Loading states with disabled buttons during async operations

**Code Review Fixes from 10D.3:**
1. Double data fetching fixed - DocumentList supports controlled mode
2. Progress bar semantics improved
3. Accessibility tests comprehensive

### Git Commit Pattern

```
feat(documents): implement documents tab file actions (Story 10D.4)
```

### Testing Checklist

- [ ] DocumentActionMenu renders all options
- [ ] View opens document in new tab
- [ ] Rename dialog validates filename
- [ ] Rename updates document and refreshes list
- [ ] Set as Act changes type badge to "Act"
- [ ] Delete shows confirmation dialog
- [ ] Delete removes document from list
- [ ] Role-based visibility (Delete hidden for non-OWNER)
- [ ] Loading states during async actions
- [ ] Error handling with toast notifications
- [ ] Keyboard navigation (Enter/Space to activate)
- [ ] Accessibility: ARIA labels present
- [ ] Backend: DELETE endpoint returns correct response
- [ ] Backend: PATCH with filename updates correctly

### References

- [Source: epics.md#Story-10D.6 - Acceptance Criteria (labeled as 10D.6 in epics file)]
- [Source: 10d-3-documents-file-list.md - Previous story with DocumentList implementation]
- [Source: DocumentList.tsx:512-530 - Action menu placeholder]
- [Source: lib/api/documents.ts - Existing API functions]
- [Source: ManualReviewDialog.tsx - Dialog pattern reference]
- [Source: components/ui/dropdown-menu.tsx - DropdownMenu component]
- [Source: components/ui/alert-dialog.tsx - AlertDialog component]
- [Source: project-context.md - Zustand selectors, naming conventions]
- [Source: document_service.py:534 - Existing delete_document method]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

#### Frontend - New Components
- `frontend/src/components/features/document/DocumentActionMenu.tsx` - Dropdown action menu component
- `frontend/src/components/features/document/RenameDocumentDialog.tsx` - Rename document dialog
- `frontend/src/components/features/document/DeleteDocumentDialog.tsx` - Delete confirmation dialog

#### Frontend - Modified Files
- `frontend/src/components/features/document/DocumentList.tsx` - Integrated action menu, added handlers
- `frontend/src/components/features/document/index.ts` - Added exports for new components
- `frontend/src/lib/api/documents.ts` - Added deleteDocument, renameDocument functions
- `frontend/src/types/document.ts` - Added filename to DocumentUpdateRequest

#### Frontend - Test Files
- `frontend/src/components/features/document/__tests__/DocumentActionMenu.test.tsx` - 14 tests
- `frontend/src/components/features/document/__tests__/RenameDocumentDialog.test.tsx` - 21 tests
- `frontend/src/components/features/document/__tests__/DeleteDocumentDialog.test.tsx` - 10 tests
- `frontend/src/components/features/document/DocumentList.test.tsx` - Updated tests

#### Backend - Modified Files
- `backend/app/api/routes/documents.py` - Added DELETE endpoint, updated exception handling
- `backend/app/models/document.py` - Added filename field to DocumentUpdateRequest
- `backend/app/services/document_service.py` - Added soft_delete_document, filename update support

#### Backend - Test Files
- `backend/tests/services/test_document_service.py` - Tests for delete and rename

#### Database Migrations
- `supabase/migrations/20260115000002_add_documents_soft_delete.sql` - Added deleted_at column

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-15 | Initial implementation of document file actions | Dev Agent |
| 2026-01-15 | Code review fixes: removed unused import, added clarifying comments, fixed test act() warnings, removed unused variable, improved exception chaining, added null pageCount test | Code Review |

