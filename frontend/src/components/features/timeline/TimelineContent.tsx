'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { useTimeline } from '@/hooks/useTimeline';
import { useTimelineStats } from '@/hooks/useTimelineStats';
import { TimelineHeader } from './TimelineHeader';
import { TimelineList } from './TimelineList';
import { TimelineHorizontal } from './TimelineHorizontal';
import { TimelineMultiTrack } from './TimelineMultiTrack';
import { TimelineFilterBar } from './TimelineFilterBar';
import { AddEventDialog } from './AddEventDialog';
import { EditEventDialog } from './EditEventDialog';
import { DeleteEventConfirmation } from './DeleteEventConfirmation';
import { timelineEventApi } from '@/lib/api/client';
import { fetchDocuments } from '@/lib/api/documents';
import useSWR from 'swr';
import type {
  TimelineViewMode,
  TimelineEvent,
  TimelineFilterState,
  ManualEventCreateRequest,
  ManualEventUpdateRequest,
} from '@/types/timeline';
import { DEFAULT_TIMELINE_FILTERS, countActiveFilters } from '@/types/timeline';

/**
 * Debounce delay for filter changes (ms)
 */
const FILTER_DEBOUNCE_MS = 300;

/**
 * Timeline Content Component
 *
 * Main component for the Timeline tab that composes:
 * - TimelineHeader with stats and view mode toggle
 * - TimelineFilterBar with event type, actor, date range, verification filters
 * - TimelineList (vertical list view)
 * - TimelineHorizontal (horizontal axis view)
 * - TimelineMultiTrack (parallel actor tracks view)
 * - AddEventDialog for manual event creation
 * - EditEventDialog for event editing
 * - DeleteEventConfirmation for manual event deletion
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #1, #2, #3)
 * Story 10B.4: Timeline Tab Alternative Views (AC #1, #2, #3)
 * Story 10B.5: Timeline Filtering and Manual Event Addition (AC #1-#8)
 */

interface TimelineContentProps {
  /** Optional className */
  className?: string;
}

export function TimelineContent({ className }: TimelineContentProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // View mode state
  const [viewMode, setViewMode] = useState<TimelineViewMode>('list');

  // Selected event state (for horizontal/multitrack views)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  // Filter state - immediate state for UI responsiveness
  const [filters, setFilters] = useState<TimelineFilterState>(DEFAULT_TIMELINE_FILTERS);
  // Debounced filter state - used for actual data fetching
  const [debouncedFilters, setDebouncedFilters] = useState<TimelineFilterState>(DEFAULT_TIMELINE_FILTERS);
  const filterTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Debounce filter changes
  useEffect(() => {
    if (filterTimeoutRef.current) {
      clearTimeout(filterTimeoutRef.current);
    }
    filterTimeoutRef.current = setTimeout(() => {
      setDebouncedFilters(filters);
    }, FILTER_DEBOUNCE_MS);

    return () => {
      if (filterTimeoutRef.current) {
        clearTimeout(filterTimeoutRef.current);
      }
    };
  }, [filters]);

  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [eventToEdit, setEventToEdit] = useState<TimelineEvent | null>(null);
  const [eventToDelete, setEventToDelete] = useState<TimelineEvent | null>(null);

  // Fetch timeline data with filters
  const {
    events,
    filteredEvents,
    uniqueEntities,
    isLoading: eventsLoading,
    isError: eventsError,
    addEvent,
    updateEvent,
    deleteEvent,
    mutate: refreshTimeline,
  } = useTimeline(matterId, { filters: debouncedFilters });

  // Fetch timeline stats
  const {
    stats,
    isLoading: statsLoading,
    isError: statsError,
    mutate: refreshStats,
  } = useTimelineStats(matterId);

  // Fetch documents for source selection in AddEventDialog
  const { data: documentsData } = useSWR(
    matterId ? `documents-${matterId}` : null,
    () => fetchDocuments(matterId, { perPage: 100 }),
    { revalidateOnFocus: false }
  );
  const documents = documentsData?.data?.map((doc) => ({
    id: doc.id,
    name: doc.filename,
  })) ?? [];

  // Handle view mode change
  const handleViewModeChange = useCallback((mode: TimelineViewMode) => {
    setViewMode(mode);
    // Clear selection when switching views
    setSelectedEventId(null);
  }, []);

  // Handle event selection
  const handleEventSelect = useCallback((event: TimelineEvent | null) => {
    setSelectedEventId(event?.id ?? null);
  }, []);

  // Handle "View in List" - switch to list view and scroll to event
  const handleViewInList = useCallback(
    (eventId: string) => {
      setViewMode('list');
      setSelectedEventId(eventId);
      // Note: List view could implement scroll-to-event based on selectedEventId
    },
    []
  );

  // Handle add event button click
  const handleAddEventClick = useCallback(() => {
    setAddDialogOpen(true);
  }, []);

  // Handle add event submission
  const handleAddEventSubmit = useCallback(
    async (request: ManualEventCreateRequest) => {
      // Call API to create event
      const response = await timelineEventApi.create(matterId, request);

      // Optimistically add the event to the local state
      addEvent({
        ...response,
        id: response.id || crypto.randomUUID(),
        eventDateText: request.eventDate,
        confidence: 1.0,
        entities: [],
        isAmbiguous: false,
        isManual: true,
      });

      // Refresh data from server
      await Promise.all([refreshTimeline(), refreshStats()]);
    },
    [matterId, addEvent, refreshTimeline, refreshStats]
  );

  // Handle edit event click
  const handleEditEvent = useCallback((event: TimelineEvent) => {
    setEventToEdit(event);
    setEditDialogOpen(true);
  }, []);

  // Handle edit event submission
  const handleEditEventSubmit = useCallback(
    async (eventId: string, updates: ManualEventUpdateRequest) => {
      // Call API to update event
      await timelineEventApi.update(matterId, eventId, updates);

      // Optimistically update the event in local state
      updateEvent(eventId, {
        eventDate: updates.eventDate,
        eventType: updates.eventType,
        description: updates.description,
      });

      // Refresh data from server
      await Promise.all([refreshTimeline(), refreshStats()]);
    },
    [matterId, updateEvent, refreshTimeline, refreshStats]
  );

  // Handle delete event click
  const handleDeleteEvent = useCallback((event: TimelineEvent) => {
    setEventToDelete(event);
    setDeleteDialogOpen(true);
  }, []);

  // Handle delete event confirmation
  const handleDeleteEventConfirm = useCallback(
    async (eventId: string) => {
      // Call API to delete event
      await timelineEventApi.delete(matterId, eventId);

      // Optimistically remove the event from local state
      deleteEvent(eventId);

      // Refresh data from server
      await Promise.all([refreshTimeline(), refreshStats()]);
    },
    [matterId, deleteEvent, refreshTimeline, refreshStats]
  );

  // Render the appropriate view based on mode
  const renderTimelineView = () => {
    // Use filtered events for display
    const displayEvents = filteredEvents;

    switch (viewMode) {
      case 'horizontal':
        return (
          <TimelineHorizontal
            events={displayEvents}
            onEventSelect={handleEventSelect}
            selectedEventId={selectedEventId}
            onViewInList={handleViewInList}
            className="mt-4"
          />
        );
      case 'multitrack':
        return (
          <TimelineMultiTrack
            events={displayEvents}
            onEventSelect={handleEventSelect}
            selectedEventId={selectedEventId}
            onViewInList={handleViewInList}
            className="mt-4"
          />
        );
      case 'list':
      default:
        return (
          <TimelineList
            events={displayEvents}
            isLoading={eventsLoading}
            isError={eventsError || statsError}
            onEditEvent={handleEditEvent}
            onDeleteEvent={handleDeleteEvent}
            className="mt-4"
          />
        );
    }
  };

  // Calculate active filter count for display
  const activeFilterCount = countActiveFilters(filters);

  return (
    <div
      className={className}
      role="tabpanel"
      aria-labelledby="tab-timeline"
      id="panel-timeline"
    >
      {/* Header with stats, view mode toggle, and add event button */}
      <TimelineHeader
        stats={stats}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        onAddEvent={handleAddEventClick}
        isLoading={statsLoading}
      />

      {/* Filter bar */}
      <TimelineFilterBar
        filters={filters}
        onFiltersChange={setFilters}
        entities={uniqueEntities}
        className="mt-4"
      />

      {/* Filter results message */}
      {activeFilterCount > 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          Showing {filteredEvents.length} of {events.length} events
        </p>
      )}

      {/* Timeline view based on mode */}
      {renderTimelineView()}

      {/* Add Event Dialog */}
      <AddEventDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSubmit={handleAddEventSubmit}
        entities={uniqueEntities}
        documents={documents}
      />

      {/* Edit Event Dialog */}
      <EditEventDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        event={eventToEdit}
        onSubmit={handleEditEventSubmit}
        entities={uniqueEntities}
      />

      {/* Delete Event Confirmation */}
      <DeleteEventConfirmation
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        event={eventToDelete}
        onConfirm={handleDeleteEventConfirm}
      />
    </div>
  );
}

/**
 * Timeline Content Skeleton
 */
export function TimelineContentSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={className}
      role="tabpanel"
      aria-labelledby="tab-timeline"
      id="panel-timeline"
    >
      <TimelineHeader
        stats={undefined}
        viewMode="list"
        onViewModeChange={() => {}}
        isLoading
      />
      <TimelineList events={[]} isLoading className="mt-4" />
    </div>
  );
}
