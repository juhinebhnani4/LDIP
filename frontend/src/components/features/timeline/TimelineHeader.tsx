'use client';

import { format, parseISO } from 'date-fns';
import { List, LayoutTemplate, Users, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { TimelineStats, TimelineViewMode } from '@/types/timeline';

/**
 * Timeline Header Component
 *
 * Displays event count, date range, view mode toggle, and add event button.
 * Supports List, Horizontal, and Multi-Track views.
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #1)
 * Story 10B.4: Timeline Tab Alternative Views (AC #1)
 * Story 10B.5: Timeline Filtering and Manual Event Addition (AC #5)
 */

interface TimelineHeaderProps {
  /** Timeline statistics for display */
  stats: TimelineStats | undefined;
  /** Currently active view mode */
  viewMode: TimelineViewMode;
  /** Callback when view mode changes */
  onViewModeChange: (mode: TimelineViewMode) => void;
  /** Callback when Add Event button is clicked */
  onAddEvent?: () => void;
  /** Whether stats are loading */
  isLoading?: boolean;
  /** Optional className for styling */
  className?: string;
}

/**
 * Format the date range for display
 */
function formatDateRange(start: string | null, end: string | null): string {
  if (!start || !end) {
    return 'No events';
  }

  try {
    const startDate = parseISO(start);
    const endDate = parseISO(end);
    const startFormatted = format(startDate, 'MMM yyyy');
    const endFormatted = format(endDate, 'MMM yyyy');

    if (startFormatted === endFormatted) {
      return startFormatted;
    }

    return `${startFormatted} - ${endFormatted}`;
  } catch {
    return 'Invalid dates';
  }
}

export function TimelineHeader({
  stats,
  viewMode,
  onViewModeChange,
  onAddEvent,
  isLoading,
  className,
}: TimelineHeaderProps) {
  if (isLoading) {
    return <TimelineHeaderSkeleton className={className} />;
  }

  const eventCount = stats?.totalEvents ?? 0;
  const dateRange = formatDateRange(
    stats?.dateRangeStart ?? null,
    stats?.dateRangeEnd ?? null
  );

  return (
    <div
      className={`flex items-center justify-between py-4 border-b ${className ?? ''}`}
      role="banner"
      aria-label="Timeline header"
    >
      {/* Left side: Stats */}
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">
          {eventCount} {eventCount === 1 ? 'event' : 'events'}
        </h2>
        <p className="text-sm text-muted-foreground">{dateRange}</p>
      </div>

      {/* Right side: Add Event button and View mode toggle */}
      <div className="flex items-center gap-3">
        {/* Add Event button */}
        {onAddEvent && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8"
                onClick={onAddEvent}
                aria-label="Add event"
              >
                <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
                <span className="text-xs">Add Event</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Add a manual event to the timeline</TooltipContent>
          </Tooltip>
        )}

        {/* View mode toggle */}
        <div
          className="flex items-center gap-1 border rounded-lg p-1"
          role="group"
          aria-label="View mode selection"
        >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-8 px-3"
              onClick={() => onViewModeChange('list')}
              aria-pressed={viewMode === 'list'}
              aria-label="List view"
            >
              <List className="h-4 w-4 mr-1.5" aria-hidden="true" />
              <span className="text-xs">List</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Vertical chronological list</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={viewMode === 'horizontal' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-8 px-3"
              onClick={() => onViewModeChange('horizontal')}
              aria-pressed={viewMode === 'horizontal'}
              aria-label="Horizontal timeline view"
            >
              <LayoutTemplate className="h-4 w-4 mr-1.5" aria-hidden="true" />
              <span className="text-xs">Horizontal</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Horizontal axis with zoom</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={viewMode === 'multitrack' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-8 px-3"
              onClick={() => onViewModeChange('multitrack')}
              aria-pressed={viewMode === 'multitrack'}
              aria-label="Multi-track view"
            >
              <Users className="h-4 w-4 mr-1.5" aria-hidden="true" />
              <span className="text-xs">Multi-Track</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Parallel timelines by actor</TooltipContent>
        </Tooltip>
        </div>
      </div>
    </div>
  );
}

/**
 * Timeline Header Skeleton
 */
export function TimelineHeaderSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={`flex items-center justify-between py-4 border-b ${className ?? ''}`}
    >
      <div className="flex flex-col gap-2">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="flex items-center gap-1">
        <Skeleton className="h-8 w-20" />
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-8 w-20" />
      </div>
    </div>
  );
}
