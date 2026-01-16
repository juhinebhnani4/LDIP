'use client'

import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

export interface ProgressBarProps {
  /** Progress value from 0 to 100 */
  value: number
  /** Optional message to display below the progress bar */
  message?: string
  /** Whether to show the percentage value */
  showPercentage?: boolean
  /** Size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Additional CSS classes */
  className?: string
}

const sizeStyles = {
  sm: { bar: 'h-1', text: 'text-xs' },
  md: { bar: 'h-2', text: 'text-sm' },
  lg: { bar: 'h-3', text: 'text-base' },
}

/**
 * Progress bar component with percentage and message.
 * Story 13.4: Graceful Degradation and Error States (AC #2)
 *
 * Features:
 * - Three size variants
 * - Optional percentage display
 * - Optional status message
 * - Accessible with appropriate ARIA attributes
 */
export function ProgressBar({
  value,
  message,
  showPercentage = true,
  size = 'md',
  className,
}: ProgressBarProps) {
  const styles = sizeStyles[size]
  const clampedValue = Math.min(100, Math.max(0, value))

  return (
    <div className={cn('w-full', className)} role="progressbar" aria-valuenow={clampedValue} aria-valuemin={0} aria-valuemax={100}>
      <div className="flex items-center justify-between gap-2 mb-1">
        {message && (
          <p className={cn('text-muted-foreground truncate', styles.text)}>{message}</p>
        )}
        {showPercentage && (
          <span className={cn('text-muted-foreground tabular-nums', styles.text)}>
            {Math.round(clampedValue)}%
          </span>
        )}
      </div>
      <Progress value={clampedValue} className={styles.bar} />
    </div>
  )
}
