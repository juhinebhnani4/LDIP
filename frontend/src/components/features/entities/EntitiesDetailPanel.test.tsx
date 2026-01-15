import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EntitiesDetailPanel } from './EntitiesDetailPanel';
import type { EntityWithRelations } from '@/types/entity';

const createMockEntity = (
  overrides: Partial<EntityWithRelations> = {}
): EntityWithRelations => ({
  id: 'entity-1',
  matterId: 'matter-1',
  canonicalName: 'John Doe',
  entityType: 'PERSON',
  mentionCount: 42,
  aliases: ['J. Doe', 'Johnny'],
  metadata: {
    roles: ['Petitioner'],
    firstExtractionConfidence: 0.92,
  },
  relationships: [
    {
      id: 'rel-1',
      matterId: 'matter-1',
      sourceEntityId: 'entity-1',
      targetEntityId: 'entity-2',
      relationshipType: 'RELATED_TO',
      confidence: 0.85,
      metadata: {},
      createdAt: '2026-01-15T00:00:00Z',
      targetEntityName: 'ACME Corp',
    },
  ],
  recentMentions: [
    {
      id: 'mention-1',
      entityId: 'entity-1',
      documentId: 'doc-1',
      chunkId: null,
      pageNumber: 5,
      bboxIds: [],
      mentionText: 'John Doe filed the petition on...',
      context: null,
      confidence: 0.95,
      createdAt: '2026-01-15T00:00:00Z',
      documentName: 'Petition.pdf',
    },
  ],
  createdAt: '2026-01-15T00:00:00Z',
  updatedAt: '2026-01-15T00:00:00Z',
  ...overrides,
});

describe('EntitiesDetailPanel', () => {
  const defaultProps = {
    entity: createMockEntity(),
    onClose: vi.fn(),
    onEntitySelect: vi.fn(),
    onFocusInGraph: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders entity name', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('renders entity type badge', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('renders role badge when available', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText('Petitioner')).toBeInTheDocument();
    });

    it('renders confidence score', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText(/confidence: 92%/i)).toBeInTheDocument();
    });

    it('renders aliases', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText('J. Doe')).toBeInTheDocument();
      expect(screen.getByText('Johnny')).toBeInTheDocument();
    });

    it('renders relationships section', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText(/relationships/i)).toBeInTheDocument();
      expect(screen.getByText('ACME Corp')).toBeInTheDocument();
    });

    it('renders recent mentions', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText(/recent mentions/i)).toBeInTheDocument();
      expect(screen.getByText(/john doe filed the petition/i)).toBeInTheDocument();
    });

    it('renders focus in graph button', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByRole('button', { name: /focus in graph/i })).toBeInTheDocument();
    });
  });

  describe('empty states', () => {
    it('returns null when no entity and not loading', () => {
      const { container } = render(
        <EntitiesDetailPanel {...defaultProps} entity={null} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('shows loading state', () => {
      render(<EntitiesDetailPanel {...defaultProps} entity={null} isLoading />);
      expect(screen.getByRole('complementary')).toBeInTheDocument();
    });

    it('shows error state', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={null}
          error="Failed to load entity"
        />
      );
      expect(screen.getByText('Failed to load entity')).toBeInTheDocument();
    });

    it('shows no aliases message when empty', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ aliases: [] })}
        />
      );
      expect(screen.queryByText('Aliases')).not.toBeInTheDocument();
    });

    it('shows no relationships message when empty', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ relationships: [] })}
        />
      );
      expect(screen.getByText(/no relationships found/i)).toBeInTheDocument();
    });

    it('shows no mentions message when empty', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ recentMentions: [] })}
        />
      );
      expect(screen.getByText(/no mentions available/i)).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onClose when close button clicked', () => {
      const onClose = vi.fn();
      render(<EntitiesDetailPanel {...defaultProps} onClose={onClose} />);

      fireEvent.click(screen.getByRole('button', { name: /close panel/i }));

      expect(onClose).toHaveBeenCalled();
    });

    it('calls onEntitySelect when relationship clicked', () => {
      const onEntitySelect = vi.fn();
      render(
        <EntitiesDetailPanel {...defaultProps} onEntitySelect={onEntitySelect} />
      );

      fireEvent.click(screen.getByText('ACME Corp'));

      expect(onEntitySelect).toHaveBeenCalledWith('entity-2');
    });

    it('calls onFocusInGraph when focus button clicked', () => {
      const onFocusInGraph = vi.fn();
      render(
        <EntitiesDetailPanel {...defaultProps} onFocusInGraph={onFocusInGraph} />
      );

      fireEvent.click(screen.getByRole('button', { name: /focus in graph/i }));

      expect(onFocusInGraph).toHaveBeenCalled();
    });
  });

  describe('entity types', () => {
    it('shows correct icon for PERSON type', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ entityType: 'PERSON' })}
        />
      );
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('shows correct icon for ORG type', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ entityType: 'ORG' })}
        />
      );
      expect(screen.getByText('Organization')).toBeInTheDocument();
    });

    it('shows correct icon for INSTITUTION type', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ entityType: 'INSTITUTION' })}
        />
      );
      expect(screen.getByText('Institution')).toBeInTheDocument();
    });

    it('shows correct icon for ASSET type', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({ entityType: 'ASSET' })}
        />
      );
      expect(screen.getByText('Asset')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has complementary role', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByRole('complementary')).toBeInTheDocument();
    });

    it('has aria-label', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(
        screen.getByRole('complementary', { name: /entity details/i })
      ).toBeInTheDocument();
    });

    it('close button has aria-label', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(
        screen.getByRole('button', { name: /close panel/i })
      ).toBeInTheDocument();
    });
  });
});
