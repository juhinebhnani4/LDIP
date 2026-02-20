'use client';

/**
 * Hook for A/B Testing status and data.
 *
 * Gap 10: Automated Voyage A/B Testing
 *
 * Polls A/B testing status every 30 seconds (slower polling since experiments
 * run for minutes, not seconds). Visibility-based polling.
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

  const fetchStatus = useCallback(async () => {
    if (fetchingRef.current || !mountedRef.current) return;
    fetchingRef.current = true;

    try {
      const data = await getABTestStatus();
      if (mountedRef.current) {
        setStatus(data);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch A/B status');
        setLoading(false);
      }
    } finally {
      fetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchStatus();

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchStatus();
      }
    }, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchStatus]);

  return { status, loading, error, refresh: fetchStatus };
}
