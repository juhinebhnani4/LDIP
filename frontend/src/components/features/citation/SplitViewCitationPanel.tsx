'use client';

/**
 * Split View Citation Panel Component
 *
 * Main container for side-by-side citation viewing with resizable panels.
 * Shows case document (left) and Act document (right) with highlights.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #1, #4, #5)
 */

import { type FC, useCallback } from 'react';
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
} from 'react-resizable-panels';
import { FileText, Book, GripVertical, Loader2 } from 'lucide-react';
import { SplitViewHeader } from './SplitViewHeader';
import { MismatchExplanation } from './MismatchExplanation';
import { PdfViewerPanel, PdfErrorBoundary } from '../pdf';
import { useSplitViewStore } from '@/stores/splitViewStore';
import type { SplitViewData } from '@/types/citation';

export interface SplitViewCitationPanelProps {
  /** Split view data */
  data: SplitViewData;
  /** Whether in full screen mode */
  isFullScreen: boolean;
  /** Navigation info for prev/next */
  navigationInfo: {
    currentIndex: number;
    totalCount: number;
    canPrev: boolean;
    canNext: boolean;
  };
  /** Loading state */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
  /** Close handler */
  onClose: () => void;
  /** Toggle full screen handler */
  onToggleFullScreen: () => void;
  /** Previous citation handler */
  onPrev: () => void;
  /** Next citation handler */
  onNext: () => void;
  /** Mark verified handler */
  onMarkVerified?: () => Promise<void>;
  /** Whether mark verified action is in progress */
  isMarkingVerified?: boolean;
  /** Retry handler when error occurs */
  onRetry?: () => void;
}

/**
 * Split view panel showing case document and Act document side by side.
 */
export const SplitViewCitationPanel: FC<SplitViewCitationPanelProps> = ({
  data,
  isFullScreen,
  navigationInfo,
  isLoading = false,
  error = null,
  onClose,
  onToggleFullScreen,
  onPrev,
  onNext,
  onMarkVerified,
  isMarkingVerified = false,
  onRetry,
}) => {
  // Store actions for viewer state
  const setSourcePage = useSplitViewStore((state) => state.setSourcePage);
  const setTargetPage = useSplitViewStore((state) => state.setTargetPage);
  const setSourceZoom = useSplitViewStore((state) => state.setSourceZoom);
  const setTargetZoom = useSplitViewStore((state) => state.setTargetZoom);
  const sourceViewState = useSplitViewStore((state) => state.sourceViewState);
  const targetViewState = useSplitViewStore((state) => state.targetViewState);

  const { citation, sourceDocument, targetDocument, verification, citationContext } = data;
  const hasTargetDocument = targetDocument !== null;

  // Always label source as "Source Document" for clarity in citation comparison
  // The source is where the citation was found (citing document)
  // The target is the Act being cited (cited document)
  const sourceLabel = 'Source Document';
  const sourcePanelTitle = 'Source Document';

  // Handle source page change
  const handleSourcePageChange = useCallback(
    (page: number) => setSourcePage(page),
    [setSourcePage]
  );

  // Handle target page change
  const handleTargetPageChange = useCallback(
    (page: number) => setTargetPage(page),
    [setTargetPage]
  );

  // Handle source zoom change
  const handleSourceZoomChange = useCallback(
    (scale: number) => setSourceZoom(scale),
    [setSourceZoom]
  );

  // Handle target zoom change
  const handleTargetZoomChange = useCallback(
    (scale: number) => setTargetZoom(scale),
    [setTargetZoom]
  );

  // Container classes based on full screen mode
  const containerClasses = isFullScreen
    ? 'fixed inset-0 z-50 bg-background'
    : 'h-full border-l bg-background';

  // Show loading state
  if (isLoading) {
    return (
      <div className={`${containerClasses} flex items-center justify-center`}>
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading citation view...</p>
        </div>
      </div>
    );
  }

  // Show error state with retry option
  if (error) {
    return (
      <div className={`${containerClasses} flex items-center justify-center`}>
        <div className="flex flex-col items-center gap-4 text-center max-w-md p-6">
          <div className="rounded-full bg-destructive/10 p-3">
            <svg
              className="h-6 w-6 text-destructive"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div>
            <p className="font-medium text-destructive mb-1">Failed to load citation</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
          <div className="flex items-center gap-3">
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary/90 transition-colors"
              >
                Try Again
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground border rounded-md transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${containerClasses} flex flex-col`}>
      {/* Header */}
      <SplitViewHeader
        citation={citation}
        verification={verification}
        isFullScreen={isFullScreen}
        navigationInfo={navigationInfo}
        onClose={onClose}
        onToggleFullScreen={onToggleFullScreen}
        onPrev={onPrev}
        onNext={onNext}
        onMarkVerified={onMarkVerified}
        isMarkingVerified={isMarkingVerified}
      />

      {/* Citation context panel - helps users understand what to compare */}
      {citationContext && (
        <div className="px-4 py-3 border-b bg-amber-50 dark:bg-amber-950/20">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">
              <svg className="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                {citationContext.instruction}
              </p>
              {citationContext.citationText && (
                <div className="mt-2 p-2 bg-white dark:bg-gray-800 rounded border border-amber-200 dark:border-amber-800">
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Citation text from source:</p>
                  <p className="text-sm text-gray-900 dark:text-gray-100 italic">
                    &ldquo;{citationContext.citationText}&rdquo;
                  </p>
                </div>
              )}
              {!citationContext.sectionFoundInAct && hasTargetDocument && (
                <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                  💡 Tip: Use Ctrl+F in your browser to search for &ldquo;{citationContext.section}&rdquo; in the Act document
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Mismatch explanation panel (AC: #3) */}
      {verification && verification.status === 'mismatch' && verification.diffDetails && (
        <MismatchExplanation verification={verification} />
      )}

      {/* Split panels */}
      <div className="flex-1 min-h-0">
        {hasTargetDocument ? (
          // Two-panel mode: source and target
          <PanelGroup direction="horizontal" className="h-full">
            {/* Source panel (document where citation was found) */}
            <Panel defaultSize={50} minSize={30}>
              <div className="h-full flex flex-col">
                <div className="flex items-center gap-2 px-3 py-2 border-b bg-yellow-50 dark:bg-yellow-950/30">
                  <FileText className="h-4 w-4 text-yellow-600" />
                  <span className="text-sm font-medium">{sourceLabel}</span>
                </div>
                <div className="flex-1 min-h-0">
                  <PdfErrorBoundary fallbackMessage="Failed to load the source document.">
                    <PdfViewerPanel
                      documentUrl={sourceDocument.documentUrl}
                      initialPage={sourceDocument.pageNumber}
                      boundingBoxes={sourceDocument.boundingBoxes}
                      bboxPageNumber={sourceDocument.pageNumber}
                      verificationStatus={citation.verificationStatus}
                      isSource={true}
                      currentPage={sourceViewState.currentPage}
                      scale={sourceViewState.scale}
                      onPageChange={handleSourcePageChange}
                      onScaleChange={handleSourceZoomChange}
                      panelTitle={sourcePanelTitle}
                      className="h-full"
                    />
                  </PdfErrorBoundary>
                </div>
              </div>
            </Panel>

            {/* Resize handle */}
            <PanelResizeHandle className="w-2 bg-border hover:bg-primary/20 transition-colors flex items-center justify-center group">
              <GripVertical className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </PanelResizeHandle>

            {/* Target panel (Act document) */}
            <Panel defaultSize={50} minSize={30}>
              <div className="h-full flex flex-col">
                <div className="flex items-center gap-2 px-3 py-2 border-b bg-blue-50 dark:bg-blue-950/30">
                  <Book className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-medium">Act Document</span>
                  {verification?.status === 'mismatch' && (
                    <span className="text-xs text-destructive">(Mismatch)</span>
                  )}
                </div>
                <div className="flex-1 min-h-0">
                  <PdfErrorBoundary fallbackMessage="Failed to load the Act document.">
                    <PdfViewerPanel
                      documentUrl={targetDocument.documentUrl}
                      initialPage={targetDocument.pageNumber}
                      boundingBoxes={targetDocument.boundingBoxes}
                      bboxPageNumber={targetDocument.pageNumber}
                      verificationStatus={citation.verificationStatus}
                      isSource={false}
                      currentPage={targetViewState.currentPage}
                      scale={targetViewState.scale}
                      onPageChange={handleTargetPageChange}
                      onScaleChange={handleTargetZoomChange}
                      panelTitle="Act Document"
                      className="h-full"
                    />
                  </PdfErrorBoundary>
                </div>
              </div>
            </Panel>
          </PanelGroup>
        ) : (
          // Single-panel mode: only source (AC: #4)
          <div className="h-full flex flex-col">
            <div className="flex items-center gap-2 px-3 py-2 border-b bg-yellow-50 dark:bg-yellow-950/30">
              <FileText className="h-4 w-4 text-yellow-600" />
              <span className="text-sm font-medium">{sourceLabel}</span>
              <span className="text-xs text-muted-foreground ml-auto">
                Target Act not uploaded - verification unavailable
              </span>
            </div>
            <div className="flex-1 min-h-0">
              <PdfErrorBoundary fallbackMessage="Failed to load the document.">
                <PdfViewerPanel
                  documentUrl={sourceDocument.documentUrl}
                  initialPage={sourceDocument.pageNumber}
                  boundingBoxes={sourceDocument.boundingBoxes}
                  bboxPageNumber={sourceDocument.pageNumber}
                  verificationStatus="act_unavailable"
                  isSource={true}
                  currentPage={sourceViewState.currentPage}
                  scale={sourceViewState.scale}
                  onPageChange={handleSourcePageChange}
                  onScaleChange={handleSourceZoomChange}
                  panelTitle={sourcePanelTitle}
                  className="h-full"
                />
              </PdfErrorBoundary>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
