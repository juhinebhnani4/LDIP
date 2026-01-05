import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ResetPasswordForm } from './ResetPasswordForm';
import { createMockSupabaseClient } from '@/tests/mocks/supabase';

// Mock the Supabase client module
vi.mock('@/lib/supabase/client', () => ({
  createClient: vi.fn(),
}));

// Import after mocking
import { createClient } from '@/lib/supabase/client';
const mockedCreateClient = vi.mocked(createClient);

// Mock router
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe('ResetPasswordForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mockedCreateClient.mockReturnValue(
      createMockSupabaseClient() as unknown as ReturnType<typeof createClient>
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the reset password form', () => {
    render(<ResetPasswordForm />);

    expect(screen.getByText(/set new password/i)).toBeInTheDocument();
    expect(screen.getByLabelText('New Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument();
  });

  it('shows validation error for password too short', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText(/new password/i);
    fireEvent.change(passwordInput, { target: { value: 'short' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for password missing uppercase', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText(/new password/i);
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password must contain at least one uppercase letter/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for password missing lowercase', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText(/new password/i);
    fireEvent.change(passwordInput, { target: { value: 'PASSWORD123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password must contain at least one lowercase letter/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for password missing number', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText(/new password/i);
    fireEvent.change(passwordInput, { target: { value: 'Passwordabc' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password must contain at least one number/i)).toBeInTheDocument();
    });
  });

  it('shows validation error when passwords do not match', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');

    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'DifferentPass123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it('calls updateUser on valid form submission', async () => {
    vi.useRealTimers();
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');

    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'ValidPass123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockClient.auth.updateUser).toHaveBeenCalledWith({
        password: 'ValidPass123',
      });
    });
  });

  it('shows success message after password reset', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');

    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'ValidPass123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password reset successful/i)).toBeInTheDocument();
      expect(screen.getByText(/redirecting to login/i)).toBeInTheDocument();
    });
  });

  it('redirects to login after successful reset', async () => {
    vi.useRealTimers(); // Use real timers for this test
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');

    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'ValidPass123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    // Wait for success state - the redirect is triggered with a 3s setTimeout
    await waitFor(() => {
      expect(screen.getByText(/password reset successful/i)).toBeInTheDocument();
    });

    // Verify success UI shows redirect message
    expect(screen.getByText(/redirecting to login/i)).toBeInTheDocument();

    // Wait for the 3 second timeout to trigger the redirect
    await waitFor(
      () => {
        expect(mockPush).toHaveBeenCalledWith('/login?password_reset=success');
      },
      { timeout: 4000 }
    );
  });

  it('shows error message for expired token', async () => {
    vi.useRealTimers();
    const mockClient = createMockSupabaseClient({
      updateUserError: new Error('Token has expired'),
    });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');

    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'ValidPass123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/this reset link has expired or already been used/i)
      ).toBeInTheDocument();
    });
  });

  it('shows loading state during submission', async () => {
    vi.useRealTimers();
    // Create a mock that never resolves to test loading state
    const mockClient = createMockSupabaseClient();
    mockClient.auth.updateUser = vi.fn().mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');

    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'ValidPass123' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /resetting/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /resetting/i })).toBeDisabled();
    });
  });

  it('toggles password visibility', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText(/new password/i);
    expect(passwordInput).toHaveAttribute('type', 'password');

    // Find visibility toggle buttons (there are two - one for each password field)
    const toggleButtons = screen.getAllByRole('button').filter((button) => {
      // Filter for buttons that contain eye icons (not the submit button)
      return button.querySelector('svg') !== null;
    });

    // Click the first toggle button (for new password field)
    fireEvent.click(toggleButtons[0]);

    await waitFor(() => {
      expect(passwordInput).toHaveAttribute('type', 'text');
    });

    // Toggle back
    fireEvent.click(toggleButtons[0]);

    await waitFor(() => {
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });

  it('clears error when user starts typing', async () => {
    vi.useRealTimers();
    render(<ResetPasswordForm />);

    const passwordInput = screen.getByLabelText(/new password/i);
    fireEvent.change(passwordInput, { target: { value: 'short' } });

    const submitButton = screen.getByRole('button', { name: /reset password/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
    });

    // Start typing again
    fireEvent.change(passwordInput, { target: { value: 'ValidPass123' } });

    await waitFor(() => {
      expect(screen.queryByText(/password must be at least 8 characters/i)).not.toBeInTheDocument();
    });
  });
});
