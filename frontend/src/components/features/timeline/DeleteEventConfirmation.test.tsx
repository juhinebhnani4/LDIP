/**
 * DeleteEventConfirmation Tests
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeleteEventConfirmation } from './DeleteEventConfirmation';
import type { TimelineEvent } from '@/types/timeline';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { toast } from 'sonner';

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
  entities: [],
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

describe('DeleteEventConfirmation', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    event: mockManualEvent,
    onConfirm: vi.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dialog when open with manual event', () => {
      render(<DeleteEventConfirmation {...defaultProps} />);

      expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      // Title contains "Delete Event" - use heading role to be specific
      expect(screen.getByRole('heading', { name: /delete event/i })).toBeInTheDocument();
    });

    it('does not render when event is null', () => {
      render(<DeleteEventConfirmation {...defaultProps} event={null} />);

      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    });

    it('does not render when event is not manual', () => {
      render(<DeleteEventConfirmation {...defaultProps} event={mockAutoEvent} />);

      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    });

    it('does not render when closed', () => {
      render(<DeleteEventConfirmation {...defaultProps} open={false} />);

      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    });

    it('shows event description', () => {
      render(<DeleteEventConfirmation {...defaultProps} />);

      expect(screen.getByText('Court filing submitted')).toBeInTheDocument();
    });

    it('shows warning message', () => {
      render(<DeleteEventConfirmation {...defaultProps} />);

      expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument();
    });
  });

  describe('Dialog Behavior', () => {
    it('shows Cancel and Delete buttons', () => {
      render(<DeleteEventConfirmation {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete event/i })).toBeInTheDocument();
    });

    it('calls onOpenChange(false) when Cancel is clicked', async () => {
      const user = userEvent.setup();
      const onOpenChange = vi.fn();
      render(<DeleteEventConfirmation {...defaultProps} onOpenChange={onOpenChange} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('calls onConfirm when Delete Event is clicked', async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      render(<DeleteEventConfirmation {...defaultProps} onConfirm={onConfirm} />);

      await user.click(screen.getByRole('button', { name: /delete event/i }));

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalledWith('event-1');
      });
    });

    it('shows success toast on successful deletion', async () => {
      const user = userEvent.setup();
      render(<DeleteEventConfirmation {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /delete event/i }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Event deleted successfully');
      });
    });

    it('shows error toast on failure', async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn().mockRejectedValue(new Error('API Error'));
      render(<DeleteEventConfirmation {...defaultProps} onConfirm={onConfirm} />);

      await user.click(screen.getByRole('button', { name: /delete event/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Failed to delete event. Please try again.');
      });
    });

    it('shows loading state during deletion', async () => {
      const user = userEvent.setup();
      let resolveDelete: () => void;
      const onConfirm = vi.fn().mockImplementation(
        () =>
          new Promise<void>((resolve) => {
            resolveDelete = resolve;
          })
      );
      render(<DeleteEventConfirmation {...defaultProps} onConfirm={onConfirm} />);

      await user.click(screen.getByRole('button', { name: /delete event/i }));

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText(/deleting/i)).toBeInTheDocument();
      });

      // Resolve the promise
      resolveDelete!();

      await waitFor(() => {
        expect(screen.queryByText(/deleting/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper alert dialog title', () => {
      render(<DeleteEventConfirmation {...defaultProps} />);

      // Title is in a heading element
      expect(screen.getByRole('heading', { name: /delete event/i })).toBeInTheDocument();
    });

    it('has confirmation question', () => {
      render(<DeleteEventConfirmation {...defaultProps} />);

      expect(screen.getByText(/are you sure you want to delete/i)).toBeInTheDocument();
    });
  });
});
