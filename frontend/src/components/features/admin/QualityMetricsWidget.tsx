'use client';

import {
  AlertTriangle,
  RefreshCw,
  Activity,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Clock,
  Target,
  Calendar,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useQualityMetrics } from '@/hooks/useQualityMetrics';
import type { MatterQualityMetrics } from '@/lib/api/admin-monitoring';

/**
 * RAG Quality Metrics Widget
 *
 * Gap 9: Automated RAGAS Regression — Quality Monitoring Dashboard
 *
 * Displays RAG evaluation quality metrics for admin monitoring:
 * - Per-matter quality scores with baseline comparison
 * - Regression alerts (score drops > configured threshold)
 * - Evaluation schedule status and config
 * - Golden dataset coverage
 * - Last evaluation timing
 *
 * UX Layout:
 * +------------------------------------------+
 * |  RAG Quality Monitor         [Refresh]   |
 * |                                          |
 * |  Summary: 5 matters | 2 baselined | ...  |
 * |                                          |
 * |  Matter                  Score   Delta   |
 * |  Smith v Jones           0.85    +0.02   |
 * |    [Baseline: 0.83]  [4 golden items]    |
 * |  Doe v State [!REGRESS]  0.62    -0.15   |
 * |    [Baseline: 0.77]  [3 golden items]    |
 * |                                          |
 * |  Schedule: Enabled (nightly 1 AM UTC)    |
 * |  Budget: $10/mo | Thresholds: 10% / 0.6 |
 * +------------------------------------------+
 */

interface QualityMetricsWidgetProps {
  className?: string;
}

/** Format score as percentage */
function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '--';
  return (score * 100).toFixed(1) + '%';
}

/** Format delta with sign */
function formatDelta(delta: number | null): string {
  if (delta === null || delta === undefined) return '--';
  const sign = delta >= 0 ? '+' : '';
  return sign + (delta * 100).toFixed(1) + '%';
}

/** Format hours as human-readable age */
function formatAge(hours: number | null): string {
  if (hours === null || hours === undefined) return 'Never';
  if (hours < 1) return '<1h ago';
  if (hours < 24) return `${Math.round(hours)}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

/** Get color class based on score */
function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground';
  if (score >= 0.8) return 'text-green-600 dark:text-green-400';
  if (score >= 0.6) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

/** Get color class for delta */
function getDeltaColor(delta: number | null): string {
  if (delta === null) return 'text-muted-foreground';
  if (delta > 0.01) return 'text-green-600 dark:text-green-400';
  if (delta < -0.01) return 'text-red-600 dark:text-red-400';
  return 'text-muted-foreground';
}

/** Per-matter quality row */
function MatterQualityItem({ matter }: { matter: MatterQualityMetrics }) {
  const hasBaseline = matter.baselineOverall !== null;
  const hasEval = matter.latestOverall !== null;

  return (
    <div className={cn(
      'py-2 space-y-1',
      matter.hasRegression && 'bg-destructive/5 -mx-2 px-2 rounded'
    )}>
      {/* Main row: title, score, delta */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          {matter.hasRegression ? (
            <TrendingDown className="size-3 text-destructive shrink-0" />
          ) : hasEval && matter.latestOverall !== null && matter.latestOverall >= 0.8 ? (
            <CheckCircle2 className="size-3 text-green-600 dark:text-green-400 shrink-0" />
          ) : hasEval ? (
            <Activity className="size-3 text-muted-foreground shrink-0" />
          ) : (
            <Clock className="size-3 text-muted-foreground shrink-0" />
          )}
          <span className="font-medium truncate" title={matter.matterTitle}>
            {matter.matterTitle}
          </span>
          {matter.hasRegression && (
            <Badge variant="destructive" className="text-[9px] px-1 py-0 h-3.5">
              REGRESSED
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 ml-2 shrink-0">
          <span className={cn('font-mono font-medium', getScoreColor(matter.latestOverall))}>
            {formatScore(matter.latestOverall)}
          </span>
          {matter.overallDelta !== null && (
            <span className={cn('font-mono text-[10px]', getDeltaColor(matter.overallDelta))}>
              {matter.overallDelta > 0.01 && <TrendingUp className="size-2.5 inline mr-0.5" />}
              {matter.overallDelta < -0.01 && <TrendingDown className="size-2.5 inline mr-0.5" />}
              {formatDelta(matter.overallDelta)}
            </span>
          )}
        </div>
      </div>

      {/* Detail row: baseline, golden items, last eval */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground pl-5">
        {hasBaseline && (
          <span>
            <Target className="size-2.5 inline mr-0.5" />
            Baseline: {formatScore(matter.baselineOverall)}
          </span>
        )}
        {!hasBaseline && hasEval && (
          <span className="text-yellow-600 dark:text-yellow-400">No baseline</span>
        )}
        <span>{matter.goldenItemCount} golden items</span>
        {matter.lastEvalAgeHours !== null && (
          <span>
            <Calendar className="size-2.5 inline mr-0.5" />
            {formatAge(matter.lastEvalAgeHours)}
          </span>
        )}
        {matter.totalEvals30d > 0 && (
          <span>{matter.totalEvals30d} evals/30d</span>
        )}
      </div>
    </div>
  );
}

/** Loading skeleton */
function QualitySkeleton() {
  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-5 w-20" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
      <Skeleton className="h-4 w-48" />
    </div>
  );
}

export function QualityMetricsWidget({ className }: QualityMetricsWidgetProps) {
  const {
    metricsData,
    matters,
    hasRegressions,
    isLoading,
    error,
    lastUpdated,
    refresh,
  } = useQualityMetrics();

  const handleRefresh = async () => {
    await refresh();
  };

  const summary = metricsData?.summary;
  const schedule = metricsData?.schedule;

  return (
    <Card className={cn(className, hasRegressions && 'border-destructive')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="size-4" />
            RAG Quality Monitor
            {hasRegressions && (
              <AlertTriangle className="size-4 text-destructive animate-pulse" />
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={handleRefresh}
            disabled={isLoading}
            title="Refresh quality metrics"
          >
            <RefreshCw className={cn('size-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Loading state */}
        {isLoading && !metricsData && <QualitySkeleton />}

        {/* Error state */}
        {error && !isLoading && (
          <div className="text-center py-4">
            <p className="text-sm text-destructive mb-2" role="alert">
              Failed to load quality metrics
            </p>
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              Retry
            </Button>
          </div>
        )}

        {/* Metrics display */}
        {!isLoading && !error && metricsData && summary && (
          <>
            {/* Summary badges */}
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="text-[10px]">
                {summary.totalMatters} matters
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                {summary.mattersWithBaseline} baselined
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                {summary.totalGoldenItems} golden items
              </Badge>
              {summary.mattersWithRegression > 0 && (
                <Badge variant="destructive" className="text-[10px]">
                  {summary.mattersWithRegression} regressed
                </Badge>
              )}
              <Badge
                variant="outline"
                className={cn(
                  'text-[10px]',
                  summary.mattersEvaluatedRecently === summary.totalMatters
                    ? 'border-green-500/50'
                    : 'border-yellow-500/50'
                )}
              >
                {summary.mattersEvaluatedRecently} evaluated &lt;48h
              </Badge>
            </div>

            {/* Per-matter breakdown */}
            {matters.length > 0 ? (
              <div className="space-y-0.5 divide-y divide-border/50">
                {matters.map((matter) => (
                  <MatterQualityItem key={matter.matterId} matter={matter} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-3">
                No matters with golden datasets found.
                Add golden items to enable quality monitoring.
              </p>
            )}

            {/* Schedule & config info */}
            {schedule && (
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground bg-muted/50 rounded p-2">
                <span>
                  Schedule: {schedule.enabled ? (
                    <span className="text-green-600 dark:text-green-400 font-medium">Enabled (1 AM UTC)</span>
                  ) : (
                    <span className="text-yellow-600 dark:text-yellow-400">Disabled</span>
                  )}
                </span>
                <span>Budget: ${schedule.monthlyBudgetUsd}/mo</span>
                <span>Warning: {(schedule.regressionThreshold * 100).toFixed(0)}% drop</span>
                <span>Critical: {(schedule.criticalThreshold * 100).toFixed(0)}%</span>
              </div>
            )}

            {/* Last updated footer */}
            {lastUpdated && (
              <div className="text-[10px] text-muted-foreground text-center pt-2 border-t">
                Last updated: {new Date(lastUpdated).toLocaleTimeString('en-US', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!isLoading && !error && !metricsData && (
          <p className="text-sm text-muted-foreground text-center py-2">
            No quality metrics available
          </p>
        )}
      </CardContent>
    </Card>
  );
}
