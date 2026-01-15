'use client';

import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, XCircle, Filter, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { jobsApi } from '@/lib/api/jobs';
import { JobProgressCard } from './JobProgressCard';
import { FailedJobCard } from './FailedJobCard';
import {
  useProcessingStore,
  selectJobsArray,
  selectActiveJobCount,
  selectFailedJobCount,
} from '@/stores/processingStore';
import type { JobStatus, ProcessingJob } from '@/types/job';

interface ProcessingQueueProps {
  /** Matter ID to show jobs for */
  matterId: string;
  /** Optional callback to get document filename by ID */
  getFilename?: (documentId: string) => string | undefined;
}

type StatusFilter = 'all' | JobStatus;

/**
 * Processing Queue
 *
 * List of all processing jobs for a matter with filtering and bulk actions.
 */
export function ProcessingQueue({ matterId, getFilename }: ProcessingQueueProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [isRetryingAll, setIsRetryingAll] = useState(false);
  const [isCancellingAll, setIsCancellingAll] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const jobs = useProcessingStore(selectJobsArray);
  const isLoading = useProcessingStore((state) => state.isLoading);
  const setJobs = useProcessingStore((state) => state.setJobs);
  const setStats = useProcessingStore((state) => state.setStats);
  const setLoading = useProcessingStore((state) => state.setLoading);
  const setMatterId = useProcessingStore((state) => state.setMatterId);

  const activeCount = useProcessingStore(selectActiveJobCount);
  const failedCount = useProcessingStore(selectFailedJobCount);

  // Load jobs on mount and when matter changes
  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsResponse, statsResponse] = await Promise.all([
        jobsApi.list({ matterId }),
        jobsApi.getStats(matterId),
      ]);
      setJobs(jobsResponse.jobs);
      setStats(statsResponse);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load jobs';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [matterId, setJobs, setStats, setLoading]);

  useEffect(() => {
    setMatterId(matterId);
    loadJobs();
  }, [matterId, setMatterId, loadJobs]);

  // Filter jobs based on status
  const filteredJobs = jobs.filter((job) => {
    if (statusFilter === 'all') return true;
    return job.status === statusFilter;
  });

  // Sort jobs: processing first, then queued, then failed, then completed
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    const statusOrder: Record<JobStatus, number> = {
      PROCESSING: 0,
      QUEUED: 1,
      FAILED: 2,
      CANCELLED: 3,
      SKIPPED: 4,
      COMPLETED: 5,
    };
    return statusOrder[a.status] - statusOrder[b.status];
  });

  // Refresh handler
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadJobs();
    setIsRefreshing(false);
  };

  // Retry all failed jobs
  const handleRetryAll = async () => {
    const failedJobs = jobs.filter((job) => job.status === 'FAILED');
    if (failedJobs.length === 0) return;

    setIsRetryingAll(true);
    let successCount = 0;
    let failCount = 0;

    for (const job of failedJobs) {
      try {
        await jobsApi.retry(job.id, { reset_retry_count: true });
        successCount++;
      } catch {
        failCount++;
      }
    }

    if (successCount > 0) {
      toast.success(`Queued ${successCount} job${successCount !== 1 ? 's' : ''} for retry`);
    }
    if (failCount > 0) {
      toast.error(`Failed to retry ${failCount} job${failCount !== 1 ? 's' : ''}`);
    }

    await loadJobs();
    setIsRetryingAll(false);
  };

  // Cancel all pending jobs
  const handleCancelAll = async () => {
    const pendingJobs = jobs.filter((job) => job.status === 'QUEUED');
    if (pendingJobs.length === 0) return;

    setIsCancellingAll(true);
    let successCount = 0;
    let failCount = 0;

    for (const job of pendingJobs) {
      try {
        await jobsApi.cancel(job.id);
        successCount++;
      } catch {
        failCount++;
      }
    }

    if (successCount > 0) {
      toast.success(`Cancelled ${successCount} job${successCount !== 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      toast.error(`Failed to cancel ${failCount} job${failCount !== 1 ? 's' : ''}`);
    }

    await loadJobs();
    setIsCancellingAll(false);
  };

  if (isLoading && jobs.length === 0) {
    return <ProcessingQueueSkeleton />;
  }

  return (
    <div className="space-y-4">
      {/* Header with filters and actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Processing Queue</h2>

          {/* Status filter */}
          <Select
            value={statusFilter}
            onValueChange={(v) => setStatusFilter(v as StatusFilter)}
          >
            <SelectTrigger className="w-36">
              <Filter className="mr-2 size-4" />
              <SelectValue placeholder="Filter" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All jobs</SelectItem>
              <SelectItem value="PROCESSING">Processing</SelectItem>
              <SelectItem value="QUEUED">Queued</SelectItem>
              <SelectItem value="FAILED">Failed</SelectItem>
              <SelectItem value="COMPLETED">Completed</SelectItem>
              <SelectItem value="CANCELLED">Cancelled</SelectItem>
              <SelectItem value="SKIPPED">Skipped</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw
              className={`mr-2 size-4 ${isRefreshing ? 'animate-spin' : ''}`}
            />
            Refresh
          </Button>

          {failedCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetryAll}
              disabled={isRetryingAll}
            >
              {isRetryingAll ? (
                <RefreshCw className="mr-2 size-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 size-4" />
              )}
              Retry all failed ({failedCount})
            </Button>
          )}

          {jobs.some((j) => j.status === 'QUEUED') && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancelAll}
              disabled={isCancellingAll}
            >
              <XCircle className="mr-2 size-4" />
              Cancel pending
            </Button>
          )}
        </div>
      </div>

      {/* Summary stats */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>
          <CheckCircle2 className="mr-1 inline size-4 text-green-500" />
          {jobs.filter((j) => j.status === 'COMPLETED').length} completed
        </span>
        <span>{activeCount} active</span>
        <span className={failedCount > 0 ? 'text-destructive' : ''}>
          {failedCount} failed
        </span>
      </div>

      {/* Job list */}
      {sortedJobs.length === 0 ? (
        <div className="rounded-lg border bg-muted/50 p-8 text-center">
          <p className="text-muted-foreground">No jobs found</p>
          {statusFilter !== 'all' && (
            <Button
              variant="link"
              onClick={() => setStatusFilter('all')}
              className="mt-2"
            >
              Clear filter
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sortedJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              filename={
                job.document_id ? getFilename?.(job.document_id) : undefined
              }
              onUpdate={loadJobs}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Render appropriate card based on job status
 */
function JobCard({
  job,
  filename,
  onUpdate,
}: {
  job: ProcessingJob;
  filename?: string;
  onUpdate: () => void;
}) {
  if (job.status === 'FAILED') {
    return (
      <FailedJobCard
        job={job}
        filename={filename}
        onRetry={onUpdate}
        onSkip={onUpdate}
      />
    );
  }

  return <JobProgressCard job={job} filename={filename} />;
}

/**
 * Loading skeleton
 */
function ProcessingQueueSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-36" />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-48 rounded-lg" />
        ))}
      </div>
    </div>
  );
}
