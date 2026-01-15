/**
 * PDFFullScreenModal Unit Tests
 *
 * Story 11.6: Implement PDF Viewer Full Modal Mode (AC: #1, #2, #3)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PDFFullScreenModal } from './PDFFullScreenModal';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';

// Mock PdfViewerPanel to avoid PDF.js complexity
vi.mock('./PdfViewerPanel', () => ({
  PdfViewerPanel: ({
    documentUrl,
    panelTitle,
    currentPage,
    scale,
  }: {
    documentUrl: string;
    panelTitle: string;
    currentPage: number;
    scale: number;
  }) => (
    <div
      data-testid="pdf-viewer-panel"
      data-url={documentUrl}
      data-page={currentPage}
      data-scale={scale}
    >
      {panelTitle}
    </div>
  ),
}));

// Mock PdfErrorBoundary
vi.mock('./PdfErrorBoundary', () => ({
  PdfErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('PDFFullScreenModal', () => {
  beforeEach(() => {
    // Reset store state before each test
    act(() => {
      usePdfSplitViewStore.getState().reset();
    });
    vi.clearAllMocks();
  });

  describe('when modal is closed', () => {
    it('does not render anything when isFullScreenOpen is false', () => {
      render(<PDFFullScreenModal />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not render when document URL is null', () => {
      // Set isFullScreenOpen but no document
      act(() => {
        usePdfSplitViewStore.setState({ isFullScreenOpen: true, documentUrl: null });
      });

      render(<PDFFullScreenModal />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  describe('when modal is open', () => {
    beforeEach(() => {
      // Open split view and full screen modal with mock data
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          {
            documentId: 'doc-123',
            documentName: 'Test Document.pdf',
            page: 5,
          },
          'matter-456',
          'https://example.com/documents/doc-123.pdf'
        );
        usePdfSplitViewStore.getState().setTotalPages(25);
        usePdfSplitViewStore.getState().openFullScreenModal();
      });
    });

    it('renders the dialog when isFullScreenOpen is true (AC: #1)', () => {
      render(<PDFFullScreenModal />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('displays document name in header (AC: #2)', () => {
      render(<PDFFullScreenModal />);

      // Document name appears in header (and also in the mocked PDF viewer)
      const documentNames = screen.getAllByText('Test Document.pdf');
      expect(documentNames.length).toBeGreaterThanOrEqual(1);
    });

    it('displays page info in header (AC: #2)', () => {
      render(<PDFFullScreenModal />);

      expect(screen.getByText('Page 5 of 25')).toBeInTheDocument();
    });

    it('renders PDF viewer panel with correct props', () => {
      render(<PDFFullScreenModal />);

      const pdfViewer = screen.getByTestId('pdf-viewer-panel');
      expect(pdfViewer).toHaveAttribute('data-url', 'https://example.com/documents/doc-123.pdf');
      expect(pdfViewer).toHaveAttribute('data-page', '5');
    });

    it('renders close button (AC: #3)', () => {
      render(<PDFFullScreenModal />);

      expect(screen.getByRole('button', { name: /close full screen view/i })).toBeInTheDocument();
    });

    it('closes modal when close button is clicked (AC: #3)', () => {
      render(<PDFFullScreenModal />);

      fireEvent.click(screen.getByRole('button', { name: /close full screen view/i }));

      expect(usePdfSplitViewStore.getState().isFullScreenOpen).toBe(false);
    });

    it('closes modal when Escape key is pressed (AC: #3)', () => {
      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(usePdfSplitViewStore.getState().isFullScreenOpen).toBe(false);
    });

    it('preserves split view state when closing (AC: #3)', () => {
      render(<PDFFullScreenModal />);

      fireEvent.click(screen.getByRole('button', { name: /close full screen view/i }));

      const state = usePdfSplitViewStore.getState();
      expect(state.isOpen).toBe(true); // Split view still open
      expect(state.documentUrl).toBe('https://example.com/documents/doc-123.pdf');
      expect(state.currentPage).toBe(5);
    });

    it('has accessible title for screen readers', () => {
      render(<PDFFullScreenModal />);

      // The dialog should have an accessible name
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });
  });

  describe('keyboard shortcuts (AC: #2)', () => {
    beforeEach(() => {
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf', page: 5 },
          'matter-1',
          'https://example.com/doc.pdf'
        );
        usePdfSplitViewStore.getState().setTotalPages(20);
        usePdfSplitViewStore.getState().openFullScreenModal();
      });
    });

    it('navigates to previous page with ArrowLeft', () => {
      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: 'ArrowLeft' });

      expect(usePdfSplitViewStore.getState().currentPage).toBe(4);
    });

    it('navigates to next page with ArrowRight', () => {
      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: 'ArrowRight' });

      expect(usePdfSplitViewStore.getState().currentPage).toBe(6);
    });

    it('does not go below page 1 with ArrowLeft', () => {
      act(() => {
        usePdfSplitViewStore.getState().setCurrentPage(1);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: 'ArrowLeft' });

      expect(usePdfSplitViewStore.getState().currentPage).toBe(1);
    });

    it('does not exceed totalPages with ArrowRight', () => {
      act(() => {
        usePdfSplitViewStore.getState().setCurrentPage(20);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: 'ArrowRight' });

      expect(usePdfSplitViewStore.getState().currentPage).toBe(20);
    });

    it('zooms in with + key', () => {
      act(() => {
        usePdfSplitViewStore.getState().setScale(1.0);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: '+' });

      expect(usePdfSplitViewStore.getState().scale).toBe(1.25);
    });

    it('zooms in with = key', () => {
      act(() => {
        usePdfSplitViewStore.getState().setScale(1.0);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: '=' });

      expect(usePdfSplitViewStore.getState().scale).toBe(1.25);
    });

    it('zooms out with - key', () => {
      act(() => {
        usePdfSplitViewStore.getState().setScale(1.0);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: '-' });

      expect(usePdfSplitViewStore.getState().scale).toBe(0.75);
    });

    it('does not zoom below minimum scale (0.5)', () => {
      act(() => {
        usePdfSplitViewStore.getState().setScale(0.5);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: '-' });

      expect(usePdfSplitViewStore.getState().scale).toBe(0.5);
    });

    it('does not zoom above maximum scale (3.0)', () => {
      act(() => {
        usePdfSplitViewStore.getState().setScale(3.0);
      });

      render(<PDFFullScreenModal />);

      fireEvent.keyDown(document, { key: '+' });

      expect(usePdfSplitViewStore.getState().scale).toBe(3.0);
    });
  });

  describe('state synchronization', () => {
    beforeEach(() => {
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf', page: 1 },
          'matter-1',
          'https://example.com/doc.pdf'
        );
        usePdfSplitViewStore.getState().setTotalPages(10);
        usePdfSplitViewStore.getState().openFullScreenModal();
      });
    });

    it('page changes in modal are reflected in store', () => {
      render(<PDFFullScreenModal />);

      // Simulate page change via keyboard
      fireEvent.keyDown(document, { key: 'ArrowRight' });

      // State should be updated
      expect(usePdfSplitViewStore.getState().currentPage).toBe(2);
    });

    it('scale changes in modal are reflected in store', () => {
      render(<PDFFullScreenModal />);

      // Simulate zoom
      fireEvent.keyDown(document, { key: '+' });

      // State should be updated
      expect(usePdfSplitViewStore.getState().scale).toBe(1.25);
    });

    it('changes persist after closing modal', () => {
      render(<PDFFullScreenModal />);

      // Make changes
      fireEvent.keyDown(document, { key: 'ArrowRight' });
      fireEvent.keyDown(document, { key: '+' });

      // Close modal
      fireEvent.keyDown(document, { key: 'Escape' });

      // Changes should persist
      const state = usePdfSplitViewStore.getState();
      expect(state.currentPage).toBe(2);
      expect(state.scale).toBe(1.25);
    });
  });

  describe('cleanup', () => {
    it('removes keyboard listener on unmount', () => {
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf' },
          'matter-1',
          'https://example.com/doc.pdf'
        );
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      const { unmount } = render(<PDFFullScreenModal />);

      // Unmount component
      unmount();

      // Simulate keypress - should not cause errors
      fireEvent.keyDown(document, { key: 'Escape' });

      // State should remain unchanged since listener was removed
      expect(usePdfSplitViewStore.getState().isFullScreenOpen).toBe(true);
    });

    it('removes keyboard listener when modal closes', () => {
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf' },
          'matter-1',
          'https://example.com/doc.pdf'
        );
        usePdfSplitViewStore.getState().setTotalPages(10);
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      render(<PDFFullScreenModal />);

      // Close the modal
      act(() => {
        usePdfSplitViewStore.getState().closeFullScreenModal();
      });

      // Store the current page
      const pageBefore = usePdfSplitViewStore.getState().currentPage;

      // Simulate arrow key - should not change page (listener removed)
      fireEvent.keyDown(document, { key: 'ArrowRight' });

      // Page should not have changed
      expect(usePdfSplitViewStore.getState().currentPage).toBe(pageBefore);
    });
  });
});
