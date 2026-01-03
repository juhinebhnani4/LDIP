import type { ReactNode } from "react"

interface MatterLayoutProps {
  children: ReactNode
  params: Promise<{ matterId: string }>
}

export default async function MatterLayout({ children, params }: MatterLayoutProps) {
  const { matterId } = await params

  return (
    <div className="min-h-screen">
      {/* Matter workspace header will be implemented in Epic 10A */}
      <main data-matter-id={matterId}>{children}</main>
    </div>
  )
}
