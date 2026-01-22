'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { toast } from 'sonner';
import { jobsApi } from '@/lib/api/jobs';
import type { StuckJobInfo } from '@/types/job';
import { STAGE_LABELS } from '@/types/job';

interface StuckJobsBannerProps {
  /** Matter ID to check for stuck jobs */
  matterId: string;
  /** Callback when jobs are refreshed */
  onRefresh?: () => void;
  /** Optional document name lookup */
  getDocumentName?: (documentId: string) => string | undefined;
  /** Poll interval in ms (default: 30000 = 30 seconds) */
  pollInterval?: number;
}

/**
 * StuckJobsBanner
 *
 * Displays a warning banner when jobs are stuck in PROCESSING state for too long.
 * Allows users to reset stuck jobs without needing admin access.
 */
export function StuckJobsBanner({
  matterId,
  onRefresh,
  getDocumentName,
  pollInterval = 30000,
}: StuckJobsBannerProps) {
  const [stuckJobs, setStuckJobs] = useState<StuckJobInfo[]>([]);
  const [thresholdMinutes, setThresholdMinutes] = useState(5);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [resettingJobs, setResettingJobs] = useState<Set<string>>(new Set());
  const [isResettingAll, setIsResettingAll] = useState(false);

  // Fetch stuck jobs
  const fetchStuckJobs = useCallback(async () => {
    try {
      const response = await jobsApi.getStuckJobs(matterId);
      setStuckJobs(response.stuck_jobs);
      setThresholdMinutes(response.threshold_minutes);
    } catch (err) {
      // Silently fail - this is a background check
      console.error('Failed to fetch stuck jobs:', err);
    }
  }, [matterId]);

  // Initial fetch and polling
  useEffect(() => {
    fetchStuckJobs();

    const interval = setInterval(fetchStuckJobs, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStuckJobs, pollInterval]);

  // Reset a single stuck job
  const handleResetJob = async (jobId: string) => {
    setResettingJobs((prev) => new Set(prev).add(jobId));
    try {
      const response = await jobsApi.reset(jobId);
      if (response.success) {
        toast.success('Job reset and re-queued for processing');
        // Remove from list
        setStuckJobs((prev) => prev.filter((j) => j.job_id !== jobId));
        onRefresh?.();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reset job';
      toast.error(message);
    } finally {
      setResettingJobs((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
    }
  };

  // Reset all stuck jobs
  const handleResetAll = async () => {
    if (stuckJobs.length === 0) return;

    setIsResettingAll(true);
    let successCount = 0;
    let failCount = 0;

    for (const job of stuckJobs) {
      try {
        await jobsApi.reset(job.job_id);
        successCount++;
      } catch {
        failCount++;
      }
    }

    if (successCount > 0) {
      toast.success(`Reset ${successCount} stuck job${successCount !== 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      toast.error(`Failed to reset ${failCount} job${failCount !== 1 ? 's' : ''}`);
    }

    await fetchStuckJobs();
    onRefresh?.();
    setIsResettingAll(false);
  };

  // Manual refresh
  const handleRefresh = async () => {
    setIsLoading(true);
    await fetchStuckJobs();
    setIsLoading(false);
  };

  // Don't render if no stuck jobs
  if (stuckJobs.length === 0) {
    return null;
  }

  return (
    <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30">
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="size-5 text-amber-600 dark:text-amber-500" />
            <div>
              <span className="font-medium text-amber-800 dark:text-amber-200">
                {stuckJobs.length} job{stuckJobs.length !== 1 ? 's' : ''} appear stuck
              </span>
              <span className="ml-2 text-sm text-amber-600 dark:text-amber-400">
                (no progress for {thresholdMinutes}+ minutes)
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetAll}
              disabled={isResettingAll}
              className="border-amber-300 bg-white hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-900/50"
            >
              {isResettingAll ? (
                <RefreshCw className="mr-2 size-4 animate-spin" />
              ) : (
                <RotateCcw className="mr-2 size-4" />
              )}
              Reset all
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
            >
              <RefreshCw
                className={`size-4 ${isLoading ? 'animate-spin' : ''}`}
              />
            </Button>

            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm">
                {isExpanded ? (
                  <ChevronUp className="size-4" />
                ) : (
                  <ChevronDown className="size-4" />
                )}
              </Button>
            </CollapsibleTrigger>
          </div>
        </div>

        <CollapsibleContent>
          <div className="border-t border-amber-200 dark:border-amber-800">
            <div className="divide-y divide-amber-200 dark:divide-amber-800">
              {stuckJobs.map((job) => (
                <StuckJobRow
                  key={job.job_id}
                  job={job}
                  documentName={
                    job.document_id
                      ? getDocumentName?.(job.document_id)
                      : undefined
                  }
                  isResetting={resettingJobs.has(job.job_id)}
                  onReset={() => handleResetJob(job.job_id)}
                />
              ))}
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

/**
 * Individual stuck job row
 */
function StuckJobRow({
  job,
  documentName,
  isResetting,
  onReset,
}: {
  job: StuckJobInfo;
  documentName?: string;
  isResetting: boolean;
  onReset: () => void;
}) {
  const stageName = job.current_stage
    ? STAGE_LABELS[job.current_stage] || job.current_stage
    : 'Unknown stage';

  return (
    <div className="flex items-center justify-between px-4 py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">
            {documentName || job.document_id?.slice(0, 8) || 'Unknown document'}
          </span>
          <Badge variant="outline" className="shrink-0 text-xs">
            {stageName}
          </Badge>
        </div>
        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="size-3" />
            Stuck for {job.stuck_minutes} min
          </span>
          <span>{job.progress_pct}% complete</span>
          {job.recovery_attempts > 0 && (
            <span className="text-amber-600">
              {job.recovery_attempts} auto-recovery attempts
            </span>
          )}
        </div>
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={onReset}
        disabled={isResetting}
        className="shrink-0 ml-4"
      >
        {isResetting ? (
          <RefreshCw className="mr-2 size-3 animate-spin" />
        ) : (
          <RotateCcw className="mr-2 size-3" />
        )}
        Reset
      </Button>
    </div>
  );
}
