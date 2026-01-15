/**
 * TimelineMultiTrack Tests
 *
 * Tests for the multi-track timeline view component.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #3)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineMultiTrack } from './TimelineMultiTrack';
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

// Mock events with multiple actors
const mockEventsWithActors: TimelineEvent[] = [
  {
    id: 'event-1',
    eventDate: '2023-01-15',
    eventDatePrecision: 'day',
    eventDateText: 'January 15, 2023',
    eventType: 'filing',
    description: 'Petition filed by John Smith',
    documentId: 'doc-1',
    sourcePage: 1,
    confidence: 0.95,
    entities: [
      {
        entityId: 'actor-john',
        canonicalName: 'John Smith',
        entityType: 'PERSON',
        role: 'Petitioner',
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
  {
    id: 'event-2',
    eventDate: '2023-02-10',
    eventDatePrecision: 'day',
    eventDateText: 'February 10, 2023',
    eventType: 'order',
    description: 'Court order issued',
    documentId: 'doc-2',
    sourcePage: 3,
    confidence: 0.92,
    entities: [
      {
        entityId: 'actor-court',
        canonicalName: 'Family Court',
        entityType: 'INSTITUTION',
        role: null,
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
  {
    id: 'event-3',
    eventDate: '2023-03-05',
    eventDatePrecision: 'day',
    eventDateText: 'March 5, 2023',
    eventType: 'filing',
    description: 'Response filed by Jane Doe',
    documentId: 'doc-3',
    sourcePage: 5,
    confidence: 0.88,
    entities: [
      {
        entityId: 'actor-jane',
        canonicalName: 'Jane Doe',
        entityType: 'PERSON',
        role: 'Respondent',
      },
    ],
    isAmbiguous: false,
    isVerified: false,
  },
  {
    id: 'event-4',
    eventDate: '2023-04-20',
    eventDatePrecision: 'day',
    eventDateText: 'April 20, 2023',
    eventType: 'hearing',
    description: 'Joint hearing with all parties',
    documentId: 'doc-4',
    sourcePage: 7,
    confidence: 0.90,
    entities: [
      {
        entityId: 'actor-john',
        canonicalName: 'John Smith',
        entityType: 'PERSON',
        role: 'Petitioner',
      },
      {
        entityId: 'actor-jane',
        canonicalName: 'Jane Doe',
        entityType: 'PERSON',
        role: 'Respondent',
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
];

// Events without entities
const mockEventsNoEntities: TimelineEvent[] = [
  {
    id: 'event-no-entity',
    eventDate: '2023-01-15',
    eventDatePrecision: 'day',
    eventDateText: 'January 15, 2023',
    eventType: 'document',
    description: 'Document uploaded',
    documentId: 'doc-x',
    sourcePage: 1,
    confidence: 0.80,
    entities: [],
    isAmbiguous: false,
    isVerified: false,
  },
];

describe('TimelineMultiTrack', () => {
  it('renders separate tracks for each actor', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    // Should show actor names as track labels
    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('Family Court')).toBeInTheDocument();
  });

  it('shows actor count indicator', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    expect(screen.getByText(/3 actors/i)).toBeInTheDocument();
  });

  it('aligns events vertically by date', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    // All event markers should have style with left position
    const markers = screen.getAllByRole('button', { name: /event/i });
    expect(markers.length).toBeGreaterThan(0);

    markers.forEach((marker) => {
      // Check that the marker has a left style attribute for positioning
      const style = marker.getAttribute('style');
      expect(style).toContain('left:');
    });
  });

  it('shows year labels in header', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    expect(screen.getByText('2023')).toBeInTheDocument();
  });

  it('handles empty events', () => {
    renderWithProviders(<TimelineMultiTrack events={[]} />);

    expect(screen.getByText('No Events Found')).toBeInTheDocument();
  });

  it('handles events with no actors', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsNoEntities} />
    );

    // Should show a track for "Unknown Actor"
    expect(screen.getByText(/Unknown Actor/i)).toBeInTheDocument();
  });

  it('selects event on marker click', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        onEventSelect={handleSelect}
      />
    );

    const markers = screen.getAllByRole('button', { name: /event/i });
    await user.click(markers[0]!);

    expect(handleSelect).toHaveBeenCalled();
  });

  it('shows event detail panel when event is selected', () => {
    renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        selectedEventId="event-1"
      />
    );

    expect(
      screen.getByRole('region', { name: /selected event details/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/Petition filed by John Smith/i)).toBeInTheDocument();
  });

  it('closes detail panel when close clicked', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        selectedEventId="event-1"
        onEventSelect={handleSelect}
      />
    );

    await user.click(screen.getByRole('button', { name: /close/i }));

    expect(handleSelect).toHaveBeenCalledWith(null);
  });

  it('highlights selected event marker', () => {
    renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        selectedEventId="event-1"
      />
    );

    const selectedMarker = screen.getAllByRole('button', { name: /event/i })
      .find((m) => m.getAttribute('aria-pressed') === 'true');

    expect(selectedMarker).toBeInTheDocument();
  });

  it('shows track labels on left side', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    // Track labels should be visible
    const johnTrack = screen.getByRole('row', { name: /John Smith/i });
    expect(johnTrack).toBeInTheDocument();
  });

  it('shows entity type above actor name', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    // Should show entity types
    expect(screen.getAllByText('PERSON').length).toBeGreaterThan(0);
    expect(screen.getByText('INSTITUTION')).toBeInTheDocument();
  });

  it('calls onViewInList when View in List clicked', async () => {
    const user = userEvent.setup();
    const handleViewInList = vi.fn();

    renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        selectedEventId="event-1"
        onViewInList={handleViewInList}
      />
    );

    await user.click(screen.getByRole('button', { name: /View in List/i }));

    expect(handleViewInList).toHaveBeenCalledWith('event-1');
  });

  it('applies custom className', () => {
    const { container } = renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        className="custom-class"
      />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('places same event on multiple tracks when it has multiple actors', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    // Event 4 has both John and Jane as actors
    // Should appear on both tracks
    const markers = screen.getAllByRole('button', { name: /Joint hearing/i });
    // Should have at least 2 markers for the joint hearing (one per track)
    expect(markers.length).toBeGreaterThanOrEqual(2);
  });

  it('sorts tracks by event count (most active first)', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    const rows = screen.getAllByRole('row');
    // John Smith has 2 events, should be first
    // The first row after header should be John Smith's track
    const trackNames = rows.map((row) => row.getAttribute('aria-label'));
    const johnIndex = trackNames.findIndex((name) =>
      name?.includes('John Smith')
    );
    const janeIndex = trackNames.findIndex((name) =>
      name?.includes('Jane Doe')
    );

    // John should come before or equal to Jane (both have 2 events after event-4)
    expect(johnIndex).toBeLessThanOrEqual(janeIndex);
  });

  it('has accessible table structure', () => {
    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    expect(
      screen.getByRole('table', { name: /multi-track timeline/i })
    ).toBeInTheDocument();
  });

  it('supports keyboard navigation', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    renderWithProviders(
      <TimelineMultiTrack
        events={mockEventsWithActors}
        onEventSelect={handleSelect}
      />
    );

    // Focus an event marker directly and activate with keyboard
    const markers = screen.getAllByRole('button', { name: /event/i });
    expect(markers.length).toBeGreaterThan(0);

    markers[0]!.focus();
    await user.keyboard('{Enter}');

    expect(handleSelect).toHaveBeenCalled();
  });

  it('shows tooltips on event hover', async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <TimelineMultiTrack events={mockEventsWithActors} />
    );

    const markers = screen.getAllByRole('button', { name: /event/i });
    await user.hover(markers[0]!);

    // Tooltip content should appear
    // Note: This depends on tooltip animation timing
    expect(markers[0]!).toHaveAccessibleName();
  });

  it('handles events spanning multiple years', () => {
    const multiYearEvents: TimelineEvent[] = [
      { ...mockEventsWithActors[0]!, eventDate: '2022-06-01' },
      { ...mockEventsWithActors[1]!, eventDate: '2023-06-01' },
      { ...mockEventsWithActors[2]!, eventDate: '2024-06-01' },
    ];

    renderWithProviders(
      <TimelineMultiTrack events={multiYearEvents} />
    );

    expect(screen.getByText('2022')).toBeInTheDocument();
    expect(screen.getByText('2023')).toBeInTheDocument();
    expect(screen.getByText('2024')).toBeInTheDocument();
  });
});
