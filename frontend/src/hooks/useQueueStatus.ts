'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import type { QueueMetrics, QueueStatusData } from '@/lib/api/admin-queue';
import { adminQueueApi } from '@/lib/api/admin-queue';

/**
 * State returned by the useQueueStatus hook.
 */
export interface QueueStatusState {
  /** Queue status data for all queues */
  statusData: QueueStatusData | null;
  /** Individual queue metrics for convenience */
  queues: QueueMetrics[];
  /** Total pending jobs across all queues */
  totalPending: number;
  /** Total active jobs across all queues */
  totalActive: number;
  /** Number of active workers */
  activeWorkers: number;
  /** Whether any queue has an alert triggered */
  hasAlerts: boolean;
  /** Queue names with triggered alerts */
  alertQueues: string[];
  /** Whether the system is healthy */
  isHealthy: boolean;
  /** Loading state for initial fetch */
  isLoading: boolean;
  /** Error from last fetch attempt */
  error: Error | null;
  /** Last successful update timestamp */
  lastCheckedAt: string | null;
  /** Whether data might be stale (older than 60 seconds) */
  isStale: boolean;
  /** Manually trigger a refresh */
  refresh: () => Promise<void>;
}

const DEFAULT_POLL_INTERVAL = 30000; // 30 seconds (more frequent than LLM quota)
const STALENESS_THRESHOLD_MS = 60000; // 60 seconds

/**
 * Hook to poll queue status.
 *
 * Story 5.6: Queue Depth Visibility Dashboard
 *
 * Features:
 * - Polls /api/admin/queue-status every 30 seconds by default
 * - Only polls when document is visible (saves resources)
 * - Returns alert status for UI display
 * - Detects stale data (>60 seconds old)
 * - Supports manual refresh
 *
 * @param pollIntervalMs - Polling interval in milliseconds (default: 30000)
 */
export function useQueueStatus(pollIntervalMs: number = DEFAULT_POLL_INTERVAL): QueueStatusState {
  const [statusData, setStatusData] = useState<QueueStatusData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef(true);

  // Track in-flight requests to prevent race conditions
  const fetchInProgressRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    // Skip if fetch already in progress (prevents stacked requests)
    if (fetchInProgressRef.current) {
      return;
    }

    fetchInProgressRef.current = true;

    try {
      const data = await adminQueueApi.getQueueStatus();

      if (isMountedRef.current) {
        setStatusData(data);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error('Unknown error fetching queue status'));
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

    // Initial fetch
    fetchStatus();

    // Only poll when document is visible
    let intervalId: NodeJS.Timeout | null = null;

    // Debounce timeout for visibility change
    let visibilityDebounceId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(fetchStatus, pollIntervalMs);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      // Debounce visibility changes to prevent rapid tab switch issues
      if (visibilityDebounceId) {
        clearTimeout(visibilityDebounceId);
      }

      visibilityDebounceId = setTimeout(() => {
        if (document.visibilityState === 'visible') {
          // Fetch immediately when becoming visible, then resume polling
          fetchStatus();
          startPolling();
        } else {
          stopPolling();
        }
      }, 100); // 100ms debounce
    };

    // Start polling if document is visible
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
  }, [fetchStatus, pollIntervalMs]);

  // Calculate derived state
  const queues = statusData?.queues ?? [];
  const totalPending = statusData?.totalPending ?? 0;
  const totalActive = statusData?.totalActive ?? 0;
  const activeWorkers = statusData?.activeWorkers ?? 0;
  const alertQueues = queues.filter((q) => q.alertTriggered).map((q) => q.queueName);
  const hasAlerts = alertQueues.length > 0;
  const isHealthy = statusData?.isHealthy ?? true;
  const lastCheckedAt = statusData?.lastCheckedAt ?? null;

  // Check staleness
  const isStale = (() => {
    if (!lastCheckedAt) return false;
    try {
      const lastCheck = new Date(lastCheckedAt).getTime();
      const now = Date.now();
      return now - lastCheck > STALENESS_THRESHOLD_MS;
    } catch {
      return false;
    }
  })();

  return {
    statusData,
    queues,
    totalPending,
    totalActive,
    activeWorkers,
    hasAlerts,
    alertQueues,
    isHealthy,
    isLoading,
    error,
    lastCheckedAt,
    isStale,
    refresh: fetchStatus,
  };
}
