# Story 9.4: Implement Upload Flow Stages 1-2

Status: complete

## Story

As an **attorney**,
I want **a guided flow to upload documents and name my matter**,
So that **I can easily start a new case analysis**.

## Acceptance Criteria

1. **Given** I click "+ New Matter"
   **When** Stage 1 (File Selection) opens
   **Then** I see a drag-drop zone with icon animation
   **And** "Browse Files" button, supported formats note (PDF, ZIP), limits note (500MB/file, 100 files)

2. **Given** I drop or select files
   **When** Stage 2 (Review & Name) appears
   **Then** I see an auto-generated matter name (editable)
   **And** file list with remove option for each file

3. **Given** citations are detected
   **When** Act Discovery Report modal appears
   **Then** I see which Acts are referenced and which are available/missing
   **And** options: upload missing Acts, skip specific Acts, continue with partial verification

4. **Given** I complete Stage 2
   **When** I click "Start Processing"
   **Then** the upload begins and Stage 3 appears

## Tasks / Subtasks

- [x] Task 1: Create UploadWizard container component (AC: #1, #2, #4)
  - [x] 1.1: Create `frontend/src/components/features/upload/UploadWizard.tsx`
  - [x] 1.2: Implement wizard state machine: STAGE_1_FILE_SELECTION → STAGE_2_REVIEW → STAGE_2_5_ACT_DISCOVERY → (hand off to 9-5)
  - [x] 1.3: Track uploaded files, matter name, detected citations
  - [x] 1.4: Use useUploadStore for file queue management (already exists)
  - [x] 1.5: Add back navigation to dashboard

- [x] Task 2: Create FileDropZone component - Stage 1 (AC: #1)
  - [x] 2.1: Create `frontend/src/components/features/upload/FileDropZone.tsx`
  - [x] 2.2: Implement drag-drop using native HTML5 API
  - [x] 2.3: Add animated icon on drag-over (folder with pulse animation)
  - [x] 2.4: Display "Browse Files" button with file input
  - [x] 2.5: Show supported formats: "Supported: PDF, ZIP (containing PDFs)"
  - [x] 2.6: Show limits: "Maximum: 500MB per file • 100 files per matter"
  - [x] 2.7: Use existing validateFiles from `lib/utils/upload-validation.ts`
  - [x] 2.8: Display validation errors inline (use existing ValidationError type)

- [x] Task 3: Create FileReviewList component - Stage 2 (AC: #2)
  - [x] 3.1: Create `frontend/src/components/features/upload/FileReviewList.tsx`
  - [x] 3.2: Display file list with name, size (formatFileSize utility exists), remove button
  - [x] 3.3: Show validation warnings (e.g., >100 files)
  - [x] 3.4: Add "Add More Files" option
  - [x] 3.5: Use UploadFile type from types/document.ts

- [x] Task 4: Create MatterNameInput component - Stage 2 (AC: #2)
  - [x] 4.1: Create `frontend/src/components/features/upload/MatterNameInput.tsx`
  - [x] 4.2: Auto-generate matter name from first uploaded file name
  - [x] 4.3: Make name editable with validation (required, max 100 chars)
  - [x] 4.4: Use shadcn/ui Input with label

- [x] Task 5: Create ActDiscoveryModal component - Stage 2.5 (AC: #3)
  - [x] 5.1: Create `frontend/src/components/features/upload/ActDiscoveryModal.tsx`
  - [x] 5.2: Display detected Acts list with status (found/missing)
  - [x] 5.3: Show citation counts per Act
  - [x] 5.4: Add "Upload Missing Acts" button with file picker
  - [x] 5.5: Add "Skip for Now" button (continues with partial verification)
  - [x] 5.6: Add "Continue with Upload" button
  - [x] 5.7: Use shadcn/ui Dialog component
  - [x] 5.8: Note: For MVP, this modal shows mock data (backend citation extraction not yet available)

- [x] Task 6: Create uploadWizardStore (AC: #1, #2, #3, #4)
  - [x] 6.1: Create `frontend/src/stores/uploadWizardStore.ts` using Zustand
  - [x] 6.2: State: currentStage, files, matterName, detectedActs, isLoading, error
  - [x] 6.3: Actions: setStage, addFiles, removeFile, setMatterName, setDetectedActs, startUpload
  - [x] 6.4: Use MANDATORY selector pattern from project-context.md

- [x] Task 7: Create upload page route (AC: #1, #4)
  - [x] 7.1: Create `frontend/src/app/(dashboard)/upload/page.tsx`
  - [x] 7.2: Import and render UploadWizard component
  - [x] 7.3: Add loading.tsx and error.tsx for the route
  - [x] 7.4: Use Next.js App Router patterns (server component by default, 'use client' where needed)

- [x] Task 8: Connect "+ New Matter" button to upload flow (AC: #1)
  - [x] 8.1: Update `frontend/src/components/features/dashboard/MatterCardsGrid.tsx`
  - [x] 8.2: Wire "+ New Matter" card to navigate to /upload route using Next.js router

- [x] Task 9: Define upload wizard types (AC: #1, #2, #3)
  - [x] 9.1: Add to `frontend/src/types/upload.ts`:
    - `UploadWizardStage` enum: 'FILE_SELECTION' | 'REVIEW' | 'ACT_DISCOVERY' | 'UPLOADING'
    - `DetectedAct` interface with actName, citationCount, status ('found' | 'missing'), sourceFile?
    - `UploadWizardState` interface
  - [x] 9.2: Note: Reuse existing UploadFile, ValidationResult from types/document.ts

- [x] Task 10: Write tests (All ACs)
  - [x] 10.1: Create `UploadWizard.test.tsx` - wizard navigation, stage transitions
  - [x] 10.2: Create `FileDropZone.test.tsx` - drag-drop, file validation, browse button
  - [x] 10.3: Create `FileReviewList.test.tsx` - file display, remove functionality
  - [x] 10.4: Create `MatterNameInput.test.tsx` - auto-generation, editing
  - [x] 10.5: Create `ActDiscoveryModal.test.tsx` - modal display, actions
  - [x] 10.6: Create `uploadWizardStore.test.ts` - store actions and state

- [x] Task 11: Update component exports (All ACs)
  - [x] 11.1: Create `frontend/src/components/features/upload/index.ts` with exports

## Dev Notes

### Critical Architecture Patterns

**UI Component Requirements:**
- Use shadcn/ui components: `Dialog`, `Button`, `Input`, `Card`, `Label`
- Follow component structure: `frontend/src/components/features/upload/`
- Co-locate tests: `ComponentName.test.tsx` in same directory
- Use lucide-react for icons: `Upload`, `Folder`, `File`, `X`, `Plus`, `AlertCircle`, `CheckCircle2`

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const currentStage = useUploadWizardStore((state) => state.currentStage);
const files = useUploadWizardStore((state) => state.files);
const setStage = useUploadWizardStore((state) => state.setStage);

// WRONG - Full store subscription (causes re-renders)
const { currentStage, files, setStage } = useUploadWizardStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions:**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `UploadWizard`, `FileDropZone` |
| Component files | PascalCase.tsx | `UploadWizard.tsx` |
| Variables | camelCase | `currentStage`, `matterName` |
| Functions | camelCase | `handleDrop`, `validateFiles` |
| Constants | SCREAMING_SNAKE | `MAX_FILE_SIZE`, `ALLOWED_MIME_TYPES` |

### UX Design Reference

From UX-Decisions-Log.md wireframes:

**Stage 1: File Selection Wireframe:**
```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    CREATE NEW MATTER                             │
│                                                                  │
│       ┌─────────────────────────────────────────────┐           │
│       │                                             │           │
│       │              ┌───────────────┐              │           │
│       │              │   📁 → 📄     │              │           │
│       │              └───────────────┘              │           │
│       │                                             │           │
│       │        Drag & drop your case files here     │           │
│       │                    or                       │           │
│       │             [Browse Files]                  │           │
│       │                                             │           │
│       │   Supported: PDF, ZIP (containing PDFs)     │           │
│       │   Maximum: 500MB per file • 100 files       │           │
│       │                                             │           │
│       └─────────────────────────────────────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Stage 2: Review & Name (after files selected):**
```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    CREATE NEW MATTER                             │
│                                                                  │
│  Matter Name:                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Shah_v_Mehta_Securities_Matter                              ││
│  └─────────────────────────────────────────────────────────────┘│
│  (Auto-generated from first file - click to edit)               │
│                                                                  │
│  Files to Upload (12 files • 45.2 MB):                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 📄 Petition.pdf                234 pages     12.5 MB   [×] ││
│  │ 📄 Reply_Affidavit.pdf         156 pages      8.3 MB   [×] ││
│  │ 📄 Annexure_K.pdf               45 pages      2.1 MB   [×] ││
│  │ ... 9 more files                                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  [+ Add More Files]                                              │
│                                                                  │
│                   [Cancel]     [Start Processing →]              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Stage 2.5: Act Discovery Modal (per ADR-005):**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ACT REFERENCES DETECTED                       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Your case files reference 6 Acts. We found 2 in your files.││
│  │  For accurate citation verification, upload missing Acts.   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ✅ DETECTED IN YOUR FILES (2)                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  ✓ Securities Act, 1992       Found in: Annexure_P3.pdf    ││
│  │  ✓ SARFAESI Act, 2002          Found in: Annexure_K.pdf     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ⚠️ MISSING ACTS (4)                      [Upload Missing Acts] │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  ○ BNS Act, 2023                Cited 12 times              ││
│  │  ○ Negotiable Instruments Act   Cited 8 times               ││
│  │  ○ DRT Act, 1993                Cited 4 times               ││
│  │  ○ Companies Act, 2013          Cited 2 times               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ℹ️ Citations to missing Acts show as "Unverified"               │
│     You can upload Acts later from the Documents Tab.            │
│                                                                  │
│                    [Skip for Now]    [Continue with Upload]      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Drag-over Visual Feedback (from UX-Decisions-Log.md):**
```
Default:                     Drag Over:
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐       ╔═══════════════════════╗
│                    │       ║  ████████████████████ ║
│   📁 Drop files    │   →   ║  ██ Drop to upload ██ ║
│      here          │       ║  ████████████████████ ║
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘       ╚═══════════════════════╝
                             ↑ Dashed → Solid border
                             ↑ Background highlight (blue-50)
                             ↑ Pulsing animation
```

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── app/(dashboard)/upload/      # NEW route
│   ├── page.tsx                 # NEW
│   ├── loading.tsx              # NEW
│   └── error.tsx                # NEW
├── components/features/upload/  # NEW directory
│   ├── UploadWizard.tsx         # NEW
│   ├── UploadWizard.test.tsx    # NEW
│   ├── FileDropZone.tsx         # NEW
│   ├── FileDropZone.test.tsx    # NEW
│   ├── FileReviewList.tsx       # NEW
│   ├── FileReviewList.test.tsx  # NEW
│   ├── MatterNameInput.tsx      # NEW
│   ├── MatterNameInput.test.tsx # NEW
│   ├── ActDiscoveryModal.tsx    # NEW
│   ├── ActDiscoveryModal.test.tsx # NEW
│   └── index.ts                 # NEW
├── stores/
│   ├── uploadStore.ts           # EXISTS - reuse for file queue
│   ├── uploadWizardStore.ts     # NEW
│   └── uploadWizardStore.test.ts # NEW
├── types/
│   ├── document.ts              # EXISTS - has UploadFile, ValidationResult
│   └── upload.ts                # NEW - wizard-specific types
└── lib/utils/
    └── upload-validation.ts     # EXISTS - validateFiles, formatFileSize
```

**Existing Components/Utilities to Reuse (DO NOT RECREATE):**
- `frontend/src/stores/uploadStore.ts` - File queue management
- `frontend/src/lib/utils/upload-validation.ts` - validateFiles, getValidFiles, formatFileSize, MAX_FILE_SIZE, MAX_FILES_PER_UPLOAD
- `frontend/src/types/document.ts` - UploadFile, UploadStatus, ValidationResult, ValidationError, ValidationWarning
- `frontend/src/components/ui/dialog.tsx` - shadcn Dialog for modal
- `frontend/src/components/ui/button.tsx`, `input.tsx`, `card.tsx`, `label.tsx`

### Backend API Integration

**No backend API exists yet for:**
- Matter creation
- File upload to Supabase Storage
- Citation extraction/Act discovery

**For MVP, implement with mock data:**
- Matter name auto-generation from filename (client-side)
- File validation (client-side - utilities exist)
- Act discovery modal shows mock detected Acts
- "Start Processing" button navigates to Story 9-5 (upload progress stage)

**Frontend Types for Future Backend:**
```typescript
// Matter creation request (future)
interface CreateMatterRequest {
  name: string;
  files: UploadFile[];
}

// Detected Act from citation extraction (future - mock for MVP)
interface DetectedAct {
  actName: string;           // e.g., "SARFAESI Act, 2002"
  citationCount: number;     // How many times cited
  status: 'found' | 'missing';
  sourceFile?: string;       // If found, which file contains it
}
```

**Future API Endpoints (not implemented yet):**
- `POST /api/matters` - Create new matter
- `POST /api/matters/{id}/documents` - Upload document to matter
- `GET /api/matters/{id}/citations/acts` - Get detected Acts

### Previous Story Intelligence (9-1, 9-2, 9-3)

**From Story 9-1 implementation:**
- DashboardHeader uses shadcn components and lucide-react icons
- NotificationsDropdown uses mock data pattern
- Tests co-located with components (48 tests)
- Code review found: unused imports, console.log issues, missing Next.js Link

**From Story 9-2 implementation:**
- MatterCardsGrid has "+ New Matter" card that needs to link to upload
- matterStore uses Zustand with selector pattern
- Mock data extracted to separate file with TODO for backend
- useShallow from zustand/react/shallow for memoization

**From Story 9-3 implementation:**
- 30-second polling pattern for real-time updates
- Error boundary wrapping for isolated failures
- Semantic HTML with aria-labels for accessibility
- All 610 tests pass

**Key Learnings to Apply:**
1. Use mock data initially - design interfaces for future backend
2. Follow selector pattern strictly for Zustand stores
3. Remove unused imports before committing
4. Use Next.js `<Link>` and `useRouter` for navigation
5. No console.log in production code
6. Add error boundaries where failures should be isolated
7. Use semantic HTML and aria-labels for accessibility
8. Co-locate test files with components

### Accessibility Requirements

From UX-Decisions-Log.md:
- Drop zone should be keyboard accessible (Tab to focus, Enter/Space to open file picker)
- File list should use semantic HTML (`<ul>`, `<li>`)
- Remove buttons should have `aria-label="Remove {filename}"`
- Modal should trap focus and be dismissible with Escape key
- Progress indicators should have `role="progressbar"` and aria-valuenow
- Color should not be the only indicator of state

### Performance Considerations

- Validate files client-side before adding to queue
- Display file list with virtualization if >50 files
- Use skeleton loading for wizard transitions
- Debounce matter name input validation (300ms)
- Cancel pending operations on unmount

### Error Handling

From UX-Decisions-Log.md error patterns:

**File Type Error:**
```
⚠️ Can't upload "document.xlsx"
LDIP supports PDF files only.
Tip: Convert your Excel file to PDF first.
```

**File Size Error:**
```
⚠️ File too large
"LargeDocument.pdf" (650 MB) exceeds the 500 MB limit.
Try compressing or splitting the file.
```

**Too Many Files:**
```
ℹ️ Maximum 100 files per upload
First 100 files accepted. 27 files were not added.
```

### Security Considerations

- Validate MIME types AND file extensions (defense in depth)
- Sanitize filenames before display (XSS prevention)
- Don't expose internal file paths in error messages
- Use signed URLs for any file operations (future backend)

### References

- [UX Wireframe: Upload & Processing](../_bmad-output/project-planning-artifacts/UX-Decisions-Log.md#4-upload--processing)
- [Architecture: ADR-005 Citation Engine](../_bmad-output/architecture.md#citation-engine-architecture-adr-005)
- [Previous Story 9-1](../_bmad-output/implementation-artifacts/9-1-dashboard-header.md)
- [Previous Story 9-2](../_bmad-output/implementation-artifacts/9-2-matter-cards-grid.md)
- [Previous Story 9-3](../_bmad-output/implementation-artifacts/9-3-activity-feed-quick-stats.md)
- [Project Context](../_bmad-output/project-context.md)
- [Architecture](../_bmad-output/architecture.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

1. Implemented all 11 tasks for Upload Flow Stages 1-2
2. Created types in `frontend/src/types/upload.ts` for wizard state and acts
3. Created Zustand store `uploadWizardStore.ts` with mandatory selector pattern
4. Created 5 new components: UploadWizard, FileDropZone, FileReviewList, MatterNameInput, ActDiscoveryModal
5. Created upload page route with loading and error states
6. Updated MatterCardsGrid to link to `/upload` instead of `/matter/new`
7. All 748 tests pass (138 new tests added)
8. Build passes successfully
9. Act Discovery modal uses mock data for MVP (backend not yet available)
10. Created processing page placeholder for Story 9-5

### File List

**New Files Created:**
- `frontend/src/types/upload.ts` - Upload wizard types
- `frontend/src/stores/uploadWizardStore.ts` - Zustand store for wizard state
- `frontend/src/stores/uploadWizardStore.test.ts` - Store tests (38 tests)
- `frontend/src/components/features/upload/UploadWizard.tsx` - Main wizard container
- `frontend/src/components/features/upload/UploadWizard.test.tsx` - Wizard tests (25 tests)
- `frontend/src/components/features/upload/FileDropZone.tsx` - Stage 1 drop zone
- `frontend/src/components/features/upload/FileDropZone.test.tsx` - Drop zone tests (21 tests)
- `frontend/src/components/features/upload/FileReviewList.tsx` - Stage 2 file list
- `frontend/src/components/features/upload/FileReviewList.test.tsx` - File list tests (23 tests)
- `frontend/src/components/features/upload/MatterNameInput.tsx` - Matter name input
- `frontend/src/components/features/upload/MatterNameInput.test.tsx` - Input tests (17 tests)
- `frontend/src/components/features/upload/ActDiscoveryModal.tsx` - Act discovery modal
- `frontend/src/components/features/upload/ActDiscoveryModal.test.tsx` - Modal tests (24 tests)
- `frontend/src/components/features/upload/index.ts` - Component exports
- `frontend/src/app/(dashboard)/upload/page.tsx` - Upload route
- `frontend/src/app/(dashboard)/upload/loading.tsx` - Loading state
- `frontend/src/app/(dashboard)/upload/error.tsx` - Error boundary
- `frontend/src/app/(dashboard)/upload/processing/page.tsx` - Processing placeholder

**Modified Files:**
- `frontend/src/components/features/dashboard/MatterCardsGrid.tsx` - Updated link to `/upload`
- `frontend/src/components/features/dashboard/MatterCardsGrid.test.tsx` - Updated test for new link
