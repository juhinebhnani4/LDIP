'use client';

import { useEffect, useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { User, Session } from '@supabase/supabase-js';

/**
 * Hook to manage and subscribe to session state.
 *
 * Story 3.5: Token refresh is handled by the API client (client.ts)
 * which proactively refreshes tokens before each request when needed.
 * This hook focuses on subscribing to auth state changes only.
 *
 * Code Review Fix: Removed duplicate interval-based refresh that conflicted
 * with client.ts proactive refresh (different thresholds caused redundant calls).
 *
 * @returns Object containing session, loading state, and error
 */
export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const supabase = createClient();

    // Get initial session
    supabase.auth.getSession().then(({ data: { session }, error }) => {
      if (error) {
        setError(error);
      } else {
        setSession(session);
      }
      setLoading(false);
    });

    // Listen for auth changes (including refreshes triggered by API client)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setError(null);
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  return { session, loading, error };
}

/**
 * Hook to get the current user.
 *
 * Subscribes to auth state changes and provides the current user object.
 *
 * @returns Object containing user, loading state, and error
 */
export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getUser().then(({ data: { user }, error }) => {
      if (error) {
        setError(error);
      } else {
        setUser(user);
      }
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null);
        setError(null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  return { user, loading, error };
}

/**
 * Hook for auth actions like sign out and refresh.
 *
 * Provides methods for signing out and manually refreshing the session.
 *
 * @returns Object containing auth action methods
 */
export function useAuthActions() {
  const [loading, setLoading] = useState(false);

  const signOut = useCallback(async () => {
    setLoading(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signOut();
      if (error) throw error;

      // Redirect to login via the logout route to clear cookies
      if (typeof window !== 'undefined') {
        window.location.href = '/auth/logout';
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSession = useCallback(async () => {
    setLoading(true);
    try {
      const supabase = createClient();
      const { data: { session }, error } = await supabase.auth.refreshSession();
      if (error) throw error;
      return session;
    } finally {
      setLoading(false);
    }
  }, []);

  return { signOut, refreshSession, loading };
}

/**
 * Combined hook for common auth patterns.
 *
 * Provides user, session, loading state, and auth actions in one hook.
 * Use this for components that need full auth context.
 *
 * @returns Combined auth state and actions
 */
export function useAuth() {
  const { session, loading: sessionLoading, error: sessionError } = useSession();
  const { user, loading: userLoading, error: userError } = useUser();
  const { signOut, refreshSession, loading: actionLoading } = useAuthActions();

  return {
    user,
    session,
    loading: sessionLoading || userLoading,
    actionLoading,
    error: sessionError || userError,
    signOut,
    refreshSession,
    isAuthenticated: !!session && !!user,
  };
}
