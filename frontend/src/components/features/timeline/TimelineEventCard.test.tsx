import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { TimelineEventCard, TimelineEventCardSkeleton } from './TimelineEventCard';
import type { TimelineEvent } from '@/types/timeline';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

// Wrap with TooltipProvider for tests
function renderWithProvider(ui: React.ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

const createMockEvent = (overrides: Partial<TimelineEvent> = {}): TimelineEvent => ({
  id: 'evt-1',
  eventDate: '2024-01-15',
  eventDatePrecision: 'day',
  eventDateText: '15th January 2024',
  eventType: 'filing',
  description: 'Petition filed before Special Court',
  documentId: 'doc-1',
  sourcePage: 1,
  confidence: 0.95,
  entities: [
    {
      entityId: 'ent-1',
      canonicalName: 'Nirav D. Jobalia',
      entityType: 'PERSON',
      role: 'petitioner',
    },
  ],
  isAmbiguous: false,
  isVerified: true,
  ...overrides,
});

describe('TimelineEventCard', () => {
  describe('date rendering', () => {
    it('renders date with correct formatting for day precision', () => {
      const event = createMockEvent({ eventDatePrecision: 'day' });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('January 15, 2024')).toBeInTheDocument();
    });

    it('renders date with month precision', () => {
      const event = createMockEvent({
        eventDate: '2024-01-01',
        eventDatePrecision: 'month',
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('January 2024')).toBeInTheDocument();
    });

    it('renders date with year precision', () => {
      const event = createMockEvent({
        eventDate: '2024-01-01',
        eventDatePrecision: 'year',
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('2024')).toBeInTheDocument();
    });

    it('renders date with approximate prefix', () => {
      const event = createMockEvent({
        eventDatePrecision: 'approximate',
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText(/~January 15, 2024/)).toBeInTheDocument();
    });

    it('shows original date text when different from event date', () => {
      const event = createMockEvent({
        eventDateText: '15th January 2024',
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('(15th January 2024)')).toBeInTheDocument();
    });
  });

  describe('event type badge', () => {
    it('renders event type icon and badge', () => {
      const event = createMockEvent({ eventType: 'filing' });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('FILING')).toBeInTheDocument();
    });

    it('renders different event types correctly', () => {
      const types = [
        'order',
        'notice',
        'hearing',
        'transaction',
        'document',
        'deadline',
      ] as const;

      types.forEach((type) => {
        const { unmount } = renderWithProvider(
          <TimelineEventCard event={createMockEvent({ eventType: type })} />
        );
        expect(screen.getByText(type.toUpperCase())).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('description', () => {
    it('renders description text', () => {
      const event = createMockEvent({
        description: 'Test description content',
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('Test description content')).toBeInTheDocument();
    });
  });

  describe('actors/entities', () => {
    it('renders actor with link to entities tab', () => {
      const event = createMockEvent();
      renderWithProvider(<TimelineEventCard event={event} />);

      const link = screen.getByRole('link', { name: 'Nirav D. Jobalia' });
      expect(link).toHaveAttribute(
        'href',
        '/matters/test-matter-id/entities?entity=ent-1'
      );
    });

    it('renders actor role in parentheses', () => {
      const event = createMockEvent();
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('(petitioner)')).toBeInTheDocument();
    });

    it('renders multiple actors separated by commas', () => {
      const event = createMockEvent({
        entities: [
          {
            entityId: 'ent-1',
            canonicalName: 'Nirav D. Jobalia',
            entityType: 'PERSON',
            role: 'petitioner',
          },
          {
            entityId: 'ent-2',
            canonicalName: 'Custodian of Records',
            entityType: 'ORG',
            role: 'respondent',
          },
        ],
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(
        screen.getByRole('link', { name: 'Nirav D. Jobalia' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('link', { name: 'Custodian of Records' })
      ).toBeInTheDocument();
    });

    it('does not render actors section when no entities', () => {
      const event = createMockEvent({ entities: [] });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText('Actor:')).not.toBeInTheDocument();
    });
  });

  describe('source document link', () => {
    it('renders source document link with page number', () => {
      const event = createMockEvent({ documentId: 'doc-1', sourcePage: 5 });
      renderWithProvider(<TimelineEventCard event={event} />);

      const link = screen.getByRole('link', { name: 'Document, pg 5' });
      expect(link).toHaveAttribute(
        'href',
        '/matters/test-matter-id/documents?doc=doc-1&page=5'
      );
    });

    it('renders source document link without page number', () => {
      const event = createMockEvent({ documentId: 'doc-1', sourcePage: null });
      renderWithProvider(<TimelineEventCard event={event} />);

      const link = screen.getByRole('link', { name: 'Document' });
      expect(link).toHaveAttribute(
        'href',
        '/matters/test-matter-id/documents?doc=doc-1'
      );
    });

    it('does not render source section when no document', () => {
      const event = createMockEvent({ documentId: null });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText('Source:')).not.toBeInTheDocument();
    });
  });

  describe('verification status', () => {
    it('shows verified badge when verified', () => {
      const event = createMockEvent({ isVerified: true });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('does not show verified badge when not verified', () => {
      const event = createMockEvent({ isVerified: false });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText('Verified')).not.toBeInTheDocument();
    });
  });

  describe('contradiction flag', () => {
    it('shows contradiction warning when flagged', () => {
      const event = createMockEvent({
        hasContradiction: true,
        contradictionDetails: 'Dates conflict with another document',
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText('Contradiction')).toBeInTheDocument();
    });

    it('does not show contradiction badge when not flagged', () => {
      const event = createMockEvent({ hasContradiction: false });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText('Contradiction')).not.toBeInTheDocument();
    });
  });

  describe('low confidence warning', () => {
    it('shows low confidence warning when below threshold', () => {
      const event = createMockEvent({ confidence: 0.65, isVerified: false });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByText(/Low confidence \(65%\)/)).toBeInTheDocument();
    });

    it('does not show warning when confidence is high', () => {
      const event = createMockEvent({ confidence: 0.9 });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText(/Low confidence/)).not.toBeInTheDocument();
    });

    it('does not show warning when verified even with low confidence', () => {
      const event = createMockEvent({ confidence: 0.65, isVerified: true });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText(/Low confidence/)).not.toBeInTheDocument();
    });
  });

  describe('cross-references', () => {
    it('renders cross-references when available', () => {
      const event = createMockEvent({
        crossReferences: ['IC-2020-045', 'IC-2021-012'],
      });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(
        screen.getByText('Cross-ref: IC-2020-045, IC-2021-012')
      ).toBeInTheDocument();
    });

    it('does not render cross-references when empty', () => {
      const event = createMockEvent({ crossReferences: [] });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.queryByText(/Cross-ref/)).not.toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const event = createMockEvent();
      const { container } = renderWithProvider(
        <TimelineEventCard event={event} className="custom-class" />
      );

      const card = container.querySelector('.custom-class');
      expect(card).toBeInTheDocument();
    });

    it('has test ID for automation', () => {
      const event = createMockEvent({ id: 'evt-123' });
      renderWithProvider(<TimelineEventCard event={event} />);

      expect(screen.getByTestId('timeline-event-evt-123')).toBeInTheDocument();
    });
  });
});

describe('TimelineEventCardSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<TimelineEventCardSkeleton />);

    const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('applies className prop', () => {
    const { container } = render(
      <TimelineEventCardSkeleton className="custom-class" />
    );

    const card = container.querySelector('.custom-class');
    expect(card).toBeInTheDocument();
  });
});
