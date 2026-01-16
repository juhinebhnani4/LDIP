/**
 * Activity Store Tests
 *
 * Story 14.5: Dashboard Real APIs
 *
 * Tests for activity store with mocked API calls.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  useActivityStore,
  selectRecentActivities,
  selectUnreadActivities,
  selectUnreadCount,
  selectActivitiesByMatter,
} from './activityStore';
import type { Activity, ActivityType, DashboardStats } from '@/types/activity';
import * as activityApiModule from '@/lib/api/activity';

// Mock the API module
vi.mock('@/lib/api/activity', () => ({
  activityApi: {
    list: vi.fn(),
    markRead: vi.fn(),
  },
  dashboardApi: {
    getStats: vi.fn(),
  },
}));

// Create mock activity data
function createMockActivity(
  overrides: Partial<Activity> = {}
): Activity {
  return {
    id: `activity_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
    matterId: 'mock-matter-id',
    matterName: 'Mock Matter',
    type: 'processing_complete' as ActivityType,
    description: 'Mock activity',
    timestamp: new Date().toISOString(),
    isRead: false,
    ...overrides,
  };
}

// Create mock stats data
function createMockStats(
  overrides: Partial<DashboardStats> = {}
): DashboardStats {
  return {
    activeMatters: 5,
    verifiedFindings: 127,
    pendingReviews: 3,
    ...overrides,
  };
}

describe('activityStore', () => {
  const mockActivityApi = activityApiModule.activityApi as {
    list: ReturnType<typeof vi.fn>;
    markRead: ReturnType<typeof vi.fn>;
  };
  const mockDashboardApi = activityApiModule.dashboardApi as {
    getStats: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    // Reset store state before each test
    useActivityStore.setState({
      activities: [],
      stats: null,
      isLoading: false,
      isStatsLoading: false,
      error: null,
      statsLastFetched: null,
    });

    // Reset mocks
    vi.clearAllMocks();

    // Setup default successful responses
    mockActivityApi.list.mockResolvedValue({
      activities: [
        createMockActivity({ id: 'activity-1', isRead: false }),
        createMockActivity({ id: 'activity-2', isRead: true }),
      ],
      total: 2,
    });
    mockActivityApi.markRead.mockResolvedValue(
      createMockActivity({ id: 'activity-1', isRead: true })
    );
    mockDashboardApi.getStats.mockResolvedValue(createMockStats());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchActivities', () => {
    it('sets loading state while fetching', async () => {
      const fetchPromise = useActivityStore.getState().fetchActivities();

      // Check loading state is set
      expect(useActivityStore.getState().isLoading).toBe(true);

      await fetchPromise;

      // Loading should be false after completion
      expect(useActivityStore.getState().isLoading).toBe(false);
    });

    it('populates activities after fetch', async () => {
      await useActivityStore.getState().fetchActivities();

      const state = useActivityStore.getState();
      expect(state.activities.length).toBe(2);
    });

    it('clears error state on successful fetch', async () => {
      // Set an error first
      useActivityStore.setState({ error: 'Previous error' });

      await useActivityStore.getState().fetchActivities();

      expect(useActivityStore.getState().error).toBeNull();
    });

    it('each activity has required fields', async () => {
      await useActivityStore.getState().fetchActivities();

      const activity = useActivityStore.getState().activities[0];
      expect(activity).toBeDefined();
      expect(activity?.id).toBeDefined();
      expect(activity?.type).toBeDefined();
      expect(activity?.description).toBeDefined();
      expect(activity?.timestamp).toBeDefined();
      expect(typeof activity?.isRead).toBe('boolean');
    });

    it('handles API error gracefully', async () => {
      mockActivityApi.list.mockRejectedValue(new Error('Network error'));

      await useActivityStore.getState().fetchActivities();

      const state = useActivityStore.getState();
      expect(state.error).toBe('Network error');
      expect(state.isLoading).toBe(false);
    });
  });

  describe('fetchStats', () => {
    it('sets stats loading state while fetching', async () => {
      const fetchPromise = useActivityStore.getState().fetchStats();

      // Check loading state is set
      expect(useActivityStore.getState().isStatsLoading).toBe(true);

      await fetchPromise;

      // Loading should be false after completion
      expect(useActivityStore.getState().isStatsLoading).toBe(false);
    });

    it('populates stats after fetch', async () => {
      await useActivityStore.getState().fetchStats();

      const state = useActivityStore.getState();
      expect(state.stats).not.toBeNull();
      expect(state.stats?.activeMatters).toBe(5);
      expect(state.stats?.verifiedFindings).toBe(127);
      expect(state.stats?.pendingReviews).toBe(3);
    });

    it('uses cached stats within cache duration', async () => {
      // First fetch
      await useActivityStore.getState().fetchStats();
      const firstFetchTime = useActivityStore.getState().statsLastFetched;

      // Second fetch (should use cache)
      await useActivityStore.getState().fetchStats();
      const secondFetchTime = useActivityStore.getState().statsLastFetched;

      // Should be the same timestamp (cached)
      expect(secondFetchTime).toBe(firstFetchTime);
      // API should only be called once
      expect(mockDashboardApi.getStats).toHaveBeenCalledTimes(1);
    });

    it('bypasses cache when forceRefresh is true', async () => {
      // First fetch
      await useActivityStore.getState().fetchStats();
      const firstFetchTime = useActivityStore.getState().statsLastFetched;

      // Wait a tiny bit to ensure different timestamp
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Force refresh
      await useActivityStore.getState().fetchStats(true);
      const secondFetchTime = useActivityStore.getState().statsLastFetched;

      // Should have a newer timestamp
      expect(secondFetchTime).toBeGreaterThan(firstFetchTime ?? 0);
      // API should be called twice
      expect(mockDashboardApi.getStats).toHaveBeenCalledTimes(2);
    });

    it('handles API error gracefully', async () => {
      mockDashboardApi.getStats.mockRejectedValue(new Error('Stats error'));

      await useActivityStore.getState().fetchStats();

      const state = useActivityStore.getState();
      expect(state.error).toBe('Stats error');
      expect(state.isStatsLoading).toBe(false);
    });
  });

  describe('markActivityRead', () => {
    it('marks a specific activity as read (optimistic update)', async () => {
      await useActivityStore.getState().fetchActivities();

      const unreadActivity = useActivityStore
        .getState()
        .activities.find((a) => !a.isRead);
      expect(unreadActivity).toBeDefined();

      if (unreadActivity) {
        useActivityStore.getState().markActivityRead(unreadActivity.id);

        // Optimistic update should happen immediately
        const updatedActivity = useActivityStore
          .getState()
          .activities.find((a) => a.id === unreadActivity.id);
        expect(updatedActivity?.isRead).toBe(true);
      }
    });

    it('calls API to persist read state', async () => {
      await useActivityStore.getState().fetchActivities();

      const unreadActivity = useActivityStore
        .getState()
        .activities.find((a) => !a.isRead);

      if (unreadActivity) {
        useActivityStore.getState().markActivityRead(unreadActivity.id);

        expect(mockActivityApi.markRead).toHaveBeenCalledWith(unreadActivity.id);
      }
    });

    it('reverts on API failure', async () => {
      mockActivityApi.markRead.mockRejectedValue(new Error('API error'));

      await useActivityStore.getState().fetchActivities();

      const unreadActivity = useActivityStore
        .getState()
        .activities.find((a) => !a.isRead);

      if (unreadActivity) {
        useActivityStore.getState().markActivityRead(unreadActivity.id);

        // Wait for API call to complete
        await new Promise((resolve) => setTimeout(resolve, 10));

        // Should revert to unread
        const updatedActivity = useActivityStore
          .getState()
          .activities.find((a) => a.id === unreadActivity.id);
        expect(updatedActivity?.isRead).toBe(false);
      }
    });

    it('does not affect other activities', async () => {
      await useActivityStore.getState().fetchActivities();

      const activities = useActivityStore.getState().activities;
      const unreadActivity = activities.find((a) => !a.isRead);
      const otherActivity = activities.find((a) => a.id !== unreadActivity?.id);

      if (unreadActivity && otherActivity) {
        const otherReadStateBefore = otherActivity.isRead;

        useActivityStore.getState().markActivityRead(unreadActivity.id);

        const otherAfter = useActivityStore
          .getState()
          .activities.find((a) => a.id === otherActivity.id);
        expect(otherAfter?.isRead).toBe(otherReadStateBefore);
      }
    });
  });

  describe('markAllRead', () => {
    it('marks all activities as read', async () => {
      await useActivityStore.getState().fetchActivities();

      useActivityStore.getState().markAllRead();

      const allRead = useActivityStore
        .getState()
        .activities.every((a) => a.isRead);
      expect(allRead).toBe(true);
    });
  });

  describe('addActivity', () => {
    it('adds a new activity to the beginning of the list', () => {
      useActivityStore.getState().addActivity({
        matterId: 'matter-1',
        matterName: 'Test Matter',
        type: 'processing_complete' as ActivityType,
        description: 'Processing complete',
        timestamp: new Date().toISOString(),
      });

      const state = useActivityStore.getState();
      expect(state.activities[0]?.description).toBe('Processing complete');
      expect(state.activities[0]?.isRead).toBe(false);
    });

    it('generates unique ID for new activity', () => {
      useActivityStore.getState().addActivity({
        matterId: 'matter-1',
        matterName: 'Test Matter 1',
        type: 'processing_complete' as ActivityType,
        description: 'Activity 1',
        timestamp: new Date().toISOString(),
      });

      useActivityStore.getState().addActivity({
        matterId: 'matter-2',
        matterName: 'Test Matter 2',
        type: 'matter_opened' as ActivityType,
        description: 'Activity 2',
        timestamp: new Date().toISOString(),
      });

      const activities = useActivityStore.getState().activities;
      expect(activities[0]?.id).not.toBe(activities[1]?.id);
    });

    it('new activity is always unread', () => {
      useActivityStore.getState().addActivity({
        matterId: 'matter-1',
        matterName: 'Test Matter',
        type: 'verification_needed' as ActivityType,
        description: 'Test',
        timestamp: new Date().toISOString(),
      });

      expect(useActivityStore.getState().activities[0]?.isRead).toBe(false);
    });
  });

  describe('setLoading', () => {
    it('sets loading state', () => {
      useActivityStore.getState().setLoading(true);
      expect(useActivityStore.getState().isLoading).toBe(true);

      useActivityStore.getState().setLoading(false);
      expect(useActivityStore.getState().isLoading).toBe(false);
    });
  });

  describe('setError', () => {
    it('sets error state', () => {
      useActivityStore.getState().setError('Test error');
      expect(useActivityStore.getState().error).toBe('Test error');

      useActivityStore.getState().setError(null);
      expect(useActivityStore.getState().error).toBeNull();
    });
  });

  describe('selectors', () => {
    it('selectRecentActivities returns max 10 activities', async () => {
      // Add more activities to exceed limit
      for (let i = 0; i < 15; i++) {
        useActivityStore.getState().addActivity({
          matterId: `matter-${i}`,
          matterName: `Matter ${i}`,
          type: 'matter_opened' as ActivityType,
          description: `Activity ${i}`,
          timestamp: new Date().toISOString(),
        });
      }

      const recent = selectRecentActivities(useActivityStore.getState());
      expect(recent.length).toBeLessThanOrEqual(10);
    });

    it('selectUnreadActivities returns only unread activities', async () => {
      await useActivityStore.getState().fetchActivities();

      const unread = selectUnreadActivities(useActivityStore.getState());
      expect(unread.every((a) => !a.isRead)).toBe(true);
      expect(unread.length).toBe(1); // Only activity-1 is unread in mock
    });

    it('selectUnreadCount returns correct count', async () => {
      await useActivityStore.getState().fetchActivities();

      const state = useActivityStore.getState();
      const actualUnread = state.activities.filter((a) => !a.isRead).length;
      const selectorCount = selectUnreadCount(state);

      expect(selectorCount).toBe(actualUnread);
      expect(selectorCount).toBe(1); // Only 1 unread in mock
    });

    it('selectActivitiesByMatter filters correctly', async () => {
      // Add activity with known matter
      useActivityStore.getState().addActivity({
        matterId: 'test-matter-123',
        matterName: 'Test Matter',
        type: 'processing_complete' as ActivityType,
        description: 'Test activity',
        timestamp: new Date().toISOString(),
      });

      const matterActivities = selectActivitiesByMatter('test-matter-123')(
        useActivityStore.getState()
      );

      expect(matterActivities.length).toBe(1);
      expect(matterActivities.every((a) => a.matterId === 'test-matter-123')).toBe(true);
    });

    it('selectActivitiesByMatter returns empty array for unknown matter', async () => {
      await useActivityStore.getState().fetchActivities();

      const matterActivities = selectActivitiesByMatter('unknown-matter')(
        useActivityStore.getState()
      );

      expect(matterActivities).toEqual([]);
    });
  });
});
