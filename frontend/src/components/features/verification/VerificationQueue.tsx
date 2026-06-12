'use client';

/**
 * Verification Queue DataTable Component
 *
 * Displays verification queue with selection, sorting, and actions.
 *
 * Story 8-5: Implement Verification Queue UI (Task 3)
 * Implements AC #1: DataTable with columns
 */

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ResponsiveTable, type ResponsiveColumn } from '@/components/ui/responsive-table';
import { cn } from '@/lib/utils';
import { Check, X, Flag, CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { VerificationQueueItem } from '@/types';
import {
  formatFindingType,
  getFindingTypeIcon,
} from '@/stores/verificationStore';
import { getDecisionStatusDisplay, formatConfidenceTooltip } from '@/lib/utils/confidenceDisplay';
import { usePowerUserMode } from '@/hooks/usePowerUserMode';

type SortDirection = 'asc' | 'desc' | null;
type SortColumn = 'findingType' | 'findingSummary' | 'confidence' | 'sourceDocument' | null;

interface VerificationQueueProps {
  /** Queue items to display */
  data: VerificationQueueItem[];
  /** Loading state */
  isLoading?: boolean;
  /** Callback when approve is clicked */
  onApprove: (id: string) => void;
  /** Callback when reject is clicked */
  onReject: (id: string) => void;
  /** Callback when flag is clicked */
  onFlag: (id: string) => void;
  /** Currently selected IDs */
  selectedIds: string[];
  /** Callback when selection is toggled */
  onToggleSelect: (id: string) => void;
  /** Callback when all rows are selected */
  onSelectAll: (ids: string[]) => void;
  /** IDs currently being processed */
  processingIds?: string[];
  /** Story 3.6: Callback when item is clicked/focused */
  onItemClick?: (id: string) => void;
  /** Story 3.6: Enable keyboard shortcuts */
  enableKeyboardShortcuts?: boolean;
}

/**
 * Verification queue data table with selection and actions.
 *
 * Features:
 * - Sortable columns (default: confidence ascending - lowest first)
 * - Row selection with checkboxes
 * - Confidence progress bars with ADR-004 color coding
 * - Inline action buttons
 *
 * @example
 * ```tsx
 * <VerificationQueue
 *   data={queue}
 *   onApprove={handleApprove}
 *   onReject={handleReject}
 *   onFlag={handleFlag}
 *   selectedIds={selectedIds}
 *   onToggleSelect={handleToggle}
 *   onSelectAll={handleSelectAll}
 * />
 * ```
 */
export function VerificationQueue({
  data,
  isLoading = false,
  onApprove,
  onReject,
  onFlag,
  selectedIds,
  onToggleSelect,
  onSelectAll,
  processingIds = [],
  onItemClick,
  enableKeyboardShortcuts = true,
}: VerificationQueueProps) {
  // Story 6.1: Gate advanced keyboard shortcuts behind Power User Mode
  const { isPowerUser } = usePowerUserMode();
  const effectiveKeyboardShortcuts = enableKeyboardShortcuts && isPowerUser;

  // Sorting state - default: confidence ascending (lowest first = highest priority)
  const [sortColumn, setSortColumn] = useState<SortColumn>('confidence');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Story 3.6: Track focused row by ID for keyboard navigation
  // Code Review Fix: Use ID instead of index to prevent stale references after data changes
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  // Handle column header click for sorting
  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      // Toggle direction or clear
      if (sortDirection === 'asc') {
        setSortDirection('desc');
      } else if (sortDirection === 'desc') {
        setSortDirection(null);
        setSortColumn(null);
      }
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Sorted data
  const sortedData = useMemo(() => {
    if (!sortColumn || !sortDirection) {
      return data;
    }

    return [...data].sort((a, b) => {
      let comparison = 0;

      switch (sortColumn) {
        case 'confidence':
          comparison = a.confidence - b.confidence;
          break;
        case 'findingType':
          comparison = a.findingType.localeCompare(b.findingType);
          break;
        case 'findingSummary':
          comparison = a.findingSummary.localeCompare(b.findingSummary);
          break;
        case 'sourceDocument':
          comparison = (a.sourceDocument ?? '').localeCompare(b.sourceDocument ?? '');
          break;
      }

      return sortDirection === 'desc' ? -comparison : comparison;
    });
  }, [data, sortColumn, sortDirection]);

  // Check if all are selected
  const allSelected = data.length > 0 && selectedIds.length === data.length;
  const someSelected = selectedIds.length > 0 && !allSelected;

  // Handle select all toggle
  const handleSelectAllToggle = (checked: boolean) => {
    if (checked) {
      onSelectAll(data.map((d) => d.id));
    } else {
      onSelectAll([]);
    }
  };

  // Story 3.6: Get focused item and its index (from sortedData)
  // Code Review Fix: Derive index from ID to handle data changes safely
  const { focusedItem } = useMemo(() => {
    if (!focusedId) return { focusedItem: null, focusedIndex: -1 };
    const index = sortedData.findIndex(item => item.id === focusedId);
    return {
      focusedItem: index >= 0 ? sortedData[index] : null,
      focusedIndex: index,
    };
  }, [focusedId, sortedData]);

  // Story 3.6: Keyboard navigation handlers
  // Code Review Fix: Navigate by ID to handle data changes safely
  const moveToNextItem = useCallback(() => {
    if (sortedData.length === 0) return;
    const currentIndex = focusedId ? sortedData.findIndex(item => item.id === focusedId) : -1;
    const nextIndex = currentIndex + 1 >= sortedData.length ? 0 : currentIndex + 1;
    const nextItem = sortedData[nextIndex];
    if (nextItem) setFocusedId(nextItem.id);
  }, [sortedData, focusedId]);

  const moveToPrevItem = useCallback(() => {
    if (sortedData.length === 0) return;
    const currentIndex = focusedId ? sortedData.findIndex(item => item.id === focusedId) : 0;
    const prevIndex = currentIndex - 1 < 0 ? sortedData.length - 1 : currentIndex - 1;
    const prevItem = sortedData[prevIndex];
    if (prevItem) setFocusedId(prevItem.id);
  }, [sortedData, focusedId]);

  const approveCurrentItem = useCallback(() => {
    if (focusedItem && !processingIds.includes(focusedItem.id)) {
      onApprove(focusedItem.id);
    }
  }, [focusedItem, processingIds, onApprove]);

  const rejectCurrentItem = useCallback(() => {
    if (focusedItem && !processingIds.includes(focusedItem.id)) {
      onReject(focusedItem.id);
    }
  }, [focusedItem, processingIds, onReject]);

  const flagCurrentItem = useCallback(() => {
    if (focusedItem && !processingIds.includes(focusedItem.id)) {
      onFlag(focusedItem.id);
    }
  }, [focusedItem, processingIds, onFlag]);

  const toggleCurrentSelection = useCallback(() => {
    if (focusedItem) {
      onToggleSelect(focusedItem.id);
    }
  }, [focusedItem, onToggleSelect]);

  const openCurrentItem = useCallback(() => {
    if (focusedItem && onItemClick) {
      onItemClick(focusedItem.id);
    }
  }, [focusedItem, onItemClick]);

  // Story 3.6: Keyboard event handler
  // Story 6.1: Gate keyboard shortcuts behind Power User Mode
  useEffect(() => {
    if (!effectiveKeyboardShortcuts || isLoading || sortedData.length === 0) {
      return;
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      // Code Review Fix: Expanded check for form controls to prevent accidental actions
      const target = e.target as HTMLElement;
      const formTags = ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'];
      if (
        formTags.includes(target.tagName) ||
        target.isContentEditable ||
        target.getAttribute('role') === 'textbox' ||
        target.getAttribute('role') === 'combobox'
      ) {
        return;
      }

      // Initialize focus if not set
      // Code Review Fix: Use ID-based focus
      if (!focusedId && sortedData.length > 0) {
        const firstItem = sortedData[0];
        if (firstItem) setFocusedId(firstItem.id);
      }

      switch (e.key) {
        case 'j':
        case 'ArrowDown':
          e.preventDefault();
          moveToNextItem();
          break;
        case 'k':
        case 'ArrowUp':
          e.preventDefault();
          moveToPrevItem();
          break;
        case 'a':
          if (!e.metaKey && !e.ctrlKey) {
            e.preventDefault();
            approveCurrentItem();
          }
          break;
        case 'r':
          if (!e.metaKey && !e.ctrlKey) {
            e.preventDefault();
            rejectCurrentItem();
          }
          break;
        case 'f':
          if (!e.metaKey && !e.ctrlKey) {
            e.preventDefault();
            flagCurrentItem();
          }
          break;
        case ' ': // Space
          e.preventDefault();
          toggleCurrentSelection();
          break;
        case 'Enter':
          e.preventDefault();
          openCurrentItem();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [
    effectiveKeyboardShortcuts,
    isLoading,
    sortedData,
    focusedId,
    moveToNextItem,
    moveToPrevItem,
    approveCurrentItem,
    rejectCurrentItem,
    flagCurrentItem,
    toggleCurrentSelection,
    openCurrentItem,
  ]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12"><Skeleton className="h-4 w-4" /></TableHead>
              <TableHead><Skeleton className="h-4 w-16" /></TableHead>
              <TableHead><Skeleton className="h-4 w-32" /></TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i}>
                <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                <TableCell><Skeleton className="h-2 w-20" /></TableCell>
                <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                <TableCell><Skeleton className="h-8 w-24" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  // Status badge — defined ONCE and used by both the desktop table and the mobile
  // card (via the column below). No table-vs-card duplicate logic.
  const renderStatus = (item: VerificationQueueItem) => {
    const status = getDecisionStatusDisplay(item.decision, item.confidence);
    const StatusIcon =
      status.level === 'approved'
        ? CheckCircle2
        : status.level === 'rejected' || status.level === 'review_required'
          ? XCircle
          : AlertCircle;
    return (
      <div className="flex items-center gap-2" title={formatConfidenceTooltip(item.confidence)}>
        <Badge variant="outline" className={status.badgeClass}>
          <StatusIcon className="mr-1 h-3 w-3" />
          {status.shortLabel}
        </Badge>
      </div>
    );
  };

  const columns: ResponsiveColumn<VerificationQueueItem>[] = [
    {
      id: 'findingType',
      header: 'Type',
      sortable: true,
      isPrimary: true,
      cell: (item) => (
        <span className="flex items-center gap-2">
          <span>{getFindingTypeIcon(item.findingType)}</span>
          <span className="font-medium">{formatFindingType(item.findingType)}</span>
        </span>
      ),
    },
    {
      id: 'findingSummary',
      header: 'Description',
      sortable: true,
      cardLabel: 'Description',
      cardBlock: true,
      cell: (item) => (
        <span className="block break-words line-clamp-2 lg:max-w-[360px]" title={item.findingSummary}>
          {item.findingSummary}
        </span>
      ),
    },
    {
      id: 'confidence',
      header: 'Status',
      sortable: true,
      cardLabel: 'Status',
      cell: (item) => renderStatus(item),
    },
    {
      id: 'sourceDocument',
      header: 'Source',
      sortable: true,
      cardLabel: 'Source',
      cell: (item) => (
        <span className="break-words text-sm text-muted-foreground">{item.sourceDocument ?? 'N/A'}</span>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      cardLabel: null,
      cardBlock: true,
      align: 'right',
      cell: (item) => {
        const isProcessing = processingIds.includes(item.id);
        return (
          <div className="flex items-center gap-1 lg:justify-end" onClick={(e) => e.stopPropagation()}>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-green-600 hover:bg-green-50 hover:text-green-700 dark:hover:bg-green-950"
              onClick={() => onApprove(item.id)}
              aria-label="Approve"
              disabled={isProcessing}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950"
              onClick={() => onReject(item.id)}
              aria-label="Reject"
              disabled={isProcessing}
            >
              <X className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-yellow-600 hover:bg-yellow-50 hover:text-yellow-700 dark:hover:bg-yellow-950"
              onClick={() => onFlag(item.id)}
              aria-label="Flag"
              disabled={isProcessing}
            >
              <Flag className="h-4 w-4" />
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="rounded-md border" ref={tableRef}>
      {/* Story 3.6: Keyboard shortcuts hint */}
      {/* Story 6.1: Only show shortcuts hint in Power User Mode */}
      {effectiveKeyboardShortcuts && sortedData.length > 0 && (
        <div className="px-3 py-1.5 text-xs text-muted-foreground bg-muted/30 border-b flex items-center gap-4 flex-wrap">
          <span className="font-medium">Shortcuts:</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">↑↓</kbd> or <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">j/k</kbd> Navigate</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">a</kbd> Approve</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">r</kbd> Reject</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">f</kbd> Flag</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Space</kbd> Select</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> Open</span>
        </div>
      )}
      <ResponsiveTable<VerificationQueueItem>
        columns={columns}
        rows={sortedData}
        getRowId={(item) => item.id}
        onRowClick={(item) => {
          setFocusedId(item.id);
          onItemClick?.(item.id);
        }}
        rowClassName={(item) =>
          cn(
            processingIds.includes(item.id) && 'pointer-events-none opacity-50',
            item.id === focusedId && 'bg-primary/5 ring-2 ring-inset ring-primary',
            selectedIds.includes(item.id) && 'bg-muted/40'
          )
        }
        selection={{
          isSelected: (item) => selectedIds.includes(item.id),
          onToggle: (item) => onToggleSelect(item.id),
          ariaLabel: () => 'Select row',
          isDisabled: (item) => processingIds.includes(item.id),
          allSelected,
          someSelected,
          onToggleAll: handleSelectAllToggle,
        }}
        sort={{
          columnId: sortColumn ?? '',
          direction: sortDirection === 'desc' ? 'desc' : 'asc',
          onSortChange: (id) => handleSort(id as SortColumn),
        }}
        emptyState={
          <div className="py-12 text-center text-muted-foreground">No verifications pending.</div>
        }
      />
    </div>
  );
}
