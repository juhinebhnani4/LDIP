'use client';

import { AlertTriangle, RefreshCw, SkipForward, Clock, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
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
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const updateJob = useProcessingStore((state) => state.updateJob);

  const failedStage = job.current_stage
    ? STAGE_LABELS[job.current_stage] || job.current_stage
    : 'Unknown stage';

  // Format timestamps
  const failedAt = job.updated_at ? new Date(job.updated_at).toLocaleString() : null;
  const startedAt = job.started_at ? new Date(job.started_at).toLocaleString() : null;
  const duration = job.started_at && job.updated_at
    ? formatDuration(new Date(job.started_at), new Date(job.updated_at))
    : null;

  // Copy error details to clipboard
  const handleCopyError = async () => {
    const errorDetails = [
      `Document: ${filename || job.document_id}`,
      `Failed at stage: ${failedStage}`,
      `Error: ${job.error_message || 'Unknown error'}`,
      job.error_code ? `Error code: ${job.error_code}` : '',
      `Retry attempts: ${job.retry_count}/${job.max_retries}`,
      startedAt ? `Started: ${startedAt}` : '',
      failedAt ? `Failed: ${failedAt}` : '',
      duration ? `Duration: ${duration}` : '',
      `Job ID: ${job.id}`,
    ].filter(Boolean).join('\n');

    try {
      await navigator.clipboard.writeText(errorDetails);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success('Error details copied to clipboard');
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

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
        {/* Error summary */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div>
              <span className="text-muted-foreground">Failed at: </span>
              <span className="font-medium">{failedStage}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopyError}
              className="h-7 px-2"
            >
              {copied ? (
                <Check className="size-3 text-green-600" />
              ) : (
                <Copy className="size-3" />
              )}
            </Button>
          </div>

          {job.error_message && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm">
              <p className="text-destructive line-clamp-2">{job.error_message}</p>
              {job.error_code && (
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  Code: {job.error_code}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Expandable details */}
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-between">
              <span className="text-xs text-muted-foreground">
                {job.retry_count}/{job.max_retries} retries
                {duration && ` • ${duration}`}
              </span>
              {isExpanded ? (
                <ChevronUp className="size-4" />
              ) : (
                <ChevronDown className="size-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-2 pt-2">
            <div className="rounded-md bg-muted/50 p-3 text-xs space-y-1">
              {startedAt && (
                <div className="flex items-center gap-2">
                  <Clock className="size-3 text-muted-foreground" />
                  <span className="text-muted-foreground">Started:</span>
                  <span>{startedAt}</span>
                </div>
              )}
              {failedAt && (
                <div className="flex items-center gap-2">
                  <AlertTriangle className="size-3 text-destructive" />
                  <span className="text-muted-foreground">Failed:</span>
                  <span>{failedAt}</span>
                </div>
              )}
              {duration && (
                <div className="flex items-center gap-2">
                  <Clock className="size-3 text-muted-foreground" />
                  <span className="text-muted-foreground">Duration:</span>
                  <span>{duration}</span>
                </div>
              )}
              <div className="pt-2 border-t border-muted">
                <span className="text-muted-foreground">Job ID: </span>
                <span className="font-mono">{job.id.slice(0, 8)}...</span>
              </div>
              {job.progress_pct > 0 && (
                <div>
                  <span className="text-muted-foreground">Progress when failed: </span>
                  <span>{job.progress_pct}%</span>
                </div>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>

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

/**
 * Format duration between two dates
 */
function formatDuration(start: Date, end: Date): string {
  const diffMs = end.getTime() - start.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes % 60}m`;
  }
  if (diffMinutes > 0) {
    return `${diffMinutes}m ${diffSeconds % 60}s`;
  }
  return `${diffSeconds}s`;
}
