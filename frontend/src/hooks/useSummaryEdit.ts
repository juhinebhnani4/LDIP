/**
 * Summary Edit Hook
 *
 * Provides edit operations for summary sections.
 *
 * Story 14.6: Summary Frontend Integration (AC #1, #2, #3)
 */

import { useState, useCallback } from 'react';
import { api } from '@/lib/api/client';
import { toast } from 'sonner';
import type { SummarySectionType, MatterSummary } from '@/types/summary';

// =============================================================================
// Story 14.6: API Response Types
// =============================================================================

interface SummaryEditResponse {
  data: {
    id: string;
    matterId: string;
    sectionType: SummarySectionType;
    sectionId: string;
    originalContent: string;
    editedContent: string;
    editedBy: string;
    editedAt: string;
  };
}

interface SummaryRegenerateResponse {
  data: MatterSummary;
}

interface UseSummaryEditOptions {
  /** Matter ID */
  matterId: string;
  /** Callback when edit is saved */
  onSaveSuccess?: () => void;
  /** Callback when regeneration completes */
  onRegenerateSuccess?: (summary: MatterSummary) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

interface UseSummaryEditReturn {
  /** Save edited content for a section */
  saveEdit: (
    sectionType: SummarySectionType,
    sectionId: string,
    content: string,
    originalContent: string
  ) => Promise<void>;
  /** Regenerate a section using GPT-4 */
  regenerate: (sectionType: SummarySectionType) => Promise<MatterSummary | null>;
  /** Loading state for save */
  isSaving: boolean;
  /** Loading state for regenerate */
  isRegenerating: boolean;
  /** Error state */
  error: Error | null;
}

/**
 * Hook for managing summary section edits
 *
 * Story 14.6: AC #1-3 - Edit operations for subject_matter, current_status, parties
 *
 * @example
 * ```tsx
 * const { saveEdit, regenerate, isSaving, isRegenerating } = useSummaryEdit({
 *   matterId,
 *   onSaveSuccess: () => refetch(),
 *   onRegenerateSuccess: (summary) => setSummary(summary),
 * });
 *
 * // Save an edit
 * await saveEdit('subject_matter', 'main', newContent, originalContent);
 *
 * // Regenerate a section
 * await regenerate('subject_matter');
 * ```
 */
export function useSummaryEdit({
  matterId,
  onSaveSuccess,
  onRegenerateSuccess,
  onError,
}: UseSummaryEditOptions): UseSummaryEditReturn {
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const saveEdit = useCallback(
    async (
      sectionType: SummarySectionType,
      sectionId: string,
      content: string,
      originalContent: string
    ) => {
      setIsSaving(true);
      setError(null);

      try {
        await api.put<SummaryEditResponse>(
          `/api/v1/matters/${matterId}/summary/sections/${sectionType}`,
          {
            sectionId,
            content,
            originalContent,
          }
        );

        toast.success('Changes saved successfully');
        onSaveSuccess?.();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to save changes');
        setError(error);
        toast.error('Failed to save changes. Please try again.');
        onError?.(error);
        throw error;
      } finally {
        setIsSaving(false);
      }
    },
    [matterId, onSaveSuccess, onError]
  );

  const regenerate = useCallback(
    async (sectionType: SummarySectionType): Promise<MatterSummary | null> => {
      setIsRegenerating(true);
      setError(null);

      try {
        const response = await api.post<SummaryRegenerateResponse>(
          `/api/v1/matters/${matterId}/summary/regenerate`,
          {
            sectionType,
          }
        );

        toast.success('Content regenerated successfully');
        onRegenerateSuccess?.(response.data);
        return response.data;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to regenerate content');
        setError(error);
        toast.error('Failed to regenerate content. Please try again.');
        onError?.(error);
        throw error;
      } finally {
        setIsRegenerating(false);
      }
    },
    [matterId, onRegenerateSuccess, onError]
  );

  return {
    saveEdit,
    regenerate,
    isSaving,
    isRegenerating,
    error,
  };
}
