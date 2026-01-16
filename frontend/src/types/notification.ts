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
 * Get color class for notification type - jaanch.ai brand palette
 */
export function getNotificationColorClass(type: NotificationType): string {
  const colors: Record<NotificationType, string> = {
    success: 'text-[#2d5a3d] dark:text-[#4a8a5d]', // Forest Green
    info: 'text-[#0d1b5e] dark:text-[#6b7cb8]', // Deep Indigo
    in_progress: 'text-[#b8973b] dark:text-[#c4a85a]', // Muted Gold
    warning: 'text-[#c4a35a] dark:text-[#d4b86a]', // Aged Gold
    error: 'text-[#8b2635] dark:text-[#c44d5e]', // Burgundy
  };
  return colors[type];
}

/**
 * Get background color class for notification type - jaanch.ai brand palette
 */
export function getNotificationBgClass(type: NotificationType): string {
  const colors: Record<NotificationType, string> = {
    success: 'bg-[#e5f0e8] dark:bg-[#1a2d20]/50', // Forest Green tint
    info: 'bg-[#e8eef8] dark:bg-[#1a2444]/50', // Deep Indigo tint
    in_progress: 'bg-[#f5f0e0] dark:bg-[#3d3520]/50', // Muted Gold tint
    warning: 'bg-[#f5e8d8] dark:bg-[#3d3520]/50', // Aged Gold tint
    error: 'bg-[#f2d4d7] dark:bg-[#3d1a20]/50', // Burgundy tint
  };
  return colors[type];
}
