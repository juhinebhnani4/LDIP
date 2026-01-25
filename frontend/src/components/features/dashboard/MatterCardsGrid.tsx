'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Plus, FolderOpen } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { MatterCard } from './MatterCard';
import { MatterCardErrorBoundary } from './MatterCardErrorBoundary';
import { BulkMatterSelectionToolbar } from './BulkMatterSelectionToolbar';
import { BulkDeleteMattersDialog } from './BulkDeleteMattersDialog';
import { useMatterStore, selectSortedMatters, initializeViewMode } from '@/stores/matterStore';
import {
  useBackgroundProcessingStore,
  selectCompletedMatters,
} from '@/stores/backgroundProcessingStore';
import { mattersApi } from '@/lib/api/matters';
import { cn } from '@/lib/utils';

/**
 * Matter Cards Grid Component
 *
 * Displays matters as a responsive grid of cards.
 * Includes "New Matter" card as first item.
 * Handles loading, empty, and error states.
 * Subscribes to background processing for live status updates.
 *
 * Grid layout:
 * - Desktop: 3 columns
 * - Tablet: 2 columns
 * - Mobile: 1 column
 *
 * Story 9-6: Added background processing subscription for live matter status updates
 */

interface MatterCardsGridProps {
  /** Optional className for styling */
  className?: string;
}

/** New Matter card - always first in grid */
function NewMatterCard() {
  return (
    <Link href="/upload" aria-label="Create new matter">
      <Card className="h-full min-h-[200px] border-dashed hover:border-primary hover:bg-accent/50 transition-colors cursor-pointer">
        <CardContent className="flex flex-col items-center justify-center h-full gap-3 py-8">
          <div className="rounded-full bg-primary/10 p-4">
            <Plus className="size-8 text-primary" />
          </div>
          <span className="font-medium text-muted-foreground">New Matter</span>
        </CardContent>
      </Card>
    </Link>
  );
}

/** Loading skeleton for matter cards */
function MatterCardSkeleton() {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
        <div className="flex gap-3">
          <Skeleton className="h-16 flex-1" />
          <Skeleton className="h-16 flex-1" />
        </div>
        <Skeleton className="h-9 w-full mt-2" />
      </CardContent>
    </Card>
  );
}

/** Empty state when no matters exist */
function EmptyState() {
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-16 text-center">
      <div className="rounded-full bg-muted p-4 mb-4">
        <FolderOpen className="size-10 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold mb-2">No matters yet</h3>
      <p className="text-muted-foreground mb-6 max-w-sm">
        Create your first matter to start uploading documents and extracting insights.
      </p>
      <Link
        href="/upload"
        className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <Plus className="size-4" />
        Create Matter
      </Link>
    </div>
  );
}

/** Error state */
function ErrorState({ error }: { error: string }) {
  const handleRetry = () => {
    useMatterStore.getState().fetchMatters();
  };

  return (
    <div className="col-span-full flex flex-col items-center justify-center py-16 text-center">
      <div className="rounded-full bg-destructive/10 p-4 mb-4">
        <FolderOpen className="size-10 text-destructive" />
      </div>
      <h3 className="text-lg font-semibold mb-2">Failed to load matters</h3>
      <p className="text-muted-foreground mb-6 max-w-sm">{error}</p>
      <button
        onClick={handleRetry}
        className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Try Again
      </button>
    </div>
  );
}

export function MatterCardsGrid({ className }: MatterCardsGridProps) {
  const isLoading = useMatterStore((state) => state.isLoading);
  const error = useMatterStore((state) => state.error);
  const viewMode = useMatterStore((state) => state.viewMode);
  const deleteMattersFromStore = useMatterStore((state) => state.deleteMatters);
  // useShallow prevents re-renders when array contents are equal
  const sortedMatters = useMatterStore(useShallow(selectSortedMatters));

  // Subscribe to background processing for live updates (Story 9-6)
  const completedBackgroundMatters = useBackgroundProcessingStore(
    useShallow(selectCompletedMatters)
  );
  const removeBackgroundMatter = useBackgroundProcessingStore(
    (state) => state.removeBackgroundMatter
  );

  // Selection state for bulk operations
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);

  // Filter to only owner matters (only owners can delete)
  const deletableMatters = sortedMatters.filter((m) => m.role === 'owner');
  const deletableMatterIds = new Set(deletableMatters.map((m) => m.id));

  // Selection mode is active when there are matters to select
  const selectionMode = deletableMatters.length > 0;

  // Compute selection states
  const selectedCount = selectedIds.size;
  const allSelected = deletableMatters.length > 0 && selectedCount === deletableMatters.length;
  const someSelected = selectedCount > 0 && !allSelected;

  // Get titles of selected matters for dialog
  const selectedMatterTitles = sortedMatters
    .filter((m) => selectedIds.has(m.id))
    .map((m) => m.title);

  // Selection handlers
  const handleSelectAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedIds(new Set(deletableMatters.map((m) => m.id)));
      } else {
        setSelectedIds(new Set());
      }
    },
    [deletableMatters]
  );

  const handleSelectOne = useCallback((matterId: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(matterId);
      } else {
        newSet.delete(matterId);
      }
      return newSet;
    });
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // Bulk delete handler
  const handleBulkDelete = useCallback(async () => {
    const idsToDelete = Array.from(selectedIds);
    if (idsToDelete.length === 0) return;

    const result = await mattersApi.deleteMany(idsToDelete);

    // Update local store for successful deletions
    if (result.succeeded > 0) {
      deleteMattersFromStore(idsToDelete.slice(0, result.succeeded));
    }

    // Show result toast
    if (result.failed === 0) {
      toast.success(`Deleted ${result.succeeded} matter${result.succeeded !== 1 ? 's' : ''}`);
    } else if (result.succeeded > 0) {
      toast.warning(
        `Deleted ${result.succeeded} matter${result.succeeded !== 1 ? 's' : ''}, ` +
          `failed to delete ${result.failed}`
      );
    } else {
      toast.error(`Failed to delete matters: ${result.errors[0] || 'Unknown error'}`);
    }

    // Clear selection
    setSelectedIds(new Set());
  }, [selectedIds, deleteMattersFromStore]);

  // Initialize view mode from localStorage and fetch matters on mount
  useEffect(() => {
    initializeViewMode();
    useMatterStore.getState().fetchMatters();
  }, []);

  // Refetch matters when background processing completes (Story 9-6)
  useEffect(() => {
    if (completedBackgroundMatters.length > 0) {
      // Force refresh matters to get updated status (ignores stale check)
      useMatterStore.getState().forceRefreshMatters();

      // Clean up completed matters from background store after a delay
      // This allows the notification to be seen before cleanup
      const timeoutId = setTimeout(() => {
        completedBackgroundMatters.forEach((matter) => {
          removeBackgroundMatter(matter.matterId);
        });
      }, 5000);

      return () => clearTimeout(timeoutId);
    }
  }, [completedBackgroundMatters, removeBackgroundMatter]);

  // Clear selection when matters change (e.g., after deletion)
  useEffect(() => {
    setSelectedIds((prev) => {
      const currentMatterIds = new Set(sortedMatters.map((m) => m.id));
      const newSelected = new Set<string>();
      prev.forEach((id) => {
        if (currentMatterIds.has(id)) {
          newSelected.add(id);
        }
      });
      return newSelected;
    });
  }, [sortedMatters]);

  const gridClasses = cn(
    'grid gap-4',
    viewMode === 'grid'
      ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
      : 'grid-cols-1',
    className
  );

  // Loading state
  if (isLoading) {
    return (
      <div className={gridClasses}>
        <NewMatterCard />
        {[1, 2, 3, 4, 5].map((i) => (
          <MatterCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={gridClasses}>
        <ErrorState error={error} />
      </div>
    );
  }

  // Empty state (no matters)
  if (sortedMatters.length === 0) {
    return (
      <div className={gridClasses}>
        <EmptyState />
      </div>
    );
  }

  // Normal state with matters
  return (
    <>
      {/* Bulk selection toolbar - show when there are deletable matters */}
      {selectionMode && (
        <BulkMatterSelectionToolbar
          totalCount={deletableMatters.length}
          selectedCount={selectedCount}
          allSelected={allSelected}
          someSelected={someSelected}
          onSelectAllChange={handleSelectAll}
          onDeleteClick={() => setBulkDeleteDialogOpen(true)}
          onClearSelection={handleClearSelection}
        />
      )}

      {/* Matter cards grid */}
      <div
        className={gridClasses}
        role="feed"
        aria-label="Matter cards"
        aria-busy={isLoading}
        data-tour="matter-cards"
      >
        <NewMatterCard />
        {sortedMatters.map((matter) => (
          <MatterCardErrorBoundary key={matter.id} matterId={matter.id}>
            <MatterCard
              matter={matter}
              selectionMode={selectionMode}
              isSelected={selectedIds.has(matter.id)}
              onSelectChange={(checked) => handleSelectOne(matter.id, checked)}
              canDelete={deletableMatterIds.has(matter.id)}
            />
          </MatterCardErrorBoundary>
        ))}
      </div>

      {/* Bulk delete confirmation dialog */}
      <BulkDeleteMattersDialog
        open={bulkDeleteDialogOpen}
        onOpenChange={setBulkDeleteDialogOpen}
        matterTitles={selectedMatterTitles}
        onDelete={handleBulkDelete}
      />
    </>
  );
}
