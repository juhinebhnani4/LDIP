'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { UsageDashboardData } from '@/lib/api/admin-usage';
import { adminUsageApi } from '@/lib/api/admin-usage';

export interface UsageDashboardState {
  data: UsageDashboardData | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

const POLL_INTERVAL = 60000; // 60 seconds

export function useUsageDashboard(
  year: number,
  month: number,
): UsageDashboardState {
  const [data, setData] = useState<UsageDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const isMountedRef = useRef(true);
  const fetchInProgressRef = useRef(false);

  const fetchData = useCallback(async () => {
    if (fetchInProgressRef.current) return;
    fetchInProgressRef.current = true;

    try {
      const result = await adminUsageApi.getUsageDashboard(year, month);
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
  }, [year, month]);

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
