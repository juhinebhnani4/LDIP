'use client';

/**
 * EntitiesListView Component
 *
 * Table/list view for entities with sorting, selection, and actions.
 *
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { useCallback, useMemo, useState } from 'react';
import {
  User,
  Building2,
  Landmark,
  Package,
  ChevronUp,
  ChevronDown,
  CheckCircle2,
  Circle,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { EntityType, EntityListItem } from '@/types/entity';

const entityTypeConfig: Record<
  EntityType,
  { icon: typeof User; color: string; label: string }
> = {
  PERSON: {
    icon: User,
    color: 'text-blue-600 dark:text-blue-400',
    label: 'Person',
  },
  ORG: {
    icon: Building2,
    color: 'text-green-600 dark:text-green-400',
    label: 'Organization',
  },
  INSTITUTION: {
    icon: Landmark,
    color: 'text-purple-600 dark:text-purple-400',
    label: 'Institution',
  },
  ASSET: {
    icon: Package,
    color: 'text-amber-600 dark:text-amber-400',
    label: 'Asset',
  },
};

type SortField = 'canonicalName' | 'entityType' | 'mentionCount';
type SortDirection = 'asc' | 'desc';

export interface EntitiesListViewProps {
  entities: EntityListItem[];
  selectedEntityId: string | null;
  onEntitySelect: (entityId: string) => void;
  isMultiSelectMode?: boolean;
  selectedForMerge?: Set<string>;
  onToggleMergeSelection?: (entityId: string) => void;
  className?: string;
}

export function EntitiesListView({
  entities,
  selectedEntityId,
  onEntitySelect,
  isMultiSelectMode = false,
  selectedForMerge = new Set(),
  onToggleMergeSelection,
  className,
}: EntitiesListViewProps) {
  const [sortField, setSortField] = useState<SortField>('mentionCount');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const sortedEntities = useMemo(() => {
    return [...entities].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'canonicalName':
          comparison = a.canonicalName.localeCompare(b.canonicalName);
          break;
        case 'entityType':
          comparison = a.entityType.localeCompare(b.entityType);
          break;
        case 'mentionCount':
          comparison = a.mentionCount - b.mentionCount;
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [entities, sortField, sortDirection]);

  const handleSort = useCallback((field: SortField) => {
    setSortField((prev) => {
      if (prev === field) {
        setSortDirection((dir) => (dir === 'asc' ? 'desc' : 'asc'));
        return field;
      }
      setSortDirection('desc');
      return field;
    });
  }, []);

  const handleRowClick = useCallback(
    (entity: EntityListItem) => {
      if (isMultiSelectMode && onToggleMergeSelection) {
        onToggleMergeSelection(entity.id);
      } else {
        onEntitySelect(entity.id);
      }
    },
    [isMultiSelectMode, onEntitySelect, onToggleMergeSelection]
  );

  const getVerificationIcon = (entity: EntityListItem) => {
    if (entity.metadata?.verified === true) {
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    }
    if (entity.metadata?.flagged === true) {
      return <AlertTriangle className="h-4 w-4 text-amber-600" />;
    }
    return <Clock className="h-4 w-4 text-muted-foreground" />;
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? (
      <ChevronUp className="h-4 w-4 ml-1" />
    ) : (
      <ChevronDown className="h-4 w-4 ml-1" />
    );
  };

  if (entities.length === 0) {
    return (
      <div
        className={cn(
          'flex items-center justify-center h-[600px] bg-muted/30 border rounded-lg',
          className
        )}
      >
        <p className="text-muted-foreground">
          No entities found matching your filters.
        </p>
      </div>
    );
  }

  return (
    <div className={cn('border rounded-lg bg-background', className)}>
      <ScrollArea className="h-[600px]">
        <Table>
          <TableHeader className="sticky top-0 bg-background z-10">
            <TableRow>
              {isMultiSelectMode && (
                <TableHead className="w-[50px]">Select</TableHead>
              )}
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 h-8 data-[state=open]:bg-accent"
                  onClick={() => handleSort('canonicalName')}
                >
                  Name
                  <SortIcon field="canonicalName" />
                </Button>
              </TableHead>
              <TableHead className="w-[140px]">
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 h-8 data-[state=open]:bg-accent"
                  onClick={() => handleSort('entityType')}
                >
                  Type
                  <SortIcon field="entityType" />
                </Button>
              </TableHead>
              <TableHead className="w-[100px]">
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 h-8 data-[state=open]:bg-accent"
                  onClick={() => handleSort('mentionCount')}
                >
                  Mentions
                  <SortIcon field="mentionCount" />
                </Button>
              </TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[150px]">Roles</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedEntities.map((entity) => {
              const config = entityTypeConfig[entity.entityType];
              const Icon = config.icon;
              const isSelected = selectedEntityId === entity.id;
              const isSelectedForMerge = selectedForMerge.has(entity.id);
              const roles = entity.metadata?.roles ?? [];

              return (
                <TableRow
                  key={entity.id}
                  className={cn(
                    'cursor-pointer',
                    isSelected && 'bg-muted/50',
                    isSelectedForMerge && 'bg-primary/10 border-l-2 border-l-primary'
                  )}
                  onClick={() => handleRowClick(entity)}
                  data-testid={`entity-row-${entity.id}`}
                >
                  {isMultiSelectMode && (
                    <TableCell>
                      <Checkbox
                        checked={isSelectedForMerge}
                        onCheckedChange={() => onToggleMergeSelection?.(entity.id)}
                        onClick={(e) => e.stopPropagation()}
                        disabled={selectedForMerge.size >= 2 && !isSelectedForMerge}
                        aria-label={`Select ${entity.canonicalName} for merge`}
                      />
                    </TableCell>
                  )}
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Icon className={cn('h-4 w-4', config.color)} />
                      {entity.canonicalName}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs">
                      {config.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    {entity.mentionCount}
                  </TableCell>
                  <TableCell>
                    {getVerificationIcon(entity)}
                  </TableCell>
                  <TableCell>
                    {roles.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {roles.slice(0, 2).map((role, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {role}
                          </Badge>
                        ))}
                        {roles.length > 2 && (
                          <span className="text-xs text-muted-foreground">
                            +{roles.length - 2}
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-xs">-</span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  );
}

EntitiesListView.displayName = 'EntitiesListView';
