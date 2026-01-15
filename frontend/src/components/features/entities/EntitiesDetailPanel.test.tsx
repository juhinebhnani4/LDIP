import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EntitiesDetailPanel } from './EntitiesDetailPanel';
import type { EntityWithRelations } from '@/types/entity';

// Mock the useEntityMentions hook
vi.mock('@/hooks/useEntities', () => ({
  useEntityMentions: vi.fn(() => ({
    mentions: [],
    total: 0,
    isLoading: false,
    error: null,
  })),
}));

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
      bboxIds: ['bbox-1'],
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
    matterId: 'matter-1',
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

    it('renders mentions with document name and page', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText(/john doe filed the petition/i)).toBeInTheDocument();
      // Check document name and page are shown together
      expect(screen.getByText(/Petition\.pdf/)).toBeInTheDocument();
    });

    it('renders focus in graph button', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByRole('button', { name: /focus in graph/i })).toBeInTheDocument();
    });

    it('renders verification status badge', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('renders verified status when entity is verified', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({
            metadata: {
              ...createMockEntity().metadata,
              verified: true,
            },
          })}
        />
      );
      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('renders flagged status when entity is flagged', () => {
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          entity={createMockEntity({
            metadata: {
              ...createMockEntity().metadata,
              flagged: true,
            },
          })}
        />
      );
      expect(screen.getByText('Flagged')).toBeInTheDocument();
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
      expect(screen.getByText('No aliases')).toBeInTheDocument();
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
          entity={createMockEntity({ recentMentions: [], mentionCount: 0 })}
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

  describe('PDF navigation', () => {
    it('calls onViewInDocument when mention clicked', () => {
      const onViewInDocument = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onViewInDocument={onViewInDocument}
        />
      );

      fireEvent.click(screen.getByText(/john doe filed the petition/i));

      expect(onViewInDocument).toHaveBeenCalledWith({
        documentId: 'doc-1',
        pageNumber: 5,
        bboxIds: ['bbox-1'],
        entityId: 'entity-1',
      });
    });

    it('renders View button when onViewInDocument is provided', () => {
      const onViewInDocument = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onViewInDocument={onViewInDocument}
        />
      );

      expect(screen.getByRole('button', { name: /view petition\.pdf page 5/i })).toBeInTheDocument();
    });

    it('mentions are clickable when onViewInDocument is provided', () => {
      const onViewInDocument = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onViewInDocument={onViewInDocument}
        />
      );

      const mentionElement = screen.getByText(/john doe filed the petition/i).closest('div');
      expect(mentionElement).toHaveAttribute('role', 'button');
      expect(mentionElement).toHaveAttribute('tabIndex', '0');
    });

    it('mentions are not clickable when onViewInDocument is not provided', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);

      const mentionElement = screen.getByText(/john doe filed the petition/i).closest('div');
      expect(mentionElement).not.toHaveAttribute('role', 'button');
    });
  });

  describe('alias management', () => {
    it('shows Add button when onAddAlias is provided', () => {
      const onAddAlias = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onAddAlias={onAddAlias}
        />
      );

      expect(screen.getByRole('button', { name: /add alias/i })).toBeInTheDocument();
    });

    it('does not show Add button when onAddAlias is not provided', () => {
      render(<EntitiesDetailPanel {...defaultProps} />);

      expect(screen.queryByRole('button', { name: /add alias/i })).not.toBeInTheDocument();
    });

    it('opens alias input when Add button clicked', async () => {
      const user = userEvent.setup();
      const onAddAlias = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onAddAlias={onAddAlias}
        />
      );

      await user.click(screen.getByRole('button', { name: /add alias/i }));

      expect(screen.getByRole('textbox', { name: /new alias/i })).toBeInTheDocument();
    });

    it('calls onAddAlias when alias is confirmed', async () => {
      const user = userEvent.setup();
      const onAddAlias = vi.fn().mockResolvedValue(undefined);
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onAddAlias={onAddAlias}
        />
      );

      await user.click(screen.getByRole('button', { name: /add alias/i }));
      await user.type(screen.getByRole('textbox', { name: /new alias/i }), 'New Alias');
      await user.click(screen.getByRole('button', { name: /confirm add alias/i }));

      await waitFor(() => {
        expect(onAddAlias).toHaveBeenCalledWith('New Alias');
      });
    });

    it('closes alias input on cancel', async () => {
      const user = userEvent.setup();
      const onAddAlias = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onAddAlias={onAddAlias}
        />
      );

      await user.click(screen.getByRole('button', { name: /add alias/i }));
      expect(screen.getByRole('textbox', { name: /new alias/i })).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: /cancel add alias/i }));
      expect(screen.queryByRole('textbox', { name: /new alias/i })).not.toBeInTheDocument();
    });

    it('submits alias on Enter key', async () => {
      const user = userEvent.setup();
      const onAddAlias = vi.fn().mockResolvedValue(undefined);
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onAddAlias={onAddAlias}
        />
      );

      await user.click(screen.getByRole('button', { name: /add alias/i }));
      await user.type(screen.getByRole('textbox', { name: /new alias/i }), 'New Alias{enter}');

      await waitFor(() => {
        expect(onAddAlias).toHaveBeenCalledWith('New Alias');
      });
    });

    it('cancels alias input on Escape key', async () => {
      const user = userEvent.setup();
      const onAddAlias = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onAddAlias={onAddAlias}
        />
      );

      await user.click(screen.getByRole('button', { name: /add alias/i }));
      await user.type(screen.getByRole('textbox', { name: /new alias/i }), 'New Alias{escape}');

      expect(screen.queryByRole('textbox', { name: /new alias/i })).not.toBeInTheDocument();
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

    it('mention cards are keyboard accessible when clickable', () => {
      const onViewInDocument = vi.fn();
      render(
        <EntitiesDetailPanel
          {...defaultProps}
          onViewInDocument={onViewInDocument}
        />
      );

      const mentionCard = screen.getByText(/john doe filed the petition/i).closest('div');
      expect(mentionCard).toHaveAttribute('tabIndex', '0');

      // Simulate keyboard activation
      if (mentionCard) {
        fireEvent.keyDown(mentionCard, { key: 'Enter' });
        expect(onViewInDocument).toHaveBeenCalled();
      }
    });
  });
});
