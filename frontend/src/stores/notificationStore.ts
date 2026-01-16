/**
 * Notification Store
 *
 * Zustand store for managing notifications in the dashboard header.
 * Story 14.10: Wired to real backend API.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const notifications = useNotificationStore((state) => state.notifications);
 *   const unreadCount = useNotificationStore((state) => state.unreadCount);
 *   const markAsRead = useNotificationStore((state) => state.markAsRead);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { notifications, markAsRead } = useNotificationStore();
 */

import { create } from 'zustand';
import type { Notification } from '@/types/notification';
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from '@/lib/api/notifications';
import { toast } from 'sonner';

/** Generate unique ID for notification (used for local-only notifications) */
function generateNotificationId(): string {
  return `notif_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

interface NotificationState {
  /** All notifications */
  notifications: Notification[];

  /** Count of unread notifications */
  unreadCount: number;

  /** Loading state for fetching notifications */
  isLoading: boolean;

  /** Error message if fetch fails */
  error: string | null;
}

interface NotificationActions {
  /** Fetch notifications from API */
  fetchNotifications: () => Promise<void>;

  /** Mark a single notification as read */
  markAsRead: (notificationId: string) => Promise<void>;

  /** Mark all notifications as read */
  markAllAsRead: () => Promise<void>;

  /** Add a new notification (for real-time updates) */
  addNotification: (notification: Omit<Notification, 'id' | 'createdAt' | 'isRead'>) => void;

  /** Remove a notification */
  removeNotification: (notificationId: string) => void;

  /** Clear all notifications */
  clearAll: () => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Set error state */
  setError: (error: string | null) => void;
}

type NotificationStore = NotificationState & NotificationActions;

/** Calculate unread count from notifications */
function calculateUnreadCount(notifications: Notification[]): number {
  return notifications.filter((n) => !n.isRead).length;
}

export const useNotificationStore = create<NotificationStore>()((set, get) => ({
  // Initial state
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  error: null,

  // Actions
  fetchNotifications: async () => {
    set({ isLoading: true, error: null });
    try {
      // Story 14.10: Call real API
      const { notifications, unreadCount } = await getNotifications({ limit: 20 });

      set({
        notifications,
        unreadCount,
        isLoading: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch notifications';
      set({ error: message, isLoading: false });
      // Don't show toast on fetch error - it's noisy during polling
    }
  },

  markAsRead: async (notificationId: string) => {
    // Optimistic update
    const previousNotifications = get().notifications;
    const previousUnreadCount = get().unreadCount;

    set((state) => {
      const notifications = state.notifications.map((n) =>
        n.id === notificationId ? { ...n, isRead: true } : n
      );
      return {
        notifications,
        unreadCount: calculateUnreadCount(notifications),
      };
    });

    try {
      // Story 14.10: Sync with backend
      await markNotificationRead(notificationId);
    } catch (error) {
      // Revert on error
      set({ notifications: previousNotifications, unreadCount: previousUnreadCount });
      const message = error instanceof Error ? error.message : 'Failed to mark notification as read';
      toast.error(message);
    }
  },

  markAllAsRead: async () => {
    // Optimistic update
    const previousNotifications = get().notifications;
    const previousUnreadCount = get().unreadCount;

    set((state) => {
      const notifications = state.notifications.map((n) => ({ ...n, isRead: true }));
      return {
        notifications,
        unreadCount: 0,
      };
    });

    try {
      // Story 14.10: Sync with backend
      await markAllNotificationsRead();
    } catch (error) {
      // Revert on error
      set({ notifications: previousNotifications, unreadCount: previousUnreadCount });
      const message =
        error instanceof Error ? error.message : 'Failed to mark all notifications as read';
      toast.error(message);
    }
  },

  addNotification: (notification) => {
    const newNotification: Notification = {
      ...notification,
      id: generateNotificationId(),
      createdAt: new Date().toISOString(),
      isRead: false,
    };

    set((state) => {
      const notifications = [newNotification, ...state.notifications];
      return {
        notifications,
        unreadCount: state.unreadCount + 1,
      };
    });
  },

  removeNotification: (notificationId: string) => {
    set((state) => {
      const notifications = state.notifications.filter((n) => n.id !== notificationId);
      return {
        notifications,
        unreadCount: calculateUnreadCount(notifications),
      };
    });
  },

  clearAll: () => {
    set({ notifications: [], unreadCount: 0 });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

/** Selector for getting only unread notifications */
export const selectUnreadNotifications = (state: NotificationStore): Notification[] =>
  state.notifications.filter((n) => !n.isRead);

/** Selector for getting notifications by matter */
export const selectNotificationsByMatter =
  (matterId: string) =>
  (state: NotificationStore): Notification[] =>
    state.notifications.filter((n) => n.matterId === matterId);

/** Selector for getting high priority unread notifications */
export const selectHighPriorityUnread = (state: NotificationStore): Notification[] =>
  state.notifications.filter((n) => !n.isRead && n.priority === 'high');
