'use client'

import { AlertTriangle, X } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useServiceHealth } from '@/hooks/useServiceHealth'
import { cn } from '@/lib/utils'

export interface ServiceStatusBannerProps {
  /** Additional CSS classes */
  className?: string
}

/**
 * Global banner showing service degradation status.
 * Story 13.4: Graceful Degradation and Error States (AC #3)
 *
 * Features:
 * - Only shows when at least one circuit is open
 * - Shows user-friendly feature names that are affected
 * - Can be dismissed (reappears if new circuits open)
 * - Polls circuit status every 30 seconds
 */
export function ServiceStatusBanner({ className }: ServiceStatusBannerProps) {
  const { hasOpenCircuits, affectedFeatures, circuits } = useServiceHealth()
  const [isDismissed, setIsDismissed] = useState(false)

  // Don't show if no open circuits or user dismissed
  if (!hasOpenCircuits || isDismissed) {
    return null
  }

  // Get cooldown info for the banner message
  const openCircuits = circuits.filter((c) => c.state === 'open')
  const maxCooldown = Math.max(...openCircuits.map((c) => c.cooldownRemaining), 0)
  const cooldownMessage = maxCooldown > 0 ? ` (recovery expected in ~${Math.ceil(maxCooldown / 60)} min)` : ''

  return (
    <div
      className={cn(
        'bg-yellow-50 dark:bg-yellow-950/30 border-b border-yellow-200 dark:border-yellow-800',
        'px-4 py-2',
        className
      )}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-3 text-sm">
          <AlertTriangle
            className="h-4 w-4 text-yellow-600 dark:text-yellow-500 shrink-0"
            aria-hidden="true"
          />
          <p className="text-yellow-800 dark:text-yellow-200">
            <span className="font-medium">Some features are limited:</span>{' '}
            {affectedFeatures.length > 0
              ? affectedFeatures.join(', ')
              : 'External services experiencing issues'}
            {cooldownMessage}
          </p>
        </div>

        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setIsDismissed(true)}
          className="text-yellow-600 hover:text-yellow-700 dark:text-yellow-400 dark:hover:text-yellow-300 shrink-0"
          aria-label="Dismiss service status banner"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
