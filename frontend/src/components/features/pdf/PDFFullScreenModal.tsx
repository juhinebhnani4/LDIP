'use client';

/**
 * PDF Full Screen Modal Component
 *
 * Full-viewport modal for viewing PDFs with complete navigation and zoom controls.
 * Opens from split view expand button, closes back to split view preserving state.
 *
 * Story 11.6: Implement PDF Viewer Full Modal Mode (AC: #1, #2, #3)
 */

import { useEffect, useCallback } from 'react';
import { X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { PdfViewerPanel } from './PdfViewerPanel';
import { PdfErrorBoundary } from './PdfErrorBoundary';
import {
  usePdfSplitViewStore,
  selectIsFullScreenOpen,
  selectPdfDocumentUrl,
  selectPdfDocumentName,
  selectPdfCurrentPage,
  selectPdfTotalPages,
  selectPdfScale,
  selectPdfBoundingBoxes,
  selectPdfBboxPageNumber,
} from '@/stores/pdfSplitViewStore';
import type { SplitViewBoundingBox } from '@/types/citation';

const MIN_SCALE = 0.5;
const MAX_SCALE = 3.0;
const SCALE_STEP = 0.25;

/**
 * Full screen modal for PDF viewing with complete navigation controls.
 * Renders via portal above all content when isFullScreenOpen is true.
 */
export function PDFFullScreenModal() {
  // Zustand selectors for state
  const isOpen = usePdfSplitViewStore(selectIsFullScreenOpen);
  const documentUrl = usePdfSplitViewStore(selectPdfDocumentUrl);
  const documentName = usePdfSplitViewStore(selectPdfDocumentName);
  const currentPage = usePdfSplitViewStore(selectPdfCurrentPage);
  const totalPages = usePdfSplitViewStore(selectPdfTotalPages);
  const scale = usePdfSplitViewStore(selectPdfScale);
  // Story 11.7: Bounding box state for source text highlighting
  const boundingBoxes = usePdfSplitViewStore(selectPdfBoundingBoxes);
  const bboxPageNumber = usePdfSplitViewStore(selectPdfBboxPageNumber);

  // Actions
  const setCurrentPage = usePdfSplitViewStore((state) => state.setCurrentPage);
  const setScale = usePdfSplitViewStore((state) => state.setScale);
  const closeFullScreenModal = usePdfSplitViewStore(
    (state) => state.closeFullScreenModal
  );

  // Handle dialog close via open change
  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (!open) {
        closeFullScreenModal();
      }
    },
    [closeFullScreenModal]
  );

  // Keyboard shortcuts (AC: #3 - Escape closes modal)
  // Additional navigation: Arrow keys for pages, +/- for zoom
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape is handled by Dialog component, but we add explicit handling
      // for modal-specific shortcuts
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        closeFullScreenModal();
        return;
      }

      // Page navigation with arrow keys
      if (e.key === 'ArrowLeft' && currentPage > 1) {
        e.preventDefault();
        setCurrentPage(currentPage - 1);
      } else if (e.key === 'ArrowRight' && currentPage < totalPages) {
        e.preventDefault();
        setCurrentPage(currentPage + 1);
      }

      // Zoom shortcuts
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        setScale(Math.min(scale + SCALE_STEP, MAX_SCALE));
      } else if (e.key === '-') {
        e.preventDefault();
        setScale(Math.max(scale - SCALE_STEP, MIN_SCALE));
      }
    };

    // Use capture phase to ensure we handle before other listeners
    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [
    isOpen,
    currentPage,
    totalPages,
    scale,
    setCurrentPage,
    setScale,
    closeFullScreenModal,
  ]);

  // Don't render if not open or no document URL
  if (!isOpen || !documentUrl) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex h-[95vh] max-w-[95vw] flex-col gap-0 overflow-hidden p-0"
        showCloseButton={false}
      >
        {/* Visually hidden title and description for accessibility */}
        <DialogTitle className="sr-only">
          {documentName ?? 'Document'} - Full Screen View
        </DialogTitle>
        <DialogDescription className="sr-only">
          Full screen PDF viewer. Use arrow keys to navigate pages, plus and
          minus keys to zoom, or press Escape to close.
        </DialogDescription>

        {/* Header bar with document name, page info, and close button */}
        <div
          className="flex shrink-0 items-center justify-between border-b bg-muted/50 px-4 py-2"
          role="banner"
          aria-label="PDF viewer header"
        >
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <span
              className="truncate text-sm font-medium"
              title={documentName ?? 'Document'}
            >
              {documentName ?? 'Document'}
            </span>
            {totalPages > 0 && (
              <span className="shrink-0 text-xs text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={closeFullScreenModal}
            title="Close (Esc)"
            aria-label="Close full screen view"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* PDF Viewer - takes remaining space */}
        <div className="min-h-0 flex-1 overflow-hidden">
          <PdfErrorBoundary>
            <PdfViewerPanel
              documentUrl={documentUrl}
              currentPage={currentPage}
              scale={scale}
              onPageChange={setCurrentPage}
              onScaleChange={setScale}
              panelTitle={documentName ?? 'Document'}
              boundingBoxes={boundingBoxes as SplitViewBoundingBox[]}
              bboxPageNumber={bboxPageNumber ?? undefined}
              highlightType="citation"
            />
          </PdfErrorBoundary>
        </div>
      </DialogContent>
    </Dialog>
  );
}
