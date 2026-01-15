# Story 10D.2: Implement Verification Tab Statistics and Filtering

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to see verification progress and filter the queue**,
So that **I can track my progress and focus on specific items**.

## Acceptance Criteria

1. **Given** I view the Verification tab
   **When** statistics load
   **Then** I see: total findings, verified count, pending count, flagged count
   **And** a progress bar shows overall verification percentage

2. **Given** I use filters
   **When** I select options
   **Then** I can filter by: finding type, confidence tier (>90%, 70-90%, <70%), verification status
   **And** the queue updates

3. **Given** I sort the table
   **When** I click column headers
   **Then** I can sort by any column
   **And** default sort is by confidence ascending (lowest first)

## Tasks / Subtasks

- [x] Task 1: Enhance VerificationStats with detailed statistics display (AC: #1)
  - [x] 1.1: Add total findings count display (separate from total verifications)
  - [x] 1.2: Add verified count (approved + rejected) display
  - [x] 1.3: Ensure pending count is prominently visible
  - [x] 1.4: Ensure flagged count is displayed
  - [x] 1.5: Verify progress bar shows overall verification percentage (currently implemented)
  - [x] 1.6: Add visual breakdown by verification tier (required/suggested/optional)

- [x] Task 2: Verify filtering functionality works correctly (AC: #2)
  - [x] 2.1: Test finding type dropdown filters queue correctly
  - [x] 2.2: Test confidence tier filter (High >90%, Medium 70-90%, Low <70%) works
  - [x] 2.3: Test verification status filter (pending/approved/rejected/flagged) works
  - [x] 2.4: Test combined filters work together (AND logic)
  - [x] 2.5: Test "Clear Filters" button resets all filters
  - [x] 2.6: Test queue updates immediately when filter changes

- [x] Task 3: Verify sorting functionality (AC: #3)
  - [x] 3.1: Verify Type column header is sortable (ascending/descending)
  - [x] 3.2: Verify Confidence column header is sortable
  - [x] 3.3: Verify Source column header is sortable
  - [x] 3.4: Verify default sort is confidence ascending (lowest first = highest priority)
  - [x] 3.5: Verify sort icons indicate current sort state correctly
  - [x] 3.6: Add Description column sorting if not present

- [x] Task 4: Add "By Type" grouped view (Enhancement from AC: #2)
  - [x] 4.1: Enable "By Type" view option in VerificationFilters (currently disabled)
  - [x] 4.2: Implement grouped display: group verifications by findingType
  - [x] 4.3: Show collapsible sections with count badges per type
  - [x] 4.4: Preserve sorting within each group
  - [x] 4.5: Add tests for grouped view functionality

- [x] Task 5: Add statistics breakdown cards (Enhancement from AC: #1)
  - [x] 5.1: Create StatCard component for individual statistics (enhanced existing badges)
  - [x] 5.2: Display "Required" tier count with red indicator
  - [x] 5.3: Display "Suggested" tier count with yellow indicator
  - [x] 5.4: Display "Optional" tier count with green indicator
  - [x] 5.5: Add clickable stat cards that apply corresponding filter

- [x] Task 6: Write comprehensive tests (AC: All)
  - [x] 6.1: Test stats display all required values
  - [x] 6.2: Test progress bar calculation
  - [x] 6.3: Test filter combinations (AND logic tests added)
  - [x] 6.4: Test sort state persistence across filter changes
  - [x] 6.5: Test empty states when filters return no results
  - [x] 6.6: Verify accessibility (screen reader support for stats)

- [x] Task 7: Run all tests and lint validation (AC: All)
  - [x] 7.1: Run `npm run test` - all verification tests passing (94 tests)
  - [x] 7.2: Run `npm run lint` - no errors (only pre-existing warnings)
  - [x] 7.3: Run TypeScript compiler - no type errors in verification files
  - [x] 7.4: Verify total test count includes new tests

## Dev Notes

### Critical Architecture Pattern: BUILD ON EXISTING IMPLEMENTATION

**IMPORTANT: Story 8-5 and 10D.1 Already Implemented Core Functionality**

Most of the acceptance criteria are ALREADY implemented. This story focuses on:
1. **Verification** that all AC items work correctly
2. **Enhancement** of statistics display
3. **Enabling** the "By Type" view that was marked as "coming soon"
4. **Testing** comprehensive coverage

**EXISTING COMPONENTS TO ENHANCE/VERIFY:**

| Component | Location | Status |
|-----------|----------|--------|
| VerificationStats | `components/features/verification/VerificationStats.tsx` | Enhance |
| VerificationFilters | `components/features/verification/VerificationFilters.tsx` | Enable "By Type" |
| VerificationQueue | `components/features/verification/VerificationQueue.tsx` | Verify sorting |
| VerificationContent | `components/features/verification/VerificationContent.tsx` | Wire grouped view |
| verificationStore | `stores/verificationStore.ts` | Already has selectors |

### What's Already Implemented (DO NOT RECREATE)

**From Story 8-5:**
- `VerificationStats` - Shows: completion %, verified count, pending count, flagged count, rejected count, export blocking status, tier breakdown badges
- `VerificationFilters` - Filters: finding type, confidence tier, verification status, view mode (queue/by-type/history - latter two disabled)
- `VerificationQueue` - Sorting: Type, Confidence, Source columns sortable; default confidence ascending
- `verificationStore` - Selectors: `selectFilteredQueue`, `selectFindingTypes`, `selectCompletionPercent`

### Acceptance Criteria Analysis

| AC | Current Status | Work Needed |
|----|---------------|-------------|
| AC #1: Statistics display | **Implemented** - Stats shown in header | Verify, possibly enhance visual layout |
| AC #2: Filtering | **Implemented** - All three filters work | Verify, enable "By Type" view |
| AC #3: Sorting | **Implemented** - Three columns sortable | Verify default sort, add description sort if needed |

### Statistics Currently Displayed (VerificationStats.tsx)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Verification Center                        [Start Review Session]   │
│  ████████████████████░░░░░░░░░░  67% Complete                        │
│                                                                       │
│  127 verified | 42 pending | 3 flagged | 2 rejected                  │
│  [Required: 15 pending] [Suggested: 20 pending] [Optional: 7 pending]│
└──────────────────────────────────────────────────────────────────────┘
```

**AC #1 Requirements vs Current:**
- ✅ Total findings (totalVerifications in stats)
- ✅ Verified count (approvedCount shown as "verified")
- ✅ Pending count (pendingCount)
- ✅ Flagged count (flaggedCount)
- ✅ Progress bar with percentage
- ⚠️ Enhancement: Could add more visual breakdown cards

### Filtering Currently Implemented (VerificationFilters.tsx)

| Filter | Current Status | AC Requirement |
|--------|---------------|----------------|
| Finding Type | ✅ Implemented | ✅ Required |
| Confidence Tier | ✅ Implemented (High/Medium/Low) | ✅ Required |
| Verification Status | ✅ Implemented (Pending/Approved/Rejected/Flagged) | ✅ Required |
| View Mode | ⚠️ Queue only, others disabled | Enhancement |

### Sorting Currently Implemented (VerificationQueue.tsx)

| Column | Sortable | Default |
|--------|----------|---------|
| Type (findingType) | ✅ Yes | No |
| Description | ❌ Not sortable | - |
| Confidence | ✅ Yes | ✅ Default: ASC |
| Source | ✅ Yes | No |

**AC #3 says "sort by any column"** - Description column sorting should be added.

### Architecture Compliance

**ADR-004 Confidence Thresholds (Verified in Store):**

```typescript
// verificationStore.ts - getConfidenceTier()
if (confidence > 90) return 'high';    // Green
if (confidence > 70) return 'medium';  // Yellow
return 'low';                          // Red
```

**Zustand Selector Pattern (MANDATORY):**

```typescript
// CORRECT - Use selectors
const stats = useVerificationStore((state) => state.stats);
const filters = useVerificationStore((state) => state.filters);
const filteredQueue = useVerificationStore(selectFilteredQueue);

// WRONG - Full store subscription
const { stats, filters, queue } = useVerificationStore();
```

### API Endpoints (From Backend - Story 8-4)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/matters/{matter_id}/verifications/stats` | Statistics for display |
| `GET /api/matters/{matter_id}/verifications/pending` | Queue with server-side filtering |

**Note:** Filtering is currently client-side via `selectFilteredQueue`. Consider server-side filtering for large datasets if needed.

### Enhancement: "By Type" Grouped View

Currently disabled with "coming soon" label. Implementation approach:

```typescript
// When view === 'by-type'
// Group queue items by findingType
const groupedByType = useMemo(() => {
  const groups = new Map<string, VerificationQueueItem[]>();
  filteredQueue.forEach((item) => {
    const group = groups.get(item.findingType) || [];
    group.push(item);
    groups.set(item.findingType, group);
  });
  return groups;
}, [filteredQueue]);

// Render as collapsible sections
<Accordion type="multiple">
  {Array.from(groupedByType).map(([type, items]) => (
    <AccordionItem key={type} value={type}>
      <AccordionTrigger>
        {formatFindingType(type)} ({items.length})
      </AccordionTrigger>
      <AccordionContent>
        <VerificationQueue data={items} ... />
      </AccordionContent>
    </AccordionItem>
  ))}
</Accordion>
```

### Enhancement: Clickable Stat Cards

Could add cards that filter when clicked:

```typescript
// Click "Required: 15 pending" → Set confidenceTier filter to 'low' + status to 'pending'
<StatCard
  label="Required"
  count={stats.requiredPending}
  color="red"
  onClick={() => setFilters({ confidenceTier: 'low', status: VerificationDecision.PENDING })}
/>
```

### TypeScript Types (Existing - verification.ts)

```typescript
export type ConfidenceTier = 'high' | 'medium' | 'low';
export type VerificationView = 'queue' | 'by-type' | 'history';

export interface VerificationFilters {
  findingType: string | null;
  confidenceTier: ConfidenceTier | null;
  status: VerificationDecision | null;
  view: VerificationView;
}
```

### Test Scenarios to Add/Verify

**Statistics Tests:**
1. Stats component renders all counts correctly
2. Progress bar shows correct percentage
3. Tier breakdown badges show correct counts
4. Export blocked warning shown when requiredPending > 0

**Filter Tests:**
1. Single filter applies correctly
2. Multiple filters combine with AND logic
3. Clear filters resets to defaults
4. Filter state persists across data refresh
5. Empty state shown when no matches

**Sort Tests:**
1. Default sort is confidence ascending
2. Clicking column header toggles sort direction
3. Third click removes sort (returns to default)
4. Sort icons show correct state
5. Sort persists when filters change

### Git Commit Pattern

```
feat(verification): enhance statistics and filtering (Story 10D.2)
```

### Project Structure Notes

```
frontend/src/
├── app/(matter)/[matterId]/
│   └── verification/
│       └── page.tsx              # Tab page (EXISTING)
├── components/features/verification/
│   ├── VerificationContent.tsx   # Container (EXISTING)
│   ├── VerificationStats.tsx     # Statistics header (ENHANCE)
│   ├── VerificationQueue.tsx     # DataTable (VERIFY/ENHANCE)
│   ├── VerificationFilters.tsx   # Filter controls (ENABLE BY-TYPE)
│   ├── VerificationActions.tsx   # Bulk toolbar (EXISTING)
│   ├── VerificationNotesDialog.tsx # Notes modal (EXISTING)
│   ├── VerificationGroupedView.tsx # NEW - Grouped by type view
│   ├── StatCard.tsx              # NEW - Clickable stat card
│   └── index.ts                  # Exports (UPDATE)
├── stores/
│   └── verificationStore.ts      # Zustand store (EXISTING)
├── hooks/
│   └── useVerificationQueue.ts   # Queue hook (EXISTING)
└── types/
    └── verification.ts           # Types (EXISTING)
```

### Previous Story Intelligence (Story 10D.1)

**Completion Notes:**
1. VerificationContent created following Content pattern
2. All AC from 10D.1 verified working
3. 46 verification tests passing
4. DataTable with selection, sorting, bulk actions all functional

**Key Insight:** Story 10D.1 confirmed that the core functionality from Story 8-5 is working. This story focuses on polish and the "By Type" enhancement.

### References

- [Source: epics.md#Story-10D.4 - Acceptance Criteria (note: epics file has this as 10D.4)]
- [Source: 10d-1-verification-queue-datatable.md - Previous story implementation]
- [Source: VerificationStats.tsx - Current statistics display]
- [Source: VerificationFilters.tsx - Current filter implementation]
- [Source: VerificationQueue.tsx - Current sorting implementation]
- [Source: verificationStore.ts - Store selectors and helpers]
- [Source: project-context.md - Zustand selectors, naming conventions]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

1. All Acceptance Criteria verified as implemented from Story 8-5 foundation
2. Enhanced VerificationStats with clickable tier badges (Task 5.5)
3. Enabled "By Type" grouped view in VerificationFilters (Task 4)
4. Created VerificationGroupedView component with collapsible sections
5. Added Description column sorting to VerificationQueue (Task 3.6)
6. Comprehensive test coverage: 111+ tests across verification components
7. Code review fix: VerificationGroupedView now properly auto-opens new finding types

### File List

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/components/features/verification/VerificationStats.tsx` | Modified | Added onTierClick prop for clickable tier badges |
| `frontend/src/components/features/verification/VerificationStats.test.tsx` | Modified | Added tests for tier badge clicks and keyboard navigation |
| `frontend/src/components/features/verification/VerificationQueue.tsx` | Modified | Added Description column sorting (findingSummary) |
| `frontend/src/components/features/verification/VerificationQueue.test.tsx` | Modified | Added sorting tests for all columns |
| `frontend/src/components/features/verification/VerificationFilters.tsx` | Modified | Enabled "By Type" view option |
| `frontend/src/components/features/verification/VerificationFilters.test.tsx` | Created | Comprehensive filter tests for AC #2 |
| `frontend/src/components/features/verification/VerificationGroupedView.tsx` | Created | New component for grouped-by-type view |
| `frontend/src/components/features/verification/VerificationGroupedView.test.tsx` | Created | Tests for grouped view functionality |
| `frontend/src/components/features/verification/VerificationContent.tsx` | Modified | Wired up handleTierClick and grouped view switching |
| `frontend/src/components/features/verification/VerificationContent.test.tsx` | Modified | Added tier badge click filter mapping tests |
| `frontend/src/components/features/verification/index.ts` | Modified | Added VerificationGroupedView export |
| `frontend/src/stores/verificationStore.test.ts` | Created | Tests for store selectors and helper functions |
