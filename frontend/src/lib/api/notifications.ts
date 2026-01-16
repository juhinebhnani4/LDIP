'use client';

import { api } from './client';
import type { Notification } from '@/types/notification';

/**
 * API Response types matching backend models.
 * Story 14.10: Notifications Backend & Frontend Wiring
 */

interface NotificationListResponse {
  data: Notification[];
  unreadCount: number;
}

interface NotificationResponse {
  data: Notification;
}

interface MarkAllReadResponse {
  count: number;
}

/**
 * Notification API client functions.
 *
 * Story 14.10: Notifications Backend & Frontend Wiring
 *
 * These functions provide a typed interface to the notification API endpoints.
 */

/**
 * Get notifications for the current user.
 *
 * @param options.limit - Maximum notifications to return (1-50, default 20)
 * @param options.unreadOnly - If true, only return unread notifications
 * @returns Notifications list and unread count
 */
export async function getNotifications(options?: {
  limit?: number;
  unreadOnly?: boolean;
}): Promise<{ notifications: Notification[]; unreadCount: number }> {
  const params = new URLSearchParams();

  if (options?.limit) {
    params.set('limit', String(options.limit));
  }
  if (options?.unreadOnly) {
    params.set('unread_only', 'true');
  }

  const queryString = params.toString();
  const endpoint = queryString ? `/api/notifications?${queryString}` : '/api/notifications';

  const response = await api.get<NotificationListResponse>(endpoint);
  return { notifications: response.data, unreadCount: response.unreadCount };
}

/**
 * Mark a single notification as read.
 *
 * @param notificationId - Notification ID to mark as read
 * @returns Updated notification
 */
export async function markNotificationRead(notificationId: string): Promise<Notification> {
  const response = await api.patch<NotificationResponse>(
    `/api/notifications/${notificationId}/read`,
    {}
  );
  return response.data;
}

/**
 * Mark all notifications as read for the current user.
 *
 * @returns Count of notifications marked as read
 */
export async function markAllNotificationsRead(): Promise<number> {
  const response = await api.post<MarkAllReadResponse>('/api/notifications/read-all', {});
  return response.count;
}

/**
 * Notification API object for convenience.
 *
 * Story 14.10: Notifications Backend & Frontend Wiring
 */
export const notificationApi = {
  list: getNotifications,
  markRead: markNotificationRead,
  markAllRead: markAllNotificationsRead,
};
