/**
 * Tests for useSummaryEdit Hook
 *
 * Story 14.6: Summary Frontend Integration (AC #1-3)
 *
 * Tests:
 * - Save edit operations
 * - Regenerate operations
 * - Loading states
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useSummaryEdit } from './useSummaryEdit';
import { api } from '@/lib/api/client';
import { toast } from 'sonner';

// Mock dependencies
vi.mock('@/lib/api/client', () => ({
  api: {
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useSummaryEdit', () => {
  const matterId = 'matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('saveEdit', () => {
    it('should save edit successfully', async () => {
      // Arrange
      const mockResponse = {
        data: {
          id: 'edit-123',
          matterId: 'matter-123',
          sectionType: 'subject_matter',
          sectionId: 'main',
          originalContent: 'Original content',
          editedContent: 'Edited content',
          editedBy: 'user-123',
          editedAt: '2026-01-16T10:00:00Z',
        },
      };
      vi.mocked(api.put).mockResolvedValue(mockResponse);
      const onSaveSuccess = vi.fn();

      // Act
      const { result } = renderHook(() =>
        useSummaryEdit({ matterId, onSaveSuccess })
      );

      await act(async () => {
        await result.current.saveEdit(
          'subject_matter',
          'main',
          'Edited content',
          'Original content'
        );
      });

      // Assert
      expect(api.put).toHaveBeenCalledWith(
        `/api/v1/matters/${matterId}/summary/sections/subject_matter`,
        {
          sectionId: 'main',
          content: 'Edited content',
          originalContent: 'Original content',
        }
      );
      expect(toast.success).toHaveBeenCalledWith('Changes saved successfully');
      expect(onSaveSuccess).toHaveBeenCalled();
    });

    it('should handle save error', async () => {
      // Arrange
      vi.mocked(api.put).mockRejectedValue(new Error('Network error'));
      const onError = vi.fn();

      // Act
      const { result } = renderHook(() =>
        useSummaryEdit({ matterId, onError })
      );

      await act(async () => {
        try {
          await result.current.saveEdit(
            'subject_matter',
            'main',
            'Edited content',
            'Original content'
          );
        } catch {
          // Expected
        }
      });

      // Assert
      expect(toast.error).toHaveBeenCalledWith('Failed to save changes. Please try again.');
      expect(onError).toHaveBeenCalled();
      expect(result.current.error).not.toBeNull();
    });

    it('should set isSaving while saving', async () => {
      // Arrange
      let resolvePromise: (value: unknown) => void;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.put).mockReturnValue(promise as Promise<unknown>);

      // Act
      const { result } = renderHook(() => useSummaryEdit({ matterId }));

      expect(result.current.isSaving).toBe(false);

      let savePromise: Promise<void>;
      act(() => {
        savePromise = result.current.saveEdit(
          'subject_matter',
          'main',
          'Content',
          'Original'
        );
      });

      // Loading state should be true
      expect(result.current.isSaving).toBe(true);

      // Resolve and wait
      await act(async () => {
        resolvePromise!({ data: {} });
        await savePromise!;
      });

      expect(result.current.isSaving).toBe(false);
    });
  });

  describe('regenerate', () => {
    it('should regenerate section successfully', async () => {
      // Arrange
      const mockSummary = {
        matterId: 'matter-123',
        attentionItems: [],
        parties: [],
        subjectMatter: {
          description: 'Regenerated content',
          sources: [],
          isVerified: false,
        },
        currentStatus: {
          lastOrderDate: '2026-01-16',
          description: 'Status',
          sourceDocument: 'doc.pdf',
          sourcePage: 1,
          isVerified: false,
        },
        keyIssues: [],
        stats: {
          totalPages: 10,
          entitiesFound: 5,
          eventsExtracted: 3,
          citationsFound: 2,
          verificationPercent: 50,
        },
        generatedAt: '2026-01-16T10:00:00Z',
      };
      vi.mocked(api.post).mockResolvedValue({ data: mockSummary });
      const onRegenerateSuccess = vi.fn();

      // Act
      const { result } = renderHook(() =>
        useSummaryEdit({ matterId, onRegenerateSuccess })
      );

      let regeneratedSummary;
      await act(async () => {
        regeneratedSummary = await result.current.regenerate('subject_matter');
      });

      // Assert
      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/matters/${matterId}/summary/regenerate`,
        { sectionType: 'subject_matter' }
      );
      expect(toast.success).toHaveBeenCalledWith('Content regenerated successfully');
      expect(onRegenerateSuccess).toHaveBeenCalledWith(mockSummary);
      expect(regeneratedSummary).toEqual(mockSummary);
    });

    it('should handle regenerate error', async () => {
      // Arrange
      vi.mocked(api.post).mockRejectedValue(new Error('API error'));
      const onError = vi.fn();

      // Act
      const { result } = renderHook(() =>
        useSummaryEdit({ matterId, onError })
      );

      await act(async () => {
        try {
          await result.current.regenerate('subject_matter');
        } catch {
          // Expected
        }
      });

      // Assert
      expect(toast.error).toHaveBeenCalledWith('Failed to regenerate content. Please try again.');
      expect(onError).toHaveBeenCalled();
    });

    it('should set isRegenerating while regenerating', async () => {
      // Arrange
      let resolvePromise: (value: unknown) => void;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.post).mockReturnValue(promise as Promise<unknown>);

      // Act
      const { result } = renderHook(() => useSummaryEdit({ matterId }));

      expect(result.current.isRegenerating).toBe(false);

      let regeneratePromise: Promise<unknown>;
      act(() => {
        regeneratePromise = result.current.regenerate('subject_matter');
      });

      // Loading state should be true
      expect(result.current.isRegenerating).toBe(true);

      // Resolve and wait
      await act(async () => {
        resolvePromise!({ data: {} });
        await regeneratePromise!;
      });

      expect(result.current.isRegenerating).toBe(false);
    });
  });

  describe('error state', () => {
    it('should clear error on successful operation', async () => {
      // First, cause an error
      vi.mocked(api.put).mockRejectedValueOnce(new Error('Error'));

      const { result } = renderHook(() => useSummaryEdit({ matterId }));

      await act(async () => {
        try {
          await result.current.saveEdit('subject_matter', 'main', 'Content', 'Original');
        } catch {
          // Expected
        }
      });

      expect(result.current.error).not.toBeNull();

      // Now succeed
      vi.mocked(api.put).mockResolvedValueOnce({ data: {} });

      await act(async () => {
        await result.current.saveEdit('subject_matter', 'main', 'Content', 'Original');
      });

      expect(result.current.error).toBeNull();
    });
  });
});
