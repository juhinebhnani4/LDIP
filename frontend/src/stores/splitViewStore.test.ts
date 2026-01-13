/**
 * Split View Store Unit Tests
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #5)
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import { useSplitViewStore } from './splitViewStore';

describe('splitViewStore', () => {
  beforeEach(() => {
    // Reset store before each test
    act(() => {
      useSplitViewStore.getState().reset();
    });
  });

  describe('openSplitView', () => {
    it('sets isOpen to true', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
      });

      expect(useSplitViewStore.getState().isOpen).toBe(true);
    });

    it('sets currentCitationId', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
      });

      expect(useSplitViewStore.getState().currentCitationId).toBe('citation-123');
    });

    it('sets matterId', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
      });

      expect(useSplitViewStore.getState().matterId).toBe('matter-456');
    });

    it('sets isLoading to true', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
      });

      expect(useSplitViewStore.getState().isLoading).toBe(true);
    });

    it('resets error to null', () => {
      // First set an error
      act(() => {
        useSplitViewStore.getState().setError('Some error');
      });
      expect(useSplitViewStore.getState().error).toBe('Some error');

      // Then open split view
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
      });

      expect(useSplitViewStore.getState().error).toBeNull();
    });
  });

  describe('closeSplitView', () => {
    it('sets isOpen to false', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
        useSplitViewStore.getState().closeSplitView();
      });

      expect(useSplitViewStore.getState().isOpen).toBe(false);
    });

    it('clears currentCitationId', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
        useSplitViewStore.getState().closeSplitView();
      });

      expect(useSplitViewStore.getState().currentCitationId).toBeNull();
    });

    it('clears splitViewData', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
        useSplitViewStore.getState().closeSplitView();
      });

      expect(useSplitViewStore.getState().splitViewData).toBeNull();
    });
  });

  describe('toggleFullScreen', () => {
    it('toggles isFullScreen from false to true', () => {
      expect(useSplitViewStore.getState().isFullScreen).toBe(false);

      act(() => {
        useSplitViewStore.getState().toggleFullScreen();
      });

      expect(useSplitViewStore.getState().isFullScreen).toBe(true);
    });

    it('toggles isFullScreen from true to false', () => {
      act(() => {
        useSplitViewStore.getState().toggleFullScreen();
      });
      expect(useSplitViewStore.getState().isFullScreen).toBe(true);

      act(() => {
        useSplitViewStore.getState().toggleFullScreen();
      });

      expect(useSplitViewStore.getState().isFullScreen).toBe(false);
    });
  });

  describe('navigation', () => {
    beforeEach(() => {
      // Set up citation list
      act(() => {
        useSplitViewStore.getState().setCitationIds([
          'citation-1',
          'citation-2',
          'citation-3',
        ]);
        useSplitViewStore.getState().openSplitView('citation-2', 'matter-456');
      });
    });

    it('setCitationIds sets the list and updates currentIndex', () => {
      expect(useSplitViewStore.getState().citationIds).toEqual([
        'citation-1',
        'citation-2',
        'citation-3',
      ]);
      expect(useSplitViewStore.getState().currentIndex).toBe(1); // citation-2 is at index 1
    });

    it('navigateToPrevCitation moves to previous citation', () => {
      act(() => {
        useSplitViewStore.getState().navigateToPrevCitation();
      });

      expect(useSplitViewStore.getState().currentCitationId).toBe('citation-1');
      expect(useSplitViewStore.getState().currentIndex).toBe(0);
    });

    it('navigateToPrevCitation returns null at first citation', () => {
      act(() => {
        useSplitViewStore.getState().navigateToPrevCitation();
      });
      // Now at first citation

      let result: string | null = 'not-null';
      act(() => {
        result = useSplitViewStore.getState().navigateToPrevCitation();
      });

      expect(result).toBeNull();
    });

    it('navigateToNextCitation moves to next citation', () => {
      act(() => {
        useSplitViewStore.getState().navigateToNextCitation();
      });

      expect(useSplitViewStore.getState().currentCitationId).toBe('citation-3');
      expect(useSplitViewStore.getState().currentIndex).toBe(2);
    });

    it('navigateToNextCitation returns null at last citation', () => {
      act(() => {
        useSplitViewStore.getState().navigateToNextCitation();
      });
      // Now at last citation

      let result: string | null = 'not-null';
      act(() => {
        result = useSplitViewStore.getState().navigateToNextCitation();
      });

      expect(result).toBeNull();
    });
  });

  describe('viewer state', () => {
    it('setSourcePage updates source page', () => {
      act(() => {
        useSplitViewStore.getState().setSourcePage(5);
      });

      expect(useSplitViewStore.getState().sourceViewState.currentPage).toBe(5);
    });

    it('setTargetPage updates target page', () => {
      act(() => {
        useSplitViewStore.getState().setTargetPage(10);
      });

      expect(useSplitViewStore.getState().targetViewState.currentPage).toBe(10);
    });

    it('setSourceZoom updates source scale', () => {
      act(() => {
        useSplitViewStore.getState().setSourceZoom(1.5);
      });

      expect(useSplitViewStore.getState().sourceViewState.scale).toBe(1.5);
    });

    it('setTargetZoom updates target scale', () => {
      act(() => {
        useSplitViewStore.getState().setTargetZoom(2.0);
      });

      expect(useSplitViewStore.getState().targetViewState.scale).toBe(2.0);
    });
  });

  describe('setError', () => {
    it('sets error message', () => {
      act(() => {
        useSplitViewStore.getState().setError('Failed to load');
      });

      expect(useSplitViewStore.getState().error).toBe('Failed to load');
    });

    it('sets isLoading to false', () => {
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
      });
      expect(useSplitViewStore.getState().isLoading).toBe(true);

      act(() => {
        useSplitViewStore.getState().setError('Failed to load');
      });

      expect(useSplitViewStore.getState().isLoading).toBe(false);
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', () => {
      // Set some state
      act(() => {
        useSplitViewStore.getState().openSplitView('citation-123', 'matter-456');
        useSplitViewStore.getState().toggleFullScreen();
        useSplitViewStore.getState().setSourcePage(10);
      });

      // Reset
      act(() => {
        useSplitViewStore.getState().reset();
      });

      const state = useSplitViewStore.getState();
      expect(state.isOpen).toBe(false);
      expect(state.isFullScreen).toBe(false);
      expect(state.currentCitationId).toBeNull();
      expect(state.matterId).toBeNull();
      expect(state.sourceViewState.currentPage).toBe(1);
    });
  });
});
