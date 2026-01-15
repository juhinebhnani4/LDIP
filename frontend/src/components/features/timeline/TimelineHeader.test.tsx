import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineHeader, TimelineHeaderSkeleton } from './TimelineHeader';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { TimelineStats } from '@/types/timeline';

// Helper to render with TooltipProvider
function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

const mockStats: TimelineStats = {
  totalEvents: 47,
  eventsByType: {
    filing: 12,
    notice: 8,
    hearing: 10,
    order: 7,
  },
  entitiesInvolved: 24,
  dateRangeStart: '2016-05-15',
  dateRangeEnd: '2024-01-15',
  eventsWithEntities: 38,
  eventsWithoutEntities: 9,
  verifiedEvents: 18,
};

describe('TimelineHeader', () => {
  describe('event count display', () => {
    it('displays event count', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByText('47 events')).toBeInTheDocument();
    });

    it('uses singular form for single event', () => {
      const singleEventStats = { ...mockStats, totalEvents: 1 };
      renderWithTooltip(
        <TimelineHeader
          stats={singleEventStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByText('1 event')).toBeInTheDocument();
    });

    it('displays 0 events when stats is undefined', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={undefined}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByText('0 events')).toBeInTheDocument();
    });
  });

  describe('date range display', () => {
    it('displays date range', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByText('May 2016 - Jan 2024')).toBeInTheDocument();
    });

    it('displays "No events" when no date range', () => {
      const noDateStats = {
        ...mockStats,
        dateRangeStart: null,
        dateRangeEnd: null,
      };
      renderWithTooltip(
        <TimelineHeader
          stats={noDateStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByText('No events')).toBeInTheDocument();
    });

    it('displays single month when start and end are same', () => {
      const sameMonthStats = {
        ...mockStats,
        dateRangeStart: '2024-01-01',
        dateRangeEnd: '2024-01-31',
      };
      renderWithTooltip(
        <TimelineHeader
          stats={sameMonthStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByText('Jan 2024')).toBeInTheDocument();
    });
  });

  describe('view mode toggles', () => {
    it('shows view mode toggle buttons for all three views', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /list/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /horizontal/i })
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /multi-track/i })).toBeInTheDocument();
    });

    it('shows List as active when viewMode is list', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      const listButton = screen.getByRole('button', { name: /list/i });
      expect(listButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('shows Horizontal as active when viewMode is horizontal', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="horizontal"
          onViewModeChange={vi.fn()}
        />
      );

      const horizontalButton = screen.getByRole('button', { name: /horizontal/i });
      expect(horizontalButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('shows Multi-Track as active when viewMode is multitrack', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="multitrack"
          onViewModeChange={vi.fn()}
        />
      );

      const multitrackButton = screen.getByRole('button', { name: /multi-track/i });
      expect(multitrackButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('all view mode buttons are enabled', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /list/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /horizontal/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /multi-track/i })).not.toBeDisabled();
    });

    it('calls onViewModeChange when List button clicked', async () => {
      const user = userEvent.setup();
      const onViewModeChange = vi.fn();

      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="horizontal"
          onViewModeChange={onViewModeChange}
        />
      );

      await user.click(screen.getByRole('button', { name: /list/i }));
      expect(onViewModeChange).toHaveBeenCalledWith('list');
    });

    it('calls onViewModeChange when Horizontal button clicked', async () => {
      const user = userEvent.setup();
      const onViewModeChange = vi.fn();

      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={onViewModeChange}
        />
      );

      await user.click(screen.getByRole('button', { name: /horizontal/i }));
      expect(onViewModeChange).toHaveBeenCalledWith('horizontal');
    });

    it('calls onViewModeChange when Multi-Track button clicked', async () => {
      const user = userEvent.setup();
      const onViewModeChange = vi.fn();

      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={onViewModeChange}
        />
      );

      await user.click(screen.getByRole('button', { name: /multi-track/i }));
      expect(onViewModeChange).toHaveBeenCalledWith('multitrack');
    });
  });

  describe('loading state', () => {
    it('shows skeleton when isLoading is true', () => {
      const { container } = renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
          isLoading
        />
      );

      // Skeleton should be rendered
      const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('accessibility', () => {
    it('has appropriate role and aria-label on header', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(
        screen.getByRole('banner', { name: /timeline header/i })
      ).toBeInTheDocument();
    });

    it('has aria-label on view mode group', () => {
      renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
        />
      );

      expect(
        screen.getByRole('group', { name: /view mode selection/i })
      ).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const { container } = renderWithTooltip(
        <TimelineHeader
          stats={mockStats}
          viewMode="list"
          onViewModeChange={vi.fn()}
          className="custom-class"
        />
      );

      const header = container.querySelector('.custom-class');
      expect(header).toBeInTheDocument();
    });
  });
});

describe('TimelineHeaderSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<TimelineHeaderSkeleton />);

    const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('applies className prop', () => {
    const { container } = render(
      <TimelineHeaderSkeleton className="custom-class" />
    );

    const wrapper = container.querySelector('.custom-class');
    expect(wrapper).toBeInTheDocument();
  });
});
