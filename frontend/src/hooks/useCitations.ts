/**
 * useCitations Hook
 *
 * SWR-based hooks for citation data fetching with filtering and pagination.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import useSWR from 'swr';
import useSWRMutation from 'swr/mutation';
import {
  getCitations,
  getCitationStats,
  getCitationSummary,
  getActDiscoveryReport,
  markActUploaded,
  markActSkipped,
  markActUploadedAndVerify,
} from '@/lib/api/citations';
import type {
  CitationListOptions,
  CitationListItem,
  CitationStats,
  CitationSummaryItem,
  ActDiscoverySummary,
  MarkActUploadedRequest,
  MarkActSkippedRequest,
  VerificationStatus,
} from '@/types';
import type { PaginationMeta } from '@/types/citation';

// =============================================================================
// Types
// =============================================================================

export interface CitationsFilterState {
  verificationStatus: VerificationStatus | null;
  actName: string | null;
  showOnlyIssues: boolean;
}

export interface UseCitationsListOptions {
  page?: number;
  perPage?: number;
  filters?: CitationsFilterState;
}

export interface UseCitationsListResult {
  citations: CitationListItem[];
  meta: PaginationMeta | null;
  isLoading: boolean;
  error: Error | null;
  mutate: () => Promise<void>;
}

export interface UseCitationStatsResult {
  stats: CitationStats | null;
  isLoading: boolean;
  error: Error | null;
  mutate: () => Promise<void>;
}

export interface UseCitationSummaryResult {
  summary: CitationSummaryItem[];
  isLoading: boolean;
  error: Error | null;
  mutate: () => Promise<void>;
}

export interface UseActDiscoveryResult {
  acts: ActDiscoverySummary[];
  missingCount: number;
  availableCount: number;
  skippedCount: number;
  isLoading: boolean;
  error: Error | null;
  mutate: () => Promise<void>;
}

export interface UseActMutationsResult {
  markUploaded: (request: MarkActUploadedRequest) => Promise<void>;
  markSkipped: (request: MarkActSkippedRequest) => Promise<void>;
  markUploadedAndVerify: (request: MarkActUploadedRequest) => Promise<void>;
  isLoading: boolean;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Build API options from filter state.
 */
function buildApiOptions(
  options: UseCitationsListOptions
): CitationListOptions {
  const { page = 1, perPage = 20, filters } = options;
  const apiOptions: CitationListOptions = {
    page,
    perPage,
  };

  if (filters) {
    if (filters.verificationStatus) {
      apiOptions.verificationStatus = filters.verificationStatus;
    }
    if (filters.actName) {
      apiOptions.actName = filters.actName;
    }
  }

  return apiOptions;
}

/**
 * Determine if a verification status is considered an "issue".
 */
function isIssueStatus(status: VerificationStatus): boolean {
  return (
    status === 'mismatch' ||
    status === 'section_not_found' ||
    status === 'act_unavailable'
  );
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Hook for fetching paginated list of citations with filtering.
 *
 * @param matterId - Matter UUID
 * @param options - Pagination and filter options
 * @returns Citations list with pagination metadata
 *
 * @example
 * ```tsx
 * const { citations, meta, isLoading } = useCitationsList(matterId, {
 *   page: 1,
 *   perPage: 20,
 *   filters: { verificationStatus: 'pending', actName: null, showOnlyIssues: false },
 * });
 * ```
 */
export function useCitationsList(
  matterId: string,
  options: UseCitationsListOptions = {}
): UseCitationsListResult {
  const apiOptions = buildApiOptions(options);
  const { filters } = options;

  // Build cache key from all parameters
  const cacheKey = matterId
    ? [
        'citations',
        matterId,
        apiOptions.page,
        apiOptions.perPage,
        apiOptions.verificationStatus ?? '',
        apiOptions.actName ?? '',
        filters?.showOnlyIssues ? 'issues' : '',
      ].join('/')
    : null;

  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    async () => {
      const response = await getCitations(matterId, apiOptions);

      // Apply client-side "show only issues" filter if enabled
      if (filters?.showOnlyIssues) {
        return {
          data: response.data.filter((c) => isIssueStatus(c.verificationStatus)),
          meta: response.meta,
        };
      }

      return response;
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    }
  );

  return {
    citations: data?.data ?? [],
    meta: data?.meta ?? null,
    isLoading,
    error: error ?? null,
    mutate: async () => {
      await mutate();
    },
  };
}

/**
 * Hook for fetching citation statistics.
 *
 * @param matterId - Matter UUID
 * @returns Citation statistics
 *
 * @example
 * ```tsx
 * const { stats, isLoading } = useCitationStats(matterId);
 * console.log(stats?.totalCitations);
 * ```
 */
export function useCitationStats(matterId: string): UseCitationStatsResult {
  const cacheKey = matterId ? `citations/stats/${matterId}` : null;

  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    () => getCitationStats(matterId),
    {
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  );

  return {
    stats: data ?? null,
    isLoading,
    error: error ?? null,
    mutate: async () => {
      await mutate();
    },
  };
}

/**
 * Hook for fetching citation summary grouped by Act.
 *
 * @param matterId - Matter UUID
 * @returns Citation summary by Act
 *
 * @example
 * ```tsx
 * const { summary, isLoading } = useCitationSummaryByAct(matterId);
 * summary.forEach(item => console.log(`${item.actName}: ${item.citationCount}`));
 * ```
 */
export function useCitationSummaryByAct(
  matterId: string
): UseCitationSummaryResult {
  const cacheKey = matterId ? `citations/summary/${matterId}` : null;

  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    () => getCitationSummary(matterId),
    {
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  );

  return {
    summary: data?.data ?? [],
    isLoading,
    error: error ?? null,
    mutate: async () => {
      await mutate();
    },
  };
}

/**
 * Hook for fetching Act Discovery Report.
 *
 * @param matterId - Matter UUID
 * @returns Act discovery data with missing/available/skipped counts
 *
 * @example
 * ```tsx
 * const { acts, missingCount, isLoading } = useActDiscoveryReport(matterId);
 * const missingActs = acts.filter(a => a.resolutionStatus === 'missing');
 * ```
 */
export function useActDiscoveryReport(matterId: string): UseActDiscoveryResult {
  const cacheKey = matterId ? `citations/acts/discovery/${matterId}` : null;

  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    () => getActDiscoveryReport(matterId, true),
    {
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  );

  const acts = data?.data ?? [];
  const missingCount = acts.filter((a) => a.resolutionStatus === 'missing').length;
  const availableCount = acts.filter((a) => a.resolutionStatus === 'available').length;
  const skippedCount = acts.filter((a) => a.resolutionStatus === 'skipped').length;

  return {
    acts,
    missingCount,
    availableCount,
    skippedCount,
    isLoading,
    error: error ?? null,
    mutate: async () => {
      await mutate();
    },
  };
}

/**
 * Hook for Act mutation operations (upload, skip, upload+verify).
 *
 * @param matterId - Matter UUID
 * @returns Mutation functions for Act operations
 *
 * @example
 * ```tsx
 * const { markUploaded, markSkipped, markUploadedAndVerify, isLoading } = useActMutations(matterId);
 *
 * await markUploadedAndVerify({
 *   actName: 'Negotiable Instruments Act, 1881',
 *   actDocumentId: 'doc-123',
 * });
 * ```
 */
export function useActMutations(matterId: string): UseActMutationsResult {
  const uploadMutation = useSWRMutation(
    `citations/acts/upload/${matterId}`,
    async (_key: string, { arg }: { arg: MarkActUploadedRequest }) => {
      return markActUploaded(matterId, arg);
    }
  );

  const skipMutation = useSWRMutation(
    `citations/acts/skip/${matterId}`,
    async (_key: string, { arg }: { arg: MarkActSkippedRequest }) => {
      return markActSkipped(matterId, arg);
    }
  );

  const uploadVerifyMutation = useSWRMutation(
    `citations/acts/upload-verify/${matterId}`,
    async (_key: string, { arg }: { arg: MarkActUploadedRequest }) => {
      return markActUploadedAndVerify(matterId, arg);
    }
  );

  return {
    markUploaded: async (request: MarkActUploadedRequest) => {
      await uploadMutation.trigger(request);
    },
    markSkipped: async (request: MarkActSkippedRequest) => {
      await skipMutation.trigger(request);
    },
    markUploadedAndVerify: async (request: MarkActUploadedRequest) => {
      await uploadVerifyMutation.trigger(request);
    },
    isLoading:
      uploadMutation.isMutating ||
      skipMutation.isMutating ||
      uploadVerifyMutation.isMutating,
  };
}

/**
 * Hook for computing issue statistics from stats data.
 *
 * @param stats - Citation statistics
 * @returns Issue-related counts
 */
export function useCitationIssueStats(stats: CitationStats | null) {
  if (!stats) {
    return {
      totalIssues: 0,
      mismatchCount: 0,
      notFoundCount: 0,
      actUnavailableCount: 0,
    };
  }

  // Issue count is total - verified - pending
  const issueCount =
    stats.totalCitations - stats.verifiedCount - stats.pendingCount;

  return {
    totalIssues: issueCount > 0 ? issueCount : 0,
    mismatchCount: 0, // Would need separate API endpoint for breakdown
    notFoundCount: 0,
    actUnavailableCount: stats.missingActsCount,
  };
}

/**
 * Get unique Act names from citation summary for filter dropdown.
 *
 * @param summary - Citation summary data
 * @returns Sorted list of unique Act names
 */
export function getActNamesFromSummary(summary: CitationSummaryItem[]): string[] {
  return summary.map((s) => s.actName).sort();
}
