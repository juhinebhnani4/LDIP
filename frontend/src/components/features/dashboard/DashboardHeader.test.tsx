import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DashboardHeader } from './DashboardHeader';

// Mock the child components
vi.mock('./NotificationsDropdown', () => ({
  NotificationsDropdown: () => <div data-testid="notifications-dropdown">Notifications</div>,
}));

vi.mock('./UserProfileDropdown', () => ({
  UserProfileDropdown: ({ initialUser }: { initialUser?: { email: string | null; fullName: string | null } }) => (
    <div data-testid="user-profile-dropdown">
      {initialUser?.fullName ?? initialUser?.email ?? 'User'}
    </div>
  ),
}));

vi.mock('./GlobalSearch', () => ({
  GlobalSearch: () => <div data-testid="global-search">Search</div>,
}));

vi.mock('@/components/features/help', () => ({
  HelpButton: (props: { 'data-tour'?: string }) => (
    <button data-testid="help-button" data-tour={props['data-tour']} aria-label="Help">
      Help
    </button>
  ),
}));

describe('DashboardHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the jaanch logo', () => {
    render(<DashboardHeader />);

    expect(screen.getByRole('link', { name: /jaanch\.ai home/i })).toHaveAttribute('href', '/');
  });

  it('renders all header components', () => {
    render(<DashboardHeader />);

    expect(screen.getByTestId('global-search')).toBeInTheDocument();
    expect(screen.getByTestId('notifications-dropdown')).toBeInTheDocument();
    expect(screen.getByTestId('user-profile-dropdown')).toBeInTheDocument();
  });

  it('renders help button with correct aria-label', () => {
    render(<DashboardHeader />);

    const helpButton = screen.getByTestId('help-button');
    expect(helpButton).toBeInTheDocument();
    expect(helpButton).toHaveAttribute('aria-label', 'Help');
  });

  it('renders help button with data-tour attribute', () => {
    render(<DashboardHeader />);

    const helpButton = screen.getByTestId('help-button');
    expect(helpButton).toHaveAttribute('data-tour', 'help-button');
  });

  it('passes user data to UserProfileDropdown', () => {
    const user = {
      email: 'test@example.com',
      fullName: 'Test User',
    };

    render(<DashboardHeader user={user} />);

    expect(screen.getByText('Test User')).toBeInTheDocument();
  });

  it('has sticky positioning with proper z-index', () => {
    render(<DashboardHeader />);

    const header = screen.getByRole('banner');
    expect(header).toHaveClass('sticky');
    expect(header).toHaveClass('top-0');
    expect(header).toHaveClass('z-50');
  });
});
