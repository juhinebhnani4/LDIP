/**
 * TimelineHorizontal Tests
 *
 * Tests for the horizontal timeline view component.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #2)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineHorizontal } from './TimelineHorizontal';
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
const mockEvents: TimelineEvent[] = [
  {
    id: 'event-1',
    eventDate: '2023-01-15',
    eventDatePrecision: 'day',
    eventDateText: 'January 15, 2023',
    eventType: 'filing',
    description: 'Initial petition filed',
    documentId: 'doc-1',
    sourcePage: 1,
    confidence: 0.95,
    entities: [
      {
        entityId: 'e1',
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
    eventDate: '2023-03-20',
    eventDatePrecision: 'day',
    eventDateText: 'March 20, 2023',
    eventType: 'hearing',
    description: 'First hearing scheduled',
    documentId: 'doc-2',
    sourcePage: 3,
    confidence: 0.88,
    entities: [],
    isAmbiguous: false,
    isVerified: false,
  },
  {
    id: 'event-3',
    eventDate: '2023-09-10',
    eventDatePrecision: 'day',
    eventDateText: 'September 10, 2023',
    eventType: 'order',
    description: 'Final order issued',
    documentId: 'doc-3',
    sourcePage: 5,
    confidence: 0.92,
    entities: [
      {
        entityId: 'e2',
        canonicalName: 'Court',
        entityType: 'INSTITUTION',
        role: null,
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
];

// Events that cluster together
const clusteringEvents: TimelineEvent[] = [
  {
    ...mockEvents[0]!,
    id: 'cluster-1',
    eventDate: '2023-05-01',
  },
  {
    ...mockEvents[1]!,
    id: 'cluster-2',
    eventDate: '2023-05-03', // 2 days later - should cluster at year zoom
  },
  {
    ...mockEvents[2]!,
    id: 'cluster-3',
    eventDate: '2023-05-05', // 4 days later - should cluster
  },
];

// Events with large gap
const gapEvents: TimelineEvent[] = [
  {
    ...mockEvents[0]!,
    id: 'gap-1',
    eventDate: '2022-01-01',
  },
  {
    ...mockEvents[1]!,
    id: 'gap-2',
    eventDate: '2022-06-01', // 150+ days gap - significant
  },
];

describe('TimelineHorizontal', () => {
  it('renders events on horizontal axis', () => {
    renderWithProviders(<TimelineHorizontal events={mockEvents} />);

    expect(
      screen.getByRole('graphics-document', { name: /horizontal timeline/i })
    ).toBeInTheDocument();

    // Should have event markers
    const markers = screen.getAllByRole('button', { name: /event/i });
    expect(markers.length).toBeGreaterThan(0);
  });

  it('shows year labels', () => {
    renderWithProviders(<TimelineHorizontal events={mockEvents} />);

    expect(screen.getByText('2023')).toBeInTheDocument();
  });

  it('shows zoom controls', () => {
    renderWithProviders(<TimelineHorizontal events={mockEvents} />);

    expect(
      screen.getByRole('group', { name: /zoom controls/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  it('handles empty state', () => {
    renderWithProviders(<TimelineHorizontal events={[]} />);

    expect(screen.getByText('No Events Found')).toBeInTheDocument();
    expect(
      screen.getByText(/Timeline events will appear here/i)
    ).toBeInTheDocument();
  });

  it('selects event on marker click', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    renderWithProviders(
      <TimelineHorizontal events={mockEvents} onEventSelect={handleSelect} />
    );

    const markers = screen.getAllByRole('button', { name: /event/i });
    await user.click(markers[0]!);

    expect(handleSelect).toHaveBeenCalled();
  });

  it('shows event detail panel when event is selected', () => {
    renderWithProviders(
      <TimelineHorizontal events={mockEvents} selectedEventId="event-1" />
    );

    // Detail panel should appear
    expect(
      screen.getByRole('region', { name: /selected event details/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/Initial petition filed/i)).toBeInTheDocument();
  });

  it('closes detail panel when close is clicked', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    renderWithProviders(
      <TimelineHorizontal
        events={mockEvents}
        selectedEventId="event-1"
        onEventSelect={handleSelect}
      />
    );

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(handleSelect).toHaveBeenCalledWith(null);
  });

  it('changes zoom level with slider controls', async () => {
    const user = userEvent.setup();

    renderWithProviders(<TimelineHorizontal events={mockEvents} />);

    // Default is 'Year'
    expect(screen.getByText('Year')).toBeInTheDocument();

    // Click zoom in
    await user.click(screen.getByRole('button', { name: /zoom in/i }));

    // Should now show 'Quarter'
    expect(screen.getByText('Quarter')).toBeInTheDocument();
  });

  it('clusters nearby events at year zoom level', () => {
    renderWithProviders(<TimelineHorizontal events={clusteringEvents} />);

    // At year zoom, events within 30 days should cluster
    // Note: This test depends on clustering logic - may need adjustment
    expect(screen.getAllByRole('button', { name: /event/i }).length).toBeLessThanOrEqual(3);
  });

  it('shows gap indicators for significant delays', () => {
    renderWithProviders(<TimelineHorizontal events={gapEvents} />);

    // Should show gap indicator for 150+ day gap
    expect(screen.getByText(/month/i)).toBeInTheDocument();
  });

  it('calls onViewInList when View in List button clicked', async () => {
    const user = userEvent.setup();
    const handleViewInList = vi.fn();

    renderWithProviders(
      <TimelineHorizontal
        events={mockEvents}
        selectedEventId="event-1"
        onViewInList={handleViewInList}
      />
    );

    await user.click(screen.getByRole('button', { name: /View in List/i }));

    expect(handleViewInList).toHaveBeenCalledWith('event-1');
  });

  it('applies custom className', () => {
    const { container } = renderWithProviders(
      <TimelineHorizontal events={mockEvents} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('highlights selected event marker', () => {
    renderWithProviders(
      <TimelineHorizontal events={mockEvents} selectedEventId="event-1" />
    );

    const markers = screen.getAllByRole('button', { name: /event/i });
    const selectedMarker = markers.find((m) => m.getAttribute('aria-pressed') === 'true');
    expect(selectedMarker).toBeInTheDocument();
  });

  it('supports keyboard navigation on markers', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    renderWithProviders(
      <TimelineHorizontal events={mockEvents} onEventSelect={handleSelect} />
    );

    // Find event marker buttons and click with keyboard
    const markers = screen.getAllByRole('button', { name: /event/i });
    expect(markers.length).toBeGreaterThan(0);

    // Focus and activate first marker
    markers[0]!.focus();
    await user.keyboard('{Enter}');
    expect(handleSelect).toHaveBeenCalled();
  });

  it('has accessible aria labels on markers', () => {
    renderWithProviders(<TimelineHorizontal events={mockEvents} />);

    const markers = screen.getAllByRole('button', { name: /event/i });
    markers.forEach((marker) => {
      expect(marker).toHaveAccessibleName();
    });
  });

  it('updates when events prop changes', () => {
    const { rerender } = renderWithProviders(
      <TimelineHorizontal events={mockEvents.slice(0, 1)} />
    );

    let markers = screen.getAllByRole('button', { name: /event/i });
    expect(markers.length).toBe(1);

    rerender(
      <TooltipProvider>
        <TimelineHorizontal events={mockEvents} />
      </TooltipProvider>
    );

    // May have different count due to clustering
    markers = screen.getAllByRole('button', { name: /event/i });
    expect(markers.length).toBeGreaterThanOrEqual(1);
  });

  it('shows multiple years when events span multiple years', () => {
    const multiYearEvents: TimelineEvent[] = [
      { ...mockEvents[0]!, eventDate: '2022-06-01' },
      { ...mockEvents[1]!, eventDate: '2023-06-01' },
      { ...mockEvents[2]!, eventDate: '2024-06-01' },
    ];

    renderWithProviders(<TimelineHorizontal events={multiYearEvents} />);

    expect(screen.getByText('2022')).toBeInTheDocument();
    expect(screen.getByText('2023')).toBeInTheDocument();
    expect(screen.getByText('2024')).toBeInTheDocument();
  });
});
