'use client';

import { format, parseISO } from 'date-fns';
import { List, LayoutTemplate, Table2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { TimelineStats, TimelineViewMode } from '@/types/timeline';

/**
 * Timeline Header Component
 *
 * Displays event count, date range, and view mode toggle.
 * Only List mode is active for Story 10B.3.
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #1)
 */

interface TimelineHeaderProps {
  /** Timeline statistics for display */
  stats: TimelineStats | undefined;
  /** Currently active view mode */
  viewMode: TimelineViewMode;
  /** Callback when view mode changes */
  onViewModeChange: (mode: TimelineViewMode) => void;
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

      {/* Right side: View mode toggle */}
      <div
        className="flex items-center gap-1 border rounded-lg p-1"
        role="group"
        aria-label="View mode selection"
      >
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
        <Button
          variant={viewMode === 'horizontal' ? 'secondary' : 'ghost'}
          size="sm"
          className="h-8 px-3"
          onClick={() => onViewModeChange('horizontal')}
          aria-pressed={viewMode === 'horizontal'}
          aria-label="Horizontal timeline view"
          disabled
          title="Coming soon in Story 10B.4"
        >
          <LayoutTemplate className="h-4 w-4 mr-1.5" aria-hidden="true" />
          <span className="text-xs">Horizontal</span>
        </Button>
        <Button
          variant={viewMode === 'table' ? 'secondary' : 'ghost'}
          size="sm"
          className="h-8 px-3"
          onClick={() => onViewModeChange('table')}
          aria-pressed={viewMode === 'table'}
          aria-label="Table view"
          disabled
          title="Coming soon"
        >
          <Table2 className="h-4 w-4 mr-1.5" aria-hidden="true" />
          <span className="text-xs">Table</span>
        </Button>
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
