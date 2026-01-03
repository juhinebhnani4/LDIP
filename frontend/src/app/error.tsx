"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"

interface ErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    // TODO: send to a monitoring service in production; for now log to console in dev only.
    if (process.env.NODE_ENV !== "production") {
      console.error("Application error:", error)
    }
  }, [error])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="space-y-4 text-center">
        <h2 className="text-2xl font-bold">Something went wrong</h2>
        <p className="text-muted-foreground">{error.message || "An unexpected error occurred"}</p>
        <Button onClick={reset}>Try again</Button>
      </div>
    </div>
  )
}
