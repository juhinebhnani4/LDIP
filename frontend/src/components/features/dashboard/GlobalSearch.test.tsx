import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GlobalSearch } from './GlobalSearch';

describe('GlobalSearch', () => {
  it('renders search input with placeholder', () => {
    render(<GlobalSearch />);

    const input = screen.getByRole('searchbox', { name: /search all matters/i });
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('placeholder', 'Search all matters...');
  });

  it('renders search icon', () => {
    render(<GlobalSearch />);

    // The search icon is in the component
    const input = screen.getByRole('searchbox');
    expect(input.parentElement).toContainHTML('svg');
  });

  it('updates input value when typing', async () => {
    const user = userEvent.setup();

    render(<GlobalSearch />);

    const input = screen.getByRole('searchbox');
    await user.type(input, 'Smith');

    expect(input).toHaveValue('Smith');
  });

  it('shows clear button when input has value', async () => {
    const user = userEvent.setup();

    render(<GlobalSearch />);

    const input = screen.getByRole('searchbox');
    await user.type(input, 'test');

    expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
  });

  it('clears input when clear button is clicked', async () => {
    const user = userEvent.setup();

    render(<GlobalSearch />);

    const input = screen.getByRole('searchbox');
    await user.type(input, 'test');

    const clearButton = screen.getByRole('button', { name: /clear search/i });
    await user.click(clearButton);

    expect(input).toHaveValue('');
  });

  it('does not show clear button when input is empty', () => {
    render(<GlobalSearch />);

    expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument();
  });

  it('has proper accessibility attributes', () => {
    render(<GlobalSearch />);

    const input = screen.getByRole('searchbox');
    expect(input).toHaveAttribute('aria-label', 'Search all matters');
    expect(input).toHaveAttribute('aria-haspopup', 'listbox');
  });

  it('has type="search" for search input', () => {
    render(<GlobalSearch />);

    const input = screen.getByRole('searchbox');
    expect(input).toHaveAttribute('type', 'search');
  });
});
