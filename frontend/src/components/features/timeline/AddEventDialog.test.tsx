/**
 * AddEventDialog Tests
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AddEventDialog } from './AddEventDialog';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// toast is mocked above via vi.mock('sonner')

// Mock entities
const mockEntities = [
  { id: 'entity-1', name: 'John Smith' },
  { id: 'entity-2', name: 'ABC Corporation' },
];

// Mock documents
const mockDocuments = [
  { id: 'doc-1', name: 'Contract.pdf' },
  { id: 'doc-2', name: 'Amendment.pdf' },
];

describe('AddEventDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onSubmit: vi.fn().mockResolvedValue(undefined),
    entities: mockEntities,
    documents: mockDocuments,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dialog when open', () => {
      render(<AddEventDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Add Timeline Event')).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      render(<AddEventDialog {...defaultProps} open={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows manual event info badge', () => {
      render(<AddEventDialog {...defaultProps} />);

      expect(
        screen.getByText(/this event will be marked as manually added/i)
      ).toBeInTheDocument();
    });

    it('renders form fields', () => {
      render(<AddEventDialog {...defaultProps} />);

      // Check form elements exist
      expect(screen.getByText(/pick a date/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/brief description of the event/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/additional details/i)).toBeInTheDocument();
    });

    it('renders cancel and submit buttons', () => {
      render(<AddEventDialog {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add event/i })).toBeInTheDocument();
    });

    it('renders actor checkboxes', () => {
      render(<AddEventDialog {...defaultProps} />);

      expect(screen.getByLabelText('John Smith')).toBeInTheDocument();
      expect(screen.getByLabelText('ABC Corporation')).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('shows error for title too short', async () => {
      const user = userEvent.setup();
      render(<AddEventDialog {...defaultProps} />);

      await user.type(screen.getByPlaceholderText(/brief description/i), 'abc');
      await user.click(screen.getByRole('button', { name: /add event/i }));

      await waitFor(() => {
        expect(screen.getByText(/title must be at least 5 characters/i)).toBeInTheDocument();
      });
    });

    it('shows error for title too long', async () => {
      const user = userEvent.setup();
      render(<AddEventDialog {...defaultProps} />);

      // Use paste instead of type for long strings to avoid timeout
      const longTitle = 'a'.repeat(201);
      const titleInput = screen.getByPlaceholderText(/brief description/i);
      await user.click(titleInput);
      await user.paste(longTitle);
      await user.click(screen.getByRole('button', { name: /add event/i }));

      await waitFor(() => {
        expect(screen.getByText(/title cannot exceed 200 characters/i)).toBeInTheDocument();
      });
    });
  });

  describe('Dialog Behavior', () => {
    it('closes on cancel button click', async () => {
      const user = userEvent.setup();
      const onOpenChange = vi.fn();
      render(<AddEventDialog {...defaultProps} onOpenChange={onOpenChange} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Actor Selection', () => {
    it('renders actor checkboxes for each entity', () => {
      render(<AddEventDialog {...defaultProps} />);

      expect(screen.getByLabelText('John Smith')).toBeInTheDocument();
      expect(screen.getByLabelText('ABC Corporation')).toBeInTheDocument();
    });

    it('allows toggling actor checkboxes', async () => {
      const user = userEvent.setup();
      render(<AddEventDialog {...defaultProps} />);

      const johnCheckbox = screen.getByLabelText('John Smith');
      expect(johnCheckbox).not.toBeChecked();

      await user.click(johnCheckbox);
      expect(johnCheckbox).toBeChecked();

      await user.click(johnCheckbox);
      expect(johnCheckbox).not.toBeChecked();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading', () => {
      render(<AddEventDialog {...defaultProps} />);
      expect(screen.getByText('Add Timeline Event')).toBeInTheDocument();
    });

    it('has description', () => {
      render(<AddEventDialog {...defaultProps} />);
      expect(
        screen.getByText(/add an event that isn't captured in the documents/i)
      ).toBeInTheDocument();
    });

    it('shows required field indicators', () => {
      render(<AddEventDialog {...defaultProps} />);

      // Required fields should have * indicator
      const eventDateLabels = screen.getAllByText(/event date/i);
      expect(eventDateLabels[0]!.parentElement).toHaveTextContent('*');
    });

    it('has info badge about manual event', () => {
      render(<AddEventDialog {...defaultProps} />);

      expect(
        screen.getByText(/this event will be marked as manually added/i)
      ).toBeInTheDocument();
    });
  });
});
