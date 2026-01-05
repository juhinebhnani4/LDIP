import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import ResetPasswordPage from './page';

// Mock the ResetPasswordForm component
vi.mock('@/components/features/auth/ResetPasswordForm', () => ({
  ResetPasswordForm: () => <div data-testid="reset-password-form">Mocked Reset Password Form</div>,
}));

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders reset password page with form when no error', () => {
    render(<ResetPasswordPage />);

    expect(screen.getByRole('heading', { name: /reset password/i })).toBeInTheDocument();
    expect(screen.getByText(/enter your new password below/i)).toBeInTheDocument();
    expect(screen.getByTestId('reset-password-form')).toBeInTheDocument();
  });

  it('shows error message for invalid_link error', () => {
    render(<ResetPasswordPage searchParams={{ error: 'invalid_link' }} />);

    expect(screen.getByRole('heading', { name: /reset password/i })).toBeInTheDocument();
    expect(screen.getByText(/there was a problem with your reset link/i)).toBeInTheDocument();
    expect(screen.getByText(/this reset link has expired or already been used/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /request a new reset link/i })).toBeInTheDocument();
  });

  it('shows error message for expired error', () => {
    render(<ResetPasswordPage searchParams={{ error: 'expired' }} />);

    expect(screen.getByText(/this reset link has expired/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /request a new reset link/i })).toBeInTheDocument();
  });

  it('shows error message for no_session error', () => {
    render(<ResetPasswordPage searchParams={{ error: 'no_session' }} />);

    expect(screen.getByText(/unable to verify your identity/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /request a new reset link/i })).toBeInTheDocument();
  });

  it('shows generic error for unknown error type', () => {
    render(<ResetPasswordPage searchParams={{ error: 'unknown_error' }} />);

    expect(screen.getByText(/an error occurred. please try again/i)).toBeInTheDocument();
  });

  it('does not show form when there is an error', () => {
    render(<ResetPasswordPage searchParams={{ error: 'invalid_link' }} />);

    expect(screen.queryByTestId('reset-password-form')).not.toBeInTheDocument();
  });

  it('link to forgot-password page is correct', () => {
    render(<ResetPasswordPage searchParams={{ error: 'invalid_link' }} />);

    const link = screen.getByRole('link', { name: /request a new reset link/i });
    expect(link).toHaveAttribute('href', '/forgot-password');
  });
});
