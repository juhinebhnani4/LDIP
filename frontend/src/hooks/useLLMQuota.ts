'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import type { LLMQuotaData, ProviderQuota } from '@/lib/api/admin-quota';
import { adminQuotaApi } from '@/lib/api/admin-quota';

/**
 * State returned by the useLLMQuota hook.
 */
export interface LLMQuotaState {
  /** Quota data for all providers */
  quotaData: LLMQuotaData | null;
  /** Individual provider quotas for convenience */
  providers: ProviderQuota[];
  /** Whether any provider has an alert triggered */
  hasAlerts: boolean;
  /** Provider names with triggered alerts */
  alertProviders: string[];
  /** Loading state for initial fetch */
  isLoading: boolean;
  /** Error from last fetch attempt */
  error: Error | null;
  /** Last successful update timestamp */
  lastUpdated: string | null;
  /** Manually trigger a refresh */
  refresh: () => Promise<void>;
}

const DEFAULT_POLL_INTERVAL = 60000; // 60 seconds

/**
 * Hook to poll LLM quota status.
 *
 * Story gap-5.2: LLM Quota Monitoring Dashboard (AC #5)
 *
 * Features:
 * - Polls /api/admin/llm-quota every 60 seconds by default
 * - Only polls when document is visible (saves resources)
 * - Returns alert status for UI display
 * - Supports manual refresh
 *
 * @param pollIntervalMs - Polling interval in milliseconds (default: 60000)
 */
export function useLLMQuota(pollIntervalMs: number = DEFAULT_POLL_INTERVAL): LLMQuotaState {
  const [quotaData, setQuotaData] = useState<LLMQuotaData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef(true);

  // F6 fix: Track in-flight requests to prevent race conditions
  const fetchInProgressRef = useRef(false);

  const fetchQuota = useCallback(async () => {
    // F6 fix: Skip if fetch already in progress (prevents stacked requests)
    if (fetchInProgressRef.current) {
      return;
    }

    fetchInProgressRef.current = true;

    try {
      const data = await adminQuotaApi.getLLMQuota();

      if (isMountedRef.current) {
        setQuotaData(data);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error('Unknown error fetching quota'));
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
    fetchQuota();

    // Only poll when document is visible
    let intervalId: NodeJS.Timeout | null = null;

    // F6 fix: Debounce timeout for visibility change
    let visibilityDebounceId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(fetchQuota, pollIntervalMs);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      // F6 fix: Debounce visibility changes to prevent rapid tab switch issues
      if (visibilityDebounceId) {
        clearTimeout(visibilityDebounceId);
      }

      visibilityDebounceId = setTimeout(() => {
        if (document.visibilityState === 'visible') {
          // Fetch immediately when becoming visible, then resume polling
          fetchQuota();
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
  }, [fetchQuota, pollIntervalMs]);

  // Calculate derived state
  const providers = quotaData?.providers ?? [];
  const alertProviders = providers.filter((p) => p.alertTriggered).map((p) => p.provider);
  const hasAlerts = alertProviders.length > 0;
  const lastUpdated = quotaData?.lastUpdated ?? null;

  return {
    quotaData,
    providers,
    hasAlerts,
    alertProviders,
    isLoading,
    error,
    lastUpdated,
    refresh: fetchQuota,
  };
}
