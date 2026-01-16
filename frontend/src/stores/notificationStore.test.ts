import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useNotificationStore, selectUnreadNotifications, selectHighPriorityUnread } from './notificationStore';
import type { NotificationType, NotificationPriority, Notification } from '@/types/notification';
import * as notificationsApi from '@/lib/api/notifications';

/**
 * Story 14.10: Updated to mock real API calls instead of relying on mock data.
 */

// Mock the notifications API module
vi.mock('@/lib/api/notifications', () => ({
  getNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

// Mock toast to prevent errors
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

const mockNotifications: Notification[] = [
  {
    id: 'notif-1',
    type: 'success',
    title: 'Processing Complete',
    message: 'Document has been processed.',
    matterId: 'matter-123',
    matterTitle: 'Smith vs. Jones',
    isRead: false,
    createdAt: '2026-01-16T10:00:00Z',
    priority: 'medium',
  },
  {
    id: 'notif-2',
    type: 'warning',
    title: 'Verification Needed',
    message: '3 citations need review.',
    matterId: 'matter-456',
    matterTitle: 'Acme Case',
    isRead: false,
    createdAt: '2026-01-16T09:30:00Z',
    priority: 'high',
  },
  {
    id: 'notif-3',
    type: 'info',
    title: 'System Update',
    message: 'System maintenance completed.',
    matterId: null,
    matterTitle: null,
    isRead: true,
    createdAt: '2026-01-16T09:00:00Z',
    priority: 'low',
  },
];

describe('notificationStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useNotificationStore.setState({
      notifications: [],
      unreadCount: 0,
      isLoading: false,
      error: null,
    });

    // Story 14.10: Set up API mocks with default successful responses
    vi.mocked(notificationsApi.getNotifications).mockResolvedValue({
      notifications: mockNotifications,
      unreadCount: 2, // notif-1 and notif-2 are unread
    });

    vi.mocked(notificationsApi.markNotificationRead).mockImplementation(async (id: string) => {
      const notification = mockNotifications.find((n) => n.id === id);
      if (!notification) throw new Error('Notification not found');
      return { ...notification, isRead: true };
    });

    vi.mocked(notificationsApi.markAllNotificationsRead).mockResolvedValue(2);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchNotifications', () => {
    it('sets loading state while fetching', async () => {
      const fetchPromise = useNotificationStore.getState().fetchNotifications();

      // Check loading state is set
      expect(useNotificationStore.getState().isLoading).toBe(true);

      await fetchPromise;

      // Loading should be false after completion
      expect(useNotificationStore.getState().isLoading).toBe(false);
    });

    it('populates notifications and unread count after fetch', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const state = useNotificationStore.getState();
      expect(state.notifications.length).toBeGreaterThan(0);
      expect(state.unreadCount).toBeGreaterThan(0);
    });

    it('clears error state on successful fetch', async () => {
      // Set an error first
      useNotificationStore.setState({ error: 'Previous error' });

      await useNotificationStore.getState().fetchNotifications();

      expect(useNotificationStore.getState().error).toBeNull();
    });

    it('calls getNotifications API', async () => {
      await useNotificationStore.getState().fetchNotifications();

      expect(notificationsApi.getNotifications).toHaveBeenCalledWith({ limit: 20 });
    });

    it('sets error state on API failure', async () => {
      vi.mocked(notificationsApi.getNotifications).mockRejectedValueOnce(
        new Error('Network error')
      );

      await useNotificationStore.getState().fetchNotifications();

      expect(useNotificationStore.getState().error).toBe('Network error');
      expect(useNotificationStore.getState().isLoading).toBe(false);
    });
  });

  describe('markAsRead', () => {
    it('marks a specific notification as read (optimistic update)', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const initialState = useNotificationStore.getState();
      const unreadNotification = initialState.notifications.find((n) => !n.isRead);
      expect(unreadNotification).toBeDefined();

      if (unreadNotification) {
        // Story 14.10: markAsRead is async with optimistic update
        await useNotificationStore.getState().markAsRead(unreadNotification.id);

        const updatedNotification = useNotificationStore
          .getState()
          .notifications.find((n) => n.id === unreadNotification.id);
        expect(updatedNotification?.isRead).toBe(true);

        // Verify API was called
        expect(notificationsApi.markNotificationRead).toHaveBeenCalledWith(unreadNotification.id);
      }
    });

    it('decreases unread count when marking as read', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const initialUnreadCount = useNotificationStore.getState().unreadCount;
      const unreadNotification = useNotificationStore
        .getState()
        .notifications.find((n) => !n.isRead);

      if (unreadNotification) {
        await useNotificationStore.getState().markAsRead(unreadNotification.id);

        expect(useNotificationStore.getState().unreadCount).toBe(initialUnreadCount - 1);
      }
    });

    it('does not change unread count when marking already-read notification', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const readNotification = useNotificationStore
        .getState()
        .notifications.find((n) => n.isRead);

      if (readNotification) {
        const initialUnreadCount = useNotificationStore.getState().unreadCount;

        await useNotificationStore.getState().markAsRead(readNotification.id);

        expect(useNotificationStore.getState().unreadCount).toBe(initialUnreadCount);
      }
    });

    it('reverts on API error', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const unreadNotification = useNotificationStore
        .getState()
        .notifications.find((n) => !n.isRead);

      if (unreadNotification) {
        // Mock API failure
        vi.mocked(notificationsApi.markNotificationRead).mockRejectedValueOnce(
          new Error('API error')
        );

        const initialUnreadCount = useNotificationStore.getState().unreadCount;

        await useNotificationStore.getState().markAsRead(unreadNotification.id);

        // Should revert to original state
        const notification = useNotificationStore
          .getState()
          .notifications.find((n) => n.id === unreadNotification.id);
        expect(notification?.isRead).toBe(false);
        expect(useNotificationStore.getState().unreadCount).toBe(initialUnreadCount);
      }
    });
  });

  describe('markAllAsRead', () => {
    it('marks all notifications as read', async () => {
      await useNotificationStore.getState().fetchNotifications();

      await useNotificationStore.getState().markAllAsRead();

      const allRead = useNotificationStore
        .getState()
        .notifications.every((n) => n.isRead);
      expect(allRead).toBe(true);

      // Verify API was called
      expect(notificationsApi.markAllNotificationsRead).toHaveBeenCalled();
    });

    it('sets unread count to 0', async () => {
      await useNotificationStore.getState().fetchNotifications();
      expect(useNotificationStore.getState().unreadCount).toBeGreaterThan(0);

      await useNotificationStore.getState().markAllAsRead();

      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });

    it('reverts on API error', async () => {
      await useNotificationStore.getState().fetchNotifications();

      // Mock API failure
      vi.mocked(notificationsApi.markAllNotificationsRead).mockRejectedValueOnce(
        new Error('API error')
      );

      const initialNotifications = useNotificationStore.getState().notifications;
      const initialUnreadCount = useNotificationStore.getState().unreadCount;

      await useNotificationStore.getState().markAllAsRead();

      // Should revert to original state
      expect(useNotificationStore.getState().unreadCount).toBe(initialUnreadCount);
      expect(
        useNotificationStore.getState().notifications.filter((n) => !n.isRead).length
      ).toBe(initialNotifications.filter((n) => !n.isRead).length);
    });
  });

  describe('addNotification', () => {
    it('adds a new notification to the beginning of the list', () => {
      useNotificationStore.getState().addNotification({
        type: 'success' as NotificationType,
        title: 'New Notification',
        message: 'This is a test notification',
        matterId: 'matter-1',
        matterTitle: 'Test Matter',
        priority: 'medium' as NotificationPriority,
      });

      const state = useNotificationStore.getState();
      expect(state.notifications[0]?.title).toBe('New Notification');
      expect(state.notifications[0]?.isRead).toBe(false);
    });

    it('increments unread count', () => {
      const initialCount = useNotificationStore.getState().unreadCount;

      useNotificationStore.getState().addNotification({
        type: 'info' as NotificationType,
        title: 'Test',
        message: 'Test message',
        matterId: null,
        matterTitle: null,
        priority: 'low' as NotificationPriority,
      });

      expect(useNotificationStore.getState().unreadCount).toBe(initialCount + 1);
    });

    it('generates unique ID for new notification', () => {
      useNotificationStore.getState().addNotification({
        type: 'warning' as NotificationType,
        title: 'Test 1',
        message: 'Message 1',
        matterId: null,
        matterTitle: null,
        priority: 'medium' as NotificationPriority,
      });

      useNotificationStore.getState().addNotification({
        type: 'error' as NotificationType,
        title: 'Test 2',
        message: 'Message 2',
        matterId: null,
        matterTitle: null,
        priority: 'high' as NotificationPriority,
      });

      const notifications = useNotificationStore.getState().notifications;
      expect(notifications[0]?.id).not.toBe(notifications[1]?.id);
    });

    it('sets createdAt to current time', () => {
      const before = new Date().toISOString();

      useNotificationStore.getState().addNotification({
        type: 'success' as NotificationType,
        title: 'Test',
        message: 'Test message',
        matterId: null,
        matterTitle: null,
        priority: 'low' as NotificationPriority,
      });

      const after = new Date().toISOString();
      const createdAt = useNotificationStore.getState().notifications[0]?.createdAt;

      expect(createdAt && createdAt >= before && createdAt <= after).toBe(true);
    });
  });

  describe('removeNotification', () => {
    it('removes notification by ID', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const notificationToRemove = useNotificationStore.getState().notifications[0];
      const initialLength = useNotificationStore.getState().notifications.length;

      if (notificationToRemove) {
        useNotificationStore.getState().removeNotification(notificationToRemove.id);

        expect(useNotificationStore.getState().notifications.length).toBe(initialLength - 1);
        expect(
          useNotificationStore.getState().notifications.find((n) => n.id === notificationToRemove.id)
        ).toBeUndefined();
      }
    });

    it('updates unread count correctly when removing unread notification', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const unreadNotification = useNotificationStore
        .getState()
        .notifications.find((n) => !n.isRead);
      const initialUnreadCount = useNotificationStore.getState().unreadCount;

      if (unreadNotification) {
        useNotificationStore.getState().removeNotification(unreadNotification.id);

        expect(useNotificationStore.getState().unreadCount).toBe(initialUnreadCount - 1);
      }
    });
  });

  describe('clearAll', () => {
    it('clears all notifications', async () => {
      await useNotificationStore.getState().fetchNotifications();
      expect(useNotificationStore.getState().notifications.length).toBeGreaterThan(0);

      useNotificationStore.getState().clearAll();

      expect(useNotificationStore.getState().notifications).toEqual([]);
      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });
  });

  describe('setLoading', () => {
    it('sets loading state', () => {
      useNotificationStore.getState().setLoading(true);
      expect(useNotificationStore.getState().isLoading).toBe(true);

      useNotificationStore.getState().setLoading(false);
      expect(useNotificationStore.getState().isLoading).toBe(false);
    });
  });

  describe('setError', () => {
    it('sets error state', () => {
      useNotificationStore.getState().setError('Test error');
      expect(useNotificationStore.getState().error).toBe('Test error');

      useNotificationStore.getState().setError(null);
      expect(useNotificationStore.getState().error).toBeNull();
    });
  });

  describe('selectors', () => {
    it('selectUnreadNotifications returns only unread notifications', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const unread = selectUnreadNotifications(useNotificationStore.getState());

      expect(unread.every((n) => !n.isRead)).toBe(true);
    });

    it('selectHighPriorityUnread returns high priority unread notifications', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const highPriority = selectHighPriorityUnread(useNotificationStore.getState());

      expect(highPriority.every((n) => !n.isRead && n.priority === 'high')).toBe(true);
    });
  });
});
