import type { ReactNode } from "react"
import { MatterWorkspaceWrapper } from "@/components/features/matter"

interface MatterLayoutProps {
  children: ReactNode
  params: Promise<{ matterId: string }>
}

export default async function MatterLayout({ children, params }: MatterLayoutProps) {
  const { matterId } = await params

  return (
    <div className="min-h-screen">
      {/* Matter workspace header will be implemented in Epic 10A */}
      <main data-matter-id={matterId}>
        <MatterWorkspaceWrapper matterId={matterId}>
          {children}
        </MatterWorkspaceWrapper>
      </main>
    </div>
  )
}
