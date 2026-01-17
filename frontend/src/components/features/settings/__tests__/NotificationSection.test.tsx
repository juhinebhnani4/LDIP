import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NotificationSection } from '../NotificationSection';

// Mock the hooks
const mockUpdatePreferences = vi.fn();

vi.mock('@/hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    preferences: {
      emailNotificationsProcessing: true,
      emailNotificationsVerification: true,
      browserNotifications: false,
    },
    isLoading: false,
    error: null,
    updatePreferences: mockUpdatePreferences,
    isUpdating: false,
    updateError: null,
  }),
}));

// Mock Notification API
const mockRequestPermission = vi.fn();
Object.defineProperty(window, 'Notification', {
  value: {
    permission: 'default',
    requestPermission: mockRequestPermission,
  },
  writable: true,
});

describe('NotificationSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdatePreferences.mockResolvedValue({ success: true });
    mockRequestPermission.mockResolvedValue('granted');
  });

  it('renders notification section with toggles', () => {
    render(<NotificationSection />);

    expect(screen.getByText('Notifications')).toBeInTheDocument();
    expect(screen.getByText('Document Processing')).toBeInTheDocument();
    expect(screen.getByText('Verification Reminders')).toBeInTheDocument();
    expect(screen.getByText('Browser Notifications')).toBeInTheDocument();
  });

  it('displays current preference states', () => {
    render(<NotificationSection />);

    const toggles = screen.getAllByRole('switch');
    expect(toggles).toHaveLength(3);

    // First two should be checked (true), third unchecked (false)
    expect(toggles[0]!).toHaveAttribute('data-state', 'checked');
    expect(toggles[1]!).toHaveAttribute('data-state', 'checked');
    expect(toggles[2]!).toHaveAttribute('data-state', 'unchecked');
  });

  it('calls updatePreferences when toggle is clicked', async () => {
    const user = userEvent.setup();
    render(<NotificationSection />);

    const toggles = screen.getAllByRole('switch');
    await user.click(toggles[0]!);

    await waitFor(() => {
      expect(mockUpdatePreferences).toHaveBeenCalledWith({
        emailNotificationsProcessing: false,
      });
    });
  });

  it('requests browser notification permission when enabling', async () => {
    const user = userEvent.setup();
    render(<NotificationSection />);

    const browserToggle = screen.getAllByRole('switch')[2]!;
    await user.click(browserToggle);

    await waitFor(() => {
      expect(mockRequestPermission).toHaveBeenCalled();
    });
  });

  it('does not enable browser notifications if permission denied', async () => {
    mockRequestPermission.mockResolvedValue('denied');
    const user = userEvent.setup();
    render(<NotificationSection />);

    const browserToggle = screen.getAllByRole('switch')[2]!;
    await user.click(browserToggle);

    await waitFor(() => {
      expect(mockUpdatePreferences).not.toHaveBeenCalledWith({
        browserNotifications: true,
      });
    });
  });

  it('shows section description', () => {
    render(<NotificationSection />);

    expect(screen.getByText(/control how you receive/i)).toBeInTheDocument();
  });

  it('has toggle for each notification type', () => {
    render(<NotificationSection />);

    // Should have 3 notification toggles
    const toggles = screen.getAllByRole('switch');
    expect(toggles.length).toBe(3);
  });
});
