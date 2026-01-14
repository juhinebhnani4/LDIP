'use client';

/**
 * Verification Action Buttons Component
 *
 * Bulk action toolbar for verification queue.
 *
 * Story 8-5: Implement Verification Queue UI (Task 4)
 * Implements AC #2, #3: Bulk approve/reject actions
 */

import { Button } from '@/components/ui/button';
import { Check, X, Flag, Loader2 } from 'lucide-react';

interface VerificationActionsProps {
  /** Number of selected items */
  selectedCount: number;
  /** Whether an action is currently in progress */
  isActioning: boolean;
  /** Current action being performed */
  currentAction: string | null;
  /** Callback for bulk approve */
  onBulkApprove: () => void;
  /** Callback for bulk reject */
  onBulkReject: () => void;
  /** Callback for bulk flag */
  onBulkFlag: () => void;
  /** Callback to clear selection */
  onClearSelection: () => void;
}

/**
 * Bulk action toolbar for verification queue.
 *
 * Shows when items are selected and provides bulk action buttons.
 *
 * @example
 * ```tsx
 * <VerificationActions
 *   selectedCount={3}
 *   isActioning={false}
 *   currentAction={null}
 *   onBulkApprove={() => handleBulkApprove(selectedIds)}
 *   onBulkReject={() => setRejectDialogOpen(true)}
 *   onBulkFlag={() => setFlagDialogOpen(true)}
 *   onClearSelection={clearSelection}
 * />
 * ```
 */
export function VerificationActions({
  selectedCount,
  isActioning,
  currentAction,
  onBulkApprove,
  onBulkReject,
  onBulkFlag,
  onClearSelection,
}: VerificationActionsProps) {
  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 py-3 px-4 bg-muted/50 rounded-lg border">
      <span className="text-sm font-medium">
        {selectedCount} {selectedCount === 1 ? 'item' : 'items'} selected
      </span>

      <div className="flex-1" />

      <Button
        size="sm"
        variant="outline"
        onClick={onClearSelection}
        disabled={isActioning}
      >
        Clear Selection
      </Button>

      <Button
        size="sm"
        variant="outline"
        className="text-green-600 border-green-500 hover:bg-green-50 dark:hover:bg-green-950"
        onClick={onBulkApprove}
        disabled={isActioning}
      >
        {currentAction === 'bulk-approve' ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : (
          <Check className="h-4 w-4 mr-2" />
        )}
        Approve Selected
      </Button>

      <Button
        size="sm"
        variant="outline"
        className="text-red-600 border-red-500 hover:bg-red-50 dark:hover:bg-red-950"
        onClick={onBulkReject}
        disabled={isActioning}
      >
        {currentAction === 'bulk-reject' ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : (
          <X className="h-4 w-4 mr-2" />
        )}
        Reject Selected
      </Button>

      <Button
        size="sm"
        variant="outline"
        className="text-yellow-600 border-yellow-500 hover:bg-yellow-50 dark:hover:bg-yellow-950"
        onClick={onBulkFlag}
        disabled={isActioning}
      >
        {currentAction === 'bulk-flag' ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : (
          <Flag className="h-4 w-4 mr-2" />
        )}
        Flag Selected
      </Button>
    </div>
  );
}
