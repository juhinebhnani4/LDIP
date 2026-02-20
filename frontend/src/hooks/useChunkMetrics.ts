'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import type { ChunkMetricsData, MatterChunkMetrics } from '@/lib/api/admin-monitoring';
import { adminMonitoringApi } from '@/lib/api/admin-monitoring';

/**
 * State returned by the useChunkMetrics hook.
 */
export interface ChunkMetricsState {
  /** Full chunk metrics data */
  metricsData: ChunkMetricsData | null;
  /** Per-matter metrics for convenience */
  matters: MatterChunkMetrics[];
  /** Global chunk count */
  globalTotal: number;
  /** Whether any alert threshold is exceeded */
  hasAlerts: boolean;
  /** Matters that exceed per-matter threshold */
  alertMatters: MatterChunkMetrics[];
  /** Loading state for initial fetch */
  isLoading: boolean;
  /** Error from last fetch attempt */
  error: Error | null;
  /** Last successful update timestamp */
  lastUpdated: string | null;
  /** Manually trigger a refresh */
  refresh: () => Promise<void>;
}

const DEFAULT_POLL_INTERVAL = 120_000; // 2 minutes (chunk counts change slowly)

/**
 * Hook to fetch and poll chunk count metrics.
 *
 * Gap 7: Vector Quantization — Monitoring Dashboard
 *
 * Features:
 * - Fetches /api/admin/chunk-metrics on mount
 * - Polls every 2 minutes by default (chunk counts change slowly)
 * - Only polls when document is visible
 * - Returns alert status for UI display
 * - Supports manual refresh
 *
 * @param pollIntervalMs - Polling interval in milliseconds (default: 120000)
 */
export function useChunkMetrics(pollIntervalMs: number = DEFAULT_POLL_INTERVAL): ChunkMetricsState {
  const [metricsData, setMetricsData] = useState<ChunkMetricsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const isMountedRef = useRef(true);
  const fetchInProgressRef = useRef(false);

  const fetchMetrics = useCallback(async () => {
    if (fetchInProgressRef.current) return;

    fetchInProgressRef.current = true;

    try {
      const data = await adminMonitoringApi.getChunkMetrics();

      if (isMountedRef.current) {
        setMetricsData(data);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error('Unknown error fetching chunk metrics'));
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

  // Calculate derived state
  const matters = metricsData?.matters ?? [];
  const globalTotal = metricsData?.global.totalChunks ?? 0;
  const alertMatters = matters.filter((m) => m.exceedsThreshold);
  const hasAlerts = metricsData?.alertsTriggered ?? false;
  const lastUpdated = metricsData?.lastUpdated ?? null;

  return {
    metricsData,
    matters,
    globalTotal,
    hasAlerts,
    alertMatters,
    isLoading,
    error,
    lastUpdated,
    refresh: fetchMetrics,
  };
}
