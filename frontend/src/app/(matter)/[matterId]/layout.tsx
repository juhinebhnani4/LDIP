import type { ReactNode } from "react"
import { MatterWorkspaceWrapper, WorkspaceHeader } from "@/components/features/matter"
import { TooltipProvider } from "@/components/ui/tooltip"

interface MatterLayoutProps {
  children: ReactNode
  params: Promise<{ matterId: string }>
}

export default async function MatterLayout({ children, params }: MatterLayoutProps) {
  const { matterId } = await params

  return (
    <TooltipProvider>
      <div className="min-h-screen flex flex-col">
        {/* Workspace header - Story 10A.1 */}
        <WorkspaceHeader matterId={matterId} />

        {/* Main content area */}
        <main data-matter-id={matterId} className="flex-1">
          <MatterWorkspaceWrapper matterId={matterId}>
            {children}
          </MatterWorkspaceWrapper>
        </main>
      </div>
    </TooltipProvider>
  )
}
