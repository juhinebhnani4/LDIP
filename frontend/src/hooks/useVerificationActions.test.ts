/**
 * useVerificationActions Hook Tests
 *
 * Story 8-5: Implement Verification Queue UI
 * Tests optimistic updates and rollback on API failure.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useVerificationActions } from './useVerificationActions';
import { useVerificationStore } from '@/stores/verificationStore';
import { verificationsApi } from '@/lib/api/verifications';
import { VerificationDecision, VerificationRequirement } from '@/types';
import type { VerificationQueueItem } from '@/types';

// Mock the API
vi.mock('@/lib/api/verifications', () => ({
  verificationsApi: {
    approve: vi.fn(),
    reject: vi.fn(),
    flag: vi.fn(),
    bulkUpdate: vi.fn(),
  },
}));

// Helper to create mock queue items
function mockQueueItem(
  id: string,
  overrides: Partial<VerificationQueueItem> = {}
): VerificationQueueItem {
  return {
    id,
    findingId: `finding-${id}`,
    findingType: 'citation_mismatch',
    findingSummary: `Test finding ${id}`,
    confidence: 75,
    requirement: VerificationRequirement.SUGGESTED,
    decision: VerificationDecision.PENDING,
    createdAt: new Date().toISOString(),
    sourceDocument: 'test.pdf',
    engine: 'citation',
    ...overrides,
  };
}

describe('useVerificationActions', () => {
  const matterId = 'matter-123';

  beforeEach(() => {
    vi.clearAllMocks();

    // Reset store
    const { result } = renderHook(() => useVerificationStore());
    act(() => {
      result.current.reset();
      result.current.setQueue([
        mockQueueItem('1'),
        mockQueueItem('2'),
        mockQueueItem('3'),
      ]);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('approve', () => {
    it('should remove item from queue on successful approve', async () => {
      vi.mocked(verificationsApi.approve).mockResolvedValueOnce({} as never);

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.approve('1');
      });

      const store = useVerificationStore.getState();
      expect(store.queue.find((i) => i.id === '1')).toBeUndefined();
      expect(store.queue).toHaveLength(2);
    });

    it('should restore item to queue on API failure', async () => {
      vi.mocked(verificationsApi.approve).mockRejectedValueOnce(
        new Error('API Error')
      );

      const onError = vi.fn();
      const { result } = renderHook(() =>
        useVerificationActions({ matterId, onError })
      );

      await act(async () => {
        await result.current.approve('1');
      });

      const store = useVerificationStore.getState();
      expect(store.queue.find((i) => i.id === '1')).toBeDefined();
      expect(store.queue).toHaveLength(3);
      expect(onError).toHaveBeenCalledWith('approve', '1', 'API Error');
    });

    it('should call onSuccess callback on success', async () => {
      vi.mocked(verificationsApi.approve).mockResolvedValueOnce({} as never);

      const onSuccess = vi.fn();
      const { result } = renderHook(() =>
        useVerificationActions({ matterId, onSuccess })
      );

      await act(async () => {
        await result.current.approve('1', 'Looks good');
      });

      expect(onSuccess).toHaveBeenCalledWith('approve', '1');
      expect(verificationsApi.approve).toHaveBeenCalledWith(matterId, '1', {
        notes: 'Looks good',
      });
    });

    it('should set isActioning during operation', async () => {
      let resolvePromise: () => void;
      const promise = new Promise<void>((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(verificationsApi.approve).mockReturnValueOnce(promise as never);

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      expect(result.current.isActioning).toBe(false);

      act(() => {
        result.current.approve('1');
      });

      await waitFor(() => {
        expect(result.current.isActioning).toBe(true);
        expect(result.current.currentAction).toBe('approve');
        expect(result.current.processingIds).toEqual(['1']);
      });

      await act(async () => {
        resolvePromise!();
        await promise;
      });

      expect(result.current.isActioning).toBe(false);
      expect(result.current.currentAction).toBeNull();
    });
  });

  describe('reject', () => {
    it('should remove item from queue on successful reject', async () => {
      vi.mocked(verificationsApi.reject).mockResolvedValueOnce({} as never);

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.reject('2', 'Incorrect finding');
      });

      const store = useVerificationStore.getState();
      expect(store.queue.find((i) => i.id === '2')).toBeUndefined();
      expect(store.queue).toHaveLength(2);
    });

    it('should restore item to queue on API failure', async () => {
      vi.mocked(verificationsApi.reject).mockRejectedValueOnce(
        new Error('Network error')
      );

      const onError = vi.fn();
      const { result } = renderHook(() =>
        useVerificationActions({ matterId, onError })
      );

      await act(async () => {
        await result.current.reject('2', 'Wrong');
      });

      const store = useVerificationStore.getState();
      expect(store.queue.find((i) => i.id === '2')).toBeDefined();
      expect(onError).toHaveBeenCalledWith('reject', '2', 'Network error');
    });
  });

  describe('flag', () => {
    it('should update decision to FLAGGED on success', async () => {
      vi.mocked(verificationsApi.flag).mockResolvedValueOnce({} as never);

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.flag('1', 'Needs review');
      });

      const store = useVerificationStore.getState();
      const item = store.queue.find((i) => i.id === '1');
      expect(item?.decision).toBe(VerificationDecision.FLAGGED);
    });

    it('should revert decision to PENDING on API failure', async () => {
      vi.mocked(verificationsApi.flag).mockRejectedValueOnce(
        new Error('Flag failed')
      );

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.flag('1', 'Needs review');
      });

      const store = useVerificationStore.getState();
      const item = store.queue.find((i) => i.id === '1');
      expect(item?.decision).toBe(VerificationDecision.PENDING);
    });
  });

  describe('bulkApprove', () => {
    it('should remove multiple items and clear selection on success', async () => {
      vi.mocked(verificationsApi.bulkUpdate).mockResolvedValueOnce({} as never);

      // Select items first
      const storeHook = renderHook(() => useVerificationStore());
      act(() => {
        storeHook.result.current.selectAll(['1', '2']);
      });

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.bulkApprove(['1', '2']);
      });

      const store = useVerificationStore.getState();
      expect(store.queue).toHaveLength(1);
      expect(store.queue[0]?.id).toBe('3');
      expect(store.selectedIds).toEqual([]);
    });

    it('should restore items on API failure', async () => {
      vi.mocked(verificationsApi.bulkUpdate).mockRejectedValueOnce(
        new Error('Bulk failed')
      );

      const onError = vi.fn();
      const { result } = renderHook(() =>
        useVerificationActions({ matterId, onError })
      );

      await act(async () => {
        await result.current.bulkApprove(['1', '2']);
      });

      const store = useVerificationStore.getState();
      expect(store.queue).toHaveLength(3);
      expect(onError).toHaveBeenCalledWith(
        'bulk-approve',
        '1,2',
        'Bulk failed'
      );
    });

    it('should not make API call for empty IDs', async () => {
      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.bulkApprove([]);
      });

      expect(verificationsApi.bulkUpdate).not.toHaveBeenCalled();
    });
  });

  describe('bulkReject', () => {
    it('should remove multiple items on success', async () => {
      vi.mocked(verificationsApi.bulkUpdate).mockResolvedValueOnce({} as never);

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.bulkReject(['1', '3'], 'All incorrect');
      });

      const store = useVerificationStore.getState();
      expect(store.queue).toHaveLength(1);
      expect(store.queue[0]?.id).toBe('2');
    });

    it('should restore items on API failure', async () => {
      vi.mocked(verificationsApi.bulkUpdate).mockRejectedValueOnce(
        new Error('Reject failed')
      );

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.bulkReject(['1', '3'], 'Wrong');
      });

      const store = useVerificationStore.getState();
      expect(store.queue).toHaveLength(3);
    });
  });

  describe('bulkFlag', () => {
    it('should update all items to FLAGGED on success', async () => {
      vi.mocked(verificationsApi.bulkUpdate).mockResolvedValueOnce({} as never);

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.bulkFlag(['1', '2'], 'All need review');
      });

      const store = useVerificationStore.getState();
      expect(store.queue.find((i) => i.id === '1')?.decision).toBe(
        VerificationDecision.FLAGGED
      );
      expect(store.queue.find((i) => i.id === '2')?.decision).toBe(
        VerificationDecision.FLAGGED
      );
      expect(store.queue.find((i) => i.id === '3')?.decision).toBe(
        VerificationDecision.PENDING
      );
    });

    it('should revert all items to PENDING on API failure', async () => {
      vi.mocked(verificationsApi.bulkUpdate).mockRejectedValueOnce(
        new Error('Flag failed')
      );

      const { result } = renderHook(() =>
        useVerificationActions({ matterId })
      );

      await act(async () => {
        await result.current.bulkFlag(['1', '2'], 'Review');
      });

      const store = useVerificationStore.getState();
      expect(store.queue.find((i) => i.id === '1')?.decision).toBe(
        VerificationDecision.PENDING
      );
      expect(store.queue.find((i) => i.id === '2')?.decision).toBe(
        VerificationDecision.PENDING
      );
    });
  });
});
