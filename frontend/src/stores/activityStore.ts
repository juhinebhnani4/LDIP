/**
 * Activity Store
 *
 * Zustand store for managing activities and dashboard stats.
 *
 * Story 14.5: Dashboard Real APIs - Wired to backend API endpoints.
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
import { activityApi, dashboardApi } from '@/lib/api/activity';

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
  /** Fetch activities from backend API */
  fetchActivities: () => Promise<void>;

  /** Fetch dashboard stats from backend API */
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
      // Story 14.5: Fetch from real backend API
      const { activities } = await activityApi.list({ limit: MAX_ACTIVITIES_DISPLAY });

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
      // Story 14.5: Fetch from real backend API
      const stats = await dashboardApi.getStats();

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
    // Optimistic update
    set((state) => ({
      activities: state.activities.map((a) =>
        a.id === activityId ? { ...a, isRead: true } : a
      ),
    }));

    // Story 14.5: Sync with backend API (fire and forget - no await in action)
    activityApi.markRead(activityId).catch((error) => {
      // Revert on failure
      set((state) => ({
        activities: state.activities.map((a) =>
          a.id === activityId ? { ...a, isRead: false } : a
        ),
      }));
      console.error('Failed to mark activity as read:', error);
    });
  },

  markAllRead: () => {
    // Local-only operation: Marks all activities as read in the UI.
    // No backend sync - individual activities are marked read via markActivityRead()
    // when clicked. Bulk mark-all-read is UI-only for convenience.
    set((state) => ({
      activities: state.activities.map((a) => ({ ...a, isRead: true })),
    }));
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
