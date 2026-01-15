import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActivityFeed, ActivityFeedSkeleton } from './ActivityFeed';
import { useActivityStore } from '@/stores/activityStore';
import type { Activity, ActivityType } from '@/types/activity';

// Mock the store
vi.mock('@/stores/activityStore', async () => {
  const actual = await vi.importActual('@/stores/activityStore');
  return {
    ...actual,
    useActivityStore: vi.fn(),
  };
});

const createMockActivities = (): Activity[] => {
  const now = new Date();
  return [
    {
      id: 'activity-1',
      matterId: 'matter-1',
      matterName: 'Shah v. Mehta',
      type: 'processing_complete' as ActivityType,
      description: 'Processing complete',
      timestamp: new Date(now.getTime() - 2 * 60 * 60000).toISOString(),
      isRead: false,
    },
    {
      id: 'activity-2',
      matterId: 'matter-2',
      matterName: 'SEBI v. Parekh',
      type: 'matter_opened' as ActivityType,
      description: 'Matter opened',
      timestamp: new Date(now.getTime() - 3 * 60 * 60000).toISOString(),
      isRead: false,
    },
    {
      id: 'activity-3',
      matterId: 'matter-3',
      matterName: 'Custody Dispute',
      type: 'contradictions_found' as ActivityType,
      description: '3 contradictions found',
      timestamp: new Date(now.getTime() - 26 * 60 * 60000).toISOString(),
      isRead: true,
    },
  ];
};

describe('ActivityFeed', () => {
  const mockFetchActivities = vi.fn();
  const mockMarkActivityRead = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const setupMockStore = (overrides: Partial<{
    activities: Activity[];
    isLoading: boolean;
    error: string | null;
  }> = {}) => {
    const defaultState = {
      activities: createMockActivities(),
      isLoading: false,
      error: null,
      ...overrides,
    };

    (useActivityStore as unknown as ReturnType<typeof vi.fn>).mockImplementation((selector: (state: unknown) => unknown) => {
      const state = {
        ...defaultState,
        fetchActivities: mockFetchActivities,
        markActivityRead: mockMarkActivityRead,
      };

      if (typeof selector === 'function') {
        return selector(state);
      }
      return state;
    });
  };

  describe('loading state', () => {
    it('renders loading skeletons when loading', () => {
      setupMockStore({ isLoading: true, activities: [] });
      render(<ActivityFeed />);

      const loadingList = screen.getByRole('list', { name: 'Loading activities' });
      expect(loadingList).toBeInTheDocument();
    });

    it('calls fetchActivities on mount', () => {
      setupMockStore();
      render(<ActivityFeed />);

      expect(mockFetchActivities).toHaveBeenCalled();
    });
  });

  describe('error state', () => {
    it('renders error message when error occurs', () => {
      setupMockStore({ error: 'Failed to load activities', activities: [] });
      render(<ActivityFeed />);

      expect(screen.getByText('Failed to load activities')).toBeInTheDocument();
    });

    it('renders retry button on error', () => {
      setupMockStore({ error: 'Failed to load activities', activities: [] });
      render(<ActivityFeed />);

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('calls fetchActivities when retry is clicked', async () => {
      const user = userEvent.setup();
      setupMockStore({ error: 'Failed to load activities', activities: [] });
      render(<ActivityFeed />);

      await user.click(screen.getByRole('button', { name: /try again/i }));

      // fetchActivities called on mount + on retry
      expect(mockFetchActivities).toHaveBeenCalledTimes(2);
    });
  });

  describe('empty state', () => {
    it('renders empty message when no activities', () => {
      setupMockStore({ activities: [] });
      render(<ActivityFeed />);

      expect(screen.getByText('No recent activity')).toBeInTheDocument();
    });
  });

  describe('activities display', () => {
    it('renders activity feed header', () => {
      setupMockStore();
      render(<ActivityFeed />);

      expect(screen.getByText('Activity Feed')).toBeInTheDocument();
    });

    it('renders all activities', () => {
      setupMockStore();
      render(<ActivityFeed />);

      expect(screen.getByText('Shah v. Mehta')).toBeInTheDocument();
      expect(screen.getByText('SEBI v. Parekh')).toBeInTheDocument();
      expect(screen.getByText('Custody Dispute')).toBeInTheDocument();
    });

    it('renders activity descriptions', () => {
      setupMockStore();
      render(<ActivityFeed />);

      expect(screen.getByText('Processing complete')).toBeInTheDocument();
      expect(screen.getByText('Matter opened')).toBeInTheDocument();
      expect(screen.getByText('3 contradictions found')).toBeInTheDocument();
    });

    it('groups activities by day', () => {
      setupMockStore();
      render(<ActivityFeed />);

      // Should have "Today" and "Yesterday" group headers (h3 elements)
      const headings = screen.getAllByRole('heading', { level: 3 });
      const headingTexts = headings.map((h) => h.textContent);
      expect(headingTexts).toContain('Today');
      expect(headingTexts).toContain('Yesterday');
    });

    it('renders View All Activity link', () => {
      setupMockStore();
      render(<ActivityFeed />);

      const viewAllLink = screen.getByRole('link', { name: /view all activity/i });
      expect(viewAllLink).toHaveAttribute('href', '/activity');
    });
  });

  describe('activity interactions', () => {
    it('marks activity as read when clicked', async () => {
      const user = userEvent.setup();
      setupMockStore();
      render(<ActivityFeed />);

      const firstActivityLink = screen.getAllByRole('link')[0];
      await user.click(firstActivityLink);

      expect(mockMarkActivityRead).toHaveBeenCalledWith('activity-1');
    });

    it('does not mark already read activity again', async () => {
      const user = userEvent.setup();
      const activities = createMockActivities();
      activities[0].isRead = true;
      setupMockStore({ activities });
      render(<ActivityFeed />);

      const firstActivityLink = screen.getAllByRole('link')[0];
      await user.click(firstActivityLink);

      expect(mockMarkActivityRead).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('renders activities in semantic list', () => {
      setupMockStore();
      render(<ActivityFeed />);

      const lists = screen.getAllByRole('list');
      expect(lists.length).toBeGreaterThan(0);
    });

    it('groups have accessible labels', () => {
      setupMockStore();
      render(<ActivityFeed />);

      expect(screen.getByRole('list', { name: /activities from today/i })).toBeInTheDocument();
      expect(screen.getByRole('list', { name: /activities from yesterday/i })).toBeInTheDocument();
    });

    it('renders error with alert role', () => {
      setupMockStore({ error: 'Test error', activities: [] });
      render(<ActivityFeed />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });
});

describe('ActivityFeedSkeleton', () => {
  it('renders card skeleton', () => {
    const { container } = render(<ActivityFeedSkeleton />);

    // Should render loading animation
    const animatedElements = container.querySelectorAll('.animate-pulse');
    expect(animatedElements.length).toBeGreaterThan(0);
  });

  it('renders loading activity placeholders', () => {
    render(<ActivityFeedSkeleton />);

    // Should have skeleton list items
    expect(screen.getByRole('list', { name: 'Loading activities' })).toBeInTheDocument();
  });
});
