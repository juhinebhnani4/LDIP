'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getMatterCosts, type MatterCostSummary } from '@/lib/api/costs';

/**
 * Hook for fetching matter cost data.
 *
 * Story 7.1: Per-Matter Cost Tracking Widget
 *
 * Code Review Fix: Added request ID tracking to prevent stale responses
 * from overwriting fresh data when matterId or days changes rapidly.
 *
 * @param matterId - Matter UUID
 * @param days - Number of days to include (default 30)
 * @returns Cost data, loading state, error, and refetch function
 */
export function useMatterCosts(matterId: string, days: number = 30) {
  const [data, setData] = useState<MatterCostSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track request ID to prevent stale responses from overwriting fresh data
  const requestIdRef = useRef(0);

  const fetchCosts = useCallback(async () => {
    if (!matterId) {
      setIsLoading(false);
      return;
    }

    // Increment request ID to track this specific request
    const currentRequestId = ++requestIdRef.current;

    setIsLoading(true);
    setError(null);

    try {
      const costs = await getMatterCosts(matterId, days);

      // Only update state if this is still the latest request
      // This prevents stale responses from overwriting fresh data
      if (currentRequestId === requestIdRef.current) {
        setData(costs);
      }
    } catch (err) {
      // Only update error state if this is still the latest request
      if (currentRequestId === requestIdRef.current) {
        const errorInstance = err instanceof Error ? err : new Error('Failed to fetch costs');
        setError(errorInstance);
      }
    } finally {
      // Only update loading state if this is still the latest request
      if (currentRequestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [matterId, days]);

  useEffect(() => {
    fetchCosts();

    // Cleanup: increment request ID on unmount or dependency change
    // to invalidate any in-flight requests
    return () => {
      requestIdRef.current++;
    };
  }, [fetchCosts]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchCosts,
  };
}
