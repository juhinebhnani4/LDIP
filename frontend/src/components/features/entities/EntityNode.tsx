'use client';

/**
 * EntityNode Component
 *
 * Custom React Flow node for displaying entities in the MIG graph.
 * Shows canonical name, entity type badge, and scales size by mention count.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import { memo, useCallback, type KeyboardEvent } from 'react';
import { Handle, Position, type NodeProps, useReactFlow } from '@xyflow/react';
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

/** Entity type configuration for icons and colors - Jaanch "Intelligent Legal" brand palette (UX Design v1.2) */
const entityTypeConfig: Record<
  EntityType,
  { icon: typeof User; color: string; label: string }
> = {
  PERSON: {
    icon: User,
    // Deep Navy (brand primary) - Light indigo background
    color: 'bg-[#e0e7ff] text-[#1a2744] border-[#c7d2fe] dark:bg-[#1a2744]/30 dark:text-[#93a3d1] dark:border-[#93a3d1]/30',
    label: 'Person',
  },
  ORG: {
    icon: Building2,
    // Legal Green - Light green background
    color: 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0] dark:bg-[#166534]/20 dark:text-[#22c55e] dark:border-[#22c55e]/30',
    label: 'Org',
  },
  INSTITUTION: {
    icon: Landmark,
    // Deep Purple - Light purple background
    color: 'bg-[#f3e8ff] text-[#7c3aed] border-[#e9d5ff] dark:bg-[#7c3aed]/20 dark:text-[#a78bfa] dark:border-[#a78bfa]/30',
    label: 'Institution',
  },
  ASSET: {
    icon: Package,
    // Warm Gold (brand accent) - Light gold background
    color: 'bg-[#f5e6b8] text-[#92400e] border-[#fde68a] dark:bg-[#c9a227]/20 dark:text-[#dbb536] dark:border-[#dbb536]/30',
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

// Use generic NodeProps to avoid type constraint issues with @xyflow/react
export type EntityNodeProps = NodeProps;

export const EntityNode = memo(function EntityNode(props: EntityNodeProps) {
  const { data, id } = props;
  const nodeData = data as unknown as EntityNodeData;
  const { icon: Icon, color, label } = entityTypeConfig[nodeData.entityType];
  const size = calculateNodeSize(nodeData.mentionCount);
  const { fitView } = useReactFlow();

  // Handle keyboard interaction - Enter/Space selects, Escape deselects
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        // Trigger click event to select/deselect node
        (event.target as HTMLElement).click();
      } else if (event.key === 'Escape') {
        // Blur the current element to deselect
        (event.target as HTMLElement).blur();
      } else if (event.key === 'f' || event.key === 'F') {
        // Focus/fit view on this node
        event.preventDefault();
        fitView({
          nodes: [{ id }],
          duration: 500,
          padding: 0.5,
        });
      }
    },
    [fitView, id]
  );

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              'flex flex-col items-center justify-center rounded-full border-2 transition-all duration-200',
              'bg-background shadow-md cursor-pointer',
              nodeData.isSelected && 'ring-4 ring-primary ring-offset-2',
              nodeData.isConnected && 'ring-2 ring-primary/50',
              nodeData.isDimmed && 'opacity-30',
              nodeData.isSelectedForMerge && 'ring-4 ring-amber-500 ring-offset-2 border-amber-500'
            )}
            style={{ width: size, height: size }}
            role="button"
            tabIndex={0}
            aria-label={`${nodeData.canonicalName}, ${label}, ${nodeData.mentionCount} mentions. Press Enter to select, F to focus.`}
            aria-pressed={nodeData.isSelected}
            onKeyDown={handleKeyDown}
          >
            <Icon className="h-5 w-5 mb-1" aria-hidden="true" />

            <span className="text-xs font-medium text-center px-2 truncate max-w-full">
              {truncateName(nodeData.canonicalName, 15)}
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
            <p className="font-medium">{nodeData.canonicalName}</p>
            <p className="text-muted-foreground text-sm">
              {label} &bull; {nodeData.mentionCount} mention
              {nodeData.mentionCount !== 1 ? 's' : ''}
            </p>
            {nodeData.aliases.length > 0 && (
              <p className="text-muted-foreground text-sm">
                {nodeData.aliases.length} alias
                {nodeData.aliases.length !== 1 ? 'es' : ''}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
});

EntityNode.displayName = 'EntityNode';
