import type { ReactNode } from 'react';
import {
  MatterWorkspaceWrapper,
  WorkspaceHeader,
  WorkspaceTabBar,
  WorkspaceContentArea,
} from '@/components/features/matter';
import { ServiceStatusBanner, ConnectionStatusBanner } from '@/components/features/status';

interface MatterLayoutProps {
  children: ReactNode;
  params: Promise<{ matterId: string }>;
}

/**
 * Matter Workspace Layout
 *
 * Provides the consistent shell for all matter pages with:
 * - WorkspaceHeader (Story 10A.1): Sticky header with back nav, matter name, actions
 * - WorkspaceTabBar (Story 10A.2): Tab navigation for Summary, Timeline, etc.
 * - WorkspaceContentArea (Story 10A.3): Resizable content + Q&A panel layout
 * - MatterWorkspaceWrapper: Processing status provider
 *
 * Layout:
 * ┌─────────────────────────────────────────────────────────────────────────────────┐
 * │  WORKSPACE HEADER (sticky top-0)                                                │
 * │  ← Dashboard      [Matter Name]                    [Export] [Share] [Settings]  │
 * ├─────────────────────────────────────────────────────────────────────────────────┤
 * │  TAB BAR (sticky top-14)                                                        │
 * │  Summary | Timeline | Entities | Citations | Contradictions | Verification | Docs │
 * ├─────────────────────────────────────────────────────────────────────────────────┤
 * │                                                                                  │
 * │  CONTENT AREA (scrollable)              │  Q&A PANEL                            │
 * │  [children - tab content]               │  [QAPanel or FloatingQAPanel]         │
 * │                                         │                                        │
 * └─────────────────────────────────────────────────────────────────────────────────┘
 */
export default async function MatterLayout({ children, params }: MatterLayoutProps) {
  const { matterId } = await params;

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Service status banner - Story 13.4 (only shows when circuits are degraded) */}
      <ServiceStatusBanner />

      {/* Connection status banner - Epic 4 (only shows during reconnection) */}
      <ConnectionStatusBanner />

      {/* Workspace header - Story 10A.1 */}
      <div className="shrink-0">
        <WorkspaceHeader matterId={matterId} />
      </div>

      {/* Tab bar navigation - Story 10A.2 */}
      <div className="shrink-0">
        <WorkspaceTabBar matterId={matterId} />
      </div>

      {/* Main content area with Q&A panel - Story 10A.3 */}
      <main data-matter-id={matterId} className="flex min-h-0 flex-1 overflow-hidden">
        <MatterWorkspaceWrapper matterId={matterId}>
          <WorkspaceContentArea matterId={matterId}>
            {children}
          </WorkspaceContentArea>
        </MatterWorkspaceWrapper>
      </main>
    </div>
  );
}
