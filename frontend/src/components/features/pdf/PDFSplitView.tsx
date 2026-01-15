'use client';

/**
 * PDF Split View Container Component
 *
 * Wraps workspace content with a resizable PDF viewer panel.
 * When a source reference is clicked, the PDF viewer opens alongside
 * the workspace content in a split-view layout.
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode (AC: #1, #3, #4, #5)
 */

import { useEffect, useCallback, type ReactNode } from 'react';
import { toast } from 'sonner';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { PdfViewerPanel } from './PdfViewerPanel';
import { PDFSplitViewHeader } from './PDFSplitViewHeader';
import { PdfErrorBoundary } from './PdfErrorBoundary';
import {
  usePdfSplitViewStore,
  selectPdfSplitViewIsOpen,
  selectPdfDocumentUrl,
  selectPdfDocumentName,
  selectPdfCurrentPage,
  selectPdfScale,
} from '@/stores/pdfSplitViewStore';

export interface PDFSplitViewProps {
  /** Workspace content to display on the left */
  children: ReactNode;
}

/**
 * Split view container that shows workspace content alongside a PDF viewer.
 * When not open, simply renders children. When open, shows resizable panels.
 */
export function PDFSplitView({ children }: PDFSplitViewProps) {
  // Zustand selectors for state
  const isOpen = usePdfSplitViewStore(selectPdfSplitViewIsOpen);
  const documentUrl = usePdfSplitViewStore(selectPdfDocumentUrl);
  const documentName = usePdfSplitViewStore(selectPdfDocumentName);
  const currentPage = usePdfSplitViewStore(selectPdfCurrentPage);
  const scale = usePdfSplitViewStore(selectPdfScale);

  // Actions
  const setCurrentPage = usePdfSplitViewStore((state) => state.setCurrentPage);
  const setScale = usePdfSplitViewStore((state) => state.setScale);
  const closePdfSplitView = usePdfSplitViewStore(
    (state) => state.closePdfSplitView
  );

  // Handle expand to full modal (Story 11.6 - placeholder)
  const handleExpand = useCallback(() => {
    // Story 11.6 will implement full modal view
    toast.info('Full screen view coming soon');
  }, []);

  // Keyboard handler for Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        closePdfSplitView();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, closePdfSplitView]);

  // If not open or no document URL, just render children
  if (!isOpen || !documentUrl) {
    return <>{children}</>;
  }

  return (
    <ResizablePanelGroup
      direction="horizontal"
      className="h-full"
      data-testid="pdf-split-view"
    >
      {/* Workspace content panel */}
      <ResizablePanel
        defaultSize={50}
        minSize={30}
        data-testid="pdf-split-view-workspace"
      >
        <div className="h-full overflow-auto">{children}</div>
      </ResizablePanel>

      <ResizableHandle withHandle aria-label="Resize PDF panel" />

      {/* PDF viewer panel */}
      <ResizablePanel
        defaultSize={50}
        minSize={30}
        data-testid="pdf-split-view-pdf"
      >
        <div className="flex h-full flex-col border-l">
          <PDFSplitViewHeader
            documentName={documentName ?? 'Document'}
            onClose={closePdfSplitView}
            onExpand={handleExpand}
          />
          <PdfErrorBoundary>
            <PdfViewerPanel
              documentUrl={documentUrl}
              currentPage={currentPage}
              scale={scale}
              onPageChange={setCurrentPage}
              onScaleChange={setScale}
              panelTitle={documentName ?? 'Document'}
            />
          </PdfErrorBoundary>
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
