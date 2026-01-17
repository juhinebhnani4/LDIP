# Story 14.13: Contradictions Tab UI Completion

Status: done

## Story

As a **legal attorney using LDIP**,
I want **the Contradictions Tab to display all detected contradictions with severity scoring and explanations**,
so that **I can review entity-based conflicts and verify or dismiss them without navigating away from the workspace**.

## Acceptance Criteria

1. **AC1: Contradictions Tab renders contradiction data from API**
   - Replace placeholder page with functional ContradictionsContent component
   - Call `GET /api/matters/{matter_id}/contradictions` on tab mount
   - Display loading skeleton while data is being fetched
   - Show empty state message when no contradictions exist

2. **AC2: Entity-grouped contradiction display**
   - Group contradictions by entity with canonical name header
   - Show contradiction count per entity in header
   - Collapsible entity sections (default expanded for first 3 entities)
   - Display contradiction cards within each entity section

3. **AC3: Contradiction card with full details per FR23**
   - Contradiction type badge (semantic/factual/date_mismatch/amount_mismatch)
   - Severity indicator with color coding (high=red, medium=yellow, low=gray)
   - Statement 1 with document name, page number, text excerpt, date (if available)
   - Statement 2 with document name, page number, text excerpt, date (if available)
   - Natural language explanation of the contradiction
   - Evidence links that open PDF split view on click

4. **AC4: Filtering controls**
   - Filter dropdown for severity (All, High, Medium, Low)
   - Filter dropdown for contradiction type (All, Semantic, Factual, Date Mismatch, Amount Mismatch)
   - Filter dropdown for entity (populated from current data)
   - Filters apply via API query parameters with URL state sync

5. **AC5: Pagination support**
   - Display pagination controls at bottom (prev/next, page numbers)
   - Default 20 items per page
   - Show total count in header ("45 contradictions found")

6. **AC6: Inline verification actions (deferred)**
   - Note: Verification buttons [Verify] [Dismiss] [Flag] will be added in a future story
   - For now, display contradiction cards as read-only

## Tasks / Subtasks

- [x] **Task 1: Create useContradictions hook** (AC: #1, #4, #5)
  - [x] 1.1 Create `frontend/src/hooks/useContradictions.ts`
  - [x] 1.2 Use SWR to fetch from `GET /api/matters/{matterId}/contradictions`
  - [x] 1.3 Add filter parameters (severity, contradictionType, entityId)
  - [x] 1.4 Add pagination parameters (page, perPage)
  - [x] 1.5 Handle loading, error, and empty states
  - [x] 1.6 Export TypeScript interfaces matching API response

- [x] **Task 2: Create ContradictionsContent component** (AC: #1, #2, #3)
  - [x] 2.1 Create `frontend/src/components/features/contradiction/ContradictionsContent.tsx`
  - [x] 2.2 Accept matterId prop and use useContradictions hook
  - [x] 2.3 Display loading skeleton using existing Skeleton components
  - [x] 2.4 Display empty state when no contradictions
  - [x] 2.5 Render EntityContradictionGroup for each entity group

- [x] **Task 3: Create EntityContradictionGroup component** (AC: #2)
  - [x] 3.1 Create `frontend/src/components/features/contradiction/EntityContradictionGroup.tsx`
  - [x] 3.2 Collapsible header with entity name and contradiction count
  - [x] 3.3 Default expanded for first 3 entities, collapsed otherwise
  - [x] 3.4 Render ContradictionCard for each contradiction

- [x] **Task 4: Create ContradictionCard component** (AC: #3)
  - [x] 4.1 Create `frontend/src/components/features/contradiction/ContradictionCard.tsx`
  - [x] 4.2 Display contradiction type badge using Badge component
  - [x] 4.3 Display severity indicator with color coding
  - [x] 4.4 Display Statement A and Statement B sections
  - [x] 4.5 Display explanation text
  - [x] 4.6 Display evidence links that open PDF viewer on click

- [x] **Task 5: Create StatementSection component** (AC: #3)
  - [x] 5.1 Create `frontend/src/components/features/contradiction/StatementSection.tsx`
  - [x] 5.2 Display document name as clickable link
  - [x] 5.3 Display page number
  - [x] 5.4 Display text excerpt with truncation (max 200 chars)
  - [x] 5.5 Display date if available

- [x] **Task 6: Create ContradictionsFilters component** (AC: #4)
  - [x] 6.1 Create `frontend/src/components/features/contradiction/ContradictionsFilters.tsx`
  - [x] 6.2 Severity dropdown (All, High, Medium, Low)
  - [x] 6.3 Type dropdown (All, Semantic, Factual, Date Mismatch, Amount Mismatch)
  - [x] 6.4 Entity dropdown (populated from unique entities in data)
  - [x] 6.5 Filters use local state (URL sync deferred - broken pattern avoided)

- [x] **Task 7: Create ContradictionsPagination component** (AC: #5)
  - [x] 7.1 Create `frontend/src/components/features/contradiction/ContradictionsPagination.tsx`
  - [x] 7.2 Custom pagination with page numbers and ellipsis
  - [x] 7.3 Show current page, total pages, prev/next buttons
  - [x] 7.4 Page changes via local state callbacks

- [x] **Task 8: Update Contradictions page** (AC: #1)
  - [x] 8.1 Update `frontend/src/app/matter/[matterId]/contradictions/page.tsx`
  - [x] 8.2 Remove placeholder content
  - [x] 8.3 Import and render ContradictionsContent component
  - [x] 8.4 Pass matterId prop from route params

- [x] **Task 9: Create component barrel file** (AC: all)
  - [x] 9.1 Create `frontend/src/components/features/contradiction/index.ts`
  - [x] 9.2 Export all contradiction components

- [x] **Task 10: Write tests** (AC: all)
  - [x] 10.1 Create `frontend/src/components/features/contradiction/__tests__/ContradictionsContent.test.tsx`
  - [x] 10.2 Test loading state display
  - [x] 10.3 Test empty state display
  - [x] 10.4 Test entity grouping renders correctly
  - [x] 10.5 Test filter changes trigger API refetch
  - [x] 10.6 Test pagination updates
  - [x] 10.7 Create `frontend/src/hooks/useContradictions.test.ts`
  - [x] 10.8 Test API call with correct parameters
  - [x] 10.9 Test error handling

## Review Notes
- Adversarial review completed
- Findings: 16 total, 5 fixed, 11 skipped (noise/low priority/deferred)
- Resolution approach: auto-fix real issues
- Fixed: Removed broken useContradictionsFilters hook, added safe transform functions, fixed button accessibility, added aria-hidden to pagination, fixed word-boundary truncation

## Dev Notes

### FR Reference

> **FR23: Contradictions Tab** - Display contradictions grouped by entity (canonical name header, contradiction cards below), show contradiction cards with: contradiction type badge (semantic/factual/date_mismatch/amount_mismatch), severity indicator (high/medium/low), entity name, Statement 1 with document+page+excerpt+date, Statement 2 with document+page+excerpt+date, contradiction explanation in natural language, evidence links (click to view in PDF), implement inline verification on each contradiction...

### Backend API (Already Implemented - Story 14-2)

```
GET /api/matters/{matter_id}/contradictions
Query params: severity, contradictionType, entityId, documentId, page, perPage, sortBy, sortOrder
```

Response structure:
```typescript
interface ContradictionsListResponse {
  data: EntityContradictions[];
  meta: {
    total: number;
    page: number;
    perPage: number;
    totalPages: number;
  };
}

interface EntityContradictions {
  entityId: string;
  entityName: string;
  contradictions: ContradictionItem[];
  count: number;
}

interface ContradictionItem {
  id: string;
  contradictionType: 'semantic_contradiction' | 'factual_contradiction' | 'date_mismatch' | 'amount_mismatch';
  severity: 'high' | 'medium' | 'low';
  entityId: string;
  entityName: string;
  statementA: StatementInfo;
  statementB: StatementInfo;
  explanation: string;
  evidenceLinks: EvidenceLink[];
  confidence: number;
  createdAt: string;
}

interface StatementInfo {
  documentId: string;
  documentName: string;
  page: number | null;
  excerpt: string;
  date: string | null;
}

interface EvidenceLink {
  statementId: string;
  documentId: string;
  documentName: string;
  page: number | null;
  bboxIds: string[];
}
```

### Existing Patterns to Follow

**SWR Hook Pattern (from useTimeline.ts):**
```typescript
export function useContradictions(matterId: string, options?: ContradictionsOptions) {
  const searchParams = useSearchParams();

  const params = new URLSearchParams();
  if (options?.severity) params.set('severity', options.severity);
  if (options?.contradictionType) params.set('contradictionType', options.contradictionType);
  // etc.

  const { data, error, isLoading, mutate } = useSWR<ContradictionsListResponse>(
    matterId ? `/api/matters/${matterId}/contradictions?${params}` : null,
    fetcher
  );

  return { data, error, isLoading, mutate };
}
```

**Component Structure (from VerificationContent.tsx):**
- Use Card component for contradiction cards
- Use Badge component for type/severity badges
- Use Collapsible from shadcn/ui for entity sections
- Use Skeleton for loading states

**Color Coding for Severity:**
- High: `bg-red-100 text-red-800` / `border-red-500`
- Medium: `bg-yellow-100 text-yellow-800` / `border-yellow-500`
- Low: `bg-gray-100 text-gray-800` / `border-gray-400`

**Type Badge Colors:**
- semantic_contradiction: `bg-purple-100 text-purple-800`
- factual_contradiction: `bg-red-100 text-red-800`
- date_mismatch: `bg-orange-100 text-orange-800`
- amount_mismatch: `bg-blue-100 text-blue-800`

### File Structure

```
frontend/src/
├── app/matter/[matterId]/contradictions/
│   └── page.tsx  (UPDATE - remove placeholder)
├── components/features/contradiction/
│   ├── index.ts
│   ├── ContradictionsContent.tsx
│   ├── ContradictionsFilters.tsx
│   ├── ContradictionsPagination.tsx
│   ├── EntityContradictionGroup.tsx
│   ├── ContradictionCard.tsx
│   ├── StatementSection.tsx
│   └── __tests__/
│       └── ContradictionsContent.test.tsx
└── hooks/
    ├── useContradictions.ts
    └── __tests__/
        └── useContradictions.test.ts
```

### Testing Strategy

- Mock SWR responses using msw or jest.mock
- Test component rendering for each state (loading, empty, data)
- Test filter interactions update URL params
- Test pagination controls

### References

- [Source: backend/app/api/routes/contradiction.py] - API endpoint implementation
- [Source: backend/app/models/contradiction_list.py] - Response models
- [Source: frontend/src/app/matter/[matterId]/contradictions/page.tsx] - Current placeholder
- [Source: frontend/src/components/features/verification/VerificationContent.tsx] - Similar pattern
- [Source: _bmad-output/implementation-artifacts/14-2-contradictions-list-api.md] - Backend story
