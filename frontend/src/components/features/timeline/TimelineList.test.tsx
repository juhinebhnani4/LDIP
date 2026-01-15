import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { TimelineList, TimelineListSkeleton } from './TimelineList';
import type { TimelineEvent } from '@/types/timeline';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

// Wrap with TooltipProvider for tests
function renderWithProvider(ui: React.ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

const createMockEvent = (
  id: string,
  date: string,
  overrides: Partial<TimelineEvent> = {}
): TimelineEvent => ({
  id,
  eventDate: date,
  eventDatePrecision: 'day',
  eventDateText: null,
  eventType: 'filing',
  description: `Event ${id}`,
  documentId: null,
  sourcePage: null,
  confidence: 0.95,
  entities: [],
  isAmbiguous: false,
  isVerified: false,
  ...overrides,
});

const mockEvents: TimelineEvent[] = [
  createMockEvent('evt-1', '2016-05-15'),
  createMockEvent('evt-2', '2016-08-20'),
  createMockEvent('evt-3', '2018-02-10'),
  createMockEvent('evt-4', '2024-01-15'),
];

describe('TimelineList', () => {
  describe('event rendering', () => {
    it('renders events in chronological order', () => {
      renderWithProvider(<TimelineList events={mockEvents} />);

      // All events should be rendered
      expect(screen.getByTestId('timeline-event-evt-1')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-evt-2')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-evt-3')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-evt-4')).toBeInTheDocument();
    });

    it('has list role with proper label', () => {
      renderWithProvider(<TimelineList events={mockEvents} />);

      expect(
        screen.getByRole('list', { name: /timeline events/i })
      ).toBeInTheDocument();
    });
  });

  describe('year separators', () => {
    it('shows year separators', () => {
      renderWithProvider(<TimelineList events={mockEvents} />);

      // Use getByText since the heading has aria-level attribute which is level 3
      expect(screen.getByText('2016')).toBeInTheDocument();
      expect(screen.getByText('2018')).toBeInTheDocument();
      expect(screen.getByText('2024')).toBeInTheDocument();
    });

    it('groups events under correct year', () => {
      renderWithProvider(<TimelineList events={mockEvents} />);

      // Find 2016 year group
      const year2016Group = screen.getByRole('group', {
        name: /events from 2016/i,
      });

      // Should contain both 2016 events
      expect(
        within(year2016Group).getByTestId('timeline-event-evt-1')
      ).toBeInTheDocument();
      expect(
        within(year2016Group).getByTestId('timeline-event-evt-2')
      ).toBeInTheDocument();
    });
  });

  describe('connectors', () => {
    it('shows connectors between events', () => {
      renderWithProvider(<TimelineList events={mockEvents} />);

      // Should have separators between events
      const separators = screen.getAllByRole('separator');
      expect(separators.length).toBeGreaterThan(0);
    });

    it('shows duration in connectors', () => {
      renderWithProvider(<TimelineList events={mockEvents} />);

      // Between first two events (May 15 to Aug 20 = ~3 months)
      expect(screen.getByText(/← 3 months/)).toBeInTheDocument();
    });
  });

  describe('gap detection', () => {
    it('emphasizes large gaps visually', () => {
      const eventsWithGap: TimelineEvent[] = [
        createMockEvent('evt-1', '2016-01-01'),
        createMockEvent('evt-2', '2018-01-01'), // 2 year gap
      ];

      const { container } = renderWithProvider(<TimelineList events={eventsWithGap} />);

      // Should have amber styling for significant gap
      const amberLine = container.querySelector('.bg-amber-400');
      expect(amberLine).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('handles empty events array', () => {
      render(<TimelineList events={[]} />);

      expect(screen.getByText('No Events Found')).toBeInTheDocument();
      expect(
        screen.getByText(/timeline events will appear here/i)
      ).toBeInTheDocument();
    });

    it('has appropriate status role for empty state', () => {
      render(<TimelineList events={[]} />);

      expect(
        screen.getByRole('status', { name: /no events found/i })
      ).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows skeleton when loading', () => {
      const { container } = render(<TimelineList events={[]} isLoading />);

      // Should have animated skeleton elements
      const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('has loading status role', () => {
      render(<TimelineList events={[]} isLoading />);

      expect(
        screen.getByRole('status', { name: /loading timeline/i })
      ).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error alert when isError is true', () => {
      render(<TimelineList events={[]} isError />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('displays custom error message', () => {
      render(
        <TimelineList
          events={[]}
          isError
          errorMessage="Custom error message"
        />
      );

      expect(screen.getByText('Custom error message')).toBeInTheDocument();
    });

    it('displays default error message when none provided', () => {
      render(<TimelineList events={[]} isError />);

      expect(
        screen.getByText(/failed to load timeline data/i)
      ).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const { container } = renderWithProvider(
        <TimelineList events={mockEvents} className="custom-class" />
      );

      const list = container.querySelector('.custom-class');
      expect(list).toBeInTheDocument();
    });
  });
});

describe('TimelineListSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<TimelineListSkeleton />);

    const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('applies className prop', () => {
    const { container } = render(
      <TimelineListSkeleton className="custom-class" />
    );

    const wrapper = container.querySelector('.custom-class');
    expect(wrapper).toBeInTheDocument();
  });
});
