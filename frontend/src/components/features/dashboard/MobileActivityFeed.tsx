'use client';

/**
 * MobileActivityFeed Component
 *
 * Compact activity feed optimized for mobile screens.
 * Features relative timestamps and smaller layout.
 *
 * Story 14.15: Mobile Activity Feed
 * Task 2: Create MobileActivityFeed variant
 */

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useShallow } from 'zustand/react/shallow';
import { ArrowRight, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useActivityStore } from '@/stores/activityStore';
import { ActivityIcon } from './ActivityFeedItem';
import { formatRelativeTime } from '@/utils/formatRelativeTime';
import { cn } from '@/lib/utils';
import type { Activity } from '@/types/activity';

interface MobileActivityFeedProps {
  /** Maximum number of items to display */
  maxItems?: number;
}

interface MobileActivityItemProps {
  activity: Activity;
}

function MobileActivityItem({ activity }: MobileActivityItemProps) {
  const getActivityLink = (act: Activity): string => {
    const base = `/matter/${act.matterId}`;
    switch (act.type) {
      case 'processing_complete':
      case 'processing_started':
      case 'processing_failed':
        return `${base}/documents`;
      case 'contradictions_found':
        return `${base}/contradictions`;
      case 'verification_needed':
        return `${base}/verification`;
      case 'matter_opened':
      default:
        return base;
    }
  };

  return (
    <Link
      href={getActivityLink(activity)}
      className={cn(
        'flex items-start gap-3 py-2.5 px-3 rounded-md transition-colors',
        'hover:bg-muted/50 active:bg-muted',
        'min-h-[44px]', // Touch target
        !activity.isRead && 'bg-primary/5'
      )}
    >
      <ActivityIcon type={activity.type} className="size-4 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm leading-snug line-clamp-2">{activity.description}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {formatRelativeTime(activity.timestamp)}
        </p>
      </div>
    </Link>
  );
}

function MobileActivityItemSkeleton() {
  return (
    <div className="flex items-start gap-3 py-2.5 px-3">
      <div className="size-4 rounded bg-muted animate-pulse mt-0.5" />
      <div className="flex-1 space-y-1.5">
        <div className="h-4 bg-muted rounded animate-pulse w-3/4" />
        <div className="h-3 bg-muted rounded animate-pulse w-1/4" />
      </div>
    </div>
  );
}

export function MobileActivityFeed({ maxItems = 5 }: MobileActivityFeedProps) {
  const activities = useActivityStore(
    useShallow((state) => state.activities.slice(0, maxItems))
  );
  const isLoading = useActivityStore((state) => state.isLoading);
  const error = useActivityStore((state) => state.error);
  const fetchActivities = useActivityStore((state) => state.fetchActivities);
  const markActivityRead = useActivityStore((state) => state.markActivityRead);

  // Memoize activities array to prevent re-renders
  const displayActivities = useMemo(() => activities, [activities]);

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  const handleRefresh = () => {
    fetchActivities();
  };

  // Mark activities as read when viewed
  useEffect(() => {
    displayActivities.forEach((activity) => {
      if (!activity.isRead) {
        markActivityRead(activity.id);
      }
    });
  }, [displayActivities, markActivityRead]);

  if (isLoading) {
    return (
      <div className="space-y-1">
        <MobileActivityItemSkeleton />
        <MobileActivityItemSkeleton />
        <MobileActivityItemSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-4">
        <p className="text-sm text-destructive mb-2">{error}</p>
        <Button variant="ghost" size="sm" onClick={handleRefresh}>
          <RefreshCw className="size-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  if (displayActivities.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No recent activity
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {displayActivities.map((activity) => (
        <MobileActivityItem key={activity.id} activity={activity} />
      ))}

      {displayActivities.length >= maxItems && (
        <Button variant="ghost" size="sm" className="w-full mt-2" asChild>
          <Link href="/activity">
            View All
            <ArrowRight className="size-4 ml-1" />
          </Link>
        </Button>
      )}
    </div>
  );
}
