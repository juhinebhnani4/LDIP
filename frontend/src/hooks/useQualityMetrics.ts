'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { QualityMetricsData, MatterQualityMetrics } from '@/lib/api/admin-monitoring';
import { adminMonitoringApi } from '@/lib/api/admin-monitoring';

/**
 * State returned by the useQualityMetrics hook.
 */
export interface QualityMetricsState {
  /** Full quality metrics data */
  metricsData: QualityMetricsData | null;
  /** Per-matter quality metrics */
  matters: MatterQualityMetrics[];
  /** Whether any matter has regression alerts */
  hasRegressions: boolean;
  /** Matters with active regressions */
  regressionMatters: MatterQualityMetrics[];
  /** Loading state for initial fetch */
  isLoading: boolean;
  /** Error from last fetch attempt */
  error: Error | null;
  /** Last successful update timestamp */
  lastUpdated: string | null;
  /** Manually trigger a refresh */
  refresh: () => Promise<void>;
}

const DEFAULT_POLL_INTERVAL = 300_000; // 5 minutes (evaluations are infrequent)

/**
 * Hook to fetch and poll RAG quality metrics.
 *
 * Gap 9: Automated RAGAS Regression — Quality Monitoring Dashboard
 *
 * Features:
 * - Fetches /api/admin/quality-metrics on mount
 * - Polls every 5 minutes (evaluation data changes slowly)
 * - Only polls when document is visible
 * - Returns regression alerts for UI display
 * - Supports manual refresh
 *
 * @param pollIntervalMs - Polling interval in milliseconds (default: 300000)
 */
export function useQualityMetrics(pollIntervalMs: number = DEFAULT_POLL_INTERVAL): QualityMetricsState {
  const [metricsData, setMetricsData] = useState<QualityMetricsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const isMountedRef = useRef(true);
  const fetchInProgressRef = useRef(false);

  const fetchMetrics = useCallback(async () => {
    if (fetchInProgressRef.current) return;

    fetchInProgressRef.current = true;

    try {
      const data = await adminMonitoringApi.getQualityMetrics();

      if (isMountedRef.current) {
        setMetricsData(data);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error('Unknown error fetching quality metrics'));
      }
    } finally {
      fetchInProgressRef.current = false;
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  // Set up polling with visibility handling
  useEffect(() => {
    isMountedRef.current = true;

    fetchMetrics();

    let intervalId: NodeJS.Timeout | null = null;
    let visibilityDebounceId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(fetchMetrics, pollIntervalMs);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (visibilityDebounceId) {
        clearTimeout(visibilityDebounceId);
      }

      visibilityDebounceId = setTimeout(() => {
        if (document.visibilityState === 'visible') {
          fetchMetrics();
          startPolling();
        } else {
          stopPolling();
        }
      }, 100);
    };

    if (document.visibilityState === 'visible') {
      startPolling();
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      stopPolling();
      if (visibilityDebounceId) {
        clearTimeout(visibilityDebounceId);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchMetrics, pollIntervalMs]);

  // Derived state — memoized to avoid creating new array references on every render
  const matters = useMemo(() => metricsData?.matters ?? [], [metricsData]);
  const regressionMatters = useMemo(() => matters.filter((m) => m.hasRegression), [matters]);
  const hasRegressions = metricsData?.hasRegressions ?? false;
  const lastUpdated = metricsData?.lastUpdated ?? null;

  return {
    metricsData,
    matters,
    hasRegressions,
    regressionMatters,
    isLoading,
    error,
    lastUpdated,
    refresh: fetchMetrics,
  };
}
