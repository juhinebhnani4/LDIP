/**
 * TimelineEventDetail Tests
 *
 * Tests for the event detail panel shown in horizontal/multi-track views.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #2, #3)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineEventDetail } from './TimelineEventDetail';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { TimelineEvent } from '@/types/timeline';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

// Helper to render with providers
function renderWithProviders(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

// Mock event data
const mockEvent: TimelineEvent = {
  id: 'event-1',
  eventDate: '2024-03-15',
  eventDatePrecision: 'day',
  eventDateText: 'March 15, 2024',
  eventType: 'filing',
  description: 'Petition filed with court for custody determination',
  documentId: 'doc-123',
  sourcePage: 5,
  confidence: 0.95,
  entities: [
    {
      entityId: 'entity-1',
      canonicalName: 'John Smith',
      entityType: 'PERSON',
      role: 'Petitioner',
    },
  ],
  isAmbiguous: false,
  isVerified: true,
};

const mockEventNoEntities: TimelineEvent = {
  ...mockEvent,
  id: 'event-2',
  entities: [],
  isVerified: false,
  confidence: 0.65,
};

const mockEventWithContradiction: TimelineEvent = {
  ...mockEvent,
  id: 'event-3',
  hasContradiction: true,
  contradictionDetails: 'Date conflicts with document X',
};

describe('TimelineEventDetail', () => {
  it('renders event information correctly', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={() => {}} />
    );

    expect(screen.getByText('FILING')).toBeInTheDocument();
    expect(screen.getByText(/Petition filed with court/i)).toBeInTheDocument();
    expect(screen.getByText(/Friday, March 15, 2024/i)).toBeInTheDocument();
  });

  it('shows verified badge when event is verified', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={() => {}} />
    );

    expect(screen.getByText('Verified')).toBeInTheDocument();
  });

  it('shows contradiction badge when event has contradiction', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEventWithContradiction} onClose={() => {}} />
    );

    expect(screen.getByText('Contradiction')).toBeInTheDocument();
  });

  it('displays actor information with link', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={() => {}} />
    );

    expect(screen.getByText('Actor:')).toBeInTheDocument();
    const actorLink = screen.getByRole('link', { name: /John Smith/i });
    expect(actorLink).toBeInTheDocument();
    expect(actorLink).toHaveAttribute(
      'href',
      '/matters/test-matter-id/entities?entity=entity-1'
    );
    expect(screen.getByText(/Petitioner/i)).toBeInTheDocument();
  });

  it('hides actor section when no entities', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEventNoEntities} onClose={() => {}} />
    );

    expect(screen.queryByText('Actor:')).not.toBeInTheDocument();
  });

  it('renders View Source button with correct link', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={() => {}} />
    );

    const sourceLink = screen.getByRole('link', { name: /View Source/i });
    expect(sourceLink).toBeInTheDocument();
    expect(sourceLink).toHaveAttribute(
      'href',
      '/matters/test-matter-id/documents?doc=doc-123&page=5'
    );
  });

  it('hides View Source when no documentId', () => {
    const eventNoDoc = { ...mockEvent, documentId: null, sourcePage: null };
    renderWithProviders(
      <TimelineEventDetail event={eventNoDoc} onClose={() => {}} />
    );

    expect(screen.queryByRole('link', { name: /View Source/i })).not.toBeInTheDocument();
  });

  it('renders View in List button when callback provided', () => {
    const handleViewInList = vi.fn();
    renderWithProviders(
      <TimelineEventDetail
        event={mockEvent}
        onClose={() => {}}
        onViewInList={handleViewInList}
      />
    );

    expect(screen.getByRole('button', { name: /View in List/i })).toBeInTheDocument();
  });

  it('hides View in List button when callback not provided', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={() => {}} />
    );

    expect(screen.queryByRole('button', { name: /View in List/i })).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();

    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={handleClose} />
    );

    await user.click(screen.getByRole('button', { name: /close/i }));

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('calls onViewInList when View in List button is clicked', async () => {
    const user = userEvent.setup();
    const handleViewInList = vi.fn();

    renderWithProviders(
      <TimelineEventDetail
        event={mockEvent}
        onClose={() => {}}
        onViewInList={handleViewInList}
      />
    );

    await user.click(screen.getByRole('button', { name: /View in List/i }));

    expect(handleViewInList).toHaveBeenCalledTimes(1);
  });

  it('shows low confidence warning for unverified low-confidence events', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEventNoEntities} onClose={() => {}} />
    );

    expect(screen.getByText(/Low confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/65%/i)).toBeInTheDocument();
  });

  it('hides low confidence warning for verified events', () => {
    const lowConfVerified = { ...mockEvent, confidence: 0.5, isVerified: true };
    renderWithProviders(
      <TimelineEventDetail event={lowConfVerified} onClose={() => {}} />
    );

    expect(screen.queryByText(/Low confidence/i)).not.toBeInTheDocument();
  });

  it('formats approximate dates correctly', () => {
    const approxEvent = { ...mockEvent, eventDatePrecision: 'approximate' as const };
    renderWithProviders(
      <TimelineEventDetail event={approxEvent} onClose={() => {}} />
    );

    expect(screen.getByText(/Approximately March 15, 2024/i)).toBeInTheDocument();
  });

  it('formats month precision dates correctly', () => {
    const monthEvent = { ...mockEvent, eventDatePrecision: 'month' as const };
    renderWithProviders(
      <TimelineEventDetail event={monthEvent} onClose={() => {}} />
    );

    expect(screen.getByText('March 2024')).toBeInTheDocument();
  });

  it('formats year precision dates correctly', () => {
    const yearEvent = { ...mockEvent, eventDatePrecision: 'year' as const };
    renderWithProviders(
      <TimelineEventDetail event={yearEvent} onClose={() => {}} />
    );

    expect(screen.getByText('2024')).toBeInTheDocument();
  });

  it('has accessible region role', () => {
    renderWithProviders(
      <TimelineEventDetail event={mockEvent} onClose={() => {}} />
    );

    expect(
      screen.getByRole('region', { name: /Selected event details/i })
    ).toBeInTheDocument();
  });

  it('applies custom className', () => {
    renderWithProviders(
      <TimelineEventDetail
        event={mockEvent}
        onClose={() => {}}
        className="custom-class"
      />
    );

    const region = screen.getByRole('region', { name: /Selected event details/i });
    expect(region).toHaveClass('custom-class');
  });

  it('renders multiple actors with correct links', () => {
    const multiActorEvent: TimelineEvent = {
      ...mockEvent,
      entities: [
        {
          entityId: 'entity-1',
          canonicalName: 'John Smith',
          entityType: 'PERSON',
          role: 'Petitioner',
        },
        {
          entityId: 'entity-2',
          canonicalName: 'Jane Doe',
          entityType: 'PERSON',
          role: 'Respondent',
        },
      ],
    };

    renderWithProviders(
      <TimelineEventDetail event={multiActorEvent} onClose={() => {}} />
    );

    expect(screen.getByRole('link', { name: /John Smith/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Jane Doe/i })).toBeInTheDocument();
    expect(screen.getByText(/Petitioner/i)).toBeInTheDocument();
    expect(screen.getByText(/Respondent/i)).toBeInTheDocument();
  });
});
