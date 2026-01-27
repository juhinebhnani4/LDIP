/**
 * Cross-Engine Link API Client
 *
 * Gap 5-3: Cross-Engine Correlation Links
 * Story 5.4: Cross-Engine Consistency Checking
 *
 * API methods for fetching cross-engine correlation data and consistency issues.
 */

import { api, type ApiMethodOptions } from './client';
import type {
  EntityJourneyResponse,
  EntityContradictionSummary,
  TimelineEventContext,
  ContradictionContext,
  CrossLinkedTimelineEvent,
  CrossLinkedContradiction,
  CrossLinkedEntity,
  ConsistencyIssue,
  ConsistencyIssueSummary,
  ConsistencyCheckResult,
  ConsistencyIssueStatus,
  ConsistencyIssueSeverity,
  ConsistencyIssueType,
  EngineType,
} from '@/types/crossEngine';

// =============================================================================
// Response Transformers (snake_case to camelCase)
// =============================================================================

function transformTimelineEvent(
  data: Record<string, unknown>
): CrossLinkedTimelineEvent {
  return {
    eventId: data.eventId as string,
    eventDate: data.eventDate as string,
    eventType: data.eventType as string,
    description: data.description as string,
    documentId: (data.documentId as string | null) ?? null,
    documentName: (data.documentName as string | null) ?? null,
    sourcePage: (data.sourcePage as number | null) ?? null,
    confidence: (data.confidence as number) ?? 1.0,
  };
}

function transformContradiction(
  data: Record<string, unknown>
): CrossLinkedContradiction {
  return {
    contradictionId: data.contradictionId as string,
    contradictionType: data.contradictionType as string,
    severity: data.severity as 'high' | 'medium' | 'low',
    explanation: data.explanation as string,
    statementAExcerpt: data.statementAExcerpt as string,
    statementBExcerpt: data.statementBExcerpt as string,
    documentAId: data.documentAId as string,
    documentAName: data.documentAName as string,
    documentBId: data.documentBId as string,
    documentBName: data.documentBName as string,
    confidence: (data.confidence as number) ?? 0.5,
  };
}

function transformEntity(data: Record<string, unknown>): CrossLinkedEntity {
  return {
    entityId: data.entityId as string,
    canonicalName: data.canonicalName as string,
    entityType: data.entityType as string,
    aliases: (data.aliases as string[]) ?? [],
  };
}

// =============================================================================
// API Methods
// =============================================================================

/**
 * Cross-engine link API methods.
 * Gap 5-3: Cross-Engine Correlation Links
 */
export const crossEngineApi = {
  /**
   * Get the timeline journey for an entity.
   * Returns all timeline events involving the entity, ordered chronologically.
   *
   * @param matterId - Matter UUID
   * @param entityId - Entity UUID
   * @param options - Pagination and API options
   * @returns EntityJourneyResponse with timeline events
   */
  getEntityJourney: async (
    matterId: string,
    entityId: string,
    options?: {
      page?: number;
      perPage?: number;
    } & ApiMethodOptions
  ): Promise<EntityJourneyResponse> => {
    const { page = 1, perPage = 50, ...apiOptions } = options ?? {};
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
    });

    const response = await api.get<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/entity/${entityId}/journey?${params}`,
      apiOptions
    );

    const events = Array.isArray(response.events)
      ? response.events.map((e) => transformTimelineEvent(e as Record<string, unknown>))
      : [];

    return {
      entityId: response.entityId as string,
      entityName: response.entityName as string,
      entityType: response.entityType as string,
      events,
      totalEvents: (response.totalEvents as number) ?? events.length,
      dateRangeStart: (response.dateRangeStart as string | null) ?? null,
      dateRangeEnd: (response.dateRangeEnd as string | null) ?? null,
    };
  },

  /**
   * Get contradictions involving an entity.
   * Returns all contradictions where the entity appears in either statement.
   *
   * @param matterId - Matter UUID
   * @param entityId - Entity UUID
   * @param options - Pagination and API options
   * @returns EntityContradictionSummary with contradictions
   */
  getEntityContradictions: async (
    matterId: string,
    entityId: string,
    options?: {
      page?: number;
      perPage?: number;
    } & ApiMethodOptions
  ): Promise<EntityContradictionSummary> => {
    const { page = 1, perPage = 20, ...apiOptions } = options ?? {};
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
    });

    const response = await api.get<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/entity/${entityId}/contradictions?${params}`,
      apiOptions
    );

    const contradictions = Array.isArray(response.contradictions)
      ? response.contradictions.map((c) =>
          transformContradiction(c as Record<string, unknown>)
        )
      : [];

    return {
      entityId: response.entityId as string,
      entityName: response.entityName as string,
      contradictions,
      totalContradictions: (response.totalContradictions as number) ?? contradictions.length,
      highSeverityCount: (response.highSeverityCount as number) ?? 0,
      mediumSeverityCount: (response.mediumSeverityCount as number) ?? 0,
      lowSeverityCount: (response.lowSeverityCount as number) ?? 0,
    };
  },

  /**
   * Get cross-engine context for a timeline event.
   * Returns entities and contradictions related to the event.
   *
   * @param matterId - Matter UUID
   * @param eventId - Timeline event UUID
   * @param options - API options
   * @returns TimelineEventContext with entities and contradictions
   */
  getTimelineEventContext: async (
    matterId: string,
    eventId: string,
    options?: ApiMethodOptions
  ): Promise<TimelineEventContext> => {
    const response = await api.get<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/timeline/${eventId}/context`,
      options
    );

    const entities = Array.isArray(response.entities)
      ? response.entities.map((e) => transformEntity(e as Record<string, unknown>))
      : [];

    const relatedContradictions = Array.isArray(response.relatedContradictions)
      ? response.relatedContradictions.map((c) =>
          transformContradiction(c as Record<string, unknown>)
        )
      : [];

    return {
      eventId: response.eventId as string,
      eventDate: response.eventDate as string,
      eventType: response.eventType as string,
      description: response.description as string,
      documentId: (response.documentId as string | null) ?? null,
      documentName: (response.documentName as string | null) ?? null,
      entities,
      relatedContradictions,
    };
  },

  /**
   * Get cross-engine context for a contradiction.
   * Returns timeline events related to the contradiction's entity.
   *
   * @param matterId - Matter UUID
   * @param contradictionId - Contradiction UUID
   * @param options - API options
   * @returns ContradictionContext with related events
   */
  getContradictionContext: async (
    matterId: string,
    contradictionId: string,
    options?: ApiMethodOptions
  ): Promise<ContradictionContext> => {
    const response = await api.get<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/contradiction/${contradictionId}/context`,
      options
    );

    const relatedEvents = Array.isArray(response.relatedEvents)
      ? response.relatedEvents.map((e) =>
          transformTimelineEvent(e as Record<string, unknown>)
        )
      : [];

    return {
      contradictionId: response.contradictionId as string,
      entityId: response.entityId as string,
      entityName: response.entityName as string,
      contradictionType: response.contradictionType as string,
      severity: response.severity as string,
      explanation: response.explanation as string,
      relatedEvents,
    };
  },

  // ===========================================================================
  // Story 5.4: Consistency Issue Methods
  // ===========================================================================

  /**
   * Get consistency issues for a matter.
   * Returns paginated list of cross-engine consistency issues.
   *
   * @param matterId - Matter UUID
   * @param options - Filter and pagination options
   * @returns List of consistency issues with metadata
   */
  getConsistencyIssues: async (
    matterId: string,
    options?: {
      status?: ConsistencyIssueStatus;
      severity?: ConsistencyIssueSeverity;
      limit?: number;
      offset?: number;
    } & ApiMethodOptions
  ): Promise<{ data: ConsistencyIssue[]; meta: { limit: number; offset: number; count: number } }> => {
    const { status, severity, limit = 50, offset = 0, ...apiOptions } = options ?? {};
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (status) params.set('status', status);
    if (severity) params.set('severity', severity);

    const response = await api.get<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/consistency-issues?${params}`,
      apiOptions
    );

    const data = Array.isArray(response.data)
      ? response.data.map((issue) => transformConsistencyIssue(issue as Record<string, unknown>))
      : [];

    const meta = response.meta as { limit: number; offset: number; count: number } | undefined;

    return {
      data,
      meta: meta ?? { limit, offset, count: data.length },
    };
  },

  /**
   * Get consistency issue summary counts for a matter.
   *
   * @param matterId - Matter UUID
   * @param options - API options
   * @returns Summary counts by status and severity
   */
  getConsistencyIssueSummary: async (
    matterId: string,
    options?: ApiMethodOptions
  ): Promise<ConsistencyIssueSummary> => {
    const response = await api.get<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/consistency-issues/summary`,
      options
    );

    const data = response.data as Record<string, unknown> | undefined;

    return {
      totalCount: (data?.totalCount as number) ?? 0,
      openCount: (data?.openCount as number) ?? 0,
      warningCount: (data?.warningCount as number) ?? 0,
      errorCount: (data?.errorCount as number) ?? 0,
    };
  },

  /**
   * Update a consistency issue status.
   *
   * @param matterId - Matter UUID
   * @param issueId - Issue UUID
   * @param update - Status update payload
   * @param options - API options
   * @returns Success response
   */
  updateConsistencyIssue: async (
    matterId: string,
    issueId: string,
    update: {
      status?: ConsistencyIssueStatus;
      resolutionNotes?: string;
    },
    options?: ApiMethodOptions
  ): Promise<{ message: string; issueId: string }> => {
    const response = await api.patch<Record<string, unknown>>(
      `/api/matters/${matterId}/cross-engine/consistency-issues/${issueId}`,
      update,
      options
    );

    return {
      message: (response.message as string) ?? 'Issue updated successfully',
      issueId: (response.issueId as string) ?? issueId,
    };
  },

  /**
   * Run a consistency check for a matter.
   *
   * @param matterId - Matter UUID
   * @param options - Check options
   * @returns Check result with issues found
   */
  runConsistencyCheck: async (
    matterId: string,
    options?: {
      engines?: string[];
    } & ApiMethodOptions
  ): Promise<ConsistencyCheckResult> => {
    const { engines, ...apiOptions } = options ?? {};
    const params = new URLSearchParams();
    if (engines) {
      engines.forEach((e) => params.append('engines', e));
    }

    const url = engines?.length
      ? `/api/matters/${matterId}/cross-engine/consistency-issues/check?${params}`
      : `/api/matters/${matterId}/cross-engine/consistency-issues/check`;

    const response = await api.post<Record<string, unknown>>(url, {}, apiOptions);

    return {
      issuesFound: (response.issuesFound as number) ?? 0,
      issuesCreated: (response.issuesCreated as number) ?? 0,
      enginesChecked: (response.enginesChecked as string[]) ?? [],
      durationMs: (response.durationMs as number) ?? 0,
    };
  },
};

// =============================================================================
// Story 5.4: Consistency Issue Transformer
// =============================================================================

function transformConsistencyIssue(data: Record<string, unknown>): ConsistencyIssue {
  // Validate required fields with sensible defaults
  const id = typeof data.id === 'string' ? data.id : '';
  const matterId = typeof data.matterId === 'string' ? data.matterId : '';
  const issueType = typeof data.issueType === 'string' ? data.issueType as ConsistencyIssueType : 'date_mismatch';
  const severity = typeof data.severity === 'string' ? data.severity as ConsistencyIssueSeverity : 'warning';
  const sourceEngine = typeof data.sourceEngine === 'string' ? data.sourceEngine as EngineType : 'timeline';
  const conflictingEngine = typeof data.conflictingEngine === 'string' ? data.conflictingEngine as EngineType : 'entity';
  const description = typeof data.description === 'string' ? data.description : '';
  const status = typeof data.status === 'string' ? data.status as ConsistencyIssueStatus : 'open';
  const detectedAt = typeof data.detectedAt === 'string' ? data.detectedAt : new Date().toISOString();
  const createdAt = typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString();
  const updatedAt = typeof data.updatedAt === 'string' ? data.updatedAt : new Date().toISOString();

  return {
    id,
    matterId,
    issueType,
    severity,
    sourceEngine,
    sourceId: typeof data.sourceId === 'string' ? data.sourceId : null,
    sourceValue: typeof data.sourceValue === 'string' ? data.sourceValue : null,
    conflictingEngine,
    conflictingId: typeof data.conflictingId === 'string' ? data.conflictingId : null,
    conflictingValue: typeof data.conflictingValue === 'string' ? data.conflictingValue : null,
    description,
    documentId: typeof data.documentId === 'string' ? data.documentId : null,
    documentName: typeof data.documentName === 'string' ? data.documentName : null,
    status,
    resolvedBy: typeof data.resolvedBy === 'string' ? data.resolvedBy : null,
    resolvedAt: typeof data.resolvedAt === 'string' ? data.resolvedAt : null,
    resolutionNotes: typeof data.resolutionNotes === 'string' ? data.resolutionNotes : null,
    detectedAt,
    createdAt,
    updatedAt,
    metadata: typeof data.metadata === 'object' && data.metadata !== null
      ? data.metadata as Record<string, unknown>
      : {},
  };
}
