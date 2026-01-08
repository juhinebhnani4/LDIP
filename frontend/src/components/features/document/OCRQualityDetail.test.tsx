import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OCRQualityDetail } from './OCRQualityDetail';
import type { OCRConfidenceResult } from '@/types/document';

// Mock the API module
vi.mock('@/lib/api/documents', () => ({
  fetchOCRQuality: vi.fn(),
  requestManualReview: vi.fn(),
}));

import { fetchOCRQuality, requestManualReview } from '@/lib/api/documents';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockQualityGood: OCRConfidenceResult = {
  documentId: 'doc-123',
  overallConfidence: 0.92,
  qualityStatus: 'good',
  totalWords: 1500,
  pageConfidences: [
    { pageNumber: 1, confidence: 0.95, wordCount: 500 },
    { pageNumber: 2, confidence: 0.90, wordCount: 500 },
    { pageNumber: 3, confidence: 0.91, wordCount: 500 },
  ],
};

const mockQualityPoor: OCRConfidenceResult = {
  documentId: 'doc-123',
  overallConfidence: 0.58,
  qualityStatus: 'poor',
  totalWords: 1200,
  pageConfidences: [
    { pageNumber: 1, confidence: 0.45, wordCount: 400 },
    { pageNumber: 2, confidence: 0.65, wordCount: 400 },
    { pageNumber: 3, confidence: 0.64, wordCount: 400 },
  ],
};

describe('OCRQualityDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows skeleton while loading', () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      render(<OCRQualityDetail documentId="doc-123" />);

      // Should show skeleton elements
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Rendering Quality Data', () => {
    it('displays overall confidence percentage', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('92%')).toBeInTheDocument();
      });
    });

    it('displays quality status label', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('Good Quality')).toBeInTheDocument();
      });
    });

    it('displays total word count', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText(/1,500 words/)).toBeInTheDocument();
      });
    });

    it('displays page count', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText(/3 pages/)).toBeInTheDocument();
      });
    });
  });

  describe('Per-Page Breakdown', () => {
    it('renders page confidence buttons', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('P1')).toBeInTheDocument();
        expect(screen.getByText('P2')).toBeInTheDocument();
        expect(screen.getByText('P3')).toBeInTheDocument();
      });
    });

    it('shows percentage for each page', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('95%')).toBeInTheDocument();
        expect(screen.getByText('90%')).toBeInTheDocument();
        expect(screen.getByText('91%')).toBeInTheDocument();
      });
    });

    it('calls onPageClick when page button is clicked', async () => {
      const user = userEvent.setup();
      const onPageClick = vi.fn();
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" onPageClick={onPageClick} />);

      await waitFor(() => {
        expect(screen.getByText('P1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('P1'));

      expect(onPageClick).toHaveBeenCalledWith(1);
    });
  });

  describe('Request Manual Review Button', () => {
    it('shows button for poor quality', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityPoor);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /request manual review/i })).toBeInTheDocument();
      });
    });

    it('does not show button for good quality', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('Good Quality')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /request manual review/i })).not.toBeInTheDocument();
    });

    it('opens dialog when button is clicked', async () => {
      const user = userEvent.setup();
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityPoor);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /request manual review/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /request manual review/i }));

      await waitFor(() => {
        // Dialog title should appear
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message on API failure', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });

  describe('Legend', () => {
    it('shows color legend for quality levels', async () => {
      (fetchOCRQuality as ReturnType<typeof vi.fn>).mockResolvedValue(mockQualityGood);

      render(<OCRQualityDetail documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText(/Good \(85%\+\)/)).toBeInTheDocument();
        expect(screen.getByText(/Fair \(70-85%\)/)).toBeInTheDocument();
        expect(screen.getByText(/Poor/)).toBeInTheDocument();
      });
    });
  });
});
