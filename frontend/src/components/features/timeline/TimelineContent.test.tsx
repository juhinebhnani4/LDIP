import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TooltipProvider } from '@/components/ui/tooltip';
import { TimelineContent, TimelineContentSkeleton } from './TimelineContent';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

// Mock the hooks
const mockEvents = [
  {
    id: 'evt-1',
    eventDate: '2024-01-15',
    eventDatePrecision: 'day' as const,
    eventDateText: null,
    eventType: 'filing' as const,
    description: 'Test event 1',
    documentId: null,
    sourcePage: null,
    confidence: 0.95,
    entities: [],
    isAmbiguous: false,
    isVerified: false,
  },
  {
    id: 'evt-2',
    eventDate: '2024-02-20',
    eventDatePrecision: 'day' as const,
    eventDateText: null,
    eventType: 'order' as const,
    description: 'Test event 2',
    documentId: null,
    sourcePage: null,
    confidence: 0.92,
    entities: [],
    isAmbiguous: false,
    isVerified: true,
  },
];

const mockStats = {
  totalEvents: 47,
  eventsByType: { filing: 12, order: 7 },
  entitiesInvolved: 24,
  dateRangeStart: '2016-05-15',
  dateRangeEnd: '2024-01-15',
  eventsWithEntities: 38,
  eventsWithoutEntities: 9,
  verifiedEvents: 18,
};

const mockUseTimeline = vi.fn(() => ({
  events: mockEvents,
  meta: { total: 2, page: 1, perPage: 50, totalPages: 1 },
  isLoading: false,
  isError: false,
  error: null,
  mutate: vi.fn(),
}));

const mockUseTimelineStats = vi.fn(() => ({
  stats: mockStats,
  isLoading: false,
  isError: false,
  error: null,
  mutate: vi.fn(),
}));

vi.mock('@/hooks/useTimeline', () => ({
  useTimeline: () => mockUseTimeline(),
}));

vi.mock('@/hooks/useTimelineStats', () => ({
  useTimelineStats: () => mockUseTimelineStats(),
}));

// Wrap with TooltipProvider for tests
function renderWithProvider(ui: React.ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('TimelineContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mocks to default behavior
    mockUseTimeline.mockReturnValue({
      events: mockEvents,
      meta: { total: 2, page: 1, perPage: 50, totalPages: 1 },
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });
    mockUseTimelineStats.mockReturnValue({
      stats: mockStats,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });
  });

  describe('rendering', () => {
    it('renders header and list', () => {
      renderWithProvider(<TimelineContent />);

      // Header should show stats
      expect(screen.getByText('47 events')).toBeInTheDocument();

      // List should show events
      expect(screen.getByTestId('timeline-event-evt-1')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-evt-2')).toBeInTheDocument();
    });

    it('has tabpanel role with proper attributes', () => {
      renderWithProvider(<TimelineContent />);

      const panel = screen.getByRole('tabpanel');
      expect(panel).toHaveAttribute('aria-labelledby', 'tab-timeline');
      expect(panel).toHaveAttribute('id', 'panel-timeline');
    });
  });

  describe('data fetching', () => {
    it('fetches timeline data using useTimeline hook', () => {
      renderWithProvider(<TimelineContent />);

      expect(mockUseTimeline).toHaveBeenCalled();
    });

    it('fetches timeline stats using useTimelineStats hook', () => {
      renderWithProvider(<TimelineContent />);

      expect(mockUseTimelineStats).toHaveBeenCalled();
    });
  });

  describe('loading state', () => {
    it('shows loading state when events are loading', () => {
      mockUseTimeline.mockReturnValue({
        events: [],
        meta: { total: 0, page: 1, perPage: 50, totalPages: 0 },
        isLoading: true,
        isError: false,
        error: null,
        mutate: vi.fn(),
      });

      const { container } = render(<TimelineContent />);

      // Should show skeletons
      const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('shows loading state when stats are loading', () => {
      mockUseTimelineStats.mockReturnValue({
        stats: { ...mockStats, totalEvents: 0 },
        isLoading: true,
        isError: false,
        error: null,
        mutate: vi.fn(),
      });

      const { container } = render(<TimelineContent />);

      // Header should show skeleton
      const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('error state', () => {
    it('shows error state when events fail to load', () => {
      mockUseTimeline.mockReturnValue({
        events: [],
        meta: { total: 0, page: 1, perPage: 50, totalPages: 0 },
        isLoading: false,
        isError: true,
        error: null,
        mutate: vi.fn(),
      });

      render(<TimelineContent />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Error')).toBeInTheDocument();
    });
  });

  describe('view mode', () => {
    it('defaults to list view mode', () => {
      renderWithProvider(<TimelineContent />);

      const listButton = screen.getByRole('button', { name: /list/i });
      expect(listButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('keeps list mode when list button clicked', async () => {
      const user = userEvent.setup();
      renderWithProvider(<TimelineContent />);

      const listButton = screen.getByRole('button', { name: /list/i });
      await user.click(listButton);

      expect(listButton).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const { container } = renderWithProvider(
        <TimelineContent className="custom-class" />
      );

      const panel = container.querySelector('.custom-class');
      expect(panel).toBeInTheDocument();
    });
  });
});

describe('TimelineContentSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<TimelineContentSkeleton />);

    const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('has tabpanel role', () => {
    render(<TimelineContentSkeleton />);

    expect(screen.getByRole('tabpanel')).toBeInTheDocument();
  });

  it('applies className prop', () => {
    const { container } = render(
      <TimelineContentSkeleton className="custom-class" />
    );

    const panel = container.querySelector('.custom-class');
    expect(panel).toBeInTheDocument();
  });
});
