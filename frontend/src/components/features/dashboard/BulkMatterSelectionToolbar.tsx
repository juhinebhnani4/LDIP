'use client';

import { Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';

interface BulkMatterSelectionToolbarProps {
  /** Total number of selectable matters */
  totalCount: number;
  /** Number of currently selected matters */
  selectedCount: number;
  /** Whether all matters are selected */
  allSelected: boolean;
  /** Whether some (but not all) matters are selected */
  someSelected: boolean;
  /** Callback to select/deselect all */
  onSelectAllChange: (checked: boolean) => void;
  /** Callback to delete selected matters */
  onDeleteClick: () => void;
  /** Callback to clear selection */
  onClearSelection: () => void;
}

/**
 * Toolbar for bulk matter operations.
 * Shows select all checkbox, selection count, and action buttons.
 */
export function BulkMatterSelectionToolbar({
  totalCount,
  selectedCount,
  allSelected,
  someSelected,
  onSelectAllChange,
  onDeleteClick,
  onClearSelection,
}: BulkMatterSelectionToolbarProps) {
  const handleSelectAllChange = (checked: boolean | 'indeterminate') => {
    if (checked !== 'indeterminate') {
      onSelectAllChange(checked);
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/50 px-4 py-3 mb-4">
      <div className="flex items-center gap-4">
        {/* Select All checkbox */}
        <div className="flex items-center gap-2">
          <Checkbox
            id="select-all-matters"
            checked={allSelected}
            onCheckedChange={handleSelectAllChange}
            aria-label="Select all matters"
            className="h-5 w-5 border-2"
            data-state={someSelected && !allSelected ? 'indeterminate' : undefined}
          />
          <label
            htmlFor="select-all-matters"
            className="text-sm font-medium cursor-pointer"
          >
            Select All
          </label>
        </div>

        {/* Selection count */}
        <div className="text-sm text-muted-foreground">
          {selectedCount} of {totalCount} selected
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        {selectedCount > 0 && (
          <>
            <Button
              variant="destructive"
              size="sm"
              onClick={onDeleteClick}
              className="gap-2"
            >
              <Trash2 className="h-4 w-4" />
              Delete Selected ({selectedCount})
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSelection}
              className="gap-1"
            >
              <X className="h-4 w-4" />
              Clear
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
