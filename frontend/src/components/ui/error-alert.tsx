'use client'

import { AlertCircle, RefreshCw, X } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'
import { cn } from '@/lib/utils'
import { getErrorMessage, isRetryableError } from '@/lib/utils/error-messages'

export interface ErrorAlertProps {
  /** The error to display - can be ApiError, Error, or string */
  error: ApiError | Error | string
  /** Callback when user clicks retry - only shown if provided and error is retryable */
  onRetry?: () => void
  /** Callback when user dismisses the alert */
  onDismiss?: () => void
  /** Additional CSS classes */
  className?: string
  /** Whether the retry operation is in progress */
  isRetrying?: boolean
}

/**
 * Reusable error alert component with optional retry and dismiss actions.
 * Story 13.4: Graceful Degradation and Error States (AC #1, #4)
 *
 * Features:
 * - Maps API error codes to user-friendly messages
 * - Shows retry button for retryable errors
 * - Optional dismiss button
 * - Loading state for retry action
 */
export function ErrorAlert({
  error,
  onRetry,
  onDismiss,
  className,
  isRetrying = false,
}: ErrorAlertProps) {
  // Extract error code and determine display properties
  const errorCode = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR'
  const errorInfo = getErrorMessage(errorCode)
  const canRetry = isRetryableError(errorCode) && Boolean(onRetry)

  // For string errors or generic Error, use the message directly
  const description =
    typeof error === 'string'
      ? error
      : error instanceof ApiError
        ? errorInfo.description
        : error.message || errorInfo.description

  return (
    <Alert
      variant="destructive"
      className={cn('relative', className)}
      role="alert"
      aria-live="polite"
    >
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>{errorInfo.title}</AlertTitle>
      <AlertDescription className="flex flex-col gap-3">
        <p>{description}</p>

        {(canRetry || onDismiss) && (
          <div className="flex items-center gap-2">
            {canRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
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
                    Try Again
                  </>
                )}
              </Button>
            )}

            {onDismiss && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onDismiss}
                className="h-7 px-2 text-xs"
                aria-label="Dismiss error"
              >
                <X className="mr-1 h-3 w-3" />
                Dismiss
              </Button>
            )}
          </div>
        )}
      </AlertDescription>
    </Alert>
  )
}
