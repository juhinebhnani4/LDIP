'use client';

import type { ReactNode } from 'react';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { useQAPanelStore } from '@/stores/qaPanelStore';
import { useUser } from '@/hooks';
import { QAPanel } from '@/components/features/chat/QAPanel';
import { FloatingQAPanel } from '@/components/features/chat/FloatingQAPanel';
import { QAPanelExpandButton } from '@/components/features/chat/QAPanelExpandButton';

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

  // Right sidebar layout
  if (position === 'right') {
    return (
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
          <QAPanel matterId={matterId} userId={userId} />
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  // Bottom panel layout
  if (position === 'bottom') {
    return (
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
          <QAPanel matterId={matterId} userId={userId} />
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  // Floating panel layout
  if (position === 'float') {
    return (
      <div className="relative flex-1">
        <div className="h-full overflow-auto">{children}</div>
        <FloatingQAPanel matterId={matterId} userId={userId} />
      </div>
    );
  }

  // Hidden - just content with expand button
  return (
    <div className="relative flex-1">
      <div className="h-full overflow-auto">{children}</div>
      <QAPanelExpandButton />
    </div>
  );
}
