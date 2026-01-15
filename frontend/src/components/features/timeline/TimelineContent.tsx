'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { useTimeline } from '@/hooks/useTimeline';
import { useTimelineStats } from '@/hooks/useTimelineStats';
import { TimelineHeader } from './TimelineHeader';
import { TimelineList } from './TimelineList';
import type { TimelineViewMode } from '@/types/timeline';

/**
 * Timeline Content Component
 *
 * Main component for the Timeline tab that composes:
 * - TimelineHeader with stats and view mode toggle
 * - TimelineList with events
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #1, #2, #3)
 */

interface TimelineContentProps {
  /** Optional className */
  className?: string;
}

export function TimelineContent({ className }: TimelineContentProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // View mode state (only 'list' is active in this story)
  const [viewMode, setViewMode] = useState<TimelineViewMode>('list');

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

  const handleViewModeChange = (mode: TimelineViewMode) => {
    // Only allow 'list' mode for now (horizontal/table disabled)
    if (mode === 'list') {
      setViewMode(mode);
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

      {/* Event list */}
      <TimelineList
        events={events}
        isLoading={eventsLoading}
        isError={eventsError || statsError}
        className="mt-4"
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
