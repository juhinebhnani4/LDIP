import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  useMatterStore,
  selectFilteredMatters,
  selectSortedMatters,
  selectMatterCounts,
  initializeViewMode,
} from './matterStore';
import type { MatterCardData } from '@/types/matter';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('matterStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useMatterStore.setState({
      matters: [],
      isLoading: false,
      error: null,
      sortBy: 'recent',
      filterBy: 'all',
      viewMode: 'grid',
    });
    localStorageMock.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchMatters', () => {
    it('sets loading state while fetching', async () => {
      const fetchPromise = useMatterStore.getState().fetchMatters();

      expect(useMatterStore.getState().isLoading).toBe(true);

      await fetchPromise;

      expect(useMatterStore.getState().isLoading).toBe(false);
    });

    it('populates matters after fetch', async () => {
      await useMatterStore.getState().fetchMatters();

      const state = useMatterStore.getState();
      expect(state.matters.length).toBeGreaterThan(0);
    });

    it('clears error state on successful fetch', async () => {
      useMatterStore.setState({ error: 'Previous error' });

      await useMatterStore.getState().fetchMatters();

      expect(useMatterStore.getState().error).toBeNull();
    });

    it('fetches matters with expected properties', async () => {
      await useMatterStore.getState().fetchMatters();

      const matter = useMatterStore.getState().matters[0];
      expect(matter).toHaveProperty('id');
      expect(matter).toHaveProperty('title');
      expect(matter).toHaveProperty('pageCount');
      expect(matter).toHaveProperty('documentCount');
      expect(matter).toHaveProperty('verificationPercent');
      expect(matter).toHaveProperty('processingStatus');
    });
  });

  describe('setSortBy', () => {
    it('updates sort option', () => {
      useMatterStore.getState().setSortBy('alphabetical');
      expect(useMatterStore.getState().sortBy).toBe('alphabetical');

      useMatterStore.getState().setSortBy('most_pages');
      expect(useMatterStore.getState().sortBy).toBe('most_pages');
    });
  });

  describe('setFilterBy', () => {
    it('updates filter option', () => {
      useMatterStore.getState().setFilterBy('processing');
      expect(useMatterStore.getState().filterBy).toBe('processing');

      useMatterStore.getState().setFilterBy('ready');
      expect(useMatterStore.getState().filterBy).toBe('ready');
    });
  });

  describe('setViewMode', () => {
    it('updates view mode', () => {
      useMatterStore.getState().setViewMode('list');
      expect(useMatterStore.getState().viewMode).toBe('list');

      useMatterStore.getState().setViewMode('grid');
      expect(useMatterStore.getState().viewMode).toBe('grid');
    });

    it('persists view mode to localStorage', () => {
      useMatterStore.getState().setViewMode('list');
      expect(localStorageMock.getItem('dashboard_view_preference')).toBe('list');

      useMatterStore.getState().setViewMode('grid');
      expect(localStorageMock.getItem('dashboard_view_preference')).toBe('grid');
    });
  });

  describe('initializeViewMode', () => {
    it('initializes view mode from localStorage', () => {
      localStorageMock.setItem('dashboard_view_preference', 'list');

      initializeViewMode();

      expect(useMatterStore.getState().viewMode).toBe('list');
    });

    it('defaults to grid if no localStorage value', () => {
      initializeViewMode();

      expect(useMatterStore.getState().viewMode).toBe('grid');
    });
  });

  describe('setLoading', () => {
    it('sets loading state', () => {
      useMatterStore.getState().setLoading(true);
      expect(useMatterStore.getState().isLoading).toBe(true);

      useMatterStore.getState().setLoading(false);
      expect(useMatterStore.getState().isLoading).toBe(false);
    });
  });

  describe('setError', () => {
    it('sets error state', () => {
      useMatterStore.getState().setError('Test error');
      expect(useMatterStore.getState().error).toBe('Test error');

      useMatterStore.getState().setError(null);
      expect(useMatterStore.getState().error).toBeNull();
    });
  });

  describe('selectFilteredMatters', () => {
    const mockMatters: MatterCardData[] = [
      {
        id: '1',
        title: 'Processing Matter',
        description: null,
        status: 'active',
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 100,
        documentCount: 5,
        verificationPercent: 0,
        issueCount: 0,
        processingStatus: 'processing',
        processingProgress: 50,
      },
      {
        id: '2',
        title: 'Ready Matter',
        description: null,
        status: 'active',
        createdAt: '2026-01-02T00:00:00Z',
        updatedAt: '2026-01-02T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 200,
        documentCount: 10,
        verificationPercent: 90,
        issueCount: 0,
        processingStatus: 'ready',
      },
      {
        id: '3',
        title: 'Needs Attention Matter',
        description: null,
        status: 'active',
        createdAt: '2026-01-03T00:00:00Z',
        updatedAt: '2026-01-03T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 300,
        documentCount: 15,
        verificationPercent: 60,
        issueCount: 5,
        processingStatus: 'needs_attention',
      },
      {
        id: '4',
        title: 'Archived Matter',
        description: null,
        status: 'archived',
        createdAt: '2026-01-04T00:00:00Z',
        updatedAt: '2026-01-04T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 400,
        documentCount: 20,
        verificationPercent: 100,
        issueCount: 0,
        processingStatus: 'ready',
      },
    ];

    beforeEach(() => {
      useMatterStore.setState({ matters: mockMatters });
    });

    it('filters by processing status', () => {
      useMatterStore.setState({ filterBy: 'processing' });
      const filtered = selectFilteredMatters(useMatterStore.getState());
      expect(filtered.length).toBe(1);
      expect(filtered[0]?.processingStatus).toBe('processing');
    });

    it('filters by ready status', () => {
      useMatterStore.setState({ filterBy: 'ready' });
      const filtered = selectFilteredMatters(useMatterStore.getState());
      expect(filtered.length).toBe(1);
      expect(filtered[0]?.processingStatus).toBe('ready');
      expect(filtered[0]?.status).not.toBe('archived');
    });

    it('filters by needs_attention', () => {
      useMatterStore.setState({ filterBy: 'needs_attention' });
      const filtered = selectFilteredMatters(useMatterStore.getState());
      // Includes Processing Matter (verificationPercent: 0) and Needs Attention Matter (verificationPercent: 60, issueCount: 5)
      expect(filtered.length).toBe(2);
      expect(filtered.every((m) => m.issueCount > 0 || m.verificationPercent < 70)).toBe(true);
    });

    it('filters by archived', () => {
      useMatterStore.setState({ filterBy: 'archived' });
      const filtered = selectFilteredMatters(useMatterStore.getState());
      expect(filtered.length).toBe(1);
      expect(filtered[0]?.status).toBe('archived');
    });

    it('shows all non-archived when filter is all', () => {
      useMatterStore.setState({ filterBy: 'all' });
      const filtered = selectFilteredMatters(useMatterStore.getState());
      expect(filtered.length).toBe(3);
      expect(filtered.every((m) => m.status !== 'archived')).toBe(true);
    });
  });

  describe('selectSortedMatters', () => {
    const mockMatters: MatterCardData[] = [
      {
        id: '1',
        title: 'Zebra Matter',
        description: null,
        status: 'active',
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-03T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 100,
        documentCount: 5,
        verificationPercent: 50,
        issueCount: 0,
        processingStatus: 'ready',
      },
      {
        id: '2',
        title: 'Alpha Matter',
        description: null,
        status: 'active',
        createdAt: '2026-01-03T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 300,
        documentCount: 15,
        verificationPercent: 90,
        issueCount: 0,
        processingStatus: 'ready',
      },
      {
        id: '3',
        title: 'Middle Matter',
        description: null,
        status: 'active',
        createdAt: '2026-01-02T00:00:00Z',
        updatedAt: '2026-01-02T00:00:00Z',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 200,
        documentCount: 10,
        verificationPercent: 70,
        issueCount: 0,
        processingStatus: 'ready',
      },
    ];

    beforeEach(() => {
      useMatterStore.setState({ matters: mockMatters, filterBy: 'all' });
    });

    it('sorts by recent (updatedAt desc)', () => {
      useMatterStore.setState({ sortBy: 'recent' });
      const sorted = selectSortedMatters(useMatterStore.getState());
      expect(sorted[0]?.title).toBe('Zebra Matter');
      expect(sorted[2]?.title).toBe('Alpha Matter');
    });

    it('sorts alphabetically', () => {
      useMatterStore.setState({ sortBy: 'alphabetical' });
      const sorted = selectSortedMatters(useMatterStore.getState());
      expect(sorted[0]?.title).toBe('Alpha Matter');
      expect(sorted[2]?.title).toBe('Zebra Matter');
    });

    it('sorts by most pages', () => {
      useMatterStore.setState({ sortBy: 'most_pages' });
      const sorted = selectSortedMatters(useMatterStore.getState());
      expect(sorted[0]?.pageCount).toBe(300);
      expect(sorted[2]?.pageCount).toBe(100);
    });

    it('sorts by least verified', () => {
      useMatterStore.setState({ sortBy: 'least_verified' });
      const sorted = selectSortedMatters(useMatterStore.getState());
      expect(sorted[0]?.verificationPercent).toBe(50);
      expect(sorted[2]?.verificationPercent).toBe(90);
    });

    it('sorts by date created', () => {
      useMatterStore.setState({ sortBy: 'date_created' });
      const sorted = selectSortedMatters(useMatterStore.getState());
      expect(sorted[0]?.title).toBe('Alpha Matter');
      expect(sorted[2]?.title).toBe('Zebra Matter');
    });
  });

  describe('selectMatterCounts', () => {
    const mockMatters: MatterCardData[] = [
      {
        id: '1',
        title: 'Processing',
        description: null,
        status: 'active',
        createdAt: '',
        updatedAt: '',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 100,
        documentCount: 5,
        verificationPercent: 0,
        issueCount: 0,
        processingStatus: 'processing',
      },
      {
        id: '2',
        title: 'Ready 1',
        description: null,
        status: 'active',
        createdAt: '',
        updatedAt: '',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 200,
        documentCount: 10,
        verificationPercent: 90,
        issueCount: 0,
        processingStatus: 'ready',
      },
      {
        id: '3',
        title: 'Ready 2',
        description: null,
        status: 'active',
        createdAt: '',
        updatedAt: '',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 300,
        documentCount: 15,
        verificationPercent: 80,
        issueCount: 0,
        processingStatus: 'ready',
      },
      {
        id: '4',
        title: 'Needs Attention',
        description: null,
        status: 'active',
        createdAt: '',
        updatedAt: '',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 400,
        documentCount: 20,
        verificationPercent: 60,
        issueCount: 3,
        processingStatus: 'needs_attention',
      },
      {
        id: '5',
        title: 'Archived',
        description: null,
        status: 'archived',
        createdAt: '',
        updatedAt: '',
        deletedAt: null,
        role: 'owner',
        memberCount: 1,
        pageCount: 500,
        documentCount: 25,
        verificationPercent: 100,
        issueCount: 0,
        processingStatus: 'ready',
      },
    ];

    beforeEach(() => {
      useMatterStore.setState({ matters: mockMatters });
    });

    it('returns correct counts', () => {
      const counts = selectMatterCounts(useMatterStore.getState());
      expect(counts.total).toBe(4); // excludes archived
      expect(counts.processing).toBe(1);
      expect(counts.ready).toBe(2);
      // Processing matter also counts (verificationPercent: 0) + Needs Attention matter
      expect(counts.needsAttention).toBe(2);
    });
  });
});
