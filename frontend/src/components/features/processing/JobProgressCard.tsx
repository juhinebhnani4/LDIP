'use client';

import { CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { ProcessingJob } from '@/types/job';
import { getJobStatusLabel, STAGE_LABELS } from '@/types/job';

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
}

/**
 * Job Progress Card
 *
 * Shows detailed progress for an individual processing job.
 * Includes visual progress bar with stage indicators and estimated time remaining.
 */
export function JobProgressCard({ job, filename, onClick }: JobProgressCardProps) {
  const isProcessing = job.status === 'PROCESSING';
  const isQueued = job.status === 'QUEUED';
  const currentStageIndex = job.current_stage
    ? PIPELINE_STAGES.indexOf(job.current_stage as (typeof PIPELINE_STAGES)[number])
    : -1;

  const estimatedTimeRemaining = job.estimated_completion
    ? formatTimeRemaining(job.estimated_completion)
    : null;

  return (
    <Card
      className={onClick ? 'cursor-pointer hover:bg-muted/30 transition-colors' : ''}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium truncate">
            {filename || `Document ${job.document_id?.slice(0, 8) || 'N/A'}`}
          </CardTitle>
          <div className="flex items-center gap-2 text-sm">
            {isProcessing && (
              <Loader2 className="size-4 animate-spin text-blue-600" aria-hidden="true" />
            )}
            {isQueued && (
              <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
            )}
            <span
              className={
                isProcessing
                  ? 'text-blue-600'
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

            return (
              <Tooltip key={stage}>
                <TooltipTrigger asChild>
                  <div
                    className={`
                      flex-1 h-1.5 rounded-full transition-colors
                      ${
                        isCompleted
                          ? 'bg-green-500'
                          : isCurrent
                            ? 'bg-blue-500 animate-pulse'
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
                      <CheckCircle2 className="size-3 text-green-500" />
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

        {/* Time remaining */}
        {estimatedTimeRemaining && isProcessing && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="size-4" aria-hidden="true" />
            <span>Est. {estimatedTimeRemaining} remaining</span>
          </div>
        )}

        {/* Stage progress text */}
        <div className="text-xs text-muted-foreground">
          Stage {job.completed_stages + 1} of {job.total_stages}
        </div>
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
