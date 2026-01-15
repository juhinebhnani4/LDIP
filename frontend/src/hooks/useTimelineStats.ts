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
 * Real fetcher - transforms snake_case API response to camelCase
 * Uses the API client for proper auth handling
 */
async function fetcher(url: string): Promise<TimelineStatsResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{
    data: {
      total_events: number;
      events_by_type: Record<string, number>;
      entities_involved: number;
      date_range_start: string | null;
      date_range_end: string | null;
      events_with_entities: number;
      events_without_entities: number;
      verified_events: number;
    };
  }>(url);

  // Transform snake_case API response to camelCase
  return {
    data: {
      totalEvents: response.data.total_events,
      eventsByType: response.data.events_by_type,
      entitiesInvolved: response.data.entities_involved,
      dateRangeStart: response.data.date_range_start,
      dateRangeEnd: response.data.date_range_end,
      eventsWithEntities: response.data.events_with_entities,
      eventsWithoutEntities: response.data.events_without_entities,
      verifiedEvents: response.data.verified_events,
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
