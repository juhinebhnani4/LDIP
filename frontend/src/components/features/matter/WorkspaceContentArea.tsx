'use client';

import { useCallback, type ReactNode } from 'react';
import { toast } from 'sonner';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { useQAPanelStore } from '@/stores/qaPanelStore';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';
import { useUser } from '@/hooks';
import { QAPanel } from '@/components/features/chat/QAPanel';
import { FloatingQAPanel } from '@/components/features/chat/FloatingQAPanel';
import { QAPanelExpandButton } from '@/components/features/chat/QAPanelExpandButton';
import { PDFSplitView } from '@/components/features/pdf/PDFSplitView';
import type { SourceReference } from '@/types/chat';

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
  const rightWidth = useQAPanelStore((state) => state.rightWidth);
  const bottomHeight = useQAPanelStore((state) => state.bottomHeight);
  const setRightWidth = useQAPanelStore((state) => state.setRightWidth);
  const setBottomHeight = useQAPanelStore((state) => state.setBottomHeight);
  const { user } = useUser();
  const userId = user?.id;

  // PDF split view action
  const openPdfSplitView = usePdfSplitViewStore(
    (state) => state.openPdfSplitView
  );

  /**
   * Handle source reference clicks from Q&A panel.
   * Fetches document signed URL and opens PDF split view.
   * Story 11.5: PDF Split View for source references (AC: #4)
   */
  const handleSourceClick = useCallback(
    async (source: SourceReference) => {
      try {
        // Fetch document details to get signed URL
        const response = await fetch(`/api/documents/${source.documentId}`);

        if (!response.ok) {
          throw new Error('Failed to fetch document');
        }

        const result = await response.json();
        const documentUrl = result.data?.storage_path;

        if (!documentUrl) {
          throw new Error('Document URL not found');
        }

        // Open PDF split view with document
        openPdfSplitView(source, matterId, documentUrl);
      } catch {
        toast.error('Unable to open document. Please try again.');
      }
    },
    [matterId, openPdfSplitView]
  );

  // Right sidebar layout
  if (position === 'right') {
    return (
      <PDFSplitView>
        <ResizablePanelGroup direction="horizontal" className="flex-1">
          <ResizablePanel defaultSize={100 - rightWidth} minSize={40}>
            <div className="h-full overflow-auto">{children}</div>
          </ResizablePanel>
          <ResizableHandle withHandle aria-label="Resize Q&A panel" />
          <ResizablePanel
            defaultSize={rightWidth}
            minSize={20}
            maxSize={60}
            onResize={setRightWidth}
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
        <ResizablePanelGroup direction="vertical" className="flex-1">
          <ResizablePanel defaultSize={100 - bottomHeight} minSize={40}>
            <div className="h-full overflow-auto">{children}</div>
          </ResizablePanel>
          <ResizableHandle withHandle aria-label="Resize Q&A panel" />
          <ResizablePanel
            defaultSize={bottomHeight}
            minSize={20}
            maxSize={60}
            onResize={setBottomHeight}
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
        <div className="relative flex-1">
          <div className="h-full overflow-auto">{children}</div>
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
      <div className="relative flex-1">
        <div className="h-full overflow-auto">{children}</div>
        <QAPanelExpandButton />
      </div>
    </PDFSplitView>
  );
}
