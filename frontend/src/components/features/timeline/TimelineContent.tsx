'use client';

import { useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useTimeline } from '@/hooks/useTimeline';
import { useTimelineStats } from '@/hooks/useTimelineStats';
import { TimelineHeader } from './TimelineHeader';
import { TimelineList } from './TimelineList';
import { TimelineHorizontal } from './TimelineHorizontal';
import { TimelineMultiTrack } from './TimelineMultiTrack';
import type { TimelineViewMode, TimelineEvent } from '@/types/timeline';

/**
 * Timeline Content Component
 *
 * Main component for the Timeline tab that composes:
 * - TimelineHeader with stats and view mode toggle
 * - TimelineList (vertical list view)
 * - TimelineHorizontal (horizontal axis view)
 * - TimelineMultiTrack (parallel actor tracks view)
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #1, #2, #3)
 * Story 10B.4: Timeline Tab Alternative Views (AC #1, #2, #3)
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

  // Fetch timeline data
  const {
    events,
    isLoading: eventsLoading,
    isError: eventsError,
  } = useTimeline(matterId);

  // Fetch timeline stats
  const {
    stats,
    isLoading: statsLoading,
    isError: statsError,
  } = useTimelineStats(matterId);

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

  // Render the appropriate view based on mode
  const renderTimelineView = () => {
    switch (viewMode) {
      case 'horizontal':
        return (
          <TimelineHorizontal
            events={events}
            onEventSelect={handleEventSelect}
            selectedEventId={selectedEventId}
            onViewInList={handleViewInList}
            className="mt-4"
          />
        );
      case 'multitrack':
        return (
          <TimelineMultiTrack
            events={events}
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
            events={events}
            isLoading={eventsLoading}
            isError={eventsError || statsError}
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
      {/* Header with stats and view mode toggle */}
      <TimelineHeader
        stats={stats}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        isLoading={statsLoading}
      />

      {/* Timeline view based on mode */}
      {renderTimelineView()}
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
