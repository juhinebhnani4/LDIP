'use client'

import { AlertCircle, AlertTriangle, Info, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type InlineErrorSeverity = 'error' | 'warning' | 'info'

export interface InlineErrorProps {
  /** Error message to display */
  message: string
  /** Severity level - affects icon and styling */
  severity?: InlineErrorSeverity
  /** Optional callback for retry action */
  onRetry?: () => void
  /** Whether retry is in progress */
  isRetrying?: boolean
  /** Additional CSS classes */
  className?: string
}

const severityStyles: Record<InlineErrorSeverity, { icon: typeof AlertCircle; className: string }> = {
  error: {
    icon: AlertCircle,
    className: 'text-destructive',
  },
  warning: {
    icon: AlertTriangle,
    className: 'text-yellow-600 dark:text-yellow-500',
  },
  info: {
    icon: Info,
    className: 'text-blue-600 dark:text-blue-400',
  },
}

/**
 * Inline error message component with icon.
 * Story 13.4: Graceful Degradation and Error States (AC #1)
 *
 * Features:
 * - Three severity levels: error, warning, info
 * - Optional retry button
 * - Compact design for inline usage
 */
export function InlineError({
  message,
  severity = 'error',
  onRetry,
  isRetrying = false,
  className,
}: InlineErrorProps) {
  const { icon: Icon, className: severityClassName } = severityStyles[severity]

  return (
    <div
      className={cn('flex items-center gap-2 text-sm', severityClassName, className)}
      role={severity === 'error' ? 'alert' : 'status'}
      aria-live="polite"
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="flex-1">{message}</span>

      {onRetry && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onRetry}
          disabled={isRetrying}
          className="h-6 px-2 text-xs"
          aria-label="Retry"
        >
          <RefreshCw
            className={cn('h-3 w-3', isRetrying && 'animate-spin')}
            aria-hidden="true"
          />
        </Button>
      )}
    </div>
  )
}
