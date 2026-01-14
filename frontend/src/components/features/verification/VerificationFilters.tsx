'use client';

/**
 * Verification Filter Controls Component
 *
 * Filter dropdowns for the verification queue.
 *
 * Story 8-5: Implement Verification Queue UI (Task 5)
 * Implements AC #5: Filter controls
 */

import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { X } from 'lucide-react';
import type { VerificationFilters as FiltersType, ConfidenceTier, VerificationView } from '@/types';
import { formatFindingType } from '@/stores/verificationStore';

interface VerificationFiltersProps {
  /** Current filter state */
  filters: FiltersType;
  /** Callback when filters change */
  onFiltersChange: (filters: Partial<FiltersType>) => void;
  /** Callback to reset all filters */
  onReset: () => void;
  /** Available finding types for dropdown */
  findingTypes: string[];
  /** Whether any filters are active */
  hasActiveFilters?: boolean;
}

/**
 * Filter controls for verification queue.
 *
 * Provides dropdowns for:
 * - Finding type filter
 * - Confidence tier filter (High >90%, Medium 70-90%, Low <70%)
 * - View mode selector (Queue, By Type, History)
 *
 * @example
 * ```tsx
 * <VerificationFilters
 *   filters={filters}
 *   onFiltersChange={setFilters}
 *   onReset={resetFilters}
 *   findingTypes={['citation_mismatch', 'timeline_anomaly']}
 * />
 * ```
 */
export function VerificationFilters({
  filters,
  onFiltersChange,
  onReset,
  findingTypes,
  hasActiveFilters = false,
}: VerificationFiltersProps) {
  // Check if any filter is active
  const anyActive =
    hasActiveFilters ||
    filters.findingType !== null ||
    filters.confidenceTier !== null;

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Finding Type Filter */}
      <Select
        value={filters.findingType ?? 'all'}
        onValueChange={(value) =>
          onFiltersChange({ findingType: value === 'all' ? null : value })
        }
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Finding Type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          {findingTypes.map((type) => (
            <SelectItem key={type} value={type}>
              {formatFindingType(type)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Confidence Tier Filter */}
      <Select
        value={filters.confidenceTier ?? 'all'}
        onValueChange={(value) =>
          onFiltersChange({
            confidenceTier: value === 'all' ? null : (value as ConfidenceTier),
          })
        }
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Confidence" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Confidence</SelectItem>
          <SelectItem value="low">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              Low (&lt;70%)
            </span>
          </SelectItem>
          <SelectItem value="medium">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-yellow-500" />
              Medium (70-90%)
            </span>
          </SelectItem>
          <SelectItem value="high">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              High (&gt;90%)
            </span>
          </SelectItem>
        </SelectContent>
      </Select>

      {/* View Mode Selector */}
      <Select
        value={filters.view}
        onValueChange={(value) =>
          onFiltersChange({ view: value as VerificationView })
        }
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="View" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="queue">Queue View</SelectItem>
          <SelectItem value="by-type">By Type</SelectItem>
          <SelectItem value="history">History</SelectItem>
        </SelectContent>
      </Select>

      {/* Clear Filters Button */}
      {anyActive && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onReset}
          className="text-muted-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear Filters
        </Button>
      )}
    </div>
  );
}
