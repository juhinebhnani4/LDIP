'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { UsageSummaryData } from '@/lib/api/usage';
import { usageApi } from '@/lib/api/usage';

export interface UsageSummaryState {
  data: UsageSummaryData | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

const POLL_INTERVAL = 120000; // 2 minutes (usage doesn't change as fast as costs)

export function useUsageSummary(): UsageSummaryState {
  const [data, setData] = useState<UsageSummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const isMountedRef = useRef(true);
  const fetchInProgressRef = useRef(false);

  const fetchData = useCallback(async () => {
    if (fetchInProgressRef.current) return;
    fetchInProgressRef.current = true;

    try {
      const result = await usageApi.getUsageSummary();
      if (isMountedRef.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error('Failed to load usage data'));
      }
    } finally {
      fetchInProgressRef.current = false;
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    setIsLoading(true);
    fetchData();

    let intervalId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(fetchData, POLL_INTERVAL);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchData();
        startPolling();
      } else {
        stopPolling();
      }
    };

    if (document.visibilityState === 'visible') {
      startPolling();
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchData]);

  return { data, isLoading, error, refresh: fetchData };
}
