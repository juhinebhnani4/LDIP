'use client';

/**
 * Activity Page
 *
 * Full activity history view with filtering and bulk actions.
 * Linked from ActivityFeed and MobileActivityFeed "View All" buttons.
 */

import { useEffect, useMemo, useState, useCallback } from 'react';
import Link from 'next/link';
import { useShallow } from 'zustand/react/shallow';
import {
  Activity as ActivityIcon,
  ArrowLeft,
  CheckCheck,
  Filter,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useActivityStore, selectUnreadCount } from '@/stores/activityStore';
import { ActivityFeedItem, ActivityFeedItemSkeleton } from '@/components/features/dashboard/ActivityFeedItem';
import { getDayGroupLabel } from '@/utils/formatRelativeTime';
import type { Activity, ActivityType } from '@/types/activity';

/** Activity type filter options */
const ACTIVITY_TYPE_FILTERS: { value: ActivityType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Activities' },
  { value: 'processing_complete', label: 'Processing Complete' },
  { value: 'processing_started', label: 'Processing Started' },
  { value: 'processing_failed', label: 'Processing Failed' },
  { value: 'verification_needed', label: 'Verification Needed' },
  { value: 'contradictions_found', label: 'Contradictions Found' },
  { value: 'matter_opened', label: 'Matter Opened' },
];

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

export default function ActivityPage() {
  const [typeFilter, setTypeFilter] = useState<ActivityType | 'all'>('all');

  // Use selector pattern for store access
  const activities = useActivityStore(useShallow((state) => state.activities));
  const isLoading = useActivityStore((state) => state.isLoading);
  const error = useActivityStore((state) => state.error);
  const fetchActivities = useActivityStore((state) => state.fetchActivities);
  const markActivityRead = useActivityStore((state) => state.markActivityRead);
  const markAllRead = useActivityStore((state) => state.markAllRead);
  const unreadCount = useActivityStore(selectUnreadCount);

  // Fetch activities on mount
  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  // Filter activities by type
  const filteredActivities = useMemo(() => {
    if (typeFilter === 'all') {
      return activities;
    }
    return activities.filter((a) => a.type === typeFilter);
  }, [activities, typeFilter]);

  // Group filtered activities by day
  const groupedActivities = useMemo(
    () => groupActivitiesByDay(filteredActivities),
    [filteredActivities]
  );

  // Handle activity click - mark as read
  const handleActivityClick = useCallback(
    (activity: Activity) => {
      if (!activity.isRead) {
        markActivityRead(activity.id);
      }
    },
    [markActivityRead]
  );

  // Handle mark all as read
  const handleMarkAllRead = useCallback(() => {
    markAllRead();
  }, [markAllRead]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    fetchActivities();
  }, [fetchActivities]);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild className="shrink-0">
            <Link href="/" aria-label="Back to dashboard">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <ActivityIcon className="size-6" aria-hidden="true" />
              Activity History
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {unreadCount > 0
                ? `${unreadCount} unread ${unreadCount === 1 ? 'activity' : 'activities'}`
                : 'All caught up'}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="size-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="size-4 mr-2" />
            )}
            Refresh
          </Button>
          {unreadCount > 0 && (
            <Button variant="outline" size="sm" onClick={handleMarkAllRead}>
              <CheckCheck className="size-4 mr-2" />
              Mark All Read
            </Button>
          )}
        </div>
      </div>

      {/* Filter bar */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="size-4" aria-hidden="true" />
            Filter
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex flex-col sm:flex-row gap-3">
            <Select
              value={typeFilter}
              onValueChange={(value) => setTypeFilter(value as ActivityType | 'all')}
            >
              <SelectTrigger className="w-full sm:w-[220px]">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                {ACTIVITY_TYPE_FILTERS.map((filter) => (
                  <SelectItem key={filter.value} value={filter.value}>
                    {filter.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {typeFilter !== 'all' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setTypeFilter('all')}
                className="text-muted-foreground"
              >
                Clear filter
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Activity list */}
      <Card>
        <CardContent className="pt-6">
          {/* Loading state */}
          {isLoading && (
            <ul className="space-y-1" role="list" aria-label="Loading activities">
              {Array.from({ length: 8 }).map((_, i) => (
                <ActivityFeedItemSkeleton key={i} />
              ))}
            </ul>
          )}

          {/* Error state */}
          {error && !isLoading && (
            <div
              className="text-sm text-destructive py-8 text-center"
              role="alert"
            >
              <p>{error}</p>
              <Button
                variant="link"
                size="sm"
                onClick={handleRefresh}
                className="mt-2"
              >
                Try again
              </Button>
            </div>
          )}

          {/* Empty state */}
          {!isLoading && !error && filteredActivities.length === 0 && (
            <div className="text-center py-12">
              <ActivityIcon className="size-12 mx-auto text-muted-foreground/50 mb-4" />
              <p className="text-muted-foreground">
                {typeFilter === 'all'
                  ? 'No activity yet'
                  : `No ${ACTIVITY_TYPE_FILTERS.find((f) => f.value === typeFilter)?.label.toLowerCase()} activities`}
              </p>
              {typeFilter !== 'all' && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => setTypeFilter('all')}
                  className="mt-2"
                >
                  Show all activities
                </Button>
              )}
            </div>
          )}

          {/* Activity list grouped by day */}
          {!isLoading && !error && filteredActivities.length > 0 && (
            <div className="space-y-6">
              {Array.from(groupedActivities.entries()).map(([dayLabel, dayActivities]) => (
                <div key={dayLabel}>
                  {/* Day group header */}
                  <h2 className="text-sm font-semibold text-muted-foreground mb-3 sticky top-0 bg-card py-1">
                    {dayLabel}
                    <span className="ml-2 text-xs font-normal">
                      ({dayActivities.length} {dayActivities.length === 1 ? 'activity' : 'activities'})
                    </span>
                  </h2>

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
        </CardContent>
      </Card>
    </div>
  );
}
