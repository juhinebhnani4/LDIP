import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NotificationsDropdown } from './NotificationsDropdown';
import { useNotificationStore } from '@/stores/notificationStore';
import type { Notification } from '@/types/notification';

// Mock the notification store
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn(),
}));

const mockNotifications: Notification[] = [
  {
    id: 'notif-1',
    type: 'success',
    title: 'Processing Complete',
    message: 'Document has been processed successfully.',
    matterId: 'matter-1',
    matterTitle: 'Smith vs. Jones',
    isRead: false,
    createdAt: new Date(Date.now() - 5 * 60000).toISOString(),
    priority: 'medium',
  },
  {
    id: 'notif-2',
    type: 'warning',
    title: 'Verification Needed',
    message: '3 citations require verification.',
    matterId: 'matter-1',
    matterTitle: 'Smith vs. Jones',
    isRead: false,
    createdAt: new Date(Date.now() - 30 * 60000).toISOString(),
    priority: 'high',
  },
];

describe('NotificationsDropdown', () => {
  const mockFetchNotifications = vi.fn().mockResolvedValue(undefined);
  const mockMarkAsRead = vi.fn();
  const mockMarkAllAsRead = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useNotificationStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (selector: (state: unknown) => unknown) => {
        const state = {
          notifications: mockNotifications,
          unreadCount: 2,
          isLoading: false,
          fetchNotifications: mockFetchNotifications,
          markAsRead: mockMarkAsRead,
          markAllAsRead: mockMarkAllAsRead,
        };
        return selector(state);
      }
    );
  });

  it('renders notification bell button', () => {
    render(<NotificationsDropdown />);

    const button = screen.getByRole('button', { name: /notifications/i });
    expect(button).toBeInTheDocument();
  });

  it('displays unread count badge when there are unread notifications', () => {
    render(<NotificationsDropdown />);

    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('does not display badge when no unread notifications', () => {
    (useNotificationStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (selector: (state: unknown) => unknown) => {
        const state = {
          notifications: [],
          unreadCount: 0,
          isLoading: false,
          fetchNotifications: mockFetchNotifications,
          markAsRead: mockMarkAsRead,
          markAllAsRead: mockMarkAllAsRead,
        };
        return selector(state);
      }
    );

    render(<NotificationsDropdown />);

    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  it('fetches notifications on mount', () => {
    render(<NotificationsDropdown />);

    expect(mockFetchNotifications).toHaveBeenCalled();
  });

  it('displays 99+ when unread count exceeds 99', () => {
    (useNotificationStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (selector: (state: unknown) => unknown) => {
        const state = {
          notifications: mockNotifications,
          unreadCount: 150,
          isLoading: false,
          fetchNotifications: mockFetchNotifications,
          markAsRead: mockMarkAsRead,
          markAllAsRead: mockMarkAllAsRead,
        };
        return selector(state);
      }
    );

    render(<NotificationsDropdown />);

    expect(screen.getByText('99+')).toBeInTheDocument();
  });

  it('button has correct aria-label with unread count', () => {
    render(<NotificationsDropdown />);

    const button = screen.getByRole('button', { name: /notifications \(2 unread\)/i });
    expect(button).toBeInTheDocument();
  });

  it('button shows aria-label without count when no unread', () => {
    (useNotificationStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (selector: (state: unknown) => unknown) => {
        const state = {
          notifications: [],
          unreadCount: 0,
          isLoading: false,
          fetchNotifications: mockFetchNotifications,
          markAsRead: mockMarkAsRead,
          markAllAsRead: mockMarkAllAsRead,
        };
        return selector(state);
      }
    );

    render(<NotificationsDropdown />);

    const button = screen.getByRole('button', { name: 'Notifications' });
    expect(button).toBeInTheDocument();
  });
});
