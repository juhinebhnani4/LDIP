'use client';

/**
 * CitationsHeader Component
 *
 * Header for the citations tab with statistics, view mode toggle, and filters.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { useCallback, useMemo, useState } from 'react';
import {
  Scale,
  List,
  Layers,
  File,
  Filter,
  X,
  CheckCircle,
  AlertTriangle,
  Clock,
  HelpCircle,
  Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { CitationStats, VerificationStatus } from '@/types/citation';

export type CitationsViewMode = 'list' | 'byDocument' | 'byAct';

export interface CitationsFilterState {
  verificationStatus: VerificationStatus | null;
  actName: string | null;
  showOnlyIssues: boolean;
}

const verificationStatusOptions: Array<{
  value: VerificationStatus;
  label: string;
  icon: typeof CheckCircle;
}> = [
  { value: 'verified', label: 'Verified', icon: CheckCircle },
  { value: 'pending', label: 'Pending', icon: Clock },
  { value: 'mismatch', label: 'Mismatch', icon: AlertTriangle },
  { value: 'section_not_found', label: 'Not Found', icon: HelpCircle },
  { value: 'act_unavailable', label: 'No Act', icon: Clock },
];

export interface CitationsHeaderProps {
  stats: CitationStats | null;
  actNames: string[];
  viewMode: CitationsViewMode;
  onViewModeChange: (mode: CitationsViewMode) => void;
  filters: CitationsFilterState;
  onFiltersChange: (filters: CitationsFilterState) => void;
  isLoading?: boolean;
  className?: string;
}

export function CitationsHeader({
  stats,
  actNames,
  viewMode,
  onViewModeChange,
  filters,
  onFiltersChange,
  isLoading = false,
  className,
}: CitationsHeaderProps) {
  const [statusFilterOpen, setStatusFilterOpen] = useState(false);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.verificationStatus) count++;
    if (filters.actName) count++;
    if (filters.showOnlyIssues) count++;
    return count;
  }, [filters]);

  // Computed stats
  const issueCount = useMemo(() => {
    if (!stats) return 0;
    return stats.totalCitations - stats.verifiedCount - stats.pendingCount;
  }, [stats]);

  const handleStatusToggle = useCallback(
    (status: VerificationStatus) => {
      const newStatus = filters.verificationStatus === status ? null : status;
      onFiltersChange({ ...filters, verificationStatus: newStatus });
    },
    [filters, onFiltersChange]
  );

  const handleActChange = useCallback(
    (actName: string) => {
      onFiltersChange({
        ...filters,
        actName: actName === 'all' ? null : actName,
      });
    },
    [filters, onFiltersChange]
  );

  const handleShowOnlyIssuesChange = useCallback(
    (checked: boolean) => {
      onFiltersChange({ ...filters, showOnlyIssues: checked });
    },
    [filters, onFiltersChange]
  );

  const handleClearFilters = useCallback(() => {
    onFiltersChange({
      verificationStatus: null,
      actName: null,
      showOnlyIssues: false,
    });
  }, [onFiltersChange]);

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {/* Top row: Title, stats, view toggle */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Citations</h2>
          {stats && !isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{stats.totalCitations} found</span>
              <span className="text-muted-foreground/50">|</span>
              <span className="flex items-center gap-1">
                <CheckCircle className="h-3.5 w-3.5 text-green-600" />
                {stats.verifiedCount} verified
              </span>
              <span className="text-muted-foreground/50">|</span>
              <span className="flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
                {issueCount > 0 ? issueCount : 0} issues
              </span>
              <span className="text-muted-foreground/50">|</span>
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {stats.pendingCount} pending
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <ToggleGroup
            type="single"
            value={viewMode}
            onValueChange={(value) => value && onViewModeChange(value as CitationsViewMode)}
            aria-label="View mode"
          >
            <ToggleGroupItem value="list" aria-label="List view">
              <List className="h-4 w-4" />
            </ToggleGroupItem>
            <ToggleGroupItem value="byDocument" aria-label="By Document view">
              <File className="h-4 w-4" />
            </ToggleGroupItem>
            <ToggleGroupItem value="byAct" aria-label="By Act view">
              <Layers className="h-4 w-4" />
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      {/* Act Discovery summary */}
      {stats && stats.uniqueActs > 0 && (
        <div className="flex items-center gap-2 text-sm bg-muted/40 px-3 py-2 rounded-md">
          <Scale className="h-4 w-4 text-muted-foreground" />
          <span>
            <strong>{stats.uniqueActs}</strong> Acts referenced
          </span>
          <span className="text-muted-foreground/50">|</span>
          <span>
            <strong>{stats.uniqueActs - stats.missingActsCount}</strong> available
          </span>
          <span className="text-muted-foreground/50">|</span>
          {stats.missingActsCount > 0 ? (
            <span className="text-destructive font-medium">
              {stats.missingActsCount} missing
            </span>
          ) : (
            <span className="text-green-600">All available</span>
          )}
        </div>
      )}

      {/* Bottom row: Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Status filter dropdown */}
        <Popover open={statusFilterOpen} onOpenChange={setStatusFilterOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              aria-label="Filter by verification status"
            >
              <Filter className="h-4 w-4" />
              Status
              {filters.verificationStatus && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0">
                  1
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[200px] p-0" align="start">
            <Command>
              <CommandList>
                <CommandGroup>
                  {verificationStatusOptions.map((option) => {
                    const Icon = option.icon;
                    const isSelected = filters.verificationStatus === option.value;
                    return (
                      <CommandItem
                        key={option.value}
                        onSelect={() => handleStatusToggle(option.value)}
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

        {/* Act name filter */}
        <Select
          value={filters.actName ?? 'all'}
          onValueChange={handleActChange}
        >
          <SelectTrigger className="w-[200px] h-9 text-sm">
            <SelectValue placeholder="All Acts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Acts</SelectItem>
            {actNames.map((name) => (
              <SelectItem key={name} value={name}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Show only issues checkbox */}
        <div className="flex items-center space-x-2">
          <Checkbox
            id="show-only-issues"
            checked={filters.showOnlyIssues}
            onCheckedChange={handleShowOnlyIssuesChange}
          />
          <Label
            htmlFor="show-only-issues"
            className="text-sm text-muted-foreground cursor-pointer"
          >
            Show only issues
          </Label>
        </div>

        {/* Clear filters button */}
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

CitationsHeader.displayName = 'CitationsHeader';
