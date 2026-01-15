/**
 * Notification Store
 *
 * Zustand store for managing notifications in the dashboard header.
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
import type { Notification, NotificationType, NotificationPriority } from '@/types/notification';

/** Generate unique ID for notification */
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
  /** Fetch notifications from API (or use mock data for now) */
  fetchNotifications: () => Promise<void>;

  /** Mark a single notification as read */
  markAsRead: (notificationId: string) => void;

  /** Mark all notifications as read */
  markAllAsRead: () => void;

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

/** Mock notifications for development (backend API not yet available) */
function getMockNotifications(): Notification[] {
  const now = new Date();
  return [
    {
      id: generateNotificationId(),
      type: 'success' as NotificationType,
      title: 'Processing Complete',
      message: 'Document "Contract_2024.pdf" has been processed successfully.',
      matterId: 'matter-1',
      matterTitle: 'Smith vs. Jones',
      isRead: false,
      createdAt: new Date(now.getTime() - 5 * 60000).toISOString(), // 5 min ago
      priority: 'medium' as NotificationPriority,
    },
    {
      id: generateNotificationId(),
      type: 'warning' as NotificationType,
      title: 'Verification Needed',
      message: '3 citations require verification in "Evidence Summary".',
      matterId: 'matter-1',
      matterTitle: 'Smith vs. Jones',
      isRead: false,
      createdAt: new Date(now.getTime() - 30 * 60000).toISOString(), // 30 min ago
      priority: 'high' as NotificationPriority,
    },
    {
      id: generateNotificationId(),
      type: 'in_progress' as NotificationType,
      title: 'OCR Processing',
      message: 'Processing 5 new documents...',
      matterId: 'matter-2',
      matterTitle: 'Acme Corp Acquisition',
      isRead: false,
      createdAt: new Date(now.getTime() - 2 * 60000).toISOString(), // 2 min ago
      priority: 'low' as NotificationPriority,
    },
    {
      id: generateNotificationId(),
      type: 'info' as NotificationType,
      title: 'Matter Opened',
      message: 'You opened matter "Acme Corp Acquisition".',
      matterId: 'matter-2',
      matterTitle: 'Acme Corp Acquisition',
      isRead: true,
      createdAt: new Date(now.getTime() - 60 * 60000).toISOString(), // 1 hour ago
      priority: 'low' as NotificationPriority,
    },
    {
      id: generateNotificationId(),
      type: 'error' as NotificationType,
      title: 'Upload Failed',
      message: 'Failed to upload "LargeFile.pdf". File size exceeds limit.',
      matterId: null,
      matterTitle: null,
      isRead: true,
      createdAt: new Date(now.getTime() - 2 * 60 * 60000).toISOString(), // 2 hours ago
      priority: 'high' as NotificationPriority,
    },
  ];
}

export const useNotificationStore = create<NotificationStore>()((set) => ({
  // Initial state
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  error: null,

  // Actions
  fetchNotifications: async () => {
    set({ isLoading: true, error: null });
    try {
      // TODO: Replace with actual API call when backend is available
      // const response = await fetch('/api/notifications');
      // const { data } = await response.json();

      // Using mock data for now
      await new Promise((resolve) => setTimeout(resolve, 300)); // Simulate network delay
      const notifications = getMockNotifications();

      set({
        notifications,
        unreadCount: calculateUnreadCount(notifications),
        isLoading: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch notifications';
      set({ error: message, isLoading: false });
    }
  },

  markAsRead: (notificationId: string) => {
    set((state) => {
      const notifications = state.notifications.map((n) =>
        n.id === notificationId ? { ...n, isRead: true } : n
      );
      return {
        notifications,
        unreadCount: calculateUnreadCount(notifications),
      };
    });

    // TODO: Sync with backend when API is available
    // await fetch(`/api/notifications/${notificationId}/read`, { method: 'POST' });
  },

  markAllAsRead: () => {
    set((state) => {
      const notifications = state.notifications.map((n) => ({ ...n, isRead: true }));
      return {
        notifications,
        unreadCount: 0,
      };
    });

    // TODO: Sync with backend when API is available
    // await fetch('/api/notifications/read-all', { method: 'POST' });
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

// =============================================================================
// Helper Functions (Story 9-6)
// =============================================================================

/**
 * Add a processing complete notification
 * Convenience function for adding matter completion notifications
 *
 * @param matterName - The name of the matter that completed processing
 * @param matterId - The ID of the completed matter
 */
export function addProcessingCompleteNotification(
  matterName: string,
  matterId: string
): void {
  useNotificationStore.getState().addNotification({
    type: 'success',
    title: 'Processing Complete',
    message: `Matter "${matterName}" is ready for analysis.`,
    matterId,
    matterTitle: matterName,
    priority: 'medium',
  });
}
