'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { adminQuotaApi } from '@/lib/api/admin-quota';

/**
 * State returned by the useAdminStatus hook.
 *
 * F1, F2, F3 fix: Runtime admin check instead of build-time env var.
 */
export interface AdminStatusState {
  /** Whether the current user is an admin */
  isAdmin: boolean;
  /** Loading state for initial check */
  isLoading: boolean;
  /** Error from check attempt */
  error: Error | null;
  /** Manually re-check admin status */
  refresh: () => Promise<void>;
}

/**
 * Hook to check if the current user has admin privileges.
 *
 * F1, F2, F3 fix: This replaces build-time ADMIN_EMAILS env var checks
 * with runtime API validation against the backend's ADMIN_EMAILS.
 *
 * Benefits:
 * - Single source of truth (backend ADMIN_EMAILS)
 * - Works correctly regardless of build-time env vars
 * - Fails closed (defaults to non-admin on error)
 */
export function useAdminStatus(): AdminStatusState {
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef(true);

  const checkStatus = useCallback(async () => {
    try {
      const data = await adminQuotaApi.checkAdminStatus();

      if (isMountedRef.current) {
        setIsAdmin(data.isAdmin);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        // Fail closed: assume non-admin on error
        setIsAdmin(false);
        setError(err instanceof Error ? err : new Error('Failed to check admin status'));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    checkStatus();

    return () => {
      isMountedRef.current = false;
    };
  }, [checkStatus]);

  return {
    isAdmin,
    isLoading,
    error,
    refresh: checkStatus,
  };
}
