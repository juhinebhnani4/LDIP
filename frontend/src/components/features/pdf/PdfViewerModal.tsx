'use client';

/**
 * PDF Viewer Modal Component
 *
 * Full-screen modal for viewing PDFs with pdf.js rendering, page navigation,
 * zoom controls, and download support. Used by the Documents tab "View" action
 * and cross-tab ?doc=&page= navigation.
 *
 * Story 2.3: PDF Modal with Source Navigation
 * BUG-LT3-G: In-app document viewer (replaces window.open raw PDF)
 */

import { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { X, Download, FileText } from 'lucide-react';
import { PdfErrorBoundary } from './PdfErrorBoundary';
import { useBoundingBoxes } from '@/hooks/useBoundingBoxes';

const PdfViewerPanel = dynamic(
  () => import('./PdfViewerPanel').then((m) => ({ default: m.PdfViewerPanel })),
  { ssr: false },
);

interface PdfViewerModalProps {
  /** Whether the modal is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Signed URL of the PDF to display */
  documentUrl: string | null;
  /** Document ID for fetching bounding boxes (BUG-LT3-I fix) */
  documentId?: string;
  /** Document name for display */
  documentName?: string;
  /** Initial page to display (1-indexed) */
  initialPage?: number;
  /** Callback when download is clicked */
  onDownload?: () => void;
}

/**
 * Full-screen PDF viewer modal using pdf.js via PdfViewerPanel.
 *
 * Replaces the previous placeholder implementation with real PDF rendering.
 */
export function PdfViewerModal({
  open,
  onOpenChange,
  documentUrl,
  documentId,
  documentName = 'Document',
  initialPage = 1,
  onDownload,
}: PdfViewerModalProps) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1.0);

  // BUG-LT3-I fix: Fetch bounding boxes for current page
  const { boundingBoxes, bboxPageNumber, fetchByPage, clearBboxes } = useBoundingBoxes();

  // Reset viewer state when a (possibly different) document is opened. Resetting
  // on the documentUrl/initialPage change is intentional — same prop-sync pattern
  // as countdown-timer. (Could become a key-remount/render-phase reset if we ever
  // migrate the whole reset-on-prop family; not worth forking the convention for
  // one site — see FE-024.)
  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCurrentPage(initialPage);
      setScale(1.0);
      setTotalPages(0);
      clearBboxes();
    }
  }, [open, documentUrl, initialPage, clearBboxes]);

  // Fetch bounding boxes when page changes (BUG-LT3-I)
  useEffect(() => {
    if (open && documentId && currentPage > 0) {
      fetchByPage(documentId, currentPage);
    }
  }, [open, documentId, currentPage, fetchByPage]);

  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      onOpenChange(newOpen);
    },
    [onOpenChange],
  );

  const handleDownload = useCallback(() => {
    if (onDownload) {
      onDownload();
    } else if (documentUrl) {
      window.open(documentUrl, '_blank');
    }
  }, [onDownload, documentUrl]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't handle if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        setScale((s) => Math.min(s + 0.25, 3.0));
      } else if (e.key === '-') {
        e.preventDefault();
        setScale((s) => Math.max(s - 0.25, 0.5));
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, currentPage, totalPages]);

  if (!documentUrl) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex h-screen w-screen max-w-none sm:max-w-none flex-col gap-0 overflow-hidden rounded-none border-0 p-0"
        showCloseButton={false}
      >
        <DialogTitle className="sr-only">
          {documentName} - Document Viewer
        </DialogTitle>
        <DialogDescription className="sr-only">
          PDF document viewer. Use arrow keys to navigate pages, plus and minus
          keys to zoom, or press Escape to close.
        </DialogDescription>

        {/* Header bar */}
        <div className="flex shrink-0 items-center justify-between border-b bg-muted/50 px-4 py-2">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span
              className="truncate text-sm font-medium"
              title={documentName}
            >
              {documentName}
            </span>
            {totalPages > 0 && (
              <span className="shrink-0 text-xs text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleDownload}
              title="Download / Open in new tab"
              aria-label="Download document"
            >
              <Download className="h-4 w-4" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => onOpenChange(false)}
              title="Close (Esc)"
              aria-label="Close document viewer"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* PDF Viewer */}
        <div className="min-h-0 flex-1 overflow-hidden">
          <PdfErrorBoundary>
            <PdfViewerPanel
              documentUrl={documentUrl}
              initialPage={initialPage}
              currentPage={currentPage}
              scale={scale}
              onPageChange={setCurrentPage}
              onScaleChange={setScale}
              onTotalPagesChange={setTotalPages}
              panelTitle={documentName}
              boundingBoxes={boundingBoxes}
              bboxPageNumber={bboxPageNumber ?? undefined}
            />
          </PdfErrorBoundary>
        </div>
      </DialogContent>
    </Dialog>
  );
}
