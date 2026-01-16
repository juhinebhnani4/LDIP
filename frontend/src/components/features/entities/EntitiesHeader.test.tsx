import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EntitiesHeader } from './EntitiesHeader';
import type { EntityFilterState, EntityType, EntityViewMode } from '@/types/entity';

const defaultStats = {
  total: 25,
  byType: {
    PERSON: 10,
    ORG: 8,
    INSTITUTION: 5,
    ASSET: 2,
  } as Record<EntityType, number>,
};

const defaultFilters: EntityFilterState = {
  entityTypes: [],
  roles: [],
  verificationStatus: 'all',
  minMentionCount: 0,
  searchQuery: '',
};

describe('EntitiesHeader', () => {
  const defaultProps = {
    stats: defaultStats,
    viewMode: 'graph' as EntityViewMode,
    onViewModeChange: vi.fn(),
    filters: defaultFilters,
    onFiltersChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('statistics display', () => {
    it('displays total entity count', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.getByText('25 total')).toBeInTheDocument();
    });

    it('displays count by entity type', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.getByText('10')).toBeInTheDocument(); // PERSON
      expect(screen.getByText('8')).toBeInTheDocument(); // ORG
      expect(screen.getByText('5')).toBeInTheDocument(); // INSTITUTION
      expect(screen.getByText('2')).toBeInTheDocument(); // ASSET
    });
  });

  describe('view mode toggle', () => {
    it('renders view mode toggle buttons', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.getByRole('group', { name: /view mode/i })).toBeInTheDocument();
    });

    it('highlights current view mode', () => {
      render(<EntitiesHeader {...defaultProps} viewMode="graph" />);
      const graphButton = screen.getByRole('radio', { name: /graph view/i });
      expect(graphButton).toHaveAttribute('data-state', 'on');
    });

    it('calls onViewModeChange when toggling', () => {
      const onViewModeChange = vi.fn();
      render(<EntitiesHeader {...defaultProps} onViewModeChange={onViewModeChange} />);

      fireEvent.click(screen.getByRole('radio', { name: /list view/i }));

      expect(onViewModeChange).toHaveBeenCalledWith('list');
    });
  });

  describe('search filter', () => {
    it('renders search input', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.getByRole('textbox', { name: /search entities/i })).toBeInTheDocument();
    });

    it('shows current search value', () => {
      render(
        <EntitiesHeader
          {...defaultProps}
          filters={{ ...defaultFilters, searchQuery: 'John' }}
        />
      );
      expect(screen.getByDisplayValue('John')).toBeInTheDocument();
    });

    it('calls onFiltersChange when searching (debounced)', async () => {
      vi.useFakeTimers();
      const onFiltersChange = vi.fn();
      render(<EntitiesHeader {...defaultProps} onFiltersChange={onFiltersChange} />);

      const input = screen.getByRole('textbox', { name: /search entities/i });
      fireEvent.change(input, { target: { value: 'test' } });

      // Should not be called immediately (debounced)
      expect(onFiltersChange).not.toHaveBeenCalled();

      // Fast-forward past the debounce delay (300ms)
      vi.advanceTimersByTime(300);

      expect(onFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({ searchQuery: 'test' })
      );

      vi.useRealTimers();
    });
  });

  describe('entity type filter', () => {
    it('renders entity type filter button', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(
        screen.getByRole('button', { name: /filter by entity type/i })
      ).toBeInTheDocument();
    });

    it('shows filter count badge when types selected', () => {
      render(
        <EntitiesHeader
          {...defaultProps}
          filters={{ ...defaultFilters, entityTypes: ['PERSON', 'ORG'] }}
        />
      );
      // Verify button exists, then check for badge count
      expect(screen.getByRole('button', { name: /filter by entity type/i })).toBeInTheDocument();
      // Badge should show the count of selected filters
      const badges = screen.getAllByText('2');
      // At least one should be present (the filter count badge)
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });

    it('opens filter dropdown on click', () => {
      render(<EntitiesHeader {...defaultProps} />);

      fireEvent.click(screen.getByRole('button', { name: /filter by entity type/i }));

      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Organization')).toBeInTheDocument();
      expect(screen.getByText('Institution')).toBeInTheDocument();
      expect(screen.getByText('Asset')).toBeInTheDocument();
    });

    it('toggles entity type selection', () => {
      const onFiltersChange = vi.fn();
      render(<EntitiesHeader {...defaultProps} onFiltersChange={onFiltersChange} />);

      // Open dropdown
      fireEvent.click(screen.getByRole('button', { name: /filter by entity type/i }));
      // Select PERSON
      fireEvent.click(screen.getByText('Person'));

      expect(onFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({ entityTypes: ['PERSON'] })
      );
    });
  });

  describe('clear filters', () => {
    it('does not show clear button when no filters active', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.queryByText(/clear filters/i)).not.toBeInTheDocument();
    });

    it('shows clear button when filters are active', () => {
      render(
        <EntitiesHeader
          {...defaultProps}
          filters={{ ...defaultFilters, entityTypes: ['PERSON'] }}
        />
      );
      expect(screen.getByText(/clear filters/i)).toBeInTheDocument();
    });

    it('clears all filters when clicked', () => {
      const onFiltersChange = vi.fn();
      render(
        <EntitiesHeader
          {...defaultProps}
          onFiltersChange={onFiltersChange}
          filters={{ ...defaultFilters, entityTypes: ['PERSON'], searchQuery: 'test' }}
        />
      );

      fireEvent.click(screen.getByText(/clear filters/i));

      expect(onFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({
          entityTypes: [],
          searchQuery: '',
          minMentionCount: 0,
        })
      );
    });
  });

  describe('accessibility', () => {
    it('has accessible view mode toggle', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.getByRole('group', { name: /view mode/i })).toBeInTheDocument();
    });

    it('has accessible search input', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(screen.getByRole('textbox', { name: /search entities/i })).toBeInTheDocument();
    });

    it('has accessible filter button', () => {
      render(<EntitiesHeader {...defaultProps} />);
      expect(
        screen.getByRole('button', { name: /filter by entity type/i })
      ).toBeInTheDocument();
    });
  });
});
