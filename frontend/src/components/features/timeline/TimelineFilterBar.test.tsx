/**
 * TimelineFilterBar Tests
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineFilterBar } from './TimelineFilterBar';
import type { TimelineFilterState } from '@/types/timeline';
import { DEFAULT_TIMELINE_FILTERS } from '@/types/timeline';

// Mock entities for actor filter
const mockEntities = [
  { id: 'entity-1', name: 'John Smith' },
  { id: 'entity-2', name: 'ABC Corporation' },
  { id: 'entity-3', name: 'Jane Doe' },
];

describe('TimelineFilterBar', () => {
  const defaultProps = {
    filters: DEFAULT_TIMELINE_FILTERS,
    onFiltersChange: vi.fn(),
    entities: mockEntities,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders all filter options', () => {
      render(<TimelineFilterBar {...defaultProps} />);

      expect(screen.getByRole('button', { name: /event type/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /actors/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /date range/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /verification/i })).toBeInTheDocument();
    });

    it('renders with role="toolbar"', () => {
      render(<TimelineFilterBar {...defaultProps} />);
      expect(screen.getByRole('toolbar')).toBeInTheDocument();
    });

    it('does not show clear button when no filters applied', () => {
      render(<TimelineFilterBar {...defaultProps} />);
      expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument();
    });

    it('shows clear button with count when filters applied', () => {
      const filtersWithSelection: TimelineFilterState = {
        ...DEFAULT_TIMELINE_FILTERS,
        eventTypes: ['filing', 'order'],
      };
      render(<TimelineFilterBar {...defaultProps} filters={filtersWithSelection} />);

      expect(screen.getByRole('button', { name: /clear.*1/i })).toBeInTheDocument();
    });
  });

  describe('Event Type Filter', () => {
    it('opens event type dropdown on click', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /event type/i }));

      // Should show event type options
      expect(screen.getByText('Filing')).toBeInTheDocument();
      expect(screen.getByText('Notice')).toBeInTheDocument();
      expect(screen.getByText('Hearing')).toBeInTheDocument();
      expect(screen.getByText('Order')).toBeInTheDocument();
    });

    it('updates event type filter on selection', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      render(<TimelineFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />);

      await user.click(screen.getByRole('button', { name: /event type/i }));
      await user.click(screen.getByText('Filing'));

      expect(onFiltersChange).toHaveBeenCalledWith({
        ...DEFAULT_TIMELINE_FILTERS,
        eventTypes: ['filing'],
      });
    });

    it('shows badge with count when event types selected', () => {
      const filtersWithSelection: TimelineFilterState = {
        ...DEFAULT_TIMELINE_FILTERS,
        eventTypes: ['filing', 'order', 'hearing'],
      };
      render(<TimelineFilterBar {...defaultProps} filters={filtersWithSelection} />);

      const eventTypeButton = screen.getByRole('button', { name: /event type/i });
      expect(within(eventTypeButton).getByText('3')).toBeInTheDocument();
    });

    it('clears event type selection', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      const filtersWithSelection: TimelineFilterState = {
        ...DEFAULT_TIMELINE_FILTERS,
        eventTypes: ['filing'],
      };
      render(
        <TimelineFilterBar
          {...defaultProps}
          filters={filtersWithSelection}
          onFiltersChange={onFiltersChange}
        />
      );

      await user.click(screen.getByRole('button', { name: /event type/i }));
      await user.click(screen.getByText('Clear selection'));

      expect(onFiltersChange).toHaveBeenCalledWith({
        ...filtersWithSelection,
        eventTypes: [],
      });
    });
  });

  describe('Actor Filter', () => {
    it('opens actor dropdown on click', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /actors/i }));

      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('ABC Corporation')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });

    it('updates actor filter on selection', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      render(<TimelineFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />);

      await user.click(screen.getByRole('button', { name: /actors/i }));
      await user.click(screen.getByText('John Smith'));

      expect(onFiltersChange).toHaveBeenCalledWith({
        ...DEFAULT_TIMELINE_FILTERS,
        entityIds: ['entity-1'],
      });
    });

    it('filters actors by search', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /actors/i }));
      await user.type(screen.getByPlaceholderText('Search actors...'), 'john');

      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.queryByText('ABC Corporation')).not.toBeInTheDocument();
    });

    it('shows "No actors found" when search has no results', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /actors/i }));
      await user.type(screen.getByPlaceholderText('Search actors...'), 'nonexistent');

      expect(screen.getByText('No actors found')).toBeInTheDocument();
    });
  });

  describe('Date Range Filter', () => {
    it('opens date range dropdown on click', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /date range/i }));

      expect(screen.getByLabelText('From')).toBeInTheDocument();
      expect(screen.getByLabelText('To')).toBeInTheDocument();
    });

    it('updates start date filter', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      render(<TimelineFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />);

      await user.click(screen.getByRole('button', { name: /date range/i }));
      const startDateInput = screen.getByLabelText('Start date');
      await user.type(startDateInput, '2024-01-01');

      expect(onFiltersChange).toHaveBeenLastCalledWith({
        ...DEFAULT_TIMELINE_FILTERS,
        dateRange: { start: '2024-01-01', end: null },
      });
    });

    it('updates end date filter', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      render(<TimelineFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />);

      await user.click(screen.getByRole('button', { name: /date range/i }));
      const endDateInput = screen.getByLabelText('End date');
      await user.type(endDateInput, '2024-12-31');

      expect(onFiltersChange).toHaveBeenLastCalledWith({
        ...DEFAULT_TIMELINE_FILTERS,
        dateRange: { start: null, end: '2024-12-31' },
      });
    });

    it('clears date range filter', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      const filtersWithDate: TimelineFilterState = {
        ...DEFAULT_TIMELINE_FILTERS,
        dateRange: { start: '2024-01-01', end: '2024-12-31' },
      };
      render(
        <TimelineFilterBar
          {...defaultProps}
          filters={filtersWithDate}
          onFiltersChange={onFiltersChange}
        />
      );

      await user.click(screen.getByRole('button', { name: /date range/i }));
      await user.click(screen.getByText('Clear dates'));

      expect(onFiltersChange).toHaveBeenCalledWith({
        ...filtersWithDate,
        dateRange: { start: null, end: null },
      });
    });
  });

  describe('Verification Status Filter', () => {
    it('opens verification dropdown on click', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /verification/i }));

      expect(screen.getByText('All Events')).toBeInTheDocument();
      expect(screen.getByText('Verified Only')).toBeInTheDocument();
      expect(screen.getByText('Unverified Only')).toBeInTheDocument();
    });

    it('updates verification status filter on selection', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      render(<TimelineFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />);

      await user.click(screen.getByRole('button', { name: /verification/i }));
      await user.click(screen.getByText('Verified Only'));

      expect(onFiltersChange).toHaveBeenCalledWith({
        ...DEFAULT_TIMELINE_FILTERS,
        verificationStatus: 'verified',
      });
    });

    it('shows correct icon for verified status', () => {
      const filtersWithVerified: TimelineFilterState = {
        ...DEFAULT_TIMELINE_FILTERS,
        verificationStatus: 'verified',
      };
      render(<TimelineFilterBar {...defaultProps} filters={filtersWithVerified} />);

      // Button should show "Verified" text within it
      const verificationButton = screen.getByRole('button', { name: /filter by verification status/i });
      expect(verificationButton).toHaveTextContent('Verified');
    });

    it('shows correct icon for unverified status', () => {
      const filtersWithUnverified: TimelineFilterState = {
        ...DEFAULT_TIMELINE_FILTERS,
        verificationStatus: 'unverified',
      };
      render(<TimelineFilterBar {...defaultProps} filters={filtersWithUnverified} />);

      const verificationButton = screen.getByRole('button', { name: /filter by verification status/i });
      expect(verificationButton).toHaveTextContent('Unverified');
    });
  });

  describe('Clear Filters', () => {
    it('clears all filters on clear button click', async () => {
      const user = userEvent.setup();
      const onFiltersChange = vi.fn();
      const filtersWithMultiple: TimelineFilterState = {
        eventTypes: ['filing', 'order'],
        entityIds: ['entity-1'],
        dateRange: { start: '2024-01-01', end: null },
        verificationStatus: 'verified',
        showAnomaliesOnly: false,
      };
      render(
        <TimelineFilterBar
          {...defaultProps}
          filters={filtersWithMultiple}
          onFiltersChange={onFiltersChange}
        />
      );

      await user.click(screen.getByRole('button', { name: /clear.*4/i }));

      expect(onFiltersChange).toHaveBeenCalledWith(DEFAULT_TIMELINE_FILTERS);
    });

    it('shows correct count of active filters', () => {
      const filtersWithMultiple: TimelineFilterState = {
        eventTypes: ['filing'],
        entityIds: ['entity-1', 'entity-2'],
        dateRange: { start: '2024-01-01', end: '2024-12-31' },
        verificationStatus: 'all',
        showAnomaliesOnly: false,
      };
      render(<TimelineFilterBar {...defaultProps} filters={filtersWithMultiple} />);

      // 3 filters: eventTypes, entityIds, dateRange (verification is 'all' so not counted)
      expect(screen.getByRole('button', { name: /clear.*3/i })).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible labels for all filter buttons', () => {
      render(<TimelineFilterBar {...defaultProps} />);

      expect(screen.getByRole('button', { name: /filter by event type/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by actors/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by date range/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by verification status/i })).toBeInTheDocument();
    });

    it('uses proper ARIA roles for menu items', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /event type/i }));

      const filingOption = screen.getByRole('menuitemcheckbox', { name: /filing/i });
      expect(filingOption).toBeInTheDocument();
      expect(filingOption).toHaveAttribute('aria-checked', 'false');
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<TimelineFilterBar {...defaultProps} />);

      // Tab to first filter button
      await user.tab();
      expect(screen.getByRole('button', { name: /event type/i })).toHaveFocus();
    });
  });

  describe('Responsive behavior', () => {
    it('applies custom className', () => {
      render(<TimelineFilterBar {...defaultProps} className="custom-class" />);

      expect(screen.getByRole('toolbar')).toHaveClass('custom-class');
    });
  });
});
