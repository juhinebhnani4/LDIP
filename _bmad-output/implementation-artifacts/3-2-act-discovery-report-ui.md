# Story 3.2: Implement Act Discovery Report UI

Status: done

## Story

As an **attorney**,
I want **to see which Acts are referenced and which are available for verification**,
So that **I can upload missing Acts to enable full verification**.

## Acceptance Criteria

1. **Given** citation extraction is complete **When** I view the Act Discovery Report **Then** I see a list of all Acts referenced in my documents **And** each Act shows: name, citation count, availability status (Available/Missing/Skipped)

2. **Given** an Act is marked as "Missing" **When** I click "Upload Act" **Then** I can upload the Act PDF **And** the Act is stored with `is_reference_material=true` **And** its status changes to "Available"

3. **Given** I choose not to upload an Act **When** I click "Skip this Act" **Then** the Act remains marked as "Skipped" **And** citations to it are marked "Unverified - Act not provided"

4. **Given** I click "Continue with Partial Verification" **When** processing continues **Then** citations to available Acts are verified **And** citations to missing Acts show graceful degradation status

## Tasks / Subtasks

- [x] Task 1: Create ActDiscoveryModal Component (AC: #1, #2, #3, #4)
  - [x] Create `frontend/src/components/features/citation/ActDiscoveryModal.tsx`
    - Use existing Dialog components from `components/ui/dialog.tsx`
    - Props: `matterId: string`, `open: boolean`, `onOpenChange: (open: boolean) => void`, `onContinue: () => void`
    - Fetch Act Discovery Report via `getActDiscoveryReport(matterId)` from `lib/api/citations.ts`
    - Display detected Acts (status: available) with green checkmarks
    - Display missing Acts (status: missing) with citation counts
    - Display skipped Acts (status: skipped) with muted styling
    - Include "Upload Missing Acts" button that opens file picker
    - Include "Skip this Act" dropdown action for each missing Act
    - Include "Skip for Now" and "Continue" footer buttons
    - Handle loading/error states with Skeleton/Alert components

- [x] Task 2: Create ActDiscoveryItem Component (AC: #1)
  - [x] Create `frontend/src/components/features/citation/ActDiscoveryItem.tsx`
    - Props: `act: ActDiscoverySummary`, `onUpload: (actName: string) => void`, `onSkip: (actName: string) => void`, `isUploading?: boolean`
    - Display act name, citation count, and status badge
    - Show "Upload" button for missing Acts
    - Show "Skip" button for missing Acts
    - Show "Uploaded" badge for available Acts
    - Show "Skipped" badge for skipped Acts
    - Use Badge component from `components/ui/badge.tsx`

- [x] Task 3: Create ActUploadDropzone Component (AC: #2)
  - [x] Create `frontend/src/components/features/citation/ActUploadDropzone.tsx`
    - Extend existing UploadDropzone pattern from `components/features/document/UploadDropzone.tsx`
    - Props: `matterId: string`, `actName: string`, `onUploadComplete: (documentId: string) => void`
    - Set `documentType` to `'act'` (is_reference_material=true)
    - Show only single file selection (Acts are single documents)
    - Auto-call `markActUploaded()` after successful upload
    - Notify parent component of successful upload

- [x] Task 4: Integrate ActDiscoveryModal into Upload Flow (AC: #1, #4)
  - [x] Update upload flow to show Act Discovery Modal after processing starts
    - Created ActDiscoveryTrigger component with Realtime subscription
    - Auto-opens modal when missing Acts detected
    - Allows user to continue without uploading all Acts
  - [x] Integrated into MatterWorkspaceWrapper as Stage 2.5

- [x] Task 5: Create useActDiscovery Hook (AC: #1, #2, #3)
  - [x] Create `frontend/src/hooks/useActDiscovery.ts`
    - Encapsulate Act Discovery Report fetching logic
    - Provide `actReport`, `isLoading`, `error`, `refetch` returns
    - Provide `markUploaded(actName, documentId)` mutation
    - Provide `markSkipped(actName)` mutation
    - Uses SWR-like pattern with useState/useEffect

- [x] Task 6: Add Real-Time Act Discovery Updates (AC: #2, #3)
  - [x] Subscribe to `citations:{matter_id}` channel for live updates via ActDiscoveryTrigger
    - Update modal when new Acts are discovered (citation_extraction_complete event)
    - Update status when user uploads an Act (act_discovery_update event)
  - [x] Use existing Supabase Realtime subscription pattern

- [x] Task 7: Write Component Tests (AC: #1, #2, #3, #4)
  - [x] Create `frontend/src/components/features/citation/ActDiscoveryModal.test.tsx`
    - Test modal renders with act list
    - Test loading state shows skeleton
    - Test error state shows alert
    - Test upload action triggers markActUploaded
    - Test skip action triggers markActSkipped
    - Test continue button closes modal and calls onContinue
  - [x] Create `frontend/src/components/features/citation/ActDiscoveryItem.test.tsx`
    - Test displays act name and citation count
    - Test shows correct status badges
    - Test upload button calls onUpload
    - Test skip button calls onSkip
  - [x] Create `frontend/src/components/features/citation/ActUploadDropzone.test.tsx`
    - Test renders dropzone with act name
    - Test validates file type (PDF only)
    - Test validates file size (100MB limit)
    - Test uploads file with documentType='act'
    - Test shows success/error toasts
    - Test drag-and-drop functionality
  - [x] Create `frontend/src/hooks/useActDiscovery.test.ts`
    - Test fetches discovery report
    - Test handles loading state
    - Test handles error state
    - Test markUploaded mutation
    - Test markSkipped mutation

## Dev Notes

### CRITICAL: Architecture Requirements (ADR-005)

**From [architecture.md#ADR-005](../_bmad-output/architecture.md#ADR-005):**

The Act Discovery UI follows the "Act Discovery + User Confirmation" pattern:

```
CITATION EXTRACTION (Automatic) ← Story 3-1 DONE
  │
  ▼
ACT DISCOVERY REPORT (System → User) ← THIS STORY
  │ "Your case references 6 Acts. 2 available, 4 missing."
  │ User options:
  │   • Upload missing Acts
  │   • Skip specific Acts
  │   • Continue with partial verification
```

**Key Principle:** User controls which Act versions are used (amendments matter). No system-maintained Act library.

### CRITICAL: Use Existing API Client and Types (DO NOT RECREATE)

**Story 3-1 already created these files - REUSE THEM:**

```typescript
// Types - frontend/src/types/citation.ts
import type {
  ActDiscoverySummary,
  ActDiscoveryResponse,
  ActResolutionStatus,
  UserAction,
  MarkActUploadedRequest,
  MarkActSkippedRequest,
} from '@/types/citation';

// API Client - frontend/src/lib/api/citations.ts
import {
  getActDiscoveryReport,
  getMissingActs,
  markActUploaded,
  markActSkipped,
} from '@/lib/api/citations';
```

**Backend endpoints already exist:**
- `GET /api/matters/{matter_id}/citations/acts/discovery` - Returns ActDiscoveryResponse
- `POST /api/matters/{matter_id}/citations/acts/mark-uploaded` - Takes MarkActUploadedRequest
- `POST /api/matters/{matter_id}/citations/acts/mark-skipped` - Takes MarkActSkippedRequest

### UX Wireframe (MANDATORY to Follow)

**From [UX-Decisions-Log.md#4.3.1](../_bmad-output/project-planning-artifacts/UX-Decisions-Log.md):**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                          ACT REFERENCES DETECTED                                │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  Your case files reference 6 Acts. We found 2 in your uploaded files.    │ │
│  │                                                                           │ │
│  │  For accurate citation verification, please upload the missing Acts.     │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ✅ DETECTED IN YOUR FILES (2)                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ✓ Securities Act, 1992         Found in: Annexure_P3.pdf               │ │
│  │  ✓ SARFAESI Act, 2002            Found in: Annexure_K.pdf                │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ⚠️ MISSING ACTS (4)                              [Upload Missing Acts]       │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ○ BNS Act, 2023                  Cited 12 times in your files          │ │
│  │  ○ Negotiable Instruments Act     Cited 8 times                          │ │
│  │  ○ DRT Act, 1993                  Cited 4 times                          │ │
│  │  ○ Companies Act, 2013            Cited 2 times                          │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ℹ️ Citations to missing Acts will show as "Unverified - Act not provided"    │
│     You can upload Acts later from the Documents Tab.                          │
│                                                                                 │
│                         [Skip for Now]     [Continue with Upload]              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Act Upload Behavior Table:**
| Action | Result |
|--------|--------|
| Upload Act now | File marked as `is_reference_material=true`, stored in matter's acts folder |
| Skip for Now | Continue processing; citations show "Unverified - Act not provided" |
| Upload later (Documents Tab) | User can "Set as Act" action on any document |

### Previous Story Intelligence (Story 3-1)

**Key Patterns from [3-1-act-citation-extraction.md](3-1-act-citation-extraction.md):**

1. **API Response Format:**
   ```typescript
   // Always wrap in { data } or { error }
   interface ActDiscoveryResponse {
     data: ActDiscoverySummary[];
   }
   ```

2. **Act Resolution Status Values:**
   - `available` - Act document uploaded and linked
   - `missing` - Act referenced but no document uploaded
   - `skipped` - User chose to skip uploading this Act

3. **User Action Values:**
   - `uploaded` - User uploaded the Act
   - `skipped` - User explicitly skipped
   - `pending` - No action yet taken

4. **Real-Time Channel:** `citations:{matter_id}` broadcasts citation extraction progress

5. **Async/Sync Pattern:** Backend uses `asyncio.to_thread()` for Supabase calls

### Project Structure Requirements

**New Files (FOLLOW EXISTING PATTERNS):**

```
frontend/src/
├── components/
│   └── features/
│       └── citation/                     (NEW DIRECTORY)
│           ├── ActDiscoveryModal.tsx     (NEW)
│           ├── ActDiscoveryModal.test.tsx (NEW)
│           ├── ActDiscoveryItem.tsx      (NEW)
│           ├── ActDiscoveryItem.test.tsx (NEW)
│           ├── ActUploadDropzone.tsx     (NEW)
│           └── ActUploadDropzone.test.tsx (NEW)
├── hooks/
│   ├── useActDiscovery.ts                (NEW)
│   └── useActDiscovery.test.ts           (NEW)
```

**DO NOT create:**
- New types (use existing `@/types/citation`)
- New API functions (use existing `@/lib/api/citations`)
- New backend endpoints (already exist)

### Component Patterns (FOLLOW EXACTLY)

**From existing codebase patterns:**

1. **Zustand Selectors (NOT destructuring):**
   ```typescript
   // CORRECT
   const actReport = useActDiscoveryStore((state) => state.actReport);
   const isLoading = useActDiscoveryStore((state) => state.isLoading);

   // WRONG
   const { actReport, isLoading } = useActDiscoveryStore();
   ```

2. **Dialog Pattern:**
   ```tsx
   <Dialog open={open} onOpenChange={onOpenChange}>
     <DialogContent className="sm:max-w-[600px]">
       <DialogHeader>
         <DialogTitle>Act References Detected</DialogTitle>
         <DialogDescription>...</DialogDescription>
       </DialogHeader>
       {/* Content */}
       <DialogFooter>
         <Button variant="outline" onClick={handleSkip}>Skip for Now</Button>
         <Button onClick={handleContinue}>Continue</Button>
       </DialogFooter>
     </DialogContent>
   </Dialog>
   ```

3. **Loading States:**
   ```tsx
   if (isLoading) return <Skeleton className="h-40 w-full" />;
   if (error) return <Alert variant="destructive">{error.message}</Alert>;
   ```

4. **API Calls in Effects:**
   ```typescript
   useEffect(() => {
     let isMounted = true;
     async function fetchData() {
       try {
         const result = await getActDiscoveryReport(matterId);
         if (isMounted) setActReport(result.data);
       } catch (err) {
         if (isMounted) setError(err);
       }
     }
     fetchData();
     return () => { isMounted = false; };
   }, [matterId]);
   ```

### Badge Styling for Status

```tsx
// Available (green)
<Badge variant="default" className="bg-green-500/10 text-green-700 border-green-200">
  <CheckCircle2 className="mr-1 h-3 w-3" />
  Available
</Badge>

// Missing (amber warning)
<Badge variant="outline" className="bg-amber-500/10 text-amber-700 border-amber-200">
  <AlertCircle className="mr-1 h-3 w-3" />
  Missing ({citationCount} citations)
</Badge>

// Skipped (muted)
<Badge variant="secondary" className="text-muted-foreground">
  Skipped
</Badge>
```

### Testing Patterns

**From existing test files (e.g., `UploadDropzone.test.tsx`):**

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ActDiscoveryModal } from './ActDiscoveryModal';

// Mock API
vi.mock('@/lib/api/citations', () => ({
  getActDiscoveryReport: vi.fn(),
  markActUploaded: vi.fn(),
  markActSkipped: vi.fn(),
}));

describe('ActDiscoveryModal', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders act list when loaded', async () => {
    const mockReport = {
      data: [
        { actName: 'NI Act', citationCount: 5, resolutionStatus: 'missing', userAction: 'pending' },
      ],
    };
    vi.mocked(getActDiscoveryReport).mockResolvedValue(mockReport);

    render(<ActDiscoveryModal matterId={mockMatterId} open={true} onOpenChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('NI Act')).toBeInTheDocument();
    });
  });
});
```

### Error Handling

```typescript
// API errors from backend
interface CitationErrorResponse {
  error: {
    code: string;  // e.g., 'ACT_NOT_FOUND', 'INTERNAL_ERROR'
    message: string;
    details: Record<string, unknown>;
  };
}

// Handle in component
try {
  await markActSkipped(matterId, { actName });
  toast.success(`Skipped ${actName}`);
} catch (err) {
  const error = err as CitationErrorResponse;
  toast.error(error.error?.message ?? 'Failed to skip Act');
}
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - tables already exist from Story 3-1

#### Environment Variables
- [ ] None - no new env vars needed

#### Dashboard Configuration
- [ ] None - no dashboard changes

#### Manual Tests
- [ ] Upload case documents with Act citations
- [ ] Verify Act Discovery Modal opens after citation extraction
- [ ] Verify available Acts show with green checkmarks
- [ ] Verify missing Acts show with citation counts
- [ ] Test uploading an Act updates its status to "Available"
- [ ] Test skipping an Act updates its status to "Skipped"
- [ ] Test "Skip for Now" closes modal and continues
- [ ] Test "Continue" with partial Acts shows graceful degradation

### Dependencies

```json
// No new dependencies - uses existing:
// - @radix-ui/react-dialog (via shadcn/ui)
// - lucide-react (icons)
// - sonner (toasts)
```

### Accessibility Requirements

- Modal traps focus when open
- Escape key closes modal
- Screen readers announce "Act References Detected" title
- Skip/Upload buttons have descriptive aria-labels
- Status badges have aria-label for screen readers

### Performance Considerations

- Lazy load modal content (don't fetch until opened)
- Cache discovery report (revalidate on upload/skip actions)
- Show skeleton placeholders during load (not spinner)
- Optimistic UI updates for skip/upload actions

### References

- [Source: architecture.md#ADR-005] - Act Discovery pattern
- [Source: UX-Decisions-Log.md#4.3.1] - Act Discovery Modal wireframe
- [Source: 3-1-act-citation-extraction.md] - Previous story patterns
- [Source: frontend/src/types/citation.ts] - Citation TypeScript types
- [Source: frontend/src/lib/api/citations.ts] - Citation API client
- [Source: backend/app/api/routes/citations.py] - Citation API endpoints
- [Source: components/ui/dialog.tsx] - Dialog component pattern
- [Source: components/features/document/UploadDropzone.tsx] - Upload pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- None

### Completion Notes List

- All 7 tasks completed successfully
- 60 tests passing (13 modal tests, 17 item tests, 18 dropzone tests, 12 hook tests)
- TypeScript compilation passes with no errors
- Integrated ActDiscoveryTrigger into MatterWorkspaceWrapper for automatic modal display
- Used existing API client and types from Story 3-1 (no new types/endpoints created)
- Followed existing patterns for Zustand selectors, Dialog components, and test structure
- Code review fixes applied: removed unused state, fixed misleading comments, extracted constants

### File List

#### New Files Created
- `frontend/src/components/features/citation/ActDiscoveryModal.tsx` - Main modal component
- `frontend/src/components/features/citation/ActDiscoveryModal.test.tsx` - Modal tests (13 tests)
- `frontend/src/components/features/citation/ActDiscoveryItem.tsx` - Individual act item component
- `frontend/src/components/features/citation/ActDiscoveryItem.test.tsx` - Item tests (17 tests)
- `frontend/src/components/features/citation/ActUploadDropzone.tsx` - Specialized act upload dropzone
- `frontend/src/components/features/citation/ActUploadDropzone.test.tsx` - Dropzone tests (18 tests)
- `frontend/src/components/features/citation/ActDiscoveryTrigger.tsx` - Real-time trigger component
- `frontend/src/components/features/citation/index.ts` - Feature barrel export
- `frontend/src/hooks/useActDiscovery.ts` - Act discovery data fetching hook
- `frontend/src/hooks/useActDiscovery.test.ts` - Hook tests (12 tests)

#### Modified Files
- `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx` - Added ActDiscoveryTrigger integration
- `frontend/src/lib/utils/upload-validation.ts` - Added MAX_ACT_FILE_SIZE constant
