# Story 10B.3: Implement Timeline Tab Vertical List View

Status: completed

## Story

As an **attorney**,
I want **a chronological list of all events**,
So that **I can understand the sequence of the case**.

## Acceptance Criteria

1. **Given** I open the Timeline tab
   **When** the default vertical list loads
   **Then** events are displayed chronologically as cards
   **And** the header shows event count and date range

2. **Given** an event card is displayed
   **When** I view it
   **Then** it shows: date, type icon (Filing, Order, etc.), title, description, actor(s), source document+page, cross-references, verification status, contradiction flag if applicable

3. **Given** events have duration between them
   **When** the list renders
   **Then** connector lines show duration between events
   **And** large gaps are visually emphasized

## Tasks / Subtasks

- [x] Task 1: Create Timeline types and API hooks (AC: All)
  - [x] 1.1: Create `frontend/src/types/timeline.ts` with TimelineEvent, TimelineStats, etc.
  - [x] 1.2: Create `frontend/src/hooks/useTimeline.ts` with SWR hook for `/api/matters/{matterId}/timeline/full`
  - [x] 1.3: Create `frontend/src/hooks/useTimelineStats.ts` for `/api/matters/{matterId}/timeline/stats`
  - [x] 1.4: Export from `frontend/src/types/index.ts` and `frontend/src/hooks/index.ts`

- [x] Task 2: Create TimelineHeader component (AC: #1)
  - [x] 2.1: Create `frontend/src/components/features/timeline/TimelineHeader.tsx`
  - [x] 2.2: Display event count (e.g., "47 events")
  - [x] 2.3: Display date range (e.g., "May 2016 - Jan 2024")
  - [x] 2.4: Add view mode toggle buttons placeholder: [List] [Horizontal] [Table] (only List active for this story)
  - [x] 2.5: Create `TimelineHeader.test.tsx`

- [x] Task 3: Create TimelineEventCard component (AC: #2)
  - [x] 3.1: Create `frontend/src/components/features/timeline/TimelineEventCard.tsx`
  - [x] 3.2: Display date with appropriate formatting (day, month, year precision)
  - [x] 3.3: Display type icon using event type mapping (Filing, Order, Notice, Hearing, Transaction, Document, Deadline)
  - [x] 3.4: Display title/description
  - [x] 3.5: Display actor(s) with entity links to Entities tab
  - [x] 3.6: Display source document + page with clickable link
  - [x] 3.7: Display cross-references if available
  - [x] 3.8: Display verification status badge (Verified/Pending)
  - [x] 3.9: Display contradiction flag if event has conflicts
  - [x] 3.10: Add skeleton variant for loading state
  - [x] 3.11: Create `TimelineEventCard.test.tsx`

- [x] Task 4: Create TimelineConnector component (AC: #3)
  - [x] 4.1: Create `frontend/src/components/features/timeline/TimelineConnector.tsx`
  - [x] 4.2: Display vertical line between events
  - [x] 4.3: Show duration text (e.g., "← 2 years, 1 month")
  - [x] 4.4: Visually emphasize large gaps (> 90 days) with warning styling
  - [x] 4.5: Add gap detection messaging for significant delays
  - [x] 4.6: Create `TimelineConnector.test.tsx`

- [x] Task 5: Create TimelineList component (AC: All)
  - [x] 5.1: Create `frontend/src/components/features/timeline/TimelineList.tsx`
  - [x] 5.2: Render events in chronological order with year separators
  - [x] 5.3: Insert TimelineConnector between events
  - [x] 5.4: Handle empty state (no events)
  - [x] 5.5: Handle loading state with skeleton
  - [x] 5.6: Handle error state with alert
  - [ ] 5.7: Implement virtualization for large event lists (> 100 events) - DEFERRED to future optimization
  - [x] 5.8: Create `TimelineList.test.tsx`

- [x] Task 6: Create TimelineContent main component (AC: All)
  - [x] 6.1: Create `frontend/src/components/features/timeline/TimelineContent.tsx`
  - [x] 6.2: Compose TimelineHeader + TimelineList
  - [x] 6.3: Fetch timeline data using useTimeline hook
  - [x] 6.4: Fetch stats using useTimelineStats hook
  - [x] 6.5: Create `TimelineContent.test.tsx`

- [x] Task 7: Update Timeline tab page (AC: All)
  - [x] 7.1: Update `frontend/src/app/(matter)/[matterId]/timeline/page.tsx` to render TimelineContent
  - [x] 7.2: Ensure proper tab panel accessibility attributes
  - [x] 7.3: Add loading.tsx for suspense boundary

- [x] Task 8: Create barrel exports and integrate (AC: All)
  - [x] 8.1: Create `frontend/src/components/features/timeline/index.ts` barrel export
  - [x] 8.2: Verify exports from types and hooks index files

- [x] Task 9: Write comprehensive tests (AC: All)
  - [x] 9.1: Test Timeline page rendering with mock data
  - [x] 9.2: Test event card displays all required fields
  - [x] 9.3: Test connector shows duration between events
  - [x] 9.4: Test gap detection for large time gaps
  - [x] 9.5: Test year separators render correctly
  - [x] 9.6: Test loading skeleton state
  - [x] 9.7: Test error state display
  - [x] 9.8: Test entity navigation links
  - [x] 9.9: Test document source links

## Dev Notes

### Critical Architecture Patterns

**Timeline Tab UX (from UX-Decisions-Log.md Section 7.1):**

The Timeline tab displays events in a vertical list with:
- Year separators (2016, 2018, etc.)
- Event cards with full details
- Connector lines showing duration between events
- Gap detection with visual warnings

**Event Types and Icons (from UX-Decisions-Log.md Section 7.3):**
| Icon | Type | Examples |
|------|------|----------|
| FileText | filing | Petitions, applications, affidavits |
| Gavel | order | Court orders, judgments, rulings |
| Mail | notice | Notices sent, received, served |
| Calendar | hearing | Court hearings, appearances |
| CreditCard | transaction | Financial transactions, transfers |
| File | document | Documents submitted, received |
| Clock | deadline | Statutory deadlines, due dates |

**Component Structure:**
```
frontend/src/
├── app/(matter)/[matterId]/timeline/
│   ├── page.tsx                          # UPDATE - Replace placeholder
│   └── loading.tsx                       # NEW - Suspense loading
├── components/features/timeline/          # NEW - Timeline tab components
│   ├── TimelineHeader.tsx                # NEW
│   ├── TimelineHeader.test.tsx           # NEW
│   ├── TimelineEventCard.tsx             # NEW
│   ├── TimelineEventCard.test.tsx        # NEW
│   ├── TimelineConnector.tsx             # NEW
│   ├── TimelineConnector.test.tsx        # NEW
│   ├── TimelineList.tsx                  # NEW
│   ├── TimelineList.test.tsx             # NEW
│   ├── TimelineContent.tsx               # NEW
│   ├── TimelineContent.test.tsx          # NEW
│   └── index.ts                          # NEW - Barrel export
├── types/
│   ├── timeline.ts                       # NEW - Timeline type definitions
│   └── index.ts                          # UPDATE - Add timeline exports
└── hooks/
    ├── useTimeline.ts                    # NEW - Timeline data hook
    ├── useTimelineStats.ts               # NEW - Timeline stats hook
    └── index.ts                          # UPDATE - Add hook exports
```

### TypeScript Type Definitions

```typescript
// types/timeline.ts

import type { EntityReference } from './entity';

/**
 * Event types for timeline (from backend EventType enum)
 */
export type TimelineEventType =
  | 'filing'
  | 'notice'
  | 'hearing'
  | 'order'
  | 'transaction'
  | 'document'
  | 'deadline'
  | 'unclassified'
  | 'raw_date';

/**
 * Date precision levels
 */
export type DatePrecision = 'day' | 'month' | 'year' | 'approximate';

/**
 * Timeline event entity reference
 */
export interface TimelineEntityReference {
  entityId: string;
  canonicalName: string;
  entityType: string;
  role: string | null;
}

/**
 * Timeline event from API
 */
export interface TimelineEvent {
  /** Event UUID */
  id: string;
  /** Event date */
  eventDate: string; // ISO date
  /** Date precision */
  eventDatePrecision: DatePrecision;
  /** Original date text from document */
  eventDateText: string | null;
  /** Classified event type */
  eventType: TimelineEventType;
  /** Event description/context */
  description: string;
  /** Source document ID */
  documentId: string | null;
  /** Source page number */
  sourcePage: number | null;
  /** Classification confidence */
  confidence: number;
  /** Linked entities (actors) */
  entities: TimelineEntityReference[];
  /** Whether date is ambiguous */
  isAmbiguous: boolean;
  /** Whether manually verified */
  isVerified: boolean;
  /** Cross-references (future: document references) */
  crossReferences?: string[];
  /** Contradiction flag */
  hasContradiction?: boolean;
  /** Contradiction details if flagged */
  contradictionDetails?: string;
}

/**
 * Timeline statistics from stats endpoint
 */
export interface TimelineStats {
  /** Total events count */
  totalEvents: number;
  /** Events by type */
  eventsByType: Record<string, number>;
  /** Number of entities involved */
  entitiesInvolved: number;
  /** Earliest event date */
  dateRangeStart: string | null; // ISO date
  /** Latest event date */
  dateRangeEnd: string | null; // ISO date
  /** Events with entity links */
  eventsWithEntities: number;
  /** Events without entity links */
  eventsWithoutEntities: number;
  /** Verified events count */
  verifiedEvents: number;
}

/**
 * Pagination meta from API
 */
export interface TimelinePaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/**
 * Timeline API response
 */
export interface TimelineResponse {
  data: TimelineEvent[];
  meta: TimelinePaginationMeta;
}

/**
 * Timeline stats API response
 */
export interface TimelineStatsResponse {
  data: TimelineStats;
}
```

### Data Fetching Pattern (SWR)

```typescript
// hooks/useTimeline.ts
import useSWR from 'swr';
import type { TimelineResponse, TimelineEvent } from '@/types/timeline';

const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch timeline');
  return res.json();
};

interface UseTimelineOptions {
  eventType?: string;
  entityId?: string;
  page?: number;
  perPage?: number;
}

export function useTimeline(matterId: string, options: UseTimelineOptions = {}) {
  const { eventType, entityId, page = 1, perPage = 50 } = options;

  const params = new URLSearchParams();
  if (eventType) params.set('event_type', eventType);
  if (entityId) params.set('entity_id', entityId);
  params.set('page', String(page));
  params.set('per_page', String(perPage));

  const { data, error, isLoading, mutate } = useSWR<TimelineResponse>(
    matterId ? `/api/matters/${matterId}/timeline/full?${params.toString()}` : null,
    fetcher
  );

  return {
    events: data?.data ?? [],
    meta: data?.meta,
    isLoading,
    isError: !!error,
    mutate,
  };
}
```

### Backend API Endpoints (Already Implemented)

**Timeline endpoints from backend/app/api/routes/timeline.py:**

1. `GET /api/matters/{matter_id}/timeline/full` - Get timeline with entity info
   - Query params: `event_type`, `entity_id`, `include_raw`, `page`, `per_page`
   - Returns: `TimelineWithEntitiesResponse`

2. `GET /api/matters/{matter_id}/timeline/stats` - Get timeline statistics
   - Returns: `TimelineStatisticsResponse`

3. `GET /api/matters/{matter_id}/timeline/events` - Get classified events
   - Query params: `event_type`, `confidence_min`, `page`, `per_page`
   - Returns: `ClassifiedEventsListResponse`

**Response shape (from backend models):**
```python
# TimelineEventWithEntities
{
  "id": "uuid",
  "event_date": "2024-01-15",
  "event_date_precision": "day",
  "event_date_text": "15th January 2024",
  "event_type": "filing",
  "description": "Petition filed before Special Court",
  "document_id": "doc-uuid",
  "source_page": 1,
  "confidence": 0.95,
  "entities": [
    {
      "entity_id": "entity-uuid",
      "canonical_name": "Nirav D. Jobalia",
      "entity_type": "PERSON",
      "role": "petitioner"
    }
  ],
  "is_ambiguous": false,
  "is_verified": true
}
```

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `Card`, `CardHeader`, `CardContent` - for event cards
- `Badge` - for event type and verification status
- `Button` - for action buttons
- `Skeleton` - for loading states
- `Alert`, `AlertTitle`, `AlertDescription` - for errors
- `Separator` - for year separators
- `Tooltip`, `TooltipContent`, `TooltipTrigger` - for date and actor tooltips

**Use lucide-react icons:**
- `FileText` - filing events
- `Gavel` - order events
- `Mail` - notice events
- `Calendar` - hearing events
- `CreditCard` - transaction events
- `File` - document events
- `Clock` - deadline events
- `HelpCircle` - unclassified events
- `CheckCircle2` - verified status
- `AlertTriangle` - contradiction flag
- `ExternalLink` - source document link
- `User` - actor/entity

### Event Type Icon Mapping

```typescript
// components/features/timeline/eventTypeIcons.ts
import {
  FileText,
  Gavel,
  Mail,
  Calendar,
  CreditCard,
  File,
  Clock,
  HelpCircle,
  LucideIcon,
} from 'lucide-react';
import type { TimelineEventType } from '@/types/timeline';

export const EVENT_TYPE_ICONS: Record<TimelineEventType, LucideIcon> = {
  filing: FileText,
  order: Gavel,
  notice: Mail,
  hearing: Calendar,
  transaction: CreditCard,
  document: File,
  deadline: Clock,
  unclassified: HelpCircle,
  raw_date: HelpCircle,
};

export const EVENT_TYPE_LABELS: Record<TimelineEventType, string> = {
  filing: 'Case Filed',
  order: 'Order',
  notice: 'Notice',
  hearing: 'Hearing',
  transaction: 'Transaction',
  document: 'Document',
  deadline: 'Deadline',
  unclassified: 'Unclassified',
  raw_date: 'Raw Date',
};

export const EVENT_TYPE_COLORS: Record<TimelineEventType, string> = {
  filing: 'bg-blue-100 text-blue-800',
  order: 'bg-purple-100 text-purple-800',
  notice: 'bg-amber-100 text-amber-800',
  hearing: 'bg-green-100 text-green-800',
  transaction: 'bg-pink-100 text-pink-800',
  document: 'bg-gray-100 text-gray-800',
  deadline: 'bg-red-100 text-red-800',
  unclassified: 'bg-slate-100 text-slate-600',
  raw_date: 'bg-slate-100 text-slate-600',
};
```

### TimelineEventCard Component Pattern

```typescript
// components/features/timeline/TimelineEventCard.tsx
'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { CheckCircle2, AlertTriangle, ExternalLink, User } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { format, parseISO } from 'date-fns';
import { cn } from '@/lib/utils';
import { EVENT_TYPE_ICONS, EVENT_TYPE_LABELS, EVENT_TYPE_COLORS } from './eventTypeIcons';
import type { TimelineEvent } from '@/types/timeline';

interface TimelineEventCardProps {
  event: TimelineEvent;
  /** Optional className */
  className?: string;
}

export function TimelineEventCard({ event, className }: TimelineEventCardProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  const Icon = EVENT_TYPE_ICONS[event.eventType] ?? EVENT_TYPE_ICONS.unclassified;
  const typeLabel = EVENT_TYPE_LABELS[event.eventType] ?? 'Event';
  const typeColor = EVENT_TYPE_COLORS[event.eventType] ?? EVENT_TYPE_COLORS.unclassified;

  // Format date based on precision
  const formatEventDate = () => {
    const date = parseISO(event.eventDate);
    switch (event.eventDatePrecision) {
      case 'day':
        return format(date, 'MMMM d, yyyy');
      case 'month':
        return format(date, 'MMMM yyyy');
      case 'year':
        return format(date, 'yyyy');
      case 'approximate':
        return `~${format(date, 'MMMM d, yyyy')}`;
      default:
        return format(date, 'MMMM d, yyyy');
    }
  };

  return (
    <Card className={cn('relative', className)}>
      <CardContent className="pt-4">
        {/* Date */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <span className="font-medium">{formatEventDate()}</span>
          {event.eventDateText && event.eventDateText !== event.eventDate && (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-xs italic cursor-help">
                  ({event.eventDateText})
                </span>
              </TooltipTrigger>
              <TooltipContent>Original text from document</TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Event Type Badge + Title */}
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="secondary" className={cn('flex items-center gap-1', typeColor)}>
            <Icon className="h-3 w-3" />
            <span>{typeLabel.toUpperCase()}</span>
          </Badge>
          {event.isVerified && (
            <Badge variant="outline" className="text-green-600 border-green-500">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Verified
            </Badge>
          )}
          {event.hasContradiction && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" className="text-amber-600 border-amber-500 cursor-help">
                  <AlertTriangle className="h-3 w-3 mr-1" />
                  Contradiction
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                {event.contradictionDetails ?? 'This event has conflicting information'}
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Description */}
        <p className="text-sm text-foreground mb-3">{event.description}</p>

        {/* Actors (Entities) */}
        {event.entities.length > 0 && (
          <div className="flex items-center gap-2 mb-2 text-sm">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Actor:</span>
            {event.entities.map((entity, idx) => (
              <span key={entity.entityId}>
                <Link
                  href={`/matters/${matterId}/entities?entity=${entity.entityId}`}
                  className="text-blue-600 hover:text-blue-800 hover:underline"
                >
                  {entity.canonicalName}
                </Link>
                {entity.role && (
                  <span className="text-muted-foreground"> ({entity.role})</span>
                )}
                {idx < event.entities.length - 1 && ', '}
              </span>
            ))}
          </div>
        )}

        {/* Source Document */}
        {event.documentId && (
          <div className="flex items-center gap-2 text-sm">
            <ExternalLink className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Source:</span>
            <Link
              href={`/matters/${matterId}/documents?doc=${event.documentId}${event.sourcePage ? `&page=${event.sourcePage}` : ''}`}
              className="text-blue-600 hover:text-blue-800 hover:underline"
            >
              {event.sourcePage ? `Document, pg ${event.sourcePage}` : 'Document'}
            </Link>
          </div>
        )}

        {/* Cross-references (if available) */}
        {event.crossReferences && event.crossReferences.length > 0 && (
          <div className="mt-2 text-sm text-muted-foreground">
            <span>Cross-ref: {event.crossReferences.join(', ')}</span>
          </div>
        )}

        {/* Low confidence warning */}
        {event.confidence < 0.7 && !event.isVerified && (
          <div className="mt-2 text-xs text-amber-600 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            Low confidence ({Math.round(event.confidence * 100)}%) - needs verification
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

### TimelineConnector Component Pattern

```typescript
// components/features/timeline/TimelineConnector.tsx
import { cn } from '@/lib/utils';
import { differenceInDays, differenceInMonths, differenceInYears, parseISO } from 'date-fns';

interface TimelineConnectorProps {
  /** Previous event date (ISO) */
  fromDate: string;
  /** Next event date (ISO) */
  toDate: string;
  /** Additional className */
  className?: string;
}

const SIGNIFICANT_GAP_DAYS = 90; // 3 months

export function TimelineConnector({ fromDate, toDate, className }: TimelineConnectorProps) {
  const from = parseISO(fromDate);
  const to = parseISO(toDate);

  const days = differenceInDays(to, from);
  const months = differenceInMonths(to, from);
  const years = differenceInYears(to, from);

  // Format duration
  const formatDuration = () => {
    if (years >= 1) {
      const remainingMonths = months % 12;
      if (remainingMonths > 0) {
        return `${years} year${years > 1 ? 's' : ''}, ${remainingMonths} month${remainingMonths > 1 ? 's' : ''}`;
      }
      return `${years} year${years > 1 ? 's' : ''}`;
    }
    if (months >= 1) {
      return `${months} month${months > 1 ? 's' : ''}`;
    }
    return `${days} day${days > 1 ? 's' : ''}`;
  };

  const isSignificantGap = days > SIGNIFICANT_GAP_DAYS;

  return (
    <div className={cn('flex items-center py-2 pl-6', className)}>
      {/* Vertical connector line */}
      <div
        className={cn(
          'w-0.5 h-8 mr-4',
          isSignificantGap ? 'bg-amber-400' : 'bg-border'
        )}
      />

      {/* Duration text */}
      <span
        className={cn(
          'text-xs',
          isSignificantGap ? 'text-amber-600 font-medium' : 'text-muted-foreground'
        )}
      >
        ← {formatDuration()}
        {isSignificantGap && days > 180 && ' (SIGNIFICANT DELAY)'}
      </span>
    </div>
  );
}
```

### Year Separator Pattern

```typescript
// Year separator within TimelineList
<div className="sticky top-0 z-10 bg-background border-b py-2 mb-4">
  <h3 className="text-lg font-semibold text-foreground">{year}</h3>
</div>
```

### Zustand Store Pattern (MANDATORY)

```typescript
// CORRECT - Selector pattern
const activeTab = useWorkspaceStore((state) => state.activeTab);

// WRONG - Full store subscription
const { activeTab } = useWorkspaceStore();
```

### Naming Conventions (from project-context.md)

| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `TimelineEventCard`, `TimelineConnector` |
| Component files | PascalCase.tsx | `TimelineEventCard.tsx` |
| Hooks | camelCase with `use` prefix | `useTimeline`, `useTimelineStats` |
| Functions | camelCase | `formatEventDate`, `formatDuration` |
| Constants | SCREAMING_SNAKE | `EVENT_TYPE_ICONS`, `SIGNIFICANT_GAP_DAYS` |
| Types/Interfaces | PascalCase | `TimelineEvent`, `TimelineStats` |

### Accessibility Requirements

- Timeline list has appropriate role and ARIA labels
- Event cards are keyboard navigable
- Date and type information announced by screen readers
- Source links have descriptive aria-labels
- Entity links announce destination
- Tab panel has `role="tabpanel"` with `aria-labelledby="tab-timeline"`
- Year separators are landmarks for navigation

### Previous Story Intelligence (Story 10B.1, 10B.2)

**From Story 10B.1/10B.2 implementation:**
- Summary tab pattern: SummaryContent component fetches data via hook, composes child components
- Uses SWR for data fetching
- Uses shadcn/ui Card, Badge, Button components
- Types defined in `types/` directory
- Hooks in `hooks/` directory
- Next.js Link for navigation
- Co-located test files

**Patterns established:**
- Comprehensive test coverage for all new components
- Co-located test files (ComponentName.test.tsx)
- Mock implementations for APIs
- Barrel exports from index.ts files
- Loading/error state handling

### Git Commit Context (Recent Relevant Commits)

```
bfaa012 feat(summary): implement inline verification for summary sections (Story 10B.2)
f1d8023 fix(security): code review fixes for Epic 1 - critical security patches
d128a40 fix(review): code review fixes for Story 10B.1
0e1485c feat(summary): implement summary tab content (Story 10B.1)
```

**Patterns to follow:**
- Commit message format: `feat(timeline): implement vertical list view (Story 10B.3)`
- Code review identifies HIGH/MEDIUM issues to fix
- Test files co-located with components

### Existing Code to Reuse

**From Summary tab components:**
- `frontend/src/components/features/summary/SummaryContent.tsx` - Component composition pattern
- `frontend/src/hooks/useMatterSummary.ts` - SWR hook pattern

**Backend timeline service:**
- `backend/app/api/routes/timeline.py` - API endpoints (already implemented)
- `backend/app/models/timeline.py` - Data models and types

**Workspace components:**
- `frontend/src/app/(matter)/[matterId]/summary/page.tsx` - Tab page pattern
- `frontend/src/stores/workspaceStore.ts` - Tab state management

### Testing Considerations

**Test file structure:**
```typescript
describe('TimelineHeader', () => {
  it('displays event count', () => {});
  it('displays date range', () => {});
  it('shows view mode toggles with List active', () => {});
});

describe('TimelineEventCard', () => {
  it('renders date with correct formatting', () => {});
  it('renders event type icon and badge', () => {});
  it('renders description', () => {});
  it('renders actor links to entities tab', () => {});
  it('renders source document link', () => {});
  it('shows verified badge when verified', () => {});
  it('shows contradiction warning when flagged', () => {});
  it('shows low confidence warning', () => {});
});

describe('TimelineConnector', () => {
  it('shows duration between events', () => {});
  it('emphasizes significant gaps', () => {});
  it('formats duration correctly for years', () => {});
  it('formats duration correctly for months', () => {});
  it('formats duration correctly for days', () => {});
});

describe('TimelineList', () => {
  it('renders events in chronological order', () => {});
  it('shows year separators', () => {});
  it('shows connectors between events', () => {});
  it('handles empty state', () => {});
});

describe('TimelineContent', () => {
  it('renders header and list', () => {});
  it('shows loading state', () => {});
  it('shows error state', () => {});
});
```

### Project Structure Notes

**File Locations (MANDATORY):**
- Timeline components go in `components/features/timeline/` (NOT `components/timeline/`)
- Types go in `types/timeline.ts` (NOT inline in components)
- Hooks go in `hooks/useTimeline.ts` (NOT in component files)
- Tests are co-located: `ComponentName.test.tsx` next to `ComponentName.tsx`

### Error Handling

**Loading State:**
```tsx
if (isLoading) {
  return <TimelineListSkeleton />;
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
        Failed to load timeline data. Please try refreshing the page.
      </AlertDescription>
    </Alert>
  );
}
```

**Empty State:**
```tsx
if (events.length === 0) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Clock className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium">No Events Found</h3>
      <p className="text-sm text-muted-foreground mt-2">
        Timeline events will appear here once documents are processed.
      </p>
    </div>
  );
}
```

### Dependencies to Install

- `date-fns` - Date formatting and calculations (likely already installed, verify)

### References

- [Source: epics.md#story-10b3 - Acceptance criteria]
- [Source: UX-Decisions-Log.md#section-7.1 - Timeline Tab Vertical List View wireframe]
- [Source: UX-Decisions-Log.md#section-7.3 - Event Types and Icons]
- [Source: architecture.md#frontend-structure - Component organization]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: Story 10B.1 - Summary tab patterns]
- [Source: Story 10B.2 - Verification badge patterns]
- [Source: backend/app/api/routes/timeline.py - API endpoints]
- [Source: backend/app/models/timeline.py - Data models]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

1. **All acceptance criteria met:**
   - AC #1: Timeline header shows event count and date range with view mode toggle
   - AC #2: Event cards display all required fields (date, type icon, description, actors, source, cross-refs, verification, contradiction)
   - AC #3: Connector lines show duration between events with gap emphasis for large delays

2. **Implementation includes:**
   - Full TypeScript types matching backend models
   - SWR hooks with mock data for MVP (real API calls ready to enable)
   - Comprehensive test coverage: 96 tests all passing
   - Proper accessibility with ARIA labels and roles
   - Loading/error/empty state handling
   - Dark mode support

3. **Deferred to future optimization:**
   - Task 5.7: Virtualization for large event lists (> 100 events) - not needed for MVP demo data

4. **Dependencies added:**
   - date-fns: For date formatting and duration calculations

### File List

**New Files:**
- frontend/src/types/timeline.ts
- frontend/src/hooks/useTimeline.ts
- frontend/src/hooks/useTimelineStats.ts
- frontend/src/components/features/timeline/index.ts
- frontend/src/components/features/timeline/eventTypeIcons.ts
- frontend/src/components/features/timeline/TimelineHeader.tsx
- frontend/src/components/features/timeline/TimelineHeader.test.tsx
- frontend/src/components/features/timeline/TimelineEventCard.tsx
- frontend/src/components/features/timeline/TimelineEventCard.test.tsx
- frontend/src/components/features/timeline/TimelineConnector.tsx
- frontend/src/components/features/timeline/TimelineConnector.test.tsx
- frontend/src/components/features/timeline/TimelineList.tsx
- frontend/src/components/features/timeline/TimelineList.test.tsx
- frontend/src/components/features/timeline/TimelineContent.tsx
- frontend/src/components/features/timeline/TimelineContent.test.tsx
- frontend/src/app/(matter)/[matterId]/timeline/loading.tsx

**Modified Files:**
- frontend/src/types/index.ts
- frontend/src/hooks/index.ts
- frontend/src/app/(matter)/[matterId]/timeline/page.tsx
- frontend/package.json (date-fns added)

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.5 | **Date:** 2026-01-15

### Issues Found & Fixed

| ID | Severity | Issue | Resolution |
|----|----------|-------|------------|
| H1 | HIGH | ESLint error - component created during render in TimelineEventCard.tsx | Fixed: Changed from `getEventTypeIcon()` function to direct constant access `EVENT_TYPE_ICONS[event.eventType]` |
| M1 | MEDIUM | Unused `realFetcher` function in useTimeline.ts | Fixed: Added `eslint-disable-next-line` comment with TODO tracking |
| M2 | MEDIUM | Unused `_url` param and `realFetcher` in useTimelineStats.ts | Fixed: Removed unused param, added eslint-disable with TODO |
| M3 | MEDIUM | Undocumented backend changes (python-multipart) | Fixed: Reverted changes not in story scope |
| L1 | LOW | Missing TODO tracking for mock-to-real API switch | Fixed: Added `TODO(Story-10B.5)` comments |

### Additional Fixes (Pre-existing Issues)

| File | Issue | Resolution |
|------|-------|------------|
| ShareDialog.tsx | Type error: `string \| undefined` not assignable to `string` | Fixed: Added nullish coalescing `?? emailToInvite` |
| WorkspaceTabBar.tsx | TypeScript readonly array assignment error | Fixed: Removed `as const satisfies`, added bounds check |

### Verification Summary

- **Lint:** ✅ Passes (0 errors, 0 warnings)
- **Timeline Tests:** ✅ 96/96 passing
- **TypeScript:** ✅ No timeline-related errors
- **Acceptance Criteria:** ✅ All 3 ACs verified

### Outcome

**APPROVED** - All issues fixed, story ready for merge.
