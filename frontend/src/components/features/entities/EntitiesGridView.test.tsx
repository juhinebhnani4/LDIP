import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EntitiesGridView } from './EntitiesGridView';
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
    firstExtractionConfidence: 0.92,
  },
  createdAt: '2026-01-15T00:00:00Z',
  updatedAt: '2026-01-15T00:00:00Z',
  ...overrides,
});

const mockEntities: EntityListItem[] = [
  createMockEntity({
    id: 'entity-1',
    canonicalName: 'John Doe',
    entityType: 'PERSON',
    mentionCount: 42,
    metadata: {
      roles: ['Petitioner'],
      aliasesFound: ['J. Doe', 'Johnny'],
      firstExtractionConfidence: 0.92,
      verified: true,
    },
  }),
  createMockEntity({
    id: 'entity-2',
    canonicalName: 'ACME Corporation',
    entityType: 'ORG',
    mentionCount: 25,
    metadata: {
      roles: ['Defendant', 'Company'],
      aliasesFound: [],
      flagged: true,
    },
  }),
  createMockEntity({
    id: 'entity-3',
    canonicalName: 'Supreme Court',
    entityType: 'INSTITUTION',
    mentionCount: 15,
    metadata: { roles: [] },
  }),
  createMockEntity({
    id: 'entity-4',
    canonicalName: 'Property Asset',
    entityType: 'ASSET',
    mentionCount: 8,
    metadata: {
      roles: ['Subject'],
      aliasesFound: ['Main Asset', 'Subject Property', 'Real Estate', 'Land'],
    },
  }),
];

describe('EntitiesGridView', () => {
  const defaultProps = {
    entities: mockEntities,
    selectedEntityId: null,
    onEntitySelect: vi.fn(),
    isMultiSelectMode: false,
    selectedForMerge: new Set<string>(),
    onToggleMergeSelection: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders all entity cards', () => {
      render(<EntitiesGridView {...defaultProps} />);

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('ACME Corporation')).toBeInTheDocument();
      expect(screen.getByText('Supreme Court')).toBeInTheDocument();
      expect(screen.getByText('Property Asset')).toBeInTheDocument();
    });

    it('renders entity type badges', () => {
      render(<EntitiesGridView {...defaultProps} />);

      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Organization')).toBeInTheDocument();
      expect(screen.getByText('Institution')).toBeInTheDocument();
      expect(screen.getByText('Asset')).toBeInTheDocument();
    });

    it('renders mention counts', () => {
      render(<EntitiesGridView {...defaultProps} />);

      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });

    it('renders roles section', () => {
      render(<EntitiesGridView {...defaultProps} />);

      // Multiple "Roles" labels
      expect(screen.getAllByText('Roles')).toHaveLength(3); // 3 entities with roles

      expect(screen.getByText('Petitioner')).toBeInTheDocument();
      expect(screen.getByText('Defendant')).toBeInTheDocument();
      expect(screen.getByText('Subject')).toBeInTheDocument();
    });

    it('renders aliases section when present', () => {
      render(<EntitiesGridView {...defaultProps} />);

      expect(screen.getAllByText('Aliases')).toHaveLength(2); // 2 entities with aliases
      expect(screen.getByText(/J\. Doe, Johnny/)).toBeInTheDocument();
    });

    it('shows overflow for many aliases', () => {
      render(<EntitiesGridView {...defaultProps} />);

      // Property Asset has 4 aliases, should show +2 more
      expect(screen.getByText(/\+2 more/)).toBeInTheDocument();
    });

    it('shows overflow for many roles', () => {
      render(<EntitiesGridView {...defaultProps} />);

      // ACME has 2 roles - should show both since limit is 2
      const acmeCard = screen.getByTestId('entity-card-entity-2');
      expect(within(acmeCard).getByText('Defendant')).toBeInTheDocument();
    });

    it('does not render roles section when no roles', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const courtCard = screen.getByTestId('entity-card-entity-3');
      expect(within(courtCard).queryByText('Roles')).not.toBeInTheDocument();
    });

    it('does not render aliases section when no aliases', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const acmeCard = screen.getByTestId('entity-card-entity-2');
      expect(within(acmeCard).queryByText('Aliases')).not.toBeInTheDocument();
    });

    it('renders confidence when available', () => {
      render(<EntitiesGridView {...defaultProps} />);

      expect(screen.getByText('92%')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no entities', () => {
      render(<EntitiesGridView {...defaultProps} entities={[]} />);

      expect(
        screen.getByText('No entities found matching your filters.')
      ).toBeInTheDocument();
    });
  });

  describe('verification status', () => {
    it('shows Verified badge', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const johnCard = screen.getByTestId('entity-card-entity-1');
      expect(within(johnCard).getByText('Verified')).toBeInTheDocument();
    });

    it('shows Flagged badge', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const acmeCard = screen.getByTestId('entity-card-entity-2');
      expect(within(acmeCard).getByText('Flagged')).toBeInTheDocument();
    });

    it('shows Pending badge for unverified entities', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const courtCard = screen.getByTestId('entity-card-entity-3');
      expect(within(courtCard).getByText('Pending')).toBeInTheDocument();
    });
  });

  describe('selection', () => {
    it('highlights selected card with ring', () => {
      render(<EntitiesGridView {...defaultProps} selectedEntityId="entity-1" />);

      const johnCard = screen.getByTestId('entity-card-entity-1');
      expect(johnCard).toHaveClass('ring-2', 'ring-primary');
    });

    it('calls onEntitySelect when card clicked', async () => {
      const onEntitySelect = vi.fn();
      render(
        <EntitiesGridView {...defaultProps} onEntitySelect={onEntitySelect} />
      );

      await userEvent.click(screen.getByTestId('entity-card-entity-2'));

      expect(onEntitySelect).toHaveBeenCalledWith('entity-2');
    });
  });

  describe('multi-select mode', () => {
    it('shows checkboxes when in multi-select mode', () => {
      render(<EntitiesGridView {...defaultProps} isMultiSelectMode />);

      expect(screen.getAllByRole('checkbox')).toHaveLength(4);
    });

    it('does not show checkboxes when not in multi-select mode', () => {
      render(<EntitiesGridView {...defaultProps} isMultiSelectMode={false} />);

      expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    });

    it('checks selected entities for merge', () => {
      const selectedForMerge = new Set(['entity-1', 'entity-2']);
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes[0]).toBeChecked(); // entity-1
      expect(checkboxes[1]).toBeChecked(); // entity-2
      expect(checkboxes[2]).not.toBeChecked();
      expect(checkboxes[3]).not.toBeChecked();
    });

    it('calls onToggleMergeSelection when checkbox clicked', async () => {
      const onToggleMergeSelection = vi.fn();
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          onToggleMergeSelection={onToggleMergeSelection}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await userEvent.click(checkboxes[0]);

      expect(onToggleMergeSelection).toHaveBeenCalledWith('entity-1');
    });

    it('calls onToggleMergeSelection when card clicked in multi-select mode', async () => {
      const onToggleMergeSelection = vi.fn();
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          onToggleMergeSelection={onToggleMergeSelection}
        />
      );

      await userEvent.click(screen.getByTestId('entity-card-entity-3'));

      expect(onToggleMergeSelection).toHaveBeenCalledWith('entity-3');
    });

    it('disables checkbox when 2 already selected and not this one', () => {
      const selectedForMerge = new Set(['entity-1', 'entity-2']);
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes[2]).toBeDisabled(); // entity-3 should be disabled
      expect(checkboxes[3]).toBeDisabled(); // entity-4 should be disabled
    });

    it('does not disable checkbox when already selected', () => {
      const selectedForMerge = new Set(['entity-1', 'entity-2']);
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes[0]).not.toBeDisabled(); // entity-1
      expect(checkboxes[1]).not.toBeDisabled(); // entity-2
    });

    it('highlights merge-selected cards', () => {
      const selectedForMerge = new Set(['entity-1']);
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const card = screen.getByTestId('entity-card-entity-1');
      expect(card).toHaveClass('ring-2', 'ring-primary', 'bg-primary/5');
    });

    it('shows selection indicator bar on selected cards', () => {
      const selectedForMerge = new Set(['entity-1']);
      render(
        <EntitiesGridView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const card = screen.getByTestId('entity-card-entity-1');
      const indicator = card.querySelector('.bg-primary.h-1');
      expect(indicator).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('checkboxes have aria-labels', () => {
      render(<EntitiesGridView {...defaultProps} isMultiSelectMode />);

      expect(
        screen.getByRole('checkbox', { name: /select john doe for merge/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('checkbox', { name: /select acme corporation for merge/i })
      ).toBeInTheDocument();
    });

    it('cards have data-testid for testing', () => {
      render(<EntitiesGridView {...defaultProps} />);

      expect(screen.getByTestId('entity-card-entity-1')).toBeInTheDocument();
      expect(screen.getByTestId('entity-card-entity-2')).toBeInTheDocument();
      expect(screen.getByTestId('entity-card-entity-3')).toBeInTheDocument();
      expect(screen.getByTestId('entity-card-entity-4')).toBeInTheDocument();
    });

    it('cards are clickable', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const card = screen.getByTestId('entity-card-entity-1');
      expect(card).toHaveClass('cursor-pointer');
    });
  });

  describe('responsive grid', () => {
    it('renders cards in a grid layout', () => {
      render(<EntitiesGridView {...defaultProps} />);

      const grid = document.querySelector('.grid');
      expect(grid).toBeInTheDocument();
      expect(grid).toHaveClass('grid-cols-1', 'sm:grid-cols-2', 'lg:grid-cols-3', 'xl:grid-cols-4');
    });
  });
});
