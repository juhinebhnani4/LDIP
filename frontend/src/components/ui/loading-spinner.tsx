'use client'

import { Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface LoadingSpinnerProps {
  /** Optional message to display below the spinner */
  message?: string
  /** Size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Additional CSS classes */
  className?: string
}

const sizeStyles = {
  sm: { spinner: 'h-4 w-4', text: 'text-xs' },
  md: { spinner: 'h-6 w-6', text: 'text-sm' },
  lg: { spinner: 'h-8 w-8', text: 'text-base' },
}

/**
 * Loading spinner with optional message.
 * Story 13.4: Graceful Degradation and Error States (AC #2)
 *
 * Features:
 * - Three size variants
 * - Optional loading message
 * - Accessible with appropriate ARIA attributes
 */
export function LoadingSpinner({ message, size = 'md', className }: LoadingSpinnerProps) {
  const styles = sizeStyles[size]

  return (
    <div
      className={cn('flex flex-col items-center justify-center gap-2', className)}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2
        className={cn('animate-spin text-muted-foreground', styles.spinner)}
        aria-hidden="true"
      />
      {message && (
        <p className={cn('text-muted-foreground', styles.text)}>{message}</p>
      )}
      <span className="sr-only">{message ?? 'Loading...'}</span>
    </div>
  )
}
