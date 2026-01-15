'use client';

import { useEffect } from 'react';
import { Folder, FileCheck, Timer } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useActivityStore } from '@/stores/activityStore';
import { cn } from '@/lib/utils';

/**
 * Quick Stats Component
 *
 * Displays dashboard statistics: active matters, verified findings, pending reviews.
 * Stats update in real-time (with 30s cache).
 *
 * UX Layout from Story 9-3:
 * ┌────────────────────────────┐
 * │  QUICK STATS               │
 * │                            │
 * │  📁 5 Active Matters       │
 * │                            │
 * │  ✓ 127 Verified Findings   │
 * │                            │
 * │  ⏳ 3 Pending Reviews      │
 * │                            │
 * └────────────────────────────┘
 */

interface QuickStatsProps {
  /** Optional className for styling */
  className?: string;
}

interface StatItemProps {
  /** Icon component to display */
  icon: React.ElementType;
  /** Label for the stat */
  label: string;
  /** Value to display */
  value: number;
  /** Color class for the icon */
  iconColorClass?: string;
}

/** Single stat item */
function StatItem({ icon: Icon, label, value, iconColorClass = 'text-muted-foreground' }: StatItemProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          'flex items-center justify-center size-9 rounded-md bg-muted/50',
        )}
        aria-hidden="true"
      >
        <Icon className={cn('size-5', iconColorClass)} />
      </div>
      <div>
        <p className="text-2xl font-bold leading-none">{value.toLocaleString()}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
      </div>
    </div>
  );
}

/** Stat item skeleton for loading state */
function StatItemSkeleton() {
  return (
    <div className="flex items-center gap-3">
      <Skeleton className="size-9 rounded-md" />
      <div className="space-y-2">
        <Skeleton className="h-6 w-12" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  );
}

export function QuickStats({ className }: QuickStatsProps) {
  // Use selector pattern (MANDATORY from project-context.md)
  const stats = useActivityStore((state) => state.stats);
  const isLoading = useActivityStore((state) => state.isStatsLoading);
  const error = useActivityStore((state) => state.error);
  const fetchStats = useActivityStore((state) => state.fetchStats);

  // Fetch stats on mount
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Quick Stats</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Loading state */}
        {isLoading && (
          <>
            <StatItemSkeleton />
            <StatItemSkeleton />
            <StatItemSkeleton />
          </>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <p className="text-sm text-destructive text-center py-2" role="alert">
            Failed to load stats
          </p>
        )}

        {/* Stats display */}
        {!isLoading && stats && (
          <>
            <StatItem
              icon={Folder}
              label="Active Matters"
              value={stats.activeMatters}
              iconColorClass="text-blue-500"
            />
            <StatItem
              icon={FileCheck}
              label="Verified Findings"
              value={stats.verifiedFindings}
              iconColorClass="text-green-500"
            />
            <StatItem
              icon={Timer}
              label="Pending Reviews"
              value={stats.pendingReviews}
              iconColorClass="text-orange-500"
            />
          </>
        )}

        {/* Empty state (stats loaded but all zero) */}
        {!isLoading && !error && !stats && (
          <p className="text-sm text-muted-foreground text-center py-2">
            No statistics available
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Quick Stats Skeleton
 *
 * Loading placeholder for the entire quick stats card.
 */
export function QuickStatsSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <Skeleton className="h-5 w-24" />
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        <StatItemSkeleton />
        <StatItemSkeleton />
        <StatItemSkeleton />
      </CardContent>
    </Card>
  );
}
