import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProfileSection } from '../ProfileSection';

// Mock the hooks
const mockUpdateProfile = vi.fn();

vi.mock('@/hooks/useUserProfile', () => ({
  useUserProfile: () => ({
    profile: {
      email: 'test@example.com',
      fullName: 'Test User',
      avatarUrl: null,
    },
    isLoading: false,
    updateProfile: mockUpdateProfile,
    isUpdating: false,
    updateError: null,
  }),
}));

describe('ProfileSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdateProfile.mockResolvedValue({ success: true });
  });

  it('renders profile section with user data', () => {
    render(<ProfileSection />);

    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test User')).toBeInTheDocument();
  });

  it('displays email as disabled (read-only)', () => {
    render(<ProfileSection />);

    const emailInput = screen.getByDisplayValue('test@example.com');
    expect(emailInput).toBeDisabled();
  });

  it('allows editing full name', async () => {
    const user = userEvent.setup();
    render(<ProfileSection />);

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'New Name');

    expect(screen.getByDisplayValue('New Name')).toBeInTheDocument();
  });

  it('shows save button', () => {
    render(<ProfileSection />);

    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });

  it('enables save button when name is changed', async () => {
    const user = userEvent.setup();
    render(<ProfileSection />);

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'New Name');

    const saveButton = screen.getByRole('button', { name: /save/i });
    expect(saveButton).not.toBeDisabled();
  });

  it('calls updateProfile when save is clicked', async () => {
    const user = userEvent.setup();
    render(<ProfileSection />);

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'New Name');

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith({ fullName: 'New Name' });
    });
  });

  it('displays avatar with initials when no avatar URL', () => {
    render(<ProfileSection />);

    // Should show initials TU for "Test User"
    expect(screen.getByText('TU')).toBeInTheDocument();
  });

  it('shows email cannot be changed message', () => {
    render(<ProfileSection />);

    expect(screen.getByText(/email cannot be changed/i)).toBeInTheDocument();
  });
});
