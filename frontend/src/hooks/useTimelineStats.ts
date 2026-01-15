/**
 * Timeline Stats Hook
 *
 * SWR hook for fetching timeline statistics.
 * Uses mock data for MVP - actual API integration exists.
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */

import useSWR from 'swr';
import type { TimelineStats, TimelineStatsResponse } from '@/types/timeline';

/** Mock stats for MVP */
const MOCK_STATS: TimelineStats = {
  totalEvents: 47,
  eventsByType: {
    filing: 12,
    notice: 8,
    hearing: 10,
    order: 7,
    transaction: 5,
    document: 3,
    deadline: 2,
  },
  entitiesInvolved: 24,
  dateRangeStart: '2016-05-15',
  dateRangeEnd: '2024-01-15',
  eventsWithEntities: 38,
  eventsWithoutEntities: 9,
  verifiedEvents: 18,
};

/**
 * Mock fetcher for MVP - simulates API call
 * TODO(Story-10B.5): Replace with actual API call when ready
 */
async function mockFetcher(): Promise<TimelineStatsResponse> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 400));

  return {
    data: MOCK_STATS,
  };
}

/**
 * Real fetcher for production - transforms snake_case to camelCase
 * TODO(Story-10B.5): Enable this when backend API is verified and working
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
async function realFetcher(url: string): Promise<TimelineStatsResponse> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error('Failed to fetch timeline stats');
  }
  const json = await res.json();

  // Transform snake_case API response to camelCase
  return {
    data: {
      totalEvents: json.data.total_events,
      eventsByType: json.data.events_by_type,
      entitiesInvolved: json.data.entities_involved,
      dateRangeStart: json.data.date_range_start,
      dateRangeEnd: json.data.date_range_end,
      eventsWithEntities: json.data.events_with_entities,
      eventsWithoutEntities: json.data.events_without_entities,
      verifiedEvents: json.data.verified_events,
    },
  };
}

// TODO(Story-10B.5): Switch to realFetcher when backend API is verified
const fetcher = mockFetcher;

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
