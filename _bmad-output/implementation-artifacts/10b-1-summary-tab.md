# Story 10B.1: Implement Summary Tab Content

Status: review

## Story

As an **attorney**,
I want **a summary view of my matter with key information**,
So that **I can quickly understand the case at a glance**.

## Acceptance Criteria

1. **Given** I open the Summary tab
   **When** content loads
   **Then** I see: attention banner (items needing action), parties section, subject matter, current status, key issues, matter statistics

2. **Given** items need attention
   **When** the attention banner shows
   **Then** it lists: contradictions found, citation issues with count
   **And** "Review All" links to the relevant tabs

3. **Given** parties are extracted
   **When** the parties section shows
   **Then** Petitioner and Respondent cards show entity links
   **And** clicking an entity opens the Entities tab

4. **Given** matter statistics load
   **When** the stats section shows
   **Then** I see cards with: total pages, entities found, events extracted, citations found

## Tasks / Subtasks

- [x] Task 1: Create Summary Tab page component (AC: #1, #4)
  - [x] 1.1: Create `frontend/src/app/(matter)/[matterId]/summary/page.tsx` - replace placeholder with full implementation
  - [x] 1.2: Create data fetching hooks with SWR for summary data
  - [x] 1.3: Implement loading skeleton state during data fetch
  - [x] 1.4: Implement error boundary for failed data fetches

- [x] Task 2: Create Attention Banner component (AC: #2)
  - [x] 2.1: Create `frontend/src/components/features/summary/AttentionBanner.tsx`
  - [x] 2.2: Display contradictions count with link to Verification tab
  - [x] 2.3: Display citation issues count with link to Citations tab
  - [x] 2.4: Display timeline gaps with link to Timeline tab
  - [x] 2.5: Add "Review All" link navigating to Verification tab
  - [x] 2.6: Create `AttentionBanner.test.tsx` with comprehensive tests

- [x] Task 3: Create Parties Section component (AC: #3)
  - [x] 3.1: Create `frontend/src/components/features/summary/PartiesSection.tsx`
  - [x] 3.2: Display Petitioner card with entity name and source link
  - [x] 3.3: Display Respondent card with entity name and source link
  - [x] 3.4: Add "View Entity" button that navigates to Entities tab with entity selected
  - [x] 3.5: Add inline verification button [Verify]
  - [x] 3.6: Create `PartiesSection.test.tsx`

- [x] Task 4: Create Subject Matter section (AC: #1)
  - [x] 4.1: Create `frontend/src/components/features/summary/SubjectMatterSection.tsx`
  - [x] 4.2: Display AI-generated subject matter description
  - [x] 4.3: Add source citations with page references
  - [x] 4.4: Add "View Sources" link to open PDF viewer
  - [x] 4.5: Add inline verification button [Verify]
  - [x] 4.6: Create `SubjectMatterSection.test.tsx`

- [x] Task 5: Create Current Status section (AC: #1)
  - [x] 5.1: Create `frontend/src/components/features/summary/CurrentStatusSection.tsx`
  - [x] 5.2: Display last order date and description
  - [x] 5.3: Add source document link with page reference
  - [x] 5.4: Add "View Full Order" link to open PDF viewer
  - [x] 5.5: Add inline verification button [Verify]
  - [x] 5.6: Create `CurrentStatusSection.test.tsx`

- [x] Task 6: Create Key Issues section (AC: #1)
  - [x] 6.1: Create `frontend/src/components/features/summary/KeyIssuesSection.tsx`
  - [x] 6.2: Display numbered list of key issues
  - [x] 6.3: Show verification status badges (Verified, Pending, Flagged)
  - [x] 6.4: Create `KeyIssuesSection.test.tsx`

- [x] Task 7: Create Matter Statistics component (AC: #4)
  - [x] 7.1: Create `frontend/src/components/features/summary/MatterStatistics.tsx`
  - [x] 7.2: Display stat cards: total pages, entities found, events extracted, citations found
  - [x] 7.3: Add verification progress bar with percentage
  - [x] 7.4: Create `MatterStatistics.test.tsx`

- [x] Task 8: Create Summary types and API hooks (AC: All)
  - [x] 8.1: Create `frontend/src/types/summary.ts` with all type definitions
  - [x] 8.2: Create `frontend/src/hooks/useMatterSummary.ts` with SWR hook
  - [x] 8.3: Define mock data for MVP (actual summary generation is Phase 2)

- [x] Task 9: Create barrel exports and integrate (AC: All)
  - [x] 9.1: Create `frontend/src/components/features/summary/index.ts` barrel export
  - [x] 9.2: Export types from `frontend/src/types/index.ts`
  - [x] 9.3: Export hooks from `frontend/src/hooks/index.ts`

- [x] Task 10: Write comprehensive tests (AC: All)
  - [x] 10.1: Test Summary page rendering with mock data
  - [x] 10.2: Test attention banner with various item counts (0, 1, many)
  - [x] 10.3: Test parties section navigation to Entities tab
  - [x] 10.4: Test statistics cards display correctly
  - [x] 10.5: Test loading skeleton state
  - [x] 10.6: Test error state display
  - [x] 10.7: Test verification button interactions

## Dev Notes

### Critical Architecture Patterns

**Summary Tab Data Structure (from UX-Decisions-Log.md Section 6):**

The Summary tab displays the following sections in order:
1. Attention Banner - Issues needing action
2. Parties - Petitioner, Respondent with entity links
3. Subject Matter - What the case is about
4. Current Status - Last order, next steps
5. Key Issues - Numbered list with verification status
6. Matter Statistics - Pages, entities, events, citations counts

**Component Structure:**
```
frontend/src/
├── app/(matter)/[matterId]/summary/
│   └── page.tsx                          # UPDATE - Replace placeholder
├── components/features/summary/          # NEW - Summary tab components
│   ├── AttentionBanner.tsx               # NEW
│   ├── AttentionBanner.test.tsx          # NEW
│   ├── PartiesSection.tsx                # NEW
│   ├── PartiesSection.test.tsx           # NEW
│   ├── SubjectMatterSection.tsx          # NEW
│   ├── SubjectMatterSection.test.tsx     # NEW
│   ├── CurrentStatusSection.tsx          # NEW
│   ├── CurrentStatusSection.test.tsx     # NEW
│   ├── KeyIssuesSection.tsx              # NEW
│   ├── KeyIssuesSection.test.tsx         # NEW
│   ├── MatterStatistics.tsx              # NEW
│   ├── MatterStatistics.test.tsx         # NEW
│   └── index.ts                          # NEW - Barrel export
├── types/
│   ├── summary.ts                        # NEW - Summary type definitions
│   └── index.ts                          # UPDATE - Add summary exports
└── hooks/
    ├── useMatterSummary.ts               # NEW - Summary data hook
    └── index.ts                          # UPDATE - Add hook export
```

### TypeScript Type Definitions

```typescript
// types/summary.ts

export interface AttentionItem {
  type: 'contradiction' | 'citation_issue' | 'timeline_gap';
  count: number;
  label: string;
  targetTab: string; // Tab to navigate to
}

export interface PartyInfo {
  entityId: string;
  entityName: string;
  role: 'petitioner' | 'respondent' | 'other';
  sourceDocument: string;
  sourcePage: number;
  isVerified: boolean;
}

export interface SubjectMatter {
  description: string;
  sources: Array<{
    documentName: string;
    pageRange: string;
  }>;
  isVerified: boolean;
}

export interface CurrentStatus {
  lastOrderDate: string; // ISO date
  description: string;
  sourceDocument: string;
  sourcePage: number;
  isVerified: boolean;
}

export interface KeyIssue {
  id: string;
  number: number;
  title: string;
  verificationStatus: 'verified' | 'pending' | 'flagged';
}

export interface MatterStats {
  totalPages: number;
  entitiesFound: number;
  eventsExtracted: number;
  citationsFound: number;
  verificationPercent: number;
}

export interface MatterSummary {
  matterId: string;
  attentionItems: AttentionItem[];
  parties: PartyInfo[];
  subjectMatter: SubjectMatter;
  currentStatus: CurrentStatus;
  keyIssues: KeyIssue[];
  stats: MatterStats;
  generatedAt: string; // ISO timestamp
}
```

### Data Fetching Pattern (SWR)

```typescript
// hooks/useMatterSummary.ts
import useSWR from 'swr';
import type { MatterSummary } from '@/types/summary';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function useMatterSummary(matterId: string) {
  const { data, error, isLoading, mutate } = useSWR<{ data: MatterSummary }>(
    matterId ? `/api/matters/${matterId}/summary` : null,
    fetcher
  );

  return {
    summary: data?.data,
    isLoading,
    isError: !!error,
    mutate,
  };
}
```

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `Card`, `CardHeader`, `CardContent` - for stat cards and sections
- `Badge` - for verification status indicators
- `Button` - for action buttons and links
- `Skeleton` - for loading states
- `Alert`, `AlertTitle`, `AlertDescription` - for attention banner

**Use lucide-react icons:**
- `AlertTriangle` - attention banner icon
- `User` / `Users` - parties section
- `FileText` - subject matter
- `Calendar` - current status date
- `CheckCircle2` - verified status
- `Clock` - pending status
- `Flag` - flagged status
- `FileStack` - total pages stat
- `UserCircle` - entities stat
- `CalendarDays` - events stat
- `Quote` - citations stat
- `ExternalLink` - view source links

### Navigation Patterns

**Tab navigation using workspaceStore:**
```typescript
import { useWorkspaceStore } from '@/stores/workspaceStore';

// Navigate to Entities tab with entity pre-selected
const handleViewEntity = (entityId: string) => {
  const setActiveTab = useWorkspaceStore.getState().setActiveTab;
  setActiveTab('entities');
  // TODO: Set selected entity in entities store when created in Epic 10C
};

// Navigate to Verification tab
const handleReviewAll = () => {
  const setActiveTab = useWorkspaceStore.getState().setActiveTab;
  setActiveTab('verification');
};
```

### Backend API Notes

**API does NOT exist yet - use mock data for MVP:**

The Summary API (`GET /api/matters/{matterId}/summary`) will be implemented in a later story. For this MVP:
1. Create mock data that matches the type structure
2. Use the mock data in the useMatterSummary hook
3. Add a TODO comment noting API integration needed

**Mock Data Pattern:**
```typescript
// hooks/useMatterSummary.ts - MVP mock implementation
const MOCK_SUMMARY: MatterSummary = {
  matterId: '', // Will be set from param
  attentionItems: [
    { type: 'contradiction', count: 3, label: 'contradictions detected', targetTab: 'verification' },
    { type: 'citation_issue', count: 2, label: 'citations need verification', targetTab: 'citations' },
  ],
  parties: [
    { entityId: 'mock-1', entityName: 'Nirav D. Jobalia', role: 'petitioner', sourceDocument: 'Petition.pdf', sourcePage: 1, isVerified: false },
    { entityId: 'mock-2', entityName: 'The Custodian', role: 'respondent', sourceDocument: 'Petition.pdf', sourcePage: 2, isVerified: false },
  ],
  // ... etc
};
```

### Zustand Store Pattern (MANDATORY)

```typescript
// CORRECT - Selector pattern
const activeTab = useWorkspaceStore((state) => state.activeTab);
const setActiveTab = useWorkspaceStore((state) => state.setActiveTab);

// WRONG - Full store subscription
const { activeTab, setActiveTab } = useWorkspaceStore();
```

### Naming Conventions (from project-context.md)

| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `AttentionBanner`, `PartiesSection` |
| Component files | PascalCase.tsx | `AttentionBanner.tsx` |
| Hooks | camelCase with `use` prefix | `useMatterSummary` |
| Functions | camelCase | `handleViewEntity`, `handleReviewAll` |
| Constants | SCREAMING_SNAKE | `DEFAULT_ATTENTION_ITEMS` |
| Types/Interfaces | PascalCase | `MatterSummary`, `PartyInfo` |

### Accessibility Requirements

- All sections have appropriate heading hierarchy (h2 for section titles)
- Stat cards are semantic with proper ARIA labels
- Navigation links announce destination
- Verification status badges have accessible names
- Tab panel has `role="tabpanel"` with `aria-labelledby="tab-summary"`

### Previous Story Intelligence (Story 10A.3)

**From Story 10A.3 implementation:**
- Tab content renders inside `WorkspaceContentArea` with Q&A panel
- Each tab page is a separate Next.js route under `app/(matter)/[matterId]/`
- Tab pages receive `matterId` from params (async in Next.js 16)
- Use container with `py-8` padding for consistent spacing
- Tests use `render()` from `@testing-library/react` with mock providers

**Patterns established:**
- Comprehensive test coverage for all new components
- Co-located test files (ComponentName.test.tsx)
- Use of Zustand selector pattern throughout
- Mock implementations for APIs not yet built
- Barrel exports from index.ts files

### Git Commit Context (Recent Relevant Commits)

```
c961683 fix(review): code review fixes for Story 10A.3
08d7d14 feat(workspace): implement Q&A panel integration (Story 10A.3)
02d261a fix(review): code review fixes for Story 10A.2
ba592a7 feat(workspace): implement tab bar navigation (Story 10A.2)
```

**Patterns to follow:**
- Commit message format: `feat(summary): implement summary tab content (Story 10B.1)`
- Code review identifies HIGH/MEDIUM issues to fix
- Test files co-located with components

### Existing Code to Reuse

**From Epic 10A components:**
- `frontend/src/components/features/matter/WorkspaceHeader.tsx` - Header styling patterns
- `frontend/src/components/features/matter/WorkspaceTabBar.tsx` - Tab navigation patterns
- `frontend/src/stores/workspaceStore.ts` - Tab state management

**Entity model (from backend):**
- `backend/app/models/entity.py` - EntityType enum (PERSON, ORG, INSTITUTION, ASSET)
- Parties are entities with metadata.roles including 'petitioner', 'respondent'

**Verification model (from backend):**
- `backend/app/models/verification.py` - VerificationDecision enum (pending, approved, rejected, flagged)
- Use similar badge styling for verification status

### Testing Considerations

**Test file structure:**
```typescript
describe('AttentionBanner', () => {
  it('renders nothing when no attention items', () => {});
  it('displays contradiction count with correct link', () => {});
  it('displays citation issues count with correct link', () => {});
  it('shows "Review All" button linking to verification tab', () => {});
  it('handles click on item to navigate to target tab', () => {});
});

describe('PartiesSection', () => {
  it('renders petitioner card with entity name', () => {});
  it('renders respondent card with entity name', () => {});
  it('shows source document and page number', () => {});
  it('navigates to entities tab when clicking View Entity', () => {});
  it('shows verification button on each party card', () => {});
});

describe('MatterStatistics', () => {
  it('renders all four stat cards', () => {});
  it('displays correct counts in each card', () => {});
  it('shows verification progress bar with percentage', () => {});
  it('handles zero values gracefully', () => {});
});
```

### Project Structure Notes

**File Locations (MANDATORY):**
- Summary components go in `components/features/summary/` (NOT `components/summary/`)
- Types go in `types/summary.ts` (NOT inline in components)
- Hooks go in `hooks/useMatterSummary.ts` (NOT in component files)
- Tests are co-located: `ComponentName.test.tsx` next to `ComponentName.tsx`

### Error Handling

**Loading State:**
```tsx
if (isLoading) {
  return <SummarySkeleton />;
}
```

**Error State:**
```tsx
if (isError) {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        Failed to load summary data. Please try refreshing the page.
      </AlertDescription>
    </Alert>
  );
}
```

### References

- [Source: epics.md#story-10b1 - Acceptance criteria]
- [Source: UX-Decisions-Log.md#section-6 - Summary Tab wireframe and sections]
- [Source: architecture.md#frontend-structure - Component organization]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: Story 10A.3 - Tab page patterns]
- [Source: backend/app/models/entity.py - Entity types for parties]
- [Source: backend/app/models/verification.py - Verification status enum]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation completed without blocking issues.

### Completion Notes List

- Implemented complete Summary Tab with all 6 sections (AttentionBanner, PartiesSection, SubjectMatterSection, CurrentStatusSection, KeyIssuesSection, MatterStatistics)
- Created comprehensive TypeScript type definitions in `types/summary.ts`
- Created SWR-based data hook with mock data for MVP (`useMatterSummary`)
- Added shadcn/ui Alert component (was missing from project)
- All 96 component tests passing
- All 1266 total frontend tests passing
- Lint passes with zero warnings
- Uses Next.js Link for tab navigation (not Zustand store action)
- Navigation pattern uses proper Next.js routing via Link components
- Installed `swr` package for data fetching
- All sections have proper accessibility (aria-labelledby, role="tabpanel")

### File List

**New Files:**
- frontend/src/types/summary.ts
- frontend/src/hooks/useMatterSummary.ts
- frontend/src/components/ui/alert.tsx
- frontend/src/components/features/summary/AttentionBanner.tsx
- frontend/src/components/features/summary/AttentionBanner.test.tsx
- frontend/src/components/features/summary/PartiesSection.tsx
- frontend/src/components/features/summary/PartiesSection.test.tsx
- frontend/src/components/features/summary/SubjectMatterSection.tsx
- frontend/src/components/features/summary/SubjectMatterSection.test.tsx
- frontend/src/components/features/summary/CurrentStatusSection.tsx
- frontend/src/components/features/summary/CurrentStatusSection.test.tsx
- frontend/src/components/features/summary/KeyIssuesSection.tsx
- frontend/src/components/features/summary/KeyIssuesSection.test.tsx
- frontend/src/components/features/summary/MatterStatistics.tsx
- frontend/src/components/features/summary/MatterStatistics.test.tsx
- frontend/src/components/features/summary/SummaryContent.tsx
- frontend/src/components/features/summary/SummaryContent.test.tsx
- frontend/src/components/features/summary/index.ts

**Modified Files:**
- frontend/src/app/(matter)/[matterId]/summary/page.tsx
- frontend/src/types/index.ts
- frontend/src/hooks/index.ts
- frontend/package.json (added swr dependency)
- frontend/package-lock.json

## Change Log

- 2026-01-15: Story implementation complete - all tasks completed, 96 tests passing, ready for code review
