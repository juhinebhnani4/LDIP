'use client';

import { useMemo } from 'react';
import { parseISO, getYear } from 'date-fns';
import { Clock, AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { TimelineEventCard, TimelineEventCardSkeleton } from './TimelineEventCard';
import { TimelineConnector } from './TimelineConnector';
import type { TimelineEvent } from '@/types/timeline';

/**
 * Timeline List Component
 *
 * Renders events in chronological order with:
 * - Year separators
 * - Connector lines between events
 * - Empty, loading, and error states
 * - Edit/delete actions for manual events
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #1, #3)
 * Story 10B.5: Timeline Filtering and Manual Event Addition (AC #6, #7, #8)
 */

interface TimelineListProps {
  /** Timeline events to display */
  events: TimelineEvent[];
  /** Whether data is loading */
  isLoading?: boolean;
  /** Whether there was an error */
  isError?: boolean;
  /** Error message to display */
  errorMessage?: string;
  /** Whether filters are currently applied (shows different empty state) */
  hasFiltersApplied?: boolean;
  /** Callback when edit is clicked on an event */
  onEditEvent?: (event: TimelineEvent) => void;
  /** Callback when delete is clicked on a manual event */
  onDeleteEvent?: (event: TimelineEvent) => void;
  /** Optional className */
  className?: string;
}

/**
 * Group events by year for rendering with year separators
 */
function groupEventsByYear(
  events: TimelineEvent[]
): Map<number, TimelineEvent[]> {
  const grouped = new Map<number, TimelineEvent[]>();

  events.forEach((event) => {
    try {
      const year = getYear(parseISO(event.eventDate));
      const existing = grouped.get(year) ?? [];
      grouped.set(year, [...existing, event]);
    } catch {
      // Skip events with invalid dates
    }
  });

  return grouped;
}

/**
 * Year Separator Component
 */
function YearSeparator({ year }: { year: number }) {
  return (
    <div
      className="sticky top-0 z-10 bg-background border-b py-2 mb-4"
      role="heading"
      aria-level={3}
    >
      <h3 className="text-lg font-semibold text-foreground">{year}</h3>
    </div>
  );
}

/**
 * Empty State Component
 * Shows different messages based on whether filters are applied
 */
function EmptyState({ hasFiltersApplied }: { hasFiltersApplied?: boolean }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      role="status"
      aria-label={hasFiltersApplied ? 'No matching events' : 'No events found'}
    >
      <Clock
        className="h-12 w-12 text-muted-foreground mb-4"
        aria-hidden="true"
      />
      <h3 className="text-lg font-medium">
        {hasFiltersApplied ? 'No Matching Events' : 'No Events Found'}
      </h3>
      <p className="text-sm text-muted-foreground mt-2 max-w-md">
        {hasFiltersApplied
          ? 'No events match your current filters. Try adjusting or clearing your filters.'
          : 'Timeline events will appear here once documents are processed and dates are extracted.'}
      </p>
    </div>
  );
}

/**
 * Error State Component
 */
function ErrorState({ message }: { message?: string }) {
  return (
    <Alert variant="destructive" className="my-4">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {message ?? 'Failed to load timeline data. Please try refreshing the page.'}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Loading Skeleton Component
 */
function LoadingSkeleton() {
  return (
    <div className="space-y-4" aria-label="Loading timeline" role="status">
      {/* Year separator skeleton */}
      <div className="sticky top-0 z-10 bg-background border-b py-2 mb-4">
        <div className="h-6 w-16 bg-muted/50 animate-pulse rounded" />
      </div>

      {/* Event cards skeleton */}
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i}>
          <TimelineEventCardSkeleton />
          {i < 5 && (
            <div className="flex items-center py-2 pl-6">
              <div className="w-0.5 h-8 mr-4 bg-muted/50 animate-pulse" />
              <div className="h-4 w-20 bg-muted/50 animate-pulse rounded" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function TimelineList({
  events,
  isLoading,
  isError,
  errorMessage,
  hasFiltersApplied,
  onEditEvent,
  onDeleteEvent,
  className,
}: TimelineListProps) {
  // Group events by year
  const eventsByYear = useMemo(() => groupEventsByYear(events), [events]);

  // Get sorted years (ascending)
  const years = useMemo(
    () => Array.from(eventsByYear.keys()).sort((a, b) => a - b),
    [eventsByYear]
  );

  // Handle loading state
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // Handle error state
  if (isError) {
    return <ErrorState message={errorMessage} />;
  }

  // Handle empty state
  if (events.length === 0) {
    return <EmptyState hasFiltersApplied={hasFiltersApplied} />;
  }

  return (
    <div
      className={className}
      role="list"
      aria-label="Timeline events"
    >
      {years.map((year, yearIndex) => {
        const yearEvents = eventsByYear.get(year) ?? [];

        return (
          <div key={year} role="group" aria-label={`Events from ${year}`}>
            <YearSeparator year={year} />

            {yearEvents.map((event, eventIndex) => {
              // Determine previous event for connector
              let prevEvent: TimelineEvent | undefined;

              if (eventIndex > 0) {
                // Previous event in same year
                prevEvent = yearEvents[eventIndex - 1];
              } else if (yearIndex > 0) {
                // Last event of previous year
                const prevYearNum = years[yearIndex - 1];
                if (prevYearNum !== undefined) {
                  const prevYearEvents = eventsByYear.get(prevYearNum);
                  if (prevYearEvents && prevYearEvents.length > 0) {
                    prevEvent = prevYearEvents[prevYearEvents.length - 1];
                  }
                }
              }

              return (
                <div key={event.id} role="listitem">
                  {/* Connector to previous event */}
                  {prevEvent && (
                    <TimelineConnector
                      fromDate={prevEvent.eventDate}
                      toDate={event.eventDate}
                    />
                  )}

                  {/* Event card */}
                  <TimelineEventCard
                    event={event}
                    onEdit={onEditEvent}
                    onDelete={onDeleteEvent}
                  />
                </div>
              );
            })}

            {/* Separator between years (not after last year) */}
            {yearIndex < years.length - 1 && (
              <Separator className="my-6" />
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Timeline List Skeleton
 */
export function TimelineListSkeleton({ className }: { className?: string }) {
  return (
    <div className={className}>
      <LoadingSkeleton />
    </div>
  );
}
