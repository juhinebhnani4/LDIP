/**
 * Matter Store
 *
 * Zustand store for managing matters in the dashboard.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const matters = useMatterStore((state) => state.matters);
 *   const isLoading = useMatterStore((state) => state.isLoading);
 *   const fetchMatters = useMatterStore((state) => state.fetchMatters);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { matters, isLoading, fetchMatters } = useMatterStore();
 */

import { create } from 'zustand';
import type {
  MatterCardData,
  MatterSortOption,
  MatterFilterOption,
  MatterViewMode,
  Matter,
} from '@/types/matter';
import { VIEW_PREFERENCE_KEY } from '@/types/matter';
import { mattersApi } from '@/lib/api/matters';

/**
 * Transform backend Matter to frontend MatterCardData.
 * Fills in default values for fields the backend doesn't yet provide.
 * TODO: Remove defaults when backend provides these fields.
 */
function transformMatterToCardData(matter: Matter): MatterCardData {
  return {
    ...matter,
    // These fields are not yet provided by backend - use sensible defaults
    pageCount: 0,
    documentCount: 0,
    verificationPercent: 0,
    issueCount: 0,
    processingStatus: 'ready',
  };
}

/** Stale time in milliseconds - data older than this will be refetched */
const STALE_TIME_MS = 30_000; // 30 seconds

interface MatterState {
  /** All matters loaded from API */
  matters: MatterCardData[];

  /** Currently active matter in workspace (for workspace header - Story 10A.1) */
  currentMatter: MatterCardData | null;

  /** Loading state for fetching matters */
  isLoading: boolean;

  /** Error message if fetch fails */
  error: string | null;

  /** Current sort option */
  sortBy: MatterSortOption;

  /** Current filter option */
  filterBy: MatterFilterOption;

  /** Current view mode (grid/list) */
  viewMode: MatterViewMode;

  /** Timestamp of last successful fetch (for stale check) */
  lastFetchTime: number | null;
}

interface MatterActions {
  /** Fetch matters from API (skips if data is fresh) */
  fetchMatters: () => Promise<void>;

  /** Force refresh matters from API (ignores stale check) */
  forceRefreshMatters: () => Promise<void>;

  /** Fetch a single matter by ID for workspace (Story 10A.1) */
  fetchMatter: (matterId: string) => Promise<void>;

  /** Set current matter for workspace context (Story 10A.1) */
  setCurrentMatter: (matter: MatterCardData | null) => void;

  /** Update matter name (Story 10A.1) */
  updateMatterName: (matterId: string, name: string) => Promise<void>;

  /** Remove matter from local state after deletion */
  deleteMatter: (matterId: string) => void;

  /** Remove multiple matters from local state after bulk deletion */
  deleteMatters: (matterIds: string[]) => void;

  /** Update matter in local state (Story 3.1) */
  updateMatter: (matter: Matter) => void;

  /** Set sort option */
  setSortBy: (sortBy: MatterSortOption) => void;

  /** Set filter option */
  setFilterBy: (filterBy: MatterFilterOption) => void;

  /** Set view mode and persist to localStorage */
  setViewMode: (viewMode: MatterViewMode) => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Set error state */
  setError: (error: string | null) => void;

  /** Invalidate cache to force next fetch to reload */
  invalidateCache: () => void;
}

type MatterStore = MatterState & MatterActions;

/** Get initial view mode from localStorage */
function getInitialViewMode(): MatterViewMode {
  if (typeof window === 'undefined') return 'grid';
  const stored = localStorage.getItem(VIEW_PREFERENCE_KEY);
  return stored === 'list' ? 'list' : 'grid';
}

export const useMatterStore = create<MatterStore>()((set, get) => ({
  // Initial state
  matters: [],
  currentMatter: null,
  isLoading: false,
  error: null,
  sortBy: 'recent',
  filterBy: 'all',
  viewMode: 'grid', // Will be overwritten by initializeViewMode
  lastFetchTime: null,

  // Actions
  fetchMatters: async () => {
    const { matters, lastFetchTime, isLoading } = get();

    // Skip if already loading (prevent duplicate requests)
    if (isLoading) {
      return;
    }

    // Skip if data is fresh (not stale)
    const isFresh = lastFetchTime && Date.now() - lastFetchTime < STALE_TIME_MS;
    if (matters.length > 0 && isFresh) {
      return;
    }

    set({ isLoading: true, error: null });
    try {
      // Fetch from real backend API
      const { matters: apiMatters } = await mattersApi.list();

      // Transform to MatterCardData (add default values for fields backend doesn't provide yet)
      const transformedMatters = apiMatters.map(transformMatterToCardData);

      set({
        matters: transformedMatters,
        isLoading: false,
        lastFetchTime: Date.now(),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch matters';
      set({ error: message, isLoading: false });
    }
  },

  /**
   * Force refresh matters from API, ignoring stale check.
   * Use this when you know data has changed (e.g., after background processing).
   */
  forceRefreshMatters: async () => {
    const { isLoading } = get();

    // Skip if already loading
    if (isLoading) {
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const { matters: apiMatters } = await mattersApi.list();
      const transformedMatters = apiMatters.map(transformMatterToCardData);

      set({
        matters: transformedMatters,
        isLoading: false,
        lastFetchTime: Date.now(),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch matters';
      set({ error: message, isLoading: false });
    }
  },

  /**
   * Invalidate cache to force next fetchMatters() to reload.
   * Useful when you want to trigger a refresh on next component mount.
   */
  invalidateCache: () => {
    set({ lastFetchTime: null });
  },

  /**
   * Fetch a single matter by ID for workspace context (Story 10A.1).
   * First checks if matter exists in local state, otherwise fetches from API.
   */
  fetchMatter: async (matterId: string) => {
    const { matters } = get();

    // Check if matter is already in local state
    const existingMatter = matters.find((m) => m.id === matterId);
    if (existingMatter) {
      set({ currentMatter: existingMatter });
      return;
    }

    // Fetch from backend API
    try {
      const matterWithMembers = await mattersApi.get(matterId);
      const matterCardData = transformMatterToCardData(matterWithMembers);
      set({ currentMatter: matterCardData });
    } catch {
      // Create a placeholder matter for unknown IDs (handles 404 gracefully)
      const placeholderMatter: MatterCardData = {
        id: matterId,
        title: 'Untitled Matter',
        description: null,
        status: 'active',
        verificationMode: 'advisory',
        analysisMode: 'deep_analysis',
        practiceGroup: null,
        dataResidency: 'default',
        role: 'owner',
        memberCount: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        deletedAt: null,
        pageCount: 0,
        documentCount: 0,
        verificationPercent: 0,
        issueCount: 0,
        processingStatus: 'ready',
      };
      set({ currentMatter: placeholderMatter });
    }
  },

  /**
   * Set current matter for workspace context (Story 10A.1).
   */
  setCurrentMatter: (matter: MatterCardData | null) => {
    set({ currentMatter: matter });
  },

  /**
   * Update matter name (Story 10A.1).
   * Performs optimistic update and syncs with backend.
   */
  updateMatterName: async (matterId: string, name: string) => {
    const { matters, currentMatter } = get();

    // Optimistic update in matters list
    const updatedMatters = matters.map((m) =>
      m.id === matterId ? { ...m, title: name, updatedAt: new Date().toISOString() } : m
    );
    set({ matters: updatedMatters });

    // Optimistic update for current matter
    if (currentMatter?.id === matterId) {
      set({ currentMatter: { ...currentMatter, title: name, updatedAt: new Date().toISOString() } });
    }

    // Sync with backend
    try {
      await mattersApi.update(matterId, { title: name });
    } catch (error) {
      // Revert optimistic update on failure
      const { matters: currentMatters } = get();
      const revertedMatters = currentMatters.map((m) =>
        m.id === matterId ? { ...m, title: matters.find((om) => om.id === matterId)?.title ?? name } : m
      );
      set({ matters: revertedMatters });
      throw error;
    }
  },

  /**
   * Remove matter from local state after deletion.
   * Called after successful API deletion to update UI immediately.
   */
  deleteMatter: (matterId: string) => {
    const { matters, currentMatter } = get();

    // Remove from matters list
    const updatedMatters = matters.filter((m) => m.id !== matterId);
    set({ matters: updatedMatters });

    // Clear currentMatter if it was the deleted one
    if (currentMatter?.id === matterId) {
      set({ currentMatter: null });
    }
  },

  /**
   * Remove multiple matters from local state after bulk deletion.
   * Called after successful API bulk deletion to update UI immediately.
   */
  deleteMatters: (matterIds: string[]) => {
    const { matters, currentMatter } = get();
    const idsToDelete = new Set(matterIds);

    // Remove from matters list
    const updatedMatters = matters.filter((m) => !idsToDelete.has(m.id));
    set({ matters: updatedMatters });

    // Clear currentMatter if it was one of the deleted ones
    if (currentMatter && idsToDelete.has(currentMatter.id)) {
      set({ currentMatter: null });
    }
  },

  /**
   * Update matter in local state (Story 3.1).
   * Called after successful API update to sync UI immediately.
   */
  updateMatter: (matter: Matter) => {
    const { matters, currentMatter } = get();
    const matterCardData = transformMatterToCardData(matter);

    // Update in matters list
    const updatedMatters = matters.map((m) =>
      m.id === matter.id ? matterCardData : m
    );
    set({ matters: updatedMatters });

    // Update currentMatter if it was the updated one
    if (currentMatter?.id === matter.id) {
      set({ currentMatter: matterCardData });
    }
  },

  /**
   * Set sort option - sorting is performed client-side via selectors.
   * No loading state needed as matters are already in memory.
   */
  setSortBy: (sortBy: MatterSortOption) => {
    set({ sortBy });
  },

  /**
   * Set filter option - filtering is performed client-side via selectors.
   * No loading state needed as matters are already in memory.
   */
  setFilterBy: (filterBy: MatterFilterOption) => {
    set({ filterBy });
  },

  setViewMode: (viewMode: MatterViewMode) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(VIEW_PREFERENCE_KEY, viewMode);
    }
    set({ viewMode });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

/** Initialize view mode from localStorage (call on client mount) */
export function initializeViewMode(): void {
  const viewMode = getInitialViewMode();
  useMatterStore.setState({ viewMode });
}

// ============================================================================
// Selectors - use these for filtered/sorted matters
// ============================================================================

/** Selector for getting filtered matters */
export const selectFilteredMatters = (state: MatterStore): MatterCardData[] => {
  const { matters, filterBy } = state;

  switch (filterBy) {
    case 'processing':
      return matters.filter((m) => m.processingStatus === 'processing');
    case 'ready':
      return matters.filter((m) => m.processingStatus === 'ready' && m.status !== 'archived');
    case 'needs_attention':
      return matters.filter(
        (m) => m.issueCount > 0 || m.verificationPercent < 70
      );
    case 'archived':
      return matters.filter((m) => m.status === 'archived');
    case 'all':
    default:
      return matters.filter((m) => m.status !== 'archived');
  }
};

/** Selector for getting sorted matters (applies after filtering) */
export const selectSortedMatters = (state: MatterStore): MatterCardData[] => {
  const filtered = selectFilteredMatters(state);
  const { sortBy } = state;

  const sorted = [...filtered];

  switch (sortBy) {
    case 'alphabetical':
      return sorted.sort((a, b) => a.title.localeCompare(b.title));
    case 'most_pages':
      return sorted.sort((a, b) => b.pageCount - a.pageCount);
    case 'least_verified':
      return sorted.sort((a, b) => a.verificationPercent - b.verificationPercent);
    case 'date_created':
      return sorted.sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
    case 'recent':
    default:
      return sorted.sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
  }
};

/** Selector for getting matters count by status */
export const selectMatterCounts = (
  state: MatterStore
): { total: number; processing: number; ready: number; needsAttention: number } => {
  const { matters } = state;
  const nonArchived = matters.filter((m) => m.status !== 'archived');
  return {
    total: nonArchived.length,
    processing: nonArchived.filter((m) => m.processingStatus === 'processing').length,
    ready: nonArchived.filter((m) => m.processingStatus === 'ready').length,
    needsAttention: nonArchived.filter(
      (m) => m.issueCount > 0 || m.verificationPercent < 70
    ).length,
  };
};
