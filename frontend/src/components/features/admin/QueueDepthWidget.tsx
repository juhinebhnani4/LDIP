'use client';

import {
  AlertTriangle,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Minus,
  Clock,
  Layers,
  Users,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useQueueStatus } from '@/hooks/useQueueStatus';
import type { QueueMetrics, QueueTrend } from '@/lib/api/admin-queue';

/**
 * Queue Depth Widget Component
 *
 * Story 5.6: Queue Depth Visibility Dashboard
 *
 * Displays Celery queue depths and metrics for admin monitoring.
 * Features:
 * - Progress bars for each queue (color-coded by usage level)
 * - Pending and active job counts
 * - Worker count display
 * - Alert indicator when queue exceeds threshold
 * - Staleness warning if data older than 60 seconds
 * - 30s polling with visibility detection
 *
 * UX Layout:
 * ┌────────────────────────────────────────┐
 * │  Queue Status              [Refresh]   │
 * │  Workers: 3                            │
 * │                                        │
 * │  default                    [stable]   │
 * │  ████████████░░░░░░░░  25/100  25%     │
 * │  5 active                              │
 * │                                        │
 * │  high                     [decreasing] │
 * │  ██░░░░░░░░░░░░░░░░░░  5/100   5%      │
 * │  2 active                              │
 * │                                        │
 * │  low                       [ALERT!]    │
 * │  ████████████████████  100/100 100%    │
 * │  1 active                              │
 * │                                        │
 * │  Last checked: 10:30 AM               │
 * └────────────────────────────────────────┘
 */

interface QueueDepthWidgetProps {
  /** Optional className for styling */
  className?: string;
}

/**
 * Get progress bar indicator color based on usage percentage.
 *
 * Returns a CSS style object since shadcn Progress doesn't support
 * className on the indicator element directly.
 */
function getUsageIndicatorStyle(pct: number): React.CSSProperties {
  if (pct >= 90) return { backgroundColor: 'hsl(var(--destructive))' };
  if (pct >= 70) return { backgroundColor: 'hsl(var(--warning, 38 92% 50%))' };
  return { backgroundColor: 'hsl(var(--primary))' };
}

/** Get trend icon based on trend direction */
function TrendIcon({ trend }: { trend: QueueTrend }) {
  switch (trend) {
    case 'increasing':
      return <TrendingUp className="size-3 text-destructive" />;
    case 'decreasing':
      return <TrendingDown className="size-3 text-[var(--success)]" />;
    default:
      return <Minus className="size-3 text-muted-foreground" />;
  }
}

/** Format timestamp to time only */
function formatTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return 'Unknown';
  }
}

/** Single queue metrics display */
function QueueMetricsItem({
  queue,
  alertThreshold,
}: {
  queue: QueueMetrics;
  alertThreshold: number;
}) {
  const usagePct = alertThreshold > 0
    ? Math.min((queue.pendingCount / alertThreshold) * 100, 100)
    : 0;

  return (
    <div className="space-y-2">
      {/* Queue header with alert badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className={cn('size-4', queue.alertTriggered ? 'text-destructive' : 'text-primary')} />
          <span className="font-medium">{queue.queueName}</span>
        </div>
        {queue.alertTriggered ? (
          <Badge variant="destructive" className="text-xs gap-1">
            <AlertTriangle className="size-3" />
            ALERT
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-xs gap-1">
            <TrendIcon trend={queue.trend} />
            {queue.trend}
          </Badge>
        )}
      </div>

      {/* Queue depth progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Pending</span>
          <span>
            {queue.pendingCount}
            {alertThreshold > 0 && `/${alertThreshold}`}
            {' '}
            ({usagePct.toFixed(0)}%)
          </span>
        </div>
        <Progress
          value={usagePct}
          className="h-2"
          indicatorStyle={getUsageIndicatorStyle(usagePct)}
        />
      </div>

      {/* Active jobs info */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1 text-muted-foreground">
          <Clock className="size-3" />
          <span>{queue.activeCount} active</span>
        </div>
        {queue.failedCount > 0 && (
          <span className="text-destructive">
            {queue.failedCount} failed (24h)
          </span>
        )}
      </div>
    </div>
  );
}

/** Loading skeleton for a single queue */
function QueueMetricsSkeleton() {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-5 w-16" />
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-12" />
          <Skeleton className="h-3 w-20" />
        </div>
        <Skeleton className="h-2 w-full" />
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

export function QueueDepthWidget({ className }: QueueDepthWidgetProps) {
  const {
    statusData,
    queues,
    activeWorkers,
    hasAlerts,
    isHealthy,
    isLoading,
    error,
    lastCheckedAt,
    isStale,
    refresh,
  } = useQueueStatus();

  const handleRefresh = async () => {
    await refresh();
  };

  const alertThreshold = statusData?.alertThreshold ?? 100;

  return (
    <Card className={cn(className, hasAlerts && 'border-destructive')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            Queue Status
            {hasAlerts && (
              <AlertTriangle className="size-4 text-destructive animate-pulse" />
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={handleRefresh}
            disabled={isLoading}
            title="Refresh queue status"
          >
            <RefreshCw className={cn('size-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
        {/* Worker count summary */}
        {statusData && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Users className="size-4" />
            <span>{activeWorkers} active worker{activeWorkers !== 1 ? 's' : ''}</span>
            {!isHealthy && (
              <Badge variant="outline" className="text-xs text-[var(--warning)]">
                Degraded
              </Badge>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Loading state */}
        {isLoading && !statusData && (
          <>
            <QueueMetricsSkeleton />
            <QueueMetricsSkeleton />
            <QueueMetricsSkeleton />
          </>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="text-center py-4">
            <p className="text-sm text-destructive mb-2" role="alert">
              Failed to load queue status
            </p>
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              Retry
            </Button>
          </div>
        )}

        {/* Queue display */}
        {!isLoading && !error && statusData && (
          <>
            {queues.map((queue) => (
              <QueueMetricsItem
                key={queue.queueName}
                queue={queue}
                alertThreshold={alertThreshold}
              />
            ))}

            {/* Last checked footer with staleness warning */}
            {lastCheckedAt && (
              <div className={cn(
                'text-xs text-center pt-2 border-t',
                isStale ? 'text-[var(--warning)]' : 'text-muted-foreground'
              )}>
                {isStale && (
                  <span className="flex items-center justify-center gap-1 mb-1">
                    <AlertTriangle className="size-3" />
                    Data may be stale
                  </span>
                )}
                Last checked: {formatTime(lastCheckedAt)}
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!isLoading && !error && queues.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-2">
            No queue data available
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Queue Depth Widget Skeleton
 *
 * Loading placeholder for the entire widget.
 */
export function QueueDepthWidgetSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-28" />
          <Skeleton className="size-8 rounded-md" />
        </div>
        <Skeleton className="h-4 w-24" />
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        <QueueMetricsSkeleton />
        <QueueMetricsSkeleton />
        <QueueMetricsSkeleton />
      </CardContent>
    </Card>
  );
}
