'use client';

/**
 * Verification Content Component
 *
 * Client component that orchestrates verification queue data fetching
 * and composition. Follows the Content component pattern used by other
 * workspace tabs (SummaryContent, TimelineContent, CitationsContent).
 *
 * Story 10D.1: Verification Tab Queue (DataTable)
 * Task 1: Create VerificationContent container component
 */

import { useState, useCallback } from 'react';
import type { ConfidenceTier } from '@/types';
import { AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { VerificationStats } from './VerificationStats';
import { VerificationQueue } from './VerificationQueue';
import { VerificationGroupedView } from './VerificationGroupedView';
import { VerificationActions } from './VerificationActions';
import { VerificationFilters } from './VerificationFilters';
import { VerificationNotesDialog } from './VerificationNotesDialog';
import { useVerificationQueue } from '@/hooks/useVerificationQueue';
import { useVerificationStats } from '@/hooks/useVerificationStats';
import { useVerificationActions } from '@/hooks/useVerificationActions';
import { useVerificationStore } from '@/stores/verificationStore';

interface VerificationContentProps {
  /** Matter ID */
  matterId: string;
  /** Optional callback to start a focused review session */
  onStartSession?: () => void;
}

/**
 * Loading skeleton for the verification page
 */
function VerificationSkeleton() {
  return (
    <div className="space-y-6">
      {/* Stats skeleton */}
      <div className="space-y-4 p-4 rounded-lg border bg-card">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-2 w-64" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-9 w-36" />
        </div>
        <div className="flex items-center gap-4">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>

      {/* Filters skeleton */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-24" />
      </div>

      {/* Table skeleton */}
      <div className="rounded-md border">
        <div className="p-4 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-2 w-20" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-8 w-24" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Error state display
 */
function VerificationError({ message }: { message?: string }) {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {message || 'Failed to load verification data. Please try refreshing the page.'}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Verification Content component.
 *
 * Provides the complete verification workflow UI:
 * - Statistics header with progress
 * - Filter controls
 * - Queue data table with selection
 * - Bulk action toolbar
 * - Notes dialog for reject/flag
 *
 * @example
 * ```tsx
 * <VerificationContent matterId="matter-123" />
 * ```
 */
export function VerificationContent({ matterId, onStartSession }: VerificationContentProps) {
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
    onError: (action, _id, error) => {
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

  // Handle tier badge click - apply confidence tier filter
  // Story 10D.2 Task 5.5: Clickable stat cards apply corresponding filter
  const handleTierClick = useCallback(
    (tier: 'required' | 'suggested' | 'optional') => {
      // Map tier names to confidence tier filter values
      const tierToConfidence: Record<string, ConfidenceTier> = {
        required: 'low',      // < 70% confidence
        suggested: 'medium',  // 70-90% confidence
        optional: 'high',     // > 90% confidence
      };
      setFilters({ confidenceTier: tierToConfidence[tier] });
    },
    [setFilters]
  );

  // Show loading state
  if (queueLoading && !filteredQueue.length) {
    return <VerificationSkeleton />;
  }

  // Show error state
  if (queueError && !filteredQueue.length) {
    return <VerificationError message={queueError} />;
  }

  return (
    <div className="space-y-6">
      {/* Statistics Header with clickable tier badges */}
      <VerificationStats
        stats={stats}
        isLoading={statsLoading}
        onStartSession={onStartSession}
        onTierClick={handleTierClick}
      />

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

      {/* Error Display (inline, when data exists) */}
      {queueError && filteredQueue.length > 0 && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {queueError}
        </div>
      )}

      {/* Queue View - conditionally render based on view mode */}
      {filters.view === 'by-type' ? (
        <VerificationGroupedView
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
      ) : (
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
      )}

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
