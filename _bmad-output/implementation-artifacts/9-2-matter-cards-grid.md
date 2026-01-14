# Story 9.2: Implement Matter Cards Grid

Status: done

## Story

As an **attorney**,
I want **to see all my matters as cards with status information**,
So that **I can quickly assess my work and continue where I left off**.

## Acceptance Criteria

1. **Given** I have multiple matters
   **When** the dashboard loads
   **Then** matters are displayed as cards in a grid (70% of viewport width)
   **And** each card shows: matter name, status badge, page count, last activity, verification %, issue count

2. **Given** a matter is processing
   **When** its card is displayed
   **Then** it shows a progress bar with percentage
   **And** estimated time remaining and doc/page counts

3. **Given** a matter is ready
   **When** its card is displayed
   **Then** it shows "Ready" status badge
   **And** a "Resume" button to enter the workspace

4. **Given** I click the view toggle
   **When** I switch between grid and list
   **Then** the layout changes accordingly
   **And** my preference is remembered

5. **Given** I use sort and filter controls
   **When** I select options
   **Then** matters are sorted by: Recent, Alphabetical, Most pages, Least verified, Date created
   **And** filtered by: All, Processing, Ready, Needs attention, Archived

## Tasks / Subtasks

- [x] Task 1: Create MatterCard component (AC: #1, #2, #3)
  - [x] 1.1: Create `frontend/src/components/features/dashboard/MatterCard.tsx`
  - [x] 1.2: Implement card layout matching UX wireframe: status badge, name, page count, last activity
  - [x] 1.3: Add verification % indicator with Badge component
  - [x] 1.4: Add issue count indicator with warning icon
  - [x] 1.5: Implement "Resume" button linking to workspace `/matter/{matterId}`

- [x] Task 2: Create MatterCardProcessing variant (AC: #2)
  - [x] 2.1: Create processing state variant within MatterCard component
  - [x] 2.2: Add progress bar using shadcn Progress component
  - [x] 2.3: Display percentage, estimated time remaining
  - [x] 2.4: Show document count and page count

- [x] Task 3: Create MatterCardsGrid component (AC: #1)
  - [x] 3.1: Create `frontend/src/components/features/dashboard/MatterCardsGrid.tsx`
  - [x] 3.2: Implement responsive grid layout (3 cols desktop, 2 tablet, 1 mobile)
  - [x] 3.3: Add "New Matter" card with + icon (first position)
  - [x] 3.4: Handle empty state (no matters)
  - [x] 3.5: Integrate with matterStore for data

- [x] Task 4: Create ViewToggle component (AC: #4)
  - [x] 4.1: Create `frontend/src/components/features/dashboard/ViewToggle.tsx`
  - [x] 4.2: Implement grid/list toggle buttons using ToggleGroup
  - [x] 4.3: Store preference in localStorage (key: `dashboard_view_preference`)
  - [x] 4.4: Initialize from localStorage on mount

- [x] Task 5: Create MatterFilters component (AC: #5)
  - [x] 5.1: Create `frontend/src/components/features/dashboard/MatterFilters.tsx`
  - [x] 5.2: Add sort dropdown: Recent, Alphabetical, Most pages, Least verified, Date created
  - [x] 5.3: Add filter buttons/dropdown: All, Processing, Ready, Needs attention, Archived
  - [x] 5.4: Connect to matterStore filter/sort state

- [x] Task 6: Create matterStore (All ACs)
  - [x] 6.1: Create `frontend/src/stores/matterStore.ts` using Zustand
  - [x] 6.2: Implement state: matters, isLoading, error, sortBy, filterBy, viewMode
  - [x] 6.3: Implement actions: fetchMatters, setSortBy, setFilterBy, setViewMode
  - [x] 6.4: Implement selectors for filtered/sorted matters
  - [x] 6.5: Connect to `/api/matters` endpoint (mock initially if needed)

- [x] Task 7: Extend matter types (All ACs)
  - [x] 7.1: Add to `frontend/src/types/matter.ts`:
    - `MatterProcessingStatus` type: 'processing' | 'ready' | 'needs_attention'
    - `MatterCardData` interface with processing fields
    - `MatterSortOption` and `MatterFilterOption` types

- [x] Task 8: Update dashboard page layout (AC: #1)
  - [x] 8.1: Update `frontend/src/app/(dashboard)/page.tsx` to add matter grid section
  - [x] 8.2: Add hero section with greeting and "+ New Matter" CTA
  - [x] 8.3: Position matter cards at 70% width (left side)
  - [x] 8.4: Reserve 30% width (right side) for activity feed (Story 9-3)

- [x] Task 9: Write tests (All ACs)
  - [x] 9.1: Create `MatterCard.test.tsx` - renders ready/processing states correctly
  - [x] 9.2: Create `MatterCardsGrid.test.tsx` - grid renders, empty state works
  - [x] 9.3: Create `ViewToggle.test.tsx` - toggle works, localStorage persists
  - [x] 9.4: Create `MatterFilters.test.tsx` - sort/filter interactions work
  - [x] 9.5: Create `matterStore.test.ts` - store actions and selectors work

## Dev Notes

### Critical Architecture Patterns

**UI Component Requirements:**
- Use shadcn/ui components: `Card`, `Badge`, `Progress`, `Button`, `ToggleGroup`, `Select`
- Follow component structure: `frontend/src/components/features/dashboard/`
- Co-locate tests: `ComponentName.test.tsx` in same directory

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const matters = useMatterStore((state) => state.matters);
const isLoading = useMatterStore((state) => state.isLoading);
const fetchMatters = useMatterStore((state) => state.fetchMatters);

// WRONG - Full store subscription (causes re-renders)
const { matters, isLoading, fetchMatters } = useMatterStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions:**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `MatterCard`, `MatterCardsGrid` |
| Component files | PascalCase.tsx | `MatterCard.tsx` |
| Variables | camelCase | `isLoading`, `filterBy` |
| Functions | camelCase | `fetchMatters`, `setFilterBy` |
| Constants | SCREAMING_SNAKE | `SORT_OPTIONS`, `FILTER_OPTIONS` |

### UX Design Reference

From UX-Decisions-Log.md wireframes:

**Matter Card - Processing State:**
```
┌────────────────────┐
│  ████████░░░ 67%   │
│                    │
│  SEBI v. Parekh    │
│                    │
│  Processing...     │
│  Est. 3 min left   │
│                    │
│  89 documents      │
│  2,100 pages       │
│                    │
│  [View Progress →] │
└────────────────────┘
```

**Matter Card - Ready State:**
```
┌────────────────────┐
│  ✓ Ready           │
│                    │
│  Shah v. Mehta     │
│                    │
│  1,247 pages       │
│  Last opened: 2h ago│
│                    │
│  ┌────┐ ┌────┐     │
│  │85% │ │ 3  │     │
│  │ ✓  │ │ ⚠️ │     │
│  └────┘ └────┘     │
│  Verified  Issues  │
│                    │
│  [Resume →]        │
└────────────────────┘
```

**Dashboard Layout (70/30 split):**
```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER (from Story 9-1)                                        │
├─────────────────────────────────────────┬───────────────────────┤
│                                         │                       │
│  Welcome, Juhi                          │  ACTIVITY FEED        │
│  [+ New Matter]                         │  (Story 9-3)          │
│                                         │                       │
│  ┌────────────┐  ┌────────────┐         │  Recent activity...   │
│  │  Matter 1  │  │  Matter 2  │         │                       │
│  │  Ready     │  │Processing  │         ├───────────────────────┤
│  │  892 pgs   │  │  67%       │         │  QUICK STATS          │
│  │[Resume →]  │  │[Progress →]│         │  (Story 9-3)          │
│  └────────────┘  └────────────┘         │                       │
│                                         │  📁 5 Active Matters  │
│  ┌────────────┐                         │  ✓ 127 Verified       │
│  │  + New     │                         │  ⏳ 3 Pending         │
│  │  Matter    │                         │                       │
│  └────────────┘                         │                       │
│  (70% width - this story)               │  (30% width - 9-3)    │
└─────────────────────────────────────────┴───────────────────────┘
```

**Sort Options:**
- Recent (default) - by `updatedAt` desc
- Alphabetical - by `title` asc
- Most pages - by `pageCount` desc
- Least verified - by `verificationPercent` asc
- Date created - by `createdAt` desc

**Filter Options:**
- All (default)
- Processing - `processingStatus === 'processing'`
- Ready - `processingStatus === 'ready'`
- Needs attention - `issueCount > 0` or `verificationPercent < 70`
- Archived - `status === 'archived'`

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── components/features/dashboard/    # This story
│   ├── DashboardHeader.tsx           # (9-1 - exists)
│   ├── MatterCard.tsx                # NEW
│   ├── MatterCard.test.tsx           # NEW
│   ├── MatterCardsGrid.tsx           # NEW
│   ├── MatterCardsGrid.test.tsx      # NEW
│   ├── ViewToggle.tsx                # NEW
│   ├── ViewToggle.test.tsx           # NEW
│   ├── MatterFilters.tsx             # NEW
│   ├── MatterFilters.test.tsx        # NEW
│   └── index.ts                      # UPDATE - add exports
├── stores/
│   ├── matterStore.ts                # NEW
│   └── matterStore.test.ts           # NEW
└── types/
    └── matter.ts                     # UPDATE - add processing types
```

**Existing Components to Use:**
- `frontend/src/components/ui/card.tsx` - Card primitives
- `frontend/src/components/ui/badge.tsx` - Status badges
- `frontend/src/components/ui/progress.tsx` - Progress bar
- `frontend/src/components/ui/button.tsx` - Buttons
- `frontend/src/components/ui/toggle-group.tsx` - View toggle
- `frontend/src/components/ui/select.tsx` - Sort/filter dropdowns

**Existing Patterns to Follow:**
- `frontend/src/stores/notificationStore.ts` - Zustand store structure (from 9-1)
- `frontend/src/components/features/dashboard/DashboardHeader.tsx` - Component structure
- `frontend/src/types/notification.ts` - TypeScript types structure

### Backend API Integration

**Existing Endpoint:** `GET /api/matters`
```typescript
// Response shape from backend/app/models/matter.py
interface MatterListResponse {
  data: Matter[];
  meta: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

interface Matter {
  id: string;
  title: string;
  description: string | null;
  status: 'active' | 'archived' | 'closed';
  createdAt: string;
  updatedAt: string;
  role: 'owner' | 'editor' | 'viewer' | null;
  memberCount: number;
}
```

**Missing Backend Data:** The current Matter model doesn't include:
- `pageCount` - total pages across all documents
- `documentCount` - number of documents
- `verificationPercent` - percentage of findings verified
- `issueCount` - flagged items needing attention
- `processingStatus` - 'processing' | 'ready' | 'needs_attention'
- `processingProgress` - percentage (0-100) during processing
- `estimatedTimeRemaining` - seconds remaining during processing

**Frontend Approach:** For MVP, extend frontend types and mock these fields. The backend will need to be updated to return this data. Use the existing API response structure and add mock data for the missing fields.

```typescript
// Extended type for frontend (mock data for now)
interface MatterCardData extends Matter {
  pageCount: number;
  documentCount: number;
  verificationPercent: number;
  issueCount: number;
  processingStatus: 'processing' | 'ready' | 'needs_attention';
  processingProgress?: number;
  estimatedTimeRemaining?: number;
  lastOpened?: string;
}
```

### Previous Story Intelligence (9-1)

**From Story 9-1 implementation:**
- DashboardHeader component successfully created with LDIP logo, search, notifications, user dropdown
- NotificationsDropdown uses mock data (backend API not yet available)
- GlobalSearch uses mock data (backend API not yet available)
- Zustand store pattern followed correctly with selectors
- Tests co-located with components (48 tests)
- Code review found: unused imports, console.log in production, missing Next.js Link component

**Key Learnings to Apply:**
1. Use mock data initially - design interfaces for future backend integration
2. Follow selector pattern strictly for Zustand stores
3. Remove unused imports before committing
4. Use Next.js `<Link>` component for internal navigation, not `<a>` tags
5. No console.log in production code

### Accessibility Requirements

From UX-Decisions-Log.md:
- Focus order: Tab through cards in reading order
- Keyboard: Enter/Space activates card actions
- ARIA: Cards should have `role="article"` or be contained in accessible list
- Status badges should have `aria-label` describing status

### Performance Considerations

- Cards render on dashboard - keep lightweight
- Lazy load matter details on hover/click
- Virtualize grid if more than 50 matters (future consideration)
- Cache matters in store with reasonable staleness (30 seconds)
- Skeleton loading state while fetching

### References

- [UX Wireframe](../_bmad-output/project-planning-artifacts/UX-Decisions-Log.md#3-dashboard--home)
- [Backend Matter API](../backend/app/api/routes/matters.py)
- [Frontend Matter Types](../frontend/src/types/matter.ts)
- [Previous Story 9-1](../_bmad-output/implementation-artifacts/9-1-dashboard-header.md)
- [Architecture Naming](../_bmad-output/architecture.md)
- [Project Context](../_bmad-output/project-context.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

- Implemented MatterCard component with ready and processing state variants
- Created MatterCardsGrid with responsive layout (3/2/1 columns), New Matter card, empty state, error state, and loading skeletons
- Added ViewToggle component with grid/list toggle, localStorage persistence via matterStore
- Created MatterFilters with sort dropdown (5 options) and filter dropdown (5 options)
- Built matterStore using Zustand with selector pattern per project-context.md
- Extended matter types with MatterCardData, MatterProcessingStatus, sort/filter types, and constants
- Updated dashboard page with 70/30 split layout, hero section with greeting
- Added shadcn/ui toggle-group component (@radix-ui/react-toggle-group)
- All 74 new tests pass (496 total tests in frontend)
- TypeScript compilation passes with no errors
- Uses mock data for backend fields not yet available (pageCount, documentCount, verificationPercent, etc.)

### File List

**New Files:**
- frontend/src/components/features/dashboard/MatterCard.tsx
- frontend/src/components/features/dashboard/MatterCard.test.tsx
- frontend/src/components/features/dashboard/MatterCardErrorBoundary.tsx (review fix)
- frontend/src/components/features/dashboard/MatterCardsGrid.tsx
- frontend/src/components/features/dashboard/MatterCardsGrid.test.tsx
- frontend/src/components/features/dashboard/ViewToggle.tsx
- frontend/src/components/features/dashboard/ViewToggle.test.tsx
- frontend/src/components/features/dashboard/MatterFilters.tsx
- frontend/src/components/features/dashboard/MatterFilters.test.tsx
- frontend/src/stores/matterStore.ts
- frontend/src/stores/matterStore.test.ts
- frontend/src/stores/__mocks__/matterData.ts (review fix)
- frontend/src/components/ui/toggle-group.tsx
- frontend/src/app/(dashboard)/DashboardContent.tsx

**Modified Files:**
- frontend/src/types/matter.ts (added processing types, sort/filter options)
- frontend/src/components/features/dashboard/index.ts (added new exports, MatterCardErrorBoundary)
- frontend/src/app/(dashboard)/page.tsx (updated layout with 70/30 split)
- frontend/package.json (added @radix-ui/react-toggle-group)

## Senior Developer Review (AI)

### Review Date: 2026-01-15

### Findings Fixed

**HIGH Priority (4 issues):**
1. **act() warning in MatterFilters test** - Fixed by wrapping store.setState in act() wrapper
2. **Zustand selector memoization** - Added useShallow from zustand/react/shallow to prevent unnecessary re-renders
3. **Client-side filtering clarity** - Added JSDoc comments to setSortBy/setFilterBy explaining client-side operation
4. **Mock data architecture** - Extracted to separate file with deterministic IDs

**MEDIUM Priority (4 issues):**
5. **Mock data extraction** - Created `frontend/src/stores/__mocks__/matterData.ts` with TODO for removal
6. **Deterministic IDs** - Mock matters now use stable IDs (e.g., `mock_matter_shah_v_mehta`) preventing React key changes
7. **Error boundary** - Created `MatterCardErrorBoundary` class component to isolate card failures
8. **Accessibility** - Added `role="feed"` and `aria-label` to grid container

**LOW Priority (1 issue):**
9. **Time constants** - Extracted magic numbers to named constants (MS_PER_MINUTE, MINUTES_PER_HOUR, etc.)

### Files Changed in Review

**New Files:**
- frontend/src/components/features/dashboard/MatterCardErrorBoundary.tsx
- frontend/src/stores/__mocks__/matterData.ts

**Modified Files:**
- frontend/src/components/features/dashboard/MatterCard.tsx (time constants)
- frontend/src/components/features/dashboard/MatterCardsGrid.tsx (useShallow, error boundary, role=feed)
- frontend/src/components/features/dashboard/MatterFilters.test.tsx (act() wrapper)
- frontend/src/components/features/dashboard/index.ts (export MatterCardErrorBoundary)
- frontend/src/stores/matterStore.ts (extracted mock data, added JSDoc comments)

### Test Results

- All 496 tests pass
- No act() warnings
- TypeScript compilation clean

## Change Log

- 2026-01-15: Story 9-2 implemented - Matter cards grid with view toggle, sort/filter, and responsive layout
- 2026-01-15: Code review fixes - Error boundary, useShallow memoization, mock data extraction, accessibility improvements

