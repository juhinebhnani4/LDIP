'use client';

/**
 * EntitiesGridView Component
 *
 * Card-based grid view for entities with selection and actions.
 *
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { useCallback } from 'react';
import { CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { entityTypeConfig, ENTITY_VIEW_HEIGHT } from '@/lib/utils/entityConstants';
import type { EntityListItem } from '@/types/entity';

export interface EntitiesGridViewProps {
  entities: EntityListItem[];
  selectedEntityId: string | null;
  onEntitySelect: (entityId: string) => void;
  isMultiSelectMode?: boolean;
  selectedForMerge?: Set<string>;
  onToggleMergeSelection?: (entityId: string) => void;
  className?: string;
}

export function EntitiesGridView({
  entities,
  selectedEntityId,
  onEntitySelect,
  isMultiSelectMode = false,
  selectedForMerge = new Set(),
  onToggleMergeSelection,
  className,
}: EntitiesGridViewProps) {
  const handleCardClick = useCallback(
    (entity: EntityListItem) => {
      if (isMultiSelectMode && onToggleMergeSelection) {
        onToggleMergeSelection(entity.id);
      } else {
        onEntitySelect(entity.id);
      }
    },
    [isMultiSelectMode, onEntitySelect, onToggleMergeSelection]
  );

  const getVerificationBadge = (entity: EntityListItem) => {
    if (entity.metadata?.verified === true) {
      return (
        <Badge variant="default" className="gap-1 bg-green-600">
          <CheckCircle2 className="h-3 w-3" />
          Verified
        </Badge>
      );
    }
    if (entity.metadata?.flagged === true) {
      return (
        <Badge variant="secondary" className="gap-1 text-amber-600">
          <AlertTriangle className="h-3 w-3" />
          Flagged
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="gap-1">
        <Clock className="h-3 w-3" />
        Pending
      </Badge>
    );
  };

  if (entities.length === 0) {
    return (
      <div
        className={cn(
          `flex items-center justify-center ${ENTITY_VIEW_HEIGHT} bg-muted/30 border rounded-lg`,
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
    <ScrollArea className={cn(ENTITY_VIEW_HEIGHT, 'pr-4', className)}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-1">
        {entities.map((entity) => {
          const config = entityTypeConfig[entity.entityType];
          const Icon = config.icon;
          const isSelected = selectedEntityId === entity.id;
          const isSelectedForMerge = selectedForMerge.has(entity.id);
          const roles = entity.metadata?.roles ?? [];
          const aliases = entity.metadata?.aliasesFound ?? [];
          const canSelect = selectedForMerge.size < 2 || isSelectedForMerge;

          return (
            <Card
              key={entity.id}
              className={cn(
                'cursor-pointer transition-all hover:shadow-md relative',
                isSelected && 'ring-2 ring-primary',
                isSelectedForMerge && 'ring-2 ring-primary bg-primary/5'
              )}
              onClick={() => handleCardClick(entity)}
              data-testid={`entity-card-${entity.id}`}
            >
              {/* Selection indicator for multi-select mode */}
              {isMultiSelectMode && (
                <div className="absolute top-3 right-3 z-10">
                  <Checkbox
                    checked={isSelectedForMerge}
                    onCheckedChange={() => onToggleMergeSelection?.(entity.id)}
                    onClick={(e) => e.stopPropagation()}
                    disabled={!canSelect}
                    aria-label={`Select ${entity.canonicalName} for merge`}
                  />
                </div>
              )}

              {/* Merge selection checkmark overlay */}
              {isSelectedForMerge && (
                <div className="absolute top-0 left-0 w-full h-1 bg-primary rounded-t-lg" />
              )}

              <CardHeader className="pb-2">
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-full',
                      config.bgColor,
                      config.color
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base leading-tight truncate pr-6">
                      {entity.canonicalName}
                    </CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" className="text-xs">
                        {config.label}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="pt-0 space-y-3">
                {/* Mention count */}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Mentions</span>
                  <span className="font-medium">{entity.mentionCount}</span>
                </div>

                {/* Verification status */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  {getVerificationBadge(entity)}
                </div>

                {/* Roles */}
                {roles.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Roles</span>
                    <div className="flex flex-wrap gap-1">
                      {roles.slice(0, 2).map((role, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs">
                          {role}
                        </Badge>
                      ))}
                      {roles.length > 2 && (
                        <span className="text-xs text-muted-foreground">
                          +{roles.length - 2} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Aliases */}
                {aliases.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Aliases</span>
                    <p className="text-xs truncate">
                      {aliases.slice(0, 2).join(', ')}
                      {aliases.length > 2 && ` +${aliases.length - 2} more`}
                    </p>
                  </div>
                )}

                {/* Confidence */}
                {entity.metadata?.firstExtractionConfidence !== undefined && (
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Confidence</span>
                    <span>{Math.round(entity.metadata.firstExtractionConfidence * 100)}%</span>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </ScrollArea>
  );
}

EntitiesGridView.displayName = 'EntitiesGridView';
