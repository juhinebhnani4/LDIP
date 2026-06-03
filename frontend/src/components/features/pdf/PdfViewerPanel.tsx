'use client';

/**
 * PDF Viewer Panel Component
 *
 * Continuous-scroll PDF viewer using pdf.js. Renders all pages vertically
 * with scroll-based lazy rendering for performance.
 * Supports zoom controls, page input (scroll-to-page), and bbox overlays.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #1, #5)
 * Story 11.6: Implement PDF Viewer Full Modal Mode (AC: #2 - Fit to Page)
 */

import {
  useEffect,
  useRef,
  useState,
  useCallback,
  type FC,
} from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize,
  Minimize2,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { BboxOverlay } from './BboxOverlay';
import type { SplitViewBoundingBox, VerificationStatus } from '@/types/citation';
import type { HighlightType } from '@/types/pdf';

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
  /** Page number the bounding boxes belong to (for filtering) */
  bboxPageNumber?: number;
  highlightType?: HighlightType;
  verificationStatus?: VerificationStatus;
  isSource?: boolean;
  /** Current page (controlled) */
  currentPage?: number;
  /** Current scale (controlled) */
  scale?: number;
  onPageChange?: (page: number) => void;
  onScaleChange?: (scale: number) => void;
  onTotalPagesChange?: (totalPages: number) => void;
  panelTitle?: string;
  className?: string;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 3.0;
const SCALE_STEP = 0.25;
const DEFAULT_SCALE = 1.0;
const PAGE_GAP = 8;

/**
 * PDF viewer panel with continuous scroll, zoom controls, and bbox highlighting.
 */
export const PdfViewerPanel: FC<PdfViewerPanelProps> = ({
  documentUrl,
  initialPage = 1,
  boundingBoxes = [],
  bboxPageNumber,
  highlightType,
  verificationStatus = 'pending',
  isSource = false,
  currentPage: controlledPage,
  scale: controlledScale,
  onPageChange,
  onScaleChange,
  onTotalPagesChange,
  panelTitle,
  className,
}) => {
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [internalPage, setInternalPage] = useState(initialPage);
  const [internalScale, setInternalScale] = useState(DEFAULT_SCALE);
  const [pageInput, setPageInput] = useState(String(initialPage));
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState({ width: 612, height: 792 });
  // Force re-render trigger when pages finish rendering (for hiding spinners)
  const [renderVersion, setRenderVersion] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const scrollCleanupRef = useRef<(() => void) | null>(null);
  const pageRefsMap = useRef<Map<number, HTMLDivElement>>(new Map());
  const canvasRefsMap = useRef<Map<number, HTMLCanvasElement>>(new Map());
  const isScrollingToPage = useRef(false);
  const renderedPagesRef = useRef<Set<number>>(new Set());
  const renderingPagesRef = useRef<Set<number>>(new Set());

  const page = controlledPage ?? internalPage;
  const scale = controlledScale ?? internalScale;

  // --- "Function ref" pattern: store the latest render functions in refs ---
  // This ensures scroll handlers always call the latest version with fresh closures,
  // avoiding the stale closure problem that plagues useCallback-based approaches.
  const renderVisiblePagesRef = useRef<() => void>(() => {});

  // renderPage: renders a single page to its canvas
  const renderPageFn = async (pageNum: number) => {
    if (!pdfDoc) return;
    if (renderedPagesRef.current.has(pageNum)) return;
    if (renderingPagesRef.current.has(pageNum)) return;

    const canvas = canvasRefsMap.current.get(pageNum);
    if (!canvas) return;

    renderingPagesRef.current.add(pageNum);

    try {
      const pageObj = await pdfDoc.getPage(pageNum);
      const viewport = pageObj.getViewport({ scale });
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      canvas.width = viewport.width * dpr;
      canvas.height = viewport.height * dpr;
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      ctx.scale(dpr, dpr);

      await pageObj.render({ canvasContext: ctx, viewport }).promise;

      renderedPagesRef.current.add(pageNum);
      renderingPagesRef.current.delete(pageNum);
      setRenderVersion((v) => v + 1);
    } catch (err) {
      renderingPagesRef.current.delete(pageNum);
      if (err instanceof Error && err.message.includes('cancelled')) return;
      console.warn(`Failed to render page ${pageNum}:`, err);
    }
  };

  // renderVisiblePages: finds visible pages via getBoundingClientRect and renders them.
  // Uses BCR (not offsetTop) for reliable coordinates inside CSS-transformed dialogs.
  const renderVisiblePagesFn = () => {
    const container = containerRef.current;
    if (!container || !pdfDoc || numPages === 0) return;

    const containerRect = container.getBoundingClientRect();
    const viewHeight = container.clientHeight;
    const buffer = viewHeight; // render 1 viewport ahead/behind

    pageRefsMap.current.forEach((el, pageNum) => {
      const elRect = el.getBoundingClientRect();
      const relativeTop = elRect.top - containerRect.top;

      if (relativeTop < viewHeight + buffer && relativeTop + el.offsetHeight > -buffer) {
        renderPageFn(pageNum);
      }
    });
  };

  // Update the ref on every render so scroll handler always gets latest closure
  renderVisiblePagesRef.current = renderVisiblePagesFn;

  const handlePageChange = useCallback(
    (newPage: number) => {
      const clampedPage = Math.max(1, Math.min(newPage, numPages || 1));
      if (onPageChange) {
        onPageChange(clampedPage);
      } else {
        setInternalPage(clampedPage);
      }
      setPageInput(String(clampedPage));

      const pageEl = pageRefsMap.current.get(clampedPage);
      if (pageEl) {
        isScrollingToPage.current = true;
        pageEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setTimeout(() => { isScrollingToPage.current = false; }, 800);
      }
    },
    [numPages, onPageChange]
  );

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

  const handleFitToWidth = useCallback(() => {
    if (!containerRef.current || pageSize.width === 0) return;
    const availableWidth = containerRef.current.clientWidth - 32;
    const fitScale = availableWidth / pageSize.width;
    handleScaleChange(Math.max(MIN_SCALE, Math.min(fitScale, MAX_SCALE)));
  }, [pageSize.width, handleScaleChange]);

  const handleFitToPage = useCallback(() => {
    if (!containerRef.current || pageSize.width === 0 || pageSize.height === 0) return;
    const availableWidth = containerRef.current.clientWidth - 32;
    const availableHeight = containerRef.current.clientHeight - 32;
    const fitScale = Math.min(availableWidth / pageSize.width, availableHeight / pageSize.height);
    handleScaleChange(Math.max(MIN_SCALE, Math.min(fitScale, MAX_SCALE)));
  }, [pageSize.width, pageSize.height, handleScaleChange]);

  // Load PDF document
  useEffect(() => {
    let cancelled = false;

    const loadPdf = async () => {
      setIsLoading(true);
      setError(null);
      renderedPagesRef.current = new Set();
      renderingPagesRef.current = new Set();

      try {
        const pdfjs = await import('pdfjs-dist');

        if (!pdfjs.GlobalWorkerOptions.workerSrc) {
          pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
        }

        const loadingTask = pdfjs.getDocument(documentUrl);
        const doc = await loadingTask.promise;

        if (cancelled) return;

        setPdfDoc(doc as unknown as PDFDocumentProxy);
        setNumPages(doc.numPages);
        onTotalPagesChange?.(doc.numPages);

        const firstPage = await doc.getPage(1);
        const vp = firstPage.getViewport({ scale: 1.0 });
        setPageSize({ width: vp.width, height: vp.height });

        setIsLoading(false);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load PDF');
        setIsLoading(false);
      }
    };

    loadPdf();
    return () => { cancelled = true; };
  }, [documentUrl, onTotalPagesChange]);

  // Initial render: when PDF loads, render visible pages after DOM settles
  useEffect(() => {
    if (!pdfDoc || numPages === 0) return;
    const timer = setTimeout(() => renderVisiblePagesRef.current(), 150);
    return () => clearTimeout(timer);
  }, [pdfDoc, numPages]);

  // When scale changes, clear rendered state and re-render
  useEffect(() => {
    if (!pdfDoc || numPages === 0) return;
    renderedPagesRef.current = new Set();
    renderingPagesRef.current = new Set();
    setRenderVersion((v) => v + 1);
    const timer = setTimeout(() => renderVisiblePagesRef.current(), 150);
    return () => clearTimeout(timer);
  }, [pdfDoc, numPages, scale]);

  // Page tracking callback ref (avoids stale onPageChange in scroll handler)
  const onPageChangeRef = useRef(onPageChange);
  onPageChangeRef.current = onPageChange;

  // Callback ref for the scroll container. Registers the scroll handler
  // the moment the DOM node appears, bypassing useEffect timing issues
  // (containerRef was null in effects due to early-return loading state).
  const containerCallbackRef = useCallback((node: HTMLDivElement | null) => {
    // Cleanup previous handler
    if (scrollCleanupRef.current) {
      scrollCleanupRef.current();
      scrollCleanupRef.current = null;
    }

    containerRef.current = node;

    if (node) {
      const handleScroll = () => {
        renderVisiblePagesRef.current();

        if (isScrollingToPage.current) return;

        const containerRect = node.getBoundingClientRect();
        const containerTop = containerRect.top;
        let closestPage = 1;
        let closestDist = Infinity;

        pageRefsMap.current.forEach((el, pageNum) => {
          const rect = el.getBoundingClientRect();
          const dist = Math.abs(rect.top - containerTop);
          if (dist < closestDist) {
            closestDist = dist;
            closestPage = pageNum;
          }
        });

        if (onPageChangeRef.current) {
          onPageChangeRef.current(closestPage);
        } else {
          setInternalPage(closestPage);
        }
        setPageInput(String(closestPage));
      };

      node.addEventListener('scroll', handleScroll, { passive: true });
      scrollCleanupRef.current = () => node.removeEventListener('scroll', handleScroll);
    }
  }, []);

  // Scroll to initial page on first load
  useEffect(() => {
    if (!pdfDoc || numPages === 0 || initialPage <= 1) return;

    const timer = setTimeout(() => {
      const pageEl = pageRefsMap.current.get(initialPage);
      if (pageEl) {
        isScrollingToPage.current = true;
        pageEl.scrollIntoView({ behavior: 'instant', block: 'start' });
        setTimeout(() => { isScrollingToPage.current = false; }, 300);
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [pdfDoc, numPages, initialPage]);

  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

  const handlePageInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newPage = parseInt(pageInput, 10);
    if (!isNaN(newPage)) {
      handlePageChange(newPage);
    } else {
      setPageInput(String(page));
    }
  };

  const setPageRef = useCallback((pageNum: number, el: HTMLDivElement | null) => {
    if (el) {
      pageRefsMap.current.set(pageNum, el);
    } else {
      pageRefsMap.current.delete(pageNum);
    }
  }, []);

  const setCanvasRef = useCallback((pageNum: number, el: HTMLCanvasElement | null) => {
    if (el) {
      canvasRefsMap.current.set(pageNum, el);
    } else {
      canvasRefsMap.current.delete(pageNum);
    }
  }, []);

  if (isLoading) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-muted/30 ${className ?? ''}`}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-2 text-sm text-muted-foreground">Loading document...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-muted/30 ${className ?? ''}`}>
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="mt-2 text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  const scaledWidth = pageSize.width * scale;
  const scaledHeight = pageSize.height * scale;

  // Suppress unused var warning - renderVersion is used to trigger re-renders
  void renderVersion;

  return (
    <div className={`flex flex-col h-full ${className ?? ''}`}>
      {/* Controls bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b bg-background">
        <div className="flex items-center gap-1">
          <form onSubmit={handlePageInputSubmit} className="flex items-center gap-1">
            <Input
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              className="h-8 w-14 text-center text-sm"
              aria-label="Page number"
              title="Enter page number and press Enter to scroll"
            />
            <span className="text-sm text-muted-foreground">/ {numPages}</span>
          </form>
        </div>

        {panelTitle && (
          <span className="text-xs font-medium text-muted-foreground truncate max-w-[40%]">
            {panelTitle}
          </span>
        )}

        <div className="flex items-center gap-1">
          <Button
            variant="ghost" size="icon" className="h-8 w-8"
            onClick={() => handleScaleChange(scale - SCALE_STEP)}
            disabled={scale <= MIN_SCALE} title="Zoom out (-)"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground min-w-[50px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <Button
            variant="ghost" size="icon" className="h-8 w-8"
            onClick={() => handleScaleChange(scale + SCALE_STEP)}
            disabled={scale >= MAX_SCALE} title="Zoom in (+)"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost" size="icon" className="h-8 w-8"
            onClick={handleFitToWidth} title="Fit to width"
            aria-label="Fit page width to view"
          >
            <Maximize className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost" size="icon" className="h-8 w-8"
            onClick={handleFitToPage} title="Fit to page"
            aria-label="Fit entire page in view"
          >
            <Minimize2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Continuous scroll PDF container */}
      <div ref={containerCallbackRef} className="flex-1 overflow-auto bg-muted/30 p-4">
        <div className="flex flex-col items-center" style={{ gap: `${PAGE_GAP}px` }}>
          {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
            <div
              key={pageNum}
              ref={(el) => setPageRef(pageNum, el)}
              data-page={pageNum}
              className="relative shadow-lg bg-white"
              style={{ width: `${scaledWidth}px`, height: `${scaledHeight}px` }}
            >
              <canvas
                ref={(el) => setCanvasRef(pageNum, el)}
                aria-label={`${panelTitle ?? 'PDF'} page ${pageNum}`}
              />

              {bboxPageNumber === pageNum && boundingBoxes.length > 0 && (
                <BboxOverlay
                  boundingBoxes={boundingBoxes}
                  pageWidth={pageSize.width}
                  pageHeight={pageSize.height}
                  scale={scale}
                  highlightType={highlightType}
                  verificationStatus={verificationStatus}
                  isSource={isSource}
                />
              )}

              {!renderedPagesRef.current.has(pageNum) && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
