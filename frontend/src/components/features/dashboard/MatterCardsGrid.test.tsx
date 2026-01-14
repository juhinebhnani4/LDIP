import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { MatterCardData } from '@/types/matter';

// Mock the store module before importing the component
const mockFetchMatters = vi.fn();

interface MockState {
  matters: MatterCardData[];
  isLoading: boolean;
  error: string | null;
  sortBy: string;
  filterBy: string;
  viewMode: 'grid' | 'list';
}

vi.mock('@/stores/matterStore', () => {
  const create = vi.fn(() => {
    let state: MockState = {
      matters: [],
      isLoading: false,
      error: null,
      sortBy: 'recent',
      filterBy: 'all',
      viewMode: 'grid',
    };

    const store = (selector: (s: MockState) => unknown) => {
      return selector(state);
    };

    store.getState = () => ({
      ...state,
      fetchMatters: mockFetchMatters,
      setSortBy: vi.fn(),
      setFilterBy: vi.fn(),
      setViewMode: vi.fn(),
      setLoading: vi.fn(),
      setError: vi.fn(),
    });

    store.setState = (partial: Partial<MockState>) => {
      state = { ...state, ...partial };
    };

    store.subscribe = vi.fn();

    return store;
  });

  const useMatterStore = create();

  return {
    useMatterStore,
    selectSortedMatters: (s: { matters: MatterCardData[] }) => s.matters,
    initializeViewMode: vi.fn(),
  };
});

// Mock the MatterCard component
vi.mock('./MatterCard', () => ({
  MatterCard: ({ matter }: { matter: MatterCardData }) => (
    <div data-testid="matter-card">{matter.title}</div>
  ),
}));

// Import after mocks are set up
import { MatterCardsGrid } from './MatterCardsGrid';
import { useMatterStore } from '@/stores/matterStore';

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

const mockMatters: MatterCardData[] = [
  {
    id: '1',
    title: 'Matter One',
    description: null,
    status: 'active',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-03T00:00:00Z',
    role: 'owner',
    memberCount: 1,
    pageCount: 100,
    documentCount: 5,
    verificationPercent: 85,
    issueCount: 0,
    processingStatus: 'ready',
  },
  {
    id: '2',
    title: 'Matter Two',
    description: null,
    status: 'active',
    createdAt: '2026-01-02T00:00:00Z',
    updatedAt: '2026-01-02T00:00:00Z',
    role: 'owner',
    memberCount: 1,
    pageCount: 200,
    documentCount: 10,
    verificationPercent: 90,
    issueCount: 0,
    processingStatus: 'ready',
  },
];

describe('MatterCardsGrid', () => {
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
    mockFetchMatters.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeletons while fetching', () => {
    useMatterStore.setState({ isLoading: true });

    render(<MatterCardsGrid />);

    // Should show New Matter card + skeleton cards
    expect(screen.getByText('New Matter')).toBeInTheDocument();
  });

  it('renders New Matter card as first item', () => {
    useMatterStore.setState({ matters: mockMatters, isLoading: false });

    render(<MatterCardsGrid />);

    const newMatterLink = screen.getByRole('link', { name: /create new matter/i });
    expect(newMatterLink).toHaveAttribute('href', '/matter/new');
    expect(screen.getByText('New Matter')).toBeInTheDocument();
  });

  it('renders matter cards for each matter', () => {
    useMatterStore.setState({ matters: mockMatters, isLoading: false });

    render(<MatterCardsGrid />);

    expect(screen.getByText('Matter One')).toBeInTheDocument();
    expect(screen.getByText('Matter Two')).toBeInTheDocument();
  });

  it('renders empty state when no matters', () => {
    useMatterStore.setState({ matters: [], isLoading: false });

    render(<MatterCardsGrid />);

    expect(screen.getByText('No matters yet')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Create your first matter to start uploading documents and extracting insights.'
      )
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /create matter/i })).toBeInTheDocument();
  });

  it('renders error state with retry button', () => {
    useMatterStore.setState({ error: 'Network error', isLoading: false });

    render(<MatterCardsGrid />);

    expect(screen.getByText('Failed to load matters')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('uses grid layout when viewMode is grid', () => {
    useMatterStore.setState({ matters: mockMatters, isLoading: false, viewMode: 'grid' });

    const { container } = render(<MatterCardsGrid />);

    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('lg:grid-cols-3');
    expect(grid).toHaveClass('md:grid-cols-2');
  });

  it('uses single column layout when viewMode is list', () => {
    useMatterStore.setState({ matters: mockMatters, isLoading: false, viewMode: 'list' });

    const { container } = render(<MatterCardsGrid />);

    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('grid-cols-1');
    expect(grid).not.toHaveClass('lg:grid-cols-3');
  });

  it('fetches matters on mount', () => {
    render(<MatterCardsGrid />);

    // The component calls useMatterStore.getState().fetchMatters() in useEffect
    expect(mockFetchMatters).toHaveBeenCalled();
  });

  it('applies custom className when provided', () => {
    useMatterStore.setState({ matters: mockMatters, isLoading: false });

    const { container } = render(<MatterCardsGrid className="custom-class" />);

    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('custom-class');
  });
});
