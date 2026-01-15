import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QuickStats, QuickStatsSkeleton } from './QuickStats';
import { useActivityStore } from '@/stores/activityStore';
import type { DashboardStats } from '@/types/activity';

// Mock the store
vi.mock('@/stores/activityStore', async () => {
  const actual = await vi.importActual('@/stores/activityStore');
  return {
    ...actual,
    useActivityStore: vi.fn(),
  };
});

const createMockStats = (overrides: Partial<DashboardStats> = {}): DashboardStats => ({
  activeMatters: 5,
  verifiedFindings: 127,
  pendingReviews: 3,
  ...overrides,
});

describe('QuickStats', () => {
  const mockFetchStats = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const setupMockStore = (overrides: Partial<{
    stats: DashboardStats | null;
    isStatsLoading: boolean;
    error: string | null;
  }> = {}) => {
    const defaultState = {
      stats: createMockStats(),
      isStatsLoading: false,
      error: null,
      ...overrides,
    };

    (useActivityStore as unknown as ReturnType<typeof vi.fn>).mockImplementation((selector: (state: unknown) => unknown) => {
      const state = {
        ...defaultState,
        fetchStats: mockFetchStats,
      };

      if (typeof selector === 'function') {
        return selector(state);
      }
      return state;
    });
  };

  describe('loading state', () => {
    it('renders loading skeletons when loading', () => {
      setupMockStore({ isStatsLoading: true, stats: null });
      const { container } = render(<QuickStats />);

      // Should have skeleton elements
      const skeletons = container.querySelectorAll('.animate-pulse, [data-slot="skeleton"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('calls fetchStats on mount', () => {
      setupMockStore();
      render(<QuickStats />);

      expect(mockFetchStats).toHaveBeenCalled();
    });
  });

  describe('error state', () => {
    it('renders error message when error occurs', () => {
      setupMockStore({ error: 'Failed to load stats', stats: null });
      render(<QuickStats />);

      expect(screen.getByText('Failed to load stats')).toBeInTheDocument();
    });

    it('has error alert role', () => {
      setupMockStore({ error: 'Test error', stats: null });
      render(<QuickStats />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('stats display', () => {
    it('renders Quick Stats header', () => {
      setupMockStore();
      render(<QuickStats />);

      expect(screen.getByText('Quick Stats')).toBeInTheDocument();
    });

    it('renders active matters count', () => {
      setupMockStore({ stats: createMockStats({ activeMatters: 5 }) });
      render(<QuickStats />);

      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('Active Matters')).toBeInTheDocument();
    });

    it('renders verified findings count', () => {
      setupMockStore({ stats: createMockStats({ verifiedFindings: 127 }) });
      render(<QuickStats />);

      expect(screen.getByText('127')).toBeInTheDocument();
      expect(screen.getByText('Verified Findings')).toBeInTheDocument();
    });

    it('renders pending reviews count', () => {
      setupMockStore({ stats: createMockStats({ pendingReviews: 3 }) });
      render(<QuickStats />);

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('Pending Reviews')).toBeInTheDocument();
    });

    it('formats large numbers with locale formatting', () => {
      setupMockStore({ stats: createMockStats({ verifiedFindings: 1234 }) });
      render(<QuickStats />);

      // Should show comma-separated number
      expect(screen.getByText('1,234')).toBeInTheDocument();
    });

    it('handles zero values', () => {
      setupMockStore({
        stats: createMockStats({
          activeMatters: 0,
          verifiedFindings: 0,
          pendingReviews: 0,
        }),
      });
      render(<QuickStats />);

      // Should show three zeros
      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBe(3);
    });
  });

  describe('null stats state', () => {
    it('renders empty state message when stats are null', () => {
      setupMockStore({ stats: null });
      render(<QuickStats />);

      expect(screen.getByText('No statistics available')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders folder icon for active matters', () => {
      setupMockStore();
      const { container } = render(<QuickStats />);

      // Check for blue folder icon
      const blueIcon = container.querySelector('.text-blue-500');
      expect(blueIcon).toBeInTheDocument();
    });

    it('renders check icon for verified findings', () => {
      setupMockStore();
      const { container } = render(<QuickStats />);

      // Check for green check icon
      const greenIcon = container.querySelector('.text-green-500');
      expect(greenIcon).toBeInTheDocument();
    });

    it('renders timer icon for pending reviews', () => {
      setupMockStore();
      const { container } = render(<QuickStats />);

      // Check for orange timer icon
      const orangeIcon = container.querySelector('.text-orange-500');
      expect(orangeIcon).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      setupMockStore();
      const { container } = render(<QuickStats className="custom-class" />);

      const card = container.firstChild;
      expect(card).toHaveClass('custom-class');
    });
  });
});

describe('QuickStatsSkeleton', () => {
  it('renders card skeleton', () => {
    const { container } = render(<QuickStatsSkeleton />);

    // Should have skeleton elements
    const card = container.firstChild;
    expect(card).toBeInTheDocument();
  });

  it('renders title skeleton', () => {
    const { container } = render(<QuickStatsSkeleton />);

    // Should have title placeholder
    const titleSkeleton = container.querySelector('.h-5.w-24');
    expect(titleSkeleton).toBeInTheDocument();
  });

  it('renders three stat item skeletons', () => {
    const { container } = render(<QuickStatsSkeleton />);

    // Should have 3 stat item placeholders (each has icon + 2 text placeholders = 3 elements each)
    const iconSkeletons = container.querySelectorAll('.size-9.rounded-md');
    expect(iconSkeletons.length).toBe(3);
  });

  it('applies className prop', () => {
    const { container } = render(<QuickStatsSkeleton className="custom-class" />);

    const card = container.firstChild;
    expect(card).toHaveClass('custom-class');
  });
});
