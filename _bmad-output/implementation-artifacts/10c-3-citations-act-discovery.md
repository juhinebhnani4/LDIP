# Story 10C.3: Implement Citations Tab List and Act Discovery

Status: review

## Story

As an **attorney**,
I want **to see all citations with their verification status**,
So that **I can identify citation issues quickly**.

## Acceptance Criteria

1. **Given** I open the Citations tab
   **When** the content loads
   **Then** I see the Act Discovery Report summary (X Acts referenced, Y available, Z missing)
   **And** a list of all extracted citations

2. **Given** citations are displayed
   **When** I view the list
   **Then** columns show: citation text, Act name, section, source document+page, verification status, confidence score

3. **Given** I filter citations
   **When** I select filters
   **Then** I can filter by: verification status (verified, mismatch, not_found, act_unavailable), Act name
   **And** the list updates accordingly

4. **Given** an Act is missing
   **When** I click "Upload Act"
   **Then** I can upload the Act document
   **And** citations are re-verified automatically

## Tasks / Subtasks

- [x] Task 1: Create CitationsHeader component with stats and filters (AC: #1, #3)
  - [x] 1.1: Create `CitationsHeader.tsx` with stats display (total, verified, issues, pending)
  - [x] 1.2: Add "X Acts referenced, Y available, Z missing" summary from Act Discovery API
  - [x] 1.3: Add verification status filter dropdown
  - [x] 1.4: Add Act name filter dropdown (populated from summary API)
  - [x] 1.5: Add view mode toggle: List | By Document | By Act (prepare for future)
  - [x] 1.6: Add "Show only issues" checkbox filter
  - [x] 1.7: Create `CitationsHeader.test.tsx` with unit tests

- [x] Task 2: Create CitationsAttentionBanner component (AC: #1)
  - [x] 2.1: Create `CitationsAttentionBanner.tsx` showing citation issues count
  - [x] 2.2: Display "X citations have incorrect section references" message
  - [x] 2.3: Add "Review Issues" button that filters to issues only
  - [x] 2.4: Show missing acts count with "Upload Missing Acts" action
  - [x] 2.5: Create `CitationsAttentionBanner.test.tsx`

- [x] Task 3: Enhance CitationsList component (AC: #2)
  - [x] 3.1: Update table columns: Citation Text, Act Name, Section, Source Doc+Page, Status, Confidence, Actions
  - [x] 3.2: Add confidence score column with percentage display
  - [x] 3.3: Add source document name column (clickable to navigate)
  - [x] 3.4: Update status badge styling per UX spec (verified, pending, issue, manual, cannot verify)
  - [x] 3.5: Add sorting by column headers (Act, Section, Status, Confidence)
  - [x] 3.6: Update `CitationsList.test.tsx` with new columns

- [x] Task 4: Implement CitationsByActView component (AC: #2)
  - [x] 4.1: Create `CitationsByActView.tsx` showing citations grouped by Act
  - [x] 4.2: Display Act name as expandable section header with citation count
  - [x] 4.3: Show section breakdown under each Act (Section 3(3): 8 citations, etc.)
  - [x] 4.4: Add inline issue indicators (e.g., "Section 15B doesn't exist")
  - [x] 4.5: Add "View" and "Fix" action buttons per row
  - [x] 4.6: Create `CitationsByActView.test.tsx`

- [x] Task 5: Implement CitationsByDocumentView component (AC: #2)
  - [x] 5.1: Create `CitationsByDocumentView.tsx` showing citations grouped by document
  - [x] 5.2: Display document name as expandable section with page count
  - [x] 5.3: Show citations in page order within each document
  - [x] 5.4: Include columns: Page, Citation, Status, Action
  - [x] 5.5: Create `CitationsByDocumentView.test.tsx`

- [x] Task 6: Create MissingActsCard component for Act upload (AC: #4)
  - [x] 6.1: Create `MissingActsCard.tsx` showing missing acts list
  - [x] 6.2: Display each missing act with citation count
  - [x] 6.3: Add "Upload Act" button per missing act
  - [x] 6.4: Integrate with existing ActUploadDropzone component
  - [x] 6.5: After upload, call `markActUploadedAndVerify` API for auto-verification
  - [x] 6.6: Add "Skip" action to mark act as skipped
  - [x] 6.7: Create `MissingActsCard.test.tsx`

- [x] Task 7: Create useCitations hook for data fetching (AC: All)
  - [x] 7.1: Create `frontend/src/hooks/useCitations.ts` with SWR
  - [x] 7.2: Add `useCitationsList` hook with filtering and pagination
  - [x] 7.3: Add `useCitationStats` hook for statistics
  - [x] 7.4: Add `useCitationSummaryByAct` hook for By Act view
  - [x] 7.5: Add `useActDiscoveryReport` hook for missing acts
  - [x] 7.6: Add mutation hooks for Act upload and skip actions
  - [x] 7.7: Create `useCitations.test.ts`

- [x] Task 8: Update CitationsContent container component (AC: All)
  - [x] 8.1: Create `CitationsContent.tsx` as main container
  - [x] 8.2: Integrate CitationsHeader with filter state
  - [x] 8.3: Integrate CitationsAttentionBanner
  - [x] 8.4: Switch between List, By Act, By Document views based on viewMode
  - [x] 8.5: Wire up filter state to API queries
  - [x] 8.6: Add MissingActsCard in sidebar or collapsible section
  - [x] 8.7: Create `CitationsContent.test.tsx`

- [x] Task 9: Update CitationsTab page component (AC: All)
  - [x] 9.1: Replace simple content with CitationsContent
  - [x] 9.2: Pass matterId to all child components
  - [x] 9.3: Update barrel exports in `index.ts`
  - [x] 9.4: Update CitationsTab.test.tsx

- [x] Task 10: TypeScript validation and final integration
  - [x] 10.1: Run TypeScript compiler - fix all errors
  - [x] 10.2: Run ESLint - fix all warnings
  - [x] 10.3: Run all Citation-related tests
  - [x] 10.4: Manual integration test with existing split view

## Dev Notes

### Critical Architecture Patterns

**Backend API (Already Implemented - backend/app/api/routes/citations.py):**

All endpoints are fully implemented:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/matters/{matter_id}/citations` | GET | List citations (paginated, filterable by act_name, verification_status, document_id) |
| `/api/matters/{matter_id}/citations/{citation_id}` | GET | Get single citation |
| `/api/matters/{matter_id}/citations/stats` | GET | Get citation statistics |
| `/api/matters/{matter_id}/citations/summary/by-act` | GET | Get citations grouped by Act |
| `/api/matters/{matter_id}/citations/acts/discovery` | GET | Get Act Discovery Report |
| `/api/matters/{matter_id}/citations/acts/mark-uploaded` | POST | Mark Act as uploaded |
| `/api/matters/{matter_id}/citations/acts/mark-skipped` | POST | Mark Act as skipped |
| `/api/matters/{matter_id}/citations/acts/mark-uploaded-verify` | POST | Upload and auto-verify |
| `/api/matters/{matter_id}/citations/{citation_id}/split-view` | GET | Get split view data |

**Frontend Types (Already Implemented - frontend/src/types/citation.ts):**

All types are defined:
- `CitationListItem`, `Citation` - Citation data models
- `CitationStats` - Statistics response
- `CitationSummaryItem`, `CitationSummaryResponse` - By-act summary
- `ActDiscoverySummary`, `ActDiscoveryResponse` - Discovery report
- `VerificationStatus` - 'pending' | 'verified' | 'mismatch' | 'section_not_found' | 'act_unavailable'

**Frontend API Client (Already Implemented - frontend/src/lib/api/citations.ts):**

All API functions exist:
- `getCitations(matterId, options)` - Paginated list with filters
- `getCitationStats(matterId)` - Statistics
- `getCitationSummary(matterId)` - By-Act summary
- `getActDiscoveryReport(matterId)` - Discovery report
- `markActUploaded(matterId, request)` - Mark uploaded
- `markActSkipped(matterId, request)` - Mark skipped
- `markActUploadedAndVerify(matterId, request)` - Upload and verify

### UX Design Specifications (from UX-Decisions-Log.md Section 10)

**Main View Layout:**
```
Citations Tab
├── Stats Bar: "23 found | 18 verified | 3 issues | 2 pending"
├── Attention Banner: "3 CITATIONS NEED ATTENTION" (collapsible)
├── View Toggle: [List] [By Document] [By Act]
├── Filters: Status dropdown, Act dropdown, "Show only issues" checkbox
└── Content Area:
    ├── List View: Table with sortable columns
    ├── By Document View: Documents as expandable sections
    └── By Act View: Acts as expandable sections with section breakdown
```

**Citation Status Types:**
| Status | Icon | Badge Variant | Description |
|--------|------|---------------|-------------|
| verified | CheckCircle | default (green) | Citation exists and matches source |
| pending | Clock | outline | Not yet verified |
| mismatch | AlertTriangle | destructive | Problem detected |
| section_not_found | HelpCircle | secondary | Section not found in Act |
| act_unavailable | Clock | outline | Act document not uploaded |

**Issue Types to Display:**
- "Section doesn't exist" - with suggestion of similar sections
- "Outdated act name" - show current name
- "Wrong year" - suggest correct year
- "Typo in citation" - suggest correction
- "Ambiguous reference" - ask user to clarify

### Existing Components to Reuse

**From frontend/src/components/features/citation/:**
- `ActDiscoveryModal.tsx` - Modal for Act discovery (adapt for MissingActsCard)
- `ActDiscoveryItem.tsx` - Single act item display
- `ActUploadDropzone.tsx` - Upload dropzone for Acts
- `SplitViewCitationPanel.tsx` - Split view panel (already integrated)
- `SplitViewModal.tsx` - Full screen split view
- `CitationsList.tsx` - Basic list (needs enhancement)

**From frontend/src/components/ui/ (shadcn/ui):**
- `Table`, `TableBody`, `TableCell`, `TableHead`, `TableHeader`, `TableRow`
- `Badge`
- `Button`
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue`
- `Checkbox`
- `Collapsible`, `CollapsibleContent`, `CollapsibleTrigger`
- `Skeleton`
- `Tabs`, `TabsList`, `TabsTrigger` (for view toggle)

### Component File Structure

```
frontend/src/components/features/citation/
├── index.ts                    # Update barrel exports
├── CitationsTab.tsx            # Update entry point
├── CitationsContent.tsx        # NEW - Main container
├── CitationsContent.test.tsx   # NEW
├── CitationsHeader.tsx         # NEW - Stats and filters
├── CitationsHeader.test.tsx    # NEW
├── CitationsAttentionBanner.tsx# NEW - Issues alert
├── CitationsAttentionBanner.test.tsx # NEW
├── CitationsList.tsx           # MODIFY - Enhanced columns
├── CitationsList.test.tsx      # Update tests
├── CitationsByActView.tsx      # NEW - Grouped by Act
├── CitationsByActView.test.tsx # NEW
├── CitationsByDocumentView.tsx # NEW - Grouped by document
├── CitationsByDocumentView.test.tsx # NEW
├── MissingActsCard.tsx         # NEW - Upload missing acts
├── MissingActsCard.test.tsx    # NEW
├── ActDiscoveryModal.tsx       # Existing
├── ActDiscoveryItem.tsx        # Existing
├── ActUploadDropzone.tsx       # Existing
├── SplitViewCitationPanel.tsx  # Existing
└── SplitViewModal.tsx          # Existing
```

### Hooks Structure

```
frontend/src/hooks/
├── useCitations.ts             # NEW - SWR hooks for citations
└── useSplitView.ts             # Existing - Already implemented
```

### State Management Pattern

```typescript
// CitationsContent.tsx state shape
interface CitationsContentState {
  viewMode: 'list' | 'byDocument' | 'byAct';
  filters: {
    verificationStatus: VerificationStatus | null;
    actName: string | null;
    showOnlyIssues: boolean;
  };
  currentPage: number;
}

// useCitations hook - SWR pattern
export function useCitationsList(matterId: string, options: CitationListOptions) {
  const queryKey = `/api/matters/${matterId}/citations?${new URLSearchParams(options)}`;
  return useSWR(queryKey, () => getCitations(matterId, options));
}

export function useCitationStats(matterId: string) {
  return useSWR(`/api/matters/${matterId}/citations/stats`, () => getCitationStats(matterId));
}

export function useActDiscoveryReport(matterId: string) {
  return useSWR(`/api/matters/${matterId}/citations/acts/discovery`, () => getActDiscoveryReport(matterId));
}
```

### Previous Story Intelligence (Story 10C.2)

**Patterns to Follow:**
- Use `entityTypeConfig` pattern for citation status icons/colors (extract to shared utility)
- Follow EntitiesHeader pattern for CitationsHeader (stats + filters)
- Follow EntitiesContent pattern for CitationsContent (view mode switching)
- Use same multi-selection pattern if needed for batch operations
- SWR hook pattern with cache invalidation after mutations

**Components Created in 10C.2:**
- EntitiesHeader.tsx - Reference for filter/stats header pattern
- EntitiesContent.tsx - Reference for view mode switching
- EntitiesListView.tsx - Reference for sortable table pattern
- EntitiesGridView.tsx - Reference for card grid layout
- EntityMergeDialog.tsx - Reference for confirmation dialogs

### Git Commit Pattern

Following established format:
```
feat(citations): implement citations tab list and act discovery (Story 10C.3)
```

### Lucide-react Icons to Use

```typescript
import {
  Scale,           // ⚖️ Act/statute icon
  FileText,        // 📄 Document icon
  CheckCircle,     // ✓ Verified status
  AlertTriangle,   // ⚠️ Issue/mismatch status
  Clock,           // ⏳ Pending status
  HelpCircle,      // ❓ Not found status
  Upload,          // Upload action
  Eye,             // View action
  Wrench,          // Fix action
  Filter,          // Filter icon
  ChevronDown,     // Expand/collapse
  ChevronRight,    // Expand indicator
  XCircle,         // Cannot verify
  List,            // List view
  Layers,          // By Act view
  File,            // By Document view
} from 'lucide-react';
```

### Testing Considerations

**Mock Data Examples:**
```typescript
const mockCitationStats: CitationStats = {
  totalCitations: 23,
  uniqueActs: 6,
  verifiedCount: 18,
  pendingCount: 2,
  missingActsCount: 2,
};

const mockActDiscovery: ActDiscoverySummary[] = [
  {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 12,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-123',
  },
  {
    actName: 'Negotiable Instruments Act, 1881',
    actNameNormalized: 'negotiable_instruments_act_1881',
    citationCount: 8,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  },
];

const mockCitationListItem: CitationListItem = {
  id: 'cit-1',
  actName: 'Securities Act, 1992',
  sectionNumber: '3',
  subsection: '3',
  clause: null,
  rawCitationText: 'Section 3(3) of the Securities Act, 1992',
  sourcePage: 45,
  verificationStatus: 'verified',
  confidence: 95.0,
  documentId: 'doc-456',
  documentName: 'Petition.pdf',
};
```

### Accessibility Requirements

- Sortable table headers with aria-sort attributes
- Filter dropdowns with proper labeling
- Expand/collapse sections with aria-expanded
- Status badges with descriptive text (not just color)
- Keyboard navigation for table rows
- Focus management when switching views

### Performance Considerations

- Lazy load citations per page (already implemented)
- SWR caching with smart invalidation
- Debounce filter changes before API call
- Virtual scrolling for large citation lists (>100 items)
- Skeleton loading states for each view

### Project Structure Notes

**File Locations (MANDATORY):**
- Citation components: `frontend/src/components/features/citation/`
- Types: `frontend/src/types/citation.ts` (existing, complete)
- API functions: `frontend/src/lib/api/citations.ts` (existing, complete)
- Hooks: `frontend/src/hooks/useCitations.ts` (new)
- Tests co-located: `ComponentName.test.tsx` next to `ComponentName.tsx`

### References

- [Source: epics.md#story-10c3 - Acceptance criteria]
- [Source: UX-Decisions-Log.md#section-10 - Citations Tab UX (sections 10.1-10.8)]
- [Source: backend/app/api/routes/citations.py - All API endpoints]
- [Source: frontend/src/types/citation.ts - All TypeScript types]
- [Source: frontend/src/lib/api/citations.ts - All API client functions]
- [Source: Story 10C.2 - Previous implementation patterns]
- [Source: project-context.md - Zustand selectors, naming conventions, testing rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Fixed ToggleGroup role queries (renders as radio buttons, not button role)
- Fixed SWR cache pollution between tests by using different matter IDs
- Fixed TypeScript noUncheckedIndexedAccess errors with safe array access
- Fixed Collapsible content visibility assertions (unmount vs hide behavior)
- Installed shadcn Collapsible component via CLI

### Completion Notes List

- All 201 citation-related tests pass
- TypeScript compilation passes for all citation components
- All new components follow established patterns from Story 10C.2
- Barrel exports updated in both components and hooks index files
- View mode toggle uses ToggleGroup for List/By Document/By Act views
- MissingActsCard integrates with ActUploadDropzone for Act uploads
- useCitations hooks implement SWR pattern with proper cache keys

### File List

**New Files to Create:**
- `frontend/src/components/features/citation/CitationsContent.tsx`
- `frontend/src/components/features/citation/CitationsContent.test.tsx`
- `frontend/src/components/features/citation/CitationsHeader.tsx`
- `frontend/src/components/features/citation/CitationsHeader.test.tsx`
- `frontend/src/components/features/citation/CitationsAttentionBanner.tsx`
- `frontend/src/components/features/citation/CitationsAttentionBanner.test.tsx`
- `frontend/src/components/features/citation/CitationsByActView.tsx`
- `frontend/src/components/features/citation/CitationsByActView.test.tsx`
- `frontend/src/components/features/citation/CitationsByDocumentView.tsx`
- `frontend/src/components/features/citation/CitationsByDocumentView.test.tsx`
- `frontend/src/components/features/citation/MissingActsCard.tsx`
- `frontend/src/components/features/citation/MissingActsCard.test.tsx`
- `frontend/src/hooks/useCitations.ts`
- `frontend/src/hooks/useCitations.test.ts`

**Files to Modify:**
- `frontend/src/components/features/citation/CitationsTab.tsx` - Use CitationsContent
- `frontend/src/components/features/citation/CitationsList.tsx` - Enhanced columns
- `frontend/src/components/features/citation/CitationsList.test.tsx` - Updated tests
- `frontend/src/components/features/citation/index.ts` - Updated barrel exports

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-15 | Story created with comprehensive developer context | Claude Opus 4.5 |
| 2026-01-15 | All tasks completed, all tests pass, status changed to review | Claude Opus 4.5 |
