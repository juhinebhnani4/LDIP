# Story 9.3: Implement Activity Feed and Quick Stats

Status: review

## Story

As an **attorney**,
I want **to see recent activity and summary statistics**,
So that **I know what's happening across my matters**.

## Acceptance Criteria

1. **Given** I view the dashboard
   **When** activity feed loads (30% of viewport width)
   **Then** I see recent activities with icon-coded entries
   **And** colors indicate: green=success, blue=info, yellow=in progress, orange=attention, red=error

2. **Given** activity entries exist
   **When** I view them
   **Then** each shows: icon, matter name, action description, timestamp
   **And** clicking an entry navigates to the relevant matter/tab

3. **Given** I view quick stats panel
   **When** it loads
   **Then** I see: active matters count, verified findings count, pending reviews count
   **And** stats update in real-time

## Tasks / Subtasks

- [x] Task 1: Create ActivityFeed component (AC: #1, #2)
  - [x] 1.1: Create `frontend/src/components/features/dashboard/ActivityFeed.tsx`
  - [x] 1.2: Implement activity list with icon-coded entries
  - [x] 1.3: Add activity type icons using lucide-react (CheckCircle2, Info, Clock, AlertTriangle, XCircle)
  - [x] 1.4: Implement color coding per activity type (success=green, info=blue, progress=yellow, attention=orange, error=red)
  - [x] 1.5: Add timestamp formatting with relative time (e.g., "2 hours ago")
  - [x] 1.6: Make entries clickable with navigation to relevant matter/tab

- [x] Task 2: Create ActivityFeedItem component (AC: #1, #2)
  - [x] 2.1: Create `frontend/src/components/features/dashboard/ActivityFeedItem.tsx`
  - [x] 2.2: Display activity icon with appropriate color
  - [x] 2.3: Display matter name (linked) and action description
  - [x] 2.4: Display formatted timestamp
  - [x] 2.5: Add hover state with subtle background highlight

- [x] Task 3: Create QuickStats component (AC: #3)
  - [x] 3.1: Create `frontend/src/components/features/dashboard/QuickStats.tsx`
  - [x] 3.2: Display active matters count with folder icon
  - [x] 3.3: Display verified findings count with check icon
  - [x] 3.4: Display pending reviews count with clock icon
  - [x] 3.5: Add loading skeleton state

- [x] Task 4: Create activityStore (AC: #1, #2, #3)
  - [x] 4.1: Create `frontend/src/stores/activityStore.ts` using Zustand
  - [x] 4.2: Implement state: activities, isLoading, error, stats
  - [x] 4.3: Implement actions: fetchActivities, fetchStats, markActivityRead
  - [x] 4.4: Implement selectors for recent activities (limit 10)
  - [x] 4.5: Use mock data initially (backend API not available yet)

- [x] Task 5: Define activity types (AC: #1, #2)
  - [x] 5.1: Add to `frontend/src/types/activity.ts`:
    - `ActivityType` enum: 'processing_complete' | 'verification_needed' | 'processing_started' | 'matter_opened' | 'contradictions_found' | 'processing_failed'
    - `Activity` interface with id, matterId, matterName, type, description, timestamp, isRead
    - `ActivityIconConfig` type mapping activity types to icons and colors
  - [x] 5.2: Add `DashboardStats` interface with activeMatters, verifiedFindings, pendingReviews

- [x] Task 6: Update dashboard page layout (AC: #1, #3)
  - [x] 6.1: Replace placeholder content in `frontend/src/app/(dashboard)/page.tsx`
  - [x] 6.2: Import and render ActivityFeed component
  - [x] 6.3: Import and render QuickStats component
  - [x] 6.4: Maintain 30% width for right sidebar (already set)

- [x] Task 7: Add relative time utility (AC: #2)
  - [x] 7.1: Create `frontend/src/utils/formatRelativeTime.ts`
  - [x] 7.2: Implement relative time formatting (now, minutes ago, hours ago, yesterday, date)
  - [x] 7.3: Use existing date-fns library if available, otherwise implement manually

- [x] Task 8: Write tests (All ACs)
  - [x] 8.1: Create `ActivityFeed.test.tsx` - renders activities, clicking navigates
  - [x] 8.2: Create `ActivityFeedItem.test.tsx` - displays correct icons/colors/timestamps
  - [x] 8.3: Create `QuickStats.test.tsx` - displays stats, shows loading state
  - [x] 8.4: Create `activityStore.test.ts` - store actions and selectors work
  - [x] 8.5: Create `formatRelativeTime.test.ts` - time formatting is correct

- [x] Task 9: Update dashboard component exports (All ACs)
  - [x] 9.1: Update `frontend/src/components/features/dashboard/index.ts` to export new components

## Dev Notes

### Critical Architecture Patterns

**UI Component Requirements:**
- Use shadcn/ui components: `Card`, `CardHeader`, `CardTitle`, `CardContent`, `Skeleton`
- Follow component structure: `frontend/src/components/features/dashboard/`
- Co-locate tests: `ComponentName.test.tsx` in same directory
- Use lucide-react for icons (consistent with 9-1 and 9-2)

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const activities = useActivityStore((state) => state.activities);
const isLoading = useActivityStore((state) => state.isLoading);
const fetchActivities = useActivityStore((state) => state.fetchActivities);

// WRONG - Full store subscription (causes re-renders)
const { activities, isLoading, fetchActivities } = useActivityStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions:**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `ActivityFeed`, `QuickStats` |
| Component files | PascalCase.tsx | `ActivityFeed.tsx` |
| Variables | camelCase | `isLoading`, `activities` |
| Functions | camelCase | `fetchActivities`, `formatRelativeTime` |
| Constants | SCREAMING_SNAKE | `ACTIVITY_TYPES`, `ACTIVITY_ICONS` |

### UX Design Reference

From UX-Decisions-Log.md wireframes:

**Dashboard Layout (70/30 split):**
```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER (from Story 9-1)                                        │
├─────────────────────────────────────────┬───────────────────────┤
│                                         │                       │
│  Welcome, Juhi                          │  ACTIVITY FEED        │
│  [+ New Matter]                         │  (THIS STORY)         │
│                                         │                       │
│  ┌────────────┐  ┌────────────┐         │  Recent activity...   │
│  │  Matter 1  │  │  Matter 2  │         │                       │
│  │  Ready     │  │Processing  │         ├───────────────────────┤
│  │  892 pgs   │  │  67%       │         │  QUICK STATS          │
│  │[Resume →]  │  │[Progress →]│         │  (THIS STORY)         │
│  └────────────┘  └────────────┘         │                       │
│                                         │  📁 5 Active Matters  │
│  ┌────────────┐                         │  ✓ 127 Verified       │
│  │  + New     │                         │  ⏳ 3 Pending         │
│  │  Matter    │                         │                       │
│  └────────────┘                         │                       │
│  (70% width - Story 9-2)                │  (30% width - 9-3)    │
└─────────────────────────────────────────┴───────────────────────┘
```

**Activity Feed Wireframe:**
```
┌────────────────────────────┐
│  ACTIVITY FEED             │
│                            │
│  Today                     │
│  ─────                     │
│  • 8:02 AM                 │
│    🟢 Shah v. Mehta        │
│    Processing complete ✓   │
│                            │
│  • 7:45 AM                 │
│    🔵 SEBI v. Parekh       │
│    Matter opened           │
│                            │
│  Yesterday                 │
│  ─────────                 │
│  • 6:15 PM                 │
│    🟠 Custody Dispute      │
│    3 contradictions found  │
│                            │
│  • 2:30 PM                 │
│    🟡 Tax Matter           │
│    Processing started      │
│                            │
│  [View All Activity →]     │
└────────────────────────────┘
```

**Quick Stats Wireframe:**
```
┌────────────────────────────┐
│  QUICK STATS               │
│                            │
│  📁 5 Active Matters       │
│                            │
│  ✓ 127 Verified Findings   │
│                            │
│  ⏳ 3 Pending Reviews      │
│                            │
└────────────────────────────┘
```

**Activity Types and Colors:**
| Icon | Type | Color | Example |
|------|------|-------|---------|
| 🟢 (CheckCircle2) | Success | green-500 | Processing complete, verification done |
| 🔵 (Info) | Info | blue-500 | Login, opened matter |
| 🟡 (Clock) | In progress | yellow-500 | Upload started, processing |
| 🟠 (AlertTriangle) | Attention needed | orange-500 | Contradictions found, low confidence |
| 🔴 (XCircle) | Error | red-500 | Processing failed, upload error |

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── components/features/dashboard/    # This story
│   ├── DashboardHeader.tsx           # (9-1 - exists)
│   ├── MatterCard.tsx                # (9-2 - exists)
│   ├── MatterCardsGrid.tsx           # (9-2 - exists)
│   ├── ActivityFeed.tsx              # NEW
│   ├── ActivityFeed.test.tsx         # NEW
│   ├── ActivityFeedItem.tsx          # NEW
│   ├── ActivityFeedItem.test.tsx     # NEW
│   ├── QuickStats.tsx                # NEW
│   ├── QuickStats.test.tsx           # NEW
│   └── index.ts                      # UPDATE - add exports
├── stores/
│   ├── matterStore.ts                # (9-2 - exists)
│   ├── notificationStore.ts          # (9-1 - exists)
│   ├── activityStore.ts              # NEW
│   └── activityStore.test.ts         # NEW
├── types/
│   └── activity.ts                   # NEW
└── utils/
    ├── formatRelativeTime.ts         # NEW
    └── formatRelativeTime.test.ts    # NEW
```

**Existing Components to Use:**
- `frontend/src/components/ui/card.tsx` - Card primitives
- `frontend/src/components/ui/skeleton.tsx` - Loading states
- Icons from `lucide-react`: CheckCircle2, Info, Clock, AlertTriangle, XCircle, Folder, FileCheck, Timer

**Existing Patterns to Follow:**
- `frontend/src/stores/matterStore.ts` - Zustand store structure (from 9-2)
- `frontend/src/stores/notificationStore.ts` - Zustand store structure (from 9-1)
- `frontend/src/components/features/dashboard/MatterCard.tsx` - Component structure
- `frontend/src/types/matter.ts` - TypeScript types structure

### Backend API Integration

**No backend API exists yet for activities/stats.** For MVP, implement with mock data similar to 9-1 and 9-2 approach.

**Frontend Types for Future Backend:**
```typescript
// Activity type for frontend (mock for now)
interface Activity {
  id: string;
  matterId: string;
  matterName: string;
  type: ActivityType;
  description: string;
  timestamp: string; // ISO date string
  isRead: boolean;
}

type ActivityType =
  | 'processing_complete'
  | 'verification_needed'
  | 'processing_started'
  | 'matter_opened'
  | 'contradictions_found'
  | 'processing_failed';

// Dashboard stats type (mock for now)
interface DashboardStats {
  activeMatters: number;
  verifiedFindings: number;
  pendingReviews: number;
}
```

**Future API Endpoints (not implemented yet):**
- `GET /api/activities?limit=10` - Returns recent activities
- `GET /api/stats/dashboard` - Returns dashboard stats
- `PATCH /api/activities/{id}/read` - Mark activity as read

### Previous Story Intelligence (9-1 and 9-2)

**From Story 9-1 implementation:**
- DashboardHeader component successfully created with LDIP logo, search, notifications, user dropdown
- NotificationsDropdown uses mock data (backend API not yet available)
- GlobalSearch uses mock data (backend API not yet available)
- Zustand store pattern followed correctly with selectors
- Tests co-located with components (48 tests)
- Code review found: unused imports, console.log in production, missing Next.js Link component

**From Story 9-2 implementation:**
- MatterCard, MatterCardsGrid, ViewToggle, MatterFilters all created
- matterStore uses Zustand with selector pattern
- Mock data extracted to `frontend/src/stores/__mocks__/matterData.ts`
- Error boundary implemented for card-level failures
- useShallow from zustand/react/shallow for memoization
- All 496 tests pass including 74 new tests

**Key Learnings to Apply:**
1. Use mock data initially - design interfaces for future backend integration
2. Follow selector pattern strictly for Zustand stores
3. Remove unused imports before committing
4. Use Next.js `<Link>` component for internal navigation, not `<a>` tags
5. No console.log in production code
6. Add useShallow for computed selectors if needed
7. Extract mock data to separate file with TODO for backend integration
8. Add error boundaries where component failures should be isolated

### Accessibility Requirements

From UX-Decisions-Log.md:
- Activity items should be focusable and navigable via keyboard
- Use semantic HTML (`<ul>`, `<li>`) for activity list
- Icons should have appropriate `aria-label` or be decorative (`aria-hidden`)
- Color coding should not be the only indicator (include text labels)
- Stats cards should have accessible labels

### Performance Considerations

- Keep activity feed lightweight (max 10 items displayed)
- Lazy load additional activities on "View All" click
- Use skeleton loading for both ActivityFeed and QuickStats
- Cache stats in store with reasonable staleness (30 seconds)
- Use `useMemo` for computed values if needed

### References

- [UX Wireframe](../_bmad-output/project-planning-artifacts/UX-Decisions-Log.md#3-dashboard--home)
- [Previous Story 9-1](../_bmad-output/implementation-artifacts/9-1-dashboard-header.md)
- [Previous Story 9-2](../_bmad-output/implementation-artifacts/9-2-matter-cards-grid.md)
- [Architecture Naming](../_bmad-output/architecture.md)
- [Project Context](../_bmad-output/project-context.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

1. **All 610 tests pass** (including 86 new tests for this story)
2. **Lint passes** for all new files
3. **Mock data pattern** - Activities and stats use mock data following 9-1 and 9-2 patterns, with TODO comments for backend integration
4. **Zustand selector pattern** - Used MANDATORY selector pattern from project-context.md
5. **TypeScript strict mode** - No `any` types used, all types properly defined
6. **Accessibility** - Semantic HTML, aria-labels, keyboard navigation, color not sole indicator
7. **Performance** - 30-second cache for stats, max 10 activities displayed, skeleton loading states
8. **Component structure** - Followed existing patterns from MatterCard.tsx and notificationStore.ts
9. **Activities grouped by day** - Today, Yesterday, weekday names, then formatted dates

### File List

**New Files Created:**
- `frontend/src/types/activity.ts` - Activity types and interfaces
- `frontend/src/utils/formatRelativeTime.ts` - Relative time formatting utility
- `frontend/src/utils/formatRelativeTime.test.ts` - Tests for relative time utility
- `frontend/src/stores/activityStore.ts` - Zustand store for activities and stats
- `frontend/src/stores/activityStore.test.ts` - Tests for activity store
- `frontend/src/components/features/dashboard/ActivityFeedItem.tsx` - Individual activity item component
- `frontend/src/components/features/dashboard/ActivityFeedItem.test.tsx` - Tests for ActivityFeedItem
- `frontend/src/components/features/dashboard/ActivityFeed.tsx` - Activity feed component with day grouping
- `frontend/src/components/features/dashboard/ActivityFeed.test.tsx` - Tests for ActivityFeed
- `frontend/src/components/features/dashboard/QuickStats.tsx` - Quick stats component
- `frontend/src/components/features/dashboard/QuickStats.test.tsx` - Tests for QuickStats
- `frontend/src/app/(dashboard)/DashboardSidebar.tsx` - Client component wrapper for sidebar

**Modified Files:**
- `frontend/src/components/features/dashboard/index.ts` - Added exports for new components
- `frontend/src/app/(dashboard)/page.tsx` - Replaced placeholder with DashboardSidebar component
