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

import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { useShallow } from 'zustand/react/shallow';
import { ArrowRight, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useActivityStore } from '@/stores/activityStore';
import { ActivityIcon } from './ActivityFeedItem';
import { formatRelativeTime } from '@/utils/formatRelativeTime';
import { cn } from '@/lib/utils';
import type { Activity } from '@/types/activity';

interface MobileActivityFeedProps {
  /** Maximum number of items to display */
  maxItems?: number;
  /** Enable pull-to-refresh on mobile */
  enablePullToRefresh?: boolean;
}

// Pull-to-refresh hook
function usePullToRefresh(
  onRefresh: () => Promise<void>,
  enabled: boolean = true
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const startYRef = useRef(0);
  const [isPulling, setIsPulling] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);

  const THRESHOLD = 80; // Pull distance to trigger refresh

  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (!enabled || isRefreshing) return;
    startYRef.current = e.touches[0]?.clientY ?? 0;
  }, [enabled, isRefreshing]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!enabled || isRefreshing) return;

    const currentY = e.touches[0]?.clientY ?? 0;
    const diff = currentY - startYRef.current;

    // Only allow pull-to-refresh when at top of scroll
    if (containerRef.current && containerRef.current.scrollTop <= 0 && diff > 0) {
      setIsPulling(true);
      setPullDistance(Math.min(diff, THRESHOLD * 1.5));
      e.preventDefault();
    }
  }, [enabled, isRefreshing]);

  const handleTouchEnd = useCallback(async () => {
    if (!enabled || isRefreshing) return;

    if (pullDistance >= THRESHOLD) {
      setIsRefreshing(true);

      // Haptic feedback if supported
      if ('vibrate' in navigator) {
        navigator.vibrate(10);
      }

      try {
        await onRefresh();
      } finally {
        setIsRefreshing(false);
      }
    }

    setIsPulling(false);
    setPullDistance(0);
  }, [enabled, isRefreshing, pullDistance, onRefresh]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !enabled) return;

    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', handleTouchMove, { passive: false });
    container.addEventListener('touchend', handleTouchEnd);

    return () => {
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
      container.removeEventListener('touchend', handleTouchEnd);
    };
  }, [enabled, handleTouchStart, handleTouchMove, handleTouchEnd]);

  return { containerRef, isPulling, isRefreshing, pullDistance };
}

interface MobileActivityItemProps {
  activity: Activity;
  onActivityClick?: (activity: Activity) => void;
}

function MobileActivityItem({ activity, onActivityClick }: MobileActivityItemProps) {
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

  const handleClick = () => {
    if (onActivityClick && !activity.isRead) {
      onActivityClick(activity);
    }
  };

  return (
    <Link
      href={getActivityLink(activity)}
      onClick={handleClick}
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

export function MobileActivityFeed({ maxItems = 5, enablePullToRefresh = true }: MobileActivityFeedProps) {
  const activities = useActivityStore(
    useShallow((state) => state.activities.slice(0, maxItems))
  );
  const isLoading = useActivityStore((state) => state.isLoading);
  const error = useActivityStore((state) => state.error);
  const fetchActivities = useActivityStore((state) => state.fetchActivities);
  const markActivityRead = useActivityStore((state) => state.markActivityRead);

  // Memoize activities array to prevent re-renders
  const displayActivities = useMemo(() => activities, [activities]);

  // Pull-to-refresh functionality
  const handlePullRefresh = useCallback(async () => {
    await fetchActivities();
  }, [fetchActivities]);

  const { containerRef, isPulling, isRefreshing, pullDistance } = usePullToRefresh(
    handlePullRefresh,
    enablePullToRefresh
  );

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  const handleRefresh = () => {
    fetchActivities();
  };

  // Handle activity click - mark as read (same pattern as desktop ActivityFeed)
  const handleActivityClick = (activity: Activity) => {
    if (!activity.isRead) {
      markActivityRead(activity.id);
    }
  };

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
    <div ref={containerRef} className="relative">
      {/* Pull-to-refresh indicator */}
      {(isPulling || isRefreshing) && (
        <div
          className="flex items-center justify-center py-2 transition-all overflow-hidden"
          style={{ height: isRefreshing ? 40 : Math.min(pullDistance, 60) }}
        >
          {isRefreshing ? (
            <Loader2 className="size-5 animate-spin text-primary" />
          ) : (
            <RefreshCw
              className={cn(
                'size-5 text-muted-foreground transition-transform',
                pullDistance >= 80 && 'text-primary rotate-180'
              )}
            />
          )}
        </div>
      )}

      <div className="space-y-1">
        {displayActivities.map((activity) => (
          <MobileActivityItem
            key={activity.id}
            activity={activity}
            onActivityClick={handleActivityClick}
          />
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
    </div>
  );
}
