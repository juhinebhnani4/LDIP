import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ManualReviewDialog } from './ManualReviewDialog';
import type { PageConfidence } from '@/types/document';

// Mock the API module
vi.mock('@/lib/api/documents', () => ({
  requestManualReview: vi.fn(),
}));

import { requestManualReview } from '@/lib/api/documents';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { toast } from 'sonner';

const mockPageConfidences: PageConfidence[] = [
  { pageNumber: 1, confidence: 0.45, wordCount: 400 },
  { pageNumber: 2, confidence: 0.65, wordCount: 400 },
  { pageNumber: 3, confidence: 0.55, wordCount: 400 },
  { pageNumber: 4, confidence: 0.85, wordCount: 400 },
  { pageNumber: 5, confidence: 0.92, wordCount: 400 },
];

describe('ManualReviewDialog', () => {
  const defaultProps = {
    documentId: 'doc-123',
    pageConfidences: mockPageConfidences,
    open: true,
    onOpenChange: vi.fn(),
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (requestManualReview as ReturnType<typeof vi.fn>).mockResolvedValue({
      documentId: 'doc-123',
      pagesAdded: 2,
      success: true,
    });
  });

  describe('Rendering', () => {
    it('renders dialog title and description', () => {
      render(<ManualReviewDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Request Manual Review')).toBeInTheDocument();
      expect(screen.getByText(/Select pages that need manual review/)).toBeInTheDocument();
    });

    it('renders all page checkboxes', () => {
      render(<ManualReviewDialog {...defaultProps} />);

      expect(screen.getByText('Page 1')).toBeInTheDocument();
      expect(screen.getByText('Page 2')).toBeInTheDocument();
      expect(screen.getByText('Page 3')).toBeInTheDocument();
      expect(screen.getByText('Page 4')).toBeInTheDocument();
      expect(screen.getByText('Page 5')).toBeInTheDocument();
    });

    it('shows confidence percentage for each page', () => {
      render(<ManualReviewDialog {...defaultProps} />);

      expect(screen.getByText('45%')).toBeInTheDocument();
      expect(screen.getByText('65%')).toBeInTheDocument();
      expect(screen.getByText('55%')).toBeInTheDocument();
      expect(screen.getByText('85%')).toBeInTheDocument();
      expect(screen.getByText('92%')).toBeInTheDocument();
    });
  });

  describe('Quick Actions', () => {
    it('shows Select Low Quality button with count', () => {
      render(<ManualReviewDialog {...defaultProps} />);

      // Pages with <60% confidence: 1 (45%), 3 (55%) = 2 pages
      expect(screen.getByRole('button', { name: /Select Low Quality \(2\)/ })).toBeInTheDocument();
    });

    it('selects low confidence pages when button clicked', async () => {
      const user = userEvent.setup();
      render(<ManualReviewDialog {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));

      // Should show 2 pages selected
      expect(screen.getByText('2 pages selected')).toBeInTheDocument();
    });

    it('selects all pages when Select All clicked', async () => {
      const user = userEvent.setup();
      render(<ManualReviewDialog {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Select All/ }));

      expect(screen.getByText('5 pages selected')).toBeInTheDocument();
    });

    it('clears selection when Clear All clicked', async () => {
      const user = userEvent.setup();
      render(<ManualReviewDialog {...defaultProps} />);

      // First select all
      await user.click(screen.getByRole('button', { name: /Select All/ }));
      expect(screen.getByText('5 pages selected')).toBeInTheDocument();

      // Then clear
      await user.click(screen.getByRole('button', { name: /Clear All/ }));
      expect(screen.getByText('0 pages selected')).toBeInTheDocument();
    });
  });

  describe('Page Selection', () => {
    it('toggles individual page selection', async () => {
      const user = userEvent.setup();
      render(<ManualReviewDialog {...defaultProps} />);

      // Click on Page 1 label to toggle
      const page1Label = screen.getByText('Page 1').closest('label');
      if (page1Label) {
        await user.click(page1Label);
      }

      expect(screen.getByText('1 page selected')).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('disables submit button when no pages are selected', async () => {
      render(<ManualReviewDialog {...defaultProps} />);

      // Submit button should be disabled when no pages are selected
      expect(screen.getByRole('button', { name: /Request Review/ })).toBeDisabled();
    });

    it('calls API with selected pages on submit', async () => {
      const user = userEvent.setup();
      render(<ManualReviewDialog {...defaultProps} />);

      // Select low confidence pages
      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));

      // Submit
      await user.click(screen.getByRole('button', { name: /Request Review/ }));

      await waitFor(() => {
        expect(requestManualReview).toHaveBeenCalledWith('doc-123', [1, 3]);
      });
    });

    it('shows success toast on successful submission', async () => {
      const user = userEvent.setup();
      render(<ManualReviewDialog {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));
      await user.click(screen.getByRole('button', { name: /Request Review/ }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('2 pages added to review queue');
      });
    });

    it('calls onSuccess callback after submission', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();
      render(<ManualReviewDialog {...defaultProps} onSuccess={onSuccess} />);

      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));
      await user.click(screen.getByRole('button', { name: /Request Review/ }));

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled();
      });
    });

    it('closes dialog after successful submission', async () => {
      const user = userEvent.setup();
      const onOpenChange = vi.fn();
      render(<ManualReviewDialog {...defaultProps} onOpenChange={onOpenChange} />);

      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));
      await user.click(screen.getByRole('button', { name: /Request Review/ }));

      await waitFor(() => {
        expect(onOpenChange).toHaveBeenCalledWith(false);
      });
    });

    it('shows error toast on API failure', async () => {
      const user = userEvent.setup();
      (requestManualReview as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      render(<ManualReviewDialog {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));
      await user.click(screen.getByRole('button', { name: /Request Review/ }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Network error');
      });
    });

    it('disables submit button while submitting', async () => {
      const user = userEvent.setup();
      // Make the API call hang
      (requestManualReview as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      render(<ManualReviewDialog {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Select Low Quality/ }));
      await user.click(screen.getByRole('button', { name: /Request Review/ }));

      expect(screen.getByRole('button', { name: /Submitting/ })).toBeDisabled();
    });
  });

  describe('Cancel Button', () => {
    it('closes dialog when Cancel is clicked', async () => {
      const user = userEvent.setup();
      const onOpenChange = vi.fn();
      render(<ManualReviewDialog {...defaultProps} onOpenChange={onOpenChange} />);

      await user.click(screen.getByRole('button', { name: /Cancel/ }));

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
