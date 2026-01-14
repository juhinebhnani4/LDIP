import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MatterFilters } from './MatterFilters';
import { useMatterStore } from '@/stores/matterStore';

describe('MatterFilters', () => {
  beforeEach(() => {
    useMatterStore.setState({
      sortBy: 'recent',
      filterBy: 'all',
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders sort dropdown', () => {
    render(<MatterFilters />);

    expect(screen.getByRole('combobox', { name: /sort matters by/i })).toBeInTheDocument();
  });

  it('renders filter dropdown', () => {
    render(<MatterFilters />);

    expect(screen.getByRole('combobox', { name: /filter matters by status/i })).toBeInTheDocument();
  });

  it('displays current sort value', () => {
    useMatterStore.setState({ sortBy: 'recent' });

    render(<MatterFilters />);

    expect(screen.getByText('Recent')).toBeInTheDocument();
  });

  it('displays current filter value', () => {
    useMatterStore.setState({ filterBy: 'all' });

    render(<MatterFilters />);

    expect(screen.getByText('All')).toBeInTheDocument();
  });

  it('shows all sort options when dropdown opened', async () => {
    const user = userEvent.setup();

    render(<MatterFilters />);

    const sortTrigger = screen.getByRole('combobox', { name: /sort matters by/i });
    await user.click(sortTrigger);

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Recent' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Alphabetical' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Most pages' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Least verified' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Date created' })).toBeInTheDocument();
    });
  });

  it('shows all filter options when dropdown opened', async () => {
    const user = userEvent.setup();

    render(<MatterFilters />);

    const filterTrigger = screen.getByRole('combobox', { name: /filter matters by status/i });
    await user.click(filterTrigger);

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'All' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Processing' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Ready' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Needs attention' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Archived' })).toBeInTheDocument();
    });
  });

  it('updates store when sort option selected', async () => {
    const user = userEvent.setup();

    render(<MatterFilters />);

    const sortTrigger = screen.getByRole('combobox', { name: /sort matters by/i });
    await user.click(sortTrigger);

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Alphabetical' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'Alphabetical' }));

    expect(useMatterStore.getState().sortBy).toBe('alphabetical');
  });

  it('updates store when filter option selected', async () => {
    const user = userEvent.setup();

    render(<MatterFilters />);

    const filterTrigger = screen.getByRole('combobox', { name: /filter matters by status/i });
    await user.click(filterTrigger);

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Processing' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'Processing' }));

    expect(useMatterStore.getState().filterBy).toBe('processing');
  });

  it('applies custom className when provided', () => {
    const { container } = render(<MatterFilters className="custom-class" />);

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('reflects store changes in UI', () => {
    const { rerender } = render(<MatterFilters />);

    // Change store directly
    useMatterStore.setState({ sortBy: 'most_pages', filterBy: 'ready' });

    rerender(<MatterFilters />);

    expect(screen.getByText('Most pages')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });
});
