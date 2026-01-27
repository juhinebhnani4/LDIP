/**
 * Cross-Engine Link Types
 *
 * Gap 5-3: Cross-Engine Correlation Links
 *
 * Types for cross-engine data correlation enabling navigation between:
 * - Timeline events ↔ Entities
 * - Timeline events ↔ Contradictions
 * - Entities ↔ Contradictions
 */

// =============================================================================
// Cross-Linked Item Types
// =============================================================================

/**
 * Timeline event with minimal data for cross-engine linking
 */
export interface CrossLinkedTimelineEvent {
  eventId: string;
  eventDate: string;
  eventType: string;
  description: string;
  documentId: string | null;
  documentName: string | null;
  sourcePage: number | null;
  confidence: number;
}

/**
 * Contradiction with minimal data for cross-engine linking
 */
export interface CrossLinkedContradiction {
  contradictionId: string;
  contradictionType: string;
  severity: 'high' | 'medium' | 'low';
  explanation: string;
  statementAExcerpt: string;
  statementBExcerpt: string;
  documentAId: string;
  documentAName: string;
  documentBId: string;
  documentBName: string;
  confidence: number;
}

/**
 * Entity with minimal data for cross-engine linking
 */
export interface CrossLinkedEntity {
  entityId: string;
  canonicalName: string;
  entityType: string;
  aliases: string[];
}

// =============================================================================
// Response Types
// =============================================================================

/**
 * Response for entity journey (timeline events for an entity)
 */
export interface EntityJourneyResponse {
  entityId: string;
  entityName: string;
  entityType: string;
  events: CrossLinkedTimelineEvent[];
  totalEvents: number;
  dateRangeStart: string | null;
  dateRangeEnd: string | null;
}

/**
 * Response for entity contradictions summary
 */
export interface EntityContradictionSummary {
  entityId: string;
  entityName: string;
  contradictions: CrossLinkedContradiction[];
  totalContradictions: number;
  highSeverityCount: number;
  mediumSeverityCount: number;
  lowSeverityCount: number;
}

/**
 * Response for timeline event context
 */
export interface TimelineEventContext {
  eventId: string;
  eventDate: string;
  eventType: string;
  description: string;
  documentId: string | null;
  documentName: string | null;
  entities: CrossLinkedEntity[];
  relatedContradictions: CrossLinkedContradiction[];
}

/**
 * Response for contradiction context
 */
export interface ContradictionContext {
  contradictionId: string;
  entityId: string;
  entityName: string;
  contradictionType: string;
  severity: string;
  explanation: string;
  relatedEvents: CrossLinkedTimelineEvent[];
}

// =============================================================================
// Link Types for UI Components
// =============================================================================

/**
 * Types of cross-engine links that can be displayed
 */
export type CrossLinkType =
  | 'entity-timeline'      // Link to entity's timeline journey
  | 'entity-contradiction' // Link to entity's contradictions
  | 'event-entities'       // Link to entities in an event
  | 'event-contradiction'  // Link to contradictions related to event
  | 'contradiction-events' // Link to events related to a contradiction
  | 'contradiction-entity';// Link to entity involved in contradiction

/**
 * Cross-link metadata for rendering
 */
export interface CrossLink {
  type: CrossLinkType;
  targetId: string;
  targetTab: 'timeline' | 'entities' | 'contradictions';
  label: string;
  count?: number;
}

/**
 * Cross-link navigation parameters
 */
export interface CrossLinkNavigation {
  matterId: string;
  targetTab: 'timeline' | 'entities' | 'contradictions';
  entityId?: string;
  eventId?: string;
  contradictionId?: string;
  highlight?: string;
}

// =============================================================================
// Counts for badges
// =============================================================================

/**
 * Cross-engine counts for displaying badges on items
 */
export interface CrossEngineCounts {
  /** Number of timeline events (for entities) */
  timelineEventCount?: number;
  /** Number of contradictions (for entities or events) */
  contradictionCount?: number;
  /** Number of high-severity contradictions */
  highSeverityCount?: number;
  /** Number of related entities (for events or contradictions) */
  entityCount?: number;
  /** Date range (for entity journey) */
  dateRange?: {
    start: string | null;
    end: string | null;
  };
}

// =============================================================================
// Story 5.4: Cross-Engine Consistency Issue Types
// =============================================================================

/**
 * Issue type classification
 */
export type ConsistencyIssueType =
  | 'date_mismatch'
  | 'entity_name_mismatch'
  | 'amount_discrepancy'
  | 'citation_conflict'
  | 'timeline_gap'
  | 'duplicate_event';

/**
 * Issue severity levels
 */
export type ConsistencyIssueSeverity = 'info' | 'warning' | 'error';

/**
 * Issue resolution status
 */
export type ConsistencyIssueStatus = 'open' | 'reviewed' | 'resolved' | 'dismissed';

/**
 * Engine type
 */
export type EngineType = 'timeline' | 'entity' | 'citation' | 'contradiction' | 'rag';

/**
 * A cross-engine consistency issue
 */
export interface ConsistencyIssue {
  id: string;
  matterId: string;
  issueType: ConsistencyIssueType;
  severity: ConsistencyIssueSeverity;
  sourceEngine: EngineType;
  sourceId: string | null;
  sourceValue: string | null;
  conflictingEngine: EngineType;
  conflictingId: string | null;
  conflictingValue: string | null;
  description: string;
  documentId: string | null;
  documentName: string | null;
  status: ConsistencyIssueStatus;
  resolvedBy: string | null;
  resolvedAt: string | null;
  resolutionNotes: string | null;
  detectedAt: string;
  createdAt: string;
  updatedAt: string;
  metadata: Record<string, unknown>;
}

/**
 * Consistency issue summary counts
 */
export interface ConsistencyIssueSummary {
  totalCount: number;
  openCount: number;
  warningCount: number;
  errorCount: number;
}

/**
 * List response for consistency issues
 */
export interface ConsistencyIssueListResponse {
  data: ConsistencyIssue[];
  meta: {
    limit: number;
    offset: number;
    count: number;
  };
}

/**
 * Summary response for consistency issues
 */
export interface ConsistencyIssueSummaryResponse {
  data: ConsistencyIssueSummary;
}

/**
 * Result of running a consistency check
 */
export interface ConsistencyCheckResult {
  issuesFound: number;
  issuesCreated: number;
  enginesChecked: string[];
  durationMs: number;
}

/**
 * Labels for issue types
 */
export const ISSUE_TYPE_LABELS: Record<ConsistencyIssueType, string> = {
  date_mismatch: 'Date Mismatch',
  entity_name_mismatch: 'Entity Name Mismatch',
  amount_discrepancy: 'Amount Discrepancy',
  citation_conflict: 'Citation Conflict',
  timeline_gap: 'Timeline Gap',
  duplicate_event: 'Duplicate Event',
};

/**
 * Descriptions for issue types
 */
export const ISSUE_TYPE_DESCRIPTIONS: Record<ConsistencyIssueType, string> = {
  date_mismatch: 'Different dates found for the same event in timeline and entity data',
  entity_name_mismatch: 'Entity name variations between MIG and citations',
  amount_discrepancy: 'Monetary or numeric values differ between extractions',
  citation_conflict: 'Citation information conflicts with document content',
  timeline_gap: 'Missing events in timeline that are referenced elsewhere',
  duplicate_event: 'Same event appears multiple times with different details',
};

/**
 * Labels for severity levels
 */
export const SEVERITY_LABELS: Record<ConsistencyIssueSeverity, string> = {
  info: 'Info',
  warning: 'Warning',
  error: 'Error',
};

/**
 * Labels for issue status
 */
export const STATUS_LABELS: Record<ConsistencyIssueStatus, string> = {
  open: 'Open',
  reviewed: 'Reviewed',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
};
