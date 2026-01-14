'use client';

/**
 * Verification Stats Hook
 *
 * Custom hook for fetching verification statistics with polling.
 *
 * Story 8-5: Implement Verification Queue UI (Task 9.2)
 */

import { useCallback, useEffect } from 'react';
import { useVerificationStore } from '@/stores/verificationStore';
import { verificationsApi } from '@/lib/api/verifications';
import type { VerificationStats } from '@/types';

interface UseVerificationStatsOptions {
  /** Matter ID to fetch stats for */
  matterId: string;
  /** Enable auto-polling (default true) */
  enablePolling?: boolean;
  /** Polling interval in ms (default 30000) */
  pollInterval?: number;
}

interface UseVerificationStatsReturn {
  /** Verification statistics */
  stats: VerificationStats | null;
  /** Loading state */
  isLoading: boolean;
  /** Error message */
  error: string | null;
  /** Completion percentage (0-100) */
  completionPercent: number;
  /** Whether export is blocked */
  exportBlocked: boolean;
  /** Number of findings blocking export */
  blockingCount: number;
  /** Refresh stats manually */
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching verification statistics with polling.
 *
 * @param options - Configuration options
 * @returns Stats state and actions
 *
 * @example
 * ```tsx
 * const {
 *   stats,
 *   completionPercent,
 *   isLoading,
 * } = useVerificationStats({ matterId: 'matter-123' });
 *
 * // Display progress
 * console.log(`${completionPercent}% complete`);
 * ```
 */
export function useVerificationStats(
  options: UseVerificationStatsOptions
): UseVerificationStatsReturn {
  const { matterId, enablePolling = true, pollInterval = 30000 } = options;

  // Store selectors
  const stats = useVerificationStore((state) => state.stats);
  const isLoading = useVerificationStore((state) => state.isLoadingStats);
  const error = useVerificationStore((state) => state.error);

  // Store actions
  const setStats = useVerificationStore((state) => state.setStats);
  const setLoadingStats = useVerificationStore((state) => state.setLoadingStats);
  const setError = useVerificationStore((state) => state.setError);

  // Computed values
  const completionPercent = stats
    ? stats.totalVerifications > 0
      ? Math.round(
          ((stats.approvedCount + stats.rejectedCount) / stats.totalVerifications) *
            100
        )
      : 0
    : 0;

  const exportBlocked = stats?.exportBlocked ?? false;
  const blockingCount = stats?.blockingCount ?? 0;

  // Fetch stats from API
  const fetchStats = useCallback(async () => {
    try {
      setLoadingStats(true);
      const data = await verificationsApi.getStats(matterId);
      setStats(data);
      setError(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load verification stats';
      setError(message);
    } finally {
      setLoadingStats(false);
    }
  }, [matterId, setLoadingStats, setStats, setError]);

  // Initial fetch
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Set up polling
  useEffect(() => {
    if (!enablePolling) {
      return;
    }

    const intervalId = setInterval(() => {
      // Don't poll if currently loading
      if (!isLoading) {
        fetchStats();
      }
    }, pollInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [enablePolling, pollInterval, isLoading, fetchStats]);

  return {
    stats,
    isLoading,
    error,
    completionPercent,
    exportBlocked,
    blockingCount,
    refresh: fetchStats,
  };
}
