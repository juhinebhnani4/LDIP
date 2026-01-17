# Story 10C.5: Citations Tab UI Completion

Status: done

## Story

As a **legal attorney using LDIP**,
I want **the Citations Tab to display all Act citations with verification status and Act Discovery information**,
so that **I can review citation accuracy, identify missing Acts, and verify citations against uploaded Act documents**.

## Acceptance Criteria

1. **AC1: Citations Tab renders citation data from API**
   - Replace placeholder page with functional CitationsContent component
   - Call `GET /api/matters/{matter_id}/citations` on tab mount
   - Display loading skeleton while data is being fetched
   - Show empty state message when no citations exist

2. **AC2: Citation list with verification status per FR22**
   - Display citation text, Act name, section number
   - Source document name and page number (clickable)
   - Verification status badge (verified/mismatch/not_found/act_unavailable)
   - Confidence score as progress bar
   - Click on citation row to open split view

3. **AC3: Act Discovery summary banner**
   - Show summary: "X Acts referenced, Y available, Z missing"
   - Button to open Act Discovery modal when missing Acts exist
   - Link to upload missing Acts

4. **AC4: Filtering controls**
   - Filter dropdown for verification status (All, Verified, Mismatch, Not Found, Act Unavailable)
   - Filter dropdown for Act name (populated from unique Acts in data)
   - Search input to filter by citation text
   - Filters apply via API query parameters with URL state sync

5. **AC5: Pagination support**
   - Display pagination controls at bottom
   - Default 20 items per page
   - Show total count in header

6. **AC6: Split view integration**
   - Click on citation opens PDF split view
   - Source document on left, Act document on right (if available)
   - Both sides highlight relevant bounding boxes
   - Use existing PdfSplitView component from Story 3-4

## Tasks / Subtasks

- [x] **Task 1: Create useCitations hook** (AC: #1, #4, #5)
  - [x] 1.1 Create `frontend/src/hooks/useCitations.ts`
  - [x] 1.2 Use SWR to fetch from `GET /api/matters/{matterId}/citations`
  - [x] 1.3 Add filter parameters (verificationStatus, actName, search)
  - [x] 1.4 Add pagination parameters (page, perPage)
  - [x] 1.5 Handle loading, error, and empty states
  - [x] 1.6 Export TypeScript interfaces matching API response

- [x] **Task 2: Create useCitationStats hook** (AC: #3)
  - [x] 2.1 Create `frontend/src/hooks/useCitationStats.ts` (implemented in useCitations.ts)
  - [x] 2.2 Fetch from `GET /api/matters/{matterId}/citations/stats`
  - [x] 2.3 Return totalCitations, uniqueActs, verifiedCount, pendingCount, missingActsCount

- [x] **Task 3: Create CitationsContent component** (AC: #1, #2, #3)
  - [x] 3.1 Create `frontend/src/components/features/citation/CitationsContent.tsx`
  - [x] 3.2 Accept matterId prop and use useCitations hook
  - [x] 3.3 Display Act Discovery summary banner at top
  - [x] 3.4 Display loading skeleton using existing Skeleton components
  - [x] 3.5 Display empty state when no citations
  - [x] 3.6 Render CitationsList component for data display

- [x] **Task 4: Create ActDiscoverySummary component** (AC: #3)
  - [x] 4.1 Implemented in CitationsHeader.tsx (integrated)
  - [x] 4.2 Use useCitationStats hook for counts
  - [x] 4.3 Display "X Acts referenced, Y available, Z missing" message
  - [x] 4.4 Show "Upload Missing Acts" button when missing > 0
  - [x] 4.5 Button triggers ActDiscoveryTrigger modal (already exists)

- [x] **Task 5: Create CitationsList component** (AC: #2)
  - [x] 5.1 Create `frontend/src/components/features/citation/CitationsList.tsx`
  - [x] 5.2 Render as table or list view
  - [x] 5.3 Columns: Citation Text, Act Name, Section, Document, Page, Status, Confidence
  - [x] 5.4 Click handler on row opens split view

- [x] **Task 6: Create CitationRow component** (AC: #2, #6)
  - [x] 6.1 Implemented inline in CitationsList.tsx (TableRow)
  - [x] 6.2 Display citation text (truncated)
  - [x] 6.3 Display Act name and section number
  - [x] 6.4 Display source document name as link
  - [x] 6.5 Display verification status badge with color coding
  - [x] 6.6 Display confidence as progress bar
  - [x] 6.7 Click handler calls onCitationClick prop

- [x] **Task 7: Create CitationsFilters component** (AC: #4)
  - [x] 7.1 Implemented in CitationsHeader.tsx (integrated)
  - [x] 7.2 Verification status dropdown (All, Verified, Mismatch, Not Found, Act Unavailable)
  - [x] 7.3 Act name dropdown (populated from useCitationStats unique acts)
  - [x] 7.4 Search input for citation text
  - [x] 7.5 Sync filters with URL query params

- [x] **Task 8: Create CitationsPagination component** (AC: #5)
  - [x] 8.1 Implemented inline in CitationsList.tsx
  - [x] 8.2 Use existing Pagination component
  - [x] 8.3 Show current page, total pages
  - [x] 8.4 Update URL query params on page change

- [x] **Task 9: Integrate CitationSplitView** (AC: #6)
  - [x] 9.1 Import existing PdfSplitView component (from Story 3-4/11-5)
  - [x] 9.2 Fetch split view data from `GET /api/matters/{matterId}/citations/{citationId}/split-view`
  - [x] 9.3 Open in slide-over panel when citation clicked
  - [x] 9.4 Handle "Act Unavailable" state gracefully (show only source side)

- [x] **Task 10: Update Citations page** (AC: #1)
  - [x] 10.1 Update `frontend/src/app/matter/[matterId]/citations/page.tsx`
  - [x] 10.2 Remove placeholder content
  - [x] 10.3 Import and render CitationsContent component
  - [x] 10.4 Pass matterId prop from route params

- [x] **Task 11: Create component barrel file** (AC: all)
  - [x] 11.1 Create/update `frontend/src/components/features/citation/index.ts`
  - [x] 11.2 Export all citation components

- [x] **Task 12: Write tests** (AC: all)
  - [x] 12.1 Create `frontend/src/components/features/citation/__tests__/CitationsContent.test.tsx`
  - [x] 12.2 Test loading state display
  - [x] 12.3 Test empty state display
  - [x] 12.4 Test citation list renders correctly
  - [x] 12.5 Test filter changes trigger API refetch
  - [x] 12.6 Test click on citation opens split view
  - [x] 12.7 Create `frontend/src/hooks/__tests__/useCitations.test.ts`

## Dev Notes

### FR Reference

> **FR22: Citations Tab** - Display Act Discovery Report summary (X Acts referenced, Y available, Z missing), show list of all extracted citations with columns: citation text, Act name, section, source document+page, verification status (verified/mismatch/not_found/act_unavailable), confidence score, implement filter by verification status and Act name, show action button to upload missing Acts, implement click on citation to open split-view showing source location (case file) on left AND target location (Act file) on right with both locations highlighted

### Backend API (Already Implemented - Stories 3-1 to 3-4)

**List Citations:**
```
GET /api/matters/{matter_id}/citations
Query params: actName, verificationStatus, documentId, page, perPage
```

**Citation Stats:**
```
GET /api/matters/{matter_id}/citations/stats
Returns: totalCitations, uniqueActs, verifiedCount, pendingCount, missingActsCount
```

**Split View Data:**
```
GET /api/matters/{matter_id}/citations/{citation_id}/split-view
Returns: citation, sourceDocument (url, page, bboxes), targetDocument (url, page, bboxes), verification
```

### TypeScript Interfaces

```typescript
interface CitationListItem {
  id: string;
  actName: string;
  sectionNumber: string;
  subsection: string | null;
  rawCitationText: string;
  sourcePage: number | null;
  verificationStatus: 'pending' | 'verified' | 'mismatch' | 'not_found' | 'act_unavailable';
  confidence: number;
  documentId: string;
  documentName: string;
}

interface CitationsListResponse {
  data: CitationListItem[];
  meta: {
    total: number;
    page: number;
    perPage: number;
    totalPages: number;
  };
}

interface CitationStatsResponse {
  totalCitations: number;
  uniqueActs: number;
  verifiedCount: number;
  pendingCount: number;
  missingActsCount: number;
}
```

### Verification Status Badge Colors

- `verified`: `bg-green-100 text-green-800 border-green-500`
- `mismatch`: `bg-red-100 text-red-800 border-red-500`
- `not_found`: `bg-yellow-100 text-yellow-800 border-yellow-500`
- `act_unavailable`: `bg-gray-100 text-gray-800 border-gray-400`
- `pending`: `bg-blue-100 text-blue-800 border-blue-400`

### Existing Components to Reuse

- `PdfSplitView` from Story 11-5 - for side-by-side PDF display
- `ActDiscoveryTrigger` from Story 3-2 - for missing Acts modal
- `Badge` from shadcn/ui - for status badges
- `Progress` from shadcn/ui - for confidence display
- `Skeleton` from shadcn/ui - for loading states

### File Structure

```
frontend/src/
├── app/matter/[matterId]/citations/
│   └── page.tsx  (UPDATE - remove placeholder)
├── components/features/citation/
│   ├── index.ts (UPDATE - add exports)
│   ├── CitationsContent.tsx
│   ├── CitationsList.tsx
│   ├── CitationRow.tsx
│   ├── CitationsFilters.tsx
│   ├── CitationsPagination.tsx
│   ├── ActDiscoverySummary.tsx
│   └── __tests__/
│       └── CitationsContent.test.tsx
└── hooks/
    ├── useCitations.ts
    ├── useCitationStats.ts
    └── __tests__/
        └── useCitations.test.ts
```

### References

- [Source: backend/app/api/routes/citations.py] - API endpoints
- [Source: backend/app/models/citation.py] - Response models
- [Source: frontend/src/app/matter/[matterId]/citations/page.tsx] - Current placeholder
- [Source: frontend/src/components/features/citation/ActDiscoveryTrigger.tsx] - Existing modal trigger
- [Source: _bmad-output/implementation-artifacts/3-4-split-view-citation-highlighting.md] - Split view story
