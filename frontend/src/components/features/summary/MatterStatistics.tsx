'use client';

import { FileStack, UserCircle, CalendarDays, Quote } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { MatterStats } from '@/types/summary';

/**
 * Matter Statistics Component
 *
 * Displays stat cards for: total pages, entities found, events extracted, citations found.
 * Also shows verification progress bar.
 *
 * Story 10B.1: Summary Tab Content (AC #4)
 */

interface MatterStatisticsProps {
  /** Matter statistics data */
  stats: MatterStats;
  /** Optional className for styling */
  className?: string;
}

interface StatCardProps {
  /** Icon component */
  icon: React.ElementType;
  /** Stat label */
  label: string;
  /** Stat value */
  value: number;
  /** Icon color class */
  iconColorClass?: string;
}

/**
 * Individual stat card
 */
function StatCard({
  icon: Icon,
  label,
  value,
  iconColorClass = 'text-muted-foreground',
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-4">
          <div
            className={cn(
              'flex items-center justify-center size-12 rounded-lg bg-muted/50'
            )}
            aria-hidden="true"
          >
            <Icon className={cn('size-6', iconColorClass)} />
          </div>
          <div>
            <p className="text-2xl font-bold leading-none">{value.toLocaleString()}</p>
            <p className="text-sm text-muted-foreground mt-1">{label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Verification progress card
 */
interface VerificationProgressCardProps {
  /** Verification percentage (0-100) */
  percent: number;
}

function VerificationProgressCard({ percent }: VerificationProgressCardProps) {
  // Determine color based on percentage
  const getProgressColor = (pct: number): string => {
    if (pct >= 90) return 'text-green-600';
    if (pct >= 70) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <Card className="col-span-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between">
          <span>Verification Progress</span>
          <span className={cn('text-lg font-bold', getProgressColor(percent))}>
            {percent}%
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        <Progress
          value={percent}
          className="h-2"
          aria-label={`${percent}% verification complete`}
        />
        <p className="text-xs text-muted-foreground mt-2">
          {percent >= 90
            ? 'Almost ready for export'
            : percent >= 70
              ? 'Good progress - some items need review'
              : 'Many items still need verification'}
        </p>
      </CardContent>
    </Card>
  );
}

export function MatterStatistics({ stats, className }: MatterStatisticsProps) {
  return (
    <section className={className} aria-labelledby="matter-stats-heading">
      <h2 id="matter-stats-heading" className="text-lg font-semibold mb-4">
        Matter Statistics
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={FileStack}
          label="Total Pages"
          value={stats.totalPages}
          iconColorClass="text-blue-500"
        />
        <StatCard
          icon={UserCircle}
          label="Entities Found"
          value={stats.entitiesFound}
          iconColorClass="text-purple-500"
        />
        <StatCard
          icon={CalendarDays}
          label="Events Extracted"
          value={stats.eventsExtracted}
          iconColorClass="text-green-500"
        />
        <StatCard
          icon={Quote}
          label="Citations Found"
          value={stats.citationsFound}
          iconColorClass="text-orange-500"
        />
        <VerificationProgressCard percent={stats.verificationPercent} />
      </div>
    </section>
  );
}

/**
 * Matter Statistics Skeleton
 */
export function MatterStatisticsSkeleton({ className }: { className?: string }) {
  return (
    <section className={className}>
      <Skeleton className="h-6 w-36 mb-4" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <Skeleton className="size-12 rounded-lg" />
                <div className="space-y-2">
                  <Skeleton className="h-7 w-16" />
                  <Skeleton className="h-4 w-20" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        <Card className="col-span-full">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-5 w-12" />
            </div>
          </CardHeader>
          <CardContent className="pt-2 space-y-2">
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-3 w-48" />
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
