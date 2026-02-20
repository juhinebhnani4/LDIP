'use client';

/**
 * Hook for A/B Testing status and data.
 *
 * Gap 10: Automated Voyage A/B Testing
 *
 * Polls A/B testing status every 30 seconds (slower polling since experiments
 * run for minutes, not seconds). Visibility-based polling: stops interval when
 * tab is hidden, restarts + fetches immediately when tab becomes visible.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ABTestStatus } from '@/lib/api/ab-testing';
import { getABTestStatus } from '@/lib/api/ab-testing';

const POLL_INTERVAL_MS = 30_000; // 30 seconds

export function useABTesting() {
  const [status, setStatus] = useState<ABTestStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const fetchingRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    if (fetchingRef.current || !mountedRef.current) return;
    fetchingRef.current = true;

    try {
      const data = await getABTestStatus();
      if (mountedRef.current) {
        setStatus(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch A/B status');
      }
    } finally {
      fetchingRef.current = false;
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const startPolling = useCallback(() => {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS);
  }, [fetchStatus]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchStatus();
    startPolling();

    // Stop polling when tab is hidden, restart + fetch when visible
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchStatus(); // Immediate fetch on return
        startPolling();
      } else {
        stopPolling();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      mountedRef.current = false;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchStatus, startPolling, stopPolling]);

  return { status, loading, error, refresh: fetchStatus };
}
