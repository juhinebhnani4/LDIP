import { vi } from 'vitest';

export const mockUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  user_metadata: {
    full_name: 'Test User',
    avatar_url: null,
  },
  created_at: '2024-01-01T00:00:00.000Z',
};

export const mockSession = {
  access_token: 'test-access-token',
  refresh_token: 'test-refresh-token',
  user: mockUser,
};

export const createMockSupabaseClient = (overrides?: {
  user?: typeof mockUser | null;
  session?: typeof mockSession | null;
  signInError?: Error | null;
  signUpError?: Error | null;
  signOutError?: Error | null;
  refreshError?: Error | null;
  resetPasswordError?: Error | null;
  updateUserError?: Error | null;
}) => {
  const {
    user = mockUser,
    session = mockSession,
    signInError = null,
    signUpError = null,
    signOutError = null,
    refreshError = null,
    resetPasswordError = null,
    updateUserError = null,
  } = overrides ?? {};

  // Track subscription callbacks for auth state changes
  const authStateCallbacks: ((event: string, session: typeof mockSession | null) => void)[] = [];

  return {
    auth: {
      signInWithPassword: vi.fn().mockResolvedValue({
        data: signInError ? null : { user, session },
        error: signInError,
      }),
      signInWithOtp: vi.fn().mockResolvedValue({
        data: signInError ? null : {},
        error: signInError,
      }),
      signInWithOAuth: vi.fn().mockResolvedValue({
        data: signInError ? null : { url: 'https://oauth.example.com' },
        error: signInError,
      }),
      signUp: vi.fn().mockResolvedValue({
        data: signUpError ? null : { user, session },
        error: signUpError,
      }),
      signOut: vi.fn().mockResolvedValue({
        error: signOutError,
      }),
      getUser: vi.fn().mockResolvedValue({
        data: { user },
        error: null,
      }),
      getSession: vi.fn().mockResolvedValue({
        data: { session },
        error: null,
      }),
      exchangeCodeForSession: vi.fn().mockResolvedValue({
        data: { session },
        error: null,
      }),
      refreshSession: vi.fn().mockResolvedValue({
        data: refreshError ? null : { session },
        error: refreshError,
      }),
      resetPasswordForEmail: vi.fn().mockResolvedValue({
        data: resetPasswordError ? null : {},
        error: resetPasswordError,
      }),
      updateUser: vi.fn().mockResolvedValue({
        data: updateUserError ? null : { user },
        error: updateUserError,
      }),
      verifyOtp: vi.fn().mockResolvedValue({
        data: signInError ? null : { user, session },
        error: signInError,
      }),
      onAuthStateChange: vi.fn().mockImplementation((callback) => {
        authStateCallbacks.push(callback);
        return {
          data: {
            subscription: {
              unsubscribe: vi.fn(),
            },
          },
        };
      }),
      // Helper to trigger auth state change in tests
      _triggerAuthStateChange: (event: string, newSession: typeof mockSession | null) => {
        authStateCallbacks.forEach((cb) => cb(event, newSession));
      },
    },
  };
};

export const mockCreateClient = vi.fn(() => createMockSupabaseClient());
