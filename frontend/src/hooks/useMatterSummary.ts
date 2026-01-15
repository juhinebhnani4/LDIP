/**
 * Matter Summary Hook
 *
 * SWR hook for fetching matter summary data.
 * Story 14.1: Summary API Endpoint - Real API integration.
 *
 * Story 10B.1: Summary Tab Content (UI implementation)
 * Story 14.1: Summary API Endpoint (Backend integration)
 */

import useSWR from 'swr';
import type { MatterSummaryResponse } from '@/types/summary';
import { api, ApiError } from '@/lib/api/client';

/**
 * Fetcher that calls the real summary API endpoint.
 * Story 14.1: AC #1 - GET /api/matters/{matter_id}/summary
 *
 * @param url - API endpoint URL
 * @returns MatterSummaryResponse from backend
 */
async function summaryFetcher(url: string): Promise<MatterSummaryResponse> {
  return api.get<MatterSummaryResponse>(url);
}

/**
 * Hook options for matter summary
 */
interface UseMatterSummaryOptions {
  /** Force refresh from server, bypassing cache */
  forceRefresh?: boolean;
}

/**
 * Hook for fetching matter summary data
 *
 * Story 14.1: AC #1, #2 - Real API integration
 *
 * @param matterId - The matter ID to fetch summary for
 * @param options - Optional hook configuration
 * @returns Summary data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { summary, isLoading, isError, mutate } = useMatterSummary(matterId);
 *
 * if (isLoading) return <SummarySkeleton />;
 * if (isError) return <SummaryError />;
 *
 * return <SummaryContent summary={summary} />;
 * ```
 */
export function useMatterSummary(
  matterId: string,
  options: UseMatterSummaryOptions = {}
) {
  const { forceRefresh = false } = options;

  // Build URL with optional forceRefresh query param
  const url = matterId
    ? `/api/matters/${matterId}/summary${forceRefresh ? '?forceRefresh=true' : ''}`
    : null;

  const { data, error, isLoading, mutate } = useSWR<MatterSummaryResponse, ApiError>(
    url,
    summaryFetcher,
    {
      // Keep data fresh but don't refetch too frequently
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds
      // Don't retry on 4xx errors
      shouldRetryOnError: (err) => {
        if (err instanceof ApiError && err.status >= 400 && err.status < 500) {
          return false;
        }
        return true;
      },
    }
  );

  return {
    /** The matter summary data */
    summary: data?.data,
    /** Whether the data is currently loading */
    isLoading,
    /** Whether an error occurred */
    isError: !!error,
    /** Error object if available */
    error,
    /** Error code for specific error handling */
    errorCode: error?.code,
    /** Function to manually revalidate */
    mutate,
    /**
     * Force refresh summary from server
     * Story 14.1: AC #4 - Force refresh to bypass cache
     */
    refresh: () =>
      mutate(
        api.get<MatterSummaryResponse>(
          `/api/matters/${matterId}/summary?forceRefresh=true`
        ),
        { revalidate: false }
      ),
  };
}
