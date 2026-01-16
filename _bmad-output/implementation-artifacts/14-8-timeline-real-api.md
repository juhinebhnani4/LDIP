# Story 14.8: Timeline Real API Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **the Timeline Tab to use real backend APIs consistently**,
So that **I see actual case events from my documents instead of mock data**.

## Acceptance Criteria

1. **Given** I view the Timeline Tab
   **When** the data loads
   **Then** it uses the real `/api/matters/{matterId}/timeline/full` endpoint
   **And** no mock data patterns or fallbacks remain in the hook

2. **Given** I create, edit, or delete a manual timeline event
   **When** the operation is performed
   **Then** it uses the correct `/api/` prefix (not `/api/v1/`)
   **And** the operation succeeds against the real backend

3. **Given** I apply filters (event type, actors, date range, verification status)
   **When** the filters are applied
   **Then** the filtering works correctly with real API data
   **And** client-side filtering is applied efficiently

4. **Given** the real API returns zero events
   **When** the Timeline Tab renders
   **Then** an appropriate empty state is shown (not mock data)

## Tasks / Subtasks

- [x] Task 1: Fix API URL prefix inconsistency (AC: #2)
  - [x] 1.1: Update `timelineEventApi.create` to use `/api/matters/` instead of `/api/v1/matters/`
  - [x] 1.2: Update `timelineEventApi.update` to use `/api/matters/` instead of `/api/v1/matters/`
  - [x] 1.3: Update `timelineEventApi.delete` to use `/api/matters/` instead of `/api/v1/matters/`
  - [x] 1.4: Update `timelineEventApi.setVerified` to use `/api/matters/` instead of `/api/v1/matters/`

- [x] Task 2: Clean up mock data patterns in useTimeline hook (AC: #1, #4)
  - [x] 2.1: Remove or move the `_MOCK_EVENTS` constant to a test file (currently marked as unused but kept for reference)
  - [x] 2.2: Remove the `eslint-disable @typescript-eslint/no-unused-vars` comment for mock data
  - [x] 2.3: Ensure the real `fetcher` function is the only data source
  - [x] 2.4: Verify error handling displays appropriate messages when API fails

- [x] Task 3: Verify real API integration is working (AC: #1, #3)
  - [x] 3.1: Verify `useTimeline` hook calls `/api/matters/${matterId}/timeline/full`
  - [x] 3.2: Verify `useTimelineStats` hook calls `/api/matters/${matterId}/timeline/stats`
  - [x] 3.3: Verify client-side `applyFilters()` function works correctly with real data
  - [x] 3.4: Test all filter combinations (event types, entities, date range, verification)

- [x] Task 4: Handle empty state properly (AC: #4)
  - [x] 4.1: Verify TimelineContent shows empty state when `events.length === 0`
  - [x] 4.2: Ensure empty state message is user-friendly (e.g., "No timeline events found. Events will appear after document processing.")
  - [x] 4.3: Verify filtered empty state shows "No events match your filters" when filters applied

- [x] Task 5: Write/update tests (AC: All)
  - [x] 5.1: Update `useTimeline` tests to verify real API URL is used
  - [x] 5.2: Add test for `timelineEventApi` with correct URL prefix
  - [x] 5.3: Test error handling when API returns 500
  - [x] 5.4: Test empty state rendering

## Dev Notes

### Current State Analysis (2026-01-16)

**IMPORTANT: The hooks ARE already connected to real APIs!**

After thorough analysis, the current implementation already uses real backend APIs:
- `useTimeline.ts` line 348: `/api/matters/${matterId}/timeline/full`
- `useTimelineStats.ts` line 65: `/api/matters/${matterId}/timeline/stats`

The gap analysis document (GAP-FE-3) mentioned "mock data" but this is outdated. The mock data in `useTimeline.ts` is marked with `@typescript-eslint/no-unused-vars` and is only kept for reference/testing.

### The Actual Issues to Fix

1. **API URL Prefix Inconsistency**: `timelineEventApi` in `client.ts` uses `/api/v1/matters/` while the correct prefix is `/api/matters/`
2. **Leftover Mock Data**: The `_MOCK_EVENTS` constant should be moved to test files for clarity
3. **Documentation/Comments**: Some comments mention mock data patterns that are no longer accurate

### File Changes Required

**frontend/src/lib/api/client.ts** (lines 277-321):
```typescript
// CURRENT (WRONG):
`/api/v1/matters/${matterId}/timeline/events`

// SHOULD BE:
`/api/matters/${matterId}/timeline/events`
```

**frontend/src/hooks/useTimeline.ts**:
- Remove or move `_MOCK_EVENTS` to test file
- Remove eslint-disable comment
- Update any misleading comments about mock data

### Backend API Reference

The backend timeline routes are at `/api/matters/{matter_id}/timeline/...`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/matters/{id}/timeline/full` | GET | Get timeline with entities |
| `/api/matters/{id}/timeline/stats` | GET | Get timeline statistics |
| `/api/matters/{id}/timeline/events` | POST | Create manual event |
| `/api/matters/{id}/timeline/events/{event_id}` | PATCH | Update event |
| `/api/matters/{id}/timeline/events/{event_id}` | DELETE | Delete manual event |
| `/api/matters/{id}/timeline/events/{event_id}/verify` | PATCH | Verify event |

[Source: backend/app/api/routes/timeline.py]
[Source: backend/app/main.py:146 - router prefix is "/api"]

### Filtering Implementation

Currently filtering is done **client-side** via the `applyFilters()` function:
- Filters by event types array
- Filters by entity IDs array
- Filters by date range (start/end)
- Filters by verification status

The backend `/full` endpoint supports:
- `event_type` (single value)
- `entity_id` (single value)

For MVP, client-side filtering is acceptable. Server-side filtering could be a future optimization for large datasets.

### Previous Story Intelligence (Story 10B.5)

From Story 10B.5 completion notes:
- All timeline filtering and manual event CRUD implemented
- TimelineFilterBar, AddEventDialog, EditEventDialog, DeleteEventConfirmation components created
- 243 frontend tests + 61 backend tests passing
- Client-side filtering chosen for better UX (immediate feedback)

### Project Context Rules

**Zustand Selector Pattern (MANDATORY):**
```typescript
// CORRECT
const events = useTimeline(matterId, { filters });

// WRONG - Don't destructure entire store
const { events, filteredEvents, ... } = useTimeline();
```

**API Response Format:**
```typescript
// Success - list with pagination
{
  "data": [...],
  "meta": { "total": 150, "page": 1, "per_page": 20, "total_pages": 8 }
}
```

### Testing Considerations

- Use MSW for network mocking in tests
- Test the real API URL paths are constructed correctly
- Test error states (network failure, 500 response)
- Test empty states (0 events returned)

### References

- [Source: _bmad-output/implementation-artifacts/mvp-gap-analysis-2026-01-16.md - GAP-FE-3]
- [Source: _bmad-output/implementation-artifacts/10b-5-timeline-filtering-manual-events.md - Previous story context]
- [Source: _bmad-output/project-context.md - Naming conventions, Zustand patterns]
- [Source: frontend/src/hooks/useTimeline.ts - Current implementation]
- [Source: frontend/src/lib/api/client.ts:268-322 - timelineEventApi]
- [Source: backend/app/api/routes/timeline.py - Backend endpoints]
- [Source: backend/app/main.py:146 - Router prefix "/api"]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Clean implementation with no debugging required.

### Completion Notes List

1. **Fixed API URL prefix inconsistency (AC #2)**: Updated all four `timelineEventApi` methods in `client.ts` to use `/api/matters/` instead of `/api/v1/matters/`:
   - `create`: POST `/api/matters/{matterId}/timeline/events`
   - `update`: PATCH `/api/matters/{matterId}/timeline/events/{eventId}`
   - `delete`: DELETE `/api/matters/{matterId}/timeline/events/{eventId}`
   - `setVerified`: PATCH `/api/matters/{matterId}/timeline/events/{eventId}/verify`

2. **Cleaned up mock data (AC #1)**: Removed the unused `_MOCK_EVENTS` constant (~180 lines) and associated eslint-disable comment from `useTimeline.ts`. The real `fetcher` function is now the only data source.

3. **Verified real API integration (AC #1, #3)**: Confirmed that:
   - `useTimeline` hook calls `/api/matters/${matterId}/timeline/full` (line 348)
   - `useTimelineStats` hook calls `/api/matters/${matterId}/timeline/stats` (line 65)
   - Client-side `applyFilters()` function correctly handles event types, entity IDs, date range, and verification status filters

4. **Enhanced empty state handling (AC #4)**: Added `hasFiltersApplied` prop to `TimelineList` component:
   - Default empty state: "No Events Found" + "Timeline events will appear here once documents are processed"
   - Filtered empty state: "No Matching Events" + "No events match your current filters. Try adjusting or clearing your filters."

5. **Added comprehensive tests (All ACs)**:
   - Created `timelineEventApi.test.ts` with 9 tests verifying URL prefix, request/response transformation, and error handling
   - Added 3 new tests to `TimelineList.test.tsx` for filtered empty state behavior
   - Total: 254 timeline tests passing (1 pre-existing failure in DeleteEventConfirmation.test.tsx unrelated to this story)

### File List

**Modified:**
- frontend/src/lib/api/client.ts (lines 277, 294, 305, 317 - fixed URL prefix)
- frontend/src/hooks/useTimeline.ts (removed mock data constant ~180 lines)
- frontend/src/components/features/timeline/TimelineList.tsx (added hasFiltersApplied prop and enhanced EmptyState)
- frontend/src/components/features/timeline/TimelineContent.tsx (passes hasFiltersApplied to TimelineList)
- frontend/src/components/features/timeline/TimelineList.test.tsx (added 3 new empty state tests)

**Created:**
- frontend/src/lib/api/timelineEventApi.test.ts (9 tests for API URL and transformation)

### Change Log

- 2026-01-16: Story implementation complete - All ACs satisfied with 254 tests passing
- 2026-01-16: Code review fixes applied:
  - Removed trailing empty lines from client.ts
  - Enhanced error handling tests with specific ApiError assertions (code, message, status)
  - Added 404 error test for non-existent event
  - Added 401 token refresh flow test
  - Total: 11 API tests now passing (was 9)
