# Story 10B.5: Implement Timeline Tab Filtering and Manual Addition

Status: complete

## Story

As an **attorney**,
I want **to filter timeline events and add manual entries**,
So that **I can focus on specific events and add missing information**.

## Acceptance Criteria

1. **Given** I am in the Timeline tab
   **When** I use filter controls
   **Then** I can filter by: Event Type, Actors, Date Range, Verification Status
   **And** the timeline updates to show only matching events

2. **Given** I click "Add Event"
   **When** the dialog opens
   **Then** I can enter: date, type, title, description, actor, source
   **And** the event is marked as "Manually added"

3. **Given** I add a manual event
   **When** it is saved
   **Then** it appears in the timeline at the correct chronological position
   **And** it can be edited or deleted

## Tasks / Subtasks

- [x] Task 1: Update timeline types for filtering and manual events (AC: All)
  - [x] 1.1: Add `TimelineFilterState` interface to `frontend/src/types/timeline.ts` with: eventTypes[], entityIds[], dateRange (start/end), verificationStatus (all/verified/unverified)
  - [x] 1.2: Add `ManualTimelineEvent` interface for creating/editing manual events (date, type, title, description, actors, source)
  - [x] 1.3: Add `ManualEventCreateRequest` and `ManualEventResponse` types for API integration
  - [x] 1.4: Export all new types from `frontend/src/types/index.ts`

- [x] Task 2: Create TimelineFilterBar component (AC: #1)
  - [x] 2.1: Create `frontend/src/components/features/timeline/TimelineFilterBar.tsx`
  - [x] 2.2: Add event type multi-select dropdown using existing TimelineEventType options
  - [x] 2.3: Add actor (entity) multi-select dropdown - fetch from `/api/matters/{matterId}/timeline/entities`
  - [x] 2.4: Add date range picker with start/end date inputs
  - [x] 2.5: Add verification status toggle (All / Verified / Unverified)
  - [x] 2.6: Add "Clear Filters" button to reset all filters
  - [x] 2.7: Display active filter count badge when filters are applied
  - [x] 2.8: Implement responsive layout (collapse to popover on mobile)
  - [x] 2.9: Create `TimelineFilterBar.test.tsx`

- [x] Task 3: Create AddEventDialog component (AC: #2, #3)
  - [x] 3.1: Create `frontend/src/components/features/timeline/AddEventDialog.tsx`
  - [x] 3.2: Implement form fields: date picker, event type select, title input, description textarea
  - [x] 3.3: Add actor multi-select (from matter entities) with "Add new actor" option
  - [x] 3.4: Add optional source document reference (document select + page number)
  - [x] 3.5: Add form validation (date required, title required, max lengths)
  - [x] 3.6: Display "This event will be marked as manually added" info badge
  - [x] 3.7: Handle submit with loading state and success/error toast
  - [x] 3.8: Create `AddEventDialog.test.tsx`

- [x] Task 4: Create EditEventDialog component (AC: #3)
  - [x] 4.1: Create `frontend/src/components/features/timeline/EditEventDialog.tsx`
  - [x] 4.2: Reuse form structure from AddEventDialog (extract shared FormFields component if needed)
  - [x] 4.3: Pre-populate fields from existing event data
  - [x] 4.4: Show "Edit Manual Event" title for manual events, "Edit Event Classification" for auto events
  - [x] 4.5: For auto events, only allow editing: event_type (classification correction), not date/description
  - [x] 4.6: Handle update with loading state and success/error toast
  - [x] 4.7: Create `EditEventDialog.test.tsx`

- [x] Task 5: Create DeleteEventConfirmation component (AC: #3)
  - [x] 5.1: Create `frontend/src/components/features/timeline/DeleteEventConfirmation.tsx`
  - [x] 5.2: Use AlertDialog from shadcn/ui for confirmation
  - [x] 5.3: Show warning: "This cannot be undone" for manual events
  - [x] 5.4: For auto-extracted events, hide delete (only allow classification edit)
  - [x] 5.5: Handle delete with loading state and success toast
  - [x] 5.6: Create `DeleteEventConfirmation.test.tsx`

- [x] Task 6: Update useTimeline hook for filtering (AC: #1)
  - [x] 6.1: Update `frontend/src/hooks/useTimeline.ts` to accept filter parameters
  - [x] 6.2: Add `eventTypes: string[]` filter (maps to multiple `event_type` query params or comma-separated)
  - [x] 6.3: Add `entityIds: string[]` filter (maps to `entity_id` - NOTE: backend only supports single entity, may need multiple calls or backend update)
  - [x] 6.4: Add `startDate: string` and `endDate: string` date range filters
  - [x] 6.5: Add `verificationStatus: 'all' | 'verified' | 'unverified'` filter
  - [x] 6.6: Update mock fetcher to apply filters to mock data
  - [x] 6.7: Comment realFetcher with TODO for backend filter support

- [x] Task 7: Create manual event API functions (AC: #2, #3)
  - [x] 7.1: Create `frontend/src/lib/api/timeline.ts` if not exists
  - [x] 7.2: Add `createManualEvent(matterId, event)` function - POST to `/api/matters/{matterId}/timeline/events`
  - [x] 7.3: Add `updateEvent(matterId, eventId, updates)` function - PATCH to `/api/matters/{matterId}/timeline/events/{eventId}`
  - [x] 7.4: Add `deleteEvent(matterId, eventId)` function - DELETE to `/api/matters/{matterId}/timeline/events/{eventId}`
  - [x] 7.5: Add mock implementations for MVP (store in localStorage for persistence across sessions)
  - [x] 7.6: Handle optimistic updates with SWR mutate

- [x] Task 8: Update TimelineHeader component (AC: #1, #2)
  - [x] 8.1: Add "Add Event" button with Plus icon next to view mode toggle
  - [x] 8.2: Add onClick handler to open AddEventDialog
  - [x] 8.3: Add filter toggle button (Filter icon) to show/hide TimelineFilterBar
  - [x] 8.4: Show active filter count badge on filter button when filters applied
  - [x] 8.5: Update event count display to show "X of Y events" when filtered
  - [x] 8.6: Update tests for new buttons and states

- [x] Task 9: Update TimelineContent component (AC: All)
  - [x] 9.1: Add filter state management: `const [filters, setFilters] = useState<TimelineFilterState>(defaultFilters)`
  - [x] 9.2: Add `showFilterBar` state toggle
  - [x] 9.3: Add dialog state management for Add/Edit/Delete dialogs
  - [x] 9.4: Pass filters to useTimeline hook
  - [x] 9.5: Render TimelineFilterBar conditionally based on showFilterBar
  - [x] 9.6: Pass onEventEdit and onEventDelete callbacks to all timeline views
  - [x] 9.7: Render AddEventDialog with controlled open state
  - [x] 9.8: Render EditEventDialog with selected event
  - [x] 9.9: Render DeleteEventConfirmation with selected event
  - [x] 9.10: After successful add/edit/delete, call mutate to refresh data
  - [x] 9.11: Update tests for filter and dialog integration

- [x] Task 10: Update TimelineEventCard component (AC: #3)
  - [x] 10.1: Add "Manually added" badge for `is_manual: true` events
  - [x] 10.2: Add context menu (three dots) with Edit and Delete options for manual events
  - [x] 10.3: For auto events, only show "Edit Classification" option (no delete)
  - [x] 10.4: Add onClick handlers for context menu items
  - [x] 10.5: Update tests for manual event display and context menu

- [x] Task 11: Update horizontal and multi-track views for manual events (AC: #3)
  - [x] 11.1: Update TimelineHorizontal markers to show "manual" indicator
  - [x] 11.2: Update TimelineMultiTrack to support edit/delete on manual events
  - [x] 11.3: Update TimelineEventDetail to show Edit/Delete buttons for manual events
  - [x] 11.4: Update tests for manual event handling in alternative views

- [x] Task 12: Backend API updates (AC: All)
  - [x] 12.1: Add POST `/api/matters/{matterId}/timeline/events` endpoint for creating manual events
  - [x] 12.2: Add DELETE `/api/matters/{matterId}/timeline/events/{eventId}` endpoint (only for is_manual=true)
  - [x] 12.3: Filtering handled client-side for better UX (backend returns all events, frontend filters)
  - [x] 12.4: Verification status filtering handled client-side (is_verified in response)
  - [x] 12.5: Add `is_manual` field to TimelineEventWithEntities response model
  - [x] 12.6: No database migration needed (events table already has is_manual and created_by columns)
  - [x] 12.7: All 61 existing timeline tests pass + new endpoints use existing patterns

- [x] Task 13: Write comprehensive tests (AC: All)
  - [x] 13.1: Test filter bar renders all filter options
  - [x] 13.2: Test event type filter updates timeline
  - [x] 13.3: Test actor filter updates timeline
  - [x] 13.4: Test date range filter updates timeline
  - [x] 13.5: Test verification status filter updates timeline
  - [x] 13.6: Test clear filters resets all filters
  - [x] 13.7: Test Add Event dialog opens and closes
  - [x] 13.8: Test Add Event form validation
  - [x] 13.9: Test Add Event creates new event in timeline
  - [x] 13.10: Test Edit Event dialog opens with event data
  - [x] 13.11: Test Edit Event updates event
  - [x] 13.12: Test Delete Event confirmation shows for manual events
  - [x] 13.13: Test Delete Event removes event from timeline
  - [x] 13.14: Test manual events show "Manually added" badge
  - [x] 13.15: Test accessibility (keyboard nav, ARIA labels, form labels)

## Dev Notes

### Critical Architecture Patterns

**Timeline Filtering (from UX-Decisions-Log.md Section 7.7):**

Filter controls allow attorneys to focus on specific aspects of the timeline:
- **Event Type Filter**: Multi-select dropdown (Filing, Notice, Hearing, Order, Transaction, Document, Deadline)
- **Actor Filter**: Multi-select dropdown populated from entities involved in timeline events
- **Date Range Filter**: Start date and end date pickers (filter inclusive of bounds)
- **Verification Status Filter**: All / Verified Only / Unverified Only

**Manual Event Addition (from UX-Decisions-Log.md Section 7.8):**

Manual events are attorney-added events for information not in documents:
- Marked distinctly as "Manually added" in UI
- Can be edited or deleted (unlike auto-extracted events which can only have classification edited)
- Store `is_manual: true` and `created_by: user_id` in database
- Appear in chronological position alongside auto-extracted events

### Component Structure

```
frontend/src/components/features/timeline/
├── index.ts                           # UPDATE - Add new exports
├── TimelineFilterBar.tsx              # NEW - Filter controls
├── TimelineFilterBar.test.tsx         # NEW
├── AddEventDialog.tsx                 # NEW - Manual event creation
├── AddEventDialog.test.tsx            # NEW
├── EditEventDialog.tsx                # NEW - Event editing
├── EditEventDialog.test.tsx           # NEW
├── DeleteEventConfirmation.tsx        # NEW - Delete confirmation
├── DeleteEventConfirmation.test.tsx   # NEW
├── TimelineHeader.tsx                 # UPDATE - Add buttons
├── TimelineHeader.test.tsx            # UPDATE
├── TimelineEventCard.tsx              # UPDATE - Manual badge, context menu
├── TimelineEventCard.test.tsx         # UPDATE
├── TimelineContent.tsx                # UPDATE - Filter state, dialogs
├── TimelineContent.test.tsx           # UPDATE
├── TimelineHorizontal.tsx             # UPDATE - Manual event markers
├── TimelineMultiTrack.tsx             # UPDATE - Manual event handling
├── TimelineEventDetail.tsx            # UPDATE - Edit/Delete buttons
└── ... existing files
```

### TypeScript Type Definitions

```typescript
// Additional types for types/timeline.ts

/**
 * Filter state for timeline view
 */
export interface TimelineFilterState {
  /** Selected event types (empty = all) */
  eventTypes: TimelineEventType[];
  /** Selected entity IDs (empty = all) */
  entityIds: string[];
  /** Date range filter */
  dateRange: {
    start: string | null;
    end: string | null;
  };
  /** Verification status filter */
  verificationStatus: 'all' | 'verified' | 'unverified';
}

/**
 * Default filter state (no filters applied)
 */
export const DEFAULT_TIMELINE_FILTERS: TimelineFilterState = {
  eventTypes: [],
  entityIds: [],
  dateRange: { start: null, end: null },
  verificationStatus: 'all',
};

/**
 * Manual event creation request
 */
export interface ManualEventCreateRequest {
  /** Event date (ISO format) */
  eventDate: string;
  /** Event type */
  eventType: TimelineEventType;
  /** Event title/short description */
  title: string;
  /** Full description */
  description: string;
  /** Linked entity IDs */
  entityIds: string[];
  /** Source document ID (optional) */
  sourceDocumentId?: string | null;
  /** Source page number (optional) */
  sourcePage?: number | null;
}

/**
 * Manual event update request
 */
export interface ManualEventUpdateRequest {
  /** Event date (ISO format) - only for manual events */
  eventDate?: string;
  /** Event type - can update for all events */
  eventType?: TimelineEventType;
  /** Event title - only for manual events */
  title?: string;
  /** Full description - only for manual events */
  description?: string;
  /** Linked entity IDs - only for manual events */
  entityIds?: string[];
}
```

### Filter Bar Implementation Pattern

```typescript
// TimelineFilterBar.tsx structure
'use client';

import { useState, useCallback } from 'react';
import { Filter, X, Check, ChevronsUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { cn } from '@/lib/utils';
import type { TimelineFilterState, TimelineEventType } from '@/types/timeline';

// Event type options
const EVENT_TYPE_OPTIONS: { value: TimelineEventType; label: string }[] = [
  { value: 'filing', label: 'Filing' },
  { value: 'notice', label: 'Notice' },
  { value: 'hearing', label: 'Hearing' },
  { value: 'order', label: 'Order' },
  { value: 'transaction', label: 'Transaction' },
  { value: 'document', label: 'Document' },
  { value: 'deadline', label: 'Deadline' },
];

interface TimelineFilterBarProps {
  filters: TimelineFilterState;
  onFiltersChange: (filters: TimelineFilterState) => void;
  /** Available entities from timeline */
  entities: { id: string; name: string }[];
  className?: string;
}

export function TimelineFilterBar({
  filters,
  onFiltersChange,
  entities,
  className,
}: TimelineFilterBarProps) {
  // Count active filters
  const activeFilterCount =
    filters.eventTypes.length +
    filters.entityIds.length +
    (filters.dateRange.start || filters.dateRange.end ? 1 : 0) +
    (filters.verificationStatus !== 'all' ? 1 : 0);

  const handleClearFilters = useCallback(() => {
    onFiltersChange(DEFAULT_TIMELINE_FILTERS);
  }, [onFiltersChange]);

  return (
    <div className={cn('flex items-center gap-2 flex-wrap py-3 border-b', className)}>
      {/* Event Type Filter */}
      <MultiSelectFilter
        title="Event Type"
        options={EVENT_TYPE_OPTIONS}
        selected={filters.eventTypes}
        onSelectionChange={(types) =>
          onFiltersChange({ ...filters, eventTypes: types as TimelineEventType[] })
        }
      />

      {/* Actor Filter */}
      <MultiSelectFilter
        title="Actors"
        options={entities.map(e => ({ value: e.id, label: e.name }))}
        selected={filters.entityIds}
        onSelectionChange={(ids) =>
          onFiltersChange({ ...filters, entityIds: ids })
        }
      />

      {/* Date Range Filter */}
      <DateRangeFilter
        startDate={filters.dateRange.start}
        endDate={filters.dateRange.end}
        onDateRangeChange={(start, end) =>
          onFiltersChange({ ...filters, dateRange: { start, end } })
        }
      />

      {/* Verification Status Filter */}
      <VerificationStatusFilter
        status={filters.verificationStatus}
        onStatusChange={(status) =>
          onFiltersChange({ ...filters, verificationStatus: status })
        }
      />

      {/* Clear Filters */}
      {activeFilterCount > 0 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClearFilters}
          className="text-muted-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear ({activeFilterCount})
        </Button>
      )}
    </div>
  );
}
```

### Add Event Dialog Pattern

```typescript
// AddEventDialog.tsx structure
'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format } from 'date-fns';
import { CalendarIcon, Plus, Info } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type { ManualEventCreateRequest } from '@/types/timeline';

const addEventSchema = z.object({
  eventDate: z.date({
    required_error: 'Event date is required',
  }),
  eventType: z.enum([
    'filing', 'notice', 'hearing', 'order',
    'transaction', 'document', 'deadline'
  ], {
    required_error: 'Event type is required',
  }),
  title: z.string()
    .min(5, 'Title must be at least 5 characters')
    .max(200, 'Title cannot exceed 200 characters'),
  description: z.string()
    .max(2000, 'Description cannot exceed 2000 characters')
    .optional(),
  entityIds: z.array(z.string()).optional(),
  sourceDocumentId: z.string().optional().nullable(),
  sourcePage: z.number().optional().nullable(),
});

interface AddEventDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (event: ManualEventCreateRequest) => Promise<void>;
  /** Available entities for actor selection */
  entities: { id: string; name: string }[];
  /** Available documents for source selection */
  documents: { id: string; name: string }[];
}

export function AddEventDialog({
  open,
  onOpenChange,
  onSubmit,
  entities,
  documents,
}: AddEventDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<z.infer<typeof addEventSchema>>({
    resolver: zodResolver(addEventSchema),
    defaultValues: {
      eventType: undefined,
      title: '',
      description: '',
      entityIds: [],
      sourceDocumentId: null,
      sourcePage: null,
    },
  });

  const handleSubmit = async (values: z.infer<typeof addEventSchema>) => {
    setIsSubmitting(true);
    try {
      await onSubmit({
        eventDate: format(values.eventDate, 'yyyy-MM-dd'),
        eventType: values.eventType,
        title: values.title,
        description: values.description ?? '',
        entityIds: values.entityIds ?? [],
        sourceDocumentId: values.sourceDocumentId,
        sourcePage: values.sourcePage,
      });
      toast.success('Event added successfully');
      form.reset();
      onOpenChange(false);
    } catch (error) {
      toast.error('Failed to add event');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Timeline Event</DialogTitle>
          <DialogDescription>
            Add an event that isn't captured in the documents.
          </DialogDescription>
        </DialogHeader>

        {/* Manual event badge */}
        <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
          <Info className="h-4 w-4 text-blue-600" />
          <span className="text-sm text-blue-600">
            This event will be marked as manually added
          </span>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            {/* Date field */}
            <FormField
              control={form.control}
              name="eventDate"
              render={({ field }) => (
                <FormItem className="flex flex-col">
                  <FormLabel>Event Date *</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          variant="outline"
                          className={cn(
                            'w-full pl-3 text-left font-normal',
                            !field.value && 'text-muted-foreground'
                          )}
                        >
                          {field.value ? (
                            format(field.value, 'PPP')
                          ) : (
                            <span>Pick a date</span>
                          )}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={field.value}
                        onSelect={field.onChange}
                        disabled={(date) =>
                          date > new Date() || date < new Date('1900-01-01')
                        }
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Event type field */}
            <FormField
              control={form.control}
              name="eventType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event Type *</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select event type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="filing">Filing</SelectItem>
                      <SelectItem value="notice">Notice</SelectItem>
                      <SelectItem value="hearing">Hearing</SelectItem>
                      <SelectItem value="order">Order</SelectItem>
                      <SelectItem value="transaction">Transaction</SelectItem>
                      <SelectItem value="document">Document</SelectItem>
                      <SelectItem value="deadline">Deadline</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Title field */}
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title *</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Brief description of the event"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description field */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Additional details about the event (optional)"
                      className="resize-none"
                      rows={3}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Actor selection - would use combobox multi-select */}
            {/* Source document selection - would use combobox */}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Adding...' : 'Add Event'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
```

### Backend API Additions Required

**New POST Endpoint: Create Manual Event**
```python
@router.post(
    "/events",
    response_model=ManualEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_event(
    matter_id: str = Path(...),
    request: ManualEventCreateRequest = ...,
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> ManualEventResponse:
    """Create a manual timeline event."""
    # Set is_manual=True, created_by=current_user.id
    # Insert into events table
    # Link entities via event_entities junction table
    ...
```

**New DELETE Endpoint: Delete Manual Event**
```python
@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_event(
    matter_id: str = Path(...),
    event_id: str = Path(...),
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])),
    timeline_service: TimelineService = Depends(_get_timeline_service),
):
    """Delete a manual timeline event.

    Only events with is_manual=True can be deleted.
    """
    # Verify event exists and is_manual=True
    # Delete from events table
    ...
```

**Updated GET /full Endpoint Filters:**
```python
@router.get("/full", ...)
async def get_timeline_with_entities(
    # ... existing params ...
    start_date: date | None = Query(None, description="Filter events on or after this date"),
    end_date: date | None = Query(None, description="Filter events on or before this date"),
    is_verified: bool | None = Query(None, description="Filter by verification status (true/false/null for all)"),
    # ...
):
```

### Zustand Store Pattern (MANDATORY)

```typescript
// CORRECT - Selector pattern
const filters = useTimelineStore((state) => state.filters);
const setFilters = useTimelineStore((state) => state.setFilters);

// WRONG - Full store subscription
const { filters, setFilters } = useTimelineStore();
```

### Naming Conventions (from project-context.md)

| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `TimelineFilterBar`, `AddEventDialog` |
| Component files | PascalCase.tsx | `TimelineFilterBar.tsx` |
| Functions | camelCase | `handleFiltersChange`, `createManualEvent` |
| Constants | SCREAMING_SNAKE | `DEFAULT_TIMELINE_FILTERS`, `EVENT_TYPE_OPTIONS` |
| Types/Interfaces | PascalCase | `TimelineFilterState`, `ManualEventCreateRequest` |
| API functions | camelCase | `createManualEvent`, `deleteEvent` |

### Previous Story Intelligence (Story 10B.4)

**From Story 10B.4 implementation (88226e3):**
- TimelineHorizontal and TimelineMultiTrack components created
- TimelineEventDetail component for showing selected event details
- TimelineZoomSlider for horizontal view zoom control
- timelineUtils.ts with helper functions: `calculateTimelineScale`, `clusterEvents`, `groupEventsByActor`, `calculateGaps`
- 168 timeline tests passing

**Patterns established:**
- View mode toggle in TimelineHeader (List, Horizontal, Multi-Track)
- Event selection state managed in TimelineContent
- `onEventSelect` callback pattern for event selection
- `onViewInList` callback for switching views
- Event detail panel below alternative views

**Files to update:**
- TimelineContent.tsx - add filter state and dialogs
- TimelineHeader.tsx - add filter and add event buttons
- TimelineEventCard.tsx - add manual badge and context menu
- TimelineEventDetail.tsx - add edit/delete buttons

### Git Commit Context (Recent Commits)

```
88226e3 feat(timeline): implement horizontal and multi-track views (Story 10B.4)
b2ca8bf feat(timeline): implement vertical list view (Story 10B.3)
bfaa012 feat(summary): implement inline verification for summary sections (Story 10B.2)
```

**Pattern to follow:**
- Commit message format: `feat(timeline): implement filtering and manual event addition (Story 10B.5)`
- Test files co-located with components
- Update barrel exports in index.ts

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `Dialog`, `DialogContent`, `DialogHeader`, `DialogFooter` - for add/edit dialogs
- `AlertDialog` - for delete confirmation
- `Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormMessage` - for forms
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` - for dropdowns
- `Popover`, `PopoverContent`, `PopoverTrigger` - for filter dropdowns
- `Command`, `CommandGroup`, `CommandItem` - for multi-select (combobox)
- `Calendar` - for date picker
- `Button`, `Input`, `Textarea`, `Badge`, `Checkbox` - standard components
- `DropdownMenu` - for context menu on event cards

**Check if these need to be added via shadcn:**
```bash
npx shadcn@latest add form calendar command
```

**Use lucide-react icons:**
- `Filter` - filter toggle button
- `Plus` - add event button
- `X` - clear filters
- `Check` - selected item
- `ChevronsUpDown` - combobox toggle
- `CalendarIcon` - date picker
- `MoreVertical` - context menu trigger
- `Pencil` - edit action
- `Trash2` - delete action
- `Info` - manual event info badge
- `User` - manual event creator badge

### Project Structure Notes

**File Locations (MANDATORY):**
- Timeline components: `frontend/src/components/features/timeline/`
- Types: `frontend/src/types/timeline.ts`
- API functions: `frontend/src/lib/api/timeline.ts`
- Tests co-located: `ComponentName.test.tsx` next to `ComponentName.tsx`

### Testing Considerations

**Test file structure:**
```typescript
describe('TimelineFilterBar', () => {
  it('renders all filter options', () => {});
  it('updates event type filter on selection', () => {});
  it('updates actor filter on selection', () => {});
  it('updates date range filter', () => {});
  it('updates verification status filter', () => {});
  it('shows active filter count', () => {});
  it('clears all filters on clear button click', () => {});
  it('is accessible with keyboard navigation', () => {});
});

describe('AddEventDialog', () => {
  it('opens when open prop is true', () => {});
  it('validates required fields', () => {});
  it('shows date validation error for empty date', () => {});
  it('shows title length validation', () => {});
  it('calls onSubmit with correct data', () => {});
  it('shows loading state during submission', () => {});
  it('shows success toast on successful creation', () => {});
  it('shows error toast on failure', () => {});
  it('closes on cancel button click', () => {});
  it('resets form on successful submission', () => {});
});

describe('EditEventDialog', () => {
  it('pre-populates form with event data', () => {});
  it('allows editing all fields for manual events', () => {});
  it('only allows classification edit for auto events', () => {});
  it('calls onUpdate with changed fields', () => {});
});

describe('DeleteEventConfirmation', () => {
  it('shows warning message', () => {});
  it('calls onDelete when confirmed', () => {});
  it('closes when cancelled', () => {});
});

describe('TimelineContent (with filters)', () => {
  it('passes filters to useTimeline hook', () => {});
  it('shows filtered events only', () => {});
  it('opens add dialog on button click', () => {});
  it('opens edit dialog with selected event', () => {});
  it('refreshes data after event modification', () => {});
});

describe('TimelineEventCard (manual events)', () => {
  it('shows "Manually added" badge for manual events', () => {});
  it('shows context menu on hover/click', () => {});
  it('opens edit dialog from context menu', () => {});
  it('opens delete confirmation from context menu', () => {});
});
```

### Accessibility Requirements

- All filter controls have accessible labels
- Multi-select dropdowns support keyboard navigation (arrow keys, enter, escape)
- Date picker is keyboard navigable
- Dialog focus management (focus trap, return focus on close)
- Screen reader announces filter changes
- Form fields have associated labels and error messages
- Delete confirmation has focus on cancel button by default
- Context menu keyboard accessible (right-click alternative via keyboard)

### Performance Considerations

- Debounce filter changes (wait 300ms before fetching)
- Use `useMemo` for derived filter state
- Optimistic updates for add/edit/delete operations
- SWR `mutate` for cache invalidation after modifications
- Consider virtualization if filter results > 500 events

### Error Handling

**API Errors:**
```typescript
try {
  await createManualEvent(matterId, eventData);
  toast.success('Event added successfully');
  mutate(); // Refresh timeline data
} catch (error) {
  if (error instanceof ApiError) {
    toast.error(error.message);
  } else {
    toast.error('Failed to add event. Please try again.');
  }
}
```

**Form Validation:**
- Show inline errors below fields
- Disable submit until form is valid
- Show toast for server-side validation errors

### References

- [Source: epics.md#story-10b5 - Acceptance criteria]
- [Source: UX-Decisions-Log.md#section-7.7 - Timeline Filtering]
- [Source: UX-Decisions-Log.md#section-7.8 - Manual Event Addition]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: Story 10B.4 - Timeline alternative views patterns]
- [Source: frontend/src/types/timeline.ts - Existing type definitions]
- [Source: frontend/src/components/features/timeline/ - Existing components]
- [Source: backend/app/api/routes/timeline.py - Existing API endpoints]
- [Source: backend/app/models/timeline.py - Existing backend models]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
