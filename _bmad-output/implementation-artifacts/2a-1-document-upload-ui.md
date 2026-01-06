# Story 2A.1: Implement Document Upload UI

Status: done

## Story

As an **attorney**,
I want **to upload PDF and ZIP files via drag-and-drop with clear progress indicators**,
So that **I can easily add case documents to my matter**.

## Acceptance Criteria

1. **Given** I am in a matter workspace or upload flow **When** I drag files onto the drop zone **Then** the drop zone highlights to indicate it will accept the files **And** supported file types (PDF, ZIP) are accepted **And** unsupported file types show an error message

2. **Given** I drop valid files **When** the upload begins **Then** I see a progress bar for each file showing upload percentage **And** I see the file name and size

3. **Given** a file exceeds 500MB **When** I attempt to upload it **Then** the file is rejected with message "File exceeds 500MB limit"

4. **Given** I have more than 100 files to upload **When** I attempt to upload them **Then** only the first 100 are accepted **And** I see a warning "Maximum 100 files per upload"

5. **Given** I click "Browse Files" button **When** the file picker opens **Then** I can select PDF and ZIP files from my computer **And** selected files are added to the upload queue

## Tasks / Subtasks

- [x] Task 1: Create UploadDropzone component (AC: #1)
  - [x] Create `frontend/src/components/features/document/UploadDropzone.tsx`
  - [x] Implement drag-and-drop zone with visual feedback (border highlight, icon change)
  - [x] Add file type validation (PDF, ZIP only)
  - [x] Show error toast for unsupported file types
  - [x] Use shadcn/ui `Card` component as container

- [x] Task 2: Implement file validation logic (AC: #3, #4)
  - [x] Create validation utility in `frontend/src/lib/utils/upload-validation.ts`
  - [x] Implement 500MB file size limit check
  - [x] Implement 100 files per upload limit
  - [x] Return structured validation errors with user-friendly messages

- [x] Task 3: Create upload progress UI (AC: #2)
  - [x] Create `frontend/src/components/features/document/UploadProgress.tsx`
  - [x] Show file name, size (formatted), and progress percentage
  - [x] Use shadcn/ui `Progress` component for progress bar
  - [x] Add cancel button for individual file uploads
  - [x] Group multiple files in a scrollable list

- [x] Task 4: Implement Browse Files button (AC: #5)
  - [x] Add hidden file input with accept=".pdf,.zip"
  - [x] Style button using shadcn/ui `Button` component
  - [x] Connect to same upload handler as drag-drop

- [x] Task 5: Create upload store with Zustand (AC: #2)
  - [x] Create `frontend/src/stores/uploadStore.ts`
  - [x] Track upload queue, progress, and status per file
  - [x] Actions: addFiles, removeFile, updateProgress, clearCompleted
  - [x] Use selectors pattern (NOT destructuring)

- [x] Task 6: Implement upload API integration
  - [x] Create `frontend/src/lib/api/documents.ts` upload function
  - [x] Use fetch with XMLHttpRequest for progress tracking
  - [x] Handle upload to Supabase Storage via backend API
  - [x] Include matter_id and document metadata in request

- [x] Task 7: Write component tests
  - [x] Create `frontend/src/components/features/document/UploadDropzone.test.tsx`
  - [x] Create `frontend/src/components/features/document/UploadProgress.test.tsx`
  - [x] Test drag-enter/leave visual states
  - [x] Test file type rejection
  - [x] Test size limit rejection
  - [x] Test file count limit warning
  - [x] Test progress display and cancel functionality

## Dev Notes

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Technology Stack
- **Next.js 16** with App Router (NOT Pages Router)
- **TypeScript 5.x** strict mode - NO `any` types allowed
- **React 19** - use new concurrent features where appropriate
- **shadcn/ui** - use existing components, don't create custom primitives
- **Zustand** for state management - ALWAYS use selectors, NEVER destructure

#### File Organization (CRITICAL)
```
frontend/src/
├── components/
│   └── features/
│       └── document/
│           ├── UploadDropzone.tsx      (NEW)
│           ├── UploadDropzone.test.tsx (NEW)
│           ├── UploadProgress.tsx      (NEW)
│           └── UploadProgress.test.tsx (NEW)
├── lib/
│   ├── api/
│   │   └── documents.ts                (NEW)
│   └── utils/
│       └── upload-validation.ts        (NEW)
├── stores/
│   └── uploadStore.ts                  (NEW)
└── types/
    └── document.ts                     (UPDATE)
```

#### Zustand Pattern (MANDATORY)

```typescript
// CORRECT - Selector pattern
const uploadQueue = useUploadStore((state) => state.uploadQueue);
const addFiles = useUploadStore((state) => state.addFiles);

// WRONG - Full store subscription (causes re-renders)
const { uploadQueue, addFiles } = useUploadStore();
```

#### TypeScript Strict Mode Requirements

```typescript
// CORRECT - Typed interfaces
interface UploadFile {
  id: string;
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

// WRONG - Using any
const handleFiles = (files: any) => { ... }
```

### UI Component Patterns

#### Dropzone Visual States

| State | Border | Background | Icon |
|-------|--------|------------|------|
| Default | dashed gray | transparent | Upload icon |
| Drag Over | dashed blue | blue/10 | Upload icon (animated) |
| Invalid File | dashed red | red/10 | X icon |
| Uploading | solid blue | transparent | Spinner |

#### Toast Messages (use shadcn/ui toast)

| Event | Type | Message |
|-------|------|---------|
| Invalid file type | error | "Only PDF and ZIP files are supported" |
| File too large | error | "File exceeds 500MB limit: {filename}" |
| Too many files | warning | "Maximum 100 files per upload. First 100 accepted." |
| Upload success | success | "Uploaded {count} files successfully" |
| Upload error | error | "Upload failed: {error message}" |

### API Integration

#### Backend Endpoint (to be created in Story 2a-2)

```typescript
// POST /api/documents/upload
// Content-Type: multipart/form-data

interface UploadRequest {
  matter_id: string;
  file: File;
  document_type: 'case_file' | 'act' | 'annexure' | 'other';
}

interface UploadResponse {
  data: {
    document_id: string;
    filename: string;
    storage_path: string;
    status: 'pending';
  }
}
```

**NOTE:** For this story, implement frontend upload with mock/placeholder API. Story 2a-2 will implement the actual backend.

#### Progress Tracking Pattern

```typescript
// Use XMLHttpRequest for upload progress
const uploadFile = async (file: File, matterId: string): Promise<UploadResponse> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('matter_id', matterId);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const progress = Math.round((event.loaded / event.total) * 100);
        // Update store with progress
        useUploadStore.getState().updateProgress(file.name, progress);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.statusText));
      }
    };

    xhr.onerror = () => reject(new Error('Network error'));
    xhr.open('POST', '/api/documents/upload');
    xhr.send(formData);
  });
};
```

### Previous Story Intelligence

**From Story 1-7 (4-Layer Matter Isolation):**
- All document operations MUST include matter_id
- Backend validates matter access via `require_matter_role` dependency
- Documents table already created with RLS policies
- Storage bucket `documents/{matter_id}/uploads/` structure established

**From Story 1-3 (Supabase Auth):**
- Use `getSupabaseClient()` from `frontend/src/lib/supabase/client.ts`
- JWT token automatically included in requests via middleware
- Current user available via `useAuth()` hook

**Key Patterns from Epic 1:**
- Component tests co-located with components
- Use `screen.getByRole()` for testing (React Testing Library)
- Mock external services in tests (MSW not yet set up - use simple mocks)

### Git Intelligence

Recent commit patterns:
- `feat(auth): implement X (Story 1-X)` - feature commits
- `fix(auth): code review fixes for X (Story 1-X)` - review fixes

**Recommended commit:** `feat(documents): implement document upload UI (Story 2a-1)`

### Testing Guidance

#### Component Testing

```typescript
// UploadDropzone.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { UploadDropzone } from './UploadDropzone';

describe('UploadDropzone', () => {
  test('shows drag active state when dragging files over', () => {
    render(<UploadDropzone matterId="test-id" />);
    const dropzone = screen.getByRole('button', { name: /drop files/i });

    fireEvent.dragEnter(dropzone);
    expect(dropzone).toHaveClass('border-blue-500');
  });

  test('rejects non-PDF/ZIP files with error message', async () => {
    render(<UploadDropzone matterId="test-id" />);
    const file = new File(['content'], 'test.doc', { type: 'application/msword' });

    const dropzone = screen.getByRole('button');
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

    expect(await screen.findByText(/only PDF and ZIP/i)).toBeInTheDocument();
  });

  test('limits files to 100 with warning', () => {
    render(<UploadDropzone matterId="test-id" />);
    const files = Array.from({ length: 105 }, (_, i) =>
      new File(['content'], `file${i}.pdf`, { type: 'application/pdf' })
    );

    const dropzone = screen.getByRole('button');
    fireEvent.drop(dropzone, { dataTransfer: { files } });

    expect(screen.getByText(/maximum 100 files/i)).toBeInTheDocument();
  });
});
```

### Anti-Patterns to AVOID

```typescript
// WRONG: Using any type
const handleDrop = (e: any) => { ... }

// WRONG: Direct DOM manipulation
document.getElementById('dropzone').classList.add('active');

// WRONG: Not validating matter access
const upload = async (file: File) => {
  // Missing matter_id validation!
  await api.upload(file);
};

// WRONG: Console.log in production code
console.log('File uploaded:', file.name);

// WRONG: Hardcoded magic numbers
if (file.size > 524288000) { ... } // Use named constant

// CORRECT: Named constants
const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB
const MAX_FILES_PER_UPLOAD = 100;
```

### Accessibility Requirements

- Dropzone must be keyboard accessible (focusable, pressable)
- Screen reader announcements for upload states
- Progress bars must have `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Error messages linked to dropzone via `aria-describedby`

### Performance Considerations

- Virtualize file list if showing many files (future enhancement)
- Cancel uploads properly using AbortController
- Clear completed uploads from store to prevent memory bloat
- Use `React.memo` for file list items if performance issues

### Project Structure Notes

- This component will be used in the matter workspace upload flow (Epic 9, Story 9.4)
- Keep component generic enough to support both drag-drop modal and inline dropzone
- Props should include: `matterId` (required), `onUploadComplete` (callback), `maxFiles` (optional override)

### References

- [Source: _bmad-output/architecture.md#File-Storage] - Supabase Storage bucket structure
- [Source: _bmad-output/architecture.md#Frontend-Structure] - Component file organization
- [Source: _bmad-output/project-context.md#Zustand-State-Management] - Selector pattern requirement
- [Source: _bmad-output/project-context.md#TypeScript-Frontend] - Strict mode requirements
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-2.1] - Acceptance criteria

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. Implemented complete document upload UI with drag-and-drop functionality
2. Created UploadDropzone component with visual states (default, drag-over, invalid, uploading)
3. Built validation utility with 500MB file size limit and 100 files per upload limit
4. Added UploadProgress component showing file name, size, progress bar, and cancel button
5. Created Zustand uploadStore with selector pattern (no destructuring)
6. Implemented upload API integration using XMLHttpRequest for progress tracking
7. Added shadcn/ui Progress component for visual feedback
8. All 106 tests pass including 40 new upload-specific tests (18 UploadDropzone + 22 UploadProgress)
9. TypeScript strict mode compliant - no `any` types
10. Zustand store uses selectors pattern as required by project-context.md
11. API integration ready for Story 2a-2 backend implementation

### File List

**New Files:**
- frontend/src/components/features/document/UploadDropzone.tsx
- frontend/src/components/features/document/UploadDropzone.test.tsx
- frontend/src/components/features/document/UploadProgress.tsx
- frontend/src/components/features/document/UploadProgress.test.tsx
- frontend/src/components/ui/progress.tsx
- frontend/src/lib/utils/upload-validation.ts
- frontend/src/lib/api/documents.ts
- frontend/src/stores/uploadStore.ts
- frontend/src/types/document.ts

**Modified Files:**
- frontend/src/types/index.ts (added document type exports)
- frontend/src/stores/index.ts (added uploadStore export)
- frontend/vitest.setup.ts (added sonner toast mock)
- frontend/package.json (added @radix-ui/react-progress dependency)

## Change Log

- 2026-01-06: Initial implementation of document upload UI (Story 2a-1)
- 2026-01-06: Code review fixes - added UploadProgress.test.tsx (22 tests), fixed act() warnings, added AbortController cleanup on unmount, added mounted state tracking, replaced magic number with INVALID_STATE_DISPLAY_MS constant, removed redundant aria attributes from Progress component
