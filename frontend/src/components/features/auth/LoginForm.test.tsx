import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginForm } from './LoginForm';
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
const mockRefresh = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    refresh: mockRefresh,
  }),
  useSearchParams: () => ({
    get: vi.fn(() => null),
  }),
}));

describe('LoginForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateClient.mockReturnValue(createMockSupabaseClient() as unknown as ReturnType<typeof createClient>);
  });

  it('renders login form with password and magic link tabs', () => {
    render(<LoginForm />);

    expect(screen.getByRole('tab', { name: /password/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /magic link/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument();
  });

  it('shows validation error for empty email', async () => {
    render(<LoginForm />);

    const submitButton = screen.getByRole('button', { name: /^sign in$/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for empty password when email is provided', async () => {
    render(<LoginForm />);

    // Use specific ID for email in password tab
    const emailInput = screen.getByLabelText('Email', { selector: '#email-password' });
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitButton = screen.getByRole('button', { name: /^sign in$/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  it('calls signInWithPassword on valid form submission', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<LoginForm />);

    // Use specific IDs for password tab inputs
    const emailInput = screen.getByLabelText('Email', { selector: '#email-password' });
    const passwordInput = document.getElementById('password') as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    const submitButton = screen.getByRole('button', { name: /^sign in$/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockClient.auth.signInWithPassword).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
  });

  it('navigates to dashboard on successful login', async () => {
    render(<LoginForm />);

    // Use specific IDs for password tab inputs
    const emailInput = screen.getByLabelText('Email', { selector: '#email-password' });
    const passwordInput = document.getElementById('password') as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    const submitButton = screen.getByRole('button', { name: /^sign in$/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/');
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  it('shows error message for invalid credentials', async () => {
    const mockClient = createMockSupabaseClient({
      signInError: new Error('Invalid login credentials'),
    });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<LoginForm />);

    // Use specific IDs for password tab inputs
    const emailInput = screen.getByLabelText('Email', { selector: '#email-password' });
    const passwordInput = document.getElementById('password') as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });

    const submitButton = screen.getByRole('button', { name: /^sign in$/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });

  it('calls signInWithOtp when magic link tab is used', async () => {
    const user = userEvent.setup();
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<LoginForm />);

    // Switch to magic link tab using userEvent for realistic interaction
    const magicLinkTab = screen.getByRole('tab', { name: /magic link/i });
    await user.click(magicLinkTab);

    // The magic link tab should now be selected
    await waitFor(() => {
      expect(magicLinkTab).toHaveAttribute('aria-selected', 'true');
    });

    // Find the "Send Magic Link" button
    const sendButton = await screen.findByRole('button', { name: /send magic link/i });

    // Fill in email in the magic link form
    const emailInput = document.getElementById('email-magic') as HTMLInputElement;
    await user.type(emailInput, 'test@example.com');

    await user.click(sendButton);

    await waitFor(() => {
      expect(mockClient.auth.signInWithOtp).toHaveBeenCalledWith({
        email: "test@example.com",
        options: {
          emailRedirectTo: expect.stringContaining("/auth/callback"),
          shouldCreateUser: true,
        },
      });
    });
  });

  it('has link to signup page', () => {
    render(<LoginForm />);

    const signupLink = screen.getByRole('link', { name: /sign up/i });
    expect(signupLink).toHaveAttribute('href', '/signup');
  });
});
