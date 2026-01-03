import Link from "next/link"

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-24">
        <h1 className="text-4xl font-bold tracking-tight">LDIP</h1>
        <p className="text-muted-foreground text-lg">
          Legal Document Intelligence Platform — upload documents, extract entities/citations, and
          build matter timelines with verifiable evidence.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link className="underline" href="/login">
            Go to Login
          </Link>
        </div>
        {/* Dashboard features will be implemented in Epic 9 */}
      </main>
    </div>
  )
}
