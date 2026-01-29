'use client';

import { useState, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Download,
  Maximize2,
  Minimize2,
  FileText,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Props for the PDF Viewer Modal
 */
interface PdfViewerModalProps {
  /** Whether the modal is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Document ID for fetching the PDF */
  documentId?: string;
  /** Document name for display */
  documentName?: string;
  /** Initial page to display (1-indexed) */
  initialPage?: number;
  /** Bounding boxes to highlight (future feature) */
  highlightBboxIds?: string[];
  /** Matter ID for access control */
  matterId?: string;
  /** Callback when download is clicked */
  onDownload?: () => void;
}

/**
 * Zoom level options
 */
const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200] as const;
type ZoomLevel = (typeof ZOOM_LEVELS)[number];

/**
 * PDF Viewer Modal Component
 *
 * A full-featured modal for viewing PDFs with:
 * - Page navigation (prev/next, jump to page)
 * - Zoom controls
 * - Rotation
 * - Full-screen toggle
 * - Bounding box highlighting (future)
 *
 * Story 2.3: PDF Modal with Source Navigation
 *
 * This is a shell component - actual PDF rendering will be
 * implemented when Supabase is unblocked.
 */
export function PdfViewerModal({
  open,
  onOpenChange,
  documentId,
  documentName = 'Document',
  initialPage = 1,
  highlightBboxIds,
  matterId,
  onDownload,
}: PdfViewerModalProps) {
  // Page navigation state
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [totalPages, setTotalPages] = useState(0); // Will be set when PDF loads
  const [pageInputValue, setPageInputValue] = useState(String(initialPage));

  // Zoom and rotation state
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>(100);
  const [rotation, setRotation] = useState(0);

  // Fullscreen state
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Loading and error state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Page navigation handlers
  const goToPreviousPage = useCallback(() => {
    if (currentPage > 1) {
      const newPage = currentPage - 1;
      setCurrentPage(newPage);
      setPageInputValue(String(newPage));
    }
  }, [currentPage]);

  const goToNextPage = useCallback(() => {
    if (currentPage < totalPages) {
      const newPage = currentPage + 1;
      setCurrentPage(newPage);
      setPageInputValue(String(newPage));
    }
  }, [currentPage, totalPages]);

  const handlePageInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setPageInputValue(value);
    },
    []
  );

  const handlePageInputBlur = useCallback(() => {
    const pageNum = parseInt(pageInputValue, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      setCurrentPage(pageNum);
    } else {
      setPageInputValue(String(currentPage));
    }
  }, [pageInputValue, totalPages, currentPage]);

  const handlePageInputKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        handlePageInputBlur();
      }
    },
    [handlePageInputBlur]
  );

  // Zoom handlers
  const zoomIn = useCallback(() => {
    const currentIndex = ZOOM_LEVELS.indexOf(zoomLevel);
    if (currentIndex < ZOOM_LEVELS.length - 1) {
      setZoomLevel(ZOOM_LEVELS[currentIndex + 1] as ZoomLevel);
    }
  }, [zoomLevel]);

  const zoomOut = useCallback(() => {
    const currentIndex = ZOOM_LEVELS.indexOf(zoomLevel);
    if (currentIndex > 0) {
      setZoomLevel(ZOOM_LEVELS[currentIndex - 1] as ZoomLevel);
    }
  }, [zoomLevel]);

  // Rotation handler
  const rotate = useCallback(() => {
    setRotation((prev) => (prev + 90) % 360);
  }, []);

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
  }, []);

  // Simulate loading completion (remove when actual PDF loading is implemented)
  // For demo purposes, we'll show a skeleton for 1.5s then show placeholder
  const [showPlaceholder, setShowPlaceholder] = useState(false);

  // Simulate document info
  const simulatedTotalPages = 42;
  if (totalPages === 0 && open) {
    setTimeout(() => {
      setTotalPages(simulatedTotalPages);
      setIsLoading(false);
      setShowPlaceholder(true);
    }, 1500);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'flex flex-col p-0 gap-0',
          isFullscreen
            ? 'w-screen h-screen max-w-none max-h-none rounded-none'
            : 'w-[95vw] h-[90vh] max-w-6xl'
        )}
        showCloseButton={false}
      >
        {/* Header */}
        <DialogHeader className="flex-shrink-0 border-b px-4 py-3">
          <div className="flex items-center justify-between">
            {/* Document title */}
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
              <DialogTitle className="truncate text-base">
                {documentName}
              </DialogTitle>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-1">
              {/* Page navigation */}
              <div className="flex items-center gap-1 mr-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={goToPreviousPage}
                  disabled={currentPage <= 1 || isLoading}
                  aria-label="Previous page"
                  className="h-8 w-8"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>

                <div className="flex items-center gap-1 text-sm">
                  <Input
                    type="text"
                    value={pageInputValue}
                    onChange={handlePageInputChange}
                    onBlur={handlePageInputBlur}
                    onKeyDown={handlePageInputKeyDown}
                    className="w-12 h-7 text-center px-1"
                    disabled={isLoading}
                    aria-label="Current page"
                  />
                  <span className="text-muted-foreground">
                    / {totalPages || '—'}
                  </span>
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={goToNextPage}
                  disabled={currentPage >= totalPages || isLoading}
                  aria-label="Next page"
                  className="h-8 w-8"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>

              {/* Divider */}
              <div className="w-px h-6 bg-border mx-1" />

              {/* Zoom controls */}
              <Button
                variant="ghost"
                size="icon"
                onClick={zoomOut}
                disabled={zoomLevel === ZOOM_LEVELS[0] || isLoading}
                aria-label="Zoom out"
                className="h-8 w-8"
              >
                <ZoomOut className="h-4 w-4" />
              </Button>

              <span className="text-sm text-muted-foreground w-12 text-center">
                {zoomLevel}%
              </span>

              <Button
                variant="ghost"
                size="icon"
                onClick={zoomIn}
                disabled={
                  zoomLevel === ZOOM_LEVELS[ZOOM_LEVELS.length - 1] || isLoading
                }
                aria-label="Zoom in"
                className="h-8 w-8"
              >
                <ZoomIn className="h-4 w-4" />
              </Button>

              {/* Divider */}
              <div className="w-px h-6 bg-border mx-1" />

              {/* Rotation */}
              <Button
                variant="ghost"
                size="icon"
                onClick={rotate}
                disabled={isLoading}
                aria-label="Rotate clockwise"
                className="h-8 w-8"
              >
                <RotateCw className="h-4 w-4" />
              </Button>

              {/* Download */}
              {onDownload && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onDownload}
                  disabled={isLoading}
                  aria-label="Download PDF"
                  className="h-8 w-8"
                >
                  <Download className="h-4 w-4" />
                </Button>
              )}

              {/* Fullscreen toggle */}
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleFullscreen}
                aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
                className="h-8 w-8"
              >
                {isFullscreen ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
              </Button>

              {/* Close button */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onOpenChange(false)}
                aria-label="Close"
                className="h-8 w-8 ml-2"
              >
                <span className="text-lg">&times;</span>
              </Button>
            </div>
          </div>
        </DialogHeader>

        {/* PDF viewer area */}
        <div className="flex-1 overflow-auto bg-muted/30 flex items-center justify-center p-4">
          {isLoading ? (
            // Loading skeleton
            <div className="flex flex-col items-center gap-4">
              <Skeleton className="w-[600px] h-[800px] max-w-full" />
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                Loading document...
              </div>
            </div>
          ) : error ? (
            // Error state
            <div className="flex flex-col items-center gap-4 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <div>
                <p className="font-medium text-destructive">
                  Failed to load document
                </p>
                <p className="text-sm text-muted-foreground mt-1">{error}</p>
              </div>
              <Button variant="outline" onClick={() => setError(null)}>
                Retry
              </Button>
            </div>
          ) : showPlaceholder ? (
            // Placeholder for PDF canvas (replace with actual PDF.js canvas later)
            <div
              className="bg-white shadow-lg flex items-center justify-center"
              style={{
                width: `${(600 * zoomLevel) / 100}px`,
                height: `${(800 * zoomLevel) / 100}px`,
                transform: `rotate(${rotation}deg)`,
                transition: 'transform 0.2s ease-out',
              }}
            >
              <div className="text-center p-8">
                <FileText className="h-16 w-16 mx-auto text-muted-foreground/50 mb-4" />
                <p className="text-lg font-medium text-muted-foreground">
                  {documentName}
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  Page {currentPage} of {totalPages}
                </p>
                <p className="text-xs text-muted-foreground/70 mt-4">
                  PDF rendering will be enabled when connected to backend
                </p>
                {highlightBboxIds && highlightBboxIds.length > 0 && (
                  <p className="text-xs text-blue-600 mt-2">
                    {highlightBboxIds.length} regions to highlight
                  </p>
                )}
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer with highlight info */}
        {highlightBboxIds && highlightBboxIds.length > 0 && (
          <div className="flex-shrink-0 border-t px-4 py-2 bg-blue-50 dark:bg-blue-950/30">
            <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
              <div className="h-3 w-3 rounded-sm bg-yellow-300/80 border border-yellow-400" />
              <span>
                {highlightBboxIds.length} text region
                {highlightBboxIds.length !== 1 ? 's' : ''} highlighted from
                source reference
              </span>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/**
 * PDF Viewer Modal Skeleton
 * For loading states when the modal data is being fetched
 */
export function PdfViewerModalSkeleton() {
  return (
    <div className="flex flex-col h-[90vh] w-[95vw] max-w-6xl bg-background rounded-lg border shadow-lg">
      {/* Header skeleton */}
      <div className="flex-shrink-0 border-b px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-5" />
            <Skeleton className="h-5 w-48" />
          </div>
          <div className="flex items-center gap-1">
            <Skeleton className="h-8 w-8" />
            <Skeleton className="h-8 w-8" />
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-8 w-8" />
            <Skeleton className="h-8 w-8" />
          </div>
        </div>
      </div>

      {/* Content skeleton */}
      <div className="flex-1 flex items-center justify-center bg-muted/30">
        <Skeleton className="w-[600px] h-[800px]" />
      </div>
    </div>
  );
}
