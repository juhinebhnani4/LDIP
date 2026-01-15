# Story 10B.4: Implement Timeline Tab Alternative Views

Status: done

## Story

As an **attorney**,
I want **different timeline visualizations**,
So that **I can view the timeline in the most useful format**.

## Acceptance Criteria

1. **Given** I am in the Timeline tab
   **When** I click the view toggle
   **Then** I can switch between: Vertical List (default), Horizontal Timeline, Multi-Track

2. **Given** I select Horizontal Timeline
   **When** the view renders
   **Then** events are displayed on a horizontal axis with zoom slider
   **And** event clusters and gap indicators are visible

3. **Given** I select Multi-Track view
   **When** the view renders
   **Then** parallel timelines are shown by actor
   **And** events are aligned vertically by date across tracks

## Tasks / Subtasks

- [x] Task 1: Update timeline types for new view modes (AC: All)
  - [x] 1.1: Update `TimelineViewMode` type in `frontend/src/types/timeline.ts` to include 'multitrack' (currently has 'list' | 'horizontal' | 'table')
  - [x] 1.2: Add `TimelineTrack` interface for multi-track data structure (actor + events)
  - [x] 1.3: Add `ZoomLevel` type and zoom-related interfaces
  - [x] 1.4: Add `EventCluster` interface for grouped events

- [x] Task 2: Create TimelineHorizontal component (AC: #2)
  - [x] 2.1: Create `frontend/src/components/features/timeline/TimelineHorizontal.tsx`
  - [x] 2.2: Render horizontal axis with year labels
  - [x] 2.3: Plot events as markers on the axis
  - [x] 2.4: Implement event clustering when events are close together (within 7 days at default zoom)
  - [x] 2.5: Show gap indicators for significant delays (> 90 days)
  - [x] 2.6: Add zoom slider to adjust time scale
  - [x] 2.7: Implement click-to-select event with detail panel below
  - [x] 2.8: Support horizontal scroll/pan for navigation
  - [x] 2.9: Handle empty state (no events)
  - [x] 2.10: Create `TimelineHorizontal.test.tsx`

- [x] Task 3: Create TimelineMultiTrack component (AC: #3)
  - [x] 3.1: Create `frontend/src/components/features/timeline/TimelineMultiTrack.tsx`
  - [x] 3.2: Group events by actor (entity) into separate tracks
  - [x] 3.3: Render parallel horizontal timelines for each actor
  - [x] 3.4: Align events vertically by date across all tracks
  - [x] 3.5: Add track labels (actor names) on left side
  - [x] 3.6: Show vertical grid lines for date alignment
  - [x] 3.7: Handle actors with no events (hide track or show empty)
  - [x] 3.8: Support click-to-select event
  - [x] 3.9: Create `TimelineMultiTrack.test.tsx`

- [x] Task 4: Create shared timeline utilities (AC: #2, #3)
  - [x] 4.1: Create `frontend/src/components/features/timeline/timelineUtils.ts`
  - [x] 4.2: Add `calculateTimelineScale()` function for date-to-position mapping
  - [x] 4.3: Add `clusterEvents()` function to group nearby events
  - [x] 4.4: Add `groupEventsByActor()` function for multi-track
  - [x] 4.5: Add `calculateGaps()` function to find significant time gaps
  - [x] 4.6: Add `formatTimeAxis()` function for axis labels

- [x] Task 5: Create TimelineZoomSlider component (AC: #2)
  - [x] 5.1: Create `frontend/src/components/features/timeline/TimelineZoomSlider.tsx`
  - [x] 5.2: Implement slider with min/max zoom levels
  - [x] 5.3: Add zoom in/out buttons (+/-)
  - [x] 5.4: Display current zoom level indicator
  - [x] 5.5: Create `TimelineZoomSlider.test.tsx`

- [x] Task 6: Create TimelineEventDetail component (AC: #2, #3)
  - [x] 6.1: Create `frontend/src/components/features/timeline/TimelineEventDetail.tsx`
  - [x] 6.2: Display selected event details in compact panel below timeline
  - [x] 6.3: Include: event type icon, date, description, actor, source link
  - [x] 6.4: Add "View in List" button to switch to list view at that event
  - [x] 6.5: Add "View Source" button to open document
  - [x] 6.6: Create `TimelineEventDetail.test.tsx`

- [x] Task 7: Update TimelineHeader component (AC: #1)
  - [x] 7.1: Enable horizontal and multi-track buttons (remove disabled state)
  - [x] 7.2: Update button title tooltips to remove "Coming soon"
  - [x] 7.3: Replace Table2 icon/button with Users icon for Multi-Track
  - [x] 7.4: Update tests for enabled buttons

- [x] Task 8: Update TimelineContent component (AC: All)
  - [x] 8.1: Update `handleViewModeChange` to allow all modes
  - [x] 8.2: Add conditional rendering based on viewMode:
    - 'list': `<TimelineList />`
    - 'horizontal': `<TimelineHorizontal />`
    - 'multitrack': `<TimelineMultiTrack />`
  - [x] 8.3: Add state for selected event (for horizontal/multitrack detail panels)
  - [x] 8.4: Pass `onEventSelect` callback to horizontal/multitrack components
  - [x] 8.5: Update tests for view mode switching

- [x] Task 9: Update barrel exports (AC: All)
  - [x] 9.1: Update `frontend/src/components/features/timeline/index.ts` with new exports
  - [x] 9.2: Verify types exported from `frontend/src/types/index.ts`

- [x] Task 10: Write comprehensive tests (AC: All)
  - [x] 10.1: Test view mode toggle enables all three options
  - [x] 10.2: Test horizontal view renders events on axis
  - [x] 10.3: Test event clustering groups nearby events
  - [x] 10.4: Test zoom slider changes timeline scale
  - [x] 10.5: Test gap indicators appear for large gaps
  - [x] 10.6: Test multi-track groups by actor
  - [x] 10.7: Test vertical alignment across tracks
  - [x] 10.8: Test event selection shows detail panel
  - [x] 10.9: Test "View in List" navigation works
  - [x] 10.10: Test accessibility (keyboard nav, ARIA labels)

## Dev Notes

### Critical Architecture Patterns

**Timeline Alternative Views (from UX-Decisions-Log.md Section 7.2, 7.3):**

The Timeline tab supports three view modes:
1. **Vertical List (default)** - Detailed reading, chronological scroll (Story 10B.3 - DONE)
2. **Horizontal Timeline** - Visual overview, pattern spotting
3. **Multi-Track** - Parallel timelines by actor, for cases with many parties

**Horizontal Timeline Features:**
- Horizontal axis with year labels
- Events as markers on the axis
- Zoom slider to adjust time scale
- Event clusters for dense periods
- Gap indicators for significant delays (> 90 days)
- Click event to see detail panel below
- Scroll/pan for navigation

**Multi-Track View Features:**
- Separate horizontal track per actor (entity)
- Events aligned vertically by date
- Track labels on left side (actor names)
- Visual comparison of parallel proceedings
- Best for cases with Petitioner, Court, Custodian, etc.

**Component Structure:**
```
frontend/src/components/features/timeline/
├── index.ts                           # UPDATE - Add new exports
├── eventTypeIcons.ts                  # EXISTING - Reuse
├── timelineUtils.ts                   # NEW - Shared utilities
├── TimelineHeader.tsx                 # UPDATE - Enable buttons
├── TimelineHeader.test.tsx            # UPDATE - Test enabled buttons
├── TimelineEventCard.tsx              # EXISTING - Reuse for list
├── TimelineEventCard.test.tsx         # EXISTING
├── TimelineConnector.tsx              # EXISTING - List view only
├── TimelineConnector.test.tsx         # EXISTING
├── TimelineList.tsx                   # EXISTING - List view
├── TimelineList.test.tsx              # EXISTING
├── TimelineHorizontal.tsx             # NEW - Horizontal view
├── TimelineHorizontal.test.tsx        # NEW
├── TimelineMultiTrack.tsx             # NEW - Multi-track view
├── TimelineMultiTrack.test.tsx        # NEW
├── TimelineZoomSlider.tsx             # NEW - Zoom control
├── TimelineZoomSlider.test.tsx        # NEW
├── TimelineEventDetail.tsx            # NEW - Compact detail panel
├── TimelineEventDetail.test.tsx       # NEW
├── TimelineContent.tsx                # UPDATE - View switching
└── TimelineContent.test.tsx           # UPDATE
```

### TypeScript Type Definitions

```typescript
// Additional types for types/timeline.ts

/**
 * Updated view modes - change 'table' to 'multitrack'
 */
export type TimelineViewMode = 'list' | 'horizontal' | 'multitrack';

/**
 * Zoom level for horizontal/multitrack views
 */
export type ZoomLevel = 'year' | 'quarter' | 'month' | 'week' | 'day';

/**
 * Timeline track for multi-track view
 */
export interface TimelineTrack {
  /** Actor entity ID */
  entityId: string;
  /** Actor name */
  actorName: string;
  /** Actor type (PERSON, ORG, INSTITUTION) */
  actorType: string;
  /** Events for this actor */
  events: TimelineEvent[];
}

/**
 * Event cluster for grouped events
 */
export interface EventCluster {
  /** Cluster ID */
  id: string;
  /** Cluster center date */
  centerDate: string;
  /** Events in cluster */
  events: TimelineEvent[];
  /** Whether cluster is expanded */
  isExpanded: boolean;
}

/**
 * Timeline gap for significant delays
 */
export interface TimelineGap {
  /** Gap start date */
  startDate: string;
  /** Gap end date */
  endDate: string;
  /** Duration in days */
  durationDays: number;
  /** Whether significant (> 90 days) */
  isSignificant: boolean;
}
```

### Horizontal Timeline Implementation

```typescript
// TimelineHorizontal.tsx structure
'use client';

import { useState, useRef, useMemo, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { TimelineZoomSlider } from './TimelineZoomSlider';
import { TimelineEventDetail } from './TimelineEventDetail';
import { calculateTimelineScale, clusterEvents, calculateGaps } from './timelineUtils';
import { EVENT_TYPE_ICONS, EVENT_TYPE_COLORS } from './eventTypeIcons';
import type { TimelineEvent, ZoomLevel } from '@/types/timeline';

interface TimelineHorizontalProps {
  events: TimelineEvent[];
  onEventSelect?: (event: TimelineEvent | null) => void;
  selectedEventId?: string | null;
  className?: string;
}

export function TimelineHorizontal({
  events,
  onEventSelect,
  selectedEventId,
  className,
}: TimelineHorizontalProps) {
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('year');
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate scale and positions
  const { scale, markers, yearLabels } = useMemo(
    () => calculateTimelineScale(events, zoomLevel),
    [events, zoomLevel]
  );

  // Cluster nearby events
  const clusters = useMemo(
    () => clusterEvents(events, zoomLevel),
    [events, zoomLevel]
  );

  // Find gaps
  const gaps = useMemo(
    () => calculateGaps(events),
    [events]
  );

  const selectedEvent = events.find(e => e.id === selectedEventId);

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Zoom controls */}
      <div className="flex justify-end mb-4">
        <TimelineZoomSlider
          zoomLevel={zoomLevel}
          onZoomChange={setZoomLevel}
        />
      </div>

      {/* Timeline axis */}
      <div
        ref={containerRef}
        className="relative h-32 overflow-x-auto border rounded-lg bg-muted/20"
        role="graphics-document"
        aria-label="Horizontal timeline"
      >
        {/* Year labels */}
        <div className="absolute top-2 left-0 right-0 flex justify-between px-4">
          {yearLabels.map(label => (
            <span key={label.year} className="text-xs text-muted-foreground">
              {label.year}
            </span>
          ))}
        </div>

        {/* Main axis line */}
        <div className="absolute top-1/2 left-4 right-4 h-0.5 bg-border" />

        {/* Event markers */}
        {clusters.map(cluster => (
          <TimelineMarker
            key={cluster.id}
            cluster={cluster}
            scale={scale}
            isSelected={cluster.events.some(e => e.id === selectedEventId)}
            onClick={() => onEventSelect?.(cluster.events[0])}
          />
        ))}

        {/* Gap indicators */}
        {gaps.filter(g => g.isSignificant).map((gap, i) => (
          <GapIndicator key={i} gap={gap} scale={scale} />
        ))}
      </div>

      {/* Selected event detail */}
      {selectedEvent && (
        <TimelineEventDetail
          event={selectedEvent}
          onClose={() => onEventSelect?.(null)}
          className="mt-4"
        />
      )}
    </div>
  );
}
```

### Multi-Track Implementation

```typescript
// TimelineMultiTrack.tsx structure
'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { groupEventsByActor } from './timelineUtils';
import { TimelineEventDetail } from './TimelineEventDetail';
import type { TimelineEvent, TimelineTrack } from '@/types/timeline';

interface TimelineMultiTrackProps {
  events: TimelineEvent[];
  onEventSelect?: (event: TimelineEvent | null) => void;
  selectedEventId?: string | null;
  className?: string;
}

export function TimelineMultiTrack({
  events,
  onEventSelect,
  selectedEventId,
  className,
}: TimelineMultiTrackProps) {
  // Group events by actor
  const tracks = useMemo(
    () => groupEventsByActor(events),
    [events]
  );

  // Calculate date range for vertical alignment
  const dateRange = useMemo(() => {
    const dates = events.map(e => new Date(e.eventDate).getTime());
    return {
      min: Math.min(...dates),
      max: Math.max(...dates),
    };
  }, [events]);

  const selectedEvent = events.find(e => e.id === selectedEventId);

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Track container */}
      <div
        className="relative border rounded-lg bg-muted/20 overflow-x-auto"
        role="graphics-document"
        aria-label="Multi-track timeline"
      >
        {/* Year header */}
        <div className="sticky top-0 h-8 border-b bg-background flex items-center px-4">
          {/* Year labels aligned with date positions */}
        </div>

        {/* Tracks */}
        {tracks.map(track => (
          <TrackRow
            key={track.entityId}
            track={track}
            dateRange={dateRange}
            selectedEventId={selectedEventId}
            onEventSelect={onEventSelect}
          />
        ))}

        {/* Vertical grid lines for date alignment */}
        <div className="absolute inset-0 pointer-events-none">
          {/* Grid lines */}
        </div>
      </div>

      {/* Selected event detail */}
      {selectedEvent && (
        <TimelineEventDetail
          event={selectedEvent}
          onClose={() => onEventSelect?.(null)}
          className="mt-4"
        />
      )}
    </div>
  );
}

function TrackRow({
  track,
  dateRange,
  selectedEventId,
  onEventSelect,
}: {
  track: TimelineTrack;
  dateRange: { min: number; max: number };
  selectedEventId?: string | null;
  onEventSelect?: (event: TimelineEvent | null) => void;
}) {
  return (
    <div className="flex items-center h-16 border-b last:border-b-0">
      {/* Track label */}
      <div className="w-40 shrink-0 px-4 truncate font-medium text-sm">
        {track.actorName}
      </div>

      {/* Track timeline */}
      <div className="flex-1 relative h-full">
        {/* Events as markers */}
        {track.events.map(event => (
          <EventMarker
            key={event.id}
            event={event}
            dateRange={dateRange}
            isSelected={event.id === selectedEventId}
            onClick={() => onEventSelect?.(event)}
          />
        ))}
      </div>
    </div>
  );
}
```

### Timeline Utilities

```typescript
// timelineUtils.ts
import { parseISO, differenceInDays, startOfYear, endOfYear, eachYearOfInterval } from 'date-fns';
import type { TimelineEvent, TimelineTrack, EventCluster, TimelineGap, ZoomLevel } from '@/types/timeline';

/**
 * Calculate timeline scale and positions
 */
export function calculateTimelineScale(
  events: TimelineEvent[],
  zoomLevel: ZoomLevel
) {
  if (events.length === 0) {
    return { scale: 1, markers: [], yearLabels: [] };
  }

  const dates = events.map(e => parseISO(e.eventDate));
  const minDate = startOfYear(dates.reduce((a, b) => a < b ? a : b));
  const maxDate = endOfYear(dates.reduce((a, b) => a > b ? a : b));

  const years = eachYearOfInterval({ start: minDate, end: maxDate });
  const yearLabels = years.map(y => ({
    year: y.getFullYear(),
    position: 0, // Calculate based on scale
  }));

  // Scale factor based on zoom level
  const scaleMultiplier = {
    year: 1,
    quarter: 4,
    month: 12,
    week: 52,
    day: 365,
  }[zoomLevel];

  return {
    scale: scaleMultiplier,
    markers: [], // Event positions
    yearLabels,
    minDate,
    maxDate,
  };
}

/**
 * Cluster events that are close together
 */
export function clusterEvents(
  events: TimelineEvent[],
  zoomLevel: ZoomLevel
): EventCluster[] {
  const clusterThreshold = {
    year: 30, // days
    quarter: 14,
    month: 7,
    week: 2,
    day: 1,
  }[zoomLevel];

  const clusters: EventCluster[] = [];
  const sorted = [...events].sort((a, b) =>
    new Date(a.eventDate).getTime() - new Date(b.eventDate).getTime()
  );

  let currentCluster: TimelineEvent[] = [];

  for (const event of sorted) {
    if (currentCluster.length === 0) {
      currentCluster.push(event);
    } else {
      const lastEvent = currentCluster[currentCluster.length - 1];
      const daysDiff = differenceInDays(
        parseISO(event.eventDate),
        parseISO(lastEvent.eventDate)
      );

      if (daysDiff <= clusterThreshold) {
        currentCluster.push(event);
      } else {
        // Save current cluster and start new one
        clusters.push(createCluster(currentCluster));
        currentCluster = [event];
      }
    }
  }

  if (currentCluster.length > 0) {
    clusters.push(createCluster(currentCluster));
  }

  return clusters;
}

function createCluster(events: TimelineEvent[]): EventCluster {
  const centerIndex = Math.floor(events.length / 2);
  return {
    id: `cluster-${events[0].id}`,
    centerDate: events[centerIndex].eventDate,
    events,
    isExpanded: false,
  };
}

/**
 * Group events by actor entity
 */
export function groupEventsByActor(events: TimelineEvent[]): TimelineTrack[] {
  const actorMap = new Map<string, TimelineTrack>();

  for (const event of events) {
    // Events can have multiple actors
    const actors = event.entities.length > 0
      ? event.entities
      : [{ entityId: 'unknown', canonicalName: 'Unknown', entityType: 'UNKNOWN' }];

    for (const actor of actors) {
      if (!actorMap.has(actor.entityId)) {
        actorMap.set(actor.entityId, {
          entityId: actor.entityId,
          actorName: actor.canonicalName,
          actorType: actor.entityType,
          events: [],
        });
      }
      actorMap.get(actor.entityId)!.events.push(event);
    }
  }

  // Sort tracks by event count (most active first)
  return Array.from(actorMap.values())
    .sort((a, b) => b.events.length - a.events.length);
}

/**
 * Calculate gaps between events
 */
export function calculateGaps(events: TimelineEvent[]): TimelineGap[] {
  const SIGNIFICANT_GAP_DAYS = 90;
  const gaps: TimelineGap[] = [];

  const sorted = [...events].sort((a, b) =>
    new Date(a.eventDate).getTime() - new Date(b.eventDate).getTime()
  );

  for (let i = 0; i < sorted.length - 1; i++) {
    const days = differenceInDays(
      parseISO(sorted[i + 1].eventDate),
      parseISO(sorted[i].eventDate)
    );

    if (days > 0) {
      gaps.push({
        startDate: sorted[i].eventDate,
        endDate: sorted[i + 1].eventDate,
        durationDays: days,
        isSignificant: days > SIGNIFICANT_GAP_DAYS,
      });
    }
  }

  return gaps;
}
```

### Zustand Store Pattern (MANDATORY)

```typescript
// CORRECT - Selector pattern
const viewMode = useTimelineStore((state) => state.viewMode);
const setViewMode = useTimelineStore((state) => state.setViewMode);

// WRONG - Full store subscription
const { viewMode, setViewMode } = useTimelineStore();
```

### Naming Conventions (from project-context.md)

| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `TimelineHorizontal`, `TimelineMultiTrack` |
| Component files | PascalCase.tsx | `TimelineHorizontal.tsx` |
| Utility files | camelCase.ts | `timelineUtils.ts` |
| Functions | camelCase | `calculateTimelineScale`, `groupEventsByActor` |
| Constants | SCREAMING_SNAKE | `SIGNIFICANT_GAP_DAYS`, `CLUSTER_THRESHOLD` |
| Types/Interfaces | PascalCase | `TimelineTrack`, `EventCluster` |

### Accessibility Requirements

- Timeline visualizations have appropriate ARIA roles (`graphics-document`)
- Event markers are keyboard navigable (Tab, Enter to select)
- Screen reader announces event details on selection
- Zoom slider has accessible labels and keyboard support
- Multi-track has track labels associated with rows
- Color coding supplemented with icons/patterns for color-blind users
- Focus visible on selected elements

### Previous Story Intelligence (Story 10B.3)

**From Story 10B.3 implementation:**
- TimelineHeader already has view toggle buttons (currently horizontal/table disabled)
- TimelineContent manages viewMode state
- TimelineList renders vertical chronological view
- TimelineEventCard has all event display logic
- Event type icons in `eventTypeIcons.ts`
- SWR hooks for data fetching: `useTimeline`, `useTimelineStats`
- 96 tests passing for list view

**Patterns established:**
- Co-located test files (ComponentName.test.tsx)
- Comprehensive mock data for testing
- Barrel exports from index.ts
- Loading/error/empty state handling
- date-fns for date calculations

### Git Commit Context (Recent Relevant Commits)

```
b2ca8bf feat(timeline): implement vertical list view (Story 10B.3)
bfaa012 feat(summary): implement inline verification for summary sections (Story 10B.2)
0e1485c feat(summary): implement summary tab content (Story 10B.1)
```

**Pattern to follow:**
- Commit message format: `feat(timeline): implement horizontal and multi-track views (Story 10B.4)`
- Test files co-located with components
- Update barrel exports

### Existing Code to Reuse

**From Story 10B.3 (Timeline List View):**
- `frontend/src/types/timeline.ts` - Type definitions (extend, don't replace)
- `frontend/src/hooks/useTimeline.ts` - Data fetching (reuse as-is)
- `frontend/src/hooks/useTimelineStats.ts` - Stats fetching (reuse as-is)
- `frontend/src/components/features/timeline/eventTypeIcons.ts` - Icon mapping
- `frontend/src/components/features/timeline/TimelineEventCard.tsx` - Could reuse for detail panel

**From Summary Tab:**
- Click-to-select pattern with detail display

### Testing Considerations

**Test file structure:**
```typescript
describe('TimelineHorizontal', () => {
  it('renders events on horizontal axis', () => {});
  it('shows year labels', () => {});
  it('clusters nearby events', () => {});
  it('shows gap indicators for significant delays', () => {});
  it('selects event on click', () => {});
  it('updates on zoom change', () => {});
  it('handles empty state', () => {});
});

describe('TimelineMultiTrack', () => {
  it('groups events by actor', () => {});
  it('renders separate tracks for each actor', () => {});
  it('aligns events vertically by date', () => {});
  it('shows track labels', () => {});
  it('selects event on click', () => {});
  it('handles events with no actor', () => {});
});

describe('TimelineZoomSlider', () => {
  it('displays zoom level', () => {});
  it('changes zoom on slider drag', () => {});
  it('zooms in on + button', () => {});
  it('zooms out on - button', () => {});
});

describe('TimelineEventDetail', () => {
  it('displays event information', () => {});
  it('shows View in List button', () => {});
  it('shows View Source button', () => {});
  it('closes on close button', () => {});
});

describe('TimelineContent (view switching)', () => {
  it('renders list view by default', () => {});
  it('switches to horizontal view', () => {});
  it('switches to multi-track view', () => {});
  it('preserves selected event across view changes', () => {});
});

describe('timelineUtils', () => {
  it('calculates scale correctly', () => {});
  it('clusters events within threshold', () => {});
  it('groups events by actor', () => {});
  it('identifies significant gaps', () => {});
});
```

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `Card`, `CardContent` - for event detail panel
- `Badge` - for event type indicators
- `Button` - for view toggle, zoom controls
- `Slider` - for zoom control (if available, else custom)
- `Tooltip`, `TooltipContent`, `TooltipTrigger` - for marker tooltips
- `ScrollArea` - for horizontal scroll container

**Use lucide-react icons:**
- Existing from Story 10B.3: `FileText`, `Gavel`, `Mail`, `Calendar`, etc.
- New for this story:
  - `ZoomIn`, `ZoomOut` - zoom controls
  - `Users` - multi-track view button (replace Table2)
  - `ChevronLeft`, `ChevronRight` - navigation

### Project Structure Notes

**File Locations (MANDATORY):**
- Timeline components go in `components/features/timeline/`
- Types go in `types/timeline.ts`
- Utilities go in `components/features/timeline/timelineUtils.ts` (component-specific)
- Tests are co-located: `ComponentName.test.tsx` next to `ComponentName.tsx`

### Performance Considerations

- Use `useMemo` for expensive calculations (scale, clusters, grouping)
- Virtualize if more than 500 events on horizontal axis
- Debounce zoom slider changes
- Lazy render off-screen tracks in multi-track view
- Use CSS transforms for positioning (GPU accelerated)

### Error Handling

**Empty State:**
```tsx
if (events.length === 0) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium">No Events Found</h3>
      <p className="text-sm text-muted-foreground mt-2">
        Timeline events will appear here once documents are processed.
      </p>
    </div>
  );
}
```

**No Actors for Multi-Track:**
```tsx
if (tracks.length === 0) {
  return (
    <div className="text-center py-8 text-muted-foreground">
      <Users className="h-8 w-8 mx-auto mb-2" />
      <p>No actor information available for multi-track view.</p>
      <p className="text-sm">Events require linked entities to display in tracks.</p>
    </div>
  );
}
```

### References

- [Source: epics.md#story-10b4 - Acceptance criteria]
- [Source: UX-Decisions-Log.md#section-7.2 - Horizontal Timeline Wireframe]
- [Source: UX-Decisions-Log.md#section-7.3 - Multi-Track View Wireframe]
- [Source: UX-Decisions-Log.md#section-7.5 - View Modes]
- [Source: UX-Decisions-Log.md#section-7.6 - Multi-Track Timeline]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: Story 10B.3 - Timeline vertical list patterns]
- [Source: frontend/src/types/timeline.ts - Existing type definitions]
- [Source: frontend/src/components/features/timeline/ - Existing components]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 10 tasks completed successfully
- 168 timeline-specific tests passing
- Lint and TypeScript errors in timeline files resolved
- Added shadcn/ui components: scroll-area, slider
- Added ResizeObserver mock for Radix UI components in tests
- Implementation follows all acceptance criteria:
  - AC #1: View toggle now enables all three modes (List, Horizontal, Multi-Track)
  - AC #2: Horizontal Timeline with zoom slider, event clustering, gap indicators
  - AC #3: Multi-Track view with parallel timelines by actor, vertical date alignment

### File List

**New Files Created:**
- `frontend/src/components/features/timeline/timelineUtils.ts` - Shared timeline utilities
- `frontend/src/components/features/timeline/timelineUtils.test.ts` - Utility tests
- `frontend/src/components/features/timeline/TimelineZoomSlider.tsx` - Zoom control component
- `frontend/src/components/features/timeline/TimelineZoomSlider.test.tsx` - Zoom slider tests
- `frontend/src/components/features/timeline/TimelineEventDetail.tsx` - Event detail panel
- `frontend/src/components/features/timeline/TimelineEventDetail.test.tsx` - Detail panel tests
- `frontend/src/components/features/timeline/TimelineHorizontal.tsx` - Horizontal timeline view
- `frontend/src/components/features/timeline/TimelineHorizontal.test.tsx` - Horizontal view tests
- `frontend/src/components/features/timeline/TimelineMultiTrack.tsx` - Multi-track timeline view
- `frontend/src/components/features/timeline/TimelineMultiTrack.test.tsx` - Multi-track view tests
- `frontend/src/components/ui/scroll-area.tsx` - shadcn scroll-area component
- `frontend/src/components/ui/slider.tsx` - shadcn slider component

**Files Modified:**
- `frontend/src/types/timeline.ts` - Added ZoomLevel, TimelineTrack, EventCluster, TimelineGap, YearLabel, TimelineScale types; changed TimelineViewMode to include 'multitrack'
- `frontend/src/components/features/timeline/TimelineHeader.tsx` - Enabled all view mode buttons, replaced Table2 icon with Users
- `frontend/src/components/features/timeline/TimelineHeader.test.tsx` - Updated tests for enabled buttons
- `frontend/src/components/features/timeline/TimelineContent.tsx` - Added view switching logic for all three modes
- `frontend/src/components/features/timeline/TimelineContent.test.tsx` - Updated tests for view mode switching
- `frontend/src/components/features/timeline/index.ts` - Added exports for new components
- `frontend/vitest.setup.ts` - Added ResizeObserver mock for Radix UI components
