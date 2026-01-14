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
} from '@/types/matter';
import { VIEW_PREFERENCE_KEY } from '@/types/matter';

/** Generate unique ID for mock matters */
function generateMatterId(): string {
  return `matter_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

interface MatterState {
  /** All matters loaded from API */
  matters: MatterCardData[];

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
}

interface MatterActions {
  /** Fetch matters from API (or use mock data for now) */
  fetchMatters: () => Promise<void>;

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
}

type MatterStore = MatterState & MatterActions;

/** Get initial view mode from localStorage */
function getInitialViewMode(): MatterViewMode {
  if (typeof window === 'undefined') return 'grid';
  const stored = localStorage.getItem(VIEW_PREFERENCE_KEY);
  return stored === 'list' ? 'list' : 'grid';
}

/** Mock matters for development (backend API not yet providing all fields) */
function getMockMatters(): MatterCardData[] {
  const now = new Date();
  return [
    {
      id: generateMatterId(),
      title: 'Shah v. Mehta',
      description: 'Property dispute case regarding commercial premises',
      status: 'active',
      createdAt: new Date(now.getTime() - 30 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 2 * 60 * 60000).toISOString(),
      role: 'owner',
      memberCount: 3,
      pageCount: 1247,
      documentCount: 89,
      verificationPercent: 85,
      issueCount: 3,
      processingStatus: 'ready',
      lastOpened: new Date(now.getTime() - 2 * 60 * 60000).toISOString(),
    },
    {
      id: generateMatterId(),
      title: 'SEBI v. Parekh',
      description: 'Securities fraud investigation',
      status: 'active',
      createdAt: new Date(now.getTime() - 7 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 5 * 60000).toISOString(),
      role: 'editor',
      memberCount: 5,
      pageCount: 2100,
      documentCount: 156,
      verificationPercent: 0,
      issueCount: 0,
      processingStatus: 'processing',
      processingProgress: 67,
      estimatedTimeRemaining: 180,
    },
    {
      id: generateMatterId(),
      title: 'Reliance v. BPCL',
      description: 'Contract dispute over gas pipeline rights',
      status: 'active',
      createdAt: new Date(now.getTime() - 60 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 24 * 60 * 60000).toISOString(),
      role: 'owner',
      memberCount: 2,
      pageCount: 892,
      documentCount: 45,
      verificationPercent: 62,
      issueCount: 8,
      processingStatus: 'needs_attention',
      lastOpened: new Date(now.getTime() - 24 * 60 * 60000).toISOString(),
    },
    {
      id: generateMatterId(),
      title: 'Tata v. Mistry',
      description: 'Corporate governance dispute',
      status: 'active',
      createdAt: new Date(now.getTime() - 90 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 48 * 60 * 60000).toISOString(),
      role: 'viewer',
      memberCount: 8,
      pageCount: 3456,
      documentCount: 210,
      verificationPercent: 94,
      issueCount: 1,
      processingStatus: 'ready',
      lastOpened: new Date(now.getTime() - 48 * 60 * 60000).toISOString(),
    },
    {
      id: generateMatterId(),
      title: 'Infosys IP Matter',
      description: 'Intellectual property licensing dispute',
      status: 'archived',
      createdAt: new Date(now.getTime() - 180 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 30 * 24 * 60 * 60000).toISOString(),
      role: 'owner',
      memberCount: 2,
      pageCount: 567,
      documentCount: 32,
      verificationPercent: 100,
      issueCount: 0,
      processingStatus: 'ready',
      lastOpened: new Date(now.getTime() - 30 * 24 * 60 * 60000).toISOString(),
    },
  ];
}

export const useMatterStore = create<MatterStore>()((set) => ({
  // Initial state
  matters: [],
  isLoading: false,
  error: null,
  sortBy: 'recent',
  filterBy: 'all',
  viewMode: 'grid', // Will be overwritten by initializeViewMode

  // Actions
  fetchMatters: async () => {
    set({ isLoading: true, error: null });
    try {
      // TODO: Replace with actual API call when backend provides extended fields
      // const response = await fetch('/api/matters');
      // const { data } = await response.json();
      // Then extend with mock data for missing fields

      // Using mock data for now
      await new Promise((resolve) => setTimeout(resolve, 400)); // Simulate network delay
      const matters = getMockMatters();

      set({
        matters,
        isLoading: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch matters';
      set({ error: message, isLoading: false });
    }
  },

  setSortBy: (sortBy: MatterSortOption) => {
    set({ sortBy });
  },

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
