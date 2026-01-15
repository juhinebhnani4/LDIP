'use client';

/**
 * ProcessingProgressView Component
 *
 * Stage 4 of the upload wizard - displays overall processing progress.
 * Shows the current stage (1-5), stage name, and overall progress bar
 * with animated pulse on the current stage indicator.
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 */

import { CheckCircle2, Loader2, Circle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  PROCESSING_STAGE_LABELS,
  PROCESSING_STAGE_NUMBERS,
  type ProcessingStage,
} from '@/types/upload';

interface ProcessingProgressViewProps {
  /** Current processing stage */
  currentStage: ProcessingStage | null;
  /** Overall progress percentage (0-100) */
  overallProgressPct: number;
  /** Number of files received */
  filesReceived?: number;
  /** Total pages extracted */
  pagesExtracted?: number;
  /** OCR progress percentage */
  ocrProgressPct?: number;
  /** Documents processed */
  documentsProcessed?: number;
  /** Total documents */
  totalDocuments?: number;
  /** Optional className */
  className?: string;
}

/** All processing stages in order */
const STAGES: ProcessingStage[] = [
  'UPLOADING',
  'OCR',
  'ENTITY_EXTRACTION',
  'ANALYSIS',
  'INDEXING',
];

/** Stage indicator dot */
function StageIndicator({
  stage,
  currentStage,
  currentStageNumber,
}: {
  stage: ProcessingStage;
  currentStage: ProcessingStage | null;
  currentStageNumber: number;
}) {
  const stageNumber = PROCESSING_STAGE_NUMBERS[stage];
  const isCurrent = stage === currentStage;
  const isComplete = stageNumber < currentStageNumber;
  const isPending = stageNumber > currentStageNumber;

  return (
    <div className="flex flex-col items-center gap-1">
      {/* Stage dot */}
      <div
        className={cn(
          'flex items-center justify-center size-8 rounded-full border-2 transition-all',
          isComplete && 'bg-green-600 border-green-600',
          isCurrent && 'border-primary bg-primary/10 animate-pulse',
          isPending && 'border-muted-foreground/30 bg-background'
        )}
      >
        {isComplete ? (
          <CheckCircle2 className="size-5 text-white" aria-hidden="true" />
        ) : isCurrent ? (
          <Loader2 className="size-4 text-primary animate-spin" aria-hidden="true" />
        ) : (
          <Circle className="size-3 text-muted-foreground/50" aria-hidden="true" />
        )}
      </div>

      {/* Stage number */}
      <span
        className={cn(
          'text-xs font-medium',
          isComplete && 'text-green-600',
          isCurrent && 'text-primary',
          isPending && 'text-muted-foreground'
        )}
      >
        {stageNumber}
      </span>
    </div>
  );
}

/** Connecting line between stages */
function StageLine({
  isComplete,
  isCurrent,
}: {
  isComplete: boolean;
  isCurrent: boolean;
}) {
  return (
    <div
      className={cn(
        'flex-1 h-0.5 mx-1 transition-colors',
        isComplete && 'bg-green-600',
        isCurrent && 'bg-gradient-to-r from-primary to-muted-foreground/30',
        !isComplete && !isCurrent && 'bg-muted-foreground/30'
      )}
    />
  );
}

export function ProcessingProgressView({
  currentStage,
  overallProgressPct,
  filesReceived,
  pagesExtracted,
  ocrProgressPct,
  documentsProcessed,
  totalDocuments,
  className,
}: ProcessingProgressViewProps) {
  const currentStageNumber = currentStage
    ? PROCESSING_STAGE_NUMBERS[currentStage]
    : 0;
  const stageName = currentStage ? PROCESSING_STAGE_LABELS[currentStage] : '';
  const isComplete = currentStageNumber === 5 && overallProgressPct === 100;

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-semibold text-center">
          PROCESSING YOUR CASE
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Main progress bar with percentage */}
        <div className="space-y-3">
          <Progress
            value={overallProgressPct}
            className={cn('h-3', isComplete && '[&>div]:bg-green-600')}
            role="progressbar"
            aria-valuenow={Math.round(overallProgressPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Overall processing progress"
          />
          <div className="flex items-center justify-between">
            <span
              className={cn(
                'text-2xl font-bold',
                isComplete ? 'text-green-600' : 'text-primary'
              )}
            >
              {Math.round(overallProgressPct)}%
            </span>
            <span
              className={cn(
                'text-sm font-medium',
                isComplete ? 'text-green-600' : 'text-muted-foreground'
              )}
              aria-live="polite"
            >
              {isComplete
                ? 'Processing complete!'
                : `Stage ${currentStageNumber} of 5: ${stageName}`}
            </span>
          </div>
        </div>

        {/* Stage indicators */}
        <div
          className="flex items-start justify-between px-2"
          role="group"
          aria-label="Processing stages"
        >
          {STAGES.map((stage, index) => (
            <div key={stage} className="flex items-center flex-1 last:flex-none">
              <StageIndicator
                stage={stage}
                currentStage={currentStage}
                currentStageNumber={currentStageNumber}
              />
              {index < STAGES.length - 1 && (
                <StageLine
                  isComplete={PROCESSING_STAGE_NUMBERS[stage] < currentStageNumber}
                  isCurrent={stage === currentStage}
                />
              )}
            </div>
          ))}
        </div>

        {/* Stage labels (compact, shown below indicators) */}
        <div className="grid grid-cols-5 gap-1 text-center">
          {STAGES.map((stage) => {
            const stageNumber = PROCESSING_STAGE_NUMBERS[stage];
            const isCurrent = stage === currentStage;
            const isComplete = stageNumber < currentStageNumber;

            return (
              <span
                key={stage}
                className={cn(
                  'text-xs truncate',
                  isComplete && 'text-green-600',
                  isCurrent && 'text-primary font-medium',
                  !isComplete && !isCurrent && 'text-muted-foreground'
                )}
                title={PROCESSING_STAGE_LABELS[stage]}
              >
                {PROCESSING_STAGE_LABELS[stage].split(' ')[0]}
              </span>
            );
          })}
        </div>

        {/* Statistics grid (optional - shown when data available) */}
        {(filesReceived !== undefined || ocrProgressPct !== undefined) && (
          <div className="grid grid-cols-2 gap-4 pt-2 border-t">
            {filesReceived !== undefined && (
              <div className="text-center">
                <div className="text-lg font-semibold">{filesReceived}</div>
                <div className="text-xs text-muted-foreground">Files Received</div>
              </div>
            )}
            {pagesExtracted !== undefined && (
              <div className="text-center">
                <div className="text-lg font-semibold">
                  {pagesExtracted.toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground">Pages Extracted</div>
              </div>
            )}
            {ocrProgressPct !== undefined && currentStage === 'OCR' && (
              <div className="col-span-2">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-muted-foreground">OCR Progress</span>
                  <span className="font-medium">{Math.round(ocrProgressPct)}%</span>
                </div>
                <Progress value={ocrProgressPct} className="h-1.5" />
              </div>
            )}
            {documentsProcessed !== undefined && totalDocuments !== undefined && (
              <div className="col-span-2 text-center text-sm text-muted-foreground">
                {documentsProcessed} of {totalDocuments} documents processed
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
