'use client';

/**
 * ContradictionsFilters Component
 *
 * Filter controls for the contradictions tab, including severity,
 * type, and entity filters with URL state sync.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 6: Create ContradictionsFilters component
 */

import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type {
  ContradictionSeverity,
  ContradictionType,
} from '@/hooks/useContradictions';

interface ContradictionsFiltersProps {
  /** Current severity filter */
  severity: ContradictionSeverity | undefined;
  /** Current type filter */
  contradictionType: ContradictionType | undefined;
  /** Current entity filter */
  entityId: string | undefined;
  /** Available entities for the entity dropdown */
  entities: { id: string; name: string }[];
  /** Whether any filters are active */
  hasActiveFilters: boolean;
  /** Callback when severity changes */
  onSeverityChange: (severity: ContradictionSeverity | undefined) => void;
  /** Callback when type changes */
  onTypeChange: (type: ContradictionType | undefined) => void;
  /** Callback when entity changes */
  onEntityChange: (entityId: string | undefined) => void;
  /** Callback to reset all filters */
  onReset: () => void;
}

const SEVERITY_OPTIONS: { value: ContradictionSeverity; label: string }[] = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const TYPE_OPTIONS: { value: ContradictionType; label: string }[] = [
  { value: 'semantic_contradiction', label: 'Semantic' },
  { value: 'factual_contradiction', label: 'Factual' },
  { value: 'date_mismatch', label: 'Date Mismatch' },
  { value: 'amount_mismatch', label: 'Amount Mismatch' },
];

/**
 * ContradictionsFilters provides filter controls for the contradictions list.
 *
 * @example
 * ```tsx
 * <ContradictionsFilters
 *   severity={filters.severity}
 *   contradictionType={filters.contradictionType}
 *   entityId={filters.entityId}
 *   entities={uniqueEntities}
 *   hasActiveFilters={hasActiveFilters}
 *   onSeverityChange={(s) => setFilters({ severity: s })}
 *   onTypeChange={(t) => setFilters({ contradictionType: t })}
 *   onEntityChange={(e) => setFilters({ entityId: e })}
 *   onReset={resetFilters}
 * />
 * ```
 */
export function ContradictionsFilters({
  severity,
  contradictionType,
  entityId,
  entities,
  hasActiveFilters,
  onSeverityChange,
  onTypeChange,
  onEntityChange,
  onReset,
}: ContradictionsFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Severity filter */}
      <Select
        value={severity ?? 'all'}
        onValueChange={(value) =>
          onSeverityChange(value === 'all' ? undefined : (value as ContradictionSeverity))
        }
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="Severity" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Severities</SelectItem>
          {SEVERITY_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Type filter */}
      <Select
        value={contradictionType ?? 'all'}
        onValueChange={(value) =>
          onTypeChange(value === 'all' ? undefined : (value as ContradictionType))
        }
      >
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          {TYPE_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Entity filter */}
      {entities.length > 0 && (
        <Select
          value={entityId ?? 'all'}
          onValueChange={(value) =>
            onEntityChange(value === 'all' ? undefined : value)
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Entity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Entities</SelectItem>
            {entities.map((entity) => (
              <SelectItem key={entity.id} value={entity.id}>
                {entity.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Reset button */}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onReset}
          className="h-9 px-2 text-muted-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear filters
        </Button>
      )}
    </div>
  );
}
