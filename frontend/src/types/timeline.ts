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
  /** Whether manually added (vs auto-extracted) */
  isManual?: boolean;
  /** User who created the event (for manual events) */
  createdBy?: string;
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

// ============================================================================
// Filtering Types (Story 10B.5)
// ============================================================================

/**
 * Filter state for timeline view
 */
export interface TimelineFilterState {
  /** Selected event types (empty = all) */
  eventTypes: TimelineEventType[];
  /** Selected entity IDs (empty = all) */
  entityIds: string[];
  /** Date range filter */
  dateRange: {
    start: string | null;
    end: string | null;
  };
  /** Verification status filter */
  verificationStatus: 'all' | 'verified' | 'unverified';
}

/**
 * Default filter state (no filters applied)
 */
export const DEFAULT_TIMELINE_FILTERS: TimelineFilterState = {
  eventTypes: [],
  entityIds: [],
  dateRange: { start: null, end: null },
  verificationStatus: 'all',
};

/**
 * Check if any filters are active
 */
export function hasActiveFilters(filters: TimelineFilterState): boolean {
  return (
    filters.eventTypes.length > 0 ||
    filters.entityIds.length > 0 ||
    filters.dateRange.start !== null ||
    filters.dateRange.end !== null ||
    filters.verificationStatus !== 'all'
  );
}

/**
 * Count active filters
 */
export function countActiveFilters(filters: TimelineFilterState): number {
  let count = 0;
  if (filters.eventTypes.length > 0) count++;
  if (filters.entityIds.length > 0) count++;
  if (filters.dateRange.start !== null || filters.dateRange.end !== null) count++;
  if (filters.verificationStatus !== 'all') count++;
  return count;
}

// ============================================================================
// Manual Event Types (Story 10B.5)
// ============================================================================

/**
 * Manual event creation request
 */
export interface ManualEventCreateRequest {
  /** Event date (ISO format YYYY-MM-DD) */
  eventDate: string;
  /** Event type */
  eventType: TimelineEventType;
  /** Event title/short description */
  title: string;
  /** Full description */
  description: string;
  /** Linked entity IDs */
  entityIds: string[];
  /** Source document ID (optional) */
  sourceDocumentId?: string | null;
  /** Source page number (optional) */
  sourcePage?: number | null;
}

/**
 * Manual event update request
 */
export interface ManualEventUpdateRequest {
  /** Event date (ISO format) - only editable for manual events */
  eventDate?: string;
  /** Event type - can update for all events (classification correction) */
  eventType?: TimelineEventType;
  /** Event title - only editable for manual events */
  title?: string;
  /** Full description - only editable for manual events */
  description?: string;
  /** Linked entity IDs - only editable for manual events */
  entityIds?: string[];
}

/**
 * Manual event API response (extends TimelineEvent)
 */
export interface ManualEventResponse extends TimelineEvent {
  /** Always true for manual events */
  isManual: true;
  /** User who created the event */
  createdBy: string;
  /** Creation timestamp */
  createdAt: string;
}
