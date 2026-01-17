"use client"

import { ThemeProvider } from "next-themes"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SWRConfig } from "swr"
import type { ReactNode } from "react"

interface ProvidersProps {
  children: ReactNode
}

/**
 * Global SWR configuration for optimal performance.
 *
 * Performance optimizations:
 * - revalidateOnFocus: false - Don't refetch when window regains focus (reduces API calls)
 * - revalidateOnReconnect: true - Refetch when network reconnects (data may be stale)
 * - dedupingInterval: 10000 - Dedupe identical requests within 10 seconds
 * - errorRetryCount: 3 - Retry failed requests up to 3 times
 * - errorRetryInterval: 5000 - Wait 5 seconds between retries
 * - shouldRetryOnError: Don't retry on 4xx client errors (they won't succeed)
 */
const swrConfig = {
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
  dedupingInterval: 10000,
  errorRetryCount: 3,
  errorRetryInterval: 5000,
  shouldRetryOnError: (error: unknown) => {
    // Don't retry on client errors (4xx) - they won't succeed
    if (error && typeof error === 'object' && 'status' in error) {
      const status = (error as { status: number }).status
      if (status >= 400 && status < 500) {
        return false
      }
    }
    return true
  },
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <SWRConfig value={swrConfig}>
        <TooltipProvider>
          {children}
        </TooltipProvider>
      </SWRConfig>
    </ThemeProvider>
  )
}
