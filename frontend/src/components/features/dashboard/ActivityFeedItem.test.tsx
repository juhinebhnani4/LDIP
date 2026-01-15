import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActivityFeedItem, ActivityFeedItemSkeleton } from './ActivityFeedItem';
import type { Activity, ActivityType } from '@/types/activity';

const createMockActivity = (overrides: Partial<Activity> = {}): Activity => ({
  id: 'activity-1',
  matterId: 'matter-1',
  matterName: 'Test Matter',
  type: 'processing_complete',
  description: 'Processing complete',
  timestamp: new Date().toISOString(),
  isRead: false,
  ...overrides,
});

describe('ActivityFeedItem', () => {
  describe('rendering', () => {
    it('renders matter name', () => {
      const activity = createMockActivity({ matterName: 'Shah v. Mehta' });
      render(<ActivityFeedItem activity={activity} />);

      expect(screen.getByText('Shah v. Mehta')).toBeInTheDocument();
    });

    it('renders activity description', () => {
      const activity = createMockActivity({ description: 'Processing complete' });
      render(<ActivityFeedItem activity={activity} />);

      expect(screen.getByText('Processing complete')).toBeInTheDocument();
    });

    it('renders relative timestamp', () => {
      const activity = createMockActivity({
        timestamp: new Date().toISOString(),
      });
      render(<ActivityFeedItem activity={activity} />);

      // Should show "Just now" for recent timestamp
      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('renders unread indicator for unread activities', () => {
      const activity = createMockActivity({ isRead: false });
      render(<ActivityFeedItem activity={activity} />);

      expect(screen.getByLabelText('New activity')).toBeInTheDocument();
    });

    it('does not render unread indicator for read activities', () => {
      const activity = createMockActivity({ isRead: true });
      render(<ActivityFeedItem activity={activity} />);

      expect(screen.queryByLabelText('New activity')).not.toBeInTheDocument();
    });

    it('links to matter workspace', () => {
      const activity = createMockActivity({ matterId: 'matter-123' });
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/matter/matter-123');
    });

    it('links to dashboard when no matterId', () => {
      const activity = createMockActivity({ matterId: null, matterName: null });
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/dashboard');
    });
  });

  describe('icon colors', () => {
    const iconTestCases: { type: ActivityType; expectedColor: string }[] = [
      { type: 'processing_complete', expectedColor: 'text-green-500' },
      { type: 'matter_opened', expectedColor: 'text-blue-500' },
      { type: 'processing_started', expectedColor: 'text-yellow-500' },
      { type: 'verification_needed', expectedColor: 'text-orange-500' },
      { type: 'contradictions_found', expectedColor: 'text-orange-500' },
      { type: 'processing_failed', expectedColor: 'text-red-500' },
    ];

    iconTestCases.forEach(({ type, expectedColor }) => {
      it(`renders correct color for ${type}`, () => {
        const activity = createMockActivity({ type });
        const { container } = render(<ActivityFeedItem activity={activity} />);

        // Check that the icon has the correct color class
        const icon = container.querySelector('svg');
        expect(icon).toHaveClass(expectedColor);
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible link with aria-label', () => {
      const activity = createMockActivity({
        matterName: 'Shah v. Mehta',
        description: 'Processing complete',
      });
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('aria-label');
      expect(link.getAttribute('aria-label')).toContain('Shah v. Mehta');
      expect(link.getAttribute('aria-label')).toContain('Processing complete');
    });

    it('renders timestamp with datetime attribute', () => {
      const timestamp = '2026-01-15T10:00:00Z';
      const activity = createMockActivity({ timestamp });
      render(<ActivityFeedItem activity={activity} />);

      const time = screen.getByRole('time');
      expect(time).toHaveAttribute('dateTime', timestamp);
    });

    it('marks icon as decorative', () => {
      const activity = createMockActivity();
      const { container } = render(<ActivityFeedItem activity={activity} />);

      const iconContainer = container.querySelector('[aria-hidden="true"]');
      expect(iconContainer).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onActivityClick when clicked', async () => {
      const user = userEvent.setup();
      const onActivityClick = vi.fn();
      const activity = createMockActivity();

      render(<ActivityFeedItem activity={activity} onActivityClick={onActivityClick} />);

      await user.click(screen.getByRole('link'));

      expect(onActivityClick).toHaveBeenCalledWith(activity);
    });

    it('is focusable via keyboard', () => {
      const activity = createMockActivity();
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      link.focus();
      expect(link).toHaveFocus();
    });
  });

  describe('hover states', () => {
    it('applies hover class to link', () => {
      const activity = createMockActivity();
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('hover:bg-muted/50');
    });

    it('applies unread background styling for unread items', () => {
      const activity = createMockActivity({ isRead: false });
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('bg-muted/30');
    });

    it('does not apply unread background for read items', () => {
      const activity = createMockActivity({ isRead: true });
      render(<ActivityFeedItem activity={activity} />);

      const link = screen.getByRole('link');
      expect(link).not.toHaveClass('bg-muted/30');
    });
  });
});

describe('ActivityFeedItemSkeleton', () => {
  it('renders loading placeholder', () => {
    render(<ActivityFeedItemSkeleton />);

    // Should render animated skeleton elements
    const listItem = screen.getByRole('listitem');
    expect(listItem).toHaveClass('animate-pulse');
  });

  it('renders icon placeholder', () => {
    const { container } = render(<ActivityFeedItemSkeleton />);

    const iconPlaceholder = container.querySelector('.size-6.rounded-full.bg-muted');
    expect(iconPlaceholder).toBeInTheDocument();
  });

  it('renders content placeholders', () => {
    const { container } = render(<ActivityFeedItemSkeleton />);

    const contentPlaceholders = container.querySelectorAll('.rounded.bg-muted');
    expect(contentPlaceholders.length).toBeGreaterThan(0);
  });
});
