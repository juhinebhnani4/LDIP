/**
 * TimelineFilterBar Component
 *
 * Filter controls for timeline events.
 * Allows filtering by: Event Type, Actors, Date Range, Verification Status.
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

'use client';

import { useCallback, useMemo, useState } from 'react';
import {
  Filter,
  X,
  Check,
  ChevronDown,
  ChevronUp,
  Calendar as CalendarIcon,
  Shield,
  ShieldCheck,
  ShieldOff,
  AlertTriangle,
  SlidersHorizontal,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
// Checkbox component available for future filter enhancements
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { TimelineFilterState, TimelineEventType } from '@/types/timeline';
import { DEFAULT_TIMELINE_FILTERS, countActiveFilters } from '@/types/timeline';
import { EVENT_TYPE_LABELS, EVENT_TYPE_ICONS } from './eventTypeIcons';

/**
 * Filterable event types (exclude internal types like raw_date)
 */
const FILTERABLE_EVENT_TYPES: TimelineEventType[] = [
  'filing',
  'notice',
  'hearing',
  'order',
  'transaction',
  'document',
  'deadline',
];

/**
 * Entity option for actor filter
 */
interface EntityOption {
  id: string;
  name: string;
}

/**
 * TimelineFilterBar props
 */
interface TimelineFilterBarProps {
  /** Current filter state */
  filters: TimelineFilterState;
  /** Callback when filters change */
  onFiltersChange: (filters: TimelineFilterState) => void;
  /** Available entities for actor filter */
  entities: EntityOption[];
  /** Count of unreviewed anomalies (to show badge) */
  anomalyCount?: number;
  /** Whether the filter bar starts collapsed (default: true for UX density) */
  defaultCollapsed?: boolean;
  /** Controlled collapsed state (optional) */
  collapsed?: boolean;
  /** Callback when collapsed state changes */
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Multi-select popover for event types
 */
function EventTypeFilter({
  selected,
  onChange,
}: {
  selected: TimelineEventType[];
  onChange: (types: TimelineEventType[]) => void;
}) {
  const [open, setOpen] = useState(false);

  const toggleType = useCallback(
    (type: TimelineEventType) => {
      if (selected.includes(type)) {
        onChange(selected.filter((t) => t !== type));
      } else {
        onChange([...selected, type]);
      }
    },
    [selected, onChange]
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 border-dashed"
          aria-label="Filter by event type"
        >
          <Filter className="mr-2 h-4 w-4" />
          Event Type
          {selected.length > 0 && (
            <Badge
              variant="secondary"
              className="ml-2 rounded-sm px-1 font-normal"
            >
              {selected.length}
            </Badge>
          )}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <div className="p-2">
          <p className="text-sm font-medium text-muted-foreground px-2 py-1.5">
            Filter by event type
          </p>
          <Separator className="my-2" />
          <div className="space-y-1">
            {FILTERABLE_EVENT_TYPES.map((type) => {
              const Icon = EVENT_TYPE_ICONS[type];
              const isSelected = selected.includes(type);
              return (
                <button
                  key={type}
                  onClick={() => toggleType(type)}
                  className={cn(
                    'flex w-full items-center rounded-sm px-2 py-1.5 text-sm',
                    'hover:bg-accent hover:text-accent-foreground',
                    'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'
                  )}
                  role="menuitemcheckbox"
                  aria-checked={isSelected}
                >
                  <div
                    className={cn(
                      'mr-2 flex h-4 w-4 items-center justify-center rounded-sm border',
                      isSelected
                        ? 'bg-primary border-primary text-primary-foreground'
                        : 'border-input'
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </div>
                  <Icon className="mr-2 h-4 w-4 text-muted-foreground" />
                  <span>{EVENT_TYPE_LABELS[type]}</span>
                </button>
              );
            })}
          </div>
          {selected.length > 0 && (
            <>
              <Separator className="my-2" />
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center"
                onClick={() => onChange([])}
              >
                Clear selection
              </Button>
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Multi-select popover for actors (entities)
 */
function ActorFilter({
  selected,
  onChange,
  entities,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
  entities: EntityOption[];
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const filteredEntities = useMemo(() => {
    if (!search) return entities;
    const lowerSearch = search.toLowerCase();
    return entities.filter((e) => e.name.toLowerCase().includes(lowerSearch));
  }, [entities, search]);

  const toggleEntity = useCallback(
    (id: string) => {
      if (selected.includes(id)) {
        onChange(selected.filter((i) => i !== id));
      } else {
        onChange([...selected, id]);
      }
    },
    [selected, onChange]
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 border-dashed"
          aria-label="Filter by actors"
        >
          Actors
          {selected.length > 0 && (
            <Badge
              variant="secondary"
              className="ml-2 rounded-sm px-1 font-normal"
            >
              {selected.length}
            </Badge>
          )}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <div className="p-2">
          <p className="text-sm font-medium text-muted-foreground px-2 py-1.5">
            Filter by actors
          </p>
          <div className="px-2 py-1.5">
            <Input
              placeholder="Search actors..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8"
              aria-label="Search actors"
            />
          </div>
          <Separator className="my-2" />
          <div className="max-h-48 overflow-y-auto space-y-1">
            {filteredEntities.length === 0 ? (
              <p className="px-2 py-4 text-sm text-muted-foreground text-center">
                No actors found
              </p>
            ) : (
              filteredEntities.map((entity) => {
                const isSelected = selected.includes(entity.id);
                return (
                  <button
                    key={entity.id}
                    onClick={() => toggleEntity(entity.id)}
                    className={cn(
                      'flex w-full items-center rounded-sm px-2 py-1.5 text-sm',
                      'hover:bg-accent hover:text-accent-foreground',
                      'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'
                    )}
                    role="menuitemcheckbox"
                    aria-checked={isSelected}
                  >
                    <div
                      className={cn(
                        'mr-2 flex h-4 w-4 items-center justify-center rounded-sm border',
                        isSelected
                          ? 'bg-primary border-primary text-primary-foreground'
                          : 'border-input'
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <span className="truncate">{entity.name}</span>
                  </button>
                );
              })
            )}
          </div>
          {selected.length > 0 && (
            <>
              <Separator className="my-2" />
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center"
                onClick={() => onChange([])}
              >
                Clear selection
              </Button>
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Date range filter
 */
function DateRangeFilter({
  startDate,
  endDate,
  onChange,
}: {
  startDate: string | null;
  endDate: string | null;
  onChange: (start: string | null, end: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const hasDateFilter = startDate !== null || endDate !== null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 border-dashed"
          aria-label="Filter by date range"
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          Date Range
          {hasDateFilter && (
            <Badge
              variant="secondary"
              className="ml-2 rounded-sm px-1 font-normal"
            >
              1
            </Badge>
          )}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-4" align="start">
        <div className="space-y-4">
          <p className="text-sm font-medium text-muted-foreground">
            Filter by date range
          </p>
          <div className="grid gap-3">
            <div className="space-y-2">
              <Label htmlFor="start-date">From</Label>
              <Input
                id="start-date"
                type="date"
                value={startDate ?? ''}
                onChange={(e) =>
                  onChange(e.target.value || null, endDate)
                }
                className="h-9"
                aria-label="Start date"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end-date">To</Label>
              <Input
                id="end-date"
                type="date"
                value={endDate ?? ''}
                onChange={(e) =>
                  onChange(startDate, e.target.value || null)
                }
                className="h-9"
                aria-label="End date"
              />
            </div>
          </div>
          {hasDateFilter && (
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => onChange(null, null)}
            >
              Clear dates
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Verification status filter
 */
function VerificationStatusFilter({
  status,
  onChange,
}: {
  status: 'all' | 'verified' | 'unverified';
  onChange: (status: 'all' | 'verified' | 'unverified') => void;
}) {
  const [open, setOpen] = useState(false);

  const options: { value: 'all' | 'verified' | 'unverified'; label: string; icon: typeof Shield }[] = [
    { value: 'all', label: 'All Events', icon: Shield },
    { value: 'verified', label: 'Verified Only', icon: ShieldCheck },
    { value: 'unverified', label: 'Unverified Only', icon: ShieldOff },
  ];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 border-dashed"
          aria-label="Filter by verification status"
        >
          {status === 'verified' ? (
            <ShieldCheck className="mr-2 h-4 w-4 text-green-600" />
          ) : status === 'unverified' ? (
            <ShieldOff className="mr-2 h-4 w-4 text-amber-600" />
          ) : (
            <Shield className="mr-2 h-4 w-4" />
          )}
          {status === 'all' ? 'Verification' : status === 'verified' ? 'Verified' : 'Unverified'}
          {status !== 'all' && (
            <Badge
              variant="secondary"
              className="ml-2 rounded-sm px-1 font-normal"
            >
              1
            </Badge>
          )}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-0" align="start">
        <div className="p-2">
          <p className="text-sm font-medium text-muted-foreground px-2 py-1.5">
            Verification status
          </p>
          <Separator className="my-2" />
          <div className="space-y-1">
            {options.map((option) => {
              const Icon = option.icon;
              const isSelected = status === option.value;
              return (
                <button
                  key={option.value}
                  onClick={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                  className={cn(
                    'flex w-full items-center rounded-sm px-2 py-1.5 text-sm',
                    'hover:bg-accent hover:text-accent-foreground',
                    isSelected && 'bg-accent',
                    'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'
                  )}
                  role="menuitemradio"
                  aria-checked={isSelected}
                >
                  <Icon className={cn(
                    'mr-2 h-4 w-4',
                    option.value === 'verified' && 'text-green-600',
                    option.value === 'unverified' && 'text-amber-600'
                  )} />
                  <span>{option.label}</span>
                  {isSelected && <Check className="ml-auto h-4 w-4" />}
                </button>
              );
            })}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * TimelineFilterBar component
 *
 * UX Optimization: Collapsed by default to reduce visual clutter.
 * Shows a compact "Filters" button that expands on click.
 */
export function TimelineFilterBar({
  filters,
  onFiltersChange,
  entities,
  anomalyCount = 0,
  defaultCollapsed = true,
  collapsed: controlledCollapsed,
  onCollapsedChange,
  className,
}: TimelineFilterBarProps) {
  // Support both controlled and uncontrolled collapse state
  const [uncontrolledCollapsed, setUncontrolledCollapsed] = useState(defaultCollapsed);
  const isCollapsed = controlledCollapsed ?? uncontrolledCollapsed;
  const setIsCollapsed = onCollapsedChange ?? setUncontrolledCollapsed;

  const activeFilterCount = useMemo(
    () => countActiveFilters(filters),
    [filters]
  );

  const handleClearFilters = useCallback(() => {
    onFiltersChange(DEFAULT_TIMELINE_FILTERS);
  }, [onFiltersChange]);

  const toggleCollapsed = useCallback(() => {
    setIsCollapsed(!isCollapsed);
  }, [isCollapsed, setIsCollapsed]);

  const handleEventTypesChange = useCallback(
    (eventTypes: TimelineEventType[]) => {
      onFiltersChange({ ...filters, eventTypes });
    },
    [filters, onFiltersChange]
  );

  const handleEntityIdsChange = useCallback(
    (entityIds: string[]) => {
      onFiltersChange({ ...filters, entityIds });
    },
    [filters, onFiltersChange]
  );

  const handleDateRangeChange = useCallback(
    (start: string | null, end: string | null) => {
      onFiltersChange({
        ...filters,
        dateRange: { start, end },
      });
    },
    [filters, onFiltersChange]
  );

  const handleVerificationStatusChange = useCallback(
    (verificationStatus: 'all' | 'verified' | 'unverified') => {
      onFiltersChange({ ...filters, verificationStatus });
    },
    [filters, onFiltersChange]
  );

  const handleAnomaliesToggle = useCallback(() => {
    onFiltersChange({ ...filters, showAnomaliesOnly: !filters.showAnomaliesOnly });
  }, [filters, onFiltersChange]);

  // Collapsed view: just a "Filters" button with active count
  if (isCollapsed) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 py-2 border-b bg-background',
          className
        )}
        role="toolbar"
        aria-label="Timeline filters (collapsed)"
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleCollapsed}
          className="h-8 gap-2 text-muted-foreground hover:text-foreground"
          aria-expanded={false}
          aria-label={`Show filters${activeFilterCount > 0 ? ` (${activeFilterCount} active)` : ''}`}
        >
          <SlidersHorizontal className="h-4 w-4" />
          <span>Filters</span>
          {activeFilterCount > 0 && (
            <Badge variant="secondary" className="ml-1 rounded-sm px-1.5 font-normal">
              {activeFilterCount}
            </Badge>
          )}
          <ChevronDown className="h-4 w-4 ml-1" />
        </Button>

        {/* Quick clear when collapsed with active filters */}
        {activeFilterCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearFilters}
            className="h-8 text-muted-foreground hover:text-foreground"
            aria-label="Clear all filters"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    );
  }

  // Expanded view: full filter controls
  return (
    <div
      className={cn(
        'flex flex-col gap-2 py-3 border-b bg-background',
        className
      )}
      role="toolbar"
      aria-label="Timeline filters"
    >
      {/* Collapse toggle row */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleCollapsed}
          className="h-7 gap-1.5 text-muted-foreground hover:text-foreground px-2"
          aria-expanded={true}
          aria-label="Hide filters"
        >
          <SlidersHorizontal className="h-4 w-4" />
          <span className="text-xs font-medium">Filters</span>
          <ChevronUp className="h-4 w-4" />
        </Button>

        {/* Clear Filters Button */}
        {activeFilterCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearFilters}
            className="h-7 text-muted-foreground hover:text-foreground text-xs"
            aria-label={`Clear all filters (${activeFilterCount} active)`}
          >
            <X className="mr-1 h-3 w-3" />
            Clear ({activeFilterCount})
          </Button>
        )}
      </div>

      {/* Filter controls row */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Event Type Filter */}
        <EventTypeFilter
          selected={filters.eventTypes}
          onChange={handleEventTypesChange}
        />

        {/* Actor Filter */}
        <ActorFilter
          selected={filters.entityIds}
          onChange={handleEntityIdsChange}
          entities={entities}
        />

        {/* Date Range Filter */}
        <DateRangeFilter
          startDate={filters.dateRange.start}
          endDate={filters.dateRange.end}
          onChange={handleDateRangeChange}
        />

        {/* Verification Status Filter */}
        <VerificationStatusFilter
          status={filters.verificationStatus}
          onChange={handleVerificationStatusChange}
        />

        {/* Anomalies Filter (Story 14.16) */}
        {anomalyCount > 0 && (
          <Button
            variant={filters.showAnomaliesOnly ? 'secondary' : 'outline'}
            size="sm"
            className={cn(
              'h-8 border-dashed gap-1',
              filters.showAnomaliesOnly && 'border-orange-300 bg-orange-50 text-orange-800 hover:bg-orange-100 dark:border-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
            )}
            onClick={handleAnomaliesToggle}
            aria-pressed={filters.showAnomaliesOnly}
            aria-label="Filter to show only events with anomalies"
          >
            <AlertTriangle className={cn('h-4 w-4', filters.showAnomaliesOnly && 'text-orange-600')} />
            Anomalies
            <Badge
              variant="secondary"
              className={cn(
                'ml-1 rounded-sm px-1 font-normal',
                filters.showAnomaliesOnly
                  ? 'bg-orange-200 text-orange-800 dark:bg-orange-800 dark:text-orange-200'
                  : 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300'
              )}
            >
              {anomalyCount}
            </Badge>
          </Button>
        )}
      </div>
    </div>
  );
}

export default TimelineFilterBar;
