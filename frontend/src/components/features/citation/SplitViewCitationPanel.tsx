'use client';

/**
 * Split View Citation Panel Component
 *
 * Main container for side-by-side citation viewing with resizable panels.
 * Shows case document (left) and Act document (right) with highlights.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #1, #4, #5)
 */

import { type FC, useCallback, useEffect } from 'react';
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
} from 'react-resizable-panels';
import { FileText, Book, GripVertical, Loader2 } from 'lucide-react';
import { SplitViewHeader } from './SplitViewHeader';
import { PdfViewerPanel } from '../pdf/PdfViewerPanel';
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
}) => {
  // Store actions for viewer state
  const setSourcePage = useSplitViewStore((state) => state.setSourcePage);
  const setTargetPage = useSplitViewStore((state) => state.setTargetPage);
  const setSourceZoom = useSplitViewStore((state) => state.setSourceZoom);
  const setTargetZoom = useSplitViewStore((state) => state.setTargetZoom);
  const sourceViewState = useSplitViewStore((state) => state.sourceViewState);
  const targetViewState = useSplitViewStore((state) => state.targetViewState);

  const { citation, sourceDocument, targetDocument, verification } = data;
  const hasTargetDocument = targetDocument !== null;

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

  // Show error state
  if (error) {
    return (
      <div className={`${containerClasses} flex items-center justify-center`}>
        <div className="flex flex-col items-center gap-2 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={onClose}
            className="text-sm text-primary hover:underline"
          >
            Close
          </button>
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
      />

      {/* Split panels */}
      <div className="flex-1 min-h-0">
        {hasTargetDocument ? (
          // Two-panel mode: source and target
          <PanelGroup direction="horizontal" className="h-full">
            {/* Source panel (case document) */}
            <Panel defaultSize={50} minSize={30}>
              <div className="h-full flex flex-col">
                <div className="flex items-center gap-2 px-3 py-2 border-b bg-yellow-50 dark:bg-yellow-950/30">
                  <FileText className="h-4 w-4 text-yellow-600" />
                  <span className="text-sm font-medium">Source Document</span>
                </div>
                <div className="flex-1 min-h-0">
                  <PdfViewerPanel
                    documentUrl={sourceDocument.documentUrl}
                    initialPage={sourceDocument.pageNumber}
                    boundingBoxes={sourceDocument.boundingBoxes}
                    verificationStatus={citation.verificationStatus}
                    isSource={true}
                    currentPage={sourceViewState.currentPage}
                    scale={sourceViewState.scale}
                    onPageChange={handleSourcePageChange}
                    onScaleChange={handleSourceZoomChange}
                    panelTitle="Case Document"
                    className="h-full"
                  />
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
                  <PdfViewerPanel
                    documentUrl={targetDocument.documentUrl}
                    initialPage={targetDocument.pageNumber}
                    boundingBoxes={targetDocument.boundingBoxes}
                    verificationStatus={citation.verificationStatus}
                    isSource={false}
                    currentPage={targetViewState.currentPage}
                    scale={targetViewState.scale}
                    onPageChange={handleTargetPageChange}
                    onScaleChange={handleTargetZoomChange}
                    panelTitle="Act Document"
                    className="h-full"
                  />
                </div>
              </div>
            </Panel>
          </PanelGroup>
        ) : (
          // Single-panel mode: only source (AC: #4)
          <div className="h-full flex flex-col">
            <div className="flex items-center gap-2 px-3 py-2 border-b bg-yellow-50 dark:bg-yellow-950/30">
              <FileText className="h-4 w-4 text-yellow-600" />
              <span className="text-sm font-medium">Source Document</span>
              <span className="text-xs text-muted-foreground ml-auto">
                Act not uploaded - verification unavailable
              </span>
            </div>
            <div className="flex-1 min-h-0">
              <PdfViewerPanel
                documentUrl={sourceDocument.documentUrl}
                initialPage={sourceDocument.pageNumber}
                boundingBoxes={sourceDocument.boundingBoxes}
                verificationStatus="act_unavailable"
                isSource={true}
                currentPage={sourceViewState.currentPage}
                scale={sourceViewState.scale}
                onPageChange={handleSourcePageChange}
                onScaleChange={handleSourceZoomChange}
                panelTitle="Case Document"
                className="h-full"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
