/**
 * Summary Verification Hook
 *
 * Provides verification actions for summary sections.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 * Story 14.4: Summary Verification API - Wire to real API
 */

import { useState, useCallback, useEffect } from 'react';
import { api } from '@/lib/api/client';
import { toast } from 'sonner';
import type {
  SummarySectionType,
  SummaryVerification,
  SummaryNote,
} from '@/types/summary';

// =============================================================================
// Story 14.4: API Response Types
// =============================================================================

interface SummaryVerificationResponse {
  data: {
    id: string;
    matterId: string;
    sectionType: SummarySectionType;
    sectionId: string;
    decision: 'verified' | 'flagged';
    notes?: string;
    verifiedBy: string;
    verifiedAt: string;
  };
}

interface SummaryNoteResponse {
  data: {
    id: string;
    matterId: string;
    sectionType: SummarySectionType;
    sectionId: string;
    text: string;
    createdBy: string;
    createdAt: string;
  };
}

interface SummaryVerificationsListResponse {
  data: Array<{
    id: string;
    matterId: string;
    sectionType: SummarySectionType;
    sectionId: string;
    decision: 'verified' | 'flagged';
    notes?: string;
    verifiedBy: string;
    verifiedAt: string;
  }>;
  meta: { total: number };
}

interface UseSummaryVerificationOptions {
  /** Matter ID */
  matterId: string;
  /** Current user name for verification attribution */
  userName?: string;
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
  /** Refresh verifications from server */
  refresh: () => Promise<void>;
}

/**
 * Hook for managing summary section verifications
 *
 * Story 14.4: Wired to real API endpoints
 */
export function useSummaryVerification({
  matterId,
  userName = 'Unknown User',
  onSuccess,
  onError,
}: UseSummaryVerificationOptions): UseSummaryVerificationReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [verifications, setVerifications] = useState<Map<string, SummaryVerification>>(new Map());
  const [notes, setNotes] = useState<Map<string, SummaryNote[]>>(new Map());

  const getKey = (sectionType: SummarySectionType, sectionId: string) =>
    `${sectionType}:${sectionId}`;

  // Story 14.4: Load existing verifications on mount
  const loadVerifications = useCallback(async () => {
    if (!matterId) return;

    try {
      const response = await api.get<SummaryVerificationsListResponse>(
        `/api/v1/matters/${matterId}/summary/verifications`
      );

      const newVerifications = new Map<string, SummaryVerification>();
      for (const v of response.data) {
        newVerifications.set(getKey(v.sectionType, v.sectionId), {
          sectionType: v.sectionType,
          sectionId: v.sectionId,
          decision: v.decision,
          verifiedBy: v.verifiedBy,
          verifiedAt: v.verifiedAt,
          notes: v.notes,
        });
      }
      setVerifications(newVerifications);
    } catch {
      // Silently fail - verifications will be empty
    }
  }, [matterId]);

  // Load verifications on mount
  useEffect(() => {
    loadVerifications();
  }, [loadVerifications]);

  const verifySection = useCallback(
    async (sectionType: SummarySectionType, sectionId: string) => {
      setIsLoading(true);
      setError(null);

      // Optimistic update
      const optimisticVerification: SummaryVerification = {
        sectionType,
        sectionId,
        decision: 'verified',
        verifiedBy: userName,
        verifiedAt: new Date().toISOString(),
      };

      const key = getKey(sectionType, sectionId);
      const previousVerification = verifications.get(key);

      setVerifications((prev) => {
        const next = new Map(prev);
        next.set(key, optimisticVerification);
        return next;
      });

      try {
        // Story 14.4: Call real API endpoint
        const response = await api.post<SummaryVerificationResponse>(
          `/api/v1/matters/${matterId}/summary/verify`,
          {
            sectionType,
            sectionId,
            decision: 'verified',
          }
        );

        // Update with server response
        setVerifications((prev) => {
          const next = new Map(prev);
          next.set(key, {
            sectionType: response.data.sectionType,
            sectionId: response.data.sectionId,
            decision: response.data.decision,
            verifiedBy: response.data.verifiedBy,
            verifiedAt: response.data.verifiedAt,
            notes: response.data.notes,
          });
          return next;
        });

        onSuccess?.();
      } catch (err) {
        // Rollback on error
        setVerifications((prev) => {
          const next = new Map(prev);
          if (previousVerification) {
            next.set(key, previousVerification);
          } else {
            next.delete(key);
          }
          return next;
        });

        const error = err instanceof Error ? err : new Error('Failed to verify section');
        setError(error);
        toast.error('Failed to verify section. Please try again.');
        onError?.(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, userName, verifications, onSuccess, onError]
  );

  const flagSection = useCallback(
    async (sectionType: SummarySectionType, sectionId: string) => {
      setIsLoading(true);
      setError(null);

      // Optimistic update
      const optimisticVerification: SummaryVerification = {
        sectionType,
        sectionId,
        decision: 'flagged',
        verifiedBy: userName,
        verifiedAt: new Date().toISOString(),
      };

      const key = getKey(sectionType, sectionId);
      const previousVerification = verifications.get(key);

      setVerifications((prev) => {
        const next = new Map(prev);
        next.set(key, optimisticVerification);
        return next;
      });

      try {
        // Story 14.4: Call real API endpoint
        const response = await api.post<SummaryVerificationResponse>(
          `/api/v1/matters/${matterId}/summary/verify`,
          {
            sectionType,
            sectionId,
            decision: 'flagged',
          }
        );

        // Update with server response
        setVerifications((prev) => {
          const next = new Map(prev);
          next.set(key, {
            sectionType: response.data.sectionType,
            sectionId: response.data.sectionId,
            decision: response.data.decision,
            verifiedBy: response.data.verifiedBy,
            verifiedAt: response.data.verifiedAt,
            notes: response.data.notes,
          });
          return next;
        });

        onSuccess?.();
      } catch (err) {
        // Rollback on error
        setVerifications((prev) => {
          const next = new Map(prev);
          if (previousVerification) {
            next.set(key, previousVerification);
          } else {
            next.delete(key);
          }
          return next;
        });

        const error = err instanceof Error ? err : new Error('Failed to flag section');
        setError(error);
        toast.error('Failed to flag section. Please try again.');
        onError?.(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, userName, verifications, onSuccess, onError]
  );

  const addNote = useCallback(
    async (sectionType: SummarySectionType, sectionId: string, noteText: string) => {
      setIsLoading(true);
      setError(null);

      // Optimistic update with temporary id
      const optimisticNote: SummaryNote = {
        id: `temp-${Date.now()}`,
        sectionType,
        sectionId,
        text: noteText,
        createdBy: userName,
        createdAt: new Date().toISOString(),
      };

      const key = getKey(sectionType, sectionId);

      setNotes((prev) => {
        const next = new Map(prev);
        const existing = prev.get(key) || [];
        next.set(key, [...existing, optimisticNote]);
        return next;
      });

      try {
        // Story 14.4: Call real API endpoint
        const response = await api.post<SummaryNoteResponse>(
          `/api/v1/matters/${matterId}/summary/notes`,
          {
            sectionType,
            sectionId,
            text: noteText,
          }
        );

        // Replace optimistic note with server response
        setNotes((prev) => {
          const next = new Map(prev);
          const existing = prev.get(key) || [];
          // Remove optimistic note and add server response
          const withoutOptimistic = existing.filter(
            (n) => n.id !== optimisticNote.id
          );
          next.set(key, [
            ...withoutOptimistic,
            {
              id: response.data.id,
              sectionType: response.data.sectionType,
              sectionId: response.data.sectionId,
              text: response.data.text,
              createdBy: response.data.createdBy,
              createdAt: response.data.createdAt,
            },
          ]);
          return next;
        });

        onSuccess?.();
      } catch (err) {
        // Rollback on error - remove optimistic note, delete key if empty
        setNotes((prev) => {
          const next = new Map(prev);
          const existing = prev.get(key) || [];
          const filtered = existing.filter((n) => n.id !== optimisticNote.id);
          if (filtered.length === 0) {
            next.delete(key);
          } else {
            next.set(key, filtered);
          }
          return next;
        });

        const error = err instanceof Error ? err : new Error('Failed to add note');
        setError(error);
        toast.error('Failed to add note. Please try again.');
        onError?.(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, userName, onSuccess, onError]
  );

  return {
    verifySection,
    flagSection,
    addNote,
    isLoading,
    error,
    verifications,
    notes,
    refresh: loadVerifications,
  };
}
