/**
 * Activity Store
 *
 * Zustand store for managing activities and dashboard stats.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const activities = useActivityStore((state) => state.activities);
 *   const isLoading = useActivityStore((state) => state.isLoading);
 *   const fetchActivities = useActivityStore((state) => state.fetchActivities);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { activities, isLoading, fetchActivities } = useActivityStore();
 */

import { create } from 'zustand';
import type { Activity, DashboardStats } from '@/types/activity';

/** Maximum number of activities to display in the feed */
const MAX_ACTIVITIES_DISPLAY = 10;

/** Cache duration in milliseconds (30 seconds) */
const STATS_CACHE_DURATION = 30000;

/** Generate unique ID for activity */
function generateActivityId(): string {
  return `activity_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

interface ActivityState {
  /** All activities */
  activities: Activity[];

  /** Dashboard statistics */
  stats: DashboardStats | null;

  /** Loading state for fetching activities */
  isLoading: boolean;

  /** Loading state for fetching stats */
  isStatsLoading: boolean;

  /** Error message if fetch fails */
  error: string | null;

  /** Timestamp of last stats fetch for cache invalidation */
  statsLastFetched: number | null;
}

interface ActivityActions {
  /** Fetch activities from API (or use mock data for now) */
  fetchActivities: () => Promise<void>;

  /** Fetch dashboard stats from API (or use mock data for now) */
  fetchStats: (forceRefresh?: boolean) => Promise<void>;

  /** Mark an activity as read */
  markActivityRead: (activityId: string) => void;

  /** Mark all activities as read */
  markAllRead: () => void;

  /** Add a new activity (for real-time updates) */
  addActivity: (activity: Omit<Activity, 'id' | 'isRead'>) => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Set error state */
  setError: (error: string | null) => void;
}

type ActivityStore = ActivityState & ActivityActions;

/**
 * Mock activities for development (backend API not yet available).
 * TODO: Replace with actual API call when backend provides activities endpoint
 */
function getMockActivities(): Activity[] {
  const now = new Date();
  return [
    {
      id: generateActivityId(),
      matterId: 'matter-1',
      matterName: 'Shah v. Mehta',
      type: 'processing_complete',
      description: 'Processing complete',
      timestamp: new Date(now.getTime() - 2 * 60 * 60000).toISOString(), // 2 hours ago
      isRead: false,
    },
    {
      id: generateActivityId(),
      matterId: 'matter-2',
      matterName: 'SEBI v. Parekh',
      type: 'matter_opened',
      description: 'Matter opened',
      timestamp: new Date(now.getTime() - 3 * 60 * 60000).toISOString(), // 3 hours ago
      isRead: false,
    },
    {
      id: generateActivityId(),
      matterId: 'matter-3',
      matterName: 'Custody Dispute - Sharma',
      type: 'contradictions_found',
      description: '3 contradictions found',
      timestamp: new Date(now.getTime() - 24 * 60 * 60000).toISOString(), // Yesterday
      isRead: false,
    },
    {
      id: generateActivityId(),
      matterId: 'matter-4',
      matterName: 'Tax Matter - Gupta',
      type: 'processing_started',
      description: 'Processing started',
      timestamp: new Date(now.getTime() - 26 * 60 * 60000).toISOString(), // Yesterday
      isRead: true,
    },
    {
      id: generateActivityId(),
      matterId: 'matter-1',
      matterName: 'Shah v. Mehta',
      type: 'verification_needed',
      description: '5 citations need verification',
      timestamp: new Date(now.getTime() - 48 * 60 * 60000).toISOString(), // 2 days ago
      isRead: true,
    },
    {
      id: generateActivityId(),
      matterId: 'matter-5',
      matterName: 'Corporate Merger - ABC Ltd',
      type: 'processing_failed',
      description: 'Processing failed - retry needed',
      timestamp: new Date(now.getTime() - 72 * 60 * 60000).toISOString(), // 3 days ago
      isRead: true,
    },
  ];
}

/**
 * Mock stats for development (backend API not yet available).
 * TODO: Replace with actual API call when backend provides stats endpoint
 */
function getMockStats(): DashboardStats {
  return {
    activeMatters: 5,
    verifiedFindings: 127,
    pendingReviews: 3,
  };
}

export const useActivityStore = create<ActivityStore>()((set, get) => ({
  // Initial state
  activities: [],
  stats: null,
  isLoading: false,
  isStatsLoading: false,
  error: null,
  statsLastFetched: null,

  // Actions
  fetchActivities: async () => {
    set({ isLoading: true, error: null });
    try {
      // TODO: Replace with actual API call when backend is available
      // const response = await fetch('/api/activities?limit=10');
      // const { data } = await response.json();

      // Using mock data for now
      await new Promise((resolve) => setTimeout(resolve, 300)); // Simulate network delay
      const activities = getMockActivities();

      set({
        activities,
        isLoading: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch activities';
      set({ error: message, isLoading: false });
    }
  },

  fetchStats: async (forceRefresh = false) => {
    const state = get();

    // Check cache validity
    if (
      !forceRefresh &&
      state.stats &&
      state.statsLastFetched &&
      Date.now() - state.statsLastFetched < STATS_CACHE_DURATION
    ) {
      return; // Use cached stats
    }

    set({ isStatsLoading: true, error: null });
    try {
      // TODO: Replace with actual API call when backend is available
      // const response = await fetch('/api/stats/dashboard');
      // const { data } = await response.json();

      // Using mock data for now
      await new Promise((resolve) => setTimeout(resolve, 200)); // Simulate network delay
      const stats = getMockStats();

      set({
        stats,
        isStatsLoading: false,
        statsLastFetched: Date.now(),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch stats';
      set({ error: message, isStatsLoading: false });
    }
  },

  markActivityRead: (activityId: string) => {
    set((state) => ({
      activities: state.activities.map((a) =>
        a.id === activityId ? { ...a, isRead: true } : a
      ),
    }));

    // TODO: Sync with backend when API is available
    // await fetch(`/api/activities/${activityId}/read`, { method: 'PATCH' });
  },

  markAllRead: () => {
    set((state) => ({
      activities: state.activities.map((a) => ({ ...a, isRead: true })),
    }));

    // TODO: Sync with backend when API is available
    // await fetch('/api/activities/read-all', { method: 'PATCH' });
  },

  addActivity: (activity) => {
    const newActivity: Activity = {
      ...activity,
      id: generateActivityId(),
      isRead: false,
    };

    set((state) => ({
      activities: [newActivity, ...state.activities],
    }));
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

// ============================================================================
// Selectors - use these for filtered/computed data
// ============================================================================

/** Selector for getting recent activities (limited to MAX_ACTIVITIES_DISPLAY) */
export const selectRecentActivities = (state: ActivityStore): Activity[] =>
  state.activities.slice(0, MAX_ACTIVITIES_DISPLAY);

/** Selector for getting unread activities */
export const selectUnreadActivities = (state: ActivityStore): Activity[] =>
  state.activities.filter((a) => !a.isRead);

/** Selector for getting unread count (uses selectUnreadActivities for consistency) */
export const selectUnreadCount = (state: ActivityStore): number =>
  selectUnreadActivities(state).length;

/** Selector for getting activities by matter */
export const selectActivitiesByMatter =
  (matterId: string) =>
  (state: ActivityStore): Activity[] =>
    state.activities.filter((a) => a.matterId === matterId);
