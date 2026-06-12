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
    <Card className="w-full min-w-0">
      <CardContent className="flex flex-col items-center gap-1 p-3 text-center">
        <div
          className="flex size-9 items-center justify-center rounded-md bg-muted/50"
          aria-hidden="true"
        >
          <Icon className={cn('size-5', iconColorClass)} />
        </div>
        <p className="text-lg font-bold leading-none">{value.toLocaleString()}</p>
        <p className="text-xs leading-tight text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

function StatCardSkeleton() {
  return (
    <Card className="w-full min-w-0">
      <CardContent className="flex flex-col items-center gap-1.5 p-3">
        <Skeleton className="size-9 shrink-0 rounded-md" />
        <Skeleton className="h-5 w-8" />
        <Skeleton className="h-3 w-14" />
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
    <div className="w-full">
      <div className="grid grid-cols-3 gap-3">
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
          <p className="col-span-3 text-sm text-muted-foreground py-2">No statistics available</p>
        )}
      </div>
    </div>
  );
}
