'use client';

import { useState } from 'react';
import { CheckCircle2, Clock, Loader2, XCircle, RotateCcw, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { toast } from 'sonner';
import { jobsApi } from '@/lib/api/jobs';
import type { ProcessingJob } from '@/types/job';
import { getJobStatusLabel, STAGE_LABELS, isJobStuck } from '@/types/job';

/** Pipeline stages in order */
const PIPELINE_STAGES = [
  'ocr',
  'validation',
  'confidence',
  'chunking',
  'embedding',
  'entity_extraction',
  'alias_resolution',
] as const;

interface JobProgressCardProps {
  /** The job to display */
  job: ProcessingJob;
  /** Document filename for display */
  filename?: string;
  /** Optional click handler */
  onClick?: () => void;
  /** Callback when job is cancelled or reset */
  onAction?: () => void;
  /** Threshold in minutes before showing stuck warning */
  stuckThresholdMinutes?: number;
}

/**
 * Job Progress Card
 *
 * Shows detailed progress for an individual processing job.
 * Includes visual progress bar with stage indicators and estimated time remaining.
 */
export function JobProgressCard({
  job,
  filename,
  onClick,
  onAction,
  stuckThresholdMinutes = 5,
}: JobProgressCardProps) {
  const [isCancelling, setIsCancelling] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const isProcessing = job.status === 'PROCESSING';
  const isQueued = job.status === 'QUEUED';
  const stuck = isJobStuck(job, stuckThresholdMinutes);

  const estimatedTimeRemaining = job.estimated_completion
    ? formatTimeRemaining(job.estimated_completion)
    : null;

  const elapsedTime = job.started_at ? formatElapsedTime(job.started_at) : null;

  // Handle cancel
  const handleCancel = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsCancelling(true);
    try {
      const response = await jobsApi.cancel(job.id);
      if (response.success) {
        toast.success('Job cancelled');
        onAction?.();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to cancel');
    } finally {
      setIsCancelling(false);
    }
  };

  // Handle reset (for stuck jobs)
  const handleReset = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsResetting(true);
    try {
      const response = await jobsApi.reset(job.id);
      if (response.success) {
        toast.success('Job reset and re-queued');
        onAction?.();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to reset');
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <Card
      className={`${onClick ? 'cursor-pointer hover:bg-muted/30 transition-colors' : ''} ${stuck ? 'border-amber-300 dark:border-amber-700' : ''}`}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium truncate">
            {filename || `Document ${job.document_id?.slice(0, 8) || 'N/A'}`}
          </CardTitle>
          {/* jaanch.ai brand: Deep Indigo for processing state */}
          <div className="flex items-center gap-2 text-sm">
            {stuck && (
              <Badge variant="outline" className="text-amber-600 border-amber-300 dark:text-amber-500 dark:border-amber-700">
                <AlertTriangle className="mr-1 size-3" />
                Stuck
              </Badge>
            )}
            {isProcessing && !stuck && (
              <Loader2 className="size-4 animate-spin text-[#0d1b5e] dark:text-[#6b7cb8]" aria-hidden="true" />
            )}
            {isQueued && (
              <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
            )}
            <span
              className={
                stuck
                  ? 'text-amber-600 dark:text-amber-500'
                  : isProcessing
                    ? 'text-[#0d1b5e] dark:text-[#6b7cb8]'
                    : isQueued
                      ? 'text-muted-foreground'
                      : ''
              }
            >
              {getJobStatusLabel(job.status)}
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Progress bar */}
        <div>
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-muted-foreground">
              {job.current_stage
                ? STAGE_LABELS[job.current_stage] || job.current_stage
                : isQueued
                  ? 'Waiting in queue'
                  : 'Starting...'}
            </span>
            <span className="font-mono">{job.progress_pct}%</span>
          </div>
          <Progress
            value={job.progress_pct}
            className="h-2"
            aria-label={`Progress: ${job.progress_pct}%`}
          />
        </div>

        {/* Stage indicators */}
        <div className="flex justify-between gap-1">
          {PIPELINE_STAGES.map((stage, index) => {
            const isCompleted = index < job.completed_stages;
            const isCurrent = stage === job.current_stage;

            {/* jaanch.ai brand: Forest Green completed, Deep Indigo current */}
            return (
              <Tooltip key={stage}>
                <TooltipTrigger asChild>
                  <div
                    className={`
                      flex-1 h-1.5 rounded-full transition-colors
                      ${
                        isCompleted
                          ? 'bg-[#2d5a3d]'
                          : isCurrent
                            ? 'bg-[#0d1b5e] animate-pulse dark:bg-[#6b7cb8]'
                            : 'bg-muted'
                      }
                    `}
                    aria-label={`${STAGE_LABELS[stage] || stage}: ${
                      isCompleted ? 'completed' : isCurrent ? 'in progress' : 'pending'
                    }`}
                  />
                </TooltipTrigger>
                <TooltipContent>
                  <div className="flex items-center gap-1">
                    {isCompleted && (
                      <CheckCircle2 className="size-3 text-[#2d5a3d] dark:text-[#4a8a5d]" />
                    )}
                    {isCurrent && (
                      <Loader2 className="size-3 animate-spin" />
                    )}
                    <span>{STAGE_LABELS[stage] || stage}</span>
                  </div>
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>

        {/* Time info */}
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Clock className="size-4" aria-hidden="true" />
            {elapsedTime && <span>Elapsed: {elapsedTime}</span>}
            {estimatedTimeRemaining && isProcessing && !stuck && (
              <span className="text-xs">({estimatedTimeRemaining} remaining)</span>
            )}
          </div>
          <span className="text-xs">
            Stage {job.completed_stages + 1} of {job.total_stages}
          </span>
        </div>

        {/* Action buttons */}
        {(isProcessing || isQueued) && (
          <div className="flex gap-2 pt-2 border-t">
            {stuck && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleReset}
                disabled={isResetting}
                className="flex-1 text-amber-600 border-amber-300 hover:bg-amber-50 dark:text-amber-500 dark:border-amber-700 dark:hover:bg-amber-950/30"
              >
                {isResetting ? (
                  <Loader2 className="mr-2 size-3 animate-spin" />
                ) : (
                  <RotateCcw className="mr-2 size-3" />
                )}
                Reset
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={isCancelling}
              className="flex-1"
            >
              {isCancelling ? (
                <Loader2 className="mr-2 size-3 animate-spin" />
              ) : (
                <XCircle className="mr-2 size-3" />
              )}
              Cancel
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Format time remaining in human-readable format
 */
function formatTimeRemaining(estimatedCompletion: string): string | null {
  const target = new Date(estimatedCompletion);
  const now = new Date();
  const diffMs = target.getTime() - now.getTime();

  if (diffMs <= 0) return null;

  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes % 60}m`;
  }
  if (diffMinutes > 0) {
    return `${diffMinutes}m`;
  }
  return `${diffSeconds}s`;
}

/**
 * Format elapsed time since job started
 */
function formatElapsedTime(startedAt: string): string {
  const start = new Date(startedAt);
  const now = new Date();
  const diffMs = now.getTime() - start.getTime();

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
