import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useSession, useUser, useAuthActions, useAuth } from './useAuth';
import { createMockSupabaseClient, mockSession, mockUser } from '@/tests/mocks/supabase';

// Mock the Supabase client module
vi.mock('@/lib/supabase/client', () => ({
  createClient: vi.fn(),
}));

// Import after mocking
import { createClient } from '@/lib/supabase/client';
const mockedCreateClient = vi.mocked(createClient);

describe('useSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns session from Supabase', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useSession());

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.session).toEqual(mockSession);
    expect(result.current.error).toBeNull();
  });

  it('returns null session when not authenticated', async () => {
    const mockClient = createMockSupabaseClient({ session: null });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useSession());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.session).toBeNull();
  });

  it('sets up auth state change listener', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    renderHook(() => useSession());

    await waitFor(() => {
      expect(mockClient.auth.onAuthStateChange).toHaveBeenCalled();
    });
  });

  it('cleans up subscription on unmount', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { unmount } = renderHook(() => useSession());

    await waitFor(() => {
      expect(mockClient.auth.onAuthStateChange).toHaveBeenCalled();
    });

    // Get the subscription from the mock
    const mockResults = mockClient.auth.onAuthStateChange.mock.results;
    expect(mockResults[0]).toBeDefined();
    const subscriptionResult = mockResults[0]!.value;
    const unsubscribe = subscriptionResult.data.subscription.unsubscribe;

    unmount();

    expect(unsubscribe).toHaveBeenCalled();
  });
});

describe('useUser', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns user from Supabase', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useUser());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.error).toBeNull();
  });

  it('returns null user when not authenticated', async () => {
    const mockClient = createMockSupabaseClient({ user: null });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useUser());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.user).toBeNull();
  });
});

describe('useAuthActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock window.location
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });
  });

  it('provides signOut function', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useAuthActions());

    expect(typeof result.current.signOut).toBe('function');
  });

  it('provides refreshSession function', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useAuthActions());

    expect(typeof result.current.refreshSession).toBe('function');
  });

  it('refreshSession calls Supabase refreshSession', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useAuthActions());

    await act(async () => {
      await result.current.refreshSession();
    });

    expect(mockClient.auth.refreshSession).toHaveBeenCalled();
  });

  it('refreshSession returns the new session', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useAuthActions());

    let newSession;
    await act(async () => {
      newSession = await result.current.refreshSession();
    });

    expect(newSession).toEqual(mockSession);
  });
});

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });
  });

  it('returns combined auth state', async () => {
    const mockClient = createMockSupabaseClient();
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.session).toEqual(mockSession);
    expect(result.current.isAuthenticated).toBe(true);
    expect(typeof result.current.signOut).toBe('function');
    expect(typeof result.current.refreshSession).toBe('function');
  });

  it('isAuthenticated is false when no session', async () => {
    const mockClient = createMockSupabaseClient({ session: null, user: null });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
  });
});
