'use client';

/**
 * Verification Queue Hook
 *
 * Custom hook for fetching and managing the verification queue.
 *
 * Story 8-5: Implement Verification Queue UI (Task 9.1)
 */

import { useCallback, useEffect, useRef } from 'react';
import { useVerificationStore } from '@/stores/verificationStore';
import { verificationsApi } from '@/lib/api/verifications';
import type { VerificationQueueItem, VerificationFilters } from '@/types';

/**
 * Default polling interval for verification queue refresh.
 * Set to 30 seconds to balance freshness with server load.
 * Can be overridden via options.pollInterval.
 */
const DEFAULT_POLL_INTERVAL_MS = 30_000;

interface UseVerificationQueueOptions {
  /** Matter ID to fetch queue for */
  matterId: string;
  /** Max items to fetch (default 50) */
  limit?: number;
  /** Enable auto-polling (default true) */
  enablePolling?: boolean;
  /** Polling interval in ms (default 30000 = 30 seconds) */
  pollInterval?: number;
}

interface UseVerificationQueueReturn {
  /** Queue items */
  queue: VerificationQueueItem[];
  /** Filtered queue based on current filters */
  filteredQueue: VerificationQueueItem[];
  /** Current filters */
  filters: VerificationFilters;
  /** Loading state */
  isLoading: boolean;
  /** Error message */
  error: string | null;
  /** Refresh the queue manually */
  refresh: () => Promise<void>;
  /** Update filters */
  setFilters: (filters: Partial<VerificationFilters>) => void;
  /** Reset filters to defaults */
  resetFilters: () => void;
  /** Available finding types for filter dropdown */
  findingTypes: string[];
}

/**
 * Hook for fetching and managing the verification queue.
 *
 * @param options - Configuration options
 * @returns Queue state and actions
 *
 * @example
 * ```tsx
 * const {
 *   queue,
 *   filteredQueue,
 *   isLoading,
 *   filters,
 *   setFilters,
 * } = useVerificationQueue({ matterId: 'matter-123' });
 *
 * // Filter by finding type
 * setFilters({ findingType: 'citation_mismatch' });
 * ```
 */
export function useVerificationQueue(
  options: UseVerificationQueueOptions
): UseVerificationQueueReturn {
  const {
    matterId,
    limit = 50,
    enablePolling = true,
    pollInterval = DEFAULT_POLL_INTERVAL_MS,
  } = options;

  // Store selectors
  const queue = useVerificationStore((state) => state.queue);
  const filters = useVerificationStore((state) => state.filters);
  const isLoading = useVerificationStore((state) => state.isLoading);
  const error = useVerificationStore((state) => state.error);

  // Store actions
  const setMatterId = useVerificationStore((state) => state.setMatterId);
  const setQueue = useVerificationStore((state) => state.setQueue);
  const setLoading = useVerificationStore((state) => state.setLoading);
  const setError = useVerificationStore((state) => state.setError);
  const setFiltersAction = useVerificationStore((state) => state.setFilters);
  const resetFiltersAction = useVerificationStore((state) => state.resetFilters);

  // Compute filtered queue
  const filteredQueue = useCallback(() => {
    let filtered = queue;

    // Filter by finding type
    if (filters.findingType) {
      filtered = filtered.filter(
        (item) => item.findingType === filters.findingType
      );
    }

    // Filter by confidence tier
    if (filters.confidenceTier) {
      filtered = filtered.filter((item) => {
        const confidence = item.confidence;
        switch (filters.confidenceTier) {
          case 'high':
            return confidence > 90;
          case 'medium':
            return confidence > 70 && confidence <= 90;
          case 'low':
            return confidence <= 70;
          default:
            return true;
        }
      });
    }

    // Filter by status
    if (filters.status) {
      filtered = filtered.filter((item) => item.decision === filters.status);
    }

    return filtered;
  }, [queue, filters])();

  // Get unique finding types for filter dropdown
  const findingTypes = useCallback(() => {
    const types = new Set(queue.map((item) => item.findingType));
    return Array.from(types).sort();
  }, [queue])();

  // Track mounted state to prevent state updates after unmount
  const isMountedRef = useRef(true);

  // Reset mounted state on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Fetch queue from API
  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      const data = await verificationsApi.getPendingQueue(matterId, limit);
      // Only update state if component is still mounted
      if (isMountedRef.current) {
        setQueue(data);
        setError(null);
      }
    } catch (err) {
      // Only update state if component is still mounted
      if (isMountedRef.current) {
        const message = err instanceof Error ? err.message : 'Failed to load verification queue';
        setError(message);
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [matterId, limit, setLoading, setQueue, setError]);

  // Initialize matter ID and fetch queue
  useEffect(() => {
    setMatterId(matterId);
    fetchQueue();
  }, [matterId, setMatterId, fetchQueue]);

  // Set up polling
  useEffect(() => {
    if (!enablePolling) {
      return;
    }

    const intervalId = setInterval(() => {
      // Don't poll if currently loading
      if (!isLoading) {
        fetchQueue();
      }
    }, pollInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [enablePolling, pollInterval, isLoading, fetchQueue]);

  return {
    queue,
    filteredQueue,
    filters,
    isLoading,
    error,
    refresh: fetchQueue,
    setFilters: setFiltersAction,
    resetFilters: resetFiltersAction,
    findingTypes,
  };
}
