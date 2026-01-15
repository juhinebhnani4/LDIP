/**
 * Timeline Utilities
 *
 * Shared utility functions for horizontal and multi-track timeline views.
 * Provides date-to-position mapping, event clustering, grouping, and gap detection.
 *
 * Story 10B.4: Timeline Tab Alternative Views
 */

import {
  parseISO,
  differenceInDays,
  startOfYear,
  endOfYear,
  eachYearOfInterval,
  isValid,
} from 'date-fns';
import type {
  TimelineEvent,
  TimelineTrack,
  EventCluster,
  TimelineGap,
  TimelineScale,
  ZoomLevel,
} from '@/types/timeline';

/**
 * Significant gap threshold in days (> 90 days)
 */
export const SIGNIFICANT_GAP_DAYS = 90;

/**
 * Cluster threshold in days based on zoom level
 */
export const CLUSTER_THRESHOLDS: Record<ZoomLevel, number> = {
  year: 30,
  quarter: 14,
  month: 7,
  week: 2,
  day: 1,
};

/**
 * Scale multipliers for zoom levels
 * Higher values = more spread out timeline
 */
export const SCALE_MULTIPLIERS: Record<ZoomLevel, number> = {
  year: 1,
  quarter: 4,
  month: 12,
  week: 52,
  day: 365,
};

/**
 * Base width per year in pixels
 */
export const BASE_WIDTH_PER_YEAR = 200;

/**
 * Parse date string safely
 */
function safeParseDateString(dateStr: string): Date | null {
  try {
    const date = parseISO(dateStr);
    return isValid(date) ? date : null;
  } catch {
    return null;
  }
}

/**
 * Calculate timeline scale and year labels for axis rendering
 */
export function calculateTimelineScale(
  events: TimelineEvent[],
  zoomLevel: ZoomLevel
): TimelineScale {
  if (events.length === 0) {
    return {
      scale: SCALE_MULTIPLIERS[zoomLevel],
      yearLabels: [],
      minDate: null,
      maxDate: null,
      totalWidth: 0,
    };
  }

  // Parse all valid dates
  const dates = events
    .map((e) => safeParseDateString(e.eventDate))
    .filter((d): d is Date => d !== null);

  if (dates.length === 0) {
    return {
      scale: SCALE_MULTIPLIERS[zoomLevel],
      yearLabels: [],
      minDate: null,
      maxDate: null,
      totalWidth: 0,
    };
  }

  // Find date range
  const sortedDates = dates.sort((a, b) => a.getTime() - b.getTime());
  const minDateRaw = sortedDates[0]!;
  const maxDateRaw = sortedDates[sortedDates.length - 1]!;

  // Expand to full years
  const minDate = startOfYear(minDateRaw);
  const maxDate = endOfYear(maxDateRaw);

  // Generate year intervals
  const years = eachYearOfInterval({ start: minDate, end: maxDate });
  const totalYears = years.length;
  const scale = SCALE_MULTIPLIERS[zoomLevel];
  const totalWidth = totalYears * BASE_WIDTH_PER_YEAR * scale;

  // Calculate year label positions
  const yearLabels = years.map((yearDate, index) => ({
    year: yearDate.getFullYear(),
    position: (index / totalYears) * 100, // percentage
  }));

  return {
    scale,
    yearLabels,
    minDate,
    maxDate,
    totalWidth,
  };
}

/**
 * Calculate position (percentage) for a date on the timeline
 */
export function calculateDatePosition(
  dateStr: string,
  minDate: Date,
  maxDate: Date
): number {
  const date = safeParseDateString(dateStr);
  if (!date) return 0;

  const totalRange = maxDate.getTime() - minDate.getTime();
  if (totalRange <= 0) return 50;

  const position = ((date.getTime() - minDate.getTime()) / totalRange) * 100;
  return Math.max(0, Math.min(100, position));
}

/**
 * Create a cluster from a group of events
 */
function createCluster(events: TimelineEvent[]): EventCluster {
  const centerIndex = Math.floor(events.length / 2);
  const firstEvent = events[0]!;
  const centerEvent = events[centerIndex]!;
  return {
    id: `cluster-${firstEvent.id}`,
    centerDate: centerEvent.eventDate,
    events,
    isExpanded: false,
  };
}

/**
 * Cluster events that are close together based on zoom level
 */
export function clusterEvents(
  events: TimelineEvent[],
  zoomLevel: ZoomLevel
): EventCluster[] {
  if (events.length === 0) {
    return [];
  }

  const clusterThreshold = CLUSTER_THRESHOLDS[zoomLevel];
  const clusters: EventCluster[] = [];

  // Sort events by date
  const sorted = [...events].sort((a, b) => {
    const dateA = safeParseDateString(a.eventDate);
    const dateB = safeParseDateString(b.eventDate);
    if (!dateA || !dateB) return 0;
    return dateA.getTime() - dateB.getTime();
  });

  let currentCluster: TimelineEvent[] = [];

  for (const event of sorted) {
    if (currentCluster.length === 0) {
      currentCluster.push(event);
    } else {
      const lastEvent = currentCluster[currentCluster.length - 1]!;
      const lastDate = safeParseDateString(lastEvent.eventDate);
      const currentDate = safeParseDateString(event.eventDate);

      if (!lastDate || !currentDate) {
        // Can't compare, start new cluster
        if (currentCluster.length > 0) {
          clusters.push(createCluster(currentCluster));
        }
        currentCluster = [event];
        continue;
      }

      const daysDiff = differenceInDays(currentDate, lastDate);

      if (daysDiff <= clusterThreshold) {
        currentCluster.push(event);
      } else {
        // Save current cluster and start new one
        clusters.push(createCluster(currentCluster));
        currentCluster = [event];
      }
    }
  }

  // Don't forget the last cluster
  if (currentCluster.length > 0) {
    clusters.push(createCluster(currentCluster));
  }

  return clusters;
}

/**
 * Group events by actor (entity) for multi-track view
 */
export function groupEventsByActor(events: TimelineEvent[]): TimelineTrack[] {
  const actorMap = new Map<string, TimelineTrack>();

  for (const event of events) {
    // Events can have multiple actors - add to each track
    const actors =
      event.entities.length > 0
        ? event.entities
        : [
            {
              entityId: 'unknown',
              canonicalName: 'Unknown Actor',
              entityType: 'UNKNOWN',
              role: null,
            },
          ];

    for (const actor of actors) {
      if (!actorMap.has(actor.entityId)) {
        actorMap.set(actor.entityId, {
          entityId: actor.entityId,
          actorName: actor.canonicalName,
          actorType: actor.entityType,
          events: [],
        });
      }
      // Only add if not already in this track (avoid duplicates)
      const track = actorMap.get(actor.entityId)!;
      if (!track.events.some((e) => e.id === event.id)) {
        track.events.push(event);
      }
    }
  }

  // Sort tracks by event count (most active first)
  // Within each track, sort events by date
  return Array.from(actorMap.values())
    .map((track) => ({
      ...track,
      events: [...track.events].sort((a, b) => {
        const dateA = safeParseDateString(a.eventDate);
        const dateB = safeParseDateString(b.eventDate);
        if (!dateA || !dateB) return 0;
        return dateA.getTime() - dateB.getTime();
      }),
    }))
    .sort((a, b) => b.events.length - a.events.length);
}

/**
 * Calculate gaps between events
 */
export function calculateGaps(events: TimelineEvent[]): TimelineGap[] {
  if (events.length < 2) {
    return [];
  }

  const gaps: TimelineGap[] = [];

  // Sort by date
  const sorted = [...events].sort((a, b) => {
    const dateA = safeParseDateString(a.eventDate);
    const dateB = safeParseDateString(b.eventDate);
    if (!dateA || !dateB) return 0;
    return dateA.getTime() - dateB.getTime();
  });

  for (let i = 0; i < sorted.length - 1; i++) {
    const currentEvent = sorted[i]!;
    const nextEvent = sorted[i + 1]!;
    const currentDate = safeParseDateString(currentEvent.eventDate);
    const nextDate = safeParseDateString(nextEvent.eventDate);

    if (!currentDate || !nextDate) continue;

    const days = differenceInDays(nextDate, currentDate);

    if (days > 0) {
      gaps.push({
        startDate: currentEvent.eventDate,
        endDate: nextEvent.eventDate,
        durationDays: days,
        isSignificant: days > SIGNIFICANT_GAP_DAYS,
      });
    }
  }

  return gaps;
}

/**
 * Format time axis label based on zoom level
 */
export function formatTimeAxisLabel(date: Date, zoomLevel: ZoomLevel): string {
  switch (zoomLevel) {
    case 'day':
      return `${date.getMonth() + 1}/${date.getDate()}`;
    case 'week':
      return `W${Math.ceil(date.getDate() / 7)}`;
    case 'month':
      return date.toLocaleDateString('en-US', { month: 'short' });
    case 'quarter':
      return `Q${Math.ceil((date.getMonth() + 1) / 3)}`;
    case 'year':
    default:
      return date.getFullYear().toString();
  }
}

/**
 * Get next zoom level (zoom in)
 */
export function getNextZoomLevel(current: ZoomLevel): ZoomLevel | null {
  const levels: ZoomLevel[] = ['year', 'quarter', 'month', 'week', 'day'];
  const currentIndex = levels.indexOf(current);
  if (currentIndex < levels.length - 1) {
    return levels[currentIndex + 1] ?? null;
  }
  return null;
}

/**
 * Get previous zoom level (zoom out)
 */
export function getPreviousZoomLevel(current: ZoomLevel): ZoomLevel | null {
  const levels: ZoomLevel[] = ['year', 'quarter', 'month', 'week', 'day'];
  const currentIndex = levels.indexOf(current);
  if (currentIndex > 0) {
    return levels[currentIndex - 1] ?? null;
  }
  return null;
}

/**
 * Format gap duration for display
 */
export function formatGapDuration(days: number): string {
  if (days < 30) {
    return `${days} day${days === 1 ? '' : 's'}`;
  }
  if (days < 365) {
    const months = Math.round(days / 30);
    return `~${months} month${months === 1 ? '' : 's'}`;
  }
  const years = Math.round(days / 365);
  return `~${years} year${years === 1 ? '' : 's'}`;
}
