/**
 * useDocumentStatus Hook
 *
 * WebSocket-based document processing status hook.
 * Replaces polling with real-time push notifications from the server.
 * Falls back to polling if WebSocket is disconnected.
 *
 * Features:
 * - Real-time status updates via WebSocket
 * - Automatic fallback to polling when WS disconnected
 * - Same API as useProcessingStatus for easy migration
 * - Initial data fetch via REST API
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api, ApiError } from '@/lib/api/client';
import { useWebSocket } from './useWebSocket';
import type {
  WSJobProgress,
  WSDocumentStatus,
  WSMessage,
} from '@/lib/ws/client';
import {
  determineOverallStage,
  isActiveStatus,
} from '@/lib/utils/stage-mapping';
import type { ProcessingStage } from '@/types/upload';

// =============================================================================
// Types (same as useProcessingStatus for compatibility)
// =============================================================================

export type JobStatus = 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'SKIPPED';

export interface ProcessingJob {
  id: string;
  matterId: string;
  documentId: string | null;
  status: JobStatus;
  jobType: string;
  currentStage: string | null;
  progressPct: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

interface JobListResponse {
  jobs: Array<{
    id: string;
    matter_id: string;
    document_id: string | null;
    status: string;
    job_type: string;
    current_stage: string | null;
    progress_pct: number;
    error_message: string | null;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
  }>;
  total: number;
  limit: number;
  offset: number;
}

interface JobQueueStats {
  matter_id: string;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  cancelled: number;
  skipped: number;
  avg_processing_time_ms: number | null;
}

export interface DocumentStatusResult {
  jobs: ProcessingJob[];
  stats: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
    total: number;
  };
  overallProgress: number;
  currentStage: ProcessingStage;
  isComplete: boolean;
  hasFailed: boolean;
  error: Error | null;
  isLoading: boolean;
  /** Whether using WebSocket (true) or polling fallback (false) */
  isRealTime: boolean;
  refresh: () => Promise<void>;
}

export interface UseDocumentStatusOptions {
  /** Polling interval for fallback (default: 2000ms) */
  pollingInterval?: number;
  /** Whether hook is enabled (default: true) */
  enabled?: boolean;
  /** Stop updates when complete (default: true) */
  stopOnComplete?: boolean;
  /** Prefer WebSocket over polling (default: true) */
  preferWebSocket?: boolean;
}

// =============================================================================
// Constants
// =============================================================================

// Increased from 2000ms to reduce Supabase egress - WebSocket is primary
const DEFAULT_POLLING_INTERVAL = 5000;

// =============================================================================
// Helper Functions
// =============================================================================

function normalizeJob(job: JobListResponse['jobs'][0]): ProcessingJob {
  const j = job as unknown as Record<string, unknown>;
  return {
    id: job.id,
    matterId: ((j.matterId ?? j.matter_id) as string),
    documentId: ((j.documentId ?? j.document_id) as string | null),
    status: (job.status ?? '').toUpperCase() as JobStatus,
    jobType: ((j.jobType ?? j.job_type) as string),
    currentStage: ((j.currentStage ?? j.current_stage) as string | null),
    progressPct: ((j.progressPct ?? j.progress_pct) as number),
    errorMessage: ((j.errorMessage ?? j.error_message) as string | null),
    createdAt: ((j.createdAt ?? j.created_at) as string),
    startedAt: ((j.startedAt ?? j.started_at) as string | null),
    completedAt: ((j.completedAt ?? j.completed_at) as string | null),
  };
}

function calculateOverallProgress(
  stats: { queued: number; processing: number; completed: number; failed: number },
  jobs: ProcessingJob[] = []
): number {
  const total = stats.queued + stats.processing + stats.completed + stats.failed;
  if (total === 0) return 0;

  const terminalProgress = (stats.completed + stats.failed) * 100;
  const processingJobs = jobs.filter((j) => j.status === 'PROCESSING');
  const processingProgress = processingJobs.reduce(
    (sum, job) => sum + (job.progressPct || 0),
    0
  );

  const totalPossible = total * 100;
  const actualProgress = terminalProgress + processingProgress;

  return Math.round((actualProgress / totalPossible) * 100);
}

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook for real-time document processing status.
 *
 * Uses WebSocket for instant updates, with automatic fallback to polling
 * if WebSocket is unavailable.
 *
 * @param matterId - Matter ID to track, null to disable
 * @param options - Configuration options
 * @returns Document status, progress, and completion state
 *
 * @example
 * // Same API as useProcessingStatus
 * const { overallProgress, currentStage, isComplete, isRealTime } = useDocumentStatus(matterId);
 *
 * // isRealTime tells you if updates are via WebSocket (true) or polling (false)
 */
export function useDocumentStatus(
  matterId: string | null,
  options: UseDocumentStatusOptions = {}
): DocumentStatusResult {
  const {
    pollingInterval = DEFAULT_POLLING_INTERVAL,
    enabled = true,
    stopOnComplete = true,
    preferWebSocket = true,
  } = options;

  // State
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [stats, setStats] = useState({
    queued: 0,
    processing: 0,
    completed: 0,
    failed: 0,
    total: 0,
  });
  const [overallProgress, setOverallProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState<ProcessingStage>('UPLOADING');
  const [isComplete, setIsComplete] = useState(false);
  const [hasFailed, setHasFailed] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Refs
  const isMountedRef = useRef(true);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isCompleteRef = useRef(false);

  // WebSocket connection
  const { isConnected, subscribe } = useWebSocket(
    preferWebSocket ? matterId : null,
    { enabled: enabled && preferWebSocket }
  );

  // Track if we're using real-time updates
  const isRealTime = preferWebSocket && isConnected;

  /**
   * Fetch initial data from REST API
   */
  const fetchStatus = useCallback(async () => {
    if (!matterId) return;

    setIsLoading(true);
    setError(null);

    try {
      const [jobsResponse, statsResponse] = await Promise.all([
        api.get<JobListResponse>(`/api/jobs/matters/${matterId}?limit=200`),
        api.get<JobQueueStats>(`/api/jobs/matters/${matterId}/stats`),
      ]);

      if (!isMountedRef.current) return;

      const normalizedJobs = jobsResponse.jobs.map(normalizeJob);
      setJobs(normalizedJobs);

      const newStats = {
        queued: statsResponse.queued,
        processing: statsResponse.processing,
        completed: statsResponse.completed,
        failed: statsResponse.failed,
        total:
          statsResponse.queued +
          statsResponse.processing +
          statsResponse.completed +
          statsResponse.failed,
      };
      setStats(newStats);

      const progress = calculateOverallProgress(newStats, normalizedJobs);
      setOverallProgress(progress);

      const activeJobs = normalizedJobs.filter((j) => isActiveStatus(j.status));
      const jobStages = activeJobs.map((j) => j.currentStage);

      if (jobStages.length > 0) {
        setCurrentStage(determineOverallStage(jobStages));
      } else if (progress >= 100) {
        setCurrentStage('INDEXING');
      }

      const allDone =
        newStats.queued === 0 && newStats.processing === 0 && newStats.total > 0;
      setIsComplete(allDone);
      isCompleteRef.current = allDone;
      setHasFailed(newStats.failed > 0);

    } catch (err) {
      if (!isMountedRef.current) return;

      if (err instanceof ApiError) {
        setError(new Error(err.message));
      } else if (err instanceof Error) {
        setError(err);
      } else {
        setError(new Error('Failed to fetch processing status'));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [matterId]);

  /**
   * Handle WebSocket job progress message
   */
  const handleJobProgress = useCallback((msg: WSMessage<WSJobProgress>) => {
    if (!msg.data) return;

    const data = msg.data;

    setJobs((prevJobs) => {
      const jobIndex = prevJobs.findIndex((j) => j.id === data.job_id);

      if (jobIndex >= 0) {
        // Update existing job
        const existingJob = prevJobs[jobIndex];
        if (!existingJob) return prevJobs;

        const updatedJobs = [...prevJobs];
        updatedJobs[jobIndex] = {
          ...existingJob,
          status: data.status.toUpperCase() as JobStatus,
          currentStage: data.stage ?? existingJob.currentStage,
          progressPct: data.progress_pct,
        };
        return updatedJobs;
      }

      return prevJobs;
    });

    // Update stats based on status change
    setStats((prevStats) => {
      // We'll need to recalculate on next full fetch
      // For now, just track the state change
      return prevStats;
    });

    // Update stage if provided
    if (data.stage) {
      setCurrentStage(determineOverallStage([data.stage]));
    }
  }, []);

  /**
   * Handle WebSocket document status message
   */
  const handleDocumentStatus = useCallback((msg: WSMessage<WSDocumentStatus>) => {
    if (!msg.data) return;

    const data = msg.data;

    // Update job status for this document
    setJobs((prevJobs) => {
      const docJobs = prevJobs.filter((j) => j.documentId === data.document_id);
      if (docJobs.length === 0) return prevJobs;

      return prevJobs.map((job) => {
        if (job.documentId === data.document_id) {
          return {
            ...job,
            status: data.status.toUpperCase() as JobStatus,
            currentStage: data.processing_stage ?? job.currentStage,
            errorMessage: data.error_message ?? job.errorMessage,
          };
        }
        return job;
      });
    });

    // Check for completion/failure
    if (data.status === 'COMPLETED' || data.status === 'FAILED') {
      // Refresh stats to get accurate counts
      void fetchStatus();
    }
  }, [fetchStatus]);

  /**
   * Subscribe to WebSocket messages
   */
  useEffect(() => {
    if (!isConnected || !enabled) return;

    const unsubJobProgress = subscribe<WSJobProgress>('job_progress', handleJobProgress);
    const unsubDocStatus = subscribe<WSDocumentStatus>('document_status', handleDocumentStatus);

    return () => {
      unsubJobProgress();
      unsubDocStatus();
    };
  }, [isConnected, enabled, subscribe, handleJobProgress, handleDocumentStatus]);

  /**
   * Initial fetch and polling fallback
   */
  useEffect(() => {
    isMountedRef.current = true;
    isCompleteRef.current = false;

    if (!enabled || !matterId) return;

    // Always do initial fetch
    void fetchStatus();

    // Only poll if WebSocket is not connected
    if (!isRealTime) {
      const poll = () => {
        if (stopOnComplete && isCompleteRef.current) return;

        pollingRef.current = setTimeout(async () => {
          if (!isMountedRef.current) return;

          await fetchStatus();

          if (!stopOnComplete || !isCompleteRef.current) {
            poll();
          }
        }, pollingInterval);
      };

      poll();
    }

    return () => {
      isMountedRef.current = false;
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [matterId, enabled, pollingInterval, stopOnComplete, isRealTime, fetchStatus]);

  /**
   * Recalculate progress when jobs change
   */
  useEffect(() => {
    const progress = calculateOverallProgress(stats, jobs);
    setOverallProgress(progress);
  }, [jobs, stats]);

  /**
   * Manual refresh
   */
  const refresh = useCallback(async () => {
    await fetchStatus();
  }, [fetchStatus]);

  return {
    jobs,
    stats,
    overallProgress,
    currentStage,
    isComplete,
    hasFailed,
    error,
    isLoading,
    isRealTime,
    refresh,
  };
}

export default useDocumentStatus;
