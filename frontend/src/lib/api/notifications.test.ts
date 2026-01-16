import { describe, test, expect, vi, beforeEach } from 'vitest';
import { getNotifications, markNotificationRead, markAllNotificationsRead } from './notifications';
import { api } from './client';

/**
 * Tests for Notification API client.
 * Story 14.10: Notifications Backend & Frontend Wiring
 */

// Mock the API client
vi.mock('./client', () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));

const mockApiGet = vi.mocked(api.get);
const mockApiPatch = vi.mocked(api.patch);
const mockApiPost = vi.mocked(api.post);

describe('notifications API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getNotifications', () => {
    const mockNotificationsResponse = {
      data: [
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
      ],
      unreadCount: 2,
    };

    test('calls correct API endpoint without options', async () => {
      mockApiGet.mockResolvedValue(mockNotificationsResponse);

      await getNotifications();

      expect(mockApiGet).toHaveBeenCalledWith('/api/notifications');
    });

    test('calls correct API endpoint with limit', async () => {
      mockApiGet.mockResolvedValue(mockNotificationsResponse);

      await getNotifications({ limit: 10 });

      expect(mockApiGet).toHaveBeenCalledWith('/api/notifications?limit=10');
    });

    test('calls correct API endpoint with unreadOnly', async () => {
      mockApiGet.mockResolvedValue(mockNotificationsResponse);

      await getNotifications({ unreadOnly: true });

      expect(mockApiGet).toHaveBeenCalledWith('/api/notifications?unread_only=true');
    });

    test('calls correct API endpoint with multiple options', async () => {
      mockApiGet.mockResolvedValue(mockNotificationsResponse);

      await getNotifications({ limit: 5, unreadOnly: true });

      expect(mockApiGet).toHaveBeenCalledWith('/api/notifications?limit=5&unread_only=true');
    });

    test('returns notifications and unread count', async () => {
      mockApiGet.mockResolvedValue(mockNotificationsResponse);

      const result = await getNotifications();

      expect(result.notifications).toHaveLength(2);
      expect(result.unreadCount).toBe(2);
      expect(result.notifications[0].id).toBe('notif-1');
      expect(result.notifications[0].isRead).toBe(false);
    });

    test('returns empty array when no notifications', async () => {
      mockApiGet.mockResolvedValue({ data: [], unreadCount: 0 });

      const result = await getNotifications();

      expect(result.notifications).toEqual([]);
      expect(result.unreadCount).toBe(0);
    });
  });

  describe('markNotificationRead', () => {
    const mockUpdatedNotification = {
      data: {
        id: 'notif-1',
        type: 'success',
        title: 'Processing Complete',
        message: 'Document has been processed.',
        matterId: 'matter-123',
        matterTitle: 'Smith vs. Jones',
        isRead: true, // Now marked as read
        createdAt: '2026-01-16T10:00:00Z',
        priority: 'medium',
      },
    };

    test('calls correct API endpoint', async () => {
      mockApiPatch.mockResolvedValue(mockUpdatedNotification);

      await markNotificationRead('notif-1');

      expect(mockApiPatch).toHaveBeenCalledWith('/api/notifications/notif-1/read', {});
    });

    test('returns updated notification with isRead true', async () => {
      mockApiPatch.mockResolvedValue(mockUpdatedNotification);

      const result = await markNotificationRead('notif-1');

      expect(result.id).toBe('notif-1');
      expect(result.isRead).toBe(true);
    });

    test('handles notification not found error', async () => {
      mockApiPatch.mockRejectedValue(new Error('Notification not found'));

      await expect(markNotificationRead('nonexistent-id')).rejects.toThrow(
        'Notification not found'
      );
    });
  });

  describe('markAllNotificationsRead', () => {
    test('calls correct API endpoint', async () => {
      mockApiPost.mockResolvedValue({ count: 5 });

      await markAllNotificationsRead();

      expect(mockApiPost).toHaveBeenCalledWith('/api/notifications/read-all', {});
    });

    test('returns count of notifications marked as read', async () => {
      mockApiPost.mockResolvedValue({ count: 5 });

      const result = await markAllNotificationsRead();

      expect(result).toBe(5);
    });

    test('returns 0 when no unread notifications', async () => {
      mockApiPost.mockResolvedValue({ count: 0 });

      const result = await markAllNotificationsRead();

      expect(result).toBe(0);
    });
  });
});
