'use client';

/**
 * useActDiscovery Hook
 *
 * Provides Act Discovery Report fetching and mutation logic.
 * Used by ActDiscoveryModal and ActDiscoveryItem components.
 *
 * Story 3-2: Act Discovery Report UI
 *
 * @example
 * ```tsx
 * const { actReport, isLoading, error, refetch, markUploaded, markSkipped } = useActDiscovery(matterId);
 *
 * // Display acts
 * actReport?.map(act => <ActDiscoveryItem key={act.actNameNormalized} act={act} />);
 *
 * // Mark an act as uploaded
 * await markUploaded('Negotiable Instruments Act', 'doc-123');
 * ```
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  getActDiscoveryReport,
  markActUploaded,
  markActSkipped,
} from '@/lib/api/citations';
import type {
  ActDiscoverySummary,
  ActResolutionResponse,
  CitationErrorResponse,
} from '@/types';

/** Hook return type */
export interface UseActDiscoveryReturn {
  /** List of Acts with their discovery status */
  actReport: ActDiscoverySummary[];
  /** Whether the report is currently loading */
  isLoading: boolean;
  /** Error if the fetch failed */
  error: Error | null;
  /** Refetch the discovery report */
  refetch: () => Promise<void>;
  /** Mark an Act as uploaded with a document ID */
  markUploaded: (actName: string, actDocumentId: string) => Promise<ActResolutionResponse | null>;
  /** Mark an Act as skipped by the user */
  markSkipped: (actName: string) => Promise<ActResolutionResponse | null>;
  /** Whether a mutation is in progress */
  isMutating: boolean;
  /** Number of available Acts */
  availableCount: number;
  /** Number of missing Acts */
  missingCount: number;
  /** Number of skipped Acts */
  skippedCount: number;
  /** Total citation count across all Acts */
  totalCitations: number;
}

/**
 * Hook for managing Act Discovery Report state.
 *
 * @param matterId - Matter UUID
 * @param enabled - Whether to fetch automatically (default: true)
 * @returns Act discovery state and mutation functions
 */
export function useActDiscovery(
  matterId: string,
  enabled: boolean = true
): UseActDiscoveryReturn {
  const [actReport, setActReport] = useState<ActDiscoverySummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  // Track mounted state to avoid state updates after unmount
  const isMountedRef = useRef(true);

  // Track if initial fetch has been done
  const hasFetchedRef = useRef(false);

  /**
   * Fetch the Act Discovery Report
   */
  const fetchReport = useCallback(async () => {
    if (!matterId) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await getActDiscoveryReport(matterId);
      if (isMountedRef.current) {
        setActReport(response.data);
      }
    } catch (err) {
      if (isMountedRef.current) {
        const message = err instanceof Error ? err.message : 'Failed to load Act discovery report';
        setError(new Error(message));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [matterId]);

  /**
   * Mark an Act as uploaded
   *
   * @param actName - Normalized Act name
   * @param actDocumentId - Document UUID of the uploaded Act
   */
  const handleMarkUploaded = useCallback(
    async (actName: string, actDocumentId: string): Promise<ActResolutionResponse | null> => {
      if (!matterId || isMutating) return null;

      setIsMutating(true);

      try {
        const result = await markActUploaded(matterId, { actName, actDocumentId });

        if (isMountedRef.current) {
          // Update local state after successful API call
          setActReport((prev) =>
            prev.map((act) =>
              act.actName === actName || act.actNameNormalized === actName
                ? {
                    ...act,
                    resolutionStatus: 'available' as const,
                    userAction: 'uploaded' as const,
                    actDocumentId,
                  }
                : act
            )
          );
          toast.success(`${actName} marked as available`);
        }

        return result;
      } catch (err) {
        if (isMountedRef.current) {
          const errorResponse = err as CitationErrorResponse;
          const message = errorResponse.error?.message ?? 'Failed to mark Act as uploaded';
          toast.error(message);
        }
        return null;
      } finally {
        if (isMountedRef.current) {
          setIsMutating(false);
        }
      }
    },
    [matterId, isMutating]
  );

  /**
   * Mark an Act as skipped
   *
   * @param actName - Normalized Act name
   */
  const handleMarkSkipped = useCallback(
    async (actName: string): Promise<ActResolutionResponse | null> => {
      if (!matterId || isMutating) return null;

      setIsMutating(true);

      try {
        const result = await markActSkipped(matterId, { actName });

        if (isMountedRef.current) {
          // Update local state after successful API call
          setActReport((prev) =>
            prev.map((act) =>
              act.actName === actName || act.actNameNormalized === actName
                ? {
                    ...act,
                    resolutionStatus: 'skipped' as const,
                    userAction: 'skipped' as const,
                  }
                : act
            )
          );
          toast.success(`${actName} skipped`);
        }

        return result;
      } catch (err) {
        if (isMountedRef.current) {
          const errorResponse = err as CitationErrorResponse;
          const message = errorResponse.error?.message ?? 'Failed to skip Act';
          toast.error(message);
        }
        return null;
      } finally {
        if (isMountedRef.current) {
          setIsMutating(false);
        }
      }
    },
    [matterId, isMutating]
  );

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Initial fetch when enabled
  useEffect(() => {
    if (enabled && matterId && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchReport();
    }
  }, [enabled, matterId, fetchReport]);

  // Reset fetch flag when matterId changes
  useEffect(() => {
    hasFetchedRef.current = false;
  }, [matterId]);

  // Computed values
  const availableCount = actReport.filter((act) => act.resolutionStatus === 'available').length;
  const missingCount = actReport.filter((act) => act.resolutionStatus === 'missing').length;
  const skippedCount = actReport.filter((act) => act.resolutionStatus === 'skipped').length;
  const totalCitations = actReport.reduce((sum, act) => sum + act.citationCount, 0);

  return {
    actReport,
    isLoading,
    error,
    refetch: fetchReport,
    markUploaded: handleMarkUploaded,
    markSkipped: handleMarkSkipped,
    isMutating,
    availableCount,
    missingCount,
    skippedCount,
    totalCitations,
  };
}
