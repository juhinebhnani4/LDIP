'use client';

import { useState } from 'react';
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  ChevronDown,
  RefreshCw,
  SkipForward,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { toast } from 'sonner';
import { jobsApi } from '@/lib/api/jobs';
import { useProcessingStore } from '@/stores/processingStore';
import type { ProcessingJob } from '@/types/job';
import {
  canRetryJob,
  canSkipJob,
  getJobStatusLabel,
  STAGE_LABELS,
} from '@/types/job';

interface DocumentProcessingStatusProps {
  /** Document ID to show status for */
  documentId: string;
  /** Whether to show in compact mode (icon only) */
  compact?: boolean;
  /** Callback when status changes */
  onStatusChange?: () => void;
}

/**
 * Document Processing Status
 *
 * Mini progress indicator for inline use in document lists.
 * Expandable to show current stage details and actions.
 */
export function DocumentProcessingStatus({
  documentId,
  compact = false,
  onStatusChange,
}: DocumentProcessingStatusProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);

  const getJobForDocument = useProcessingStore((state) => state.getJobForDocument);
  const updateJob = useProcessingStore((state) => state.updateJob);

  const job = getJobForDocument(documentId);

  // No job = no status to show
  if (!job) return null;

  const handleRetry = async () => {
    if (!canRetryJob(job)) return;

    setIsRetrying(true);
    try {
      const response = await jobsApi.retry(job.id, { reset_retry_count: true });
      if (response.success) {
        toast.success('Job queued for retry');
        updateJob({
          ...job,
          status: 'QUEUED',
          retry_count: 0,
          error_message: null,
          error_code: null,
        });
        onStatusChange?.();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to retry');
    } finally {
      setIsRetrying(false);
    }
  };

  const handleSkip = async () => {
    if (!canSkipJob(job)) return;

    setIsSkipping(true);
    try {
      const response = await jobsApi.skip(job.id);
      if (response.success) {
        toast.success('Job skipped');
        updateJob({ ...job, status: 'SKIPPED' });
        onStatusChange?.();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to skip');
    } finally {
      setIsSkipping(false);
    }
  };

  // Render based on status
  if (compact) {
    return (
      <CompactStatus
        job={job}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        onRetry={handleRetry}
        onSkip={handleSkip}
        isRetrying={isRetrying}
        isSkipping={isSkipping}
      />
    );
  }

  return (
    <InlineStatus
      job={job}
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      onRetry={handleRetry}
      onSkip={handleSkip}
      isRetrying={isRetrying}
      isSkipping={isSkipping}
    />
  );
}

/**
 * Compact status indicator (icon only with popover)
 */
function CompactStatus({
  job,
  isOpen,
  onOpenChange,
  onRetry,
  onSkip,
  isRetrying,
  isSkipping,
}: {
  job: ProcessingJob;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onRetry: () => void;
  onSkip: () => void;
  isRetrying: boolean;
  isSkipping: boolean;
}) {
  return (
    <Popover open={isOpen} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <button
          className="inline-flex items-center gap-1 rounded p-1 hover:bg-muted/50"
          aria-label={`Processing status: ${getJobStatusLabel(job.status)}`}
        >
          <StatusIcon job={job} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="start">
        <StatusDetails
          job={job}
          onRetry={onRetry}
          onSkip={onSkip}
          isRetrying={isRetrying}
          isSkipping={isSkipping}
        />
      </PopoverContent>
    </Popover>
  );
}

/**
 * Inline status with progress bar
 */
function InlineStatus({
  job,
  isOpen,
  onOpenChange,
  onRetry,
  onSkip,
  isRetrying,
  isSkipping,
}: {
  job: ProcessingJob;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onRetry: () => void;
  onSkip: () => void;
  isRetrying: boolean;
  isSkipping: boolean;
}) {
  const isActive = job.status === 'QUEUED' || job.status === 'PROCESSING';
  const isFailed = job.status === 'FAILED';

  return (
    <Popover open={isOpen} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <button
          className={`inline-flex items-center gap-2 rounded-md px-2 py-1 text-sm transition-colors hover:bg-muted/50 ${
            isFailed ? 'text-destructive' : ''
          }`}
          aria-label={`Processing status: ${getJobStatusLabel(job.status)}`}
        >
          <StatusIcon job={job} />
          {isActive && (
            <>
              <Progress
                value={job.progress_pct}
                className="h-1.5 w-16"
                aria-label={`${job.progress_pct}% complete`}
              />
              <span className="text-xs text-muted-foreground">
                {job.progress_pct}%
              </span>
            </>
          )}
          {isFailed && (
            <span className="text-xs">Failed</span>
          )}
          <ChevronDown className="size-3" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="start">
        <StatusDetails
          job={job}
          onRetry={onRetry}
          onSkip={onSkip}
          isRetrying={isRetrying}
          isSkipping={isSkipping}
        />
      </PopoverContent>
    </Popover>
  );
}

/**
 * Status icon based on job state
 */
function StatusIcon({ job }: { job: ProcessingJob }) {
  switch (job.status) {
    case 'PROCESSING':
      return (
        <Loader2
          className="size-4 animate-spin text-blue-600"
          aria-hidden="true"
        />
      );
    case 'QUEUED':
      return (
        <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
      );
    case 'COMPLETED':
      return (
        <CheckCircle2 className="size-4 text-green-600" aria-hidden="true" />
      );
    case 'FAILED':
      return (
        <AlertCircle className="size-4 text-destructive" aria-hidden="true" />
      );
    default:
      return (
        <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
      );
  }
}

/**
 * Detailed status content for popover
 */
function StatusDetails({
  job,
  onRetry,
  onSkip,
  isRetrying,
  isSkipping,
}: {
  job: ProcessingJob;
  onRetry: () => void;
  onSkip: () => void;
  isRetrying: boolean;
  isSkipping: boolean;
}) {
  const stageName = job.current_stage
    ? STAGE_LABELS[job.current_stage] || job.current_stage
    : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-medium">{getJobStatusLabel(job.status)}</span>
        {(job.status === 'QUEUED' || job.status === 'PROCESSING') && (
          <span className="text-sm text-muted-foreground">
            {job.progress_pct}%
          </span>
        )}
      </div>

      {stageName && (
        <div className="text-sm text-muted-foreground">
          Current stage: {stageName}
        </div>
      )}

      {(job.status === 'QUEUED' || job.status === 'PROCESSING') && (
        <div>
          <Progress
            value={job.progress_pct}
            className="h-2"
            aria-label={`${job.progress_pct}% complete`}
          />
          <div className="mt-1 text-xs text-muted-foreground">
            Stage {job.completed_stages + 1} of {job.total_stages}
          </div>
        </div>
      )}

      {job.status === 'FAILED' && (
        <div className="space-y-2">
          {job.error_message && (
            <div className="rounded bg-destructive/10 p-2 text-sm text-destructive">
              {job.error_message}
            </div>
          )}
          <div className="text-xs text-muted-foreground">
            Attempts: {job.retry_count} / {job.max_retries}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={onRetry}
              disabled={!canRetryJob(job) || isRetrying || isSkipping}
              className="flex-1"
            >
              {isRetrying ? (
                <RefreshCw className="mr-1 size-3 animate-spin" />
              ) : (
                <RefreshCw className="mr-1 size-3" />
              )}
              Retry
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onSkip}
              disabled={!canSkipJob(job) || isRetrying || isSkipping}
              className="flex-1"
            >
              {isSkipping ? (
                <SkipForward className="mr-1 size-3 animate-pulse" />
              ) : (
                <SkipForward className="mr-1 size-3" />
              )}
              Skip
            </Button>
          </div>
        </div>
      )}

      {job.estimated_completion && job.status === 'PROCESSING' && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="size-3" />
          Est. completion:{' '}
          {new Date(job.estimated_completion).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
