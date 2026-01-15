# Story 9.5: Implement Upload Flow Stages 3-4

Status: review

## Story

As an **attorney**,
I want **to see upload progress and live discoveries**,
So that **I know processing is working and what's being found**.

## Acceptance Criteria

1. **Given** upload begins (Stage 3)
   **When** files are uploading
   **Then** I see file-by-file progress bars with checkmarks on completion
   **And** overall progress percentage

2. **Given** processing begins (Stage 4)
   **When** analysis runs
   **Then** I see overall progress bar with stage indicator ("Stage 3 of 5: Extracting entities")
   **And** split view showing: document processing progress, live discoveries panel

3. **Given** live discoveries are found
   **When** the panel updates
   **Then** I see: entities found with roles, dates extracted (earliest/latest), citations detected by Act, mini timeline preview, early insights with warnings

4. **Given** I want to continue working
   **When** I click "Continue in Background"
   **Then** I return to the dashboard
   **And** the matter card shows processing progress

## Tasks / Subtasks

- [ ] Task 1: Extend upload types for processing stages (AC: #1, #2, #3)
  - [ ] 1.1: Add to `frontend/src/types/upload.ts`:
    - `ProcessingStage` type: 'UPLOADING' | 'OCR' | 'ENTITY_EXTRACTION' | 'ANALYSIS' | 'INDEXING'
    - `LiveDiscovery` interface with type, count, details, timestamp
    - `UploadProgress` interface for file-by-file tracking
    - `ProcessingProgress` interface for overall stage tracking
  - [ ] 1.2: Add `DiscoveredEntity`, `DiscoveredDate`, `DiscoveredCitation` interfaces
  - [ ] 1.3: Add `EarlyInsight` interface with message, type ('info' | 'warning'), icon

- [ ] Task 2: Extend uploadWizardStore for Stage 3-4 (AC: #1, #2, #3, #4)
  - [ ] 2.1: Add state to `frontend/src/stores/uploadWizardStore.ts`:
    - `uploadProgress: Map<string, UploadProgress>` (file upload status)
    - `processingStage: ProcessingStage | null`
    - `overallProgressPct: number`
    - `liveDiscoveries: LiveDiscovery[]`
    - `matterId: string | null` (set after matter creation)
  - [ ] 2.2: Add actions: `setUploadProgress`, `setProcessingStage`, `addLiveDiscovery`, `setMatterId`, `setOverallProgress`
  - [ ] 2.3: Add selectors: `selectUploadComplete`, `selectDiscoveriesByType`, `selectCurrentStageName`
  - [ ] 2.4: Follow MANDATORY selector pattern from project-context.md

- [ ] Task 3: Create UploadProgressView component - Stage 3 (AC: #1)
  - [ ] 3.1: Create `frontend/src/components/features/upload/UploadProgressView.tsx`
  - [ ] 3.2: Display file-by-file list with:
    - Filename and size
    - Individual progress bar per file (0-100%)
    - Checkmark icon when complete, loader when uploading
    - Error state with red X if file upload fails
  - [ ] 3.3: Show overall upload progress bar at top
  - [ ] 3.4: Display "X of Y files uploaded" counter
  - [ ] 3.5: Use existing UploadFile type from types/document.ts

- [ ] Task 4: Create ProcessingProgressView component - Stage 4 (AC: #2)
  - [ ] 4.1: Create `frontend/src/components/features/upload/ProcessingProgressView.tsx`
  - [ ] 4.2: Display overall progress bar with percentage
  - [ ] 4.3: Show stage indicator: "Stage X of 5: [Stage Name]"
  - [ ] 4.4: Use STAGE_LABELS from types/job.ts for stage names
  - [ ] 4.5: Add animated pulse on current stage indicator

- [ ] Task 5: Create LiveDiscoveriesPanel component (AC: #3)
  - [ ] 5.1: Create `frontend/src/components/features/upload/LiveDiscoveriesPanel.tsx`
  - [ ] 5.2: Display sections with icons:
    - Entities Found (Users icon): count + top 3 with roles
    - Dates Extracted (Calendar icon): earliest/latest range
    - Citations Detected (Scale icon): grouped by Act name with counts
  - [ ] 5.3: Create MiniTimelinePreview sub-component:
    - Horizontal line with dots for date clusters
    - Show year labels at earliest/latest points
  - [ ] 5.4: Display Early Insights section:
    - Info items (blue background) with Lightbulb icon
    - Warning items (yellow background) with AlertTriangle icon
  - [ ] 5.5: Add fade-in animation when new discoveries appear
  - [ ] 5.6: Use mock data initially (backend not ready)

- [ ] Task 6: Create ProcessingScreen component - Combined Stage 3-4 (AC: #1, #2, #3, #4)
  - [ ] 6.1: Create `frontend/src/components/features/upload/ProcessingScreen.tsx`
  - [ ] 6.2: Implement split layout:
    - Left panel: Document progress (UploadProgressView → ProcessingProgressView)
    - Right panel: LiveDiscoveriesPanel
  - [ ] 6.3: Add "Continue in Background" button at bottom
  - [ ] 6.4: Wire button to navigate to dashboard and persist progress in store
  - [ ] 6.5: Add header with matter name and back navigation

- [ ] Task 7: Update processing page route (AC: #1, #2, #3, #4)
  - [ ] 7.1: Replace placeholder in `frontend/src/app/(dashboard)/upload/processing/page.tsx`
  - [ ] 7.2: Render ProcessingScreen component
  - [ ] 7.3: Handle redirect if no files in store
  - [ ] 7.4: Use mock progress simulation for MVP (backend not ready)

- [ ] Task 8: Create mock progress simulation for MVP (AC: #1, #2, #3)
  - [ ] 8.1: Create `frontend/src/lib/utils/mock-processing.ts`
  - [ ] 8.2: Implement `simulateUploadProgress(files: File[])`:
    - Returns observable/callback-based progress updates
    - Simulates 500ms-2s per file upload
    - Randomly generates mock live discoveries
  - [ ] 8.3: Implement `simulateProcessingProgress()`:
    - Cycles through 5 stages with delays
    - Generates mock entities, dates, citations per stage
  - [ ] 8.4: Add MOCK_ENTITIES, MOCK_DATES, MOCK_CITATIONS constants
  - [ ] 8.5: Add TODO comments for future backend integration

- [ ] Task 9: Update MatterCardsGrid to show processing status (AC: #4)
  - [ ] 9.1: Modify `frontend/src/components/features/dashboard/MatterCardsGrid.tsx`
  - [ ] 9.2: Add "Processing" badge to matter card when matter is being processed
  - [ ] 9.3: Show mini progress bar on matter card during processing
  - [ ] 9.4: Update mock matters data to include processing state example

- [ ] Task 10: Export new components (AC: All)
  - [ ] 10.1: Update `frontend/src/components/features/upload/index.ts` with exports
  - [ ] 10.2: Ensure all new components are properly exported

- [ ] Task 11: Write comprehensive tests (AC: All)
  - [ ] 11.1: Create `UploadProgressView.test.tsx` - file progress, completion states
  - [ ] 11.2: Create `ProcessingProgressView.test.tsx` - stage display, progress bar
  - [ ] 11.3: Create `LiveDiscoveriesPanel.test.tsx` - discovery display, animations
  - [ ] 11.4: Create `ProcessingScreen.test.tsx` - layout, navigation, button actions
  - [ ] 11.5: Update `uploadWizardStore.test.ts` - new state and actions
  - [ ] 11.6: Create `mock-processing.test.ts` - simulation functions
  - [ ] 11.7: Update `MatterCardsGrid.test.tsx` - processing state display

## Dev Notes

### Critical Architecture Patterns

**UI Component Requirements:**
- Use shadcn/ui components: `Progress`, `Card`, `Button`, `Badge`, `Skeleton`
- Follow component structure: `frontend/src/components/features/upload/`
- Co-locate tests: `ComponentName.test.tsx` in same directory
- Use lucide-react icons: `CheckCircle2`, `Loader2`, `Users`, `Calendar`, `Scale`, `Lightbulb`, `AlertTriangle`, `ArrowLeft`, `Clock`

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const processingStage = useUploadWizardStore((state) => state.processingStage);
const overallProgressPct = useUploadWizardStore((state) => state.overallProgressPct);
const setProcessingStage = useUploadWizardStore((state) => state.setProcessingStage);

// WRONG - Full store subscription (causes re-renders)
const { processingStage, overallProgressPct } = useUploadWizardStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions:**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `ProcessingScreen`, `LiveDiscoveriesPanel` |
| Component files | PascalCase.tsx | `ProcessingScreen.tsx` |
| Variables | camelCase | `processingStage`, `overallProgressPct` |
| Functions | camelCase | `simulateUploadProgress`, `addLiveDiscovery` |
| Constants | SCREAMING_SNAKE | `MOCK_ENTITIES`, `PROCESSING_STAGES` |
| Types | PascalCase | `ProcessingStage`, `LiveDiscovery` |

### UX Design Reference

From UX-Decisions-Log.md Section 4.2 - Processing & Live Discovery Wireframe:

**Stage 3-4 Layout (from wireframe):**
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                    SEBI v. Parekh Securities Matter       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  PROCESSING YOUR CASE                                                     │ │
│  │  ████████████████████████████░░░░░░░░░░░░░░  67%                         │ │
│  │  Stage 3 of 5: Extracting entities & relationships                        │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │  📄 DOCUMENTS                       │  │  🔍 LIVE DISCOVERIES             │ │
│  │                                     │  │                                  │ │
│  │  ✓ 89 files received                │  │  👤 ENTITIES FOUND (34)          │ │
│  │  ✓ 2,100 pages extracted            │  │  • Mehul Parekh (Petitioner)     │ │
│  │                                     │  │  • Nirav D. Jobalia              │ │
│  │  OCR Progress:                      │  │  • Jitendra Kumar (Custodian)    │ │
│  │  ████████████████░░░░ 78%           │  │  • +8 more...                    │ │
│  │                                     │  │                                  │ │
│  │  ✓ Petition.pdf (234 pg)           │  │  📅 DATES EXTRACTED (47)         │ │
│  │  ✓ Reply_Affidavit.pdf (156 pg)    │  │  Earliest: May 12, 2016          │ │
│  │  ⏳ Annexure_K.pdf...              │  │  Latest: Jan 15, 2024            │ │
│  │  ○ ... 84 more                     │  │                                  │ │
│  │                                     │  │  ⚖️ CITATIONS DETECTED (23)      │ │
│  └─────────────────────────────────────┘  │  • Securities Act 1992 (18)      │ │
│                                           │  • SARFAESI Act 2002 (4)         │ │
│  ┌─────────────────────────────────────┐  │                                  │ │
│  │  📅 TIMELINE PREVIEW                │  └──────────────────────────────────┘ │
│  │  2016 ──●───────2018──●●●──2024──●  │                                      │
│  └─────────────────────────────────────┘                                      │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  💡 EARLY INSIGHTS                                                        │ │
│  │  🔍 "This case spans 7+ years with 4 major procedural stages"            │ │
│  │  ⚠️ "Found potential date discrepancy in notice timeline"                │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│                              [Continue in Background]                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Processing Stages (from UX-Decisions-Log.md Section 4.3):**
| Stage | Description |
|-------|-------------|
| Stage 1 | Upload - File upload, validation, unzip if needed |
| Stage 2 | OCR & Extract - Page-by-page text + bounding boxes |
| Stage 3 | Entity Resolution - Entity extraction, alias resolution, relationships |
| Stage 4 | Analysis Engines - Timeline, Citations, Contradictions |
| Stage 5 | Final Index - Final indexing, cache warming, ready notification |

**Live Discovery Updates (from UX-Decisions-Log.md Section 4.5):**
- Show live updates during processing to keep users engaged
- 2-5 minute wait feels shorter when seeing progress
- Updates shown: Documents processed, entities found, dates extracted, citations detected, early insights

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── app/(dashboard)/upload/processing/
│   └── page.tsx                    # UPDATE (replace placeholder)
├── components/features/upload/
│   ├── UploadProgressView.tsx      # NEW
│   ├── UploadProgressView.test.tsx # NEW
│   ├── ProcessingProgressView.tsx  # NEW
│   ├── ProcessingProgressView.test.tsx # NEW
│   ├── LiveDiscoveriesPanel.tsx    # NEW
│   ├── LiveDiscoveriesPanel.test.tsx # NEW
│   ├── ProcessingScreen.tsx        # NEW
│   ├── ProcessingScreen.test.tsx   # NEW
│   └── index.ts                    # UPDATE (add exports)
├── stores/
│   ├── uploadWizardStore.ts        # UPDATE (add processing state)
│   └── uploadWizardStore.test.ts   # UPDATE (add tests)
├── types/
│   └── upload.ts                   # UPDATE (add processing types)
└── lib/utils/
    ├── mock-processing.ts          # NEW
    └── mock-processing.test.ts     # NEW
```

**Existing Components/Utilities to Reuse (DO NOT RECREATE):**
- `frontend/src/types/job.ts` - JobStatus, STAGE_LABELS (for stage names)
- `frontend/src/types/upload.ts` - UploadWizardStage, DetectedAct (extend, don't replace)
- `frontend/src/stores/uploadWizardStore.ts` - Extend existing store (don't create new)
- `frontend/src/components/ui/progress.tsx` - shadcn Progress component
- `frontend/src/components/ui/card.tsx`, `badge.tsx`, `skeleton.tsx`
- `frontend/src/components/features/processing/JobProgressCard.tsx` - Reference for progress patterns

**Existing Processing Components (Reference for Patterns):**
- `JobProgressCard.tsx` - Shows how to display stage progress with tooltips
- `ProcessingQueue.tsx` - Shows job list with filtering and status display
- `processingStore.ts` - Shows how to handle job state with Map structure

### Backend API Integration

**No backend API exists yet for:**
- Matter creation with file upload
- Processing job status
- Live discovery streaming

**For MVP, implement with mock simulation:**
- `simulateUploadProgress()` - Fake file-by-file upload progress
- `simulateProcessingProgress()` - Fake stage transitions with discoveries
- `MOCK_DISCOVERIES` - Pre-defined entity/date/citation discoveries

**Mock Data Constants:**
```typescript
const MOCK_ENTITIES = [
  { name: 'Mehul Parekh', role: 'Petitioner' },
  { name: 'Nirav D. Jobalia', role: 'Respondent' },
  { name: 'Jitendra Kumar', role: 'Custodian' },
  { name: 'SEBI', role: 'Regulatory Authority' },
];

const MOCK_DATES = {
  earliest: new Date('2016-05-12'),
  latest: new Date('2024-01-15'),
  count: 47,
};

const MOCK_CITATIONS = [
  { actName: 'Securities Act 1992', count: 18 },
  { actName: 'SARFAESI Act 2002', count: 4 },
  { actName: 'Companies Act 2013', count: 1 },
];

const MOCK_INSIGHTS = [
  { type: 'info', message: 'This case spans 7+ years with 4 major procedural stages' },
  { type: 'warning', message: 'Found potential date discrepancy in notice timeline' },
];
```

**Future API Endpoints (not implemented yet):**
- `POST /api/matters` - Create matter and start upload
- `GET /api/matters/{id}/processing/status` - Get processing status
- `GET /api/matters/{id}/discoveries` - Get live discoveries (SSE stream)
- `POST /api/matters/{id}/background` - Move processing to background

### Previous Story Intelligence (9-1 through 9-4)

**From Story 9-4 implementation (direct predecessor):**
- UploadWizard navigates to `/upload/processing` after Act Discovery
- uploadWizardStore exists with FILE_SELECTION, REVIEW, ACT_DISCOVERY, UPLOADING stages
- Files stored in `files: File[]` array in store
- Matter name in `matterName: string`
- Processing page placeholder already exists at `app/(dashboard)/upload/processing/page.tsx`
- All 748 tests pass including 138 new tests from 9-4

**From Story 9-3 implementation:**
- 30-second polling pattern for real-time updates (reference for live updates)
- Error boundary wrapping for isolated failures
- Semantic HTML with aria-labels for accessibility
- QuickStats component shows card-based metrics display

**From Story 9-2 implementation:**
- MatterCardsGrid has existing card structure to modify for processing status
- matterStore uses Zustand with selector pattern
- Mock data extracted to separate file with TODO for backend

**Key Patterns Established:**
1. Use mock data initially - design interfaces for future backend
2. Follow selector pattern strictly for Zustand stores
3. Remove unused imports before committing
4. Use Next.js `<Link>` and `useRouter` for navigation
5. No console.log in production code
6. Add error boundaries where failures should be isolated
7. Use semantic HTML and aria-labels for accessibility
8. Co-locate test files with components

### Accessibility Requirements

From UX-Decisions-Log.md and project-context.md:
- Progress bars must have `role="progressbar"` and `aria-valuenow`
- Stage indicators should be announced to screen readers
- "Continue in Background" button should be keyboard accessible
- Live discoveries should use `aria-live="polite"` for announcements
- File completion checkmarks need `aria-label="Upload complete"`
- Error states need clear `aria-describedby` linking

### Performance Considerations

- Use `requestAnimationFrame` for smooth progress bar updates
- Batch live discovery updates (max 1 per 500ms to prevent DOM thrashing)
- Virtualize file list if >50 files using existing patterns
- Cancel simulation intervals on component unmount
- Use `useCallback` for stable function references
- Debounce store updates during rapid progress changes

### Animation Guidelines

**Progress Animations:**
```css
/* Progress bar fill - use CSS transitions */
.progress-bar {
  transition: width 300ms ease-out;
}

/* Stage indicator pulse */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.current-stage {
  animation: pulse 2s infinite;
}

/* Discovery fade-in */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
.discovery-item {
  animation: fadeIn 300ms ease-out;
}
```

### Error Handling

**Upload Errors:**
- Individual file failures should not stop other uploads
- Show red X icon on failed file with error message on hover
- Provide "Retry" button for failed uploads
- Track failed files in store: `failedUploads: Map<string, string>`

**Processing Errors:**
- Stage failures show warning but continue to next stage
- Critical failures redirect to error page with retry option
- Log errors to console with structured format (no raw console.log)

### Security Considerations

- Validate MIME types before simulating upload
- Don't expose internal file paths in UI
- Sanitize filenames before display
- Use `encodeURIComponent` for any URL parameters

### References

- [UX Wireframe: Processing & Live Discovery](../_bmad-output/project-planning-artifacts/UX-Decisions-Log.md#4-upload--processing)
- [Previous Story 9-4](../_bmad-output/implementation-artifacts/9-4-upload-stage-1-2.md)
- [Job Types](../frontend/src/types/job.ts)
- [Processing Store Pattern](../frontend/src/stores/processingStore.ts)
- [Project Context](../_bmad-output/project-context.md)
- [Architecture](../_bmad-output/architecture.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Types Extended (Task 1)**: Added `ProcessingStage`, `LiveDiscovery`, `UploadProgress`, `ProcessingProgress`, `DiscoveredEntity`, `DiscoveredDate`, `DiscoveredCitation`, `EarlyInsight` types to `frontend/src/types/upload.ts`. Added `PROCESSING_STAGE_LABELS` and `PROCESSING_STAGE_NUMBERS` constants.

2. **Store Extended (Task 2)**: Extended `uploadWizardStore.ts` with processing state (`uploadProgress`, `processingStage`, `overallProgressPct`, `liveDiscoveries`, `matterId`, `failedUploads`) and actions (`setUploadProgress`, `setProcessingStage`, `addLiveDiscovery`, `setMatterId`, `setOverallProgress`, `setUploadFailed`, `clearProcessingState`). Added selectors following MANDATORY pattern.

3. **UploadProgressView (Task 3)**: Created component showing file-by-file upload progress with status icons (CheckCircle2 for complete, Loader2 for uploading, XCircle for error, File for pending), individual progress bars, and overall progress percentage.

4. **ProcessingProgressView (Task 4)**: Created component with 5-stage indicator (UPLOADING → OCR → ENTITY_EXTRACTION → ANALYSIS → INDEXING), animated pulse on current stage, overall progress bar with percentage, and optional statistics display.

5. **LiveDiscoveriesPanel (Task 5)**: Created component with Entities section (Users icon), Dates section (Calendar icon) with earliest/latest, Citations section (Scale icon) grouped by Act, MiniTimelinePreview sub-component, and Early Insights section with info/warning styling. Added fade-in animations.

6. **ProcessingScreen (Task 6)**: Created combined Stage 3-4 screen with split layout (Documents | Discoveries), header with matter name, and "Continue in Background" button.

7. **Processing Page Route (Task 7)**: Updated `/upload/processing/page.tsx` to integrate ProcessingScreen with mock simulation. Handles redirect if no files in store.

8. **Mock Processing Simulation (Task 8)**: Created `mock-processing.ts` with `simulateUploadAndProcessing()`, `simulateUploadProgress()`, and `simulateProcessingProgress()` functions. Uses AbortController for cleanup. Generates mock entities, dates, citations, and insights per stage.

9. **MatterCardsGrid (Task 9)**: Already supports processing status via existing MatterCard component which has progress bar and status display - no changes needed.

10. **Component Exports (Task 10)**: Updated `frontend/src/components/features/upload/index.ts` with Stage 3-4 component exports.

11. **Comprehensive Tests (Task 11)**: Created tests for all new components:
    - `UploadProgressView.test.tsx` - 18 tests for file progress, completion states, accessibility
    - `ProcessingProgressView.test.tsx` - 18 tests for stage display, progress bar, statistics
    - `LiveDiscoveriesPanel.test.tsx` - 20 tests for discovery display, animations
    - `ProcessingScreen.test.tsx` - 16 tests for layout, navigation, button actions
    - `mock-processing.test.ts` - 16 tests for simulation functions
    - Extended `uploadWizardStore.test.ts` - 69 tests total (added ~40 new processing tests)

**All 869 tests pass.**

### File List

**New Files Created:**
- `frontend/src/components/features/upload/UploadProgressView.tsx`
- `frontend/src/components/features/upload/UploadProgressView.test.tsx`
- `frontend/src/components/features/upload/ProcessingProgressView.tsx`
- `frontend/src/components/features/upload/ProcessingProgressView.test.tsx`
- `frontend/src/components/features/upload/LiveDiscoveriesPanel.tsx`
- `frontend/src/components/features/upload/LiveDiscoveriesPanel.test.tsx`
- `frontend/src/components/features/upload/ProcessingScreen.tsx`
- `frontend/src/components/features/upload/ProcessingScreen.test.tsx`
- `frontend/src/lib/utils/mock-processing.ts`
- `frontend/src/lib/utils/mock-processing.test.ts`

**Modified Files:**
- `frontend/src/types/upload.ts` - Added processing types and constants
- `frontend/src/stores/uploadWizardStore.ts` - Extended with processing state/actions
- `frontend/src/stores/uploadWizardStore.test.ts` - Added processing tests
- `frontend/src/components/features/upload/index.ts` - Added Stage 3-4 exports
- `frontend/src/app/(dashboard)/upload/processing/page.tsx` - Replaced placeholder with ProcessingScreen
- `frontend/src/app/globals.css` - Added fade-in animation utility class

