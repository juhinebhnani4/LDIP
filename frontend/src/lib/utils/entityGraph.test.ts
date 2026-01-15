import { describe, it, expect } from 'vitest';
import {
  calculateNodeSize,
  transformEntitiesToNodes,
  transformRelationshipsToEdges,
  getConnectedNodeIds,
  applyDagreLayout,
  filterNodesByTypes,
  filterNodesBySearch,
  filterNodesByMentionCount,
  filterEdgesForNodes,
  updateNodeStates,
  getEntityTypeColor,
  countEntitiesByType,
  isLargeGraph,
  getTopEntitiesByMentions,
} from './entityGraph';
import type {
  EntityListItem,
  EntityEdge,
  EntityGraphNode,
  EntityGraphEdge,
} from '@/types/entity';

// Mock data factories
function createMockEntity(
  overrides: Partial<EntityListItem> = {}
): EntityListItem {
  return {
    id: 'entity-1',
    canonicalName: 'Test Entity',
    entityType: 'PERSON',
    mentionCount: 10,
    metadata: {},
    ...overrides,
  };
}

function createMockApiEdge(overrides: Partial<EntityEdge> = {}): EntityEdge {
  return {
    id: 'edge-1',
    matterId: 'matter-1',
    sourceEntityId: 'entity-1',
    targetEntityId: 'entity-2',
    relationshipType: 'RELATED_TO',
    confidence: 0.85,
    metadata: {},
    createdAt: '2026-01-15T00:00:00Z',
    ...overrides,
  };
}

function createMockGraphNode(
  overrides: Partial<EntityGraphNode> = {}
): EntityGraphNode {
  return {
    id: 'node-1',
    type: 'entity',
    position: { x: 0, y: 0 },
    data: {
      id: 'node-1',
      canonicalName: 'Test Node',
      entityType: 'PERSON',
      mentionCount: 10,
      aliases: [],
      metadata: {},
      isSelected: false,
      isConnected: false,
      isDimmed: false,
    },
    ...overrides,
  };
}

function createMockGraphEdge(
  overrides: Partial<EntityGraphEdge> = {}
): EntityGraphEdge {
  return {
    id: 'edge-1',
    source: 'node-1',
    target: 'node-2',
    type: 'relationship',
    data: {
      relationshipType: 'RELATED_TO',
      confidence: 0.85,
      metadata: {},
    },
    ...overrides,
  };
}

describe('calculateNodeSize', () => {
  it('returns near minimum size for 0 mentions', () => {
    // log10(0 + 1 + 1) = log10(2) ≈ 0.301, so size is ~66px
    const size = calculateNodeSize(0);
    expect(size).toBeGreaterThanOrEqual(60);
    expect(size).toBeLessThan(70);
  });

  it('returns size between min and max for moderate mentions', () => {
    const size = calculateNodeSize(50);
    expect(size).toBeGreaterThan(60);
    expect(size).toBeLessThan(120);
  });

  it('approaches maximum for high mentions', () => {
    const size = calculateNodeSize(1000);
    expect(size).toBeGreaterThan(110);
    expect(size).toBeLessThanOrEqual(120);
  });

  it('handles negative values same as 0', () => {
    // Negative values are treated as 0 due to Math.max(mentionCount, 1)
    expect(calculateNodeSize(-10)).toEqual(calculateNodeSize(0));
  });
});

describe('transformEntitiesToNodes', () => {
  it('transforms entities to React Flow nodes', () => {
    const entities = [
      createMockEntity({ id: 'e1', canonicalName: 'Entity 1' }),
      createMockEntity({ id: 'e2', canonicalName: 'Entity 2' }),
    ];

    const nodes = transformEntitiesToNodes(entities);

    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe('e1');
    expect(nodes[0].type).toBe('entity');
    expect(nodes[0].data.canonicalName).toBe('Entity 1');
    expect(nodes[1].id).toBe('e2');
  });

  it('sets default node states', () => {
    const entities = [createMockEntity()];
    const nodes = transformEntitiesToNodes(entities);

    expect(nodes[0].data.isSelected).toBe(false);
    expect(nodes[0].data.isConnected).toBe(false);
    expect(nodes[0].data.isDimmed).toBe(false);
  });

  it('uses provided positions when available', () => {
    const entities = [createMockEntity({ id: 'e1' })];
    const positions = new Map([['e1', { x: 100, y: 200 }]]);

    const nodes = transformEntitiesToNodes(entities, positions);

    expect(nodes[0].position).toEqual({ x: 100, y: 200 });
  });

  it('extracts aliases from metadata', () => {
    const entities = [
      createMockEntity({
        metadata: { aliasesFound: ['Alias 1', 'Alias 2'] },
      }),
    ];

    const nodes = transformEntitiesToNodes(entities);

    expect(nodes[0].data.aliases).toEqual(['Alias 1', 'Alias 2']);
  });
});

describe('transformRelationshipsToEdges', () => {
  it('transforms API edges to React Flow edges', () => {
    const relationships = [
      createMockApiEdge({
        id: 'rel-1',
        sourceEntityId: 'e1',
        targetEntityId: 'e2',
        relationshipType: 'ALIAS_OF',
      }),
    ];

    const edges = transformRelationshipsToEdges(relationships);

    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe('rel-1');
    expect(edges[0].source).toBe('e1');
    expect(edges[0].target).toBe('e2');
    expect(edges[0].type).toBe('relationship');
    expect(edges[0].data?.relationshipType).toBe('ALIAS_OF');
  });

  it('preserves confidence score', () => {
    const relationships = [
      createMockApiEdge({ confidence: 0.92 }),
    ];

    const edges = transformRelationshipsToEdges(relationships);

    expect(edges[0].data?.confidence).toBe(0.92);
  });
});

describe('getConnectedNodeIds', () => {
  it('returns empty array when no edges', () => {
    const result = getConnectedNodeIds('node-1', []);
    expect(result).toEqual([]);
  });

  it('finds connected nodes as source', () => {
    const edges = [
      createMockGraphEdge({ source: 'node-1', target: 'node-2' }),
      createMockGraphEdge({ id: 'e2', source: 'node-1', target: 'node-3' }),
    ];

    const result = getConnectedNodeIds('node-1', edges);

    expect(result).toContain('node-2');
    expect(result).toContain('node-3');
  });

  it('finds connected nodes as target', () => {
    const edges = [
      createMockGraphEdge({ source: 'node-2', target: 'node-1' }),
    ];

    const result = getConnectedNodeIds('node-1', edges);

    expect(result).toContain('node-2');
  });

  it('returns unique IDs', () => {
    const edges = [
      createMockGraphEdge({ id: 'e1', source: 'node-1', target: 'node-2' }),
      createMockGraphEdge({ id: 'e2', source: 'node-2', target: 'node-1' }),
    ];

    const result = getConnectedNodeIds('node-1', edges);

    expect(result).toHaveLength(1);
    expect(result).toContain('node-2');
  });
});

describe('applyDagreLayout', () => {
  it('returns empty array for empty nodes', () => {
    const result = applyDagreLayout([], []);
    expect(result).toEqual([]);
  });

  it('positions nodes in layout', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1' }),
      createMockGraphNode({ id: 'n2' }),
    ];
    const edges = [createMockGraphEdge({ source: 'n1', target: 'n2' })];

    const result = applyDagreLayout(nodes, edges);

    expect(result).toHaveLength(2);
    // Nodes should have different positions
    expect(result[0].position).not.toEqual(result[1].position);
  });

  it('handles disconnected nodes', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1' }),
      createMockGraphNode({ id: 'n2' }),
    ];

    const result = applyDagreLayout(nodes, []);

    expect(result).toHaveLength(2);
    // Both nodes should have positions
    expect(result[0].position).toBeDefined();
    expect(result[1].position).toBeDefined();
  });
});

describe('filterNodesByTypes', () => {
  it('returns all nodes when no filter', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1', data: { ...createMockGraphNode().data, entityType: 'PERSON' } }),
      createMockGraphNode({ id: 'n2', data: { ...createMockGraphNode().data, entityType: 'ORG' } }),
    ];

    const result = filterNodesByTypes(nodes, []);

    expect(result).toHaveLength(2);
  });

  it('filters by single type', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1', data: { ...createMockGraphNode().data, entityType: 'PERSON' } }),
      createMockGraphNode({ id: 'n2', data: { ...createMockGraphNode().data, entityType: 'ORG' } }),
    ];

    const result = filterNodesByTypes(nodes, ['PERSON']);

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('n1');
  });

  it('filters by multiple types', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1', data: { ...createMockGraphNode().data, entityType: 'PERSON' } }),
      createMockGraphNode({ id: 'n2', data: { ...createMockGraphNode().data, entityType: 'ORG' } }),
      createMockGraphNode({ id: 'n3', data: { ...createMockGraphNode().data, entityType: 'ASSET' } }),
    ];

    const result = filterNodesByTypes(nodes, ['PERSON', 'ORG']);

    expect(result).toHaveLength(2);
  });
});

describe('filterNodesBySearch', () => {
  it('returns all nodes when no search query', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1' }),
      createMockGraphNode({ id: 'n2' }),
    ];

    const result = filterNodesBySearch(nodes, '');

    expect(result).toHaveLength(2);
  });

  it('filters by canonical name', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1', data: { ...createMockGraphNode().data, canonicalName: 'John Doe' } }),
      createMockGraphNode({ id: 'n2', data: { ...createMockGraphNode().data, canonicalName: 'Jane Smith' } }),
    ];

    const result = filterNodesBySearch(nodes, 'John');

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('n1');
  });

  it('is case insensitive', () => {
    const nodes = [
      createMockGraphNode({ data: { ...createMockGraphNode().data, canonicalName: 'JOHN DOE' } }),
    ];

    const result = filterNodesBySearch(nodes, 'john');

    expect(result).toHaveLength(1);
  });
});

describe('filterNodesByMentionCount', () => {
  it('returns all nodes when min is 0', () => {
    const nodes = [
      createMockGraphNode({ data: { ...createMockGraphNode().data, mentionCount: 5 } }),
      createMockGraphNode({ id: 'n2', data: { ...createMockGraphNode().data, mentionCount: 10 } }),
    ];

    const result = filterNodesByMentionCount(nodes, 0);

    expect(result).toHaveLength(2);
  });

  it('filters by minimum count', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1', data: { ...createMockGraphNode().data, mentionCount: 5 } }),
      createMockGraphNode({ id: 'n2', data: { ...createMockGraphNode().data, mentionCount: 10 } }),
      createMockGraphNode({ id: 'n3', data: { ...createMockGraphNode().data, mentionCount: 15 } }),
    ];

    const result = filterNodesByMentionCount(nodes, 10);

    expect(result).toHaveLength(2);
    expect(result.map((n) => n.id)).toEqual(['n2', 'n3']);
  });
});

describe('filterEdgesForNodes', () => {
  it('keeps edges where both nodes exist', () => {
    const edges = [
      createMockGraphEdge({ source: 'n1', target: 'n2' }),
      createMockGraphEdge({ id: 'e2', source: 'n2', target: 'n3' }),
    ];
    const nodeIds = new Set(['n1', 'n2']);

    const result = filterEdgesForNodes(edges, nodeIds);

    expect(result).toHaveLength(1);
    expect(result[0].source).toBe('n1');
    expect(result[0].target).toBe('n2');
  });

  it('removes edges with missing nodes', () => {
    const edges = [
      createMockGraphEdge({ source: 'n1', target: 'n2' }),
    ];
    const nodeIds = new Set(['n1']); // n2 missing

    const result = filterEdgesForNodes(edges, nodeIds);

    expect(result).toHaveLength(0);
  });
});

describe('updateNodeStates', () => {
  it('clears all states when nothing selected', () => {
    const nodes = [
      createMockGraphNode({ data: { ...createMockGraphNode().data, isSelected: true } }),
    ];

    const result = updateNodeStates(nodes, null, []);

    expect(result[0].data.isSelected).toBe(false);
    expect(result[0].data.isConnected).toBe(false);
    expect(result[0].data.isDimmed).toBe(false);
  });

  it('marks selected node', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1' }),
      createMockGraphNode({ id: 'n2' }),
    ];

    const result = updateNodeStates(nodes, 'n1', []);

    expect(result[0].data.isSelected).toBe(true);
    expect(result[1].data.isSelected).toBe(false);
  });

  it('marks connected nodes', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1' }),
      createMockGraphNode({ id: 'n2' }),
      createMockGraphNode({ id: 'n3' }),
    ];
    const edges = [createMockGraphEdge({ source: 'n1', target: 'n2' })];

    const result = updateNodeStates(nodes, 'n1', edges);

    expect(result[0].data.isConnected).toBe(false); // selected, not connected
    expect(result[1].data.isConnected).toBe(true);
    expect(result[2].data.isConnected).toBe(false);
  });

  it('dims unconnected nodes', () => {
    const nodes = [
      createMockGraphNode({ id: 'n1' }),
      createMockGraphNode({ id: 'n2' }),
      createMockGraphNode({ id: 'n3' }),
    ];
    const edges = [createMockGraphEdge({ source: 'n1', target: 'n2' })];

    const result = updateNodeStates(nodes, 'n1', edges);

    expect(result[0].data.isDimmed).toBe(false); // selected
    expect(result[1].data.isDimmed).toBe(false); // connected
    expect(result[2].data.isDimmed).toBe(true); // not connected
  });
});

describe('getEntityTypeColor', () => {
  it('returns blue for PERSON', () => {
    expect(getEntityTypeColor('PERSON')).toBe('#3b82f6');
  });

  it('returns green for ORG', () => {
    expect(getEntityTypeColor('ORG')).toBe('#10b981');
  });

  it('returns purple for INSTITUTION', () => {
    expect(getEntityTypeColor('INSTITUTION')).toBe('#8b5cf6');
  });

  it('returns amber for ASSET', () => {
    expect(getEntityTypeColor('ASSET')).toBe('#f59e0b');
  });
});

describe('countEntitiesByType', () => {
  it('returns zero counts for empty array', () => {
    const result = countEntitiesByType([]);

    expect(result.PERSON).toBe(0);
    expect(result.ORG).toBe(0);
    expect(result.INSTITUTION).toBe(0);
    expect(result.ASSET).toBe(0);
  });

  it('counts entities by type', () => {
    const entities = [
      createMockEntity({ entityType: 'PERSON' }),
      createMockEntity({ id: 'e2', entityType: 'PERSON' }),
      createMockEntity({ id: 'e3', entityType: 'ORG' }),
    ];

    const result = countEntitiesByType(entities);

    expect(result.PERSON).toBe(2);
    expect(result.ORG).toBe(1);
    expect(result.INSTITUTION).toBe(0);
  });
});

describe('isLargeGraph', () => {
  it('returns false for 100 or fewer nodes', () => {
    expect(isLargeGraph(100)).toBe(false);
    expect(isLargeGraph(50)).toBe(false);
  });

  it('returns true for more than 100 nodes', () => {
    expect(isLargeGraph(101)).toBe(true);
    expect(isLargeGraph(500)).toBe(true);
  });
});

describe('getTopEntitiesByMentions', () => {
  it('returns top entities by mention count', () => {
    const entities = [
      createMockEntity({ id: 'e1', mentionCount: 5 }),
      createMockEntity({ id: 'e2', mentionCount: 20 }),
      createMockEntity({ id: 'e3', mentionCount: 10 }),
    ];

    const result = getTopEntitiesByMentions(entities, 2);

    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('e2'); // 20 mentions
    expect(result[1].id).toBe('e3'); // 10 mentions
  });

  it('returns all entities if limit exceeds count', () => {
    const entities = [
      createMockEntity({ id: 'e1' }),
      createMockEntity({ id: 'e2' }),
    ];

    const result = getTopEntitiesByMentions(entities, 10);

    expect(result).toHaveLength(2);
  });

  it('does not modify original array', () => {
    const entities = [
      createMockEntity({ id: 'e1', mentionCount: 5 }),
      createMockEntity({ id: 'e2', mentionCount: 20 }),
    ];

    getTopEntitiesByMentions(entities, 1);

    expect(entities[0].id).toBe('e1'); // Original order preserved
  });
});
