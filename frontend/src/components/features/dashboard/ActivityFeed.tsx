'use client';

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { Activity as ActivityIcon, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useActivityStore, selectRecentActivities } from '@/stores/activityStore';
import { ActivityFeedItem, ActivityFeedItemSkeleton } from './ActivityFeedItem';
import { getDayGroupLabel } from '@/utils/formatRelativeTime';
import type { Activity } from '@/types/activity';

/**
 * Activity Feed Component
 *
 * Displays recent activities with icon-coded entries grouped by day.
 * Activities are clickable and navigate to the relevant matter/tab.
 *
 * UX Layout from Story 9-3:
 * ┌────────────────────────────┐
 * │  ACTIVITY FEED             │
 * │                            │
 * │  Today                     │
 * │  ─────                     │
 * │  • 🟢 Shah v. Mehta        │
 * │    Processing complete ✓   │
 * │                            │
 * │  • 🔵 SEBI v. Parekh       │
 * │    Matter opened           │
 * │                            │
 * │  Yesterday                 │
 * │  ─────────                 │
 * │  • 🟠 Custody Dispute      │
 * │    3 contradictions found  │
 * │                            │
 * │  [View All Activity →]     │
 * └────────────────────────────┘
 */

interface ActivityFeedProps {
  /** Optional className for styling */
  className?: string;
}

/** Group activities by day */
function groupActivitiesByDay(activities: Activity[]): Map<string, Activity[]> {
  const groups = new Map<string, Activity[]>();

  activities.forEach((activity) => {
    const dayLabel = getDayGroupLabel(activity.timestamp);

    if (!groups.has(dayLabel)) {
      groups.set(dayLabel, []);
    }
    groups.get(dayLabel)?.push(activity);
  });

  return groups;
}

export function ActivityFeed({ className }: ActivityFeedProps) {
  // Use selector pattern (MANDATORY from project-context.md)
  const activities = useActivityStore(selectRecentActivities);
  const isLoading = useActivityStore((state) => state.isLoading);
  const error = useActivityStore((state) => state.error);
  const fetchActivities = useActivityStore((state) => state.fetchActivities);
  const markActivityRead = useActivityStore((state) => state.markActivityRead);

  // Fetch activities on mount
  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  // Group activities by day
  const groupedActivities = useMemo(
    () => groupActivitiesByDay(activities),
    [activities]
  );

  // Handle activity click - mark as read
  const handleActivityClick = (activity: Activity) => {
    if (!activity.isRead) {
      markActivityRead(activity.id);
    }
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ActivityIcon className="size-4" aria-hidden="true" />
          Activity Feed
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {/* Loading state */}
        {isLoading && (
          <ul className="space-y-1" role="list" aria-label="Loading activities">
            {Array.from({ length: 4 }).map((_, i) => (
              <ActivityFeedItemSkeleton key={i} />
            ))}
          </ul>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div
            className="text-sm text-destructive py-4 text-center"
            role="alert"
          >
            {error}
            <Button
              variant="link"
              size="sm"
              onClick={() => fetchActivities()}
              className="block mx-auto mt-2"
            >
              Try again
            </Button>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && activities.length === 0 && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No recent activity
          </p>
        )}

        {/* Activity list grouped by day */}
        {!isLoading && !error && activities.length > 0 && (
          <div className="space-y-4">
            {Array.from(groupedActivities.entries()).map(([dayLabel, dayActivities]) => (
              <div key={dayLabel}>
                {/* Day group header */}
                <h3 className="text-xs font-medium text-muted-foreground mb-2">
                  {dayLabel}
                </h3>

                {/* Activities for this day */}
                <ul className="space-y-1" role="list" aria-label={`Activities from ${dayLabel}`}>
                  {dayActivities.map((activity) => (
                    <ActivityFeedItem
                      key={activity.id}
                      activity={activity}
                      onActivityClick={handleActivityClick}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {/* View all link */}
        {!isLoading && activities.length > 0 && (
          <div className="mt-4 pt-3 border-t">
            <Button variant="ghost" size="sm" className="w-full" asChild>
              <Link href="/activity">
                View All Activity
                <ArrowRight className="size-4 ml-1" />
              </Link>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Activity Feed Skeleton
 *
 * Loading placeholder for the entire activity feed card.
 */
export function ActivityFeedSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="h-5 w-28 rounded bg-muted animate-pulse" />
      </CardHeader>
      <CardContent className="pt-0">
        <ul className="space-y-1" aria-label="Loading activities">
          {Array.from({ length: 4 }).map((_, i) => (
            <ActivityFeedItemSkeleton key={i} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
