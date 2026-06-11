'use client';

import { useCallback, useState, type ReactNode } from 'react';
import dynamic from 'next/dynamic';
import { toast } from 'sonner';
import { MessageSquare } from 'lucide-react';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { useQAPanelStore } from '@/stores/qaPanelStore';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';
import { useUser, useBoundingBoxes, useIsBelowBreakpoint } from '@/hooks';
import { QAPanel } from '@/components/features/chat/QAPanel';
import { FloatingQAPanel } from '@/components/features/chat/FloatingQAPanel';
import { QAPanelExpandButton } from '@/components/features/chat/QAPanelExpandButton';
import { fetchDocument } from '@/lib/api/documents';
import type { SourceReference } from '@/types/chat';

const PDFSplitView = dynamic(
  () => import('@/components/features/pdf/PDFSplitView').then((m) => ({ default: m.PDFSplitView })),
  { ssr: false },
);

/**
 * Workspace Content Area
 *
 * Handles the main content layout with Q&A panel integration.
 * Supports four panel positions: right sidebar, bottom panel, floating, and hidden.
 *
 * Layout patterns:
 * - Right: [Tab Content | Q&A Panel] - horizontal split
 * - Bottom: [Tab Content / Q&A Panel] - vertical split
 * - Float: [Tab Content] + floating overlay
 * - Hidden: [Tab Content] + expand button
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 * Story 11.2: Implement Q&A Conversation History
 * Story 11.5: PDF Split View for source references
 */
interface WorkspaceContentAreaProps {
  /** Tab content to render in main area */
  children: ReactNode;
  /** Matter ID for the current workspace */
  matterId: string;
}

export function WorkspaceContentArea({
  children,
  matterId,
}: WorkspaceContentAreaProps) {
  const position = useQAPanelStore((state) => state.position);
  // FE-ARCH-02: below the tablet breakpoint the side-by-side split is unusable,
  // so we structurally collapse the Q&A panel into a bottom sheet. This is a
  // VIEW-TIME override derived from viewport width — we deliberately do NOT
  // write to qaPanelStore (the stored position is the user's desktop preference;
  // mutating it from viewport would clobber it and create a "remember to restore
  // on resize" rule). The desktop branches below are untouched.
  const isBelowTablet = useIsBelowBreakpoint('lg');
  const [mobileQaOpen, setMobileQaOpen] = useState(false);
  const rightWidth = useQAPanelStore((state) => state.rightWidth);
  const bottomHeight = useQAPanelStore((state) => state.bottomHeight);
  const setRightWidth = useQAPanelStore((state) => state.setRightWidth);
  const setBottomHeight = useQAPanelStore((state) => state.setBottomHeight);
  const { user } = useUser();
  const userId = user?.id;

  // PDF split view actions
  const openPdfSplitView = usePdfSplitViewStore(
    (state) => state.openPdfSplitView
  );
  const setBoundingBoxes = usePdfSplitViewStore(
    (state) => state.setBoundingBoxes
  );

  // Bounding box hook for fetching bbox data (Story 11.7)
  const { fetchByChunkId, fetchByBboxIds } = useBoundingBoxes();

  /**
   * Handle source reference clicks from Q&A panel.
   * Fetches document signed URL and opens PDF split view.
   * Story 11.5: PDF Split View for source references (AC: #4)
   * Story 11.7: Fetch bounding boxes for source text highlighting (AC: #1)
   */
  const handleSourceClick = useCallback(
    async (source: SourceReference) => {
      // Track the document being opened to prevent race conditions
      const targetDocumentId = source.documentId;

      try {
        // Fetch document details to get signed URL
        const document = await fetchDocument(source.documentId);
        const documentUrl = document.storagePath;

        if (!documentUrl) {
          throw new Error('Document URL not found');
        }

        // Open PDF split view with document
        openPdfSplitView(source, matterId, documentUrl);

        // Story 11.7: Fetch bounding boxes for source text highlighting
        // Priority: 1) Direct bboxIds from source, 2) Fetch by chunkId
        // Bounding box highlighting is optional - don't block or error if unavailable
        try {
          let bboxes: { x: number; y: number; width: number; height: number }[] = [];
          let fetchedPageNumber: number | null = null;

          // Try direct bboxIds first (from SSE response) - avoids extra API call
          if (source.bboxIds && source.bboxIds.length > 0) {
            const result = await fetchByBboxIds(source.bboxIds, matterId);
            bboxes = result.bboxes.map((bbox) => ({
              x: bbox.x,
              y: bbox.y,
              width: bbox.width,
              height: bbox.height,
            }));
            fetchedPageNumber = result.pageNumber;
          }
          // Fall back to fetching by chunkId if no direct bboxIds
          else if (source.chunkId) {
            const result = await fetchByChunkId(source.chunkId);
            bboxes = result.bboxes.map((bbox) => ({
              x: bbox.x,
              y: bbox.y,
              width: bbox.width,
              height: bbox.height,
            }));
            fetchedPageNumber = result.pageNumber;
          }

          // Verify we're still viewing the same document (race condition guard)
          const currentDocumentId = usePdfSplitViewStore.getState().documentId;
          if (currentDocumentId !== targetDocumentId) {
            // User navigated to different document, discard these bboxes
            return;
          }

          if (bboxes.length > 0) {
            // Use page number from API response, fall back to source.page only if unavailable
            const pageNumber = fetchedPageNumber ?? source.page ?? 1;
            setBoundingBoxes(bboxes, pageNumber);
          }
        } catch {
          // Bbox highlighting is optional - log but don't fail the operation
          console.warn('Failed to fetch bounding boxes for source highlight');
        }
      } catch {
        toast.error('Unable to open document. Please try again.');
      }
    },
    [matterId, openPdfSplitView, fetchByChunkId, fetchByBboxIds, setBoundingBoxes]
  );

  // FE-ARCH-02: Mobile / small-tablet layout (below md).
  // The horizontal/vertical split is unusable at narrow widths, so the main
  // content takes the full width and the Q&A panel collapses into a bottom
  // sheet opened by a single trigger. This branch structurally overrides the
  // stored desktop position; it does not depend on which of the four positions
  // the user last chose on desktop.
  if (isBelowTablet) {
    return (
      <PDFSplitView>
        <div className="relative h-full flex-1" data-testid="workspace-content-area">
          <div className="h-full overflow-y-auto overflow-x-hidden pb-24" data-testid="workspace-main-content">
            {children}
          </div>
          <Sheet open={mobileQaOpen} onOpenChange={setMobileQaOpen}>
            <SheetTrigger asChild>
              <Button
                size="sm"
                className="absolute bottom-4 left-1/2 z-40 -translate-x-1/2 gap-2 rounded-full shadow-lg"
                data-testid="mobile-qa-trigger"
              >
                <MessageSquare className="h-4 w-4" aria-hidden="true" />
                Ask jaanch
              </Button>
            </SheetTrigger>
            <SheetContent
              side="bottom"
              className="flex h-[85dvh] flex-col rounded-t-xl p-0"
              data-testid="mobile-qa-sheet"
            >
              {/* compact QAPanel hides its own header, so the sheet supplies the
                  single visible "Ask jaanch" title. Description stays SR-only. */}
              <SheetHeader className="border-b p-3 text-left">
                <SheetTitle className="text-sm font-semibold">Ask jaanch</SheetTitle>
                <SheetDescription className="sr-only">
                  Ask questions about this matter and its documents.
                </SheetDescription>
              </SheetHeader>
              <div className="min-h-0 flex-1">
                <QAPanel
                  matterId={matterId}
                  userId={userId}
                  onSourceClick={handleSourceClick}
                  compact
                />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </PDFSplitView>
    );
  }

  // Right sidebar layout
  if (position === 'right') {
    return (
      <PDFSplitView>
        <ResizablePanelGroup direction="horizontal" className="h-full flex-1" data-testid="workspace-content-area">
          <ResizablePanel defaultSize={100 - rightWidth} minSize={40}>
            <div className="h-full overflow-y-auto overflow-x-hidden" data-testid="workspace-main-content">{children}</div>
          </ResizablePanel>
          <ResizableHandle withHandle aria-label="Resize Q&A panel" />
          <ResizablePanel
            defaultSize={rightWidth}
            minSize={20}
            maxSize={60}
            onResize={setRightWidth}
            className="h-full"
          >
            <QAPanel
              matterId={matterId}
              userId={userId}
              onSourceClick={handleSourceClick}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </PDFSplitView>
    );
  }

  // Bottom panel layout
  if (position === 'bottom') {
    return (
      <PDFSplitView>
        <ResizablePanelGroup direction="vertical" className="h-full flex-1" data-testid="workspace-content-area">
          <ResizablePanel defaultSize={100 - bottomHeight} minSize={40}>
            <div className="h-full overflow-y-auto overflow-x-hidden" data-testid="workspace-main-content">{children}</div>
          </ResizablePanel>
          <ResizableHandle withHandle aria-label="Resize Q&A panel" />
          <ResizablePanel
            defaultSize={bottomHeight}
            minSize={20}
            maxSize={60}
            onResize={setBottomHeight}
            className="h-full"
          >
            <QAPanel
              matterId={matterId}
              userId={userId}
              onSourceClick={handleSourceClick}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </PDFSplitView>
    );
  }

  // Floating panel layout
  if (position === 'float') {
    return (
      <PDFSplitView>
        <div className="relative h-full flex-1" data-testid="workspace-content-area">
          <div className="h-full overflow-y-auto overflow-x-hidden" data-testid="workspace-main-content">{children}</div>
          <FloatingQAPanel
            matterId={matterId}
            userId={userId}
            onSourceClick={handleSourceClick}
          />
        </div>
      </PDFSplitView>
    );
  }

  // Hidden - just content with expand button
  return (
    <PDFSplitView>
      <div className="relative h-full flex-1" data-testid="workspace-content-area">
        <div className="h-full overflow-y-auto overflow-x-hidden" data-testid="workspace-main-content">{children}</div>
        <QAPanelExpandButton />
      </div>
    </PDFSplitView>
  );
}
