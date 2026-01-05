import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LogoutButton } from './LogoutButton';
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
}));

describe('LogoutButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateClient.mockReturnValue(createMockSupabaseClient() as unknown as ReturnType<typeof createClient>);
  });

  it('renders logout button with default text', () => {
    render(<LogoutButton />);

    expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument();
  });

  it('calls signOut when clicked', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockClient.auth.signOut).toHaveBeenCalled();
    });
  });

  it('navigates to login after signout', async () => {
    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/login');
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  it('shows loading state during signout', async () => {
    const mockClient = createMockSupabaseClient();
    mockClient.auth.signOut = vi.fn(
      () => new Promise((resolve) => setTimeout(() => resolve({ error: null }), 100))
    );
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing out/i })).toBeInTheDocument();
    });
  });

  it('still navigates to login even if signOut fails', async () => {
    const mockClient = createMockSupabaseClient({
      signOutError: new Error('Sign out failed'),
    });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/login');
    });
  });

  it('accepts custom variant prop', () => {
    render(<LogoutButton variant="destructive" />);

    const button = screen.getByRole('button', { name: /sign out/i });
    expect(button).toBeInTheDocument();
  });

  it('can hide icon when showIcon is false', () => {
    render(<LogoutButton showIcon={false} />);

    const button = screen.getByRole('button', { name: /sign out/i });
    expect(button).toBeInTheDocument();
    // Icon is not rendered when showIcon is false
  });
});
