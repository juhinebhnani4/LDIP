import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EntitiesContent } from './EntitiesContent';
import * as useEntitiesHook from '@/hooks/useEntities';
import type { EntityListItem, EntityWithRelations } from '@/types/entity';

// Mock the hooks
vi.mock('@/hooks/useEntities', () => ({
  useEntities: vi.fn(),
  useEntityDetail: vi.fn(),
  useEntityRelationships: vi.fn(),
  useEntityStats: vi.fn(),
}));

// Mock child components
vi.mock('./EntitiesHeader', () => ({
  EntitiesHeader: ({ onViewModeChange, onFiltersChange }: {
    onViewModeChange: (mode: string) => void;
    onFiltersChange: (filters: unknown) => void;
  }) => (
    <div data-testid="entities-header">
      <button onClick={() => onViewModeChange('list')}>Switch to List</button>
      <button onClick={() => onFiltersChange({ entityTypes: ['PERSON'], searchQuery: '', roles: [], verificationStatus: 'all', minMentionCount: 0 })}>
        Filter PERSON
      </button>
    </div>
  ),
}));

vi.mock('./EntitiesGraph', () => ({
  EntitiesGraph: ({ data, selectedNodeId, onNodeSelect }: {
    data: { nodes: Array<{ id: string }>; edges: unknown[] };
    selectedNodeId: string | null;
    onNodeSelect: (id: string | null) => void;
  }) => (
    <div data-testid="entities-graph">
      {data.nodes.map((node) => (
        <button
          key={node.id}
          data-testid={`node-${node.id}`}
          onClick={() => onNodeSelect(node.id)}
          data-selected={selectedNodeId === node.id}
        >
          Node {node.id}
        </button>
      ))}
    </div>
  ),
}));

vi.mock('./EntitiesDetailPanel', () => ({
  EntitiesDetailPanel: ({ entity, onClose }: {
    entity: EntityWithRelations | null;
    onClose: () => void;
  }) => (
    <div data-testid="detail-panel">
      {entity?.canonicalName}
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

const createMockEntity = (id: string): EntityListItem => ({
  id,
  canonicalName: `Entity ${id}`,
  entityType: 'PERSON',
  mentionCount: 10,
  metadata: {},
});

const createMockEntityWithRelations = (id: string): EntityWithRelations => ({
  id,
  matterId: 'matter-1',
  canonicalName: `Entity ${id}`,
  entityType: 'PERSON',
  mentionCount: 10,
  aliases: [],
  metadata: {},
  relationships: [],
  recentMentions: [],
  createdAt: '2026-01-15',
  updatedAt: '2026-01-15',
});

describe('EntitiesContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    vi.mocked(useEntitiesHook.useEntities).mockReturnValue({
      entities: [createMockEntity('1'), createMockEntity('2')],
      total: 2,
      isLoading: false,
      isValidating: false,
      error: null,
      mutate: vi.fn(),
    });

    vi.mocked(useEntitiesHook.useEntityRelationships).mockReturnValue({
      edges: [],
      isLoading: false,
      error: null,
    });

    vi.mocked(useEntitiesHook.useEntityDetail).mockReturnValue({
      entity: null,
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });

    vi.mocked(useEntitiesHook.useEntityStats).mockReturnValue({
      total: 2,
      byType: { PERSON: 2, ORG: 0, INSTITUTION: 0, ASSET: 0 },
    });
  });

  describe('rendering', () => {
    it('renders header component', () => {
      render(<EntitiesContent matterId="matter-1" />);
      expect(screen.getByTestId('entities-header')).toBeInTheDocument();
    });

    it('renders graph view by default', () => {
      render(<EntitiesContent matterId="matter-1" />);
      expect(screen.getByTestId('entities-graph')).toBeInTheDocument();
    });

    it('renders entity nodes in graph', () => {
      render(<EntitiesContent matterId="matter-1" />);
      expect(screen.getByTestId('node-1')).toBeInTheDocument();
      expect(screen.getByTestId('node-2')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when entities loading', () => {
      vi.mocked(useEntitiesHook.useEntities).mockReturnValue({
        entities: [],
        total: 0,
        isLoading: true,
        isValidating: false,
        error: null,
        mutate: vi.fn(),
      });

      render(<EntitiesContent matterId="matter-1" />);
      expect(screen.queryByTestId('entities-graph')).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message on fetch error', () => {
      vi.mocked(useEntitiesHook.useEntities).mockReturnValue({
        entities: [],
        total: 0,
        isLoading: false,
        isValidating: false,
        error: new Error('Failed'),
        mutate: vi.fn(),
      });

      render(<EntitiesContent matterId="matter-1" />);
      expect(screen.getByText(/failed to load entities/i)).toBeInTheDocument();
    });
  });

  describe('view mode switching', () => {
    it('switches to list view', () => {
      render(<EntitiesContent matterId="matter-1" />);

      fireEvent.click(screen.getByText('Switch to List'));

      expect(screen.getByText(/list view coming/i)).toBeInTheDocument();
    });
  });

  describe('node selection', () => {
    it('opens detail panel when node selected', async () => {
      vi.mocked(useEntitiesHook.useEntityDetail).mockReturnValue({
        entity: createMockEntityWithRelations('1'),
        isLoading: false,
        error: null,
        mutate: vi.fn(),
      });

      render(<EntitiesContent matterId="matter-1" />);

      fireEvent.click(screen.getByTestId('node-1'));

      await waitFor(() => {
        expect(screen.getByTestId('detail-panel')).toBeInTheDocument();
      });
    });

    it('closes detail panel when close button clicked', async () => {
      vi.mocked(useEntitiesHook.useEntityDetail).mockReturnValue({
        entity: createMockEntityWithRelations('1'),
        isLoading: false,
        error: null,
        mutate: vi.fn(),
      });

      render(<EntitiesContent matterId="matter-1" />);

      // Select node
      fireEvent.click(screen.getByTestId('node-1'));

      await waitFor(() => {
        expect(screen.getByTestId('detail-panel')).toBeInTheDocument();
      });

      // Close panel
      fireEvent.click(screen.getByText('Close'));

      await waitFor(() => {
        expect(screen.queryByTestId('detail-panel')).not.toBeInTheDocument();
      });
    });
  });

  describe('filtering', () => {
    it('applies entity type filter', () => {
      render(<EntitiesContent matterId="matter-1" />);

      fireEvent.click(screen.getByText('Filter PERSON'));

      // Filter is applied - graph should re-render with filtered data
      expect(screen.getByTestId('entities-graph')).toBeInTheDocument();
    });
  });
});
