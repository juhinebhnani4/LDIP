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

describe('DashboardHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the LDIP logo', () => {
    render(<DashboardHeader />);

    expect(screen.getByText('LDIP')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /ldip home/i })).toHaveAttribute('href', '/');
  });

  it('renders all header components', () => {
    render(<DashboardHeader />);

    expect(screen.getByTestId('global-search')).toBeInTheDocument();
    expect(screen.getByTestId('notifications-dropdown')).toBeInTheDocument();
    expect(screen.getByTestId('user-profile-dropdown')).toBeInTheDocument();
  });

  it('renders help button with correct aria-label', () => {
    render(<DashboardHeader />);

    const helpButton = screen.getByRole('button', { name: /help/i });
    expect(helpButton).toBeInTheDocument();
  });

  it('opens help link in new tab when help button clicked', () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

    render(<DashboardHeader />);

    const helpButton = screen.getByRole('button', { name: /help/i });
    helpButton.click();

    expect(windowOpenSpy).toHaveBeenCalledWith('https://help.ldip.app', '_blank');
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
