'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  WorkerInfo,
  JobsOverview,
  BottleneckStats,
  ErrorPatterns,
} from '@/lib/api/admin-pipeline';
import { adminPipelineApi } from '@/lib/api/admin-pipeline';

export interface WorkerDiagnosticsState {
  workerInfo: WorkerInfo | null;
  jobsOverview: JobsOverview | null;
  bottleneckStats: BottleneckStats | null;
  errorPatterns: ErrorPatterns | null;
  isLoading: boolean;
  error: Error | null;
  lastFetchedAt: string | null;
  refresh: () => Promise<void>;
}

const DEFAULT_POLL_INTERVAL = 10000; // 10 seconds

export function useWorkerDiagnostics(
  pollIntervalMs: number = DEFAULT_POLL_INTERVAL
): WorkerDiagnosticsState {
  const [workerInfo, setWorkerInfo] = useState<WorkerInfo | null>(null);
  const [jobsOverview, setJobsOverview] = useState<JobsOverview | null>(null);
  const [bottleneckStats, setBottleneckStats] = useState<BottleneckStats | null>(null);
  const [errorPatterns, setErrorPatterns] = useState<ErrorPatterns | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  const fetchInProgressRef = useRef(false);

  const fetchAll = useCallback(async () => {
    if (fetchInProgressRef.current) return;
    fetchInProgressRef.current = true;

    try {
      // Fetch all 4 endpoints in parallel
      const [worker, jobs, bottleneck, errors] = await Promise.all([
        adminPipelineApi.getWorkerInfo().catch(() => null),
        adminPipelineApi.getJobsOverview({ limit: 50 }).catch(() => null),
        adminPipelineApi.getBottleneckStats({ hours: 24 }).catch(() => null),
        adminPipelineApi.getErrorPatterns({ hours: 24, limit: 10 }).catch(() => null),
      ]);

      if (isMountedRef.current) {
        if (worker) setWorkerInfo(worker);
        if (jobs) setJobsOverview(jobs);
        if (bottleneck) setBottleneckStats(bottleneck);
        if (errors) setErrorPatterns(errors);
        setError(null);
        setLastFetchedAt(new Date().toISOString());
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error('Failed to fetch diagnostics'));
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
    fetchAll();

    let intervalId: NodeJS.Timeout | null = null;
    let visibilityDebounceId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(fetchAll, pollIntervalMs);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (visibilityDebounceId) clearTimeout(visibilityDebounceId);
      visibilityDebounceId = setTimeout(() => {
        if (document.visibilityState === 'visible') {
          fetchAll();
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
      if (visibilityDebounceId) clearTimeout(visibilityDebounceId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchAll, pollIntervalMs]);

  return {
    workerInfo,
    jobsOverview,
    bottleneckStats,
    errorPatterns,
    isLoading,
    error,
    lastFetchedAt,
    refresh: fetchAll,
  };
}
