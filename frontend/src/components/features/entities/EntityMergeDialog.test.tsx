import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EntityMergeDialog } from './EntityMergeDialog';
import type { EntityListItem } from '@/types/entity';

const createMockEntity = (
  overrides: Partial<EntityListItem> = {}
): EntityListItem => ({
  id: 'entity-1',
  matterId: 'matter-1',
  canonicalName: 'John Doe',
  entityType: 'PERSON',
  mentionCount: 42,
  metadata: {
    roles: ['Petitioner'],
    aliasesFound: ['J. Doe', 'Johnny'],
    firstExtractionConfidence: 0.92,
  },
  createdAt: '2026-01-15T00:00:00Z',
  updatedAt: '2026-01-15T00:00:00Z',
  ...overrides,
});

const mockSourceEntity = createMockEntity({
  id: 'entity-1',
  canonicalName: 'John Doe',
  mentionCount: 42,
});

const mockTargetEntity = createMockEntity({
  id: 'entity-2',
  canonicalName: 'J. Doe',
  mentionCount: 5,
  metadata: {
    roles: ['Petitioner'],
    aliasesFound: [],
    firstExtractionConfidence: 0.75,
  },
});

describe('EntityMergeDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    sourceEntity: mockSourceEntity,
    targetEntity: mockTargetEntity,
    onConfirm: vi.fn().mockResolvedValue(undefined),
    isLoading: false,
    error: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders dialog when open', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render dialog when closed', () => {
      render(<EntityMergeDialog {...defaultProps} open={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders dialog title', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByText('Merge Entities')).toBeInTheDocument();
    });

    it('renders dialog description', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(
        screen.getByText(/combine two entities into one/i)
      ).toBeInTheDocument();
    });

    it('renders both entity names', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('J. Doe')).toBeInTheDocument();
    });

    it('renders mention counts for both entities', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByText('42 mentions')).toBeInTheDocument();
      expect(screen.getByText('5 mentions')).toBeInTheDocument();
    });

    it('renders "Will be deleted" and "Will be kept" labels', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByText('Will be deleted')).toBeInTheDocument();
      expect(screen.getByText('Will be kept')).toBeInTheDocument();
    });

    it('renders reason textarea', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(
        screen.getByRole('textbox', { name: /reason/i })
      ).toBeInTheDocument();
    });

    it('renders Cancel and Confirm buttons', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /confirm merge/i })
      ).toBeInTheDocument();
    });
  });

  describe('type mismatch warning', () => {
    it('shows warning when entity types differ', () => {
      const orgEntity = createMockEntity({
        id: 'entity-3',
        entityType: 'ORG',
        canonicalName: 'ACME Corp',
      });

      render(
        <EntityMergeDialog
          {...defaultProps}
          sourceEntity={mockSourceEntity}
          targetEntity={orgEntity}
        />
      );

      expect(screen.getByText('Type Mismatch')).toBeInTheDocument();
      expect(
        screen.getByText(/different types.*Person.*Organization/i)
      ).toBeInTheDocument();
    });

    it('does not show warning when entity types match', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.queryByText('Type Mismatch')).not.toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('displays error message when error prop is set', () => {
      render(
        <EntityMergeDialog {...defaultProps} error="Merge failed: server error" />
      );

      expect(screen.getByText('Merge Failed')).toBeInTheDocument();
      expect(screen.getByText('Merge failed: server error')).toBeInTheDocument();
    });

    it('does not show error alert when error is null', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.queryByText('Merge Failed')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when isLoading is true', () => {
      render(<EntityMergeDialog {...defaultProps} isLoading />);
      expect(screen.getByText('Merging...')).toBeInTheDocument();
    });

    it('disables Cancel button when loading', () => {
      render(<EntityMergeDialog {...defaultProps} isLoading />);
      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    });

    it('disables Confirm button when loading', () => {
      render(<EntityMergeDialog {...defaultProps} isLoading />);
      expect(screen.getByRole('button', { name: /merging/i })).toBeDisabled();
    });

    it('disables reason textarea when loading', () => {
      render(<EntityMergeDialog {...defaultProps} isLoading />);
      expect(screen.getByRole('textbox', { name: /reason/i })).toBeDisabled();
    });
  });

  describe('interactions', () => {
    it('calls onOpenChange with false when Cancel clicked', async () => {
      const onOpenChange = vi.fn();
      render(<EntityMergeDialog {...defaultProps} onOpenChange={onOpenChange} />);

      await userEvent.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('calls onConfirm with correct parameters on Confirm', async () => {
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      render(<EntityMergeDialog {...defaultProps} onConfirm={onConfirm} />);

      await userEvent.click(screen.getByRole('button', { name: /confirm merge/i }));

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalled();
      });

      // Entity with fewer mentions should be source (deleted)
      const [sourceId, targetId] = onConfirm.mock.calls[0];
      expect(sourceId).toBe('entity-2'); // J. Doe (5 mentions) deleted
      expect(targetId).toBe('entity-1'); // John Doe (42 mentions) kept
    });

    it('includes reason in onConfirm call', async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      render(<EntityMergeDialog {...defaultProps} onConfirm={onConfirm} />);

      await user.type(
        screen.getByRole('textbox', { name: /reason/i }),
        'Same person with nickname'
      );
      await user.click(screen.getByRole('button', { name: /confirm merge/i }));

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalledWith(
          expect.any(String),
          expect.any(String),
          'Same person with nickname'
        );
      });
    });

    it('allows switching which entity to keep', async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      render(<EntityMergeDialog {...defaultProps} onConfirm={onConfirm} />);

      // Click on the source entity card to select it as the one to keep
      const sourceCard = screen.getByText('Will be deleted').closest('[role="button"]');
      if (sourceCard) {
        await user.click(sourceCard);
      }

      await user.click(screen.getByRole('button', { name: /confirm merge/i }));

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalled();
      });
    });
  });

  describe('entity selection defaults', () => {
    it('defaults to keeping entity with more mentions', () => {
      render(<EntityMergeDialog {...defaultProps} />);

      // John Doe (42 mentions) should be marked as "Will be kept"
      const keptCard = screen.getByText('Will be kept').closest('[role="button"]');
      expect(keptCard).toHaveTextContent('John Doe');

      // J. Doe (5 mentions) should be marked as "Will be deleted"
      const deletedCard = screen.getByText('Will be deleted').closest('[role="button"]');
      expect(deletedCard).toHaveTextContent('J. Doe');
    });
  });

  describe('null entities', () => {
    it('shows placeholder when source entity is null', () => {
      render(
        <EntityMergeDialog
          {...defaultProps}
          sourceEntity={null}
        />
      );

      expect(screen.getByText('Select an entity')).toBeInTheDocument();
    });

    it('shows placeholder when target entity is null', () => {
      render(
        <EntityMergeDialog
          {...defaultProps}
          targetEntity={null}
        />
      );

      expect(screen.getByText('Select an entity')).toBeInTheDocument();
    });

    it('disables Confirm button when entities are null', () => {
      render(
        <EntityMergeDialog
          {...defaultProps}
          sourceEntity={null}
          targetEntity={null}
        />
      );

      expect(
        screen.getByRole('button', { name: /confirm merge/i })
      ).toBeDisabled();
    });
  });

  describe('accessibility', () => {
    it('dialog has proper role', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('entity cards are keyboard accessible', () => {
      render(<EntityMergeDialog {...defaultProps} />);

      const cards = screen.getAllByRole('button');
      // Filter to entity cards (not Cancel/Confirm buttons)
      const entityCards = cards.filter(
        (card) =>
          card.getAttribute('aria-label')?.includes('Select') ||
          card.getAttribute('aria-label')?.includes('entity')
      );

      entityCards.forEach((card) => {
        expect(card).toHaveAttribute('tabIndex', '0');
      });
    });

    it('cards respond to keyboard Enter', () => {
      render(<EntityMergeDialog {...defaultProps} />);

      const sourceCard = screen.getByText('Will be deleted').closest('[role="button"]');
      if (sourceCard) {
        fireEvent.keyDown(sourceCard, { key: 'Enter' });
        // Card selection should toggle
      }
    });

    it('cards respond to keyboard Space', () => {
      render(<EntityMergeDialog {...defaultProps} />);

      const sourceCard = screen.getByText('Will be deleted').closest('[role="button"]');
      if (sourceCard) {
        fireEvent.keyDown(sourceCard, { key: ' ' });
        // Card selection should toggle
      }
    });
  });

  describe('aliases display', () => {
    it('displays entity aliases', () => {
      render(<EntityMergeDialog {...defaultProps} />);
      expect(screen.getByText(/J\. Doe, Johnny/)).toBeInTheDocument();
    });

    it('truncates long alias lists', () => {
      const manyAliases = createMockEntity({
        metadata: {
          aliasesFound: ['Alias 1', 'Alias 2', 'Alias 3', 'Alias 4', 'Alias 5'],
        },
      });

      render(
        <EntityMergeDialog
          {...defaultProps}
          sourceEntity={manyAliases}
        />
      );

      expect(screen.getByText(/\+2 more/)).toBeInTheDocument();
    });
  });
});
