# Story 10A.2: Implement Tab Bar Navigation

Status: review

## Story

As an **attorney**,
I want **tabs to navigate between different analysis views**,
So that **I can switch between timeline, entities, citations, etc.**.

## Acceptance Criteria

1. **Given** I am in the workspace
   **When** the tab bar loads
   **Then** tabs appear in order: Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents

2. **Given** I click a tab
   **When** the tab activates
   **Then** the main content area updates to show that tab's content
   **And** the URL updates to reflect the active tab

3. **Given** findings need attention
   **When** the tab bar renders
   **Then** affected tabs show a badge with count (e.g., Citations (3))
   **And** the badge indicates issues to review

4. **Given** documents are still processing (from Story 2C.3 AC#5)
   **When** the tab bar renders
   **Then** tabs show what's ready vs. still processing (e.g., "Timeline (12 events)" vs. "Entities (processing...)")
   **And** loading placeholders appear for tabs still receiving data

## Tasks / Subtasks

- [x] Task 1: Create WorkspaceTabBar component (AC: #1)
  - [x] 1.1: Create `frontend/src/components/features/matter/WorkspaceTabBar.tsx`
  - [x] 1.2: Define TAB_CONFIG constant with tab order: summary, timeline, entities, citations, contradictions, verification, documents
  - [x] 1.3: Use Next.js `usePathname` and `useParams` for active tab detection
  - [x] 1.4: Implement horizontal scrollable tab bar for smaller screens
  - [x] 1.5: Use shadcn/ui styling patterns (consistent with existing components)
  - [x] 1.6: Add keyboard navigation support (arrow keys to navigate between tabs)

- [x] Task 2: Implement URL-based tab routing (AC: #2)
  - [x] 2.1: Create route structure: `/matters/[matterId]/[tab]` where tab is: summary, timeline, entities, citations, contradictions, verification, documents
  - [x] 2.2: Add default redirect from `/matters/[matterId]` to `/matters/[matterId]/summary`
  - [x] 2.3: Create placeholder page for each tab route (will be implemented in Epic 10B-10D)
  - [x] 2.4: Ensure Next.js Link component for client-side navigation (no full page reload)
  - [x] 2.5: Update matter layout to include WorkspaceTabBar below WorkspaceHeader

- [x] Task 3: Implement tab badges for attention counts (AC: #3)
  - [x] 3.1: Create `TabBadge` component or integrate with existing shadcn Badge
  - [x] 3.2: Define `TabCounts` interface: `{ unverifiedCount: number; issueCount: number; processingCount: number }`
  - [x] 3.3: Add badge display logic: show badge if count > 0
  - [x] 3.4: Style badge as small pill with destructive variant for issues, default for counts
  - [x] 3.5: Mock tab counts from store for MVP (will connect to real API later)

- [x] Task 4: Implement processing status indicators (AC: #4)
  - [x] 4.1: Create `TabStatusIndicator` component for showing ready vs. processing state
  - [x] 4.2: Define status modes: 'ready' (shows count), 'processing' (shows spinner + "processing...")
  - [x] 4.3: Add `Loader2` icon with `animate-spin` for processing tabs
  - [x] 4.4: Show item count when ready: "Timeline (12 events)", "Entities (24)"
  - [x] 4.5: Integrate with `processingStore` or `matterStore` for processing state

- [x] Task 5: Create tab content placeholder pages (AC: #2)
  - [x] 5.1: Create `frontend/src/app/(matter)/[matterId]/summary/page.tsx` - Placeholder
  - [x] 5.2: Create `frontend/src/app/(matter)/[matterId]/timeline/page.tsx` - Placeholder
  - [x] 5.3: Create `frontend/src/app/(matter)/[matterId]/entities/page.tsx` - Placeholder
  - [x] 5.4: Create `frontend/src/app/(matter)/[matterId]/citations/page.tsx` - Placeholder
  - [x] 5.5: Create `frontend/src/app/(matter)/[matterId]/contradictions/page.tsx` - Placeholder
  - [x] 5.6: Create `frontend/src/app/(matter)/[matterId]/verification/page.tsx` - Placeholder (existing, kept)
  - [x] 5.7: Create `frontend/src/app/(matter)/[matterId]/documents/page.tsx` - Placeholder
  - [x] 5.8: Each placeholder shows tab name and "Coming in Epic 10B/10C/10D" message

- [x] Task 6: Update matter layout integration (AC: #1, #2)
  - [x] 6.1: Modify `frontend/src/app/(matter)/[matterId]/layout.tsx` to include WorkspaceTabBar
  - [x] 6.2: Position tab bar below WorkspaceHeader, above main content
  - [x] 6.3: Ensure tab bar is sticky below header for scrolling content
  - [x] 6.4: Pass matterId prop from route params to WorkspaceTabBar

- [x] Task 7: Create/update workspaceStore for tab state (AC: #3, #4)
  - [x] 7.1: Create `frontend/src/stores/workspaceStore.ts` for workspace-specific state
  - [x] 7.2: Add `tabCounts` state: `Record<TabId, { count: number; issueCount: number }>`
  - [x] 7.3: Add `tabProcessingStatus` state: `Record<TabId, 'ready' | 'processing'>`
  - [x] 7.4: Add `setTabCount`, `setTabProcessingStatus` actions
  - [x] 7.5: Add `fetchTabStats(matterId: string)` action (mock implementation for MVP)
  - [x] 7.6: Follow MANDATORY Zustand selector pattern

- [x] Task 8: Export new components (AC: All)
  - [x] 8.1: Update `frontend/src/components/features/matter/index.ts` to export WorkspaceTabBar
  - [x] 8.2: Export workspaceStore from stores index if exists

- [x] Task 9: Write comprehensive tests (AC: All)
  - [x] 9.1: Create `WorkspaceTabBar.test.tsx` - tab rendering, navigation, active state
  - [x] 9.2: Test badge display for attention counts
  - [x] 9.3: Test processing status indicators
  - [x] 9.4: Test keyboard navigation between tabs
  - [x] 9.5: Test URL synchronization with active tab
  - [x] 9.6: Test placeholder pages render correctly

## Dev Notes

### Critical Architecture Patterns

**Tab Configuration (CRITICAL - Exact Order Required):**
```typescript
// Tab IDs must match route segments exactly
export type TabId =
  | 'summary'
  | 'timeline'
  | 'entities'
  | 'citations'
  | 'contradictions'
  | 'verification'
  | 'documents';

// Tab configuration with labels and icons
export const TAB_CONFIG: Array<{
  id: TabId;
  label: string;
  icon: LucideIcon;
  epic: string; // Which epic implements this tab's content
}> = [
  { id: 'summary', label: 'Summary', icon: FileText, epic: 'Epic 10B' },
  { id: 'timeline', label: 'Timeline', icon: Clock, epic: 'Epic 10B' },
  { id: 'entities', label: 'Entities', icon: Users, epic: 'Epic 10C' },
  { id: 'citations', label: 'Citations', icon: Quote, epic: 'Epic 10C' },
  { id: 'contradictions', label: 'Contradictions', icon: AlertTriangle, epic: 'Epic 5' },
  { id: 'verification', label: 'Verification', icon: CheckCircle, epic: 'Epic 10D' },
  { id: 'documents', label: 'Documents', icon: FolderOpen, epic: 'Epic 10D' },
];
```

**Component Structure (from architecture.md):**
```
frontend/src/
├── app/(matter)/[matterId]/
│   ├── layout.tsx                    # UPDATE - Add WorkspaceTabBar
│   ├── page.tsx                      # UPDATE - Redirect to /summary
│   ├── summary/page.tsx              # NEW - Placeholder
│   ├── timeline/page.tsx             # NEW - Placeholder
│   ├── entities/page.tsx             # NEW - Placeholder
│   ├── citations/page.tsx            # NEW - Placeholder
│   ├── contradictions/page.tsx       # NEW - Placeholder
│   ├── verification/page.tsx         # NEW - Placeholder
│   └── documents/page.tsx            # NEW - Placeholder
├── components/features/matter/
│   ├── WorkspaceTabBar.tsx           # NEW - Main tab navigation
│   ├── WorkspaceTabBar.test.tsx      # NEW - Tab bar tests
│   └── index.ts                      # UPDATE - Add exports
└── stores/
    └── workspaceStore.ts             # NEW - Workspace state (tab counts, processing)
```

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const tabCounts = useWorkspaceStore((state) => state.tabCounts);
const tabProcessingStatus = useWorkspaceStore((state) => state.tabProcessingStatus);

// WRONG - Full store subscription (causes re-renders)
const { tabCounts, tabProcessingStatus, setTabCount } = useWorkspaceStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions (from project-context.md):**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `WorkspaceTabBar`, `TabBadge` |
| Component files | PascalCase.tsx | `WorkspaceTabBar.tsx` |
| Route segments | lowercase-kebab | `/matters/[matterId]/summary` |
| Functions | camelCase | `handleTabClick`, `getTabHref` |
| Constants | SCREAMING_SNAKE | `TAB_CONFIG`, `DEFAULT_TAB` |
| Types/Interfaces | PascalCase | `TabId`, `TabConfig`, `TabCounts` |

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` - Base tab primitives (BUT we use custom routing, not TabsContent)
- `Badge` - For count indicators
- `Button` - For tab triggers if needed
- `Tooltip` - For icon-only mode on small screens

**Use lucide-react icons:**
- `FileText` - Summary tab
- `Clock` - Timeline tab
- `Users` - Entities tab
- `Quote` - Citations tab
- `AlertTriangle` - Contradictions tab
- `CheckCircle` or `Shield` - Verification tab
- `FolderOpen` or `Files` - Documents tab
- `Loader2` - Processing spinner

### Tab Bar Layout Reference

```tsx
// WorkspaceTabBar layout pattern
<nav
  className="sticky top-14 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
  role="tablist"
  aria-label="Matter workspace navigation"
>
  <div className="container flex h-12 items-center overflow-x-auto">
    {TAB_CONFIG.map((tab) => (
      <Link
        key={tab.id}
        href={`/matters/${matterId}/${tab.id}`}
        role="tab"
        aria-selected={activeTab === tab.id}
        className={cn(
          "flex items-center gap-2 px-4 py-2 text-sm font-medium whitespace-nowrap",
          "border-b-2 -mb-[2px] transition-colors",
          activeTab === tab.id
            ? "border-primary text-foreground"
            : "border-transparent text-muted-foreground hover:text-foreground"
        )}
      >
        <tab.icon className="h-4 w-4" />
        <span>{tab.label}</span>
        {/* Badge for counts/processing */}
        <TabStatusIndicator
          tabId={tab.id}
          count={tabCounts[tab.id]?.count}
          issueCount={tabCounts[tab.id]?.issueCount}
          isProcessing={tabProcessingStatus[tab.id] === 'processing'}
        />
      </Link>
    ))}
  </div>
</nav>
```

### Tab Status Indicator Component Pattern

```tsx
interface TabStatusIndicatorProps {
  tabId: TabId;
  count?: number;
  issueCount?: number;
  isProcessing?: boolean;
}

function TabStatusIndicator({
  tabId,
  count,
  issueCount,
  isProcessing
}: TabStatusIndicatorProps) {
  // Processing state - show spinner
  if (isProcessing) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span className="sr-only">processing</span>
      </span>
    );
  }

  // Issue count - show destructive badge
  if (issueCount && issueCount > 0) {
    return (
      <Badge variant="destructive" className="h-5 px-1.5 text-xs">
        {issueCount}
      </Badge>
    );
  }

  // Regular count - show muted badge or inline count
  if (count !== undefined && count > 0) {
    return (
      <span className="text-xs text-muted-foreground">
        ({count})
      </span>
    );
  }

  return null;
}
```

### URL Routing Pattern

**Route Structure:**
```
/matters/[matterId]              → Redirects to /matters/[matterId]/summary
/matters/[matterId]/summary      → Summary tab content
/matters/[matterId]/timeline     → Timeline tab content
/matters/[matterId]/entities     → Entities tab content
/matters/[matterId]/citations    → Citations tab content
/matters/[matterId]/contradictions → Contradictions tab content
/matters/[matterId]/verification → Verification tab content
/matters/[matterId]/documents    → Documents tab content
```

**Active Tab Detection:**
```typescript
'use client';

import { usePathname, useParams } from 'next/navigation';

function WorkspaceTabBar() {
  const pathname = usePathname();
  const params = useParams();
  const matterId = params.matterId as string;

  // Extract active tab from pathname
  const activeTab = pathname.split('/').pop() as TabId || 'summary';

  // Validate it's a known tab
  const isValidTab = TAB_CONFIG.some(tab => tab.id === activeTab);
  const currentTab = isValidTab ? activeTab : 'summary';

  // ...
}
```

### Workspace Store Pattern

```typescript
// stores/workspaceStore.ts
import { create } from 'zustand';

interface TabStats {
  count: number;
  issueCount: number;
}

interface WorkspaceState {
  // Tab statistics
  tabCounts: Partial<Record<TabId, TabStats>>;
  tabProcessingStatus: Partial<Record<TabId, 'ready' | 'processing'>>;

  // Actions
  setTabStats: (tabId: TabId, stats: TabStats) => void;
  setTabProcessingStatus: (tabId: TabId, status: 'ready' | 'processing') => void;
  setAllTabStats: (stats: Partial<Record<TabId, TabStats>>) => void;
  fetchTabStats: (matterId: string) => Promise<void>;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  tabCounts: {},
  tabProcessingStatus: {},

  setTabStats: (tabId, stats) => set((state) => ({
    tabCounts: { ...state.tabCounts, [tabId]: stats }
  })),

  setTabProcessingStatus: (tabId, status) => set((state) => ({
    tabProcessingStatus: { ...state.tabProcessingStatus, [tabId]: status }
  })),

  setAllTabStats: (stats) => set({ tabCounts: stats }),

  fetchTabStats: async (matterId: string) => {
    // TODO: Replace with actual API call
    // GET /api/matters/{matter_id}/tab-stats

    // Mock data for MVP
    await new Promise(resolve => setTimeout(resolve, 300));

    set({
      tabCounts: {
        summary: { count: 1, issueCount: 0 },
        timeline: { count: 24, issueCount: 0 },
        entities: { count: 18, issueCount: 2 },
        citations: { count: 45, issueCount: 3 },
        contradictions: { count: 7, issueCount: 7 },
        verification: { count: 12, issueCount: 5 },
        documents: { count: 8, issueCount: 0 },
      },
      tabProcessingStatus: {
        summary: 'ready',
        timeline: 'ready',
        entities: 'ready',
        citations: 'ready',
        contradictions: 'ready',
        verification: 'ready',
        documents: 'ready',
      }
    });
  }
}));
```

### Placeholder Page Template

```tsx
// app/(matter)/[matterId]/summary/page.tsx
import { FileText } from 'lucide-react';

interface PageProps {
  params: Promise<{ matterId: string }>;
}

export default async function SummaryPage({ params }: PageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <FileText className="h-16 w-16 text-muted-foreground mb-4" />
        <h1 className="text-2xl font-semibold mb-2">Summary</h1>
        <p className="text-muted-foreground max-w-md">
          The Summary tab will show case overview, attention items, parties,
          subject matter, and key issues.
        </p>
        <p className="text-sm text-muted-foreground mt-4">
          Coming in Epic 10B
        </p>
        <p className="text-xs text-muted-foreground/70 mt-2">
          Matter ID: {matterId}
        </p>
      </div>
    </div>
  );
}
```

### Existing Code to Reference/Reuse

**WorkspaceHeader (pattern reference):**
- `frontend/src/components/features/matter/WorkspaceHeader.tsx` - Sticky header pattern, container class

**DashboardHeader (pattern reference):**
- `frontend/src/components/features/dashboard/DashboardHeader.tsx` - Header layout, styling

**Matter Layout (integration point):**
- `frontend/src/app/(matter)/[matterId]/layout.tsx` - Where WorkspaceTabBar will be added

**Stores:**
- `frontend/src/stores/matterStore.ts` - Store pattern reference
- `frontend/src/stores/notificationStore.ts` - Toast notifications pattern

**Types:**
- `frontend/src/types/matter.ts` - Matter type definitions
- `frontend/src/types/job.ts` - Processing status types (for tab processing indicators)

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── app/(matter)/[matterId]/
│   ├── layout.tsx                    # UPDATE - Add WorkspaceTabBar
│   ├── page.tsx                      # UPDATE - Redirect to /summary
│   ├── summary/
│   │   └── page.tsx                  # NEW
│   ├── timeline/
│   │   └── page.tsx                  # NEW
│   ├── entities/
│   │   └── page.tsx                  # NEW
│   ├── citations/
│   │   └── page.tsx                  # NEW
│   ├── contradictions/
│   │   └── page.tsx                  # NEW
│   ├── verification/
│   │   └── page.tsx                  # NEW
│   └── documents/
│       └── page.tsx                  # NEW
├── components/features/matter/
│   ├── WorkspaceTabBar.tsx           # NEW
│   ├── WorkspaceTabBar.test.tsx      # NEW
│   └── index.ts                      # UPDATE - Add exports
└── stores/
    └── workspaceStore.ts             # NEW
```

### Previous Story Intelligence (Story 10A.1)

**From Story 10A.1 implementation:**
- WorkspaceHeader uses sticky positioning with backdrop blur
- Header height is `h-14` - tab bar should position at `top-14`
- Container class provides proper max-width and centering
- Matter layout already has WorkspaceHeader integrated
- MatterWorkspaceWrapper continues to function for processing status

**Key patterns established:**
- Comprehensive test coverage for all new components
- Co-located test files (ComponentName.test.tsx)
- Use of Zustand selector pattern throughout
- Mock implementations for APIs not yet built

### Git Commit Context (Recent Relevant Commits)

```
79e7f0a fix(review): code review fixes for Story 10A.1
a6a6865 feat(workspace): implement workspace shell header (Story 10A.1)
b8529da fix(review): code review fixes for Story 9-6
689dc40 feat(upload): implement upload flow stage 5 completion (Story 9-6)
```

Recent patterns established:
- Stories in Epic 10A follow consistent component patterns
- Test files co-located with components
- Zustand selectors enforced throughout

### Testing Considerations

**WorkspaceTabBar tests:**
```typescript
describe('WorkspaceTabBar', () => {
  // Rendering tests (AC #1)
  it('renders all seven tabs in correct order', () => {});
  it('displays tab icons', () => {});
  it('displays tab labels', () => {});

  // Navigation tests (AC #2)
  it('highlights active tab based on URL', () => {});
  it('generates correct href for each tab', () => {});
  it('uses Next.js Link for client-side navigation', () => {});

  // Badge tests (AC #3)
  it('displays badge with issue count when > 0', () => {});
  it('hides badge when issue count is 0', () => {});
  it('uses destructive variant for issue badges', () => {});

  // Processing status tests (AC #4)
  it('displays spinner for processing tabs', () => {});
  it('displays count for ready tabs', () => {});
  it('shows "processing..." text for processing state', () => {});

  // Accessibility tests
  it('has proper ARIA roles (tablist, tab)', () => {});
  it('sets aria-selected on active tab', () => {});
  it('supports keyboard navigation', () => {});

  // Responsive tests
  it('is horizontally scrollable on small screens', () => {});
});
```

**Placeholder page tests:**
```typescript
describe('Tab Placeholder Pages', () => {
  it('renders Summary placeholder with correct epic info', () => {});
  it('renders Timeline placeholder with correct epic info', () => {});
  // ... for each tab
  it('displays matter ID on placeholder pages', () => {});
});
```

### Accessibility Requirements

From project-context.md and UX best practices:
- Tab bar uses `role="tablist"`
- Each tab link uses `role="tab"` with `aria-selected`
- Active tab has `aria-selected="true"`
- Keyboard navigation: Arrow keys to move between tabs, Enter/Space to activate
- Badge counts announced to screen readers
- Processing state announced ("Timeline, processing" vs "Timeline, 24 events")
- Tooltips provide context for badge meanings
- Color contrast meets WCAG AA standards

### Error Handling

**Invalid tab route:**
- If user navigates to `/matters/[matterId]/invalid-tab`, show 404 or redirect to summary
- Use Next.js `notFound()` function or redirect

**Tab stats fetch failure:**
- Show tabs without counts/badges
- Log error to console with structured format
- Don't block navigation due to stats failure

### Constants to Define

```typescript
// In WorkspaceTabBar or constants file
export const DEFAULT_TAB: TabId = 'summary';

export const TAB_LABELS: Record<TabId, string> = {
  summary: 'Summary',
  timeline: 'Timeline',
  entities: 'Entities',
  citations: 'Citations',
  contradictions: 'Contradictions',
  verification: 'Verification',
  documents: 'Documents',
};

export const TAB_EPIC_INFO: Record<TabId, string> = {
  summary: 'Epic 10B',
  timeline: 'Epic 10B',
  entities: 'Epic 10C',
  citations: 'Epic 10C',
  contradictions: 'Phase 2', // Deferred per architecture
  verification: 'Epic 10D',
  documents: 'Epic 10D',
};
```

### Integration with Processing Status

The tab bar should integrate with the existing job tracking system (Story 2c-3):

```typescript
// Hook into processing status for tab indicators
import { useJobStore } from '@/stores/jobStore'; // if exists

function useTabProcessingStatus(matterId: string) {
  // Check if any jobs are running that affect specific tabs
  // Example: If OCR is running, entities/timeline might show processing
  // Example: If entity extraction is running, entities tab shows processing
}
```

### References

- [Source: epics.md#story-10a2 - Acceptance criteria]
- [Source: architecture.md#frontend-structure - Component organization]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: Story 10A.1 - Previous story patterns and WorkspaceHeader integration]
- [Source: Story 2C.3 - Background job tracking for processing status]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

No debug issues encountered.

### Completion Notes List

- ✅ Created WorkspaceTabBar component with 7 tabs in correct order (Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents)
- ✅ Implemented URL-based routing with default redirect from `/matters/[matterId]` to `/matters/[matterId]/summary`
- ✅ Created workspaceStore with Zustand selector pattern for tab counts and processing status
- ✅ Implemented TabStatusIndicator showing issue badges (destructive variant), regular counts, and processing spinners
- ✅ Added keyboard navigation (ArrowLeft/Right, Home/End) with roving tabindex pattern
- ✅ Created 6 placeholder pages (Summary, Timeline, Entities, Citations, Contradictions, Documents) - Verification already existed
- ✅ Updated matter layout to include WorkspaceTabBar below WorkspaceHeader with sticky positioning
- ✅ Full test coverage: 59 new tests (32 for WorkspaceTabBar, 27 for workspaceStore)
- ✅ All 1045 frontend tests pass, lint passes with 0 warnings

### File List

**New Files:**
- frontend/src/components/features/matter/WorkspaceTabBar.tsx
- frontend/src/components/features/matter/WorkspaceTabBar.test.tsx
- frontend/src/stores/workspaceStore.ts
- frontend/src/stores/workspaceStore.test.ts
- frontend/src/app/(matter)/[matterId]/summary/page.tsx
- frontend/src/app/(matter)/[matterId]/timeline/page.tsx
- frontend/src/app/(matter)/[matterId]/entities/page.tsx
- frontend/src/app/(matter)/[matterId]/citations/page.tsx
- frontend/src/app/(matter)/[matterId]/contradictions/page.tsx
- frontend/src/app/(matter)/[matterId]/documents/page.tsx

**Modified Files:**
- frontend/src/app/(matter)/[matterId]/page.tsx (redirect to /summary)
- frontend/src/app/(matter)/[matterId]/layout.tsx (added WorkspaceTabBar)
- frontend/src/components/features/matter/index.ts (export WorkspaceTabBar)

### Change Log

- 2026-01-15: Implemented Story 10A.2 Tab Bar Navigation - 59 tests passing

