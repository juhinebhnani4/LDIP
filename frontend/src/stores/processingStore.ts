/**
 * Processing Store
 *
 * Zustand store for managing document processing status.
 * Story 2c-3: Background Job Status Tracking and Retry
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const jobs = useProcessingStore((state) => state.jobs);
 *   const stats = useProcessingStore((state) => state.stats);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { jobs, stats } = useProcessingStore();
 */

import { create } from 'zustand';
import type {
  JobQueueStats,
  JobStatus,
  ProcessingJob,
  JobProgressEvent,
  JobStatusChangeEvent,
} from '@/types/job';

// =============================================================================
// Store Types
// =============================================================================

interface ProcessingState {
  /** Jobs indexed by job_id */
  jobs: Map<string, ProcessingJob>;

  /** Jobs indexed by document_id for quick lookup */
  jobsByDocument: Map<string, string>;

  /** Queue statistics for current matter */
  stats: JobQueueStats | null;

  /** Current matter ID being tracked */
  matterId: string | null;

  /** Whether the store is loading data */
  isLoading: boolean;

  /** Last update timestamp */
  lastUpdate: number;
}

interface ProcessingActions {
  /** Set the current matter ID and reset state */
  setMatterId: (matterId: string | null) => void;

  /** Set jobs list from API response */
  setJobs: (jobs: ProcessingJob[]) => void;

  /** Update a single job */
  updateJob: (job: ProcessingJob) => void;

  /** Update job from progress event (real-time) */
  handleProgressEvent: (event: JobProgressEvent) => void;

  /** Update job from status change event (real-time) */
  handleStatusChangeEvent: (event: JobStatusChangeEvent) => void;

  /** Set queue statistics */
  setStats: (stats: JobQueueStats) => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Get job for a document */
  getJobForDocument: (documentId: string) => ProcessingJob | null;

  /** Get all active jobs (QUEUED or PROCESSING) */
  getActiveJobs: () => ProcessingJob[];

  /** Get all failed jobs */
  getFailedJobs: () => ProcessingJob[];

  /** Clear all state */
  clear: () => void;
}

type ProcessingStore = ProcessingState & ProcessingActions;

// =============================================================================
// Initial State
// =============================================================================

const initialState: ProcessingState = {
  jobs: new Map(),
  jobsByDocument: new Map(),
  stats: null,
  matterId: null,
  isLoading: false,
  lastUpdate: 0,
};

// =============================================================================
// Store Implementation
// =============================================================================

export const useProcessingStore = create<ProcessingStore>()((set, get) => ({
  // Initial state
  ...initialState,

  // Actions
  setMatterId: (matterId: string | null) => {
    set({
      matterId,
      jobs: new Map(),
      jobsByDocument: new Map(),
      stats: null,
      lastUpdate: 0,
    });
  },

  setJobs: (jobs: ProcessingJob[]) => {
    const jobsMap = new Map<string, ProcessingJob>();
    const jobsByDocument = new Map<string, string>();

    for (const job of jobs) {
      jobsMap.set(job.id, job);
      if (job.document_id) {
        // Only track active jobs for document lookup
        const existingJobId = jobsByDocument.get(job.document_id);
        if (!existingJobId || isMoreRecentJob(job, jobsMap.get(existingJobId))) {
          jobsByDocument.set(job.document_id, job.id);
        }
      }
    }

    set({
      jobs: jobsMap,
      jobsByDocument,
      lastUpdate: Date.now(),
      isLoading: false,
    });
  },

  updateJob: (job: ProcessingJob) => {
    set((state) => {
      const newJobs = new Map(state.jobs);
      newJobs.set(job.id, job);

      const newJobsByDocument = new Map(state.jobsByDocument);
      if (job.document_id) {
        newJobsByDocument.set(job.document_id, job.id);
      }

      return {
        jobs: newJobs,
        jobsByDocument: newJobsByDocument,
        lastUpdate: Date.now(),
      };
    });
  },

  handleProgressEvent: (event: JobProgressEvent) => {
    set((state) => {
      const job = state.jobs.get(event.job_id);
      if (!job) return state;

      const updatedJob: ProcessingJob = {
        ...job,
        current_stage: event.stage,
        progress_pct: event.progress_pct,
        estimated_completion: event.estimated_completion ?? job.estimated_completion,
        status: 'PROCESSING' as JobStatus,
        updated_at: new Date().toISOString(),
      };

      const newJobs = new Map(state.jobs);
      newJobs.set(event.job_id, updatedJob);

      return {
        jobs: newJobs,
        lastUpdate: Date.now(),
      };
    });
  },

  handleStatusChangeEvent: (event: JobStatusChangeEvent) => {
    set((state) => {
      const job = state.jobs.get(event.job_id);
      if (!job) return state;

      const updatedJob: ProcessingJob = {
        ...job,
        status: event.new_status,
        updated_at: new Date().toISOString(),
        // Clear progress on terminal states
        progress_pct: ['COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED'].includes(event.new_status)
          ? (event.new_status === 'COMPLETED' ? 100 : job.progress_pct)
          : job.progress_pct,
      };

      const newJobs = new Map(state.jobs);
      newJobs.set(event.job_id, updatedJob);

      // Update stats if available
      let newStats = state.stats;
      if (newStats) {
        newStats = updateStatsForStatusChange(newStats, event.old_status, event.new_status);
      }

      return {
        jobs: newJobs,
        stats: newStats,
        lastUpdate: Date.now(),
      };
    });
  },

  setStats: (stats: JobQueueStats) => {
    set({ stats, lastUpdate: Date.now() });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  getJobForDocument: (documentId: string) => {
    const { jobs, jobsByDocument } = get();
    const jobId = jobsByDocument.get(documentId);
    if (!jobId) return null;
    return jobs.get(jobId) ?? null;
  },

  getActiveJobs: () => {
    const { jobs } = get();
    return Array.from(jobs.values()).filter(
      (job) => job.status === 'QUEUED' || job.status === 'PROCESSING'
    );
  },

  getFailedJobs: () => {
    const { jobs } = get();
    return Array.from(jobs.values()).filter((job) => job.status === 'FAILED');
  },

  clear: () => {
    set(initialState);
  },
}));

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Check if job1 is more recent than job2.
 */
function isMoreRecentJob(
  job1: ProcessingJob,
  job2: ProcessingJob | undefined
): boolean {
  if (!job2) return true;

  // Prefer active jobs
  const job1Active = job1.status === 'QUEUED' || job1.status === 'PROCESSING';
  const job2Active = job2.status === 'QUEUED' || job2.status === 'PROCESSING';

  if (job1Active && !job2Active) return true;
  if (!job1Active && job2Active) return false;

  // Compare timestamps
  return new Date(job1.created_at) > new Date(job2.created_at);
}

/**
 * Update stats when job status changes.
 */
function updateStatsForStatusChange(
  stats: JobQueueStats,
  oldStatus: JobStatus,
  newStatus: JobStatus
): JobQueueStats {
  const newStats = { ...stats };

  // Decrement old status count
  const oldKey = oldStatus.toLowerCase() as keyof Pick<
    JobQueueStats,
    'queued' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'skipped'
  >;
  if (oldKey in newStats && typeof newStats[oldKey] === 'number') {
    (newStats[oldKey] as number) = Math.max(0, (newStats[oldKey] as number) - 1);
  }

  // Increment new status count
  const newKey = newStatus.toLowerCase() as keyof Pick<
    JobQueueStats,
    'queued' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'skipped'
  >;
  if (newKey in newStats && typeof newStats[newKey] === 'number') {
    (newStats[newKey] as number) += 1;
  }

  return newStats;
}

// =============================================================================
// Selectors (for optimized re-renders)
// =============================================================================

/** Select jobs as array */
export const selectJobsArray = (state: ProcessingStore) =>
  Array.from(state.jobs.values());

/** Select active job count */
export const selectActiveJobCount = (state: ProcessingStore) => {
  let count = 0;
  for (const job of state.jobs.values()) {
    if (job.status === 'QUEUED' || job.status === 'PROCESSING') {
      count++;
    }
  }
  return count;
};

/** Select failed job count */
export const selectFailedJobCount = (state: ProcessingStore) => {
  let count = 0;
  for (const job of state.jobs.values()) {
    if (job.status === 'FAILED') {
      count++;
    }
  }
  return count;
};

/** Select whether any jobs are processing */
export const selectIsProcessing = (state: ProcessingStore) => {
  for (const job of state.jobs.values()) {
    if (job.status === 'PROCESSING') {
      return true;
    }
  }
  return false;
};
