'use client';

/**
 * Split View Hook
 *
 * Custom hook for managing split-view citation highlighting.
 * Handles open/close state, keyboard shortcuts, and data loading.
 *
 * Story 3-4: Split-View Citation Highlighting
 */

import { useCallback, useEffect } from 'react';
import { useSplitViewStore } from '@/stores/splitViewStore';
import { getCitationSplitViewData } from '@/lib/api/citations';
import type { PdfViewerState } from '@/types/pdf';
import type { SplitViewData } from '@/types/citation';
import { PDF_KEYBOARD_SHORTCUTS } from '@/types/pdf';

interface UseSplitViewOptions {
  /** Enable keyboard shortcuts */
  enableKeyboardShortcuts?: boolean;
}

interface UseSplitViewReturn {
  /** Whether split view is open */
  isOpen: boolean;
  /** Whether in full screen mode */
  isFullScreen: boolean;
  /** Current citation ID */
  currentCitationId: string | null;
  /** Loaded split view data */
  splitViewData: SplitViewData | null;
  /** Loading state */
  isLoading: boolean;
  /** Error message */
  error: string | null;
  /** Source viewer state */
  sourceViewState: PdfViewerState;
  /** Target viewer state */
  targetViewState: PdfViewerState;
  /** Navigation info */
  navigationInfo: {
    currentIndex: number;
    totalCount: number;
    canPrev: boolean;
    canNext: boolean;
  };
  /** Open split view for a citation */
  openSplitView: (citationId: string, matterId: string) => Promise<void>;
  /** Close split view */
  closeSplitView: () => void;
  /** Toggle full screen mode */
  toggleFullScreen: () => void;
  /** Navigate to previous citation */
  navigateToPrev: () => void;
  /** Navigate to next citation */
  navigateToNext: () => void;
  /** Set citation IDs for navigation */
  setCitationIds: (ids: string[]) => void;
}

/**
 * Hook for managing split-view citation display.
 *
 * @param options - Configuration options
 * @returns Split view state and actions
 *
 * @example
 * ```tsx
 * const {
 *   isOpen,
 *   splitViewData,
 *   openSplitView,
 *   closeSplitView,
 * } = useSplitView({ enableKeyboardShortcuts: true });
 *
 * // Open split view for a citation
 * await openSplitView('citation-123', 'matter-456');
 * ```
 */
export function useSplitView(options: UseSplitViewOptions = {}): UseSplitViewReturn {
  const { enableKeyboardShortcuts = true } = options;

  // Use selectors to avoid unnecessary re-renders
  const isOpen = useSplitViewStore((state) => state.isOpen);
  const isFullScreen = useSplitViewStore((state) => state.isFullScreen);
  const currentCitationId = useSplitViewStore((state) => state.currentCitationId);
  const matterId = useSplitViewStore((state) => state.matterId);
  const splitViewData = useSplitViewStore((state) => state.splitViewData);
  const isLoading = useSplitViewStore((state) => state.isLoading);
  const error = useSplitViewStore((state) => state.error);
  const sourceViewState = useSplitViewStore((state) => state.sourceViewState);
  const targetViewState = useSplitViewStore((state) => state.targetViewState);
  const citationIds = useSplitViewStore((state) => state.citationIds);
  const currentIndex = useSplitViewStore((state) => state.currentIndex);

  // Actions
  const storeOpenSplitView = useSplitViewStore((state) => state.openSplitView);
  const storeCloseSplitView = useSplitViewStore((state) => state.closeSplitView);
  const storeToggleFullScreen = useSplitViewStore((state) => state.toggleFullScreen);
  const setSplitViewData = useSplitViewStore((state) => state.setSplitViewData);
  const setLoading = useSplitViewStore((state) => state.setLoading);
  const setError = useSplitViewStore((state) => state.setError);
  const storeCitationIds = useSplitViewStore((state) => state.setCitationIds);
  const storeNavigateToPrev = useSplitViewStore((state) => state.navigateToPrevCitation);
  const storeNavigateToNext = useSplitViewStore((state) => state.navigateToNextCitation);
  const setSourceZoom = useSplitViewStore((state) => state.setSourceZoom);
  const setTargetZoom = useSplitViewStore((state) => state.setTargetZoom);

  // Computed navigation info
  const navigationInfo = {
    currentIndex,
    totalCount: citationIds.length,
    canPrev: currentIndex > 0 && citationIds.length > 0,
    canNext: currentIndex < citationIds.length - 1 && citationIds.length > 0,
  };

  // Load split view data from API
  const loadSplitViewData = useCallback(async (citationId: string, mId: string) => {
    try {
      setLoading(true);
      const response = await getCitationSplitViewData(mId, citationId);
      setSplitViewData(response.data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load split view data';
      setError(message);
    }
  }, [setLoading, setSplitViewData, setError]);

  // Open split view and load data
  const openSplitView = useCallback(async (citationId: string, mId: string) => {
    storeOpenSplitView(citationId, mId);
    await loadSplitViewData(citationId, mId);
  }, [storeOpenSplitView, loadSplitViewData]);

  // Navigate to previous citation
  const navigateToPrev = useCallback(async () => {
    const newCitationId = storeNavigateToPrev();
    if (newCitationId && matterId) {
      await loadSplitViewData(newCitationId, matterId);
    }
  }, [storeNavigateToPrev, matterId, loadSplitViewData]);

  // Navigate to next citation
  const navigateToNext = useCallback(async () => {
    const newCitationId = storeNavigateToNext();
    if (newCitationId && matterId) {
      await loadSplitViewData(newCitationId, matterId);
    }
  }, [storeNavigateToNext, matterId, loadSplitViewData]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!enableKeyboardShortcuts || !isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't capture shortcuts when typing in inputs
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (event.key) {
        case PDF_KEYBOARD_SHORTCUTS.close:
          event.preventDefault();
          storeCloseSplitView();
          break;

        case PDF_KEYBOARD_SHORTCUTS.toggleFullscreen:
          event.preventDefault();
          storeToggleFullScreen();
          break;

        case PDF_KEYBOARD_SHORTCUTS.prevCitation:
          if (navigationInfo.canPrev) {
            event.preventDefault();
            navigateToPrev();
          }
          break;

        case PDF_KEYBOARD_SHORTCUTS.nextCitation:
          if (navigationInfo.canNext) {
            event.preventDefault();
            navigateToNext();
          }
          break;

        // Zoom shortcuts - apply to both panels simultaneously
        case PDF_KEYBOARD_SHORTCUTS.zoomIn:
        case PDF_KEYBOARD_SHORTCUTS.zoomInAlt:
          event.preventDefault();
          setSourceZoom(Math.min(sourceViewState.scale + 0.25, 3.0));
          setTargetZoom(Math.min(targetViewState.scale + 0.25, 3.0));
          break;

        case PDF_KEYBOARD_SHORTCUTS.zoomOut:
          event.preventDefault();
          setSourceZoom(Math.max(sourceViewState.scale - 0.25, 0.5));
          setTargetZoom(Math.max(targetViewState.scale - 0.25, 0.5));
          break;

        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [
    enableKeyboardShortcuts,
    isOpen,
    storeCloseSplitView,
    storeToggleFullScreen,
    navigationInfo.canPrev,
    navigationInfo.canNext,
    navigateToPrev,
    navigateToNext,
    setSourceZoom,
    setTargetZoom,
    sourceViewState.scale,
    targetViewState.scale,
  ]);

  return {
    isOpen,
    isFullScreen,
    currentCitationId,
    splitViewData,
    isLoading,
    error,
    sourceViewState,
    targetViewState,
    navigationInfo,
    openSplitView,
    closeSplitView: storeCloseSplitView,
    toggleFullScreen: storeToggleFullScreen,
    navigateToPrev,
    navigateToNext,
    setCitationIds: storeCitationIds,
  };
}
