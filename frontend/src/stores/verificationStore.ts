/**
 * Verification Store
 *
 * Zustand store for managing verification queue state.
 * Story 8-5: Verification Queue UI
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const queue = useVerificationStore((state) => state.queue);
 *   const selectedIds = useVerificationStore((state) => state.selectedIds);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { queue, selectedIds } = useVerificationStore();
 */

import { create } from 'zustand';
import type {
  VerificationQueueItem,
  VerificationStats,
  VerificationFilters,
  ConfidenceTier,
  VerificationView,
} from '@/types';
import { VerificationDecision } from '@/types';

// =============================================================================
// Store Types
// =============================================================================

interface VerificationState {
  /** Verification queue items */
  queue: VerificationQueueItem[];

  /** Verification statistics */
  stats: VerificationStats | null;

  /** Current filter state */
  filters: VerificationFilters;

  /** Selected verification IDs for bulk operations */
  selectedIds: string[];

  /** Loading state for queue */
  isLoading: boolean;

  /** Loading state for stats */
  isLoadingStats: boolean;

  /** Error message if any operation failed */
  error: string | null;

  /** Current matter ID */
  matterId: string | null;
}

interface VerificationActions {
  /** Set current matter ID */
  setMatterId: (matterId: string | null) => void;

  /** Set queue items */
  setQueue: (queue: VerificationQueueItem[]) => void;

  /** Set statistics */
  setStats: (stats: VerificationStats) => void;

  /** Update filter state */
  setFilters: (filters: Partial<VerificationFilters>) => void;

  /** Reset filters to defaults */
  resetFilters: () => void;

  /** Toggle selection of a single item */
  toggleSelected: (id: string) => void;

  /** Select all items by IDs */
  selectAll: (ids: string[]) => void;

  /** Clear all selections */
  clearSelection: () => void;

  /** Remove an item from queue (after action) */
  removeFromQueue: (id: string) => void;

  /** Remove multiple items from queue (after bulk action) */
  removeMultipleFromQueue: (ids: string[]) => void;

  /** Add item back to queue (for rollback on API failure) */
  addToQueue: (item: VerificationQueueItem) => void;

  /** Add multiple items back to queue (for rollback on API failure) */
  addMultipleToQueue: (items: VerificationQueueItem[]) => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Set stats loading state */
  setLoadingStats: (isLoadingStats: boolean) => void;

  /** Set error state */
  setError: (error: string | null) => void;

  /** Update a single queue item (for optimistic updates) */
  updateQueueItem: (id: string, updates: Partial<VerificationQueueItem>) => void;

  /** Reset all state */
  reset: () => void;
}

type VerificationStore = VerificationState & VerificationActions;

// =============================================================================
// Initial State
// =============================================================================

const DEFAULT_FILTERS: VerificationFilters = {
  findingType: null,
  confidenceTier: null,
  status: null,
  view: 'queue',
};

const initialState: VerificationState = {
  queue: [],
  stats: null,
  filters: { ...DEFAULT_FILTERS },
  selectedIds: [],
  isLoading: false,
  isLoadingStats: false,
  error: null,
  matterId: null,
};

// =============================================================================
// Store Implementation
// =============================================================================

export const useVerificationStore = create<VerificationStore>()((set, get) => ({
  // Initial state
  ...initialState,

  // Actions
  setMatterId: (matterId) => {
    const currentMatterId = get().matterId;
    // Reset state if matter changes
    if (currentMatterId !== matterId) {
      set({
        ...initialState,
        matterId,
      });
    } else {
      set({ matterId });
    }
  },

  setQueue: (queue) => set({ queue, error: null }),

  setStats: (stats) => set({ stats, error: null }),

  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
      // Clear selection when filters change
      selectedIds: [],
    })),

  resetFilters: () =>
    set({
      filters: { ...DEFAULT_FILTERS },
      selectedIds: [],
    }),

  toggleSelected: (id) =>
    set((state) => ({
      selectedIds: state.selectedIds.includes(id)
        ? state.selectedIds.filter((i) => i !== id)
        : [...state.selectedIds, id],
    })),

  selectAll: (ids) => set({ selectedIds: ids }),

  clearSelection: () => set({ selectedIds: [] }),

  removeFromQueue: (id) =>
    set((state) => ({
      queue: state.queue.filter((item) => item.id !== id),
      selectedIds: state.selectedIds.filter((i) => i !== id),
    })),

  removeMultipleFromQueue: (ids) =>
    set((state) => {
      const idSet = new Set(ids);
      return {
        queue: state.queue.filter((item) => !idSet.has(item.id)),
        selectedIds: state.selectedIds.filter((i) => !idSet.has(i)),
      };
    }),

  addToQueue: (item) =>
    set((state) => {
      // Avoid duplicates
      if (state.queue.some((i) => i.id === item.id)) {
        return state;
      }
      // Insert at beginning (most recently added)
      return { queue: [item, ...state.queue] };
    }),

  addMultipleToQueue: (items) =>
    set((state) => {
      const existingIds = new Set(state.queue.map((i) => i.id));
      const newItems = items.filter((item) => !existingIds.has(item.id));
      return { queue: [...newItems, ...state.queue] };
    }),

  setLoading: (isLoading) => set({ isLoading }),

  setLoadingStats: (isLoadingStats) => set({ isLoadingStats }),

  setError: (error) => set({ error, isLoading: false }),

  updateQueueItem: (id, updates) =>
    set((state) => ({
      queue: state.queue.map((item) =>
        item.id === id ? { ...item, ...updates } : item
      ),
    })),

  reset: () => set(initialState),
}));

// =============================================================================
// Selectors (for optimized re-renders)
// =============================================================================

/** Select queue items */
export const selectQueue = (state: VerificationStore) => state.queue;

/** Select stats */
export const selectStats = (state: VerificationStore) => state.stats;

/** Select filter state */
export const selectFilters = (state: VerificationStore) => state.filters;

/** Select selected IDs */
export const selectSelectedIds = (state: VerificationStore) => state.selectedIds;

/** Select loading state */
export const selectIsLoading = (state: VerificationStore) => state.isLoading;

/** Select stats loading state */
export const selectIsLoadingStats = (state: VerificationStore) => state.isLoadingStats;

/** Select error state */
export const selectError = (state: VerificationStore) => state.error;

/** Select matter ID */
export const selectMatterId = (state: VerificationStore) => state.matterId;

/** Select count of selected items */
export const selectSelectedCount = (state: VerificationStore) =>
  state.selectedIds.length;

/** Select whether any items are selected */
export const selectHasSelection = (state: VerificationStore) =>
  state.selectedIds.length > 0;

/** Select whether all visible items are selected */
export const selectAllSelected = (state: VerificationStore) =>
  state.queue.length > 0 && state.selectedIds.length === state.queue.length;

/** Select filtered queue based on current filters */
export const selectFilteredQueue = (state: VerificationStore) => {
  let filtered = state.queue;

  // Filter by finding type
  if (state.filters.findingType) {
    filtered = filtered.filter(
      (item) => item.findingType === state.filters.findingType
    );
  }

  // Filter by confidence tier
  if (state.filters.confidenceTier) {
    filtered = filtered.filter((item) => {
      const confidence = item.confidence;
      switch (state.filters.confidenceTier) {
        case 'high':
          return confidence > 90;
        case 'medium':
          return confidence > 70 && confidence <= 90;
        case 'low':
          return confidence <= 70;
        default:
          return true;
      }
    });
  }

  // Filter by status
  if (state.filters.status) {
    filtered = filtered.filter((item) => item.decision === state.filters.status);
  }

  return filtered;
};

/** Select verification completion percentage */
export const selectCompletionPercent = (state: VerificationStore) => {
  if (!state.stats || state.stats.totalVerifications === 0) {
    return 0;
  }
  const completed = state.stats.approvedCount + state.stats.rejectedCount;
  return Math.round((completed / state.stats.totalVerifications) * 100);
};

/** Select unique finding types from queue */
export const selectFindingTypes = (state: VerificationStore) => {
  const types = new Set(state.queue.map((item) => item.findingType));
  return Array.from(types).sort();
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get confidence tier from confidence value.
 */
export function getConfidenceTier(confidence: number): ConfidenceTier {
  if (confidence > 90) return 'high';
  if (confidence > 70) return 'medium';
  return 'low';
}

/**
 * Get confidence color class based on confidence value.
 * Per ADR-004: >90% green, 70-90% yellow, <70% red
 */
export function getConfidenceColorClass(confidence: number): string {
  if (confidence > 90) return 'bg-green-500';
  if (confidence > 70) return 'bg-yellow-500';
  return 'bg-red-500';
}

/**
 * Get confidence label based on tier.
 */
export function getConfidenceLabel(tier: ConfidenceTier): string {
  switch (tier) {
    case 'high':
      return 'High (>90%)';
    case 'medium':
      return 'Medium (70-90%)';
    case 'low':
      return 'Low (<70%)';
  }
}

/**
 * Format finding type for display.
 */
export function formatFindingType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Get icon for finding type.
 */
export function getFindingTypeIcon(type: string): string {
  const typeNormalized = type.toLowerCase();

  if (typeNormalized.includes('contradiction')) return '⚡';
  if (typeNormalized.includes('citation')) return '⚖️';
  if (typeNormalized.includes('timeline')) return '📅';
  if (typeNormalized.includes('entity')) return '👤';
  if (typeNormalized.includes('summary')) return '📋';

  return '📄';
}
