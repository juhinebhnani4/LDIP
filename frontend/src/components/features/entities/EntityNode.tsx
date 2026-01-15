'use client';

/**
 * EntityNode Component
 *
 * Custom React Flow node for displaying entities in the MIG graph.
 * Shows canonical name, entity type badge, and scales size by mention count.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { User, Building2, Landmark, Package } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { EntityNodeData, EntityType } from '@/types/entity';

/** Entity type configuration for icons and colors */
const entityTypeConfig: Record<
  EntityType,
  { icon: typeof User; color: string; label: string }
> = {
  PERSON: {
    icon: User,
    color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800',
    label: 'Person',
  },
  ORG: {
    icon: Building2,
    color: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800',
    label: 'Org',
  },
  INSTITUTION: {
    icon: Landmark,
    color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800',
    label: 'Institution',
  },
  ASSET: {
    icon: Package,
    color: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800',
    label: 'Asset',
  },
};

/**
 * Calculate node size based on mention count (60-120px, log scale)
 */
export function calculateNodeSize(mentionCount: number): number {
  const minSize = 60;
  const maxSize = 120;
  const logScale = Math.log10(Math.max(mentionCount, 1) + 1);
  const normalizedScale = Math.min(logScale / 3, 1); // Cap at ~1000 mentions
  return minSize + (maxSize - minSize) * normalizedScale;
}

/**
 * Truncate text with ellipsis
 */
function truncateName(name: string, maxLength: number): string {
  if (name.length <= maxLength) return name;
  return `${name.slice(0, maxLength - 3)}...`;
}

export interface EntityNodeProps extends NodeProps {
  data: EntityNodeData;
}

export const EntityNode = memo(function EntityNode({ data }: EntityNodeProps) {
  const { icon: Icon, color, label } = entityTypeConfig[data.entityType];
  const size = calculateNodeSize(data.mentionCount);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              'flex flex-col items-center justify-center rounded-full border-2 transition-all duration-200',
              'bg-background shadow-md cursor-pointer',
              data.isSelected && 'ring-4 ring-primary ring-offset-2',
              data.isConnected && 'ring-2 ring-primary/50',
              data.isDimmed && 'opacity-30'
            )}
            style={{ width: size, height: size }}
            role="button"
            tabIndex={0}
            aria-label={`${data.canonicalName}, ${label}, ${data.mentionCount} mentions`}
            aria-selected={data.isSelected}
          >
            <Icon className="h-5 w-5 mb-1" aria-hidden="true" />

            <span className="text-xs font-medium text-center px-2 truncate max-w-full">
              {truncateName(data.canonicalName, 15)}
            </span>

            <Badge
              variant="secondary"
              className={cn('text-[10px] mt-1 border', color)}
            >
              {label}
            </Badge>

            <Handle
              type="target"
              position={Position.Top}
              className="!opacity-0 !w-2 !h-2"
              aria-hidden="true"
            />
            <Handle
              type="source"
              position={Position.Bottom}
              className="!opacity-0 !w-2 !h-2"
              aria-hidden="true"
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-1">
            <p className="font-medium">{data.canonicalName}</p>
            <p className="text-muted-foreground text-sm">
              {label} &bull; {data.mentionCount} mention
              {data.mentionCount !== 1 ? 's' : ''}
            </p>
            {data.aliases.length > 0 && (
              <p className="text-muted-foreground text-sm">
                {data.aliases.length} alias
                {data.aliases.length !== 1 ? 'es' : ''}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
});

EntityNode.displayName = 'EntityNode';
