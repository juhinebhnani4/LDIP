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
import { Checkbox } from '@/components/ui/checkbox';
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
import { Check, X, Flag, ArrowUpDown, ArrowUp, ArrowDown, CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { VerificationQueueItem } from '@/types';
import {
  getConfidenceColorClass,
  formatFindingType,
  getFindingTypeIcon,
} from '@/stores/verificationStore';
import { getVerificationStatus, formatConfidenceTooltip } from '@/lib/utils/confidenceDisplay';
import { usePowerUserMode } from '@/hooks/usePowerUserMode';

type SortDirection = 'asc' | 'desc' | null;
type SortColumn = 'findingType' | 'findingSummary' | 'confidence' | 'sourceDocument' | null;

/**
 * Sort icon component - displays appropriate arrow based on sort state.
 * Defined outside VerificationQueue to avoid recreating during render.
 */
function SortIcon({
  column,
  sortColumn,
  sortDirection,
}: {
  column: SortColumn;
  sortColumn: SortColumn;
  sortDirection: SortDirection;
}) {
  if (sortColumn !== column) {
    return <ArrowUpDown className="ml-2 h-4 w-4" />;
  }
  if (sortDirection === 'asc') {
    return <ArrowUp className="ml-2 h-4 w-4" />;
  }
  return <ArrowDown className="ml-2 h-4 w-4" />;
}

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
  const { focusedItem, focusedIndex } = useMemo(() => {
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
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">
              <Checkbox
                checked={allSelected || (someSelected ? 'indeterminate' : false)}
                onCheckedChange={(checked) => handleSelectAllToggle(!!checked)}
                aria-label="Select all"
              />
            </TableHead>
            <TableHead>
              <Button
                variant="ghost"
                size="sm"
                className="-ml-3 h-8"
                onClick={() => handleSort('findingType')}
              >
                Type
                <SortIcon column="findingType" sortColumn={sortColumn} sortDirection={sortDirection} />
              </Button>
            </TableHead>
            <TableHead>
              <Button
                variant="ghost"
                size="sm"
                className="-ml-3 h-8"
                onClick={() => handleSort('findingSummary')}
              >
                Description
                <SortIcon column="findingSummary" sortColumn={sortColumn} sortDirection={sortDirection} />
              </Button>
            </TableHead>
            <TableHead>
              <Button
                variant="ghost"
                size="sm"
                className="-ml-3 h-8"
                onClick={() => handleSort('confidence')}
              >
                Status
                <SortIcon column="confidence" sortColumn={sortColumn} sortDirection={sortDirection} />
              </Button>
            </TableHead>
            <TableHead>
              <Button
                variant="ghost"
                size="sm"
                className="-ml-3 h-8"
                onClick={() => handleSort('sourceDocument')}
              >
                Source
                <SortIcon column="sourceDocument" sortColumn={sortColumn} sortDirection={sortDirection} />
              </Button>
            </TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedData.length > 0 ? (
            sortedData.map((item, index) => {
              const isProcessing = processingIds.includes(item.id);
              const isSelected = selectedIds.includes(item.id);
              // Code Review Fix: Compare by ID for reliable focus tracking
              const isFocused = item.id === focusedId;
              const colorClass = getConfidenceColorClass(item.confidence);

              return (
                <TableRow
                  key={item.id}
                  data-state={isSelected ? 'selected' : undefined}
                  className={`
                    ${isProcessing ? 'opacity-50 pointer-events-none' : ''}
                    ${isFocused ? 'ring-2 ring-primary ring-inset bg-primary/5' : ''}
                    ${!isProcessing ? 'cursor-pointer hover:bg-muted/50' : ''}
                  `.trim()}
                  onClick={() => {
                    setFocusedId(item.id);
                    onItemClick?.(item.id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && onItemClick) {
                      onItemClick(item.id);
                    }
                  }}
                  tabIndex={isFocused ? 0 : -1}
                >
                  <TableCell>
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => onToggleSelect(item.id)}
                      aria-label="Select row"
                      disabled={isProcessing}
                    />
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-2">
                      <span>{getFindingTypeIcon(item.findingType)}</span>
                      <span className="font-medium">
                        {formatFindingType(item.findingType)}
                      </span>
                    </span>
                  </TableCell>
                  <TableCell>
                    <span
                      className="max-w-[300px] truncate block"
                      title={item.findingSummary}
                    >
                      {item.findingSummary}
                    </span>
                  </TableCell>
                  <TableCell>
                    {(() => {
                      const status = getVerificationStatus(item.confidence);
                      const StatusIcon = status.level === 'verified' ? CheckCircle2 : status.level === 'likely_correct' ? AlertCircle : XCircle;
                      return (
                        <div
                          className="flex items-center gap-2"
                          title={formatConfidenceTooltip(item.confidence)}
                        >
                          <Badge variant="outline" className={status.badgeClass}>
                            <StatusIcon className="h-3 w-3 mr-1" />
                            {status.shortLabel}
                          </Badge>
                        </div>
                      );
                    })()}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground">
                      {item.sourceDocument ?? 'N/A'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-950"
                        onClick={() => onApprove(item.id)}
                        aria-label="Approve"
                        disabled={isProcessing}
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                        onClick={() => onReject(item.id)}
                        aria-label="Reject"
                        disabled={isProcessing}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50 dark:hover:bg-yellow-950"
                        onClick={() => onFlag(item.id)}
                        aria-label="Flag"
                        disabled={isProcessing}
                      >
                        <Flag className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })
          ) : (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center">
                No verifications pending.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
