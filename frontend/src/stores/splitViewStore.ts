/**
 * Split View Store
 *
 * Zustand store for managing split-view citation highlighting state.
 * Story 3-4: Split-View Citation Highlighting
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const isOpen = useSplitViewStore((state) => state.isOpen);
 *   const openSplitView = useSplitViewStore((state) => state.openSplitView);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { isOpen, openSplitView } = useSplitViewStore();
 */

import { create } from 'zustand';
import type { PdfViewerState } from '@/types/pdf';
import type { SplitViewData } from '@/types/citation';

// =============================================================================
// Store Types
// =============================================================================

interface SplitViewState {
  /** Whether the split view panel is open */
  isOpen: boolean;

  /** Whether the split view is in full screen modal mode */
  isFullScreen: boolean;

  /** Current citation ID being viewed */
  currentCitationId: string | null;

  /** Current matter ID for context */
  matterId: string | null;

  /** Loaded split view data for the current citation */
  splitViewData: SplitViewData | null;

  /** Loading state for split view data */
  isLoading: boolean;

  /** Error message if data loading failed */
  error: string | null;

  /** Viewer state for the source (left) panel */
  sourceViewState: PdfViewerState;

  /** Viewer state for the target (right) panel */
  targetViewState: PdfViewerState;

  /** List of all citation IDs for prev/next navigation */
  citationIds: string[];

  /** Current index in citationIds for navigation */
  currentIndex: number;
}

interface SplitViewActions {
  /** Open split view for a specific citation */
  openSplitView: (citationId: string, matterId: string) => void;

  /** Close the split view */
  closeSplitView: () => void;

  /** Toggle full screen mode */
  toggleFullScreen: () => void;

  /** Set split view data after loading */
  setSplitViewData: (data: SplitViewData) => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Set error state */
  setError: (error: string | null) => void;

  /** Update source panel page */
  setSourcePage: (page: number) => void;

  /** Update target panel page */
  setTargetPage: (page: number) => void;

  /** Update source panel zoom */
  setSourceZoom: (scale: number) => void;

  /** Update target panel zoom */
  setTargetZoom: (scale: number) => void;

  /** Update source panel scroll position */
  setSourceScroll: (position: { x: number; y: number }) => void;

  /** Update target panel scroll position */
  setTargetScroll: (position: { x: number; y: number }) => void;

  /** Set the list of citation IDs for navigation */
  setCitationIds: (ids: string[]) => void;

  /** Navigate to previous citation */
  navigateToPrevCitation: () => string | null;

  /** Navigate to next citation */
  navigateToNextCitation: () => string | null;

  /** Reset all state */
  reset: () => void;
}

type SplitViewStore = SplitViewState & SplitViewActions;

// =============================================================================
// Initial State
// =============================================================================

const DEFAULT_VIEWER_STATE: PdfViewerState = {
  currentPage: 1,
  scale: 1.0,
  scrollPosition: { x: 0, y: 0 },
};

const initialState: SplitViewState = {
  isOpen: false,
  isFullScreen: false,
  currentCitationId: null,
  matterId: null,
  splitViewData: null,
  isLoading: false,
  error: null,
  sourceViewState: { ...DEFAULT_VIEWER_STATE },
  targetViewState: { ...DEFAULT_VIEWER_STATE },
  citationIds: [],
  currentIndex: -1,
};

// =============================================================================
// Store Implementation
// =============================================================================

export const useSplitViewStore = create<SplitViewStore>()((set, get) => ({
  // Initial state
  ...initialState,

  // Actions
  openSplitView: (citationId: string, matterId: string) => {
    const { citationIds } = get();
    const currentIndex = citationIds.indexOf(citationId);

    set({
      isOpen: true,
      currentCitationId: citationId,
      matterId,
      isLoading: true,
      error: null,
      splitViewData: null,
      sourceViewState: { ...DEFAULT_VIEWER_STATE },
      targetViewState: { ...DEFAULT_VIEWER_STATE },
      currentIndex: currentIndex >= 0 ? currentIndex : -1,
    });
  },

  closeSplitView: () => {
    set({
      isOpen: false,
      isFullScreen: false,
      currentCitationId: null,
      splitViewData: null,
      isLoading: false,
      error: null,
    });
  },

  toggleFullScreen: () => {
    set((state) => ({ isFullScreen: !state.isFullScreen }));
  },

  setSplitViewData: (data: SplitViewData) => {
    set({
      splitViewData: data,
      isLoading: false,
      error: null,
      // Initialize viewer states with the correct pages
      sourceViewState: {
        ...DEFAULT_VIEWER_STATE,
        currentPage: data.sourceDocument.pageNumber,
      },
      targetViewState: {
        ...DEFAULT_VIEWER_STATE,
        currentPage: data.targetDocument?.pageNumber ?? 1,
      },
    });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  setError: (error: string | null) => {
    set({ error, isLoading: false });
  },

  setSourcePage: (page: number) => {
    set((state) => ({
      sourceViewState: { ...state.sourceViewState, currentPage: page },
    }));
  },

  setTargetPage: (page: number) => {
    set((state) => ({
      targetViewState: { ...state.targetViewState, currentPage: page },
    }));
  },

  setSourceZoom: (scale: number) => {
    set((state) => ({
      sourceViewState: { ...state.sourceViewState, scale },
    }));
  },

  setTargetZoom: (scale: number) => {
    set((state) => ({
      targetViewState: { ...state.targetViewState, scale },
    }));
  },

  setSourceScroll: (position: { x: number; y: number }) => {
    set((state) => ({
      sourceViewState: { ...state.sourceViewState, scrollPosition: position },
    }));
  },

  setTargetScroll: (position: { x: number; y: number }) => {
    set((state) => ({
      targetViewState: { ...state.targetViewState, scrollPosition: position },
    }));
  },

  setCitationIds: (ids: string[]) => {
    const { currentCitationId } = get();
    const currentIndex = currentCitationId ? ids.indexOf(currentCitationId) : -1;
    set({ citationIds: ids, currentIndex });
  },

  navigateToPrevCitation: () => {
    const { citationIds, currentIndex } = get();
    if (currentIndex <= 0 || citationIds.length === 0) {
      return null;
    }

    const newIndex = currentIndex - 1;
    const newCitationId = citationIds[newIndex];

    // Safety check - should never happen given the bounds check above
    if (!newCitationId) {
      return null;
    }

    set({
      currentIndex: newIndex,
      currentCitationId: newCitationId,
      isLoading: true,
      error: null,
      splitViewData: null,
    });

    return newCitationId;
  },

  navigateToNextCitation: () => {
    const { citationIds, currentIndex } = get();
    if (currentIndex >= citationIds.length - 1 || citationIds.length === 0) {
      return null;
    }

    const newIndex = currentIndex + 1;
    const newCitationId = citationIds[newIndex];

    // Safety check - should never happen given the bounds check above
    if (!newCitationId) {
      return null;
    }

    set({
      currentIndex: newIndex,
      currentCitationId: newCitationId,
      isLoading: true,
      error: null,
      splitViewData: null,
    });

    return newCitationId;
  },

  reset: () => {
    set(initialState);
  },
}));

// =============================================================================
// Selectors (for optimized re-renders)
// =============================================================================

/** Select whether split view is open */
export const selectIsOpen = (state: SplitViewStore) => state.isOpen;

/** Select whether in full screen mode */
export const selectIsFullScreen = (state: SplitViewStore) => state.isFullScreen;

/** Select current citation ID */
export const selectCurrentCitationId = (state: SplitViewStore) => state.currentCitationId;

/** Select split view data */
export const selectSplitViewData = (state: SplitViewStore) => state.splitViewData;

/** Select loading state */
export const selectIsLoading = (state: SplitViewStore) => state.isLoading;

/** Select error state */
export const selectError = (state: SplitViewStore) => state.error;

/** Select source viewer state */
export const selectSourceViewState = (state: SplitViewStore) => state.sourceViewState;

/** Select target viewer state */
export const selectTargetViewState = (state: SplitViewStore) => state.targetViewState;

/** Select whether navigation to previous citation is possible */
export const selectCanNavigatePrev = (state: SplitViewStore) =>
  state.currentIndex > 0 && state.citationIds.length > 0;

/** Select whether navigation to next citation is possible */
export const selectCanNavigateNext = (state: SplitViewStore) =>
  state.currentIndex < state.citationIds.length - 1 && state.citationIds.length > 0;

/** Select navigation info */
export const selectNavigationInfo = (state: SplitViewStore) => ({
  currentIndex: state.currentIndex,
  totalCount: state.citationIds.length,
  canPrev: state.currentIndex > 0 && state.citationIds.length > 0,
  canNext: state.currentIndex < state.citationIds.length - 1 && state.citationIds.length > 0,
});
