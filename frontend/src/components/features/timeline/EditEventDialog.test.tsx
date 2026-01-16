/**
 * EditEventDialog Tests
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EditEventDialog } from './EditEventDialog';
import type { TimelineEvent } from '@/types/timeline';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock manual event
const mockManualEvent: TimelineEvent = {
  id: 'event-1',
  eventDate: '2024-06-15',
  eventDatePrecision: 'day',
  eventDateText: 'June 15, 2024',
  eventType: 'filing',
  description: 'Court filing submitted',
  documentId: null,
  sourcePage: null,
  confidence: 1.0,
  entities: [{ entityId: 'entity-1', canonicalName: 'John Smith', entityType: 'PERSON', role: null }],
  isAmbiguous: false,
  isVerified: false,
  isManual: true,
  createdBy: 'user-123',
};

// Mock auto event
const mockAutoEvent: TimelineEvent = {
  id: 'event-2',
  eventDate: '2024-05-10',
  eventDatePrecision: 'day',
  eventDateText: 'May 10, 2024',
  eventType: 'hearing',
  description: 'Preliminary hearing conducted',
  documentId: 'doc-1',
  sourcePage: 5,
  confidence: 0.92,
  entities: [],
  isAmbiguous: false,
  isVerified: false,
  isManual: false,
};

// Mock entities
const mockEntities = [
  { id: 'entity-1', name: 'John Smith' },
  { id: 'entity-2', name: 'ABC Corporation' },
];

describe('EditEventDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    event: mockManualEvent,
    onSubmit: vi.fn().mockResolvedValue(undefined),
    entities: mockEntities,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dialog when open with manual event', () => {
      render(<EditEventDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Edit Manual Event')).toBeInTheDocument();
    });

    it('renders dialog when open with auto event', () => {
      render(<EditEventDialog {...defaultProps} event={mockAutoEvent} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Edit Event Classification')).toBeInTheDocument();
    });

    it('does not render when event is null', () => {
      render(<EditEventDialog {...defaultProps} event={null} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not render when closed', () => {
      render(<EditEventDialog {...defaultProps} open={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows "Manually added" badge for manual events', () => {
      render(<EditEventDialog {...defaultProps} />);

      expect(screen.getByText('Manually added')).toBeInTheDocument();
    });

    it('shows "Auto-extracted" badge for auto events', () => {
      render(<EditEventDialog {...defaultProps} event={mockAutoEvent} />);

      expect(screen.getByText('Auto-extracted')).toBeInTheDocument();
    });
  });

  describe('Manual Event Form', () => {
    it('renders all form fields for manual events', () => {
      render(<EditEventDialog {...defaultProps} />);

      expect(screen.getByText('Event Date')).toBeInTheDocument();
      expect(screen.getByText('Event Type')).toBeInTheDocument();
      expect(screen.getByText('Title')).toBeInTheDocument();
      expect(screen.getByText('Description')).toBeInTheDocument();
    });

    it('pre-populates form with event data', () => {
      render(<EditEventDialog {...defaultProps} />);

      // Title should be pre-filled
      const titleInput = screen.getByPlaceholderText(/brief description/i);
      expect(titleInput).toHaveValue('Court filing submitted');
    });
  });

  describe('Auto Event Form', () => {
    it('only shows event type field for auto events', () => {
      render(<EditEventDialog {...defaultProps} event={mockAutoEvent} />);

      expect(screen.getByText('Event Type')).toBeInTheDocument();
      expect(screen.queryByText('Title')).not.toBeInTheDocument();
      expect(screen.queryByText('Description')).not.toBeInTheDocument();
    });

    it('shows description about limited editing', () => {
      render(<EditEventDialog {...defaultProps} event={mockAutoEvent} />);

      expect(screen.getByText(/only event type can be modified/i)).toBeInTheDocument();
    });
  });

  describe('Dialog Behavior', () => {
    it('closes on cancel button click', async () => {
      const user = userEvent.setup();
      const onOpenChange = vi.fn();
      render(<EditEventDialog {...defaultProps} onOpenChange={onOpenChange} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('has Save Changes button for manual events', () => {
      render(<EditEventDialog {...defaultProps} />);

      expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
    });

    it('has Update Classification button for auto events', () => {
      render(<EditEventDialog {...defaultProps} event={mockAutoEvent} />);

      expect(screen.getByRole('button', { name: /update classification/i })).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper dialog title', () => {
      render(<EditEventDialog {...defaultProps} />);

      expect(screen.getByText('Edit Manual Event')).toBeInTheDocument();
    });

    it('has proper dialog description for manual events', () => {
      render(<EditEventDialog {...defaultProps} />);

      expect(screen.getByText(/update the details/i)).toBeInTheDocument();
    });

    it('has proper dialog description for auto events', () => {
      render(<EditEventDialog {...defaultProps} event={mockAutoEvent} />);

      expect(screen.getByText(/correct the classification/i)).toBeInTheDocument();
    });
  });
});
