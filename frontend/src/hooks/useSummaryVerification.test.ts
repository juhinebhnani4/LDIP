/**
 * useSummaryVerification Hook Tests
 *
 * Story 14.4: Summary Verification API
 * Tests API integration, optimistic updates, and rollback on failure.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useSummaryVerification } from './useSummaryVerification';
import { api } from '@/lib/api/client';

// Mock the API
vi.mock('@/lib/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('useSummaryVerification', () => {
  const matterId = 'matter-123';

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock for initial load
    vi.mocked(api.get).mockResolvedValue({
      data: [],
      meta: { total: 0 },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('should load existing verifications on mount', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({
        data: [
          {
            id: 'v1',
            matterId: 'matter-123',
            sectionType: 'subject_matter',
            sectionId: 'main',
            decision: 'verified',
            verifiedBy: 'user-1',
            verifiedAt: '2026-01-16T10:00:00Z',
          },
        ],
        meta: { total: 1 },
      });

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      await waitFor(() => {
        expect(result.current.verifications.size).toBe(1);
      });

      const key = 'subject_matter:main';
      const verification = result.current.verifications.get(key);
      expect(verification?.decision).toBe('verified');
    });

    it('should call correct API endpoint on mount', async () => {
      renderHook(() => useSummaryVerification({ matterId }));

      await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith(
          '/api/v1/matters/matter-123/summary/verifications'
        );
      });
    });
  });

  describe('verifySection', () => {
    it('should verify a section and update state', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          id: 'v1',
          matterId: 'matter-123',
          sectionType: 'subject_matter',
          sectionId: 'main',
          decision: 'verified',
          verifiedBy: 'user-1',
          verifiedAt: '2026-01-16T10:00:00Z',
        },
      });

      const onSuccess = vi.fn();
      const { result } = renderHook(() =>
        useSummaryVerification({ matterId, onSuccess })
      );

      await act(async () => {
        await result.current.verifySection('subject_matter', 'main');
      });

      expect(api.post).toHaveBeenCalledWith(
        '/api/v1/matters/matter-123/summary/verify',
        {
          sectionType: 'subject_matter',
          sectionId: 'main',
          decision: 'verified',
        }
      );

      const key = 'subject_matter:main';
      expect(result.current.verifications.get(key)?.decision).toBe('verified');
      expect(onSuccess).toHaveBeenCalled();
    });

    it('should optimistically update then rollback on API failure', async () => {
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));

      const onError = vi.fn();
      const { result } = renderHook(() =>
        useSummaryVerification({ matterId, onError })
      );

      // Wait for initial load
      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      await act(async () => {
        try {
          await result.current.verifySection('subject_matter', 'main');
        } catch {
          // Expected to throw
        }
      });

      // After rollback, verification should not exist
      const key = 'subject_matter:main';
      expect(result.current.verifications.get(key)).toBeUndefined();
      expect(onError).toHaveBeenCalled();
      expect(result.current.error).not.toBeNull();
    });

    it('should set isLoading during API call', async () => {
      let resolvePromise: (value: unknown) => void;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      vi.mocked(api.post).mockReturnValueOnce(promise as never);

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      // Wait for initial load
      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      act(() => {
        result.current.verifySection('subject_matter', 'main');
      });

      expect(result.current.isLoading).toBe(true);

      await act(async () => {
        resolvePromise!({
          data: {
            id: 'v1',
            matterId: 'matter-123',
            sectionType: 'subject_matter',
            sectionId: 'main',
            decision: 'verified',
            verifiedBy: 'user-1',
            verifiedAt: '2026-01-16T10:00:00Z',
          },
        });
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('flagSection', () => {
    it('should flag a section and update state', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          id: 'v1',
          matterId: 'matter-123',
          sectionType: 'current_status',
          sectionId: 'main',
          decision: 'flagged',
          verifiedBy: 'user-1',
          verifiedAt: '2026-01-16T10:00:00Z',
        },
      });

      const onSuccess = vi.fn();
      const { result } = renderHook(() =>
        useSummaryVerification({ matterId, onSuccess })
      );

      await act(async () => {
        await result.current.flagSection('current_status', 'main');
      });

      expect(api.post).toHaveBeenCalledWith(
        '/api/v1/matters/matter-123/summary/verify',
        {
          sectionType: 'current_status',
          sectionId: 'main',
          decision: 'flagged',
        }
      );

      const key = 'current_status:main';
      expect(result.current.verifications.get(key)?.decision).toBe('flagged');
      expect(onSuccess).toHaveBeenCalled();
    });

    it('should rollback on API failure when flagging', async () => {
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      // Wait for initial load
      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      await act(async () => {
        try {
          await result.current.flagSection('current_status', 'main');
        } catch {
          // Expected to throw
        }
      });

      const key = 'current_status:main';
      expect(result.current.verifications.get(key)).toBeUndefined();
    });
  });

  describe('addNote', () => {
    it('should add a note and update state', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          id: 'n1',
          matterId: 'matter-123',
          sectionType: 'parties',
          sectionId: 'entity-123',
          text: 'Need to verify this party',
          createdBy: 'user-1',
          createdAt: '2026-01-16T10:00:00Z',
        },
      });

      const onSuccess = vi.fn();
      const { result } = renderHook(() =>
        useSummaryVerification({ matterId, onSuccess })
      );

      await act(async () => {
        await result.current.addNote('parties', 'entity-123', 'Need to verify this party');
      });

      expect(api.post).toHaveBeenCalledWith(
        '/api/v1/matters/matter-123/summary/notes',
        {
          sectionType: 'parties',
          sectionId: 'entity-123',
          text: 'Need to verify this party',
        }
      );

      const key = 'parties:entity-123';
      const notes = result.current.notes.get(key);
      expect(notes).toHaveLength(1);
      expect(notes![0]!.text).toBe('Need to verify this party');
      expect(notes![0]!.id).toBe('n1'); // Server-provided ID
      expect(onSuccess).toHaveBeenCalled();
    });

    it('should rollback optimistic note on API failure', async () => {
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      // Wait for initial load
      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      await act(async () => {
        try {
          await result.current.addNote('parties', 'entity-123', 'Test note');
        } catch {
          // Expected to throw
        }
      });

      const key = 'parties:entity-123';
      const notes = result.current.notes.get(key);
      // After rollback, key should be deleted (undefined) since notes array was empty
      expect(notes).toBeUndefined();
    });
  });

  describe('refresh', () => {
    it('should reload verifications from server', async () => {
      vi.mocked(api.get)
        .mockResolvedValueOnce({
          data: [],
          meta: { total: 0 },
        })
        .mockResolvedValueOnce({
          data: [
            {
              id: 'v1',
              matterId: 'matter-123',
              sectionType: 'key_issue',
              sectionId: 'issue-1',
              decision: 'verified',
              verifiedBy: 'user-1',
              verifiedAt: '2026-01-16T10:00:00Z',
            },
          ],
          meta: { total: 1 },
        });

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      // Wait for initial (empty) load
      await waitFor(() => {
        expect(api.get).toHaveBeenCalledTimes(1);
      });

      expect(result.current.verifications.size).toBe(0);

      // Trigger refresh
      await act(async () => {
        await result.current.refresh();
      });

      expect(api.get).toHaveBeenCalledTimes(2);
      expect(result.current.verifications.size).toBe(1);
    });
  });

  describe('error handling', () => {
    it('should silently handle initial load errors', async () => {
      vi.mocked(api.get).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      // Should not throw, verifications should be empty
      expect(result.current.verifications.size).toBe(0);
    });

    it('should clear error on successful operation', async () => {
      // First call fails
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));
      // Second call succeeds
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          id: 'v1',
          matterId: 'matter-123',
          sectionType: 'subject_matter',
          sectionId: 'main',
          decision: 'verified',
          verifiedBy: 'user-1',
          verifiedAt: '2026-01-16T10:00:00Z',
        },
      });

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      // Wait for initial load
      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      // First call - should fail
      await act(async () => {
        try {
          await result.current.verifySection('subject_matter', 'main');
        } catch {
          // Expected
        }
      });

      expect(result.current.error).not.toBeNull();

      // Second call - should succeed and clear error
      await act(async () => {
        await result.current.verifySection('subject_matter', 'main');
      });

      expect(result.current.error).toBeNull();
    });

    it('should show toast notification on verify failure', async () => {
      const { toast } = await import('sonner');
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      await act(async () => {
        try {
          await result.current.verifySection('subject_matter', 'main');
        } catch {
          // Expected
        }
      });

      expect(toast.error).toHaveBeenCalledWith('Failed to verify section. Please try again.');
    });

    it('should show toast notification on flag failure', async () => {
      const { toast } = await import('sonner');
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      await act(async () => {
        try {
          await result.current.flagSection('current_status', 'main');
        } catch {
          // Expected
        }
      });

      expect(toast.error).toHaveBeenCalledWith('Failed to flag section. Please try again.');
    });

    it('should show toast notification on addNote failure', async () => {
      const { toast } = await import('sonner');
      vi.mocked(api.post).mockRejectedValueOnce(new Error('API Error'));

      const { result } = renderHook(() =>
        useSummaryVerification({ matterId })
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      await act(async () => {
        try {
          await result.current.addNote('parties', 'entity-123', 'Test note');
        } catch {
          // Expected
        }
      });

      expect(toast.error).toHaveBeenCalledWith('Failed to add note. Please try again.');
    });
  });
});
