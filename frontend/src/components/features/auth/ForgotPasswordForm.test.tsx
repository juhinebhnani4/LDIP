import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ForgotPasswordForm } from './ForgotPasswordForm';
import { createMockSupabaseClient } from '@/tests/mocks/supabase';

// Mock the Supabase client module
vi.mock('@/lib/supabase/client', () => ({
  createClient: vi.fn(),
}));

// Import after mocking
import { createClient } from '@/lib/supabase/client';
const mockedCreateClient = vi.mocked(createClient);

describe('ForgotPasswordForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateClient.mockReturnValue(
      createMockSupabaseClient() as unknown as ReturnType<typeof createClient>
    );
    // Mock window.location.origin
    Object.defineProperty(window, 'location', {
      value: { origin: 'http://localhost:3000' },
      writable: true,
    });
  });

  it('renders the forgot password form', () => {
    render(<ForgotPasswordForm />);

    // CardTitle is a div, not a heading - test by text content
    expect(screen.getByText('Reset Your Password')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to login/i })).toBeInTheDocument();
  });

  it('shows validation error for empty email', async () => {
    render(<ForgotPasswordForm />);

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid email format', async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    // Use an email without @ sign - clearly invalid
    await user.clear(emailInput);
    await user.type(emailInput, 'notanemail');

    const form = emailInput.closest('form');
    expect(form).toBeTruthy();

    // Submit the form directly
    fireEvent.submit(form!);

    // Check for validation error
    await waitFor(() => {
      expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument();
    });
  });

  it('calls resetPasswordForEmail on valid form submission', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockClient.auth.resetPasswordForEmail).toHaveBeenCalledWith('test@example.com', {
        redirectTo: 'http://localhost:3000/auth/callback?type=recovery',
      });
    });
  });

  it('shows success message after email sent', async () => {
    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/if an account exists with this email, you will receive password reset instructions/i)
      ).toBeInTheDocument();
    });
  });

  it('shows email confirmation view after submission', async () => {
    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/sent to:/i)).toBeInTheDocument();
      expect(screen.getByText(/test@example.com/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /resend email/i })).toBeInTheDocument();
    });
  });

  it('shows loading state during submission', async () => {
    // Create a mock that never resolves to test loading state
    const mockClient = createMockSupabaseClient();
    mockClient.auth.resetPasswordForEmail = vi.fn().mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sending/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    });
  });

  it('shows error message on API failure', async () => {
    const mockClient = createMockSupabaseClient({
      resetPasswordError: new Error('Rate limit exceeded'),
    });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/rate limit exceeded/i)).toBeInTheDocument();
    });
  });

  it('allows changing email after initial submission', async () => {
    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /send reset link/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /resend email/i })).toBeInTheDocument();
    });

    const changeEmailButton = screen.getByRole('button', { name: /use a different email/i });
    fireEvent.click(changeEmailButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
    });
  });

  it('has link to login page', () => {
    render(<ForgotPasswordForm />);

    const loginLink = screen.getByRole('link', { name: /back to login/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });
});
