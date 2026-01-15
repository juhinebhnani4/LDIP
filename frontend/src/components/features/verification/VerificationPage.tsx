'use client';

/**
 * Verification Page Component
 *
 * Main page component for the verification queue UI.
 *
 * Story 8-5: Implement Verification Queue UI (Task 1)
 * Implements all AC: #1-5
 */

import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { VerificationStats } from './VerificationStats';
import { VerificationQueue } from './VerificationQueue';
import { VerificationActions } from './VerificationActions';
import { VerificationFilters } from './VerificationFilters';
import { VerificationNotesDialog } from './VerificationNotesDialog';
import { useVerificationQueue } from '@/hooks/useVerificationQueue';
import { useVerificationStats } from '@/hooks/useVerificationStats';
import { useVerificationActions } from '@/hooks/useVerificationActions';
import { useVerificationStore } from '@/stores/verificationStore';

interface VerificationPageProps {
  /** Matter ID */
  matterId: string;
}

/**
 * Verification Center page component.
 *
 * Provides complete verification workflow UI:
 * - Statistics header with progress
 * - Filter controls
 * - Queue data table with selection
 * - Bulk action toolbar
 * - Notes dialog for reject/flag
 *
 * @example
 * ```tsx
 * <VerificationPage matterId="matter-123" />
 * ```
 */
export function VerificationPage({ matterId }: VerificationPageProps) {
  // Dialog state for notes input
  const [notesDialogOpen, setNotesDialogOpen] = useState(false);
  const [notesAction, setNotesAction] = useState<'reject' | 'flag'>('reject');
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [isBulkAction, setIsBulkAction] = useState(false);

  // Hooks for data fetching
  const {
    filteredQueue,
    filters,
    isLoading: queueLoading,
    error: queueError,
    setFilters,
    resetFilters,
    findingTypes,
    refresh: refreshQueue,
  } = useVerificationQueue({ matterId });

  const {
    stats,
    isLoading: statsLoading,
    refresh: refreshStats,
  } = useVerificationStats({ matterId });

  // Store selectors
  const selectedIds = useVerificationStore((state) => state.selectedIds);
  const toggleSelected = useVerificationStore((state) => state.toggleSelected);
  const selectAll = useVerificationStore((state) => state.selectAll);
  const clearSelection = useVerificationStore((state) => state.clearSelection);

  // Action handlers with callbacks
  const {
    approve,
    reject,
    flag,
    bulkApprove,
    bulkReject,
    bulkFlag,
    isActioning,
    currentAction,
    processingIds,
  } = useVerificationActions({
    matterId,
    onSuccess: (action) => {
      const actionName = action.replace('bulk-', '').replace('-', ' ');
      toast.success(`Successfully ${actionName}ed`);
      // Refresh data after successful action
      refreshQueue();
      refreshStats();
    },
    onError: (action, id, error) => {
      toast.error(`Failed to ${action}: ${error}`);
    },
  });

  // Handle single approve
  const handleApprove = useCallback(
    async (id: string) => {
      await approve(id);
    },
    [approve]
  );

  // Handle single reject - show notes dialog
  const handleRejectClick = useCallback((id: string) => {
    setPendingActionId(id);
    setNotesAction('reject');
    setIsBulkAction(false);
    setNotesDialogOpen(true);
  }, []);

  // Handle single flag - show notes dialog
  const handleFlagClick = useCallback((id: string) => {
    setPendingActionId(id);
    setNotesAction('flag');
    setIsBulkAction(false);
    setNotesDialogOpen(true);
  }, []);

  // Handle bulk approve
  const handleBulkApprove = useCallback(async () => {
    await bulkApprove(selectedIds);
  }, [bulkApprove, selectedIds]);

  // Handle bulk reject - show notes dialog
  const handleBulkRejectClick = useCallback(() => {
    setNotesAction('reject');
    setIsBulkAction(true);
    setNotesDialogOpen(true);
  }, []);

  // Handle bulk flag - show notes dialog
  const handleBulkFlagClick = useCallback(() => {
    setNotesAction('flag');
    setIsBulkAction(true);
    setNotesDialogOpen(true);
  }, []);

  // Handle notes submission
  const handleNotesSubmit = useCallback(
    async (notes: string) => {
      if (isBulkAction) {
        if (notesAction === 'reject') {
          await bulkReject(selectedIds, notes);
        } else {
          await bulkFlag(selectedIds, notes);
        }
      } else if (pendingActionId) {
        if (notesAction === 'reject') {
          await reject(pendingActionId, notes);
        } else {
          await flag(pendingActionId, notes);
        }
      }
      setNotesDialogOpen(false);
      setPendingActionId(null);
    },
    [isBulkAction, notesAction, pendingActionId, selectedIds, bulkReject, bulkFlag, reject, flag]
  );

  return (
    <div className="space-y-6 p-6">
      {/* Statistics Header */}
      <VerificationStats stats={stats} isLoading={statsLoading} />

      {/* Filter Controls */}
      <VerificationFilters
        filters={filters}
        onFiltersChange={setFilters}
        onReset={resetFilters}
        findingTypes={findingTypes}
        hasActiveFilters={filters.findingType !== null || filters.confidenceTier !== null}
      />

      {/* Bulk Actions Toolbar (shown when items selected) */}
      <VerificationActions
        selectedCount={selectedIds.length}
        isActioning={isActioning}
        currentAction={currentAction}
        onBulkApprove={handleBulkApprove}
        onBulkReject={handleBulkRejectClick}
        onBulkFlag={handleBulkFlagClick}
        onClearSelection={clearSelection}
      />

      {/* Error Display */}
      {queueError && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {queueError}
        </div>
      )}

      {/* Queue DataTable */}
      <VerificationQueue
        data={filteredQueue}
        isLoading={queueLoading}
        onApprove={handleApprove}
        onReject={handleRejectClick}
        onFlag={handleFlagClick}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelected}
        onSelectAll={selectAll}
        processingIds={processingIds}
      />

      {/* Notes Dialog for Reject/Flag */}
      <VerificationNotesDialog
        open={notesDialogOpen}
        onOpenChange={setNotesDialogOpen}
        action={notesAction}
        itemCount={isBulkAction ? selectedIds.length : 1}
        isLoading={isActioning}
        onSubmit={handleNotesSubmit}
      />
    </div>
  );
}
