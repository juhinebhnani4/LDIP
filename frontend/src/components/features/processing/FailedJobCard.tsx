'use client';

import { AlertTriangle, RefreshCw, SkipForward } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { jobsApi } from '@/lib/api/jobs';
import type { ProcessingJob } from '@/types/job';
import { canRetryJob, canSkipJob, STAGE_LABELS } from '@/types/job';
import { useProcessingStore } from '@/stores/processingStore';

interface FailedJobCardProps {
  /** The failed job to display */
  job: ProcessingJob;
  /** Document filename for display */
  filename?: string;
  /** Callback when job is retried successfully */
  onRetry?: () => void;
  /** Callback when job is skipped */
  onSkip?: () => void;
}

/**
 * Failed Job Card
 *
 * Shows a failed job with error details and action buttons.
 * Allows retrying or skipping the failed job.
 */
export function FailedJobCard({
  job,
  filename,
  onRetry,
  onSkip,
}: FailedJobCardProps) {
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);

  const updateJob = useProcessingStore((state) => state.updateJob);

  const failedStage = job.current_stage
    ? STAGE_LABELS[job.current_stage] || job.current_stage
    : 'Unknown stage';

  const handleRetry = async () => {
    if (!canRetryJob(job)) {
      toast.error('This job cannot be retried');
      return;
    }

    setIsRetrying(true);
    try {
      const response = await jobsApi.retry(job.id, { reset_retry_count: true });
      if (response.success) {
        toast.success('Job queued for retry');
        // Optimistically update the job in the store
        updateJob({
          ...job,
          status: 'QUEUED',
          retry_count: 0,
          error_message: null,
          error_code: null,
        });
        onRetry?.();
      } else {
        toast.error(response.message || 'Failed to retry job');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to retry job';
      toast.error(message);
    } finally {
      setIsRetrying(false);
    }
  };

  const handleSkip = async () => {
    if (!canSkipJob(job)) {
      toast.error('This job cannot be skipped');
      return;
    }

    setIsSkipping(true);
    try {
      const response = await jobsApi.skip(job.id);
      if (response.success) {
        toast.success('Job marked as skipped');
        // Optimistically update the job in the store
        updateJob({
          ...job,
          status: 'SKIPPED',
        });
        onSkip?.();
      } else {
        toast.error(response.message || 'Failed to skip job');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to skip job';
      toast.error(message);
    } finally {
      setIsSkipping(false);
    }
  };

  return (
    <Card className="border-destructive/50 bg-destructive/5">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle
              className="size-5 flex-shrink-0 text-destructive"
              aria-hidden="true"
            />
            <CardTitle className="text-base font-medium truncate">
              {filename || `Document ${job.document_id?.slice(0, 8) || 'N/A'}`}
            </CardTitle>
          </div>
          <Badge variant="destructive" className="flex-shrink-0">
            Failed
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Error details */}
        <div className="space-y-2">
          <div className="text-sm">
            <span className="text-muted-foreground">Failed at: </span>
            <span className="font-medium">{failedStage}</span>
          </div>

          {job.error_message && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm">
              <p className="text-destructive">{job.error_message}</p>
              {job.error_code && (
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  Error code: {job.error_code}
                </p>
              )}
            </div>
          )}

          {/* Retry count indicator */}
          <div className="text-sm text-muted-foreground">
            Retry attempts: {job.retry_count} / {job.max_retries}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            disabled={!canRetryJob(job) || isRetrying || isSkipping}
            className="flex-1"
          >
            {isRetrying ? (
              <RefreshCw className="mr-2 size-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 size-4" />
            )}
            Retry
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleSkip}
            disabled={!canSkipJob(job) || isRetrying || isSkipping}
            className="flex-1"
          >
            {isSkipping ? (
              <SkipForward className="mr-2 size-4 animate-pulse" />
            ) : (
              <SkipForward className="mr-2 size-4" />
            )}
            Skip
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
