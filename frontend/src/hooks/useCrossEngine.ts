/**
 * Cross-Engine Data Hooks
 *
 * Gap 5-3: Cross-Engine Correlation Links
 *
 * React hooks for fetching cross-engine correlation data with SWR caching.
 */

import useSWR, { useSWRConfig } from 'swr';
import { useState, useCallback } from 'react';
import { crossEngineApi } from '@/lib/api/crossEngine';
import type {
  EntityJourneyResponse,
  EntityContradictionSummary,
  TimelineEventContext,
  ContradictionContext,
  ConsistencyIssue,
  ConsistencyIssueSummary,
  ConsistencyIssueStatus,
  ConsistencyIssueSeverity,
  ConsistencyCheckResult,
} from '@/types/crossEngine';

// =============================================================================
// SWR Configuration
// =============================================================================

const SWR_CONFIG = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  dedupingInterval: 60_000, // 1 minute deduplication
  errorRetryCount: 2,
};

// =============================================================================
// Entity Journey Hook
// =============================================================================

interface UseEntityJourneyOptions {
  page?: number;
  perPage?: number;
  enabled?: boolean;
}

/**
 * Hook to fetch timeline events for an entity (entity journey).
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID (null to disable fetching)
 * @param options - Pagination and fetch options
 * @returns Entity journey data, loading state, and error
 */
export function useEntityJourney(
  matterId: string,
  entityId: string | null,
  options: UseEntityJourneyOptions = {}
) {
  const { page = 1, perPage = 50, enabled = true } = options;

  const key =
    entityId && enabled
      ? ['entity-journey', matterId, entityId, page, perPage]
      : null;

  const { data, error, isLoading, isValidating, mutate } = useSWR<EntityJourneyResponse>(
    key,
    () => crossEngineApi.getEntityJourney(matterId, entityId!, { page, perPage }),
    SWR_CONFIG
  );

  return {
    journey: data ?? null,
    events: data?.events ?? [],
    totalEvents: data?.totalEvents ?? 0,
    dateRange: data
      ? { start: data.dateRangeStart, end: data.dateRangeEnd }
      : null,
    isLoading,
    isValidating,
    error: error instanceof Error ? error.message : null,
    mutate,
  };
}

// =============================================================================
// Entity Contradictions Hook
// =============================================================================

interface UseEntityContradictionsOptions {
  page?: number;
  perPage?: number;
  enabled?: boolean;
}

/**
 * Hook to fetch contradictions involving an entity.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID (null to disable fetching)
 * @param options - Pagination and fetch options
 * @returns Entity contradictions data, loading state, and error
 */
export function useEntityContradictions(
  matterId: string,
  entityId: string | null,
  options: UseEntityContradictionsOptions = {}
) {
  const { page = 1, perPage = 20, enabled = true } = options;

  const key =
    entityId && enabled
      ? ['entity-contradictions', matterId, entityId, page, perPage]
      : null;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<EntityContradictionSummary>(
      key,
      () => crossEngineApi.getEntityContradictions(matterId, entityId!, { page, perPage }),
      SWR_CONFIG
    );

  return {
    summary: data ?? null,
    contradictions: data?.contradictions ?? [],
    totalContradictions: data?.totalContradictions ?? 0,
    severityCounts: data
      ? {
          high: data.highSeverityCount,
          medium: data.mediumSeverityCount,
          low: data.lowSeverityCount,
        }
      : null,
    isLoading,
    isValidating,
    error: error instanceof Error ? error.message : null,
    mutate,
  };
}

// =============================================================================
// Timeline Event Context Hook
// =============================================================================

interface UseTimelineEventContextOptions {
  enabled?: boolean;
}

/**
 * Hook to fetch cross-engine context for a timeline event.
 *
 * @param matterId - Matter UUID
 * @param eventId - Event UUID (null to disable fetching)
 * @param options - Fetch options
 * @returns Event context data, loading state, and error
 */
export function useTimelineEventContext(
  matterId: string,
  eventId: string | null,
  options: UseTimelineEventContextOptions = {}
) {
  const { enabled = true } = options;

  const key =
    eventId && enabled
      ? ['timeline-event-context', matterId, eventId]
      : null;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<TimelineEventContext>(
      key,
      () => crossEngineApi.getTimelineEventContext(matterId, eventId!),
      SWR_CONFIG
    );

  return {
    context: data ?? null,
    entities: data?.entities ?? [],
    contradictions: data?.relatedContradictions ?? [],
    isLoading,
    isValidating,
    error: error instanceof Error ? error.message : null,
    mutate,
  };
}

// =============================================================================
// Contradiction Context Hook
// =============================================================================

interface UseContradictionContextOptions {
  enabled?: boolean;
}

/**
 * Hook to fetch cross-engine context for a contradiction.
 *
 * @param matterId - Matter UUID
 * @param contradictionId - Contradiction UUID (null to disable fetching)
 * @param options - Fetch options
 * @returns Contradiction context data, loading state, and error
 */
export function useContradictionContext(
  matterId: string,
  contradictionId: string | null,
  options: UseContradictionContextOptions = {}
) {
  const { enabled = true } = options;

  const key =
    contradictionId && enabled
      ? ['contradiction-context', matterId, contradictionId]
      : null;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<ContradictionContext>(
      key,
      () => crossEngineApi.getContradictionContext(matterId, contradictionId!),
      SWR_CONFIG
    );

  return {
    context: data ?? null,
    events: data?.relatedEvents ?? [],
    entityId: data?.entityId ?? null,
    entityName: data?.entityName ?? null,
    isLoading,
    isValidating,
    error: error instanceof Error ? error.message : null,
    mutate,
  };
}

// =============================================================================
// Combined Cross-Engine Counts Hook
// =============================================================================

interface UseCrossEngineCountsOptions {
  enabled?: boolean;
}

/**
 * Hook to fetch all cross-engine counts for an entity.
 * Useful for showing badges with counts.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID (null to disable fetching)
 * @param options - Fetch options
 * @returns Combined counts data
 */
export function useCrossEngineCounts(
  matterId: string,
  entityId: string | null,
  options: UseCrossEngineCountsOptions = {}
) {
  const { enabled = true } = options;

  const journey = useEntityJourney(matterId, entityId, { enabled, perPage: 1 });
  const contradictions = useEntityContradictions(matterId, entityId, {
    enabled,
    perPage: 1,
  });

  const isLoading = journey.isLoading || contradictions.isLoading;
  const error = journey.error || contradictions.error;

  return {
    timelineEventCount: journey.totalEvents,
    contradictionCount: contradictions.totalContradictions,
    highSeverityCount: contradictions.severityCounts?.high ?? 0,
    dateRange: journey.dateRange,
    isLoading,
    error,
  };
}

// =============================================================================
// Story 5.4: Consistency Issue Hooks
// =============================================================================

interface UseConsistencyIssuesOptions {
  status?: ConsistencyIssueStatus;
  severity?: ConsistencyIssueSeverity;
  limit?: number;
  offset?: number;
  enabled?: boolean;
}

/**
 * Hook to fetch consistency issues for a matter.
 *
 * Story 5.4: Cross-Engine Consistency Checking
 *
 * @param matterId - Matter UUID
 * @param options - Filter and pagination options
 * @returns Consistency issues data, loading state, and error
 */
export function useConsistencyIssues(
  matterId: string | null,
  options: UseConsistencyIssuesOptions = {}
) {
  const { status, severity, limit = 50, offset = 0, enabled = true } = options;

  const key =
    matterId && enabled
      ? ['consistency-issues', matterId, status, severity, limit, offset]
      : null;

  const { data, error, isLoading, isValidating, mutate } = useSWR<{
    data: ConsistencyIssue[];
    meta: { limit: number; offset: number; count: number };
  }>(
    key,
    () => crossEngineApi.getConsistencyIssues(matterId!, { status, severity, limit, offset }),
    SWR_CONFIG
  );

  return {
    issues: data?.data ?? [],
    meta: data?.meta ?? { limit, offset, count: 0 },
    isLoading,
    isValidating,
    error: error instanceof Error ? error.message : null,
    mutate,
  };
}

interface UseConsistencyIssueSummaryOptions {
  enabled?: boolean;
}

/**
 * Hook to fetch consistency issue summary counts for a matter.
 *
 * Story 5.4: Cross-Engine Consistency Checking
 *
 * @param matterId - Matter UUID
 * @param options - Fetch options
 * @returns Summary counts data
 */
export function useConsistencyIssueSummary(
  matterId: string | null,
  options: UseConsistencyIssueSummaryOptions = {}
) {
  const { enabled = true } = options;

  const key =
    matterId && enabled
      ? ['consistency-issue-summary', matterId]
      : null;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<ConsistencyIssueSummary>(
      key,
      () => crossEngineApi.getConsistencyIssueSummary(matterId!),
      SWR_CONFIG
    );

  return {
    summary: data ?? null,
    totalCount: data?.totalCount ?? 0,
    openCount: data?.openCount ?? 0,
    warningCount: data?.warningCount ?? 0,
    errorCount: data?.errorCount ?? 0,
    isLoading,
    isValidating,
    error: error instanceof Error ? error.message : null,
    mutate,
  };
}

/**
 * Hook for consistency issue mutations (update status, run check).
 *
 * Story 5.4: Cross-Engine Consistency Checking
 *
 * @param matterId - Matter UUID
 * @returns Mutation functions and loading states
 */
export function useConsistencyIssueMutations(matterId: string | null) {
  const { mutate } = useSWRConfig();
  const [isUpdating, setIsUpdating] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<ConsistencyCheckResult | null>(null);

  /**
   * Update an issue's status
   */
  const updateIssueStatus = useCallback(
    async (
      issueId: string,
      status: ConsistencyIssueStatus,
      resolutionNotes?: string
    ) => {
      if (!matterId) return false;

      setIsUpdating(true);
      setError(null);

      try {
        await crossEngineApi.updateConsistencyIssue(matterId, issueId, {
          status,
          resolutionNotes,
        });

        // Invalidate related caches
        mutate((key) => {
          if (Array.isArray(key)) {
            return key[0] === 'consistency-issues' || key[0] === 'consistency-issue-summary';
          }
          return false;
        });

        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update issue');
        return false;
      } finally {
        setIsUpdating(false);
      }
    },
    [matterId, mutate]
  );

  /**
   * Run a consistency check
   */
  const runConsistencyCheck = useCallback(
    async (engines?: string[]) => {
      if (!matterId) return null;

      setIsChecking(true);
      setError(null);
      setCheckResult(null);

      try {
        const result = await crossEngineApi.runConsistencyCheck(matterId, { engines });
        setCheckResult(result);

        // Invalidate related caches
        mutate((key) => {
          if (Array.isArray(key)) {
            return key[0] === 'consistency-issues' || key[0] === 'consistency-issue-summary';
          }
          return false;
        });

        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to run consistency check');
        return null;
      } finally {
        setIsChecking(false);
      }
    },
    [matterId, mutate]
  );

  return {
    updateIssueStatus,
    runConsistencyCheck,
    isUpdating,
    isChecking,
    error,
    checkResult,
  };
}
