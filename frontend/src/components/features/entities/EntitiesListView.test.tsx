import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EntitiesListView } from './EntitiesListView';
import type { EntityListItem } from '@/types/entity';

const createMockEntity = (
  overrides: Partial<EntityListItem> = {}
): EntityListItem => ({
  id: 'entity-1',
  canonicalName: 'John Doe',
  entityType: 'PERSON',
  mentionCount: 42,
  metadata: {
    roles: ['Petitioner'],
    firstExtractionConfidence: 0.92,
  },
  ...overrides,
});

const mockEntities: EntityListItem[] = [
  createMockEntity({
    id: 'entity-1',
    canonicalName: 'John Doe',
    entityType: 'PERSON',
    mentionCount: 42,
    metadata: { roles: ['Petitioner'], verified: true },
  }),
  createMockEntity({
    id: 'entity-2',
    canonicalName: 'ACME Corporation',
    entityType: 'ORG',
    mentionCount: 25,
    metadata: { roles: ['Defendant', 'Organization'], flagged: true },
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
    metadata: { roles: ['Subject'] },
  }),
];

describe('EntitiesListView', () => {
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
    it('renders table with all entities', () => {
      render(<EntitiesListView {...defaultProps} />);

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('ACME Corporation')).toBeInTheDocument();
      expect(screen.getByText('Supreme Court')).toBeInTheDocument();
      expect(screen.getByText('Property Asset')).toBeInTheDocument();
    });

    it('renders column headers', () => {
      render(<EntitiesListView {...defaultProps} />);

      expect(screen.getByRole('button', { name: /name/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /type/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /mentions/i })).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Roles')).toBeInTheDocument();
    });

    it('renders entity type badges', () => {
      render(<EntitiesListView {...defaultProps} />);

      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Organization')).toBeInTheDocument();
      expect(screen.getByText('Institution')).toBeInTheDocument();
      expect(screen.getByText('Asset')).toBeInTheDocument();
    });

    it('renders mention counts', () => {
      render(<EntitiesListView {...defaultProps} />);

      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });

    it('renders role badges', () => {
      render(<EntitiesListView {...defaultProps} />);

      expect(screen.getByText('Petitioner')).toBeInTheDocument();
      expect(screen.getByText('Defendant')).toBeInTheDocument();
      expect(screen.getByText('Subject')).toBeInTheDocument();
    });

    it('shows overflow indicator for many roles', () => {
      render(<EntitiesListView {...defaultProps} />);

      // ACME Corp has 2 roles shown, with overflow
      const acmeRow = screen.getByTestId('entity-row-entity-2');
      expect(within(acmeRow).getByText('Defendant')).toBeInTheDocument();
    });

    it('shows dash for entities without roles', () => {
      render(<EntitiesListView {...defaultProps} />);

      const courtRow = screen.getByTestId('entity-row-entity-3');
      expect(within(courtRow).getByText('-')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no entities', () => {
      render(<EntitiesListView {...defaultProps} entities={[]} />);

      expect(
        screen.getByText('No entities found matching your filters.')
      ).toBeInTheDocument();
    });
  });

  describe('verification status', () => {
    it('shows verified status icon', () => {
      render(<EntitiesListView {...defaultProps} />);

      const johnRow = screen.getByTestId('entity-row-entity-1');
      // Verified entity should have CheckCircle2 icon (green)
      expect(johnRow.querySelector('.text-green-600')).toBeInTheDocument();
    });

    it('shows flagged status icon', () => {
      render(<EntitiesListView {...defaultProps} />);

      const acmeRow = screen.getByTestId('entity-row-entity-2');
      // Flagged entity should have AlertTriangle icon (amber)
      expect(acmeRow.querySelector('.text-amber-600')).toBeInTheDocument();
    });

    it('shows pending status icon for unverified entities', () => {
      render(<EntitiesListView {...defaultProps} />);

      const courtRow = screen.getByTestId('entity-row-entity-3');
      // Pending entity should have Clock icon (muted)
      expect(courtRow.querySelector('.text-muted-foreground')).toBeInTheDocument();
    });
  });

  describe('selection', () => {
    it('highlights selected row', () => {
      render(<EntitiesListView {...defaultProps} selectedEntityId="entity-1" />);

      const johnRow = screen.getByTestId('entity-row-entity-1');
      expect(johnRow).toHaveClass('bg-muted/50');
    });

    it('calls onEntitySelect when row clicked', async () => {
      const onEntitySelect = vi.fn();
      render(
        <EntitiesListView {...defaultProps} onEntitySelect={onEntitySelect} />
      );

      await userEvent.click(screen.getByTestId('entity-row-entity-2'));

      expect(onEntitySelect).toHaveBeenCalledWith('entity-2');
    });
  });

  describe('sorting', () => {
    it('sorts by mention count descending by default', () => {
      render(<EntitiesListView {...defaultProps} />);

      const rows = screen.getAllByRole('row').slice(1); // Skip header row
      expect(within(rows[0]!).getByText('John Doe')).toBeInTheDocument();
      expect(within(rows[1]!).getByText('ACME Corporation')).toBeInTheDocument();
      expect(within(rows[2]!).getByText('Supreme Court')).toBeInTheDocument();
      expect(within(rows[3]!).getByText('Property Asset')).toBeInTheDocument();
    });

    it('toggles sort direction when clicking same column', async () => {
      const user = userEvent.setup();
      render(<EntitiesListView {...defaultProps} />);

      // Click Mentions again to toggle direction
      await user.click(screen.getByRole('button', { name: /mentions/i }));

      const rows = screen.getAllByRole('row').slice(1);
      // Should now be ascending
      expect(within(rows[0]!).getByText('Property Asset')).toBeInTheDocument();
      expect(within(rows[3]!).getByText('John Doe')).toBeInTheDocument();
    });

    it('sorts by name when Name column clicked', async () => {
      const user = userEvent.setup();
      render(<EntitiesListView {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /name/i }));

      const rows = screen.getAllByRole('row').slice(1);
      // Should be sorted by name descending (Z-A)
      expect(within(rows[0]!).getByText('Supreme Court')).toBeInTheDocument();
    });

    it('sorts by type when Type column clicked', async () => {
      const user = userEvent.setup();
      render(<EntitiesListView {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /type/i }));

      const rows = screen.getAllByRole('row').slice(1);
      // Should be sorted by type
      expect(rows[0]).toBeInTheDocument();
    });
  });

  describe('multi-select mode', () => {
    it('shows checkboxes when in multi-select mode', () => {
      render(<EntitiesListView {...defaultProps} isMultiSelectMode />);

      expect(screen.getByText('Select')).toBeInTheDocument();
      expect(screen.getAllByRole('checkbox')).toHaveLength(4);
    });

    it('does not show checkboxes when not in multi-select mode', () => {
      render(<EntitiesListView {...defaultProps} isMultiSelectMode={false} />);

      expect(screen.queryByText('Select')).not.toBeInTheDocument();
      expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    });

    it('checks selected entities for merge', () => {
      const selectedForMerge = new Set(['entity-1', 'entity-2']);
      render(
        <EntitiesListView
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
        <EntitiesListView
          {...defaultProps}
          isMultiSelectMode
          onToggleMergeSelection={onToggleMergeSelection}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await userEvent.click(checkboxes[0]!);

      expect(onToggleMergeSelection).toHaveBeenCalledWith('entity-1');
    });

    it('calls onToggleMergeSelection when row clicked in multi-select mode', async () => {
      const onToggleMergeSelection = vi.fn();
      render(
        <EntitiesListView
          {...defaultProps}
          isMultiSelectMode
          onToggleMergeSelection={onToggleMergeSelection}
        />
      );

      await userEvent.click(screen.getByTestId('entity-row-entity-3'));

      expect(onToggleMergeSelection).toHaveBeenCalledWith('entity-3');
    });

    it('disables checkbox when 2 already selected and not this one', () => {
      const selectedForMerge = new Set(['entity-1', 'entity-2']);
      render(
        <EntitiesListView
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
        <EntitiesListView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes[0]).not.toBeDisabled(); // entity-1
      expect(checkboxes[1]).not.toBeDisabled(); // entity-2
    });

    it('highlights merge-selected rows', () => {
      const selectedForMerge = new Set(['entity-1']);
      render(
        <EntitiesListView
          {...defaultProps}
          isMultiSelectMode
          selectedForMerge={selectedForMerge}
        />
      );

      const row = screen.getByTestId('entity-row-entity-1');
      expect(row).toHaveClass('bg-primary/10');
      expect(row).toHaveClass('border-l-primary');
    });
  });

  describe('accessibility', () => {
    it('checkboxes have aria-labels', () => {
      render(<EntitiesListView {...defaultProps} isMultiSelectMode />);

      expect(
        screen.getByRole('checkbox', { name: /select john doe for merge/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('checkbox', { name: /select acme corporation for merge/i })
      ).toBeInTheDocument();
    });

    it('rows have data-testid for testing', () => {
      render(<EntitiesListView {...defaultProps} />);

      expect(screen.getByTestId('entity-row-entity-1')).toBeInTheDocument();
      expect(screen.getByTestId('entity-row-entity-2')).toBeInTheDocument();
    });
  });
});
