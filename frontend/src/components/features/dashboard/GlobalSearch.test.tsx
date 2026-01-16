import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GlobalSearch } from './GlobalSearch';

// Mock the globalSearch API
vi.mock('@/lib/api/globalSearch', () => ({
  globalSearch: vi.fn(),
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

import { globalSearch } from '@/lib/api/globalSearch';
import { toast } from 'sonner';

const mockGlobalSearch = vi.mocked(globalSearch);

describe('GlobalSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGlobalSearch.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

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

  // API Integration Tests (Story 14.11)
  // These tests use real timers with waitFor to handle debounce
  describe('API integration', () => {
    it('calls globalSearch API after debounce delay', async () => {
      const user = userEvent.setup();

      mockGlobalSearch.mockResolvedValue([
        {
          id: 'matter-1',
          type: 'matter' as const,
          title: 'Test Matter',
          matterId: 'matter-1',
          matterTitle: 'Test Matter',
          matchedContent: 'Test content',
        },
      ]);

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      // Wait for debounce and API call
      await waitFor(
        () => {
          expect(mockGlobalSearch).toHaveBeenCalledWith('test');
        },
        { timeout: 1000 }
      );
    });

    it('displays search results from API', async () => {
      const user = userEvent.setup();

      mockGlobalSearch.mockResolvedValue([
        {
          id: 'result-1',
          type: 'matter' as const,
          title: 'TestMatterResult',
          matterId: 'matter-1',
          matterTitle: 'TestMatterResult',
          matchedContent: 'Some matter content...',
        },
        {
          id: 'result-2',
          type: 'document' as const,
          title: 'TestDocumentResult',
          matterId: 'matter-1',
          matterTitle: 'TestMatterResult',
          matchedContent: 'Some document content...',
        },
      ]);

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      // Wait for results to render - search for unique text
      await waitFor(
        () => {
          expect(screen.getByText('TestDocumentResult')).toBeInTheDocument();
        },
        { timeout: 1000 }
      );

      // Verify both types of results are shown
      const buttons = screen.getAllByRole('button');
      // Should have clear button + 2 result buttons
      expect(buttons.length).toBeGreaterThanOrEqual(2);
    });

    it('shows no results message when API returns empty array', async () => {
      const user = userEvent.setup();

      mockGlobalSearch.mockResolvedValue([]);

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'xyz');

      await waitFor(
        () => {
          expect(screen.getByText(/no results found/i)).toBeInTheDocument();
        },
        { timeout: 1000 }
      );
    });

    it('shows error state and retry button when API fails', async () => {
      const user = userEvent.setup();

      mockGlobalSearch.mockRejectedValue(new Error('Network error'));

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      await waitFor(
        () => {
          expect(screen.getByText('Search failed')).toBeInTheDocument();
          expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
        },
        { timeout: 1000 }
      );

      expect(toast.error).toHaveBeenCalledWith('Search failed. Please try again.');
    });

    it('retry button triggers new search', async () => {
      const user = userEvent.setup();

      // Always fail so we can see the retry button
      mockGlobalSearch.mockRejectedValue(new Error('Network error'));

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      // Wait for error state
      await waitFor(
        () => {
          expect(screen.getByText('Search failed')).toBeInTheDocument();
        },
        { timeout: 1000 }
      );

      // Click retry
      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      // Wait for another API call
      await waitFor(
        () => {
          expect(mockGlobalSearch).toHaveBeenCalledTimes(2);
        },
        { timeout: 1000 }
      );
    });

    it('short queries do not trigger API call', async () => {
      const user = userEvent.setup();

      // Setup a result for when API is called
      mockGlobalSearch.mockResolvedValue([
        {
          id: 'result-1',
          type: 'matter' as const,
          title: 'Result',
          matterId: 'matter-1',
          matterTitle: 'Result',
          matchedContent: 'Content',
        },
      ]);

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');

      // Type only 1 character
      await user.type(input, 'a');

      // Wait for debounce time
      await waitFor(
        () => {
          // After debounce, API should not be called for 1-char query
          expect(mockGlobalSearch).not.toHaveBeenCalled();
        },
        { timeout: 500 }
      );

      // Now type another character to make it 2+ chars
      await user.type(input, 'b');

      // Now API should be called
      await waitFor(
        () => {
          expect(mockGlobalSearch).toHaveBeenCalled();
        },
        { timeout: 1000 }
      );
    });

    it('clears error state when clear button is clicked', async () => {
      const user = userEvent.setup();

      mockGlobalSearch.mockRejectedValue(new Error('Network error'));

      render(<GlobalSearch />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      // Wait for error state
      await waitFor(
        () => {
          expect(screen.getByText('Search failed')).toBeInTheDocument();
        },
        { timeout: 1000 }
      );

      // Clear the search
      const clearButton = screen.getByRole('button', { name: /clear search/i });
      await user.click(clearButton);

      // Error should be cleared
      expect(screen.queryByText('Search failed')).not.toBeInTheDocument();
    });
  });
});
