'use client';

import { useState, useEffect, useCallback } from 'react';
import { Clock, RefreshCw, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { jobsApi } from '@/lib/api/jobs';
import type { JobQueueStats, ETAEstimate } from '@/types/job';

/**
 * Processing Status Widget
 *
 * Story 5.7: Processing ETA Display
 *
 * Displays document processing status with ETA estimate for a matter.
 * Features:
 * - Processing progress bar (completed / total)
 * - ETA estimate with confidence range
 * - Worker count display
 * - Auto-refresh every 10 seconds when active
 *
 * UX Layout:
 * ┌────────────────────────────────────────┐
 * │  Processing Status          [Refresh]  │
 * │                                         │
 * │  ████████████░░░░░░░░  25/50  50%      │
 * │                                         │
 * │  ⏱ Estimated: 2-5 minutes              │
 * │  Confidence: high                       │
 * │  Pages remaining: 125                   │
 * │                                         │
 * │  ✓ 25 completed  ⏳ 3 processing       │
 * │  ✗ 2 failed     ⏸ 20 queued            │
 * └────────────────────────────────────────┘
 */

interface ProcessingStatusWidgetProps {
  /** Matter ID to fetch stats for */
  matterId: string;
  /** Optional className for styling */
  className?: string;
  /** Show compact view (less detail) */
  compact?: boolean;
  /** Auto-refresh interval in ms (0 to disable) */
  refreshInterval?: number;
  /** Callback when processing is complete */
  onComplete?: () => void;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} seconds`;
  }
  if (seconds < 3600) {
    const mins = Math.round(seconds / 60);
    return `${mins} minute${mins !== 1 ? 's' : ''}`;
  }
  const hours = Math.floor(seconds / 3600);
  const mins = Math.round((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function formatETARange(eta: ETAEstimate): string {
  if (eta.minSeconds === eta.maxSeconds) {
    return formatDuration(eta.bestGuessSeconds);
  }
  const min = formatDuration(eta.minSeconds);
  const max = formatDuration(eta.maxSeconds);
  return `${min} - ${max}`;
}

function getConfidenceBadge(confidence: string) {
  switch (confidence) {
    case 'high':
      return <Badge variant="default" className="text-xs">High confidence</Badge>;
    case 'medium':
      return <Badge variant="secondary" className="text-xs">Medium confidence</Badge>;
    default:
      return <Badge variant="outline" className="text-xs">Low confidence</Badge>;
  }
}

function getProgressColor(completed: number, total: number): React.CSSProperties {
  const pct = total > 0 ? (completed / total) * 100 : 0;
  if (pct >= 100) return { backgroundColor: 'hsl(var(--success, 142 76% 36%))' };
  if (pct >= 50) return { backgroundColor: 'hsl(var(--primary))' };
  return { backgroundColor: 'hsl(var(--muted-foreground))' };
}

export function ProcessingStatusWidget({
  matterId,
  className,
  compact = false,
  refreshInterval = 10000,
  onComplete,
}: ProcessingStatusWidgetProps) {
  const [stats, setStats] = useState<JobQueueStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const data = await jobsApi.getStats(matterId);
      setStats(data);
      setError(null);

      // Check if processing is complete
      const pending = data.queued + data.processing;
      if (pending === 0 && data.completed > 0 && onComplete) {
        onComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch stats'));
    } finally {
      setIsLoading(false);
    }
  }, [matterId, onComplete]);

  // Initial fetch
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Auto-refresh when there are pending jobs
  useEffect(() => {
    if (refreshInterval === 0) return;
    if (!stats) return;

    const pending = stats.queued + stats.processing;
    if (pending === 0) return;

    const intervalId = setInterval(fetchStats, refreshInterval);
    return () => clearInterval(intervalId);
  }, [stats, refreshInterval, fetchStats]);

  const handleRefresh = async () => {
    setIsLoading(true);
    await fetchStats();
  };

  // Calculate derived values
  const total = stats
    ? stats.queued + stats.processing + stats.completed + stats.failed + stats.skipped
    : 0;
  const completed = stats?.completed ?? 0;
  const pending = stats ? stats.queued + stats.processing : 0;
  const progressPct = total > 0 ? (completed / total) * 100 : 0;
  const isComplete = pending === 0 && completed > 0;

  // Loading state
  if (isLoading && !stats) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="size-8 rounded-md" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-2 w-full" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-36" />
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error && !stats) {
    return (
      <Card className={cn(className, 'border-destructive')}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertCircle className="size-4 text-destructive" />
            Processing Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive mb-2">Failed to load status</p>
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(className, isComplete && 'border-[var(--success)]')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            {isComplete ? (
              <>
                <CheckCircle2 className="size-4 text-[var(--success)]" />
                Processing Complete
              </>
            ) : (
              <>
                <Loader2 className="size-4 animate-spin text-primary" />
                Processing Documents
              </>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={handleRefresh}
            disabled={isLoading}
            title="Refresh status"
          >
            <RefreshCw className={cn('size-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span>{completed} of {total} documents</span>
            <span>{progressPct.toFixed(0)}%</span>
          </div>
          <Progress
            value={progressPct}
            className="h-2"
            indicatorStyle={getProgressColor(completed, total)}
          />
        </div>

        {/* ETA display */}
        {!isComplete && stats?.eta && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Clock className="size-4 text-muted-foreground" />
              <span>
                Estimated: <strong>{formatETARange(stats.eta)}</strong>
              </span>
            </div>
            {!compact && (
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{stats.eta.pendingPages} pages remaining</span>
                {getConfidenceBadge(stats.eta.confidence)}
              </div>
            )}
          </div>
        )}

        {/* Detailed stats (non-compact mode) */}
        {!compact && (
          <div className="grid grid-cols-2 gap-2 text-sm pt-2 border-t">
            <div className="flex items-center gap-2">
              <span className="text-[var(--success)]">✓</span>
              <span>{stats?.completed ?? 0} completed</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">⏳</span>
              <span>{stats?.processing ?? 0} processing</span>
            </div>
            {(stats?.failed ?? 0) > 0 && (
              <div className="flex items-center gap-2 text-destructive">
                <span>✗</span>
                <span>{stats?.failed} failed</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">⏸</span>
              <span>{stats?.queued ?? 0} queued</span>
            </div>
          </div>
        )}

        {/* Complete message */}
        {isComplete && (
          <div className="text-sm text-[var(--success)] text-center pt-2">
            All documents processed successfully!
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Compact inline processing indicator
 *
 * For use in headers or small spaces.
 */
export function ProcessingStatusBadge({ matterId }: { matterId: string }) {
  const [stats, setStats] = useState<JobQueueStats | null>(null);

  useEffect(() => {
    jobsApi.getStats(matterId).then(setStats).catch(() => {});
  }, [matterId]);

  if (!stats) return null;

  const pending = stats.queued + stats.processing;
  if (pending === 0) return null;

  return (
    <Badge variant="secondary" className="gap-1.5">
      <Loader2 className="size-3 animate-spin" />
      {pending} processing
      {stats.eta && (
        <span className="text-muted-foreground">
          ~ {formatDuration(stats.eta.bestGuessSeconds)}
        </span>
      )}
    </Badge>
  );
}
