import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AccountSection } from '../AccountSection';

// Mock next/navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock Supabase client
const mockSignOut = vi.fn();
vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      signOut: mockSignOut,
    },
  }),
}));

// Mock fetch for logout API
global.fetch = vi.fn();

describe('AccountSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSignOut.mockResolvedValue({ error: null });
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true });
  });

  it('renders account section', () => {
    render(<AccountSection />);

    expect(screen.getByText('Account')).toBeInTheDocument();
  });

  it('displays change password option', () => {
    render(<AccountSection />);

    expect(screen.getByText(/change password/i)).toBeInTheDocument();
  });

  it('displays sign out buttons', () => {
    render(<AccountSection />);

    // Should have both regular sign out and sign out all devices
    expect(screen.getByRole('button', { name: /^Sign Out$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign out all/i })).toBeInTheDocument();
  });

  it('displays delete account option', () => {
    render(<AccountSection />);

    expect(screen.getByText(/delete account/i)).toBeInTheDocument();
  });

  it('calls signOut when sign out button is clicked', async () => {
    const user = userEvent.setup();
    render(<AccountSection />);

    const signOutButton = screen.getByRole('button', { name: /^Sign Out$/i });
    await user.click(signOutButton);

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
    });
  });

  it('redirects to login after sign out', async () => {
    const user = userEvent.setup();
    render(<AccountSection />);

    const signOutButton = screen.getByRole('button', { name: /^Sign Out$/i });
    await user.click(signOutButton);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/login');
    });
  });

  it('shows delete account section with warning text', () => {
    render(<AccountSection />);

    // Delete Account text and warning should be present
    expect(screen.getByText('Delete Account')).toBeInTheDocument();
    expect(screen.getByText(/permanently delete your account/i)).toBeInTheDocument();
  });

  it('renders the account section with all options', () => {
    render(<AccountSection />);

    // Verify all account options are present
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.getByText(/change your account password/i)).toBeInTheDocument();
    // Sign Out appears both as label and button text
    expect(screen.getAllByText('Sign Out').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Sign Out All Devices')).toBeInTheDocument();
    expect(screen.getByText('Delete Account')).toBeInTheDocument();
  });

  it('has delete account section with destructive styling', () => {
    render(<AccountSection />);

    // The delete account text should have destructive styling
    const deleteText = screen.getByText('Delete Account');
    expect(deleteText).toHaveClass('text-destructive');
  });

  it('shows sign out all devices option', () => {
    render(<AccountSection />);

    expect(screen.getByText('Sign Out All Devices')).toBeInTheDocument();
    expect(screen.getByText(/sign out from all logged in devices/i)).toBeInTheDocument();
  });

  it('disables sign out button while signing out', async () => {
    mockSignOut.mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 100))
    );
    const user = userEvent.setup();
    render(<AccountSection />);

    const signOutButton = screen.getByRole('button', { name: /^Sign Out$/i });
    await user.click(signOutButton);

    expect(signOutButton).toBeDisabled();
  });
});
