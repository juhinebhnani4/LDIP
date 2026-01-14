'use client';

/**
 * Verification Actions Hook
 *
 * Custom hook for verification action handlers with optimistic updates.
 *
 * Story 8-5: Implement Verification Queue UI (Task 9.3)
 */

import { useCallback, useState } from 'react';
import { useVerificationStore } from '@/stores/verificationStore';
import { verificationsApi } from '@/lib/api/verifications';
import { VerificationDecision } from '@/types';
import type { VerificationQueueItem } from '@/types';

interface UseVerificationActionsOptions {
  /** Matter ID for API calls */
  matterId: string;
  /** Callback after successful action */
  onSuccess?: (action: string, id: string) => void;
  /** Callback after action error */
  onError?: (action: string, id: string, error: string) => void;
}

interface UseVerificationActionsReturn {
  /** Approve a verification */
  approve: (id: string, notes?: string) => Promise<void>;
  /** Reject a verification (notes required) */
  reject: (id: string, notes: string) => Promise<void>;
  /** Flag a verification for review (notes required) */
  flag: (id: string, notes: string) => Promise<void>;
  /** Bulk approve selected verifications */
  bulkApprove: (ids: string[], notes?: string) => Promise<void>;
  /** Bulk reject selected verifications (notes required) */
  bulkReject: (ids: string[], notes: string) => Promise<void>;
  /** Bulk flag selected verifications (notes required) */
  bulkFlag: (ids: string[], notes: string) => Promise<void>;
  /** Whether an action is in progress */
  isActioning: boolean;
  /** Current action being performed */
  currentAction: string | null;
  /** IDs currently being processed */
  processingIds: string[];
}

/**
 * Hook for verification action handlers with optimistic updates.
 *
 * @param options - Configuration options
 * @returns Action handlers and state
 *
 * @example
 * ```tsx
 * const {
 *   approve,
 *   reject,
 *   bulkApprove,
 *   isActioning,
 * } = useVerificationActions({ matterId: 'matter-123' });
 *
 * // Approve a single verification
 * await approve('ver-456');
 *
 * // Bulk approve selected
 * await bulkApprove(selectedIds);
 * ```
 */
export function useVerificationActions(
  options: UseVerificationActionsOptions
): UseVerificationActionsReturn {
  const { matterId, onSuccess, onError } = options;

  // Local state for action progress
  const [isActioning, setIsActioning] = useState(false);
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [processingIds, setProcessingIds] = useState<string[]>([]);

  // Store state and actions
  const queue = useVerificationStore((state) => state.queue);
  const removeFromQueue = useVerificationStore((state) => state.removeFromQueue);
  const removeMultipleFromQueue = useVerificationStore(
    (state) => state.removeMultipleFromQueue
  );
  const addToQueue = useVerificationStore((state) => state.addToQueue);
  const addMultipleToQueue = useVerificationStore((state) => state.addMultipleToQueue);
  const updateQueueItem = useVerificationStore((state) => state.updateQueueItem);
  const clearSelection = useVerificationStore((state) => state.clearSelection);

  /**
   * Approve a single verification.
   */
  const approve = useCallback(
    async (id: string, notes?: string) => {
      setIsActioning(true);
      setCurrentAction('approve');
      setProcessingIds([id]);

      // Capture item before removal for potential rollback
      const itemToRestore = queue.find((item) => item.id === id);

      try {
        // Optimistic update - remove from queue immediately
        removeFromQueue(id);

        // Make API call
        await verificationsApi.approve(matterId, id, { notes });

        onSuccess?.('approve', id);
      } catch (err) {
        // Rollback: restore item to queue on API failure
        if (itemToRestore) {
          addToQueue(itemToRestore);
        }
        const message = err instanceof Error ? err.message : 'Failed to approve';
        onError?.('approve', id, message);
      } finally {
        setIsActioning(false);
        setCurrentAction(null);
        setProcessingIds([]);
      }
    },
    [matterId, queue, removeFromQueue, addToQueue, onSuccess, onError]
  );

  /**
   * Reject a single verification.
   */
  const reject = useCallback(
    async (id: string, notes: string) => {
      setIsActioning(true);
      setCurrentAction('reject');
      setProcessingIds([id]);

      // Capture item before removal for potential rollback
      const itemToRestore = queue.find((item) => item.id === id);

      try {
        // Optimistic update
        removeFromQueue(id);

        // Make API call
        await verificationsApi.reject(matterId, id, notes);

        onSuccess?.('reject', id);
      } catch (err) {
        // Rollback: restore item to queue on API failure
        if (itemToRestore) {
          addToQueue(itemToRestore);
        }
        const message = err instanceof Error ? err.message : 'Failed to reject';
        onError?.('reject', id, message);
      } finally {
        setIsActioning(false);
        setCurrentAction(null);
        setProcessingIds([]);
      }
    },
    [matterId, queue, removeFromQueue, addToQueue, onSuccess, onError]
  );

  /**
   * Flag a single verification.
   */
  const flag = useCallback(
    async (id: string, notes: string) => {
      setIsActioning(true);
      setCurrentAction('flag');
      setProcessingIds([id]);

      try {
        // Optimistic update - update decision but keep in queue
        updateQueueItem(id, { decision: VerificationDecision.FLAGGED });

        // Make API call
        await verificationsApi.flag(matterId, id, notes);

        onSuccess?.('flag', id);
      } catch (err) {
        // Revert optimistic update
        updateQueueItem(id, { decision: VerificationDecision.PENDING });

        const message = err instanceof Error ? err.message : 'Failed to flag';
        onError?.('flag', id, message);
      } finally {
        setIsActioning(false);
        setCurrentAction(null);
        setProcessingIds([]);
      }
    },
    [matterId, updateQueueItem, onSuccess, onError]
  );

  /**
   * Bulk approve selected verifications.
   */
  const bulkApprove = useCallback(
    async (ids: string[], notes?: string) => {
      if (ids.length === 0) return;

      setIsActioning(true);
      setCurrentAction('bulk-approve');
      setProcessingIds(ids);

      // Capture items before removal for potential rollback
      const idSet = new Set(ids);
      const itemsToRestore = queue.filter((item) => idSet.has(item.id));

      try {
        // Optimistic update
        removeMultipleFromQueue(ids);
        clearSelection();

        // Make API call
        await verificationsApi.bulkUpdate(
          matterId,
          ids,
          VerificationDecision.APPROVED,
          notes
        );

        onSuccess?.('bulk-approve', ids.join(','));
      } catch (err) {
        // Rollback: restore items to queue on API failure
        if (itemsToRestore.length > 0) {
          addMultipleToQueue(itemsToRestore);
        }
        const message = err instanceof Error ? err.message : 'Failed to bulk approve';
        onError?.('bulk-approve', ids.join(','), message);
      } finally {
        setIsActioning(false);
        setCurrentAction(null);
        setProcessingIds([]);
      }
    },
    [matterId, queue, removeMultipleFromQueue, addMultipleToQueue, clearSelection, onSuccess, onError]
  );

  /**
   * Bulk reject selected verifications.
   */
  const bulkReject = useCallback(
    async (ids: string[], notes: string) => {
      if (ids.length === 0) return;

      setIsActioning(true);
      setCurrentAction('bulk-reject');
      setProcessingIds(ids);

      // Capture items before removal for potential rollback
      const idSet = new Set(ids);
      const itemsToRestore = queue.filter((item) => idSet.has(item.id));

      try {
        // Optimistic update
        removeMultipleFromQueue(ids);
        clearSelection();

        // Make API call
        await verificationsApi.bulkUpdate(
          matterId,
          ids,
          VerificationDecision.REJECTED,
          notes
        );

        onSuccess?.('bulk-reject', ids.join(','));
      } catch (err) {
        // Rollback: restore items to queue on API failure
        if (itemsToRestore.length > 0) {
          addMultipleToQueue(itemsToRestore);
        }
        const message = err instanceof Error ? err.message : 'Failed to bulk reject';
        onError?.('bulk-reject', ids.join(','), message);
      } finally {
        setIsActioning(false);
        setCurrentAction(null);
        setProcessingIds([]);
      }
    },
    [matterId, queue, removeMultipleFromQueue, addMultipleToQueue, clearSelection, onSuccess, onError]
  );

  /**
   * Bulk flag selected verifications.
   */
  const bulkFlag = useCallback(
    async (ids: string[], notes: string) => {
      if (ids.length === 0) return;

      setIsActioning(true);
      setCurrentAction('bulk-flag');
      setProcessingIds(ids);

      try {
        // Optimistic update - update decision for all items
        for (const id of ids) {
          updateQueueItem(id, { decision: VerificationDecision.FLAGGED });
        }
        clearSelection();

        // Make API call
        await verificationsApi.bulkUpdate(
          matterId,
          ids,
          VerificationDecision.FLAGGED,
          notes
        );

        onSuccess?.('bulk-flag', ids.join(','));
      } catch (err) {
        // Revert optimistic updates
        for (const id of ids) {
          updateQueueItem(id, { decision: VerificationDecision.PENDING });
        }

        const message = err instanceof Error ? err.message : 'Failed to bulk flag';
        onError?.('bulk-flag', ids.join(','), message);
      } finally {
        setIsActioning(false);
        setCurrentAction(null);
        setProcessingIds([]);
      }
    },
    [matterId, updateQueueItem, clearSelection, onSuccess, onError]
  );

  return {
    approve,
    reject,
    flag,
    bulkApprove,
    bulkReject,
    bulkFlag,
    isActioning,
    currentAction,
    processingIds,
  };
}
