/**
 * Notification Types
 *
 * Types for the notification system used in the dashboard header.
 * From UX-Decisions-Log.md:
 * - Success (green): Processing complete, verification done
 * - Info (blue): Login, opened matter
 * - In progress (yellow): Upload started, processing
 * - Attention needed (warning): Contradictions found, low confidence
 * - Error (red): Processing failed, upload error
 */

/** Notification type categories */
export type NotificationType = 'success' | 'info' | 'warning' | 'error' | 'in_progress';

/** Notification priority levels */
export type NotificationPriority = 'high' | 'medium' | 'low';

/** A single notification item */
export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  matterId: string | null;
  matterTitle: string | null;
  isRead: boolean;
  createdAt: string;
  priority: NotificationPriority;
}

/** Request model for marking notification as read */
export interface MarkNotificationReadRequest {
  notificationId: string;
}

/** API response wrapper for notification list */
export interface NotificationListResponse {
  data: Notification[];
}

/** API response for notification count */
export interface NotificationCountResponse {
  data: {
    total: number;
    unread: number;
  };
}

/**
 * Get icon emoji for notification type (for display purposes)
 * Matches UX-Decisions-Log.md specification
 */
export function getNotificationIcon(type: NotificationType): string {
  const icons: Record<NotificationType, string> = {
    success: '🟢',
    info: '🔵',
    in_progress: '🟡',
    warning: '⚠️',
    error: '🔴',
  };
  return icons[type];
}

/**
 * Get color class for notification type
 */
export function getNotificationColorClass(type: NotificationType): string {
  const colors: Record<NotificationType, string> = {
    success: 'text-green-600 dark:text-green-400',
    info: 'text-blue-600 dark:text-blue-400',
    in_progress: 'text-yellow-600 dark:text-yellow-400',
    warning: 'text-orange-600 dark:text-orange-400',
    error: 'text-red-600 dark:text-red-400',
  };
  return colors[type];
}

/**
 * Get background color class for notification type
 */
export function getNotificationBgClass(type: NotificationType): string {
  const colors: Record<NotificationType, string> = {
    success: 'bg-green-50 dark:bg-green-950/30',
    info: 'bg-blue-50 dark:bg-blue-950/30',
    in_progress: 'bg-yellow-50 dark:bg-yellow-950/30',
    warning: 'bg-orange-50 dark:bg-orange-950/30',
    error: 'bg-red-50 dark:bg-red-950/30',
  };
  return colors[type];
}
