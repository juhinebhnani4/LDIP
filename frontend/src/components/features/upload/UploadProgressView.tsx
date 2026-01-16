'use client';

/**
 * UploadProgressView Component
 *
 * Stage 3 of the upload wizard - displays file-by-file upload progress.
 * Shows individual progress bars for each file, checkmarks on completion,
 * error states, and overall upload progress.
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 */

import { useMemo } from 'react';
import { CheckCircle2, Loader2, XCircle, File, RefreshCw, SkipForward } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { formatFileSize } from '@/lib/utils/upload-validation';
import type { UploadProgress } from '@/types/upload';

interface UploadProgressViewProps {
  /** Array of file upload progress */
  uploadProgress: UploadProgress[];
  /** Total number of files to upload */
  totalFiles: number;
  /** Optional className */
  className?: string;
  /** Callback when user clicks retry on a failed file */
  onRetryFile?: (fileName: string) => void;
  /** Callback when user clicks skip on a failed file */
  onSkipFile?: (fileName: string) => void;
}

/** Status icon component for file upload state */
function StatusIcon({ status }: { status: UploadProgress['status'] }) {
  switch (status) {
    case 'complete':
      return (
        <CheckCircle2
          className="size-5 text-green-600 flex-shrink-0"
          aria-label="Upload complete"
        />
      );
    case 'error':
      return (
        <XCircle
          className="size-5 text-destructive flex-shrink-0"
          aria-label="Upload failed"
        />
      );
    case 'uploading':
      return (
        <Loader2
          className="size-5 text-primary flex-shrink-0 animate-spin"
          aria-label="Uploading"
        />
      );
    case 'pending':
    default:
      return (
        <File
          className="size-5 text-muted-foreground flex-shrink-0"
          aria-label="Pending upload"
        />
      );
  }
}

interface FileProgressItemProps {
  progress: UploadProgress;
  onRetry?: (fileName: string) => void;
  onSkip?: (fileName: string) => void;
}

/** Individual file progress item */
function FileProgressItem({ progress, onRetry, onSkip }: FileProgressItemProps) {
  const isComplete = progress.status === 'complete';
  const isError = progress.status === 'error';
  const isUploading = progress.status === 'uploading';

  return (
    <li
      className={cn(
        'flex flex-col gap-2 py-3 px-3 rounded-md transition-colors',
        isError && 'bg-destructive/5',
        isComplete && 'bg-green-50 dark:bg-green-950/20'
      )}
      aria-describedby={isError ? `error-${progress.fileName}` : undefined}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <StatusIcon status={progress.status} />
          <span
            className={cn(
              'truncate text-sm font-medium',
              isComplete && 'text-green-700 dark:text-green-400',
              isError && 'text-destructive'
            )}
            title={progress.fileName}
          >
            {progress.fileName}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {formatFileSize(progress.fileSize)}
          </span>
          {isUploading && (
            <span className="text-sm font-medium text-primary min-w-[3ch]">
              {Math.round(progress.progressPct)}%
            </span>
          )}
          {/* Story 13.4: Retry and Skip buttons for failed files */}
          {isError && (
            <div className="flex items-center gap-1">
              {onRetry && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onRetry(progress.fileName)}
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        aria-label={`Retry upload for ${progress.fileName}`}
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Retry Processing</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
              {onSkip && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onSkip(progress.fileName)}
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        aria-label={`Skip ${progress.fileName}`}
                      >
                        <SkipForward className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Skip Document</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Individual file progress bar */}
      {isUploading && (
        <Progress
          value={progress.progressPct}
          className="h-1.5"
          aria-label={`Upload progress for ${progress.fileName}`}
        />
      )}

      {/* Error message with truncation and expand on hover */}
      {isError && progress.errorMessage && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <p
                id={`error-${progress.fileName}`}
                className="text-sm text-destructive ml-8 truncate cursor-help max-w-[300px]"
              >
                {progress.errorMessage}
              </p>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-[400px]">
              <p className="text-sm">{progress.errorMessage}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </li>
  );
}

export function UploadProgressView({
  uploadProgress,
  totalFiles,
  className,
  onRetryFile,
  onSkipFile,
}: UploadProgressViewProps) {
  // Calculate overall progress
  const { completedCount, overallProgressPct } = useMemo(() => {
    if (uploadProgress.length === 0) {
      return { completedCount: 0, overallProgressPct: 0 };
    }

    let completed = 0;
    let totalProgress = 0;

    for (const progress of uploadProgress) {
      if (progress.status === 'complete') {
        completed++;
        totalProgress += 100;
      } else if (progress.status === 'uploading') {
        totalProgress += progress.progressPct;
      }
      // pending and error files contribute 0 to progress
    }

    const overall = totalFiles > 0 ? totalProgress / totalFiles : 0;
    return { completedCount: completed, overallProgressPct: overall };
  }, [uploadProgress, totalFiles]);

  const hasErrors = uploadProgress.some((p) => p.status === 'error');
  const allComplete =
    completedCount === totalFiles &&
    totalFiles > 0 &&
    !hasErrors;

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">
          <div className="flex items-center justify-between">
            <span>Uploading Files</span>
            <span className="text-sm font-normal text-muted-foreground">
              {completedCount} of {totalFiles} uploaded
            </span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Overall progress bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Overall Progress</span>
            <span className={cn('font-medium', allComplete && 'text-green-600')}>
              {Math.round(overallProgressPct)}%
            </span>
          </div>
          <Progress
            value={overallProgressPct}
            className={cn('h-2', allComplete && '[&>div]:bg-green-600')}
            role="progressbar"
            aria-valuenow={Math.round(overallProgressPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Overall upload progress"
          />
        </div>

        {/* File list */}
        <ul
          className="max-h-[300px] overflow-y-auto divide-y divide-border -mx-3"
          role="list"
          aria-label="Files being uploaded"
          aria-live="polite"
        >
          {uploadProgress.map((progress) => (
            <FileProgressItem
              key={progress.fileName}
              progress={progress}
              onRetry={onRetryFile}
              onSkip={onSkipFile}
            />
          ))}
        </ul>

        {/* Success message */}
        {allComplete && (
          <div className="flex items-center gap-2 text-green-600 text-sm font-medium">
            <CheckCircle2 className="size-4" />
            All files uploaded successfully
          </div>
        )}

        {/* Error summary */}
        {hasErrors && (
          <div className="flex items-center gap-2 text-destructive text-sm">
            <XCircle className="size-4" />
            Some files failed to upload. You can retry or continue without them.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
