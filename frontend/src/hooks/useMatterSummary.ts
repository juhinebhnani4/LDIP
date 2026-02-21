/**
 * Matter Summary Hook
 *
 * SWR hook for fetching matter summary data.
 * Story 14.1: Summary API Endpoint - Real API integration.
 *
 * Story 10B.1: Summary Tab Content (UI implementation)
 * Story 14.1: Summary API Endpoint (Backend integration)
 *
 * Supports background generation: when the backend returns status="generating",
 * the hook polls every 3 seconds until the summary is ready or failed.
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
 * Hook for fetching matter summary data
 *
 * Story 14.1: AC #1, #2 - Real API integration
 *
 * @param matterId - The matter ID to fetch summary for
 * @returns Summary data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { summary, isLoading, isError, isGenerating, progress, stage } = useMatterSummary(matterId);
 *
 * if (isLoading) return <SummarySkeleton />;
 * if (isGenerating) return <SummaryGenerating progress={progress} stage={stage} />;
 * if (isError) return <SummaryError />;
 *
 * return <SummaryContent summary={summary} />;
 * ```
 */
export function useMatterSummary(matterId: string) {
  // SWR key never includes forceRefresh — that's a one-time mutation only.
  // This prevents the polling loop from re-dispatching jobs on every tick.
  const url = matterId ? `/api/matters/${matterId}/summary` : null;

  const { data, error, isLoading, mutate } = useSWR<MatterSummaryResponse, ApiError>(
    url,
    summaryFetcher,
    {
      // Keep data fresh but don't refetch too frequently
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds
      // Poll every 3s while generating, stop otherwise
      refreshInterval: (latestData: MatterSummaryResponse | undefined) => {
        if (latestData?.status === 'generating') return 3000;
        return 0;
      },
      // Don't retry on 4xx errors
      shouldRetryOnError: (err) => {
        if (err instanceof ApiError && err.status >= 400 && err.status < 500) {
          return false;
        }
        return true;
      },
    }
  );

  const isGenerating = data?.status === 'generating';
  const isFailed = data?.status === 'failed';

  return {
    /** The matter summary data (only when status is "ready") */
    summary: data?.status === 'ready' ? data.data ?? undefined : undefined,
    /** Whether the data is currently loading (initial fetch) */
    isLoading,
    /** Whether summary is being generated in background */
    isGenerating,
    /** Generation progress percentage */
    progress: data?.progress,
    /** Current generation stage */
    stage: data?.stage,
    /** Background job ID */
    jobId: data?.jobId,
    /** Whether an error occurred (API error or generation failure) */
    isError: !!error || isFailed,
    /** Error object if available */
    error,
    /** Error message from failed generation */
    generationError: data?.error,
    /** Error code for specific error handling */
    errorCode: error?.code,
    /** Function to manually revalidate */
    mutate,
    /**
     * Force refresh summary from server.
     * Story 14.1: AC #4 - Force refresh to bypass cache.
     * Dispatches a one-time request with forceRefresh=true, then SWR
     * switches back to polling the plain URL (no forceRefresh).
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
