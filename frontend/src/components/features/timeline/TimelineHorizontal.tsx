'use client';

/**
 * Timeline Horizontal Component
 *
 * Horizontal timeline view with events on a time axis.
 * Features zoom control, event clustering, and gap indicators.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #2)
 */

import { useState, useMemo, useRef, useCallback } from 'react';
import { Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { TimelineZoomSlider } from './TimelineZoomSlider';
import { TimelineEventDetail } from './TimelineEventDetail';
import {
  calculateTimelineScale,
  calculateDatePosition,
  clusterEvents,
  calculateGaps,
  formatGapDuration,
} from './timelineUtils';
import {
  EVENT_TYPE_ICONS,
  EVENT_TYPE_COLORS,
} from './eventTypeIcons';
import type { TimelineEvent, ZoomLevel, EventCluster } from '@/types/timeline';

interface TimelineHorizontalProps {
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
 * Marker for a single event or cluster
 */
function TimelineMarker({
  cluster,
  position,
  isSelected,
  onClick,
}: {
  cluster: EventCluster;
  position: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const event = cluster.events[0];
  if (!event) return null;

  const isCluster = cluster.events.length > 1;
  const Icon = EVENT_TYPE_ICONS[event.eventType] ?? EVENT_TYPE_ICONS.unclassified;
  const colorClass = EVENT_TYPE_COLORS[event.eventType] ?? EVENT_TYPE_COLORS.unclassified;

  // Extract background color from the color class
  const bgMatch = colorClass.match(/bg-(\w+)-(\d+)/);
  const bgColor = bgMatch ? `bg-${bgMatch[1]}-${bgMatch[2]}` : 'bg-gray-200';

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          className={cn(
            'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
            'flex items-center justify-center',
            'rounded-full transition-all cursor-pointer',
            'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
            isCluster ? 'w-8 h-8' : 'w-6 h-6',
            isSelected
              ? 'ring-2 ring-primary ring-offset-2 scale-110'
              : 'hover:scale-110',
            bgColor
          )}
          style={{ left: `${position}%` }}
          onClick={onClick}
          aria-label={`Event: ${event.description.slice(0, 50)}${event.description.length > 50 ? '...' : ''}`}
          aria-pressed={isSelected}
        >
          <Icon className="h-3 w-3 text-foreground" aria-hidden="true" />
          {isCluster && (
            <span className="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 bg-primary text-primary-foreground text-[10px] font-bold rounded-full">
              {cluster.events.length}
            </span>
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        {isCluster ? (
          <div>
            <p className="font-medium">{cluster.events.length} events</p>
            <p className="text-xs text-muted-foreground">Click to view details</p>
          </div>
        ) : (
          <div>
            <p className="font-medium">{event.description.slice(0, 100)}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {new Date(event.eventDate).toLocaleDateString()}
            </p>
          </div>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Gap indicator for significant delays
 */
function GapIndicator({
  startPosition,
  endPosition,
  duration,
}: {
  startPosition: number;
  endPosition: number;
  duration: number;
}) {
  const width = endPosition - startPosition;
  if (width < 2) return null; // Too small to show

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className="absolute top-1/2 -translate-y-1/2 h-1 bg-muted-foreground/20 rounded cursor-help"
          style={{
            left: `${startPosition}%`,
            width: `${width}%`,
          }}
          aria-label={`Gap of ${formatGapDuration(duration)}`}
        >
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-[9px] text-muted-foreground bg-background px-1 rounded">
              {formatGapDuration(duration)}
            </span>
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent>
        <p>Gap: {formatGapDuration(duration)}</p>
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Empty state for timeline
 */
function EmptyState() {
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

export function TimelineHorizontal({
  events,
  onEventSelect,
  selectedEventId,
  onViewInList,
  className,
}: TimelineHorizontalProps) {
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('year');
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate scale and positions
  const scale = useMemo(
    () => calculateTimelineScale(events, zoomLevel),
    [events, zoomLevel]
  );

  // Cluster nearby events
  const clusters = useMemo(
    () => clusterEvents(events, zoomLevel),
    [events, zoomLevel]
  );

  // Find gaps
  const gaps = useMemo(() => calculateGaps(events), [events]);

  // Selected event
  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  // Handle cluster click - select first event in cluster
  const handleClusterClick = useCallback(
    (cluster: EventCluster) => {
      // If cluster, select first event (could expand in future)
      const firstEvent = cluster.events[0];
      if (firstEvent) {
        onEventSelect?.(firstEvent);
      }
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

  // Empty state
  if (events.length === 0) {
    return (
      <div className={cn('flex flex-col', className)}>
        <EmptyState />
      </div>
    );
  }

  // Calculate timeline width based on zoom
  const timelineWidth = scale.totalWidth > 0 ? Math.max(scale.totalWidth, 800) : 800;

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Zoom controls */}
      <div className="flex justify-end mb-4">
        <TimelineZoomSlider zoomLevel={zoomLevel} onZoomChange={setZoomLevel} />
      </div>

      {/* Timeline container */}
      <ScrollArea className="w-full border rounded-lg bg-muted/20">
        <div
          ref={containerRef}
          className="relative h-40 px-8 py-4"
          style={{ width: `${timelineWidth}px`, minWidth: '100%' }}
          role="graphics-document"
          aria-label="Horizontal timeline"
        >
          {/* Year labels */}
          <div className="absolute top-2 left-8 right-8 flex">
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

          {/* Main axis line */}
          <div className="absolute top-1/2 left-8 right-8 h-0.5 bg-border -translate-y-1/2" />

          {/* Tick marks for years */}
          {scale.yearLabels.map((label) => (
            <div
              key={`tick-${label.year}`}
              className="absolute top-1/2 w-0.5 h-4 bg-border -translate-y-1/2"
              style={{ left: `calc(8px + ${label.position}% * (100% - 64px) / 100)` }}
            />
          ))}

          {/* Gap indicators */}
          {scale.minDate &&
            scale.maxDate &&
            gaps
              .filter((g) => g.isSignificant)
              .map((gap, idx) => {
                const startPos = calculateDatePosition(
                  gap.startDate,
                  scale.minDate!,
                  scale.maxDate!
                );
                const endPos = calculateDatePosition(
                  gap.endDate,
                  scale.minDate!,
                  scale.maxDate!
                );
                return (
                  <GapIndicator
                    key={`gap-${idx}`}
                    startPosition={startPos}
                    endPosition={endPos}
                    duration={gap.durationDays}
                  />
                );
              })}

          {/* Event markers */}
          {scale.minDate &&
            scale.maxDate &&
            clusters.map((cluster) => {
              const position = calculateDatePosition(
                cluster.centerDate,
                scale.minDate!,
                scale.maxDate!
              );
              const isSelected = cluster.events.some(
                (e) => e.id === selectedEventId
              );
              return (
                <TimelineMarker
                  key={cluster.id}
                  cluster={cluster}
                  position={position}
                  isSelected={isSelected}
                  onClick={() => handleClusterClick(cluster)}
                />
              );
            })}
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
