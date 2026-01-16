/**
 * CitationsHeader Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CitationsHeader, CitationsViewMode, CitationsFilterState } from './CitationsHeader';
import type { CitationStats } from '@/types/citation';

const mockStats: CitationStats = {
  totalCitations: 23,
  uniqueActs: 6,
  verifiedCount: 18,
  pendingCount: 2,
  missingActsCount: 2,
};

const mockActNames = [
  'Companies Act, 2013',
  'Negotiable Instruments Act, 1881',
  'Securities Act, 1992',
];

const defaultFilters: CitationsFilterState = {
  verificationStatus: null,
  actName: null,
  showOnlyIssues: false,
};

describe('CitationsHeader', () => {
  const defaultProps = {
    stats: mockStats,
    actNames: mockActNames,
    viewMode: 'list' as CitationsViewMode,
    onViewModeChange: vi.fn(),
    filters: defaultFilters,
    onFiltersChange: vi.fn(),
  };

  it('renders citation statistics correctly', () => {
    render(<CitationsHeader {...defaultProps} />);

    expect(screen.getByText('Citations')).toBeInTheDocument();
    expect(screen.getByText('23 found')).toBeInTheDocument();
    expect(screen.getByText(/18 verified/)).toBeInTheDocument();
    expect(screen.getByText(/3 issues/)).toBeInTheDocument();
    expect(screen.getByText(/2 pending/)).toBeInTheDocument();
  });

  it('renders Act Discovery summary', () => {
    render(<CitationsHeader {...defaultProps} />);

    expect(screen.getByText(/6/)).toBeInTheDocument(); // Acts referenced
    expect(screen.getByText(/4/)).toBeInTheDocument(); // available (6 - 2 missing)
    expect(screen.getByText(/2 missing/)).toBeInTheDocument();
  });

  it('shows "All available" when no missing acts', () => {
    const statsNoMissing: CitationStats = {
      ...mockStats,
      missingActsCount: 0,
    };

    render(<CitationsHeader {...defaultProps} stats={statsNoMissing} />);

    expect(screen.getByText('All available')).toBeInTheDocument();
  });

  it('renders view mode toggle buttons', () => {
    render(<CitationsHeader {...defaultProps} />);

    // ToggleGroup renders as radio buttons
    expect(screen.getByRole('radio', { name: /list view/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /by document view/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /by act view/i })).toBeInTheDocument();
  });

  it('calls onViewModeChange when view mode is toggled', async () => {
    const user = userEvent.setup();
    const onViewModeChange = vi.fn();

    render(
      <CitationsHeader
        {...defaultProps}
        onViewModeChange={onViewModeChange}
      />
    );

    await user.click(screen.getByRole('radio', { name: /by act view/i }));

    expect(onViewModeChange).toHaveBeenCalledWith('byAct');
  });

  it('renders status filter button', () => {
    render(<CitationsHeader {...defaultProps} />);

    expect(screen.getByRole('button', { name: /filter by verification status/i })).toBeInTheDocument();
  });

  it('opens status filter popover on click', async () => {
    const user = userEvent.setup();

    render(<CitationsHeader {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /filter by verification status/i }));

    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Mismatch')).toBeInTheDocument();
    expect(screen.getByText('Not Found')).toBeInTheDocument();
    expect(screen.getByText('No Act')).toBeInTheDocument();
  });

  it('renders Act name filter select', () => {
    render(<CitationsHeader {...defaultProps} />);

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders show only issues checkbox', () => {
    render(<CitationsHeader {...defaultProps} />);

    expect(screen.getByRole('checkbox', { name: /show only issues/i })).toBeInTheDocument();
  });

  it('calls onFiltersChange when show only issues is toggled', async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();

    render(
      <CitationsHeader
        {...defaultProps}
        onFiltersChange={onFiltersChange}
      />
    );

    await user.click(screen.getByRole('checkbox', { name: /show only issues/i }));

    expect(onFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      showOnlyIssues: true,
    });
  });

  it('shows badge count when status filter is active', () => {
    const filtersWithStatus: CitationsFilterState = {
      ...defaultFilters,
      verificationStatus: 'verified',
    };

    render(
      <CitationsHeader
        {...defaultProps}
        filters={filtersWithStatus}
      />
    );

    // The badge should show "1" for active filter
    const badge = screen.getByText('1');
    expect(badge).toBeInTheDocument();
  });

  it('shows clear filters button when filters are active', () => {
    const activeFilters: CitationsFilterState = {
      verificationStatus: 'verified',
      actName: 'Companies Act, 2013',
      showOnlyIssues: true,
    };

    render(
      <CitationsHeader
        {...defaultProps}
        filters={activeFilters}
      />
    );

    expect(screen.getByRole('button', { name: /clear filters/i })).toBeInTheDocument();
  });

  it('does not show clear filters button when no filters are active', () => {
    render(<CitationsHeader {...defaultProps} />);

    expect(screen.queryByRole('button', { name: /clear filters/i })).not.toBeInTheDocument();
  });

  it('calls onFiltersChange with reset values when clear filters is clicked', async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    const activeFilters: CitationsFilterState = {
      verificationStatus: 'verified',
      actName: 'Companies Act, 2013',
      showOnlyIssues: true,
    };

    render(
      <CitationsHeader
        {...defaultProps}
        filters={activeFilters}
        onFiltersChange={onFiltersChange}
      />
    );

    await user.click(screen.getByRole('button', { name: /clear filters/i }));

    expect(onFiltersChange).toHaveBeenCalledWith({
      verificationStatus: null,
      actName: null,
      showOnlyIssues: false,
    });
  });

  it('handles null stats gracefully', () => {
    render(<CitationsHeader {...defaultProps} stats={null} />);

    expect(screen.getByText('Citations')).toBeInTheDocument();
    // Stats should not be shown
    expect(screen.queryByText(/found/)).not.toBeInTheDocument();
  });

  it('hides Act Discovery summary when uniqueActs is 0', () => {
    const statsNoActs: CitationStats = {
      ...mockStats,
      uniqueActs: 0,
    };

    render(<CitationsHeader {...defaultProps} stats={statsNoActs} />);

    expect(screen.queryByText(/Acts referenced/)).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <CitationsHeader {...defaultProps} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('highlights current view mode', () => {
    render(<CitationsHeader {...defaultProps} viewMode="byDocument" />);

    // The byDocument radio should be checked (aria-checked=true)
    const byDocButton = screen.getByRole('radio', { name: /by document view/i });
    expect(byDocButton).toHaveAttribute('data-state', 'on');
  });
});
