'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { toast } from 'sonner';
import { useCrossTabNavigation } from '@/hooks/useCrossTabNavigation';
import { useTimeline } from '@/hooks/useTimeline';
import { useTimelineStats } from '@/hooks/useTimelineStats';
import {
  useAnomaliesByEvent,
  useAnomalySummary,
  useAnomalyMutations,
  type AnomalyListItem,
} from '@/hooks/useAnomalies';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';
import { useBoundingBoxes } from '@/hooks/useBoundingBoxes';
import { TimelineHeader } from './TimelineHeader';
import { TimelineList } from './TimelineList';
import { TimelineHorizontal } from './TimelineHorizontal';
import { TimelineMultiTrack } from './TimelineMultiTrack';
import { TimelineFilterBar } from './TimelineFilterBar';
import { AnomaliesBanner } from './AnomaliesBanner';
import { AnomalyDetailPanel } from './AnomalyDetailPanel';
import { AddEventDialog } from './AddEventDialog';
import { EditEventDialog } from './EditEventDialog';
import { DeleteEventConfirmation } from './DeleteEventConfirmation';
import { timelineEventApi } from '@/lib/api/client';
import { fetchDocument, fetchDocuments } from '@/lib/api/documents';
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
 * Story 14.16: Anomalies UI Integration (AC #1, #2, #3, #4)
 */

interface TimelineContentProps {
  /** Optional className */
  className?: string;
}

export function TimelineContent({ className }: TimelineContentProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // Cross-tab navigation: detect event/entity params from URL
  const { context } = useCrossTabNavigation(matterId);
  const [highlightedEventId, setHighlightedEventId] = useState<string | null>(null);

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

  // Cross-tab navigation: set highlighted event from URL param
  useEffect(() => {
    if (context.highlightedEventId) {
      setHighlightedEventId(context.highlightedEventId);
    }
  }, [context.highlightedEventId]);

  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [eventToEdit, setEventToEdit] = useState<TimelineEvent | null>(null);
  const [eventToDelete, setEventToDelete] = useState<TimelineEvent | null>(null);

  // Anomaly state (Story 14.16)
  const [anomalyPanelOpen, setAnomalyPanelOpen] = useState(false);
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyListItem | null>(null);

  // Track page for loading more events
  const [currentPerPage, setCurrentPerPage] = useState(500);

  // Fetch timeline data with filters
  const {
    events,
    filteredEvents,
    uniqueEntities,
    meta: timelineMeta,
    isLoading: eventsLoading,
    isError: eventsError,
    addEvent,
    updateEvent,
    deleteEvent,
    mutate: refreshTimeline,
  } = useTimeline(matterId, { filters: debouncedFilters, perPage: currentPerPage });

  // Fetch timeline stats
  const {
    stats,
    isLoading: statsLoading,
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

  // Fetch anomaly data (Story 14.16)
  const { getAnomaliesForEvent } = useAnomaliesByEvent(matterId);
  const { summary: anomalySummary, mutate: refreshAnomalySummary } = useAnomalySummary(matterId);
  const {
    dismiss: dismissAnomaly,
    verify: verifyAnomaly,
    isLoading: anomalyMutationLoading,
  } = useAnomalyMutations(matterId);

  // PDF split view for source document viewing
  const openPdfSplitView = usePdfSplitViewStore((state) => state.openPdfSplitView);
  const setBoundingBoxes = usePdfSplitViewStore((state) => state.setBoundingBoxes);
  const { fetchByBboxIds } = useBoundingBoxes();

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

  // Handle anomaly click (Story 14.16)
  const handleAnomalyClick = useCallback((anomaly: AnomalyListItem) => {
    setSelectedAnomaly(anomaly);
    setAnomalyPanelOpen(true);
  }, []);

  // Handle anomaly panel close
  const handleAnomalyPanelClose = useCallback(() => {
    setAnomalyPanelOpen(false);
    setSelectedAnomaly(null);
  }, []);

  // Handle anomaly dismiss
  const handleAnomalyDismiss = useCallback(
    async (anomalyId: string) => {
      await dismissAnomaly(anomalyId);
      await refreshAnomalySummary();
      handleAnomalyPanelClose();
    },
    [dismissAnomaly, refreshAnomalySummary, handleAnomalyPanelClose]
  );

  // Handle anomaly verify
  const handleAnomalyVerify = useCallback(
    async (anomalyId: string) => {
      await verifyAnomaly(anomalyId);
      await refreshAnomalySummary();
      handleAnomalyPanelClose();
    },
    [verifyAnomaly, refreshAnomalySummary, handleAnomalyPanelClose]
  );

  // Handle anomalies banner click
  const handleAnomaliesBannerClick = useCallback(() => {
    // Enable show anomalies only filter
    setFilters((prev) => ({ ...prev, showAnomaliesOnly: true }));
  }, []);

  /**
   * Handle source document click from timeline event card.
   * Opens the document in PDF split view instead of navigating away.
   */
  const handleSourceClick = useCallback(
    async (event: TimelineEvent) => {
      if (!event.documentId) return;

      try {
        // Fetch document details to get signed URL and filename
        const document = await fetchDocument(event.documentId);
        const documentUrl = document.storagePath;

        if (!documentUrl) {
          throw new Error('Document URL not found');
        }

        // Open PDF split view with document at the source page
        // Warn user if page is unknown (will default to page 1)
        const pageNumber = event.sourcePage ?? 1;
        if (!event.sourcePage) {
          toast.warning('Page number unknown - opening to page 1');
        }

        openPdfSplitView(
          {
            documentId: event.documentId,
            documentName: document.filename,
            page: pageNumber,
            bboxIds: event.sourceBboxIds || [],
          },
          matterId,
          documentUrl
        );

        // Fetch and set bounding boxes for highlighting (BBOX-3 Gap 2 + BBOX-8)
        if (event.sourceBboxIds && event.sourceBboxIds.length > 0) {
          try {
            const { bboxes, pageNumber: bboxPage } = await fetchByBboxIds(
              event.sourceBboxIds,
              matterId
            );
            if (bboxes.length > 0) {
              setBoundingBoxes(bboxes, bboxPage ?? pageNumber);
            }
          } catch {
            // Bbox fetch failure shouldn't block document viewing
          }
        }
      } catch {
        toast.error('Unable to open document. Please try again.');
      }
    },
    [matterId, openPdfSplitView, fetchByBboxIds, setBoundingBoxes]
  );

  // Calculate active filter count for display
  const activeFilterCount = countActiveFilters(filters);

  // Apply anomaly filter if enabled (Story 14.16)
  const displayEvents = useMemo(() => {
    if (!filters.showAnomaliesOnly) {
      return filteredEvents;
    }
    // Filter to only show events that have anomalies
    return filteredEvents.filter((event) => {
      const eventAnomalies = getAnomaliesForEvent(event.id);
      return eventAnomalies.length > 0;
    });
  }, [filteredEvents, filters.showAnomaliesOnly, getAnomaliesForEvent]);

  // Cross-tab navigation: scroll to highlighted event after data loads.
  // Uses setInterval with fresh DOM queries on each tick to handle
  // Suspense swaps and layout shifts that reset scrollTop.
  useEffect(() => {
    if (!highlightedEventId || eventsLoading || displayEvents.length === 0) return;

    let stableCount = 0;
    let highlighted = false;

    const intervalId = setInterval(() => {
      // Re-query DOM each tick to handle element replacement (Suspense swaps)
      const el = document.querySelector(
        `[data-testid="timeline-event-${highlightedEventId}"]`
      ) as HTMLElement | null;
      if (!el) return;

      const scrollContainer = document.querySelector(
        '[data-testid="workspace-main-content"]'
      );
      if (!scrollContainer) return;

      // Add highlight ring on first successful find
      if (!highlighted) {
        el.style.boxShadow = '0 0 0 2px hsl(var(--primary))';
        highlighted = true;
      }

      // Calculate target scroll position (center element in viewport)
      const containerRect = scrollContainer.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      const offsetTop = elRect.top - containerRect.top + scrollContainer.scrollTop;
      const targetScrollTop = Math.max(0, offsetTop - containerRect.height / 2 + elRect.height / 2);

      // Check if scroll is already near target
      if (Math.abs(scrollContainer.scrollTop - targetScrollTop) < 50) {
        stableCount++;
        if (stableCount >= 3) {
          // Scroll has been stable for 3 ticks - stop polling
          clearInterval(intervalId);
        }
      } else {
        stableCount = 0;
        // Set scroll position directly (instant, not cancellable like smooth)
        scrollContainer.scrollTop = targetScrollTop;
      }
    }, 150);

    // Stop polling after 6 seconds max
    const maxTimer = setTimeout(() => {
      clearInterval(intervalId);
    }, 6000);

    // Clean up highlight after 7 seconds
    const cleanupTimer = setTimeout(() => {
      const el = document.querySelector(
        `[data-testid="timeline-event-${highlightedEventId}"]`
      ) as HTMLElement | null;
      if (el) el.style.boxShadow = '';
      setHighlightedEventId(null);
    }, 7000);

    return () => {
      clearInterval(intervalId);
      clearTimeout(maxTimer);
      clearTimeout(cleanupTimer);
    };
  }, [highlightedEventId, eventsLoading, displayEvents.length]);

  // Render the appropriate view based on mode
  const renderTimelineView = () => {

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
            isError={eventsError}
            hasFiltersApplied={activeFilterCount > 0}
            onEditEvent={handleEditEvent}
            onDeleteEvent={handleDeleteEvent}
            onRetry={refreshTimeline}
            getAnomaliesForEvent={getAnomaliesForEvent}
            onAnomalyClick={handleAnomalyClick}
            onSourceClick={handleSourceClick}
            className="mt-4"
          />
        );
    }
  };

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
        isLoading={statsLoading && eventsLoading}
        fallbackEventCount={events.length}
        totalEventsFromMeta={timelineMeta?.total}
      />

      {/* Anomalies Banner (Story 14.16) */}
      <AnomaliesBanner
        summary={anomalySummary}
        onShowAnomalies={handleAnomaliesBannerClick}
        className="mt-4"
      />

      {/* Filter bar */}
      <TimelineFilterBar
        filters={filters}
        onFiltersChange={setFilters}
        entities={uniqueEntities}
        anomalyCount={anomalySummary?.unreviewed ?? 0}
        className="mt-4"
      />

      {/* Events count message and Load More button */}
      <div className="mt-2 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {activeFilterCount > 0 ? (
            <>Showing {displayEvents.length} of {events.length} loaded events</>
          ) : timelineMeta && events.length < timelineMeta.total ? (
            <>Showing {events.length} of {timelineMeta.total} events</>
          ) : (
            <>{events.length} events</>
          )}
        </p>
        {timelineMeta && events.length < timelineMeta.total && !eventsLoading && (
          <button
            onClick={() => setCurrentPerPage((prev) => Math.min(prev + 500, timelineMeta.total))}
            className="text-sm text-primary hover:underline"
          >
            Load more events ({timelineMeta.total - events.length} remaining)
          </button>
        )}
      </div>

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

      {/* Anomaly Detail Panel (Story 14.16) */}
      <AnomalyDetailPanel
        isOpen={anomalyPanelOpen}
        onClose={handleAnomalyPanelClose}
        anomaly={selectedAnomaly}
        onDismiss={handleAnomalyDismiss}
        onVerify={handleAnomalyVerify}
        isLoading={anomalyMutationLoading}
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
