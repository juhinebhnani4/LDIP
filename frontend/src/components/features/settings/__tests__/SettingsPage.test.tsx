import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock the section components
vi.mock('../ProfileSection', () => ({
  ProfileSection: () => <div data-testid="profile-section">ProfileSection</div>,
}));

vi.mock('../NotificationSection', () => ({
  NotificationSection: () => <div data-testid="notification-section">NotificationSection</div>,
}));

vi.mock('../AppearanceSection', () => ({
  AppearanceSection: () => <div data-testid="appearance-section">AppearanceSection</div>,
}));

vi.mock('../AccountSection', () => ({
  AccountSection: () => <div data-testid="account-section">AccountSection</div>,
}));

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    back: vi.fn(),
    push: vi.fn(),
  }),
}));

// Import after mocks
import SettingsPage from '@/app/settings/page';

describe('SettingsPage', () => {
  it('renders page title', () => {
    render(<SettingsPage />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders back link', () => {
    render(<SettingsPage />);

    expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument();
  });

  it('renders all settings sections', () => {
    render(<SettingsPage />);

    expect(screen.getByTestId('profile-section')).toBeInTheDocument();
    expect(screen.getByTestId('notification-section')).toBeInTheDocument();
    expect(screen.getByTestId('appearance-section')).toBeInTheDocument();
    expect(screen.getByTestId('account-section')).toBeInTheDocument();
  });

  it('sections are in correct order', () => {
    render(<SettingsPage />);

    const sections = screen.getAllByTestId(/-section$/);
    expect(sections[0]).toHaveAttribute('data-testid', 'profile-section');
    expect(sections[1]).toHaveAttribute('data-testid', 'notification-section');
    expect(sections[2]).toHaveAttribute('data-testid', 'appearance-section');
    expect(sections[3]).toHaveAttribute('data-testid', 'account-section');
  });

  it('has proper heading hierarchy', () => {
    render(<SettingsPage />);

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('Settings');
  });
});
