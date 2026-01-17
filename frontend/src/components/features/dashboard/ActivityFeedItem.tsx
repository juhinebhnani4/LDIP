'use client';

import Link from 'next/link';
import { CheckCircle2, Info, Clock, AlertTriangle, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/utils/formatRelativeTime';
import type { Activity, ActivityType } from '@/types/activity';
import { ACTIVITY_ICONS } from '@/types/activity';

/**
 * Activity Feed Item Component
 *
 * Displays a single activity entry with icon, matter name, description, and timestamp.
 * Clicking navigates to the relevant matter.
 *
 * UX Layout from Story 9-3:
 * ┌────────────────────────────────────────┐
 * │  🟢  Shah v. Mehta                      │
 * │      Processing complete   ·  2h ago   │
 * └────────────────────────────────────────┘
 */

interface ActivityFeedItemProps {
  /** Activity data to display */
  activity: Activity;
  /** Callback when activity is clicked */
  onActivityClick?: (activity: Activity) => void;
  /** Optional className for styling */
  className?: string;
}

/** Activity icon component that renders the correct icon based on type */
export function ActivityIcon({ type, className }: { type: ActivityType; className?: string }) {
  const config = ACTIVITY_ICONS[type];
  const iconClassName = cn('size-4', config.colorClass, className);

  switch (config.icon) {
    case 'CheckCircle2':
      return <CheckCircle2 className={iconClassName} />;
    case 'Info':
      return <Info className={iconClassName} />;
    case 'Clock':
      return <Clock className={iconClassName} />;
    case 'AlertTriangle':
      return <AlertTriangle className={iconClassName} />;
    case 'XCircle':
      return <XCircle className={iconClassName} />;
  }
}

export function ActivityFeedItem({
  activity,
  onActivityClick,
  className,
}: ActivityFeedItemProps) {
  const iconConfig = ACTIVITY_ICONS[activity.type];

  const handleClick = () => {
    onActivityClick?.(activity);
  };

  // Build the link href based on matter
  const href = activity.matterId ? `/matter/${activity.matterId}` : '/dashboard';

  return (
    <li className={cn('group', className)}>
      <Link
        href={href}
        onClick={handleClick}
        className={cn(
          'flex items-start gap-3 rounded-md p-2 -mx-2 transition-colors',
          'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          !activity.isRead && 'bg-muted/30'
        )}
        aria-label={`${activity.matterName ?? 'System'}: ${activity.description}, ${formatRelativeTime(activity.timestamp)}`}
      >
        {/* Activity icon with color */}
        <div
          className={cn(
            'mt-0.5 flex-shrink-0 rounded-full p-1',
            iconConfig.bgColorClass
          )}
          aria-hidden="true"
        >
          <ActivityIcon type={activity.type} />
        </div>

        {/* Activity content */}
        <div className="flex-1 min-w-0 space-y-0.5">
          {/* Matter name */}
          {activity.matterName && (
            <p className="text-sm font-medium leading-tight truncate">
              {activity.matterName}
            </p>
          )}

          {/* Description and timestamp */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="truncate">{activity.description}</span>
            <span aria-hidden="true">·</span>
            <time
              dateTime={activity.timestamp}
              className="flex-shrink-0"
              title={new Date(activity.timestamp).toLocaleString()}
            >
              {formatRelativeTime(activity.timestamp)}
            </time>
          </div>
        </div>

        {/* Unread indicator with tooltip for sighted users */}
        {!activity.isRead && (
          <div
            className="size-2 rounded-full bg-blue-500 flex-shrink-0 mt-2"
            role="status"
            aria-label="New activity"
            title="New"
          />
        )}
      </Link>
    </li>
  );
}

/**
 * Activity Feed Item Skeleton
 *
 * Loading placeholder for activity items.
 */
export function ActivityFeedItemSkeleton() {
  return (
    <li className="flex items-start gap-3 p-2 -mx-2 animate-pulse">
      {/* Icon placeholder */}
      <div className="size-6 rounded-full bg-muted flex-shrink-0" />

      {/* Content placeholder */}
      <div className="flex-1 space-y-2">
        <div className="h-4 w-32 rounded bg-muted" />
        <div className="h-3 w-48 rounded bg-muted" />
      </div>
    </li>
  );
}
