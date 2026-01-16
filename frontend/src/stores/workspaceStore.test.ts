import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act } from '@testing-library/react';
import {
  useWorkspaceStore,
  selectTotalIssueCount,
  selectIsAnyTabProcessing,
  selectTabsWithIssuesCount,
} from './workspaceStore';
import type { TabId, TabStats, TabProcessingStatus } from './workspaceStore';

// Story 14.12: Mock the tabStats API module
vi.mock('@/lib/api/tabStats', () => ({
  fetchTabStats: vi.fn(),
  transformTabStatsResponse: vi.fn((response) => ({
    tabCounts: response.data.tabCounts,
    tabProcessingStatus: response.data.tabProcessingStatus,
  })),
}));

import { fetchTabStats } from '@/lib/api/tabStats';
const mockFetchTabStats = vi.mocked(fetchTabStats);

// Mock API response data factory
const createMockApiResponse = () => ({
  data: {
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
      summary: 'ready' as const,
      timeline: 'ready' as const,
      entities: 'ready' as const,
      citations: 'ready' as const,
      contradictions: 'ready' as const,
      verification: 'ready' as const,
      documents: 'ready' as const,
    },
  },
});

describe('workspaceStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    act(() => {
      useWorkspaceStore.getState().resetWorkspace();
    });
    // Reset all mocks
    vi.clearAllMocks();
    // Setup default mock response
    mockFetchTabStats.mockResolvedValue(createMockApiResponse());
  });

  describe('Initial State', () => {
    it('has null currentMatterId initially', () => {
      const state = useWorkspaceStore.getState();
      expect(state.currentMatterId).toBeNull();
    });

    it('has empty tabCounts initially', () => {
      const state = useWorkspaceStore.getState();
      expect(state.tabCounts).toEqual({});
    });

    it('has empty tabProcessingStatus initially', () => {
      const state = useWorkspaceStore.getState();
      expect(state.tabProcessingStatus).toEqual({});
    });

    it('is not loading initially', () => {
      const state = useWorkspaceStore.getState();
      expect(state.isLoadingTabStats).toBe(false);
    });

    it('has no error initially', () => {
      const state = useWorkspaceStore.getState();
      expect(state.tabStatsError).toBeNull();
    });
  });

  describe('setCurrentMatterId', () => {
    it('sets the current matter ID', () => {
      act(() => {
        useWorkspaceStore.getState().setCurrentMatterId('matter-123');
      });

      expect(useWorkspaceStore.getState().currentMatterId).toBe('matter-123');
    });

    it('can clear the current matter ID', () => {
      act(() => {
        useWorkspaceStore.getState().setCurrentMatterId('matter-123');
        useWorkspaceStore.getState().setCurrentMatterId(null);
      });

      expect(useWorkspaceStore.getState().currentMatterId).toBeNull();
    });
  });

  describe('setTabStats', () => {
    it('sets stats for a single tab', () => {
      const stats: TabStats = { count: 10, issueCount: 2 };

      act(() => {
        useWorkspaceStore.getState().setTabStats('timeline', stats);
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabCounts.timeline).toEqual(stats);
    });

    it('preserves other tab stats when setting one', () => {
      const timelineStats: TabStats = { count: 10, issueCount: 2 };
      const entitiesStats: TabStats = { count: 20, issueCount: 0 };

      act(() => {
        useWorkspaceStore.getState().setTabStats('timeline', timelineStats);
        useWorkspaceStore.getState().setTabStats('entities', entitiesStats);
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabCounts.timeline).toEqual(timelineStats);
      expect(state.tabCounts.entities).toEqual(entitiesStats);
    });

    it('updates existing tab stats', () => {
      act(() => {
        useWorkspaceStore.getState().setTabStats('citations', { count: 5, issueCount: 1 });
        useWorkspaceStore.getState().setTabStats('citations', { count: 10, issueCount: 3 });
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabCounts.citations).toEqual({ count: 10, issueCount: 3 });
    });
  });

  describe('setTabProcessingStatus', () => {
    it('sets processing status for a single tab', () => {
      act(() => {
        useWorkspaceStore.getState().setTabProcessingStatus('entities', 'processing');
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabProcessingStatus.entities).toBe('processing');
    });

    it('preserves other tab statuses when setting one', () => {
      act(() => {
        useWorkspaceStore.getState().setTabProcessingStatus('timeline', 'ready');
        useWorkspaceStore.getState().setTabProcessingStatus('entities', 'processing');
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabProcessingStatus.timeline).toBe('ready');
      expect(state.tabProcessingStatus.entities).toBe('processing');
    });
  });

  describe('setAllTabStats', () => {
    it('sets all tab stats at once', () => {
      const allStats: Partial<Record<TabId, TabStats>> = {
        summary: { count: 1, issueCount: 0 },
        timeline: { count: 24, issueCount: 0 },
        citations: { count: 45, issueCount: 3 },
      };

      act(() => {
        useWorkspaceStore.getState().setAllTabStats(allStats);
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabCounts).toEqual(allStats);
    });

    it('replaces existing stats', () => {
      act(() => {
        useWorkspaceStore.getState().setTabStats('timeline', { count: 100, issueCount: 10 });
        useWorkspaceStore.getState().setAllTabStats({
          summary: { count: 1, issueCount: 0 },
        });
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabCounts.timeline).toBeUndefined();
      expect(state.tabCounts.summary).toEqual({ count: 1, issueCount: 0 });
    });
  });

  describe('setAllTabProcessingStatus', () => {
    it('sets all processing statuses at once', () => {
      const allStatuses: Partial<Record<TabId, TabProcessingStatus>> = {
        summary: 'ready',
        timeline: 'processing',
        entities: 'ready',
      };

      act(() => {
        useWorkspaceStore.getState().setAllTabProcessingStatus(allStatuses);
      });

      const state = useWorkspaceStore.getState();
      expect(state.tabProcessingStatus).toEqual(allStatuses);
    });
  });

  describe('fetchTabStats', () => {
    it('sets loading state while fetching', async () => {
      const fetchPromise = useWorkspaceStore.getState().fetchTabStats('matter-123');

      expect(useWorkspaceStore.getState().isLoadingTabStats).toBe(true);

      await fetchPromise;

      expect(useWorkspaceStore.getState().isLoadingTabStats).toBe(false);
    });

    it('sets currentMatterId when fetching', async () => {
      await useWorkspaceStore.getState().fetchTabStats('matter-456');

      expect(useWorkspaceStore.getState().currentMatterId).toBe('matter-456');
    });

    it('calls API with correct matter ID', async () => {
      await useWorkspaceStore.getState().fetchTabStats('matter-123');

      expect(mockFetchTabStats).toHaveBeenCalledWith('matter-123');
    });

    it('populates tab counts from API response', async () => {
      await useWorkspaceStore.getState().fetchTabStats('matter-123');

      const state = useWorkspaceStore.getState();
      expect(state.tabCounts.summary).toEqual({ count: 1, issueCount: 0 });
      expect(state.tabCounts.timeline).toEqual({ count: 24, issueCount: 0 });
      expect(state.tabCounts.entities).toEqual({ count: 18, issueCount: 2 });
      expect(state.tabCounts.citations).toEqual({ count: 45, issueCount: 3 });
      expect(state.tabCounts.contradictions).toEqual({ count: 7, issueCount: 7 });
      expect(state.tabCounts.verification).toEqual({ count: 12, issueCount: 5 });
      expect(state.tabCounts.documents).toEqual({ count: 8, issueCount: 0 });
    });

    it('populates tab processing status from API response', async () => {
      await useWorkspaceStore.getState().fetchTabStats('matter-123');

      const state = useWorkspaceStore.getState();
      expect(state.tabProcessingStatus.summary).toBe('ready');
      expect(state.tabProcessingStatus.timeline).toBe('ready');
      expect(state.tabProcessingStatus.documents).toBe('ready');
    });

    it('clears error on successful fetch', async () => {
      act(() => {
        useWorkspaceStore.setState({ tabStatsError: 'Previous error' });
      });

      await useWorkspaceStore.getState().fetchTabStats('matter-123');

      expect(useWorkspaceStore.getState().tabStatsError).toBeNull();
    });

    it('handles API error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockFetchTabStats.mockRejectedValue(new Error('Network error'));

      await useWorkspaceStore.getState().fetchTabStats('matter-123');

      const state = useWorkspaceStore.getState();
      expect(state.tabStatsError).toBe('Network error');
      expect(state.isLoadingTabStats).toBe(false);
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('skips fetch if data already loaded for same matter', async () => {
      // First fetch
      await useWorkspaceStore.getState().fetchTabStats('matter-123');
      mockFetchTabStats.mockClear();

      // Second fetch for same matter should skip
      await useWorkspaceStore.getState().fetchTabStats('matter-123');

      expect(mockFetchTabStats).not.toHaveBeenCalled();
    });

    it('fetches again for different matter', async () => {
      // First fetch
      await useWorkspaceStore.getState().fetchTabStats('matter-123');
      mockFetchTabStats.mockClear();

      // Reset to allow fetch for new matter
      act(() => {
        useWorkspaceStore.setState({ tabCounts: {} });
      });

      // Second fetch for different matter should proceed
      await useWorkspaceStore.getState().fetchTabStats('matter-456');

      expect(mockFetchTabStats).toHaveBeenCalledWith('matter-456');
    });
  });

  describe('resetWorkspace', () => {
    it('resets all state to initial values', () => {
      // Set some state first
      act(() => {
        useWorkspaceStore.getState().setCurrentMatterId('matter-123');
        useWorkspaceStore.getState().setTabStats('timeline', { count: 10, issueCount: 2 });
        useWorkspaceStore.getState().setTabProcessingStatus('entities', 'processing');
      });

      // Reset
      act(() => {
        useWorkspaceStore.getState().resetWorkspace();
      });

      const state = useWorkspaceStore.getState();
      expect(state.currentMatterId).toBeNull();
      expect(state.tabCounts).toEqual({});
      expect(state.tabProcessingStatus).toEqual({});
      expect(state.isLoadingTabStats).toBe(false);
      expect(state.tabStatsError).toBeNull();
    });
  });

  describe('Selectors', () => {
    describe('selectTotalIssueCount', () => {
      it('returns 0 when no tab counts', () => {
        const state = useWorkspaceStore.getState();
        expect(selectTotalIssueCount(state)).toBe(0);
      });

      it('sums issue counts across all tabs', () => {
        act(() => {
          useWorkspaceStore.getState().setAllTabStats({
            citations: { count: 45, issueCount: 3 },
            verification: { count: 12, issueCount: 5 },
            entities: { count: 18, issueCount: 2 },
          });
        });

        const state = useWorkspaceStore.getState();
        expect(selectTotalIssueCount(state)).toBe(10); // 3 + 5 + 2
      });

      it('handles tabs with zero issue counts', () => {
        act(() => {
          useWorkspaceStore.getState().setAllTabStats({
            summary: { count: 1, issueCount: 0 },
            citations: { count: 45, issueCount: 3 },
          });
        });

        const state = useWorkspaceStore.getState();
        expect(selectTotalIssueCount(state)).toBe(3);
      });
    });

    describe('selectIsAnyTabProcessing', () => {
      it('returns false when no processing status', () => {
        const state = useWorkspaceStore.getState();
        expect(selectIsAnyTabProcessing(state)).toBe(false);
      });

      it('returns false when all tabs are ready', () => {
        act(() => {
          useWorkspaceStore.getState().setAllTabProcessingStatus({
            summary: 'ready',
            timeline: 'ready',
            entities: 'ready',
          });
        });

        const state = useWorkspaceStore.getState();
        expect(selectIsAnyTabProcessing(state)).toBe(false);
      });

      it('returns true when at least one tab is processing', () => {
        act(() => {
          useWorkspaceStore.getState().setAllTabProcessingStatus({
            summary: 'ready',
            timeline: 'ready',
            entities: 'processing',
          });
        });

        const state = useWorkspaceStore.getState();
        expect(selectIsAnyTabProcessing(state)).toBe(true);
      });
    });

    describe('selectTabsWithIssuesCount', () => {
      it('returns 0 when no tab counts', () => {
        const state = useWorkspaceStore.getState();
        expect(selectTabsWithIssuesCount(state)).toBe(0);
      });

      it('counts tabs with issueCount > 0', () => {
        act(() => {
          useWorkspaceStore.getState().setAllTabStats({
            summary: { count: 1, issueCount: 0 },
            citations: { count: 45, issueCount: 3 },
            verification: { count: 12, issueCount: 5 },
            entities: { count: 18, issueCount: 0 },
          });
        });

        const state = useWorkspaceStore.getState();
        expect(selectTabsWithIssuesCount(state)).toBe(2); // citations and verification
      });
    });
  });
});
