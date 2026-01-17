'use client';

/**
 * MobileQuickStats Component
 *
 * Horizontal scrollable quick stats for mobile devices.
 * Touch-friendly with minimum 44px tap targets.
 *
 * Story 14.15: Mobile Activity Feed
 * Task 5: Update QuickStats for mobile
 */

import { useEffect, useRef } from 'react';
import { Folder, FileCheck, Timer } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useActivityStore } from '@/stores/activityStore';
import { cn } from '@/lib/utils';

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: number;
  iconColorClass?: string;
}

function StatCard({ icon: Icon, label, value, iconColorClass = 'text-muted-foreground' }: StatCardProps) {
  return (
    <Card className="shrink-0 w-[140px] snap-start">
      <CardContent className="p-3 flex items-center gap-3">
        <div
          className="flex items-center justify-center size-10 rounded-md bg-muted/50"
          aria-hidden="true"
        >
          <Icon className={cn('size-5', iconColorClass)} />
        </div>
        <div className="min-w-0">
          <p className="text-lg font-bold leading-none">{value.toLocaleString()}</p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function StatCardSkeleton() {
  return (
    <Card className="shrink-0 w-[140px]">
      <CardContent className="p-3 flex items-center gap-3">
        <Skeleton className="size-10 rounded-md" />
        <div className="space-y-1.5">
          <Skeleton className="h-5 w-8" />
          <Skeleton className="h-3 w-16" />
        </div>
      </CardContent>
    </Card>
  );
}

export function MobileQuickStats() {
  const stats = useActivityStore((state) => state.stats);
  const isLoading = useActivityStore((state) => state.isStatsLoading);
  const error = useActivityStore((state) => state.error);
  const fetchStats = useActivityStore((state) => state.fetchStats);

  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    fetchStats();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchStats]);

  if (error && !isLoading) {
    return (
      <p className="text-sm text-destructive text-center py-2" role="alert">
        Failed to load stats
      </p>
    );
  }

  return (
    <div className="w-full overflow-x-auto pb-2 -mx-4 px-4 snap-x snap-mandatory scrollbar-hide">
      <div className="flex gap-3 min-w-min">
        {isLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : stats ? (
          <>
            <StatCard
              icon={Folder}
              label="Active Matters"
              value={stats.activeMatters}
              iconColorClass="text-primary"
            />
            <StatCard
              icon={FileCheck}
              label="Verified"
              value={stats.verifiedFindings}
              iconColorClass="text-[var(--success)]"
            />
            <StatCard
              icon={Timer}
              label="Pending"
              value={stats.pendingReviews}
              iconColorClass="text-[var(--warning)]"
            />
          </>
        ) : (
          <p className="text-sm text-muted-foreground py-2">No statistics available</p>
        )}
      </div>
    </div>
  );
}
