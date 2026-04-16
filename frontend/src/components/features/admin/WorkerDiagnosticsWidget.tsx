'use client';

import {
  AlertTriangle,
  Clock,
  Cpu,
  RefreshCw,
  Timer,
  XCircle,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useWorkerDiagnostics } from '@/hooks/useWorkerDiagnostics';

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return 'Unknown';
  }
}

function shortTaskName(fullName: string): string {
  // "app.workers.tasks.document_tasks.resolve_aliases" → "resolve_aliases"
  const parts = fullName.split('.');
  return parts[parts.length - 1] || fullName;
}

function ActiveTasksSection({
  workerInfo,
}: {
  workerInfo: NonNullable<ReturnType<typeof useWorkerDiagnostics>['workerInfo']>;
}) {
  const { workerCount, activeTasks } = workerInfo;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Cpu className="size-4 text-primary" />
        Worker Now
        <Badge variant="outline" className="text-xs">
          {workerCount} worker{workerCount !== 1 ? 's' : ''}
        </Badge>
      </div>
      {activeTasks.length === 0 ? (
        <p className="text-xs text-muted-foreground pl-6">No tasks running (idle)</p>
      ) : (
        <div className="space-y-1 pl-6">
          {activeTasks.map((task) => (
            <div
              key={task.taskId}
              className={cn(
                'flex items-center justify-between text-xs p-1.5 rounded',
                task.runtimeSeconds > 600
                  ? 'bg-destructive/10 text-destructive'
                  : task.runtimeSeconds > 120
                    ? 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400'
                    : 'bg-muted'
              )}
            >
              <span className="font-mono truncate max-w-[200px]">
                {shortTaskName(task.taskName)}
              </span>
              <span className="font-medium whitespace-nowrap ml-2">
                {formatDuration(task.runtimeSeconds)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function WaitingJobsSection({
  jobsOverview,
}: {
  jobsOverview: NonNullable<ReturnType<typeof useWorkerDiagnostics>['jobsOverview']>;
}) {
  const { jobs, queuedCount, processingCount } = jobsOverview;
  const queuedJobs = jobs.filter((j) => j.status === 'QUEUED' || j.status === 'PROCESSING');
  const displayJobs = queuedJobs.slice(0, 8);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Clock className="size-4 text-primary" />
        Queue
        <Badge variant="secondary" className="text-xs">
          {queuedCount} queued
        </Badge>
        <Badge variant="outline" className="text-xs">
          {processingCount} processing
        </Badge>
      </div>
      {displayJobs.length === 0 ? (
        <p className="text-xs text-muted-foreground pl-6">No jobs waiting</p>
      ) : (
        <div className="space-y-1 pl-6">
          {displayJobs.map((job) => (
            <div
              key={job.jobId}
              className="flex items-center justify-between text-xs bg-muted p-1.5 rounded"
            >
              <div className="flex items-center gap-1.5 truncate">
                <Badge
                  variant={job.status === 'QUEUED' ? 'secondary' : 'default'}
                  className="text-[10px] px-1 py-0"
                >
                  {job.status}
                </Badge>
                <span className="font-mono truncate max-w-[120px]">
                  {job.jobType}
                </span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground whitespace-nowrap">
                {job.queueWaitSeconds != null && (
                  <span>wait: {formatDuration(job.queueWaitSeconds)}</span>
                )}
                <span className="font-mono text-[10px]">
                  {job.matterId.slice(0, 6)}
                </span>
              </div>
            </div>
          ))}
          {queuedJobs.length > 8 && (
            <p className="text-xs text-muted-foreground text-center">
              +{queuedJobs.length - 8} more
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function BottleneckSection({
  bottleneckStats,
}: {
  bottleneckStats: NonNullable<ReturnType<typeof useWorkerDiagnostics>['bottleneckStats']>;
}) {
  const { stages } = bottleneckStats;
  if (stages.length === 0) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Timer className="size-4 text-primary" />
          Stage Bottlenecks (24h)
        </div>
        <p className="text-xs text-muted-foreground pl-6">No stage data yet</p>
      </div>
    );
  }

  const maxAvg = Math.max(...stages.map((s) => s.avgDurationSeconds), 1);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Timer className="size-4 text-primary" />
        Stage Bottlenecks (24h)
      </div>
      <div className="space-y-1.5 pl-6">
        {stages.slice(0, 8).map((stage) => {
          const pct = Math.min((stage.avgDurationSeconds / maxAvg) * 100, 100);
          const isSlow = stage.avgDurationSeconds > 300; // >5 min is slow

          return (
            <div key={stage.stageName} className="space-y-0.5">
              <div className="flex items-center justify-between text-xs">
                <span className={cn('font-mono', isSlow && 'text-destructive font-medium')}>
                  {stage.stageName}
                </span>
                <span className="text-muted-foreground">
                  avg {formatDuration(stage.avgDurationSeconds)}
                  {' / '}
                  max {formatDuration(stage.maxDurationSeconds)}
                  {' '}
                  ({stage.totalRuns} runs
                  {stage.failedRuns > 0 && (
                    <span className="text-destructive">, {stage.failedRuns} failed</span>
                  )}
                  )
                </span>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    isSlow ? 'bg-destructive' : 'bg-primary'
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ErrorsSection({
  errorPatterns,
}: {
  errorPatterns: NonNullable<ReturnType<typeof useWorkerDiagnostics>['errorPatterns']>;
}) {
  const { patterns, totalErrors } = errorPatterns;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <XCircle className="size-4 text-destructive" />
        Error Patterns (24h)
        {totalErrors > 0 && (
          <Badge variant="destructive" className="text-xs">
            {totalErrors} total
          </Badge>
        )}
      </div>
      {patterns.length === 0 ? (
        <p className="text-xs text-muted-foreground pl-6">No errors in last 24h</p>
      ) : (
        <div className="space-y-1 pl-6">
          {patterns.slice(0, 5).map((pattern, i) => (
            <div
              key={i}
              className="flex items-start justify-between text-xs bg-destructive/5 p-1.5 rounded gap-2"
            >
              <div className="truncate">
                <span className="font-mono text-destructive">{pattern.stageName}</span>
                <span className="text-muted-foreground ml-1 truncate">
                  {pattern.errorMessage.slice(0, 80)}
                  {pattern.errorMessage.length > 80 && '...'}
                </span>
              </div>
              <Badge variant="outline" className="text-[10px] shrink-0">
                x{pattern.count}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkerDiagnosticsWidget({ className }: { className?: string }) {
  const {
    workerInfo,
    jobsOverview,
    bottleneckStats,
    errorPatterns,
    isLoading,
    error,
    lastFetchedAt,
    refresh,
  } = useWorkerDiagnostics();

  const hasData = workerInfo || jobsOverview || bottleneckStats || errorPatterns;

  // Detect starvation signals
  const longestTask = workerInfo?.activeTasks?.[0];
  const isStarving = longestTask && longestTask.runtimeSeconds > 600; // >10 min
  const hasQueuedJobs = (jobsOverview?.queuedCount ?? 0) > 0;
  const showAlert = isStarving && hasQueuedJobs;

  return (
    <Card className={cn(className, showAlert && 'border-destructive')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            Worker Diagnostics
            {showAlert && (
              <Badge variant="destructive" className="text-xs gap-1 animate-pulse">
                <AlertTriangle className="size-3" />
                STARVATION
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={() => refresh()}
            disabled={isLoading}
            title="Refresh diagnostics"
          >
            <RefreshCw className={cn('size-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Loading state */}
        {isLoading && !hasData && (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && !hasData && (
          <div className="text-center py-4">
            <p className="text-sm text-destructive mb-2">Failed to load diagnostics</p>
            <Button variant="outline" size="sm" onClick={() => refresh()}>
              Retry
            </Button>
          </div>
        )}

        {/* Data */}
        {hasData && (
          <>
            {workerInfo && <ActiveTasksSection workerInfo={workerInfo} />}

            <div className="border-t" />

            {jobsOverview && <WaitingJobsSection jobsOverview={jobsOverview} />}

            <div className="border-t" />

            {bottleneckStats && <BottleneckSection bottleneckStats={bottleneckStats} />}

            <div className="border-t" />

            {errorPatterns && <ErrorsSection errorPatterns={errorPatterns} />}

            {/* Footer */}
            {lastFetchedAt && (
              <div className="text-xs text-muted-foreground text-center pt-2 border-t">
                Last updated: {formatTime(lastFetchedAt)} (auto-refresh 10s)
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
