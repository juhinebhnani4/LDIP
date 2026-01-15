/**
 * useProcessingStatus Hook
 *
 * Polls backend job APIs to track processing progress for a matter.
 * Returns real-time status, progress percentage, current stage, and completion state.
 *
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 *
 * Backend APIs used:
 * - GET /api/jobs/matters/{matter_id} - List all jobs for matter
 * - GET /api/jobs/matters/{matter_id}/stats - Queue statistics
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api, ApiError } from '@/lib/api/client';
import {
  mapBackendStageToUI,
  determineOverallStage,
  isTerminalStatus,
  isActiveStatus,
} from '@/lib/utils/stage-mapping';
import type { ProcessingStage } from '@/types/upload';

// =============================================================================
// Types
// =============================================================================

/** Job status from backend */
export type JobStatus = 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'SKIPPED';

/** Single processing job from backend */
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

/** Job list response from GET /api/jobs/matters/{matter_id} */
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

/** Queue statistics from GET /api/jobs/matters/{matter_id}/stats */
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

/** Hook return value */
export interface ProcessingStatusResult {
  /** List of processing jobs */
  jobs: ProcessingJob[];
  /** Queue statistics */
  stats: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
    total: number;
  };
  /** Overall progress percentage (0-100) */
  overallProgress: number;
  /** Current processing stage for UI display */
  currentStage: ProcessingStage;
  /** Whether all jobs have completed (success or failure) */
  isComplete: boolean;
  /** Whether there are any failed jobs */
  hasFailed: boolean;
  /** Error from API calls */
  error: Error | null;
  /** Whether currently fetching */
  isLoading: boolean;
  /** Force a refresh of the data */
  refresh: () => Promise<void>;
}

/** Hook options */
export interface UseProcessingStatusOptions {
  /** Polling interval in ms (default: 1000ms during processing, 2000ms when idle) */
  pollingInterval?: number;
  /** Whether to enable polling (default: true) */
  enabled?: boolean;
  /** Stop polling when complete (default: true) */
  stopOnComplete?: boolean;
}

// =============================================================================
// Constants
// =============================================================================

/** Default polling interval during active processing (ms) */
const DEFAULT_POLLING_INTERVAL = 1000;

/** Slower polling when matter is mostly complete (ms) */
const SLOW_POLLING_INTERVAL = 2000;

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Convert snake_case job to camelCase
 */
function normalizeJob(job: JobListResponse['jobs'][0]): ProcessingJob {
  return {
    id: job.id,
    matterId: job.matter_id,
    documentId: job.document_id,
    status: job.status.toUpperCase() as JobStatus,
    jobType: job.job_type,
    currentStage: job.current_stage,
    progressPct: job.progress_pct,
    errorMessage: job.error_message,
    createdAt: job.created_at,
    startedAt: job.started_at,
    completedAt: job.completed_at,
  };
}

/**
 * Calculate overall progress from job completion counts
 */
function calculateOverallProgress(stats: {
  queued: number;
  processing: number;
  completed: number;
  failed: number;
}): number {
  const total = stats.queued + stats.processing + stats.completed + stats.failed;
  if (total === 0) return 0;

  // Terminal states (completed + failed) count as 100% done
  const done = stats.completed + stats.failed;
  return Math.round((done / total) * 100);
}

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook to poll processing status for a matter.
 *
 * @param matterId - Matter ID to track, null to disable
 * @param options - Polling configuration options
 * @returns Processing status, progress, and completion state
 *
 * @example
 * const { overallProgress, currentStage, isComplete, error } = useProcessingStatus(matterId);
 *
 * // In effect to detect completion
 * useEffect(() => {
 *   if (isComplete) {
 *     showCompletionScreen();
 *   }
 * }, [isComplete]);
 */
export function useProcessingStatus(
  matterId: string | null,
  options: UseProcessingStatusOptions = {}
): ProcessingStatusResult {
  const {
    pollingInterval = DEFAULT_POLLING_INTERVAL,
    enabled = true,
    stopOnComplete = true,
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

  // Refs for cleanup and preventing stale closures
  const isMountedRef = useRef(true);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isCompleteRef = useRef(false);

  /**
   * Fetch jobs and stats from backend
   */
  const fetchStatus = useCallback(async () => {
    if (!matterId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Fetch jobs and stats in parallel
      const [jobsResponse, statsResponse] = await Promise.all([
        api.get<JobListResponse>(`/api/jobs/matters/${matterId}?limit=200`),
        api.get<JobQueueStats>(`/api/jobs/matters/${matterId}/stats`),
      ]);

      if (!isMountedRef.current) return;

      // Normalize jobs
      const normalizedJobs = jobsResponse.jobs.map(normalizeJob);
      setJobs(normalizedJobs);

      // Update stats
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

      // Calculate overall progress
      const progress = calculateOverallProgress(newStats);
      setOverallProgress(progress);

      // Determine current stage from active jobs
      const activeJobs = normalizedJobs.filter((j) => isActiveStatus(j.status));
      const jobStages = activeJobs.map((j) => j.currentStage);

      if (jobStages.length > 0) {
        setCurrentStage(determineOverallStage(jobStages));
      } else if (progress >= 100) {
        // All done, show INDEXING (final stage)
        setCurrentStage('INDEXING');
      }

      // Check completion: no QUEUED or PROCESSING jobs
      const allDone =
        newStats.queued === 0 && newStats.processing === 0 && newStats.total > 0;
      setIsComplete(allDone);
      isCompleteRef.current = allDone;

      // Check for failures
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
   * Manual refresh function
   */
  const refresh = useCallback(async () => {
    await fetchStatus();
  }, [fetchStatus]);

  // Set up polling
  useEffect(() => {
    isMountedRef.current = true;
    isCompleteRef.current = false;

    // Don't poll if disabled or no matterId
    if (!enabled || !matterId) {
      return;
    }

    // Initial fetch
    void fetchStatus();

    // Set up polling interval
    const poll = () => {
      // Stop polling if complete and stopOnComplete is true
      if (stopOnComplete && isCompleteRef.current) {
        return;
      }

      pollingRef.current = setTimeout(async () => {
        if (!isMountedRef.current) return;

        await fetchStatus();

        // Continue polling if not complete or stopOnComplete is false
        if (!stopOnComplete || !isCompleteRef.current) {
          poll();
        }
      }, pollingInterval);
    };

    poll();

    // Cleanup
    return () => {
      isMountedRef.current = false;
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [matterId, enabled, pollingInterval, stopOnComplete, fetchStatus]);

  return {
    jobs,
    stats,
    overallProgress,
    currentStage,
    isComplete,
    hasFailed,
    error,
    isLoading,
    refresh,
  };
}

export default useProcessingStatus;
