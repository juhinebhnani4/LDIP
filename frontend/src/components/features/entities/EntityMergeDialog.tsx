'use client';

/**
 * EntityMergeDialog Component
 *
 * Dialog for confirming entity merge operations.
 * Shows both entities side-by-side and lets user choose which to keep.
 *
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { useCallback, useState } from 'react';
import { ArrowRight, Check, AlertTriangle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { entityTypeConfig } from '@/lib/utils/entityConstants';
import type { EntityListItem } from '@/types/entity';

export interface EntityMergeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceEntity: EntityListItem | null;
  targetEntity: EntityListItem | null;
  onConfirm: (sourceId: string, targetId: string, reason?: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
}

export function EntityMergeDialog({
  open,
  onOpenChange,
  sourceEntity,
  targetEntity,
  onConfirm,
  isLoading = false,
  error = null,
}: EntityMergeDialogProps) {
  const [keptEntityId, setKeptEntityId] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  // Determine which entity is source (deleted) and target (kept)
  const getSourceAndTarget = useCallback(() => {
    if (!sourceEntity || !targetEntity) return null;

    // If user has selected which to keep
    if (keptEntityId === sourceEntity.id) {
      return { source: targetEntity, target: sourceEntity };
    } else if (keptEntityId === targetEntity.id) {
      return { source: sourceEntity, target: targetEntity };
    }

    // Default: keep the one with more mentions
    if (sourceEntity.mentionCount >= targetEntity.mentionCount) {
      return { source: targetEntity, target: sourceEntity };
    }
    return { source: sourceEntity, target: targetEntity };
  }, [sourceEntity, targetEntity, keptEntityId]);

  const handleConfirm = useCallback(async () => {
    const entities = getSourceAndTarget();
    if (!entities) return;

    await onConfirm(entities.source.id, entities.target.id, reason || undefined);
  }, [getSourceAndTarget, onConfirm, reason]);

  const handleClose = useCallback(() => {
    if (!isLoading) {
      setKeptEntityId(null);
      setReason('');
      onOpenChange(false);
    }
  }, [isLoading, onOpenChange]);

  const entities = getSourceAndTarget();
  const sameType = sourceEntity?.entityType === targetEntity?.entityType;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Merge Entities</DialogTitle>
          <DialogDescription>
            Combine two entities into one. The source entity will be deleted and
            its aliases will be added to the target entity.
          </DialogDescription>
        </DialogHeader>

        {!sameType && sourceEntity && targetEntity && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Type Mismatch</AlertTitle>
            <AlertDescription>
              These entities have different types ({entityTypeConfig[sourceEntity.entityType].label} and{' '}
              {entityTypeConfig[targetEntity.entityType].label}). Merging is typically
              done between entities of the same type.
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Merge Failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-[1fr,auto,1fr] gap-4 items-center py-4">
          {/* Source Entity (will be deleted) */}
          <EntityCard
            entity={entities?.source ?? sourceEntity}
            label="Will be deleted"
            isSelected={entities?.source?.id !== keptEntityId}
            onSelect={() => {
              const other = sourceEntity?.id === entities?.source?.id ? targetEntity : sourceEntity;
              if (other) setKeptEntityId(other.id);
            }}
            variant="source"
          />

          {/* Arrow */}
          <div className="flex flex-col items-center gap-1">
            <ArrowRight className="h-6 w-6 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">merges into</span>
          </div>

          {/* Target Entity (will be kept) */}
          <EntityCard
            entity={entities?.target ?? targetEntity}
            label="Will be kept"
            isSelected={entities?.target?.id === keptEntityId || !keptEntityId}
            onSelect={() => {
              const target = entities?.target ?? targetEntity;
              if (target) setKeptEntityId(target.id);
            }}
            variant="target"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="merge-reason">Reason (optional)</Label>
          <Textarea
            id="merge-reason"
            placeholder="e.g., Same person with different name variations"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={isLoading}
            rows={2}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isLoading || !entities}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Merging...
              </>
            ) : (
              'Confirm Merge'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface EntityCardProps {
  entity: EntityListItem | null;
  label: string;
  isSelected: boolean;
  onSelect: () => void;
  variant: 'source' | 'target';
}

function EntityCard({
  entity,
  label,
  isSelected,
  onSelect,
  variant,
}: EntityCardProps) {
  if (!entity) {
    return (
      <Card className="opacity-50">
        <CardContent className="flex items-center justify-center h-32">
          <span className="text-muted-foreground">Select an entity</span>
        </CardContent>
      </Card>
    );
  }

  const config = entityTypeConfig[entity.entityType];
  const Icon = config.icon;

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all',
        isSelected && variant === 'source' && 'border-destructive/50 bg-destructive/5',
        isSelected && variant === 'target' && 'border-primary bg-primary/5',
        !isSelected && 'opacity-60 hover:opacity-100'
      )}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onSelect();
        }
      }}
      aria-label={`Select ${entity.canonicalName} as ${variant === 'source' ? 'entity to delete' : 'entity to keep'}`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Badge
            variant={variant === 'source' ? 'destructive' : 'default'}
            className="text-xs"
          >
            {label}
          </Badge>
          {isSelected && (
            <Check className={cn(
              'h-4 w-4',
              variant === 'source' ? 'text-destructive' : 'text-primary'
            )} />
          )}
        </div>
        <CardTitle className="text-base flex items-center gap-2 mt-2">
          <Icon className={cn('h-4 w-4', config.color)} />
          {entity.canonicalName}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-1 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {config.label}
            </Badge>
          </div>
          <p>{entity.mentionCount} mentions</p>
          {entity.metadata.aliasesFound && entity.metadata.aliasesFound.length > 0 && (
            <p className="text-xs">
              Aliases: {entity.metadata.aliasesFound.slice(0, 3).join(', ')}
              {entity.metadata.aliasesFound.length > 3 && ` +${entity.metadata.aliasesFound.length - 3} more`}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

EntityMergeDialog.displayName = 'EntityMergeDialog';
