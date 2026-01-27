'use client';

import { AlertTriangle, RefreshCw, TrendingDown, TrendingUp, Minus, Zap, DollarSign } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useLLMQuota } from '@/hooks/useLLMQuota';
import type { ProviderQuota, QuotaTrend } from '@/lib/api/admin-quota';

/**
 * LLM Quota Widget Component
 *
 * Story gap-5.2: LLM Quota Monitoring Dashboard
 *
 * Displays LLM API usage vs limits for OpenAI and Gemini.
 * Features:
 * - Progress bars for each provider (color-coded by usage level)
 * - Cost display in INR with USD equivalent
 * - Projected exhaustion date with trend indicator
 * - 80% threshold warning styling
 * - 60s polling with visibility detection
 *
 * UX Layout:
 * ┌────────────────────────────────────────┐
 * │  LLM Quota Status          [Refresh]  │
 * │                                        │
 * │  Gemini                     [stable]  │
 * │  ████████████░░░░░░░░  500K/1M  50%   │
 * │  ₹250.50 (~$3.00)                     │
 * │  Projected: Feb 15 ↗                  │
 * │                                        │
 * │  OpenAI                    [ALERT!]   │
 * │  ████████████████████  450K/500K 90%  │
 * │  ₹2,100.00 (~$25.00)                  │
 * │  Projected: Today ↑                   │
 * │                                        │
 * │  Last updated: 10:30 AM               │
 * └────────────────────────────────────────┘
 */

interface LLMQuotaWidgetProps {
  /** Optional className for styling */
  className?: string;
}

/**
 * F9 fix: Get progress bar indicator color based on usage percentage.
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
function TrendIcon({ trend }: { trend: QuotaTrend }) {
  switch (trend) {
    case 'increasing':
      return <TrendingUp className="size-3 text-destructive" />;
    case 'decreasing':
      return <TrendingDown className="size-3 text-[var(--success)]" />;
    default:
      return <Minus className="size-3 text-muted-foreground" />;
  }
}

/** Format large numbers with K/M suffix */
function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return num.toString();
}

/** Format INR with USD equivalent */
function formatCurrency(inr: number, rate: number): string {
  const usd = inr / rate;
  return `₹${inr.toLocaleString('en-IN', { maximumFractionDigits: 2 })} (~$${usd.toFixed(2)})`;
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

/** Single provider quota display */
function ProviderQuotaItem({
  quota,
  usdToInrRate,
}: {
  quota: ProviderQuota;
  usdToInrRate: number;
}) {
  // F10 fix: Calculate usage percentage with guards against zero/null limits
  const tokenUsagePct = quota.dailyTokenLimit && quota.dailyTokenLimit > 0
    ? (quota.dailyTokensUsed / quota.dailyTokenLimit) * 100
    : 0;
  const costUsagePct = quota.dailyCostLimitInr && quota.dailyCostLimitInr > 0
    ? (quota.dailyCostInr / quota.dailyCostLimitInr) * 100
    : 0;
  const displayPct = Math.max(tokenUsagePct, costUsagePct);

  return (
    <div className="space-y-2">
      {/* Provider header with alert badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className={cn('size-4', quota.alertTriggered ? 'text-destructive' : 'text-primary')} />
          <span className="font-medium capitalize">{quota.provider}</span>
        </div>
        {quota.alertTriggered ? (
          <Badge variant="destructive" className="text-xs gap-1">
            <AlertTriangle className="size-3" />
            ALERT
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-xs gap-1">
            <TrendIcon trend={quota.trend} />
            {quota.trend}
          </Badge>
        )}
      </div>

      {/* Token usage progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Tokens</span>
          <span>
            {formatNumber(quota.dailyTokensUsed)}
            {quota.dailyTokenLimit && quota.dailyTokenLimit > 0 && `/${formatNumber(quota.dailyTokenLimit)}`}
            {' '}
            ({tokenUsagePct.toFixed(0)}%)
          </span>
        </div>
        {/* F9 fix: Use indicatorStyle prop for dynamic coloring */}
        <Progress
          value={Math.min(tokenUsagePct, 100)}
          className="h-2"
          indicatorStyle={getUsageIndicatorStyle(tokenUsagePct)}
        />
      </div>

      {/* Cost and projection */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1 text-muted-foreground">
          <DollarSign className="size-3" />
          <span>{formatCurrency(quota.dailyCostInr, usdToInrRate)}</span>
        </div>
        {quota.projectedExhaustion && (
          <div className="flex items-center gap-1 text-muted-foreground">
            <span>Est. exhaustion:</span>
            <span className={cn(quota.alertTriggered && 'text-destructive font-medium')}>
              {quota.projectedExhaustion}
            </span>
            <TrendIcon trend={quota.trend} />
          </div>
        )}
      </div>

      {/* Rate limiter info */}
      {quota.rateLimitedCount > 0 && (
        <div className="text-xs text-[var(--warning)]">
          Rate limited {quota.rateLimitedCount} times this session
        </div>
      )}
    </div>
  );
}

/** Loading skeleton for a single provider */
function ProviderQuotaSkeleton() {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-5 w-16" />
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-12" />
          <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton className="h-2 w-full" />
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-3 w-32" />
      </div>
    </div>
  );
}

export function LLMQuotaWidget({ className }: LLMQuotaWidgetProps) {
  const {
    quotaData,
    providers,
    hasAlerts,
    isLoading,
    error,
    lastUpdated,
    refresh,
  } = useLLMQuota();

  const handleRefresh = async () => {
    await refresh();
  };

  return (
    <Card className={cn(className, hasAlerts && 'border-destructive')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            LLM Quota Status
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
            title="Refresh quota data"
          >
            <RefreshCw className={cn('size-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Loading state */}
        {isLoading && !quotaData && (
          <>
            <ProviderQuotaSkeleton />
            <ProviderQuotaSkeleton />
          </>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="text-center py-4">
            <p className="text-sm text-destructive mb-2" role="alert">
              Failed to load quota data
            </p>
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              Retry
            </Button>
          </div>
        )}

        {/* Quota display */}
        {!isLoading && !error && quotaData && (
          <>
            {providers.map((provider) => (
              <ProviderQuotaItem
                key={provider.provider}
                quota={provider}
                usdToInrRate={quotaData.usdToInrRate}
              />
            ))}

            {/* Last updated footer */}
            {lastUpdated && (
              <div className="text-xs text-muted-foreground text-center pt-2 border-t">
                Last updated: {formatTime(lastUpdated)}
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!isLoading && !error && providers.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-2">
            No quota data available
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * LLM Quota Widget Skeleton
 *
 * Loading placeholder for the entire widget.
 */
export function LLMQuotaWidgetSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="size-8 rounded-md" />
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        <ProviderQuotaSkeleton />
        <ProviderQuotaSkeleton />
      </CardContent>
    </Card>
  );
}
