'use client';

import { useEffect, useCallback } from 'react';
import { Bell, Check, CheckCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useNotificationStore } from '@/stores/notificationStore';
import type { Notification } from '@/types/notification';
import { getNotificationIcon, getNotificationBgClass } from '@/types/notification';
import { cn } from '@/lib/utils';

/** Format relative time for notification display */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

interface NotificationItemProps {
  notification: Notification;
  onMarkAsRead: (id: string) => void;
}

function NotificationItem({ notification, onMarkAsRead }: NotificationItemProps) {
  const handleMarkAsRead = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onMarkAsRead(notification.id);
    },
    [notification.id, onMarkAsRead]
  );

  return (
    <DropdownMenuItem
      className={cn(
        'flex flex-col items-start gap-1 p-3 cursor-pointer',
        !notification.isRead && getNotificationBgClass(notification.type)
      )}
    >
      <div className="flex w-full items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm" role="img" aria-label={notification.type}>
            {getNotificationIcon(notification.type)}
          </span>
          <span className={cn('text-sm font-medium', !notification.isRead && 'font-semibold')}>
            {notification.title}
          </span>
        </div>
        {!notification.isRead && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0"
            onClick={handleMarkAsRead}
            aria-label="Mark as read"
          >
            <Check className="h-3 w-3" />
          </Button>
        )}
      </div>
      <p className="text-xs text-muted-foreground line-clamp-2 pl-6">{notification.message}</p>
      <div className="flex w-full items-center justify-between pl-6">
        {notification.matterTitle && (
          <span className="text-xs text-muted-foreground">{notification.matterTitle}</span>
        )}
        <span className="text-xs text-muted-foreground ml-auto">
          {formatRelativeTime(notification.createdAt)}
        </span>
      </div>
    </DropdownMenuItem>
  );
}

export function NotificationsDropdown() {
  // Use selectors to prevent unnecessary re-renders
  const notifications = useNotificationStore((state) => state.notifications);
  const unreadCount = useNotificationStore((state) => state.unreadCount);
  const isLoading = useNotificationStore((state) => state.isLoading);
  const fetchNotifications = useNotificationStore((state) => state.fetchNotifications);
  const markAsRead = useNotificationStore((state) => state.markAsRead);
  const markAllAsRead = useNotificationStore((state) => state.markAllAsRead);

  // Fetch notifications on first open (lazy load)
  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (open && notifications.length === 0 && !isLoading) {
        fetchNotifications();
      }
    },
    [notifications.length, isLoading, fetchNotifications]
  );

  // Also fetch on mount for the badge count
  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  return (
    <DropdownMenu onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 min-w-5 px-1 text-xs"
            >
              {unreadCount > 99 ? '99+' : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80" align="end">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Notifications</span>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-auto p-1 text-xs"
              onClick={markAllAsRead}
            >
              <CheckCheck className="mr-1 h-3 w-3" />
              Mark all as read
            </Button>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup className="max-h-80 overflow-y-auto">
          {isLoading && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Loading notifications...
            </div>
          )}
          {!isLoading && notifications.length === 0 && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No notifications yet
            </div>
          )}
          {!isLoading &&
            notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                onMarkAsRead={markAsRead}
              />
            ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
