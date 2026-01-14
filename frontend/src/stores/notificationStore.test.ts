import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useNotificationStore, selectUnreadNotifications, selectHighPriorityUnread } from './notificationStore';
import type { NotificationType, NotificationPriority } from '@/types/notification';

describe('notificationStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useNotificationStore.setState({
      notifications: [],
      unreadCount: 0,
      isLoading: false,
      error: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
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
  });

  describe('markAsRead', () => {
    it('marks a specific notification as read', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const initialState = useNotificationStore.getState();
      const unreadNotification = initialState.notifications.find((n) => !n.isRead);
      expect(unreadNotification).toBeDefined();

      if (unreadNotification) {
        useNotificationStore.getState().markAsRead(unreadNotification.id);

        const updatedNotification = useNotificationStore
          .getState()
          .notifications.find((n) => n.id === unreadNotification.id);
        expect(updatedNotification?.isRead).toBe(true);
      }
    });

    it('decreases unread count when marking as read', async () => {
      await useNotificationStore.getState().fetchNotifications();

      const initialUnreadCount = useNotificationStore.getState().unreadCount;
      const unreadNotification = useNotificationStore
        .getState()
        .notifications.find((n) => !n.isRead);

      if (unreadNotification) {
        useNotificationStore.getState().markAsRead(unreadNotification.id);

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

        useNotificationStore.getState().markAsRead(readNotification.id);

        expect(useNotificationStore.getState().unreadCount).toBe(initialUnreadCount);
      }
    });
  });

  describe('markAllAsRead', () => {
    it('marks all notifications as read', async () => {
      await useNotificationStore.getState().fetchNotifications();

      useNotificationStore.getState().markAllAsRead();

      const allRead = useNotificationStore
        .getState()
        .notifications.every((n) => n.isRead);
      expect(allRead).toBe(true);
    });

    it('sets unread count to 0', async () => {
      await useNotificationStore.getState().fetchNotifications();
      expect(useNotificationStore.getState().unreadCount).toBeGreaterThan(0);

      useNotificationStore.getState().markAllAsRead();

      expect(useNotificationStore.getState().unreadCount).toBe(0);
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
