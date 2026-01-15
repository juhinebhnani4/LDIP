'use client';

/**
 * EntityEdge Component
 *
 * Custom React Flow edge for displaying relationships between entities.
 * Shows relationship type label and confidence score on hover.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import { memo, useState } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react';
import { cn } from '@/lib/utils';
import type { EntityEdgeData, RelationshipType } from '@/types/entity';

/** Relationship type configuration for styling */
const relationshipConfig: Record<
  RelationshipType,
  { label: string; color: string; dashed: boolean }
> = {
  ALIAS_OF: {
    label: 'Alias',
    color: '#6b7280', // gray-500
    dashed: true,
  },
  HAS_ROLE: {
    label: 'Has Role',
    color: '#3b82f6', // blue-500
    dashed: false,
  },
  RELATED_TO: {
    label: 'Related',
    color: '#10b981', // green-500
    dashed: false,
  },
};

// Use generic EdgeProps to avoid type constraint issues with @xyflow/react
export type EntityEdgeProps = EdgeProps;

export const EntityEdge = memo(function EntityEdge(props: EntityEdgeProps) {
  const {
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    data,
    selected,
    markerEnd,
  } = props;
  const [isHovered, setIsHovered] = useState(false);

  const edgeData = data as unknown as EntityEdgeData | undefined;
  const relationshipType = edgeData?.relationshipType ?? 'RELATED_TO';
  const config = relationshipConfig[relationshipType];
  const confidence = edgeData?.confidence ?? 0;

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 16,
  });

  return (
    <>
      {/* Invisible wider path for easier hover detection */}
      <path
        d={edgePath}
        fill="none"
        strokeWidth={20}
        stroke="transparent"
        className="cursor-pointer"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      />

      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: config.color,
          strokeWidth: selected || isHovered ? 3 : 2,
          strokeDasharray: config.dashed ? '5 5' : undefined,
          transition: 'stroke-width 150ms ease-in-out',
        }}
      />

      <EdgeLabelRenderer>
        <div
          className={cn(
            'absolute transform -translate-x-1/2 -translate-y-1/2 pointer-events-none',
            'px-2 py-1 rounded text-xs font-medium transition-opacity duration-150',
            'bg-background/90 border shadow-sm',
            isHovered || selected ? 'opacity-100' : 'opacity-70'
          )}
          style={{
            left: labelX,
            top: labelY,
            borderColor: config.color,
          }}
        >
          <span style={{ color: config.color }}>{config.label}</span>
          {(isHovered || selected) && confidence > 0 && (
            <span className="ml-1 text-muted-foreground">
              ({Math.round(confidence * 100)}%)
            </span>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
});

EntityEdge.displayName = 'EntityEdge';

/**
 * Get edge style based on relationship type
 */
export function getEdgeStyle(relationshipType: RelationshipType): {
  strokeDasharray?: string;
  stroke: string;
} {
  const config = relationshipConfig[relationshipType];
  return {
    stroke: config.color,
    strokeDasharray: config.dashed ? '5 5' : undefined,
  };
}
