'use client'

import { useState, useCallback } from 'react'
import { AlertCircle, RefreshCw, Clock } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { CountdownTimer } from '@/components/ui/countdown-timer'
import { ApiError } from '@/lib/api/client'
import { cn } from '@/lib/utils'

export interface RateLimitErrorProps {
  /** The ApiError with rate limit details */
  error: ApiError
  /** Callback when user clicks retry or countdown completes */
  onRetry: () => Promise<void> | void
  /** Callback when user dismisses the alert */
  onDismiss?: () => void
  /** Whether to auto-retry when countdown ends */
  autoRetry?: boolean
  /** Additional CSS classes */
  className?: string
}

/**
 * RateLimitError component with countdown timer and auto-retry.
 * Story 13.6: User-Facing Error Messages with Actionable Guidance (AC #3)
 *
 * Features:
 * - Shows countdown timer for rate limit duration
 * - Auto-retry option when countdown ends
 * - Manual retry button
 * - Progress visualization
 */
export function RateLimitError({
  error,
  onRetry,
  onDismiss,
  autoRetry = true,
  className,
}: RateLimitErrorProps) {
  const [isRetrying, setIsRetrying] = useState(false)
  const [countdownComplete, setCountdownComplete] = useState(false)

  // Get retry-after seconds from error, default to 60
  const retryAfter = error.rateLimitDetails?.retryAfter ?? 60

  const handleRetry = useCallback(async () => {
    setIsRetrying(true)
    try {
      await onRetry()
    } finally {
      setIsRetrying(false)
    }
  }, [onRetry])

  const handleCountdownComplete = useCallback(() => {
    setCountdownComplete(true)
    if (autoRetry) {
      handleRetry()
    }
  }, [autoRetry, handleRetry])

  return (
    <Alert
      variant="destructive"
      className={cn('relative', className)}
      role="alert"
      aria-live="polite"
    >
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Too Many Requests</AlertTitle>
      <AlertDescription className="flex flex-col gap-3">
        <p>
          You&apos;re making requests too quickly. Please wait before trying again.
        </p>

        {/* Countdown Timer */}
        {!countdownComplete && !isRetrying && (
          <div className="py-2">
            <CountdownTimer
              seconds={retryAfter}
              onComplete={handleCountdownComplete}
              showProgress
              label={autoRetry ? 'Auto-retry in' : 'Retry available in'}
            />
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {countdownComplete || isRetrying ? (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetry}
              disabled={isRetrying}
              className="h-7 px-2 text-xs"
            >
              {isRetrying ? (
                <>
                  <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
                  Retrying...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Try Again Now
                </>
              )}
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetry}
              disabled={isRetrying}
              className="h-7 px-2 text-xs"
            >
              <Clock className="mr-1 h-3 w-3" />
              Skip Wait
            </Button>
          )}

          {onDismiss && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              disabled={isRetrying}
              className="h-7 px-2 text-xs"
            >
              Dismiss
            </Button>
          )}
        </div>

        {autoRetry && !countdownComplete && (
          <p className="text-xs text-muted-foreground">
            Your request will automatically retry when the wait time is over.
          </p>
        )}
      </AlertDescription>
    </Alert>
  )
}
