/**
 * Summary Verification Hook
 *
 * Provides verification actions for summary sections.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 */

import { useState, useCallback } from 'react';
import type {
  SummarySectionType,
  SummaryVerification,
  SummaryNote,
} from '@/types/summary';

interface UseSummaryVerificationOptions {
  /** Matter ID */
  matterId: string;
  /** Callback when verification is successful */
  onSuccess?: () => void;
  /** Callback when verification fails */
  onError?: (error: Error) => void;
}

interface UseSummaryVerificationReturn {
  /** Verify a section */
  verifySection: (sectionType: SummarySectionType, sectionId: string) => Promise<void>;
  /** Flag a section */
  flagSection: (sectionType: SummarySectionType, sectionId: string) => Promise<void>;
  /** Add a note to a section */
  addNote: (sectionType: SummarySectionType, sectionId: string, note: string) => Promise<void>;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Verification records */
  verifications: Map<string, SummaryVerification>;
  /** Notes */
  notes: Map<string, SummaryNote[]>;
}

/**
 * Hook for managing summary section verifications
 */
export function useSummaryVerification({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- Will be used when API is implemented
  matterId,
  onSuccess,
  onError,
}: UseSummaryVerificationOptions): UseSummaryVerificationReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [verifications, setVerifications] = useState<Map<string, SummaryVerification>>(new Map());
  const [notes, setNotes] = useState<Map<string, SummaryNote[]>>(new Map());

  const getKey = (sectionType: SummarySectionType, sectionId: string) =>
    `${sectionType}:${sectionId}`;

  const verifySection = useCallback(
    async (sectionType: SummarySectionType, sectionId: string) => {
      setIsLoading(true);
      setError(null);

      try {
        // TODO: Replace with actual API call when backend is ready
        // await api.post(`/matters/${matterId}/summary/verify`, {
        //   sectionType,
        //   sectionId,
        //   decision: 'verified',
        // });

        // Optimistic update
        const verification: SummaryVerification = {
          sectionType,
          sectionId,
          decision: 'verified',
          verifiedBy: 'Current User', // TODO: Get from auth context
          verifiedAt: new Date().toISOString(),
        };

        setVerifications((prev) => {
          const next = new Map(prev);
          next.set(getKey(sectionType, sectionId), verification);
          return next;
        });

        onSuccess?.();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to verify section');
        setError(error);
        onError?.(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [onSuccess, onError]
  );

  const flagSection = useCallback(
    async (sectionType: SummarySectionType, sectionId: string) => {
      setIsLoading(true);
      setError(null);

      try {
        // TODO: Replace with actual API call when backend is ready
        // await api.post(`/matters/${matterId}/summary/flag`, {
        //   sectionType,
        //   sectionId,
        //   decision: 'flagged',
        // });

        // Optimistic update
        const verification: SummaryVerification = {
          sectionType,
          sectionId,
          decision: 'flagged',
          verifiedBy: 'Current User', // TODO: Get from auth context
          verifiedAt: new Date().toISOString(),
        };

        setVerifications((prev) => {
          const next = new Map(prev);
          next.set(getKey(sectionType, sectionId), verification);
          return next;
        });

        onSuccess?.();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to flag section');
        setError(error);
        onError?.(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [onSuccess, onError]
  );

  const addNote = useCallback(
    async (sectionType: SummarySectionType, sectionId: string, noteText: string) => {
      setIsLoading(true);
      setError(null);

      try {
        // TODO: Replace with actual API call when backend is ready
        // await api.post(`/matters/${matterId}/summary/notes`, {
        //   sectionType,
        //   sectionId,
        //   text: noteText,
        // });

        // Optimistic update
        const note: SummaryNote = {
          sectionType,
          sectionId,
          text: noteText,
          createdBy: 'Current User', // TODO: Get from auth context
          createdAt: new Date().toISOString(),
        };

        setNotes((prev) => {
          const next = new Map(prev);
          const key = getKey(sectionType, sectionId);
          const existing = prev.get(key) || [];
          next.set(key, [...existing, note]);
          return next;
        });

        onSuccess?.();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to add note');
        setError(error);
        onError?.(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [onSuccess, onError]
  );

  return {
    verifySection,
    flagSection,
    addNote,
    isLoading,
    error,
    verifications,
    notes,
  };
}
