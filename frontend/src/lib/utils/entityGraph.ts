/**
 * Entity Graph Utilities
 *
 * Transformation utilities for converting API entity data to React Flow format.
 * Includes dagre layout for automatic hierarchical positioning.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import dagre from 'dagre';
import type {
  EntityGraphNode,
  EntityGraphEdge,
  EntityListItem,
  EntityEdge as ApiEntityEdge,
  EntityType,
} from '@/types/entity';

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
 * Transform API entities to React Flow nodes
 */
export function transformEntitiesToNodes(
  entities: EntityListItem[],
  positions?: Map<string, { x: number; y: number }>
): EntityGraphNode[] {
  return entities.map((entity, index) => {
    const position = positions?.get(entity.id) ?? { x: index * 150, y: 0 };

    return {
      id: entity.id,
      type: 'entity',
      position,
      data: {
        id: entity.id,
        canonicalName: entity.canonicalName,
        entityType: entity.entityType,
        mentionCount: entity.mentionCount,
        aliases: entity.metadata.aliasesFound ?? [],
        metadata: entity.metadata,
        isSelected: false,
        isConnected: false,
        isDimmed: false,
      },
    };
  });
}

/**
 * Transform API relationships to React Flow edges
 */
export function transformRelationshipsToEdges(
  relationships: ApiEntityEdge[]
): EntityGraphEdge[] {
  return relationships.map((rel) => ({
    id: rel.id,
    source: rel.sourceEntityId,
    target: rel.targetEntityId,
    type: 'relationship',
    data: {
      relationshipType: rel.relationshipType,
      confidence: rel.confidence,
      metadata: rel.metadata,
    },
  }));
}

/**
 * Get IDs of nodes connected to a given node
 */
export function getConnectedNodeIds(
  nodeId: string,
  edges: EntityGraphEdge[]
): string[] {
  const connectedIds = new Set<string>();

  for (const edge of edges) {
    if (edge.source === nodeId) {
      connectedIds.add(edge.target);
    } else if (edge.target === nodeId) {
      connectedIds.add(edge.source);
    }
  }

  return Array.from(connectedIds);
}

/**
 * Apply dagre layout to nodes for hierarchical positioning
 */
export function applyDagreLayout(
  nodes: EntityGraphNode[],
  edges: EntityGraphEdge[],
  direction: 'TB' | 'LR' = 'TB'
): EntityGraphNode[] {
  if (nodes.length === 0) return nodes;

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    nodesep: 80,
    ranksep: 100,
    marginx: 20,
    marginy: 20,
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Add nodes to dagre
  for (const node of nodes) {
    const size = calculateNodeSize(node.data.mentionCount);
    g.setNode(node.id, { width: size, height: size });
  }

  // Add edges to dagre
  for (const edge of edges) {
    // Only add edge if both source and target exist in nodes
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  }

  // Calculate layout
  dagre.layout(g);

  // Apply positions
  return nodes.map((node) => {
    const nodeWithPosition = g.node(node.id);
    if (!nodeWithPosition) return node;

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });
}

/**
 * Filter nodes by entity types
 */
export function filterNodesByTypes(
  nodes: EntityGraphNode[],
  entityTypes: EntityType[]
): EntityGraphNode[] {
  if (entityTypes.length === 0) return nodes;
  return nodes.filter((node) => entityTypes.includes(node.data.entityType));
}

/**
 * Filter nodes by search query (canonical name match)
 */
export function filterNodesBySearch(
  nodes: EntityGraphNode[],
  searchQuery: string
): EntityGraphNode[] {
  if (!searchQuery.trim()) return nodes;
  const query = searchQuery.toLowerCase().trim();
  return nodes.filter((node) =>
    node.data.canonicalName.toLowerCase().includes(query)
  );
}

/**
 * Filter nodes by minimum mention count
 */
export function filterNodesByMentionCount(
  nodes: EntityGraphNode[],
  minMentionCount: number
): EntityGraphNode[] {
  if (minMentionCount <= 0) return nodes;
  return nodes.filter((node) => node.data.mentionCount >= minMentionCount);
}

/**
 * Filter edges to only include those connecting visible nodes
 */
export function filterEdgesForNodes(
  edges: EntityGraphEdge[],
  nodeIds: Set<string>
): EntityGraphEdge[] {
  return edges.filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)
  );
}

/**
 * Update node states based on selection
 */
export function updateNodeStates(
  nodes: EntityGraphNode[],
  selectedNodeId: string | null,
  edges: EntityGraphEdge[]
): EntityGraphNode[] {
  if (!selectedNodeId) {
    // Clear all states when nothing selected
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        isSelected: false,
        isConnected: false,
        isDimmed: false,
      },
    }));
  }

  const connectedIds = new Set(getConnectedNodeIds(selectedNodeId, edges));
  connectedIds.add(selectedNodeId);

  return nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      isSelected: node.id === selectedNodeId,
      isConnected: connectedIds.has(node.id) && node.id !== selectedNodeId,
      isDimmed: !connectedIds.has(node.id),
    },
  }));
}

/**
 * Get entity type color for minimap
 * Uses jaanch.ai brand colors
 */
export function getEntityTypeColor(entityType: EntityType): string {
  const colors: Record<EntityType, string> = {
    PERSON: '#0d1b5e', // Deep Indigo (brand primary)
    ORG: '#2d5a3d', // Forest Green
    INSTITUTION: '#5a3d6b', // Deep Purple
    ASSET: '#b8973b', // Muted Gold (brand accent)
  };
  return colors[entityType] ?? '#6b6b6b'; // Soft Gray fallback
}

/**
 * Count entities by type
 */
export function countEntitiesByType(
  entities: EntityListItem[]
): Record<EntityType, number> {
  const counts: Record<EntityType, number> = {
    PERSON: 0,
    ORG: 0,
    INSTITUTION: 0,
    ASSET: 0,
  };

  for (const entity of entities) {
    counts[entity.entityType]++;
  }

  return counts;
}

/**
 * Check if graph is considered large (>100 nodes)
 */
export function isLargeGraph(nodeCount: number): boolean {
  return nodeCount > 100;
}

/**
 * Get top entities by mention count for large graph filtering
 */
export function getTopEntitiesByMentions(
  entities: EntityListItem[],
  limit: number
): EntityListItem[] {
  return [...entities]
    .sort((a, b) => b.mentionCount - a.mentionCount)
    .slice(0, limit);
}
