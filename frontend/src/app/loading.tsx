export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="animate-pulse space-y-4 text-center">
        <div className="bg-muted h-8 w-32 rounded" />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  )
}
