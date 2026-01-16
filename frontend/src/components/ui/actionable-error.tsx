'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  AlertCircle,
  RefreshCw,
  X,
  LogIn,
  ExternalLink,
  Clock,
  HelpCircle,
} from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'
import { cn } from '@/lib/utils'
import {
  getErrorMessageWithAction,
  getErrorAction,
  getSecondaryErrorAction,
  type ActionType,
  type ErrorAction,
} from '@/lib/utils/error-messages'

export interface ActionableErrorProps {
  /** The error to display - can be ApiError, Error, or string */
  error: ApiError | Error | string
  /** Explicit error code if not in error object */
  errorCode?: string
  /** Callback when user clicks retry - only used for retry actions */
  onRetry?: () => Promise<void> | void
  /** Callback when user dismisses the alert */
  onDismiss?: () => void
  /** Additional CSS classes */
  className?: string
  /** Matter ID for support context */
  matterId?: string
  /** Callback for opening contact support dialog */
  onContactSupport?: (context: ErrorContext) => void
}

/** Context passed to contact support */
export interface ErrorContext {
  errorCode: string
  errorMessage: string
  timestamp: string
  matterId?: string
  currentUrl: string
}

/** Icon map for action types */
const ACTION_ICONS: Record<ActionType, typeof RefreshCw> = {
  retry: RefreshCw,
  wait: Clock,
  contact_support: HelpCircle,
  login: LogIn,
  refresh: RefreshCw,
  navigate: ExternalLink,
}

/**
 * ActionableError component with action buttons based on error type.
 * Story 13.6: User-Facing Error Messages with Actionable Guidance
 *
 * Features:
 * - Maps API error codes to user-friendly messages with actions
 * - Primary action button based on error type
 * - Optional secondary action (e.g., contact support)
 * - Loading state for retry action
 * - Handles navigation, login redirect, and page refresh
 */
export function ActionableError({
  error,
  errorCode: explicitErrorCode,
  onRetry,
  onDismiss,
  className,
  matterId,
  onContactSupport,
}: ActionableErrorProps) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)

  // Extract error code and details
  const errorCode =
    explicitErrorCode ?? (error instanceof ApiError ? error.code : 'UNKNOWN_ERROR')
  const retryAfter = error instanceof ApiError ? error.rateLimitDetails?.retryAfter : undefined
  const errorInfo = getErrorMessageWithAction(errorCode)
  const primaryAction = getErrorAction(errorCode, { retryAfter, matterId })
  const secondaryAction = getSecondaryErrorAction(errorCode)

  // Get description (prefer API error user message, fallback to mapped description)
  const description =
    typeof error === 'string'
      ? error
      : error instanceof ApiError
        ? error.userMessage
        : error.message || errorInfo.description

  // Build error context for support
  const buildErrorContext = (): ErrorContext => ({
    errorCode,
    errorMessage: description,
    timestamp: new Date().toISOString(),
    matterId,
    currentUrl: typeof window !== 'undefined' ? window.location.href : '',
  })

  // Handle action button click
  const handleAction = async (action: ErrorAction) => {
    switch (action.type) {
      case 'retry':
        if (onRetry) {
          setIsLoading(true)
          try {
            await onRetry()
          } finally {
            setIsLoading(false)
          }
        }
        break

      case 'wait':
        // Wait action is handled by CountdownTimer in parent
        // If no countdown, treat as retry
        if (onRetry) {
          setIsLoading(true)
          try {
            await onRetry()
          } finally {
            setIsLoading(false)
          }
        }
        break

      case 'contact_support':
        if (onContactSupport) {
          onContactSupport(buildErrorContext())
        } else {
          // Fallback: open mailto link
          const context = buildErrorContext()
          const subject = encodeURIComponent(`Error Report: ${errorCode}`)
          const body = encodeURIComponent(
            `Error Code: ${context.errorCode}\n` +
              `Time: ${context.timestamp}\n` +
              `URL: ${context.currentUrl}\n` +
              `Matter: ${context.matterId ?? 'N/A'}\n\n` +
              `Description: ${context.errorMessage}`
          )
          window.open(`mailto:support@jaanch.ai?subject=${subject}&body=${body}`, '_blank')
        }
        break

      case 'login':
        // Store return URL before redirect
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('returnUrl', window.location.href)
        }
        router.push('/login?session_expired=true')
        break

      case 'refresh':
        if (typeof window !== 'undefined') {
          window.location.reload()
        }
        break

      case 'navigate':
        if (action.url) {
          if (action.url.startsWith('#')) {
            // Anchor navigation
            const element = document.querySelector(action.url)
            element?.scrollIntoView({ behavior: 'smooth' })
          } else {
            router.push(action.url)
          }
        }
        break
    }
  }

  // Get icon for action
  const getActionIcon = (actionType: ActionType) => {
    const Icon = ACTION_ICONS[actionType]
    return <Icon className={cn('mr-1 h-3 w-3', isLoading && actionType === 'retry' && 'animate-spin')} />
  }

  // Should show primary action button
  const showPrimaryAction =
    primaryAction.type === 'retry' && onRetry
      ? true
      : primaryAction.type === 'wait' && onRetry
        ? true
        : primaryAction.type !== 'retry' && primaryAction.type !== 'wait'

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

        {(showPrimaryAction || secondaryAction || onDismiss) && (
          <div className="flex flex-wrap items-center gap-2">
            {showPrimaryAction && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction(primaryAction)}
                disabled={isLoading}
                className="h-7 px-2 text-xs"
              >
                {getActionIcon(primaryAction.type)}
                {isLoading && primaryAction.type === 'retry' ? 'Retrying...' : primaryAction.label}
              </Button>
            )}

            {secondaryAction && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleAction(secondaryAction)}
                disabled={isLoading}
                className="h-7 px-2 text-xs"
              >
                {getActionIcon(secondaryAction.type)}
                {secondaryAction.label}
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
