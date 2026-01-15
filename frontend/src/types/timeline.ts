/**
 * Timeline Types for Timeline Tab
 *
 * Types for timeline events and statistics.
 * Matches backend Pydantic models in app/models/timeline.py
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */

/**
 * Event types for timeline (from backend EventType enum)
 */
export type TimelineEventType =
  | 'filing'
  | 'notice'
  | 'hearing'
  | 'order'
  | 'transaction'
  | 'document'
  | 'deadline'
  | 'unclassified'
  | 'raw_date';

/**
 * Date precision levels
 */
export type DatePrecision = 'day' | 'month' | 'year' | 'approximate';

/**
 * Timeline event entity reference
 */
export interface TimelineEntityReference {
  entityId: string;
  canonicalName: string;
  entityType: string;
  role: string | null;
}

/**
 * Timeline event from API
 * Matches backend TimelineEventWithEntities model
 */
export interface TimelineEvent {
  /** Event UUID */
  id: string;
  /** Event date (ISO format) */
  eventDate: string;
  /** Date precision */
  eventDatePrecision: DatePrecision;
  /** Original date text from document */
  eventDateText: string | null;
  /** Classified event type */
  eventType: TimelineEventType;
  /** Event description/context */
  description: string;
  /** Source document ID */
  documentId: string | null;
  /** Source page number */
  sourcePage: number | null;
  /** Classification confidence */
  confidence: number;
  /** Linked entities (actors) */
  entities: TimelineEntityReference[];
  /** Whether date is ambiguous */
  isAmbiguous: boolean;
  /** Whether manually verified */
  isVerified: boolean;
  /** Cross-references (future: document references) */
  crossReferences?: string[];
  /** Contradiction flag */
  hasContradiction?: boolean;
  /** Contradiction details if flagged */
  contradictionDetails?: string;
}

/**
 * Timeline statistics from stats endpoint
 * Matches backend TimelineStatisticsData model
 */
export interface TimelineStats {
  /** Total events count */
  totalEvents: number;
  /** Events by type */
  eventsByType: Record<string, number>;
  /** Number of entities involved */
  entitiesInvolved: number;
  /** Earliest event date (ISO format) */
  dateRangeStart: string | null;
  /** Latest event date (ISO format) */
  dateRangeEnd: string | null;
  /** Events with entity links */
  eventsWithEntities: number;
  /** Events without entity links */
  eventsWithoutEntities: number;
  /** Verified events count */
  verifiedEvents: number;
}

/**
 * Pagination meta from API
 */
export interface TimelinePaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/**
 * Timeline API response
 * GET /api/matters/{matterId}/timeline/full
 */
export interface TimelineResponse {
  data: TimelineEvent[];
  meta: TimelinePaginationMeta;
}

/**
 * Timeline stats API response
 * GET /api/matters/{matterId}/timeline/stats
 */
export interface TimelineStatsResponse {
  data: TimelineStats;
}

/**
 * View modes for timeline display
 * - list: Vertical chronological list (Story 10B.3)
 * - horizontal: Horizontal axis with zoom (Story 10B.4)
 * - multitrack: Parallel tracks by actor (Story 10B.4)
 */
export type TimelineViewMode = 'list' | 'horizontal' | 'multitrack';

/**
 * Zoom level for horizontal/multitrack views
 */
export type ZoomLevel = 'year' | 'quarter' | 'month' | 'week' | 'day';

/**
 * Timeline track for multi-track view
 */
export interface TimelineTrack {
  /** Actor entity ID */
  entityId: string;
  /** Actor name */
  actorName: string;
  /** Actor type (PERSON, ORG, INSTITUTION) */
  actorType: string;
  /** Events for this actor */
  events: TimelineEvent[];
}

/**
 * Event cluster for grouped events
 */
export interface EventCluster {
  /** Cluster ID */
  id: string;
  /** Cluster center date */
  centerDate: string;
  /** Events in cluster */
  events: TimelineEvent[];
  /** Whether cluster is expanded */
  isExpanded: boolean;
}

/**
 * Timeline gap for significant delays
 */
export interface TimelineGap {
  /** Gap start date */
  startDate: string;
  /** Gap end date */
  endDate: string;
  /** Duration in days */
  durationDays: number;
  /** Whether significant (> 90 days) */
  isSignificant: boolean;
}

/**
 * Year label for timeline axis
 */
export interface YearLabel {
  /** Year number */
  year: number;
  /** Position on axis (percentage or pixels) */
  position: number;
}

/**
 * Timeline scale calculation result
 */
export interface TimelineScale {
  /** Scale multiplier based on zoom level */
  scale: number;
  /** Year labels for axis */
  yearLabels: YearLabel[];
  /** Minimum date in range */
  minDate: Date | null;
  /** Maximum date in range */
  maxDate: Date | null;
  /** Total width in pixels (for horizontal scroll) */
  totalWidth: number;
}

/**
 * Options for useTimeline hook
 */
export interface UseTimelineOptions {
  eventType?: TimelineEventType;
  entityId?: string;
  page?: number;
  perPage?: number;
}
