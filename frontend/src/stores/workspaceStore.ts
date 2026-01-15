/**
 * Workspace Store
 *
 * Zustand store for workspace-specific state (tab counts, processing status).
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const tabCounts = useWorkspaceStore((state) => state.tabCounts);
 *   const tabProcessingStatus = useWorkspaceStore((state) => state.tabProcessingStatus);
 *   const fetchTabStats = useWorkspaceStore((state) => state.fetchTabStats);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { tabCounts, tabProcessingStatus, fetchTabStats } = useWorkspaceStore();
 *
 * Story 10A.2: Tab Bar Navigation
 */

import { create } from 'zustand';

/**
 * Tab ID type - must match route segments
 */
export type TabId =
  | 'summary'
  | 'timeline'
  | 'entities'
  | 'citations'
  | 'contradictions'
  | 'verification'
  | 'documents';

/**
 * Tab statistics for displaying counts and issues
 */
export interface TabStats {
  /** Number of items in this tab */
  count: number;
  /** Number of issues requiring attention */
  issueCount: number;
}

/**
 * Processing status for each tab
 */
export type TabProcessingStatus = 'ready' | 'processing';

interface WorkspaceState {
  /** Current matter ID for the workspace */
  currentMatterId: string | null;

  /** Tab statistics (counts, issues) */
  tabCounts: Partial<Record<TabId, TabStats>>;

  /** Processing status for each tab */
  tabProcessingStatus: Partial<Record<TabId, TabProcessingStatus>>;

  /** Loading state for tab stats fetch */
  isLoadingTabStats: boolean;

  /** Error message if tab stats fetch fails */
  tabStatsError: string | null;
}

interface WorkspaceActions {
  /** Set the current matter ID */
  setCurrentMatterId: (matterId: string | null) => void;

  /** Set stats for a single tab */
  setTabStats: (tabId: TabId, stats: TabStats) => void;

  /** Set processing status for a single tab */
  setTabProcessingStatus: (tabId: TabId, status: TabProcessingStatus) => void;

  /** Set all tab stats at once */
  setAllTabStats: (stats: Partial<Record<TabId, TabStats>>) => void;

  /** Set all tab processing statuses at once */
  setAllTabProcessingStatus: (statuses: Partial<Record<TabId, TabProcessingStatus>>) => void;

  /** Fetch tab stats from API (mock for MVP) */
  fetchTabStats: (matterId: string) => Promise<void>;

  /** Reset workspace state */
  resetWorkspace: () => void;
}

type WorkspaceStore = WorkspaceState & WorkspaceActions;

const initialState: WorkspaceState = {
  currentMatterId: null,
  tabCounts: {},
  tabProcessingStatus: {},
  isLoadingTabStats: false,
  tabStatsError: null,
};

export const useWorkspaceStore = create<WorkspaceStore>()((set, get) => ({
  ...initialState,

  setCurrentMatterId: (matterId) => {
    set({ currentMatterId: matterId });
  },

  setTabStats: (tabId, stats) => {
    set((state) => ({
      tabCounts: { ...state.tabCounts, [tabId]: stats },
    }));
  },

  setTabProcessingStatus: (tabId, status) => {
    set((state) => ({
      tabProcessingStatus: { ...state.tabProcessingStatus, [tabId]: status },
    }));
  },

  setAllTabStats: (stats) => {
    set({ tabCounts: stats });
  },

  setAllTabProcessingStatus: (statuses) => {
    set({ tabProcessingStatus: statuses });
  },

  fetchTabStats: async (matterId: string) => {
    // Skip if already loaded for this matter
    const { currentMatterId, isLoadingTabStats } = get();
    if (currentMatterId === matterId && !isLoadingTabStats) {
      // Check if we already have data
      const { tabCounts } = get();
      if (Object.keys(tabCounts).length > 0) {
        return;
      }
    }

    set({ isLoadingTabStats: true, tabStatsError: null, currentMatterId: matterId });

    try {
      // TODO: Replace with actual API call
      // GET /api/matters/{matter_id}/tab-stats

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 300));

      // Mock data for MVP
      set({
        tabCounts: {
          summary: { count: 1, issueCount: 0 },
          timeline: { count: 24, issueCount: 0 },
          entities: { count: 18, issueCount: 2 },
          citations: { count: 45, issueCount: 3 },
          contradictions: { count: 7, issueCount: 7 },
          verification: { count: 12, issueCount: 5 },
          documents: { count: 8, issueCount: 0 },
        },
        tabProcessingStatus: {
          summary: 'ready',
          timeline: 'ready',
          entities: 'ready',
          citations: 'ready',
          contradictions: 'ready',
          verification: 'ready',
          documents: 'ready',
        },
        isLoadingTabStats: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch tab stats';
      set({ tabStatsError: message, isLoadingTabStats: false });
    }
  },

  resetWorkspace: () => {
    set(initialState);
  },
}));

// ============================================================================
// Selectors - use these for derived state
// ============================================================================

/**
 * Selector for getting total issue count across all tabs
 */
export const selectTotalIssueCount = (state: WorkspaceStore): number => {
  const { tabCounts } = state;
  return Object.values(tabCounts).reduce(
    (total, stats) => total + (stats?.issueCount ?? 0),
    0
  );
};

/**
 * Selector for checking if any tab is processing
 */
export const selectIsAnyTabProcessing = (state: WorkspaceStore): boolean => {
  const { tabProcessingStatus } = state;
  return Object.values(tabProcessingStatus).some((status) => status === 'processing');
};

/**
 * Selector for getting count of tabs with issues
 */
export const selectTabsWithIssuesCount = (state: WorkspaceStore): number => {
  const { tabCounts } = state;
  return Object.values(tabCounts).filter(
    (stats) => stats && stats.issueCount > 0
  ).length;
};
