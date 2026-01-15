import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EntitiesGraph } from './EntitiesGraph';
import type { EntityGraphData, EntityGraphNode, EntityGraphEdge } from '@/types/entity';

// Mock React Flow components
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children, nodes, onNodeClick, onPaneClick }: {
    children: React.ReactNode;
    nodes: EntityGraphNode[];
    onNodeClick?: (e: unknown, node: EntityGraphNode) => void;
    onPaneClick?: () => void;
  }) => (
    <div data-testid="react-flow" onClick={onPaneClick}>
      {nodes.map((node) => (
        <div
          key={node.id}
          data-testid={`node-${node.id}`}
          onClick={(e) => onNodeClick?.(e, node)}
          data-selected={node.data.isSelected}
          data-dimmed={node.data.isDimmed}
        >
          {node.data.canonicalName}
        </div>
      ))}
      {children}
    </div>
  ),
  Controls: () => <div data-testid="controls">Controls</div>,
  MiniMap: () => <div data-testid="minimap">MiniMap</div>,
  Background: () => <div data-testid="background">Background</div>,
  BackgroundVariant: { Dots: 'dots' },
  useNodesState: (initial: EntityGraphNode[]) => [initial, vi.fn(), vi.fn()],
  useEdgesState: (initial: EntityGraphEdge[]) => [initial, vi.fn(), vi.fn()],
}));

vi.mock('./EntityNode', () => ({
  EntityNode: () => <div>EntityNode</div>,
}));

vi.mock('./EntityEdge', () => ({
  EntityEdge: () => <div>EntityEdge</div>,
}));

vi.mock('@/lib/utils/entityGraph', () => ({
  updateNodeStates: (nodes: EntityGraphNode[]) => nodes,
  getEntityTypeColor: () => '#3b82f6',
  isLargeGraph: (count: number) => count > 100,
  applyDagreLayout: (nodes: EntityGraphNode[]) => nodes,
}));

const createMockNode = (id: string, overrides = {}): EntityGraphNode => ({
  id,
  type: 'entity',
  position: { x: 0, y: 0 },
  data: {
    id,
    canonicalName: `Entity ${id}`,
    entityType: 'PERSON',
    mentionCount: 10,
    aliases: [],
    metadata: {},
    isSelected: false,
    isConnected: false,
    isDimmed: false,
    ...overrides,
  },
});

const createMockEdge = (source: string, target: string): EntityGraphEdge => ({
  id: `${source}-${target}`,
  source,
  target,
  type: 'relationship',
  data: {
    relationshipType: 'RELATED_TO',
    confidence: 0.85,
    metadata: {},
  },
});

describe('EntitiesGraph', () => {
  const defaultProps = {
    data: {
      nodes: [createMockNode('1'), createMockNode('2')],
      edges: [createMockEdge('1', '2')],
    } as EntityGraphData,
    selectedNodeId: null,
    onNodeSelect: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders React Flow container', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });

    it('renders all entity nodes', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(screen.getByTestId('node-1')).toBeInTheDocument();
      expect(screen.getByTestId('node-2')).toBeInTheDocument();
    });

    it('renders controls', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(screen.getByTestId('controls')).toBeInTheDocument();
    });

    it('renders minimap', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(screen.getByTestId('minimap')).toBeInTheDocument();
    });

    it('renders background', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(screen.getByTestId('background')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no entities', () => {
      render(
        <EntitiesGraph
          {...defaultProps}
          data={{ nodes: [], edges: [] }}
        />
      );
      expect(
        screen.getByText(/No entities found/i)
      ).toBeInTheDocument();
    });

    it('does not render React Flow when empty', () => {
      render(
        <EntitiesGraph
          {...defaultProps}
          data={{ nodes: [], edges: [] }}
        />
      );
      expect(screen.queryByTestId('react-flow')).not.toBeInTheDocument();
    });
  });

  describe('node interaction', () => {
    it('calls onNodeSelect when node is clicked', () => {
      const onNodeSelect = vi.fn();
      render(<EntitiesGraph {...defaultProps} onNodeSelect={onNodeSelect} />);

      fireEvent.click(screen.getByTestId('node-1'));

      expect(onNodeSelect).toHaveBeenCalledWith('1');
    });

    it('deselects when clicking same node', () => {
      const onNodeSelect = vi.fn();
      render(
        <EntitiesGraph
          {...defaultProps}
          selectedNodeId="1"
          onNodeSelect={onNodeSelect}
        />
      );

      fireEvent.click(screen.getByTestId('node-1'));

      expect(onNodeSelect).toHaveBeenCalledWith(null);
    });

    it('calls onNodeSelect with null when pane is clicked', () => {
      const onNodeSelect = vi.fn();
      render(
        <EntitiesGraph
          {...defaultProps}
          selectedNodeId="1"
          onNodeSelect={onNodeSelect}
        />
      );

      fireEvent.click(screen.getByTestId('react-flow'));

      expect(onNodeSelect).toHaveBeenCalledWith(null);
    });
  });

  describe('accessibility', () => {
    it('has region role', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(screen.getByRole('region')).toBeInTheDocument();
    });

    it('has aria-label', () => {
      render(<EntitiesGraph {...defaultProps} />);
      expect(
        screen.getByRole('region', { name: /entity graph/i })
      ).toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const { container } = render(
        <EntitiesGraph {...defaultProps} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });
});
