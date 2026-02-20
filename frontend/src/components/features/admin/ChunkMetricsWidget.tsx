'use client';

import {
  AlertTriangle,
  RefreshCw,
  Database,
  HardDrive,
  Cpu,
  Info,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useChunkMetrics } from '@/hooks/useChunkMetrics';
import type { MatterChunkMetrics, IndexConfig } from '@/lib/api/admin-monitoring';

/**
 * Chunk Metrics Widget Component
 *
 * Gap 7: Vector Quantization — Chunk Count Monitoring Dashboard
 *
 * Displays chunk count metrics for monitoring when to consider
 * vector quantization. Features:
 * - Global chunk count with threshold progress bar
 * - Per-matter breakdown (top matters by chunk count)
 * - HNSW index configuration display
 * - Quantization recommendation
 * - Alert when thresholds exceeded
 * - 2-minute polling with visibility detection
 *
 * UX Layout:
 * +----------------------------------------+
 * |  Vector Index Health        [Refresh]  |
 * |                                        |
 * |  Global: 15,000 / 500,000  (3%)       |
 * |  ██░░░░░░░░░░░░░░░░░░░░░░░░░░  3%    |
 * |                                        |
 * |  HNSW Config                           |
 * |  m=16  ef_build=128  ef_search=80     |
 * |  Quantization: float32                 |
 * |                                        |
 * |  Top Matters          Chunks           |
 * |  Smith v Jones        5,000            |
 * |    parent: 800 | child: 4,000 | ...   |
 * |  Doe v State          3,200            |
 * |                                        |
 * |  Recommendation: No action needed      |
 * +----------------------------------------+
 */

interface ChunkMetricsWidgetProps {
  className?: string;
}

/** Format large numbers with commas */
function formatNumber(num: number): string {
  return num.toLocaleString('en-IN');
}

/** Get progress bar color based on usage percentage */
function getUsageIndicatorStyle(pct: number): React.CSSProperties {
  if (pct >= 80) return { backgroundColor: 'hsl(var(--destructive))' };
  if (pct >= 50) return { backgroundColor: 'hsl(var(--warning, 38 92% 50%))' };
  return { backgroundColor: 'hsl(var(--primary))' };
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

/** HNSW configuration display */
function IndexConfigDisplay({ config }: { config: IndexConfig }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Cpu className="size-3" />
        HNSW Index Config
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-muted/50 rounded px-2 py-1 text-center">
          <div className="font-mono font-medium">m={config.m}</div>
          <div className="text-muted-foreground text-[10px]">connections</div>
        </div>
        <div className="bg-muted/50 rounded px-2 py-1 text-center">
          <div className="font-mono font-medium">ef_c={config.efConstruction}</div>
          <div className="text-muted-foreground text-[10px]">build quality</div>
        </div>
        <div className="bg-muted/50 rounded px-2 py-1 text-center">
          <div className="font-mono font-medium">ef_s={config.efSearch}</div>
          <div className="text-muted-foreground text-[10px]">query recall</div>
        </div>
      </div>
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <HardDrive className="size-3" />
        <span>{config.quantization}</span>
        <span className="text-muted-foreground/60">|</span>
        <span>OpenAI {config.vectorDimensions.openai}d</span>
        <span className="text-muted-foreground/60">|</span>
        <span>Voyage {config.vectorDimensions.voyage}d</span>
      </div>
    </div>
  );
}

/** Single matter chunk metrics row */
function MatterMetricsItem({ matter }: { matter: MatterChunkMetrics }) {
  return (
    <div className={cn(
      'flex items-start justify-between py-1.5 text-xs',
      matter.exceedsThreshold && 'text-destructive'
    )}>
      <div className="min-w-0 flex-1">
        <div className="font-medium truncate" title={matter.matterTitle}>
          {matter.matterTitle}
        </div>
        <div className="text-muted-foreground text-[10px]">
          {formatNumber(matter.parentChunks)} parent
          {' | '}{formatNumber(matter.childChunks)} child
          {matter.tableChunks > 0 && <>{' | '}{formatNumber(matter.tableChunks)} table</>}
        </div>
      </div>
      <div className="flex items-center gap-1 ml-2 shrink-0">
        <span className="font-mono font-medium">{formatNumber(matter.totalChunks)}</span>
        {matter.exceedsThreshold && (
          <AlertTriangle className="size-3 text-destructive" />
        )}
      </div>
    </div>
  );
}

/** Loading skeleton */
function MetricsSkeleton() {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-2 w-full" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Skeleton className="h-10 w-full rounded" />
        <Skeleton className="h-10 w-full rounded" />
        <Skeleton className="h-10 w-full rounded" />
      </div>
      <Skeleton className="h-3 w-48" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    </div>
  );
}

export function ChunkMetricsWidget({ className }: ChunkMetricsWidgetProps) {
  const {
    metricsData,
    matters,
    globalTotal,
    hasAlerts,
    isLoading,
    error,
    lastUpdated,
    refresh,
  } = useChunkMetrics();

  const handleRefresh = async () => {
    await refresh();
  };

  const globalThreshold = metricsData?.thresholds.global ?? 500_000;
  const globalPct = globalThreshold > 0
    ? Math.min((globalTotal / globalThreshold) * 100, 100)
    : 0;

  // Show top 5 matters by chunk count
  const topMatters = matters.slice(0, 5);

  return (
    <Card className={cn(className, hasAlerts && 'border-destructive')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Database className="size-4" />
            Vector Index Health
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
            title="Refresh chunk metrics"
          >
            <RefreshCw className={cn('size-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Loading state */}
        {isLoading && !metricsData && <MetricsSkeleton />}

        {/* Error state */}
        {error && !isLoading && (
          <div className="text-center py-4">
            <p className="text-sm text-destructive mb-2" role="alert">
              Failed to load chunk metrics
            </p>
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              Retry
            </Button>
          </div>
        )}

        {/* Metrics display */}
        {!isLoading && !error && metricsData && (
          <>
            {/* Global progress */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  Global chunks
                </span>
                <span className="font-mono">
                  {formatNumber(globalTotal)} / {formatNumber(globalThreshold)}
                  {' '}({globalPct.toFixed(1)}%)
                </span>
              </div>
              <Progress
                value={globalPct}
                className="h-2"
                indicatorStyle={getUsageIndicatorStyle(globalPct)}
              />
              <div className="flex gap-3 text-[10px] text-muted-foreground">
                <span>{formatNumber(metricsData.global.totalWithEmbedding)} embedded</span>
                <span>{formatNumber(metricsData.global.totalWithVoyage)} Voyage</span>
                <span>{metricsData.global.totalMatters} matters</span>
              </div>
            </div>

            {/* HNSW Index Config */}
            <IndexConfigDisplay config={metricsData.indexConfig} />

            {/* Per-matter breakdown */}
            {topMatters.length > 0 && (
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="font-medium">Top Matters</span>
                  <span>Chunks</span>
                </div>
                <div className="divide-y divide-border/50">
                  {topMatters.map((matter) => (
                    <MatterMetricsItem
                      key={matter.matterId}
                      matter={matter}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Recommendation */}
            <div className={cn(
              'flex items-start gap-2 text-xs p-2 rounded',
              hasAlerts
                ? 'bg-destructive/10 text-destructive'
                : 'bg-muted/50 text-muted-foreground'
            )}>
              <Info className="size-3 mt-0.5 shrink-0" />
              <span>{metricsData.indexConfig.recommendation}</span>
            </div>

            {/* Threshold badges */}
            <div className="flex gap-2 text-[10px]">
              <Badge variant="outline" className="text-[10px]">
                Per-matter: {formatNumber(metricsData.thresholds.perMatter)}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                Global: {formatNumber(metricsData.thresholds.global)}
              </Badge>
            </div>

            {/* Last updated footer */}
            {lastUpdated && (
              <div className="text-xs text-muted-foreground text-center pt-2 border-t">
                Last updated: {formatTime(lastUpdated)}
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!isLoading && !error && !metricsData && (
          <p className="text-sm text-muted-foreground text-center py-2">
            No chunk metrics available
          </p>
        )}
      </CardContent>
    </Card>
  );
}
