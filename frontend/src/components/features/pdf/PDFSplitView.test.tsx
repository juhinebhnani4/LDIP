/**
 * PDFSplitView Unit Tests
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode (AC: #1, #3, #4, #5)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PDFSplitView } from './PDFSplitView';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    info: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock PdfViewerPanel to avoid PDF.js complexity in unit tests
vi.mock('./PdfViewerPanel', () => ({
  PdfViewerPanel: ({ documentUrl, panelTitle }: { documentUrl: string; panelTitle: string }) => (
    <div data-testid="pdf-viewer-panel" data-url={documentUrl}>
      {panelTitle}
    </div>
  ),
}));

// Mock PdfErrorBoundary
vi.mock('./PdfErrorBoundary', () => ({
  PdfErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('PDFSplitView', () => {
  beforeEach(() => {
    // Reset store state before each test
    act(() => {
      usePdfSplitViewStore.getState().reset();
    });
    vi.clearAllMocks();
  });

  describe('when split view is closed', () => {
    it('renders children without split layout (AC: #1)', () => {
      render(
        <PDFSplitView>
          <div data-testid="workspace-content">Workspace Content</div>
        </PDFSplitView>
      );

      expect(screen.getByTestId('workspace-content')).toBeInTheDocument();
      expect(screen.getByText('Workspace Content')).toBeInTheDocument();
      expect(screen.queryByTestId('pdf-split-view')).not.toBeInTheDocument();
    });

    it('does not render PDF viewer panel', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      expect(screen.queryByTestId('pdf-viewer-panel')).not.toBeInTheDocument();
    });
  });

  describe('when split view is open', () => {
    beforeEach(() => {
      // Open split view with mock data
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          {
            documentId: 'doc-123',
            documentName: 'Test Document.pdf',
            page: 5,
            chunkId: 'chunk-1',
          },
          'matter-456',
          'https://example.com/documents/doc-123.pdf'
        );
      });
    });

    it('renders split view container (AC: #1)', () => {
      render(
        <PDFSplitView>
          <div data-testid="workspace-content">Workspace Content</div>
        </PDFSplitView>
      );

      expect(screen.getByTestId('pdf-split-view')).toBeInTheDocument();
    });

    it('renders workspace content in left panel (AC: #1)', () => {
      render(
        <PDFSplitView>
          <div data-testid="workspace-content">Workspace Content</div>
        </PDFSplitView>
      );

      expect(screen.getByTestId('pdf-split-view-workspace')).toBeInTheDocument();
      expect(screen.getByText('Workspace Content')).toBeInTheDocument();
    });

    it('renders PDF viewer panel on right (AC: #1)', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      expect(screen.getByTestId('pdf-split-view-pdf')).toBeInTheDocument();
      expect(screen.getByTestId('pdf-viewer-panel')).toBeInTheDocument();
    });

    it('displays document name in header (AC: #2)', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Document name appears in both header and mocked PDF viewer panel
      const documentNames = screen.getAllByText('Test Document.pdf');
      expect(documentNames.length).toBeGreaterThanOrEqual(1);
    });

    it('passes document URL to PDF viewer', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      const pdfViewer = screen.getByTestId('pdf-viewer-panel');
      expect(pdfViewer).toHaveAttribute(
        'data-url',
        'https://example.com/documents/doc-123.pdf'
      );
    });

    it('renders resize handle', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      expect(screen.getByRole('separator', { name: /resize pdf panel/i })).toBeInTheDocument();
    });

    it('closes split view when close button is clicked (AC: #5)', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Click close button
      fireEvent.click(screen.getByRole('button', { name: /close pdf viewer/i }));

      // Split view should be closed
      expect(usePdfSplitViewStore.getState().isOpen).toBe(false);
    });

    it('closes split view when Escape key is pressed (AC: #5)', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Press Escape key
      fireEvent.keyDown(document, { key: 'Escape' });

      // Split view should be closed
      expect(usePdfSplitViewStore.getState().isOpen).toBe(false);
    });

    it('shows toast when expand button is clicked (placeholder for Story 11.6)', async () => {
      const { toast } = await import('sonner');

      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Click expand button
      fireEvent.click(screen.getByRole('button', { name: /open document in full screen/i }));

      expect(toast.info).toHaveBeenCalledWith('Full screen mode will be available in Story 11.6');
    });

    it('workspace content remains interactive (AC: #1)', () => {
      const handleClick = vi.fn();

      render(
        <PDFSplitView>
          <button onClick={handleClick}>Interactive Button</button>
        </PDFSplitView>
      );

      fireEvent.click(screen.getByText('Interactive Button'));

      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('with missing document URL', () => {
    it('renders children when document URL is null', () => {
      // Open with URL, then manually set URL to null
      act(() => {
        usePdfSplitViewStore.setState({ isOpen: true, documentUrl: null });
      });

      render(
        <PDFSplitView>
          <div data-testid="workspace-content">Workspace Content</div>
        </PDFSplitView>
      );

      // Should render children only (no split view)
      expect(screen.getByTestId('workspace-content')).toBeInTheDocument();
      expect(screen.queryByTestId('pdf-split-view')).not.toBeInTheDocument();
    });
  });

  describe('keyboard navigation', () => {
    beforeEach(() => {
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf', page: 1 },
          'matter-1',
          'https://example.com/doc.pdf'
        );
      });
    });

    it('does not close on other key presses', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Press other keys
      fireEvent.keyDown(document, { key: 'Enter' });
      fireEvent.keyDown(document, { key: 'Space' });
      fireEvent.keyDown(document, { key: 'Tab' });

      // Split view should still be open
      expect(usePdfSplitViewStore.getState().isOpen).toBe(true);
    });

    it('removes keyboard listener on unmount', () => {
      const { unmount } = render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Unmount component
      unmount();

      // Press Escape - should not cause errors
      fireEvent.keyDown(document, { key: 'Escape' });

      // Store should still be open (listener was removed)
      expect(usePdfSplitViewStore.getState().isOpen).toBe(true);
    });

    it('removes keyboard listener when split view closes', () => {
      render(
        <PDFSplitView>
          <div>Content</div>
        </PDFSplitView>
      );

      // Close the split view
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      // Re-open and check Escape still works
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-2', documentName: 'Another.pdf' },
          'matter-2',
          'https://example.com/doc2.pdf'
        );
      });

      // Escape should close the new split view
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(usePdfSplitViewStore.getState().isOpen).toBe(false);
    });
  });
});
