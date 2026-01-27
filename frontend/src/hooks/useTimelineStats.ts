/**
 * Timeline Stats Hook
 *
 * SWR hook for fetching timeline statistics.
 * Connected to real backend API at /api/matters/{matterId}/timeline/stats
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */

import useSWR from 'swr';
import type { TimelineStatsResponse } from '@/types/timeline';

/**
 * Real fetcher - API returns camelCase due to Pydantic aliases
 * Uses the API client for proper auth handling
 */
async function fetcher(url: string): Promise<TimelineStatsResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{
    data: {
      // API returns camelCase due to Pydantic alias configuration
      totalEvents: number;
      eventsByType: Record<string, number>;
      entitiesInvolved: number;
      dateRangeStart: string | null;
      dateRangeEnd: string | null;
      eventsWithEntities: number;
      eventsWithoutEntities: number;
      verifiedEvents: number;
    };
  }>(url);

  // API already returns camelCase, pass through directly
  return {
    data: {
      totalEvents: response.data.totalEvents,
      eventsByType: response.data.eventsByType,
      entitiesInvolved: response.data.entitiesInvolved,
      dateRangeStart: response.data.dateRangeStart,
      dateRangeEnd: response.data.dateRangeEnd,
      eventsWithEntities: response.data.eventsWithEntities,
      eventsWithoutEntities: response.data.eventsWithoutEntities,
      verifiedEvents: response.data.verifiedEvents,
    },
  };
}

/**
 * Hook for fetching timeline statistics
 *
 * @param matterId - The matter ID to fetch stats for
 * @returns Stats data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { stats, isLoading, isError } = useTimelineStats(matterId);
 *
 * if (isLoading) return <StatsSkeleton />;
 * if (isError) return <StatsError />;
 *
 * return <TimelineHeader stats={stats} />;
 * ```
 */
export function useTimelineStats(matterId: string) {
  const { data, error, isLoading, mutate } = useSWR<TimelineStatsResponse>(
    matterId ? `/api/matters/${matterId}/timeline/stats` : null,
    fetcher,
    {
      // Stats change less frequently
      revalidateOnFocus: false,
      dedupingInterval: 60000, // 1 minute
    }
  );

  return {
    /** The timeline statistics */
    stats: data?.data,
    /** Whether the data is currently loading */
    isLoading,
    /** Whether an error occurred */
    isError: !!error,
    /** Error object if available */
    error,
    /** Function to manually revalidate */
    mutate,
  };
}
