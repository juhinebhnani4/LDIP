'use client';

/**
 * PDF Split View Container Component
 *
 * Wraps workspace content with a resizable PDF viewer panel.
 * When a source reference is clicked, the PDF viewer opens alongside
 * the workspace content in a split-view layout.
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode (AC: #1, #3, #4, #5)
 * Story 11.6: Implement PDF Viewer Full Modal Mode (integration)
 */

import { useEffect, useCallback, type ReactNode } from 'react';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { PdfViewerPanel } from './PdfViewerPanel';
import { PDFSplitViewHeader } from './PDFSplitViewHeader';
import { PdfErrorBoundary } from './PdfErrorBoundary';
import { PDFFullScreenModal } from './PDFFullScreenModal';
import {
  usePdfSplitViewStore,
  selectPdfSplitViewIsOpen,
  selectIsFullScreenOpen,
  selectPdfDocumentUrl,
  selectPdfDocumentName,
  selectPdfCurrentPage,
  selectPdfTotalPages,
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
  const isFullScreenOpen = usePdfSplitViewStore(selectIsFullScreenOpen);
  const documentUrl = usePdfSplitViewStore(selectPdfDocumentUrl);
  const documentName = usePdfSplitViewStore(selectPdfDocumentName);
  const currentPage = usePdfSplitViewStore(selectPdfCurrentPage);
  const totalPages = usePdfSplitViewStore(selectPdfTotalPages);
  const scale = usePdfSplitViewStore(selectPdfScale);

  // Actions
  const setCurrentPage = usePdfSplitViewStore((state) => state.setCurrentPage);
  const setTotalPages = usePdfSplitViewStore((state) => state.setTotalPages);
  const setScale = usePdfSplitViewStore((state) => state.setScale);
  const closePdfSplitView = usePdfSplitViewStore(
    (state) => state.closePdfSplitView
  );
  const openFullScreenModal = usePdfSplitViewStore(
    (state) => state.openFullScreenModal
  );

  // Handle expand to full modal (Story 11.6)
  const handleExpand = useCallback(() => {
    openFullScreenModal();
  }, [openFullScreenModal]);

  // Handle total pages update from PDF viewer
  const handleTotalPagesChange = useCallback(
    (pages: number) => {
      setTotalPages(pages);
    },
    [setTotalPages]
  );

  // Keyboard handler for split view (Escape to close, F to toggle full screen)
  // Full screen modal has its own Escape handler with higher priority
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only close split view if full screen modal is NOT open
      // (modal has priority and handles its own Escape)
      if (e.key === 'Escape' && isOpen && !isFullScreenOpen) {
        e.preventDefault();
        closePdfSplitView();
        return;
      }

      // F key toggles full screen from split view (AC: #4.4)
      // Only trigger if not typing in an input and not already in full screen
      if (
        (e.key === 'f' || e.key === 'F') &&
        isOpen &&
        !isFullScreenOpen &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault();
        openFullScreenModal();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, isFullScreenOpen, closePdfSplitView, openFullScreenModal]);

  // If not open or no document URL, just render children
  if (!isOpen || !documentUrl) {
    return <>{children}</>;
  }

  return (
    <>
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
              currentPage={currentPage}
              totalPages={totalPages > 0 ? totalPages : undefined}
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
                onTotalPagesChange={handleTotalPagesChange}
                panelTitle={documentName ?? 'Document'}
              />
            </PdfErrorBoundary>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      {/* Full screen modal - renders via portal above everything (Story 11.6) */}
      <PDFFullScreenModal />
    </>
  );
}
