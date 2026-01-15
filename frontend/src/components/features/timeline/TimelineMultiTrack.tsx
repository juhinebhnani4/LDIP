'use client';

/**
 * Timeline Multi-Track Component
 *
 * Multi-track timeline view with parallel horizontal timelines by actor.
 * Events are aligned vertically by date across all tracks.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #3)
 */

import { useState, useMemo, useCallback } from 'react';
import { Users, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { TimelineEventDetail } from './TimelineEventDetail';
import { TimelineZoomSlider } from './TimelineZoomSlider';
import {
  calculateTimelineScale,
  calculateDatePosition,
  groupEventsByActor,
} from './timelineUtils';
import {
  EVENT_TYPE_ICONS,
  EVENT_TYPE_MARKER_BG,
} from './eventTypeIcons';
import type { TimelineEvent, TimelineTrack, ZoomLevel } from '@/types/timeline';

interface TimelineMultiTrackProps {
  /** Timeline events */
  events: TimelineEvent[];
  /** Callback when event is selected */
  onEventSelect?: (event: TimelineEvent | null) => void;
  /** Currently selected event ID */
  selectedEventId?: string | null;
  /** Callback to switch to list view at selected event */
  onViewInList?: (eventId: string) => void;
  /** Optional className */
  className?: string;
}

/**
 * Track row showing events for one actor
 *
 * Renders a single horizontal track in the multi-track timeline.
 * Shows actor label on the left and event markers positioned by date.
 *
 * @param track - TimelineTrack containing actor info and their events
 * @param minDate - Minimum date for calculating event positions
 * @param maxDate - Maximum date for calculating event positions
 * @param selectedEventId - Currently selected event ID (for highlighting)
 * @param onEventSelect - Callback when an event marker is clicked
 */
function TrackRow({
  track,
  minDate,
  maxDate,
  selectedEventId,
  onEventSelect,
}: {
  track: TimelineTrack;
  minDate: Date;
  maxDate: Date;
  selectedEventId?: string | null;
  onEventSelect?: (event: TimelineEvent) => void;
}) {
  return (
    <div
      className="flex items-center h-16 border-b last:border-b-0"
      role="row"
      aria-label={`Timeline track for ${track.actorName}`}
    >
      {/* Track label */}
      <div
        className="w-40 shrink-0 px-4 truncate font-medium text-sm border-r bg-muted/30"
        title={track.actorName}
      >
        <span className="text-xs text-muted-foreground block">
          {track.actorType}
        </span>
        <span className="truncate block">{track.actorName}</span>
      </div>

      {/* Track timeline area */}
      <div className="flex-1 relative h-full">
        {/* Track line */}
        <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-border/50 -translate-y-1/2" />

        {/* Event markers */}
        {track.events.map((event) => {
          const position = calculateDatePosition(
            event.eventDate,
            minDate,
            maxDate
          );
          const isSelected = event.id === selectedEventId;
          const Icon =
            EVENT_TYPE_ICONS[event.eventType] ?? EVENT_TYPE_ICONS.unclassified;
          const bgColor =
            EVENT_TYPE_MARKER_BG[event.eventType] ??
            EVENT_TYPE_MARKER_BG.unclassified;

          return (
            <Tooltip key={event.id}>
              <TooltipTrigger asChild>
                <button
                  className={cn(
                    'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
                    'flex items-center justify-center w-5 h-5',
                    'rounded-full transition-all cursor-pointer',
                    'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1',
                    isSelected
                      ? 'ring-2 ring-primary ring-offset-1 scale-125 z-10'
                      : 'hover:scale-110',
                    bgColor
                  )}
                  style={{ left: `${position}%` }}
                  onClick={() => onEventSelect?.(event)}
                  aria-label={`Event: ${event.description.slice(0, 80)}${event.description.length > 80 ? '...' : ''}`}
                  aria-pressed={isSelected}
                >
                  <Icon className="h-2.5 w-2.5 text-foreground" aria-hidden="true" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs">
                <p className="font-medium">{event.description.slice(0, 80)}...</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {new Date(event.eventDate).toLocaleDateString()}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Empty state - no events or no actors
 */
function EmptyState({ hasEvents }: { hasEvents: boolean }) {
  if (!hasEvents) {
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

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Users className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium">No Actor Information</h3>
      <p className="text-sm text-muted-foreground mt-2">
        Events require linked entities to display in multi-track view.
      </p>
      <p className="text-sm text-muted-foreground">
        Try the List or Horizontal view instead.
      </p>
    </div>
  );
}

export function TimelineMultiTrack({
  events,
  onEventSelect,
  selectedEventId,
  onViewInList,
  className,
}: TimelineMultiTrackProps) {
  // Configurable zoom level for multi-track view
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('year');

  // Group events by actor
  const tracks = useMemo(() => groupEventsByActor(events), [events]);

  // Calculate scale for positioning
  const scale = useMemo(
    () => calculateTimelineScale(events, zoomLevel),
    [events, zoomLevel]
  );

  // Selected event
  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  // Handle event click
  const handleEventSelect = useCallback(
    (event: TimelineEvent) => {
      onEventSelect?.(event);
    },
    [onEventSelect]
  );

  // Handle view in list navigation
  const handleViewInList = useCallback(() => {
    if (selectedEventId && onViewInList) {
      onViewInList(selectedEventId);
    }
  }, [selectedEventId, onViewInList]);

  // Handle close detail
  const handleCloseDetail = useCallback(() => {
    onEventSelect?.(null);
  }, [onEventSelect]);

  // Empty states
  if (events.length === 0) {
    return (
      <div className={cn('flex flex-col', className)}>
        <EmptyState hasEvents={false} />
      </div>
    );
  }

  // Filter out unknown actor track if there are other tracks
  const filteredTracks =
    tracks.length > 1
      ? tracks.filter((t) => t.entityId !== 'unknown')
      : tracks;

  if (filteredTracks.length === 0) {
    return (
      <div className={cn('flex flex-col', className)}>
        <EmptyState hasEvents={true} />
      </div>
    );
  }

  // Calculate timeline width
  const timelineWidth =
    scale.totalWidth > 0 ? Math.max(scale.totalWidth, 800) : 800;

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Track count and zoom controls */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Users className="h-4 w-4" />
          <span>
            {filteredTracks.length} actor{filteredTracks.length !== 1 ? 's' : ''}
          </span>
        </div>
        <TimelineZoomSlider zoomLevel={zoomLevel} onZoomChange={setZoomLevel} />
      </div>

      {/* Multi-track container */}
      <ScrollArea className="w-full border rounded-lg bg-muted/20">
        <div
          className="relative"
          style={{ width: `${timelineWidth + 160}px`, minWidth: '100%' }}
          role="table"
          aria-label="Multi-track timeline"
        >
          {/* Year header row */}
          <div className="flex items-center h-8 border-b bg-background sticky top-0 z-10">
            {/* Empty space for track labels */}
            <div className="w-40 shrink-0 border-r bg-muted/30" />

            {/* Year labels */}
            <div className="flex-1 relative px-2">
              {scale.yearLabels.map((label) => (
                <span
                  key={label.year}
                  className="absolute text-xs text-muted-foreground font-medium"
                  style={{ left: `${label.position}%` }}
                >
                  {label.year}
                </span>
              ))}
            </div>
          </div>

          {/* Vertical grid lines */}
          <div className="absolute top-8 bottom-0 left-40 right-0 pointer-events-none">
            {scale.yearLabels.map((label) => (
              <div
                key={`grid-${label.year}`}
                className="absolute top-0 bottom-0 w-px bg-border/30"
                style={{ left: `${label.position}%` }}
              />
            ))}
          </div>

          {/* Track rows */}
          {scale.minDate &&
            scale.maxDate &&
            filteredTracks.map((track) => (
              <TrackRow
                key={track.entityId}
                track={track}
                minDate={scale.minDate!}
                maxDate={scale.maxDate!}
                selectedEventId={selectedEventId}
                onEventSelect={handleEventSelect}
              />
            ))}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>

      {/* Selected event detail panel */}
      {selectedEvent && (
        <TimelineEventDetail
          event={selectedEvent}
          onClose={handleCloseDetail}
          onViewInList={onViewInList ? handleViewInList : undefined}
          className="mt-4"
        />
      )}
    </div>
  );
}
