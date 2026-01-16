'use client';

/**
 * EntitiesRenderer Component
 *
 * Renders the Entities section in export preview.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { Button } from '@/components/ui/button';
import { X, RotateCcw, User, Building2, Landmark, Briefcase } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EntityListItem } from '@/types/entity';

export interface EntitiesRendererProps {
  /** Entities list */
  entities?: EntityListItem[];
  /** IDs of removed entities */
  removedItemIds: string[];
  /** Handler for removing an entity */
  onRemoveItem: (itemId: string) => void;
  /** Handler for restoring an entity */
  onRestoreItem: (itemId: string) => void;
  /** Whether editing is active */
  isEditing: boolean;
}

/**
 * Get icon for entity type
 */
function getEntityIcon(type: string) {
  switch (type) {
    case 'PERSON':
      return User;
    case 'ORG':
      return Building2;
    case 'INSTITUTION':
      return Landmark;
    case 'ASSET':
      return Briefcase;
    default:
      return User;
  }
}

/**
 * EntitiesRenderer displays entities with type indicators.
 */
export function EntitiesRenderer({
  entities,
  removedItemIds,
  onRemoveItem,
  onRestoreItem,
  isEditing,
}: EntitiesRendererProps) {
  if (!entities || entities.length === 0) {
    return <p className="text-muted-foreground text-sm">No entities available</p>;
  }

  // Filter out removed entities
  const visibleEntities = entities.filter((entity) => !removedItemIds.includes(entity.id));
  const removedEntities = entities.filter((entity) => removedItemIds.includes(entity.id));

  return (
    <div className="space-y-2 font-serif text-sm">
      {visibleEntities.length === 0 ? (
        <p className="text-muted-foreground">All entities have been removed</p>
      ) : (
        <div className="grid gap-2">
          {visibleEntities.map((entity) => {
            const Icon = getEntityIcon(entity.entityType);
            return (
              <div
                key={entity.id}
                className={cn(
                  'flex items-center gap-3 p-3 rounded border border-gray-200 dark:border-gray-700 group',
                  isEditing && 'hover:border-red-300 dark:hover:border-red-700'
                )}
                data-testid={`entity-item-${entity.id}`}
              >
                <div className={cn(
                  'p-2 rounded-full',
                  entity.entityType === 'PERSON' && 'bg-blue-100 dark:bg-blue-900',
                  entity.entityType === 'ORG' && 'bg-green-100 dark:bg-green-900',
                  entity.entityType === 'INSTITUTION' && 'bg-purple-100 dark:bg-purple-900',
                  entity.entityType === 'ASSET' && 'bg-orange-100 dark:bg-orange-900'
                )}>
                  <Icon className="h-4 w-4" />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="font-medium">{entity.canonicalName}</p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {entity.entityType.toLowerCase().replace('_', ' ')}
                    {entity.aliases && entity.aliases.length > 0 && (
                      <span> · Also known as: {entity.aliases.slice(0, 2).join(', ')}</span>
                    )}
                  </p>
                </div>

                {isEditing && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                    onClick={() => onRemoveItem(entity.id)}
                    aria-label={`Remove entity: ${entity.canonicalName}`}
                  >
                    <X className="h-4 w-4 text-red-500" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Removed entities (edit mode only) */}
      {isEditing && removedEntities.length > 0 && (
        <div className="mt-4 pt-4 border-t border-dashed">
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Removed Entities:</h4>
          {removedEntities.map((entity) => (
            <div
              key={entity.id}
              className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded opacity-60"
            >
              <span className="flex-1 text-sm line-through">{entity.canonicalName}</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1"
                onClick={() => onRestoreItem(entity.id)}
              >
                <RotateCcw className="h-3 w-3" />
                Restore
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
