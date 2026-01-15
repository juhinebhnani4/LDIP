import type { ReactNode } from 'react';
import { MatterWorkspaceWrapper, WorkspaceHeader, WorkspaceTabBar } from '@/components/features/matter';

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
 * │  CONTENT AREA (scrollable)                                                       │
 * │  [children - tab content]                                                        │
 * │                                                                                  │
 * └─────────────────────────────────────────────────────────────────────────────────┘
 */
export default async function MatterLayout({ children, params }: MatterLayoutProps) {
  const { matterId } = await params;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Workspace header - Story 10A.1 */}
      <WorkspaceHeader matterId={matterId} />

      {/* Tab bar navigation - Story 10A.2 */}
      <WorkspaceTabBar matterId={matterId} />

      {/* Main content area */}
      <main data-matter-id={matterId} className="flex-1">
        <MatterWorkspaceWrapper matterId={matterId}>
          {children}
        </MatterWorkspaceWrapper>
      </main>
    </div>
  );
}
