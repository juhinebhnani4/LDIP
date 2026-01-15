'use client';

/**
 * EntitiesHeader Component
 *
 * Header for the entities tab with statistics, view mode toggle, filters,
 * and multi-selection merge functionality.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import {
  Network,
  List,
  LayoutGrid,
  Search,
  Filter,
  X,
  User,
  Building2,
  Landmark,
  Package,
  Check,
  GitMerge,
  MousePointerClick,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  ToggleGroup,
  ToggleGroupItem,
} from '@/components/ui/toggle-group';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import type { EntityType, EntityViewMode, EntityFilterState } from '@/types/entity';

const entityTypeOptions: Array<{
  value: EntityType;
  label: string;
  icon: typeof User;
}> = [
  { value: 'PERSON', label: 'Person', icon: User },
  { value: 'ORG', label: 'Organization', icon: Building2 },
  { value: 'INSTITUTION', label: 'Institution', icon: Landmark },
  { value: 'ASSET', label: 'Asset', icon: Package },
];

export interface EntitiesHeaderProps {
  stats: {
    total: number;
    byType: Record<EntityType, number>;
    filteredTotal?: number;
  };
  viewMode: EntityViewMode;
  onViewModeChange: (mode: EntityViewMode) => void;
  filters: EntityFilterState;
  onFiltersChange: (filters: EntityFilterState) => void;
  isMultiSelectMode?: boolean;
  onMultiSelectModeChange?: (enabled: boolean) => void;
  selectedForMergeCount?: number;
  onMergeClick?: () => void;
  className?: string;
}

export function EntitiesHeader({
  stats,
  viewMode,
  onViewModeChange,
  filters,
  onFiltersChange,
  isMultiSelectMode = false,
  onMultiSelectModeChange,
  selectedForMergeCount = 0,
  onMergeClick,
  className,
}: EntitiesHeaderProps) {
  const [searchValue, setSearchValue] = useState(filters.searchQuery);
  const [typeFilterOpen, setTypeFilterOpen] = useState(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.entityTypes.length > 0) count++;
    if (filters.searchQuery) count++;
    if (filters.minMentionCount > 0) count++;
    if (filters.verificationStatus !== 'all') count++;
    if (filters.roles.length > 0) count++;
    return count;
  }, [filters]);

  // Debounced search - updates filter after 300ms of no typing
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchValue(value);

      // Clear existing timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // Set new debounced update
      debounceTimerRef.current = setTimeout(() => {
        onFiltersChange({ ...filters, searchQuery: value });
      }, 300);
    },
    [filters, onFiltersChange]
  );

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const handleTypeToggle = useCallback(
    (type: EntityType) => {
      const newTypes = filters.entityTypes.includes(type)
        ? filters.entityTypes.filter((t) => t !== type)
        : [...filters.entityTypes, type];
      onFiltersChange({ ...filters, entityTypes: newTypes });
    },
    [filters, onFiltersChange]
  );

  const handleClearFilters = useCallback(() => {
    setSearchValue('');
    onFiltersChange({
      entityTypes: [],
      roles: [],
      verificationStatus: 'all',
      minMentionCount: 0,
      searchQuery: '',
    });
  }, [onFiltersChange]);

  const handleMultiSelectToggle = useCallback(() => {
    if (onMultiSelectModeChange) {
      onMultiSelectModeChange(!isMultiSelectMode);
    }
  }, [isMultiSelectMode, onMultiSelectModeChange]);

  const canMerge = selectedForMergeCount === 2;

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Entities</h2>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>
              {stats.filteredTotal !== undefined && stats.filteredTotal !== stats.total
                ? `${stats.filteredTotal} of ${stats.total}`
                : `${stats.total} total`}
            </span>
            <span className="text-muted-foreground/50">|</span>
            <span className="flex items-center gap-1">
              <User className="h-3.5 w-3.5" />
              {stats.byType.PERSON}
            </span>
            <span className="flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" />
              {stats.byType.ORG}
            </span>
            <span className="flex items-center gap-1">
              <Landmark className="h-3.5 w-3.5" />
              {stats.byType.INSTITUTION}
            </span>
            <span className="flex items-center gap-1">
              <Package className="h-3.5 w-3.5" />
              {stats.byType.ASSET}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Multi-select merge controls */}
          {onMultiSelectModeChange && (
            <>
              <Button
                variant={isMultiSelectMode ? 'default' : 'outline'}
                size="sm"
                onClick={handleMultiSelectToggle}
                className="gap-2"
                aria-label={isMultiSelectMode ? 'Exit merge selection mode' : 'Select entities for merge'}
              >
                <MousePointerClick className="h-4 w-4" />
                {isMultiSelectMode ? 'Cancel Selection' : 'Select for Merge'}
              </Button>

              {isMultiSelectMode && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={onMergeClick}
                  disabled={!canMerge}
                  className="gap-2"
                  aria-label="Merge selected entities"
                >
                  <GitMerge className="h-4 w-4" />
                  Merge
                  {selectedForMergeCount > 0 && (
                    <Badge variant="secondary" className="ml-1 px-1.5 py-0 bg-primary-foreground/20">
                      {selectedForMergeCount}/2
                    </Badge>
                  )}
                </Button>
              )}
            </>
          )}

          <ToggleGroup
            type="single"
            value={viewMode}
            onValueChange={(value) => value && onViewModeChange(value as EntityViewMode)}
            aria-label="View mode"
          >
            <ToggleGroupItem value="graph" aria-label="Graph view">
              <Network className="h-4 w-4" />
            </ToggleGroupItem>
            <ToggleGroupItem value="list" aria-label="List view">
              <List className="h-4 w-4" />
            </ToggleGroupItem>
            <ToggleGroupItem value="grid" aria-label="Grid view">
              <LayoutGrid className="h-4 w-4" />
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search entities..."
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9"
            aria-label="Search entities"
          />
        </div>

        <Popover open={typeFilterOpen} onOpenChange={setTypeFilterOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              aria-label="Filter by entity type"
            >
              <Filter className="h-4 w-4" />
              Entity Type
              {filters.entityTypes.length > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0">
                  {filters.entityTypes.length}
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[200px] p-0" align="start">
            <Command>
              <CommandList>
                <CommandGroup>
                  {entityTypeOptions.map((option) => {
                    const Icon = option.icon;
                    const isSelected = filters.entityTypes.includes(option.value);
                    return (
                      <CommandItem
                        key={option.value}
                        onSelect={() => handleTypeToggle(option.value)}
                        className="flex items-center gap-2"
                      >
                        <div
                          className={cn(
                            'flex h-4 w-4 items-center justify-center rounded border',
                            isSelected
                              ? 'bg-primary border-primary text-primary-foreground'
                              : 'border-muted'
                          )}
                        >
                          {isSelected && <Check className="h-3 w-3" />}
                        </div>
                        <Icon className="h-4 w-4" />
                        <span>{option.label}</span>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>

        {activeFilterCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearFilters}
            className="gap-1"
          >
            <X className="h-4 w-4" />
            Clear Filters
          </Button>
        )}
      </div>
    </div>
  );
}

EntitiesHeader.displayName = 'EntitiesHeader';
