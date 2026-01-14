'use client';

import { ArrowDownAZ, Filter } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useMatterStore } from '@/stores/matterStore';
import { SORT_OPTIONS, FILTER_OPTIONS } from '@/types/matter';
import type { MatterSortOption, MatterFilterOption } from '@/types/matter';

/**
 * Matter Filters Component
 *
 * Provides sort and filter controls for the matter cards grid.
 *
 * Sort options:
 * - Recent (default) - by updatedAt desc
 * - Alphabetical - by title asc
 * - Most pages - by pageCount desc
 * - Least verified - by verificationPercent asc
 * - Date created - by createdAt desc
 *
 * Filter options:
 * - All (default)
 * - Processing
 * - Ready
 * - Needs attention
 * - Archived
 */

interface MatterFiltersProps {
  /** Optional className for styling */
  className?: string;
}

export function MatterFilters({ className }: MatterFiltersProps) {
  const sortBy = useMatterStore((state) => state.sortBy);
  const filterBy = useMatterStore((state) => state.filterBy);
  const setSortBy = useMatterStore((state) => state.setSortBy);
  const setFilterBy = useMatterStore((state) => state.setFilterBy);

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-3">
        {/* Sort dropdown */}
        <div className="flex items-center gap-2">
          <ArrowDownAZ className="size-4 text-muted-foreground" aria-hidden="true" />
          <Select
            value={sortBy}
            onValueChange={(value) => setSortBy(value as MatterSortOption)}
          >
            <SelectTrigger className="w-[160px]" aria-label="Sort matters by">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Filter dropdown */}
        <div className="flex items-center gap-2">
          <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
          <Select
            value={filterBy}
            onValueChange={(value) => setFilterBy(value as MatterFilterOption)}
          >
            <SelectTrigger className="w-[160px]" aria-label="Filter matters by status">
              <SelectValue placeholder="Filter" />
            </SelectTrigger>
            <SelectContent>
              {FILTER_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
