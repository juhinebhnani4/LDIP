'use client';

/**
 * Verification Statistics Header Component
 *
 * Displays verification progress and statistics for the dashboard.
 *
 * Story 8-5: Implement Verification Queue UI (Task 2)
 * Implements AC #4: Statistics header
 */

import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { VerificationStats as StatsType } from '@/types';

interface VerificationStatsProps {
  /** Verification statistics */
  stats: StatsType | null;
  /** Loading state */
  isLoading?: boolean;
  /** Callback when "Start Review Session" is clicked */
  onStartSession?: () => void;
}

/**
 * Verification statistics header showing overall progress.
 *
 * Displays:
 * - Progress bar with completion percentage
 * - Count of verified, pending, flagged findings
 * - Export blocking status
 * - Category breakdown badges
 *
 * @example
 * ```tsx
 * <VerificationStats
 *   stats={stats}
 *   isLoading={isLoading}
 *   onStartSession={() => setFocusMode(true)}
 * />
 * ```
 */
export function VerificationStats({
  stats,
  isLoading = false,
  onStartSession,
}: VerificationStatsProps) {
  // Loading skeleton
  if (isLoading || !stats) {
    return (
      <div className="space-y-4 p-4 rounded-lg border bg-card">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-2 w-64" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-9 w-36" />
        </div>
        <div className="flex items-center gap-4">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>
    );
  }

  // Calculate completion percentage
  const completedCount = stats.approvedCount + stats.rejectedCount;
  const completionPercent =
    stats.totalVerifications > 0
      ? Math.round((completedCount / stats.totalVerifications) * 100)
      : 0;

  return (
    <div className="space-y-4 p-4 rounded-lg border bg-card">
      {/* Header with progress */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Verification Center</h2>
          <Progress
            value={completionPercent}
            className="w-64 h-2 mt-2"
            aria-label={`${completionPercent}% complete`}
          />
          <p className="text-sm text-muted-foreground mt-1">
            {completionPercent}% Complete
          </p>
        </div>
        {onStartSession && (
          <Button onClick={onStartSession} disabled={stats.pendingCount === 0}>
            Start Review Session
          </Button>
        )}
      </div>

      {/* Statistics summary */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-green-600 dark:text-green-400">
          {stats.approvedCount} verified
        </span>
        <span className="text-muted-foreground">|</span>
        <span className="text-yellow-600 dark:text-yellow-400">
          {stats.pendingCount} pending
        </span>
        <span className="text-muted-foreground">|</span>
        <span className="text-orange-600 dark:text-orange-400">
          {stats.flaggedCount} flagged
        </span>
        {stats.rejectedCount > 0 && (
          <>
            <span className="text-muted-foreground">|</span>
            <span className="text-red-600 dark:text-red-400">
              {stats.rejectedCount} rejected
            </span>
          </>
        )}
        {stats.exportBlocked && (
          <>
            <span className="text-muted-foreground">|</span>
            <Badge variant="destructive">
              {stats.blockingCount} blocking export
            </Badge>
          </>
        )}
      </div>

      {/* Category breakdown by verification tier */}
      <div className="flex flex-wrap gap-2">
        {stats.requiredPending > 0 && (
          <Badge variant="destructive" className="font-normal">
            Required: {stats.requiredPending} pending
          </Badge>
        )}
        {stats.suggestedPending > 0 && (
          <Badge variant="outline" className="font-normal text-yellow-600 border-yellow-500">
            Suggested: {stats.suggestedPending} pending
          </Badge>
        )}
        {stats.optionalPending > 0 && (
          <Badge variant="outline" className="font-normal text-green-600 border-green-500">
            Optional: {stats.optionalPending} pending
          </Badge>
        )}
      </div>
    </div>
  );
}
