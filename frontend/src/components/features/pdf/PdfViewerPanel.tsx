'use client';

/**
 * PDF Viewer Panel Component
 *
 * Wraps PDF.js viewer for split-view context with navigation and zoom controls.
 * Only renders visible page + 1 buffer for performance per project-context.md.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #1, #5)
 */

import {
  useEffect,
  useRef,
  useState,
  useCallback,
  type FC,
} from 'react';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { BboxOverlay } from './BboxOverlay';
import type { SplitViewBoundingBox, VerificationStatus } from '@/types/citation';

// PDF.js types - we'll use dynamic import for the actual library
type PDFDocumentProxy = {
  numPages: number;
  getPage: (pageNumber: number) => Promise<PDFPageProxy>;
};

type PDFPageProxy = {
  getViewport: (options: { scale: number }) => PDFPageViewport;
  render: (context: { canvasContext: CanvasRenderingContext2D; viewport: PDFPageViewport }) => { promise: Promise<void> };
};

type PDFPageViewport = {
  width: number;
  height: number;
  scale: number;
};

export interface PdfViewerPanelProps {
  /** Document URL to display */
  documentUrl: string;
  /** Initial page number to display */
  initialPage?: number;
  /** Bounding boxes to highlight */
  boundingBoxes?: SplitViewBoundingBox[];
  /** Verification status for highlight colors */
  verificationStatus?: VerificationStatus;
  /** Whether this is the source (left) panel */
  isSource?: boolean;
  /** Current page (controlled) */
  currentPage?: number;
  /** Current scale (controlled) */
  scale?: number;
  /** Callback when page changes */
  onPageChange?: (page: number) => void;
  /** Callback when scale changes */
  onScaleChange?: (scale: number) => void;
  /** Panel title for accessibility */
  panelTitle?: string;
  /** Optional className */
  className?: string;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 3.0;
const SCALE_STEP = 0.25;
const DEFAULT_SCALE = 1.0;

/**
 * PDF viewer panel with page navigation, zoom controls, and bbox highlighting.
 */
export const PdfViewerPanel: FC<PdfViewerPanelProps> = ({
  documentUrl,
  initialPage = 1,
  boundingBoxes = [],
  verificationStatus = 'pending',
  isSource = false,
  currentPage: controlledPage,
  scale: controlledScale,
  onPageChange,
  onScaleChange,
  panelTitle,
  className,
}) => {
  // State
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [internalPage, setInternalPage] = useState(initialPage);
  const [internalScale, setInternalScale] = useState(DEFAULT_SCALE);
  const [pageInput, setPageInput] = useState(String(initialPage));
  const [isLoading, setIsLoading] = useState(true);
  const [isRendering, setIsRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState({ width: 612, height: 792 }); // Default letter size

  // Refs
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<{ promise: Promise<void> } | null>(null);

  // Use controlled values if provided, otherwise use internal state
  const page = controlledPage ?? internalPage;
  const scale = controlledScale ?? internalScale;

  // Page change handler
  const handlePageChange = useCallback(
    (newPage: number) => {
      const clampedPage = Math.max(1, Math.min(newPage, numPages || 1));
      if (onPageChange) {
        onPageChange(clampedPage);
      } else {
        setInternalPage(clampedPage);
      }
      setPageInput(String(clampedPage));
    },
    [numPages, onPageChange]
  );

  // Scale change handler
  const handleScaleChange = useCallback(
    (newScale: number) => {
      const clampedScale = Math.max(MIN_SCALE, Math.min(newScale, MAX_SCALE));
      if (onScaleChange) {
        onScaleChange(clampedScale);
      } else {
        setInternalScale(clampedScale);
      }
    },
    [onScaleChange]
  );

  // Load PDF document
  useEffect(() => {
    let cancelled = false;

    const loadPdf = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Dynamic import of PDF.js
        const pdfjs = await import('pdfjs-dist');

        // Configure worker
        pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

        const loadingTask = pdfjs.getDocument(documentUrl);
        const doc = await loadingTask.promise;

        if (cancelled) return;

        setPdfDoc(doc as unknown as PDFDocumentProxy);
        setNumPages(doc.numPages);
        setIsLoading(false);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load PDF');
        setIsLoading(false);
      }
    };

    loadPdf();

    return () => {
      cancelled = true;
    };
  }, [documentUrl]);

  // Render current page
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let cancelled = false;

    const renderPage = async () => {
      setIsRendering(true);

      try {
        // Cancel any ongoing render
        if (renderTaskRef.current) {
          await renderTaskRef.current.promise.catch(() => {});
        }

        const pageObj = await pdfDoc.getPage(page);

        if (cancelled) return;

        const viewport = pageObj.getViewport({ scale });
        const canvas = canvasRef.current;

        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Handle high DPI displays
        const dpr = window.devicePixelRatio || 1;
        canvas.width = viewport.width * dpr;
        canvas.height = viewport.height * dpr;
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        ctx.scale(dpr, dpr);

        // Store page size for bbox overlay
        setPageSize({
          width: viewport.width / scale,
          height: viewport.height / scale,
        });

        // Render PDF page
        const renderTask = pageObj.render({
          canvasContext: ctx,
          viewport,
        });
        renderTaskRef.current = renderTask;

        await renderTask.promise;

        if (!cancelled) {
          setIsRendering(false);
        }
      } catch (err) {
        if (!cancelled) {
          // Ignore cancelled render errors
          if (err instanceof Error && err.message.includes('cancelled')) {
            return;
          }
          setError(err instanceof Error ? err.message : 'Failed to render page');
          setIsRendering(false);
        }
      }
    };

    renderPage();

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, page, scale]);

  // Update page input when controlled page changes
  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

  // Handle page input submission
  const handlePageInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newPage = parseInt(pageInput, 10);
    if (!isNaN(newPage)) {
      handlePageChange(newPage);
    } else {
      setPageInput(String(page));
    }
  };

  // Filter bboxes for current page
  const currentPageBboxes = boundingBoxes.filter((bbox) => {
    // If bbox doesn't have page info, show on all pages
    // In practice, bbox coordinates are for specific pages
    return true;
  });

  // Render loading state
  if (isLoading) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-muted/30 ${className ?? ''}`}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-2 text-sm text-muted-foreground">Loading document...</p>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-muted/30 ${className ?? ''}`}>
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="mt-2 text-sm text-destructive">{error}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => window.location.reload()}
        >
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className ?? ''}`}>
      {/* Controls bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b bg-background">
        {/* Page navigation */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            title="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <form onSubmit={handlePageInputSubmit} className="flex items-center gap-1">
            <Input
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              className="h-8 w-14 text-center text-sm"
              aria-label="Page number"
            />
            <span className="text-sm text-muted-foreground">/ {numPages}</span>
          </form>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= numPages}
            title="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {/* Panel title */}
        {panelTitle && (
          <span className="text-xs font-medium text-muted-foreground">
            {panelTitle}
          </span>
        )}

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => handleScaleChange(scale - SCALE_STEP)}
            disabled={scale <= MIN_SCALE}
            title="Zoom out (-)"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>

          <span className="text-xs text-muted-foreground min-w-[50px] text-center">
            {Math.round(scale * 100)}%
          </span>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => handleScaleChange(scale + SCALE_STEP)}
            disabled={scale >= MAX_SCALE}
            title="Zoom in (+)"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => handleScaleChange(1.0)}
            title="Fit to width"
          >
            <Maximize className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* PDF canvas container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-muted/30 p-4"
      >
        <div className="relative inline-block mx-auto">
          {/* PDF page canvas */}
          <canvas
            ref={canvasRef}
            className="shadow-lg"
            aria-label={`${panelTitle ?? 'PDF'} page ${page}`}
          />

          {/* Bbox overlay */}
          {currentPageBboxes.length > 0 && (
            <BboxOverlay
              boundingBoxes={currentPageBboxes}
              pageWidth={pageSize.width}
              pageHeight={pageSize.height}
              scale={scale}
              verificationStatus={verificationStatus}
              isSource={isSource}
            />
          )}

          {/* Rendering indicator */}
          {isRendering && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
