'use client';

import { AlertCircle, ChevronDown, ChevronUp, Loader2, X } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  useProcessingStore,
  selectActiveJobCount,
  selectFailedJobCount,
} from '@/stores/processingStore';
import type { ProcessingJob } from '@/types/job';
import { STAGE_LABELS } from '@/types/job';

interface ProcessingStatusBannerProps {
  /** Optional callback when banner is dismissed */
  onDismiss?: () => void;
  /** Whether the banner can be collapsed */
  collapsible?: boolean;
}

/**
 * Processing Status Banner
 *
 * Shows a banner when documents are being processed.
 * Displays overall progress and allows expanding for details.
 */
export function ProcessingStatusBanner({
  onDismiss,
  collapsible = true,
}: ProcessingStatusBannerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const activeCount = useProcessingStore(selectActiveJobCount);
  const failedCount = useProcessingStore(selectFailedJobCount);
  const jobs = useProcessingStore((state) => state.jobs);
  const stats = useProcessingStore((state) => state.stats);

  // Get active jobs for display
  const activeJobs = Array.from(jobs.values()).filter(
    (job) => job.status === 'QUEUED' || job.status === 'PROCESSING'
  );

  // Calculate overall progress
  const overallProgress = calculateOverallProgress(activeJobs);

  // Don't show if no active jobs and no failed jobs
  if (activeCount === 0 && failedCount === 0) {
    return null;
  }

  return (
    <div
      className="rounded-lg border bg-muted/50 p-4"
      role="status"
      aria-live="polite"
      aria-label="Processing status"
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {activeCount > 0 ? (
            <Loader2
              className="size-5 animate-spin text-blue-600"
              aria-hidden="true"
            />
          ) : (
            <AlertCircle
              className="size-5 text-destructive"
              aria-hidden="true"
            />
          )}

          <div>
            <p className="font-medium">
              {activeCount > 0 ? (
                <>
                  Processing {activeCount} document
                  {activeCount !== 1 ? 's' : ''} - {overallProgress}% complete
                </>
              ) : (
                <>
                  {failedCount} document{failedCount !== 1 ? 's' : ''} failed
                  processing
                </>
              )}
            </p>
            {activeCount > 0 && stats && (
              <p className="text-sm text-muted-foreground">
                {stats.completed} completed, {stats.queued} queued
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {collapsible && activeJobs.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              aria-expanded={isExpanded}
              aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
            >
              {isExpanded ? (
                <>
                  Hide details
                  <ChevronUp className="ml-1 size-4" />
                </>
              ) : (
                <>
                  Show details
                  <ChevronDown className="ml-1 size-4" />
                </>
              )}
            </Button>
          )}

          {onDismiss && activeCount === 0 && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onDismiss}
              aria-label="Dismiss"
            >
              <X className="size-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {activeCount > 0 && (
        <div className="mt-3">
          <Progress
            value={overallProgress}
            className="h-2"
            aria-label={`Overall progress: ${overallProgress}%`}
          />
        </div>
      )}

      {/* Expanded details */}
      {isExpanded && activeJobs.length > 0 && (
        <div className="mt-4 space-y-2 border-t pt-4">
          {activeJobs.slice(0, 5).map((job) => (
            <ProcessingJobRow key={job.id} job={job} />
          ))}
          {activeJobs.length > 5 && (
            <p className="text-sm text-muted-foreground">
              ...and {activeJobs.length - 5} more
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Individual job row for expanded view
 */
function ProcessingJobRow({ job }: { job: ProcessingJob }) {
  const stageName = job.current_stage
    ? STAGE_LABELS[job.current_stage] || job.current_stage
    : 'Starting...';

  return (
    <div className="flex items-center gap-3 text-sm">
      <div className="flex-1 truncate">
        <span className="font-medium">Document</span>
        {job.document_id && (
          <span className="ml-2 text-muted-foreground">
            {job.document_id.slice(0, 8)}...
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">{stageName}</span>
        <span className="font-mono text-xs">{job.progress_pct}%</span>
      </div>
    </div>
  );
}

/**
 * Calculate overall progress from active jobs
 */
function calculateOverallProgress(jobs: ProcessingJob[]): number {
  if (jobs.length === 0) return 0;

  const totalProgress = jobs.reduce((sum, job) => sum + job.progress_pct, 0);
  return Math.round(totalProgress / jobs.length);
}
