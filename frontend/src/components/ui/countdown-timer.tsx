'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Clock } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Progress } from '@/components/ui/progress'

export interface CountdownTimerProps {
  /** Initial seconds to count down from */
  seconds: number
  /** Callback when countdown reaches 0 */
  onComplete?: () => void
  /** Show progress bar */
  showProgress?: boolean
  /** Label to show before the countdown (e.g., "Retry in") */
  label?: string
  /** Additional CSS classes */
  className?: string
  /** Whether the timer is paused */
  isPaused?: boolean
}

/**
 * CountdownTimer component for rate limit and wait states.
 * Story 13.6: User-Facing Error Messages with Actionable Guidance (AC #3)
 *
 * Features:
 * - Counts down from provided seconds
 * - Calls onComplete when reaches 0
 * - Optional progress bar visualization
 * - Cleans up interval on unmount
 * - Can be paused/resumed
 */
export function CountdownTimer({
  seconds: initialSeconds,
  onComplete,
  showProgress = false,
  label = 'Retry in',
  className,
  isPaused = false,
}: CountdownTimerProps) {
  const [remainingSeconds, setRemainingSeconds] = useState(initialSeconds)
  const [hasCompleted, setHasCompleted] = useState(false)
  // Ref to prevent double onComplete calls during React strict mode or effect re-runs
  const completionCalledRef = useRef(false)

  // Calculate progress percentage (inverted: starts at 100%, ends at 0%)
  const progressPercent = (remainingSeconds / initialSeconds) * 100

  // Main countdown effect
  useEffect(() => {
    // Don't run if paused or already completed
    if (isPaused || hasCompleted) {
      return
    }

    // Complete immediately if time is already 0
    if (remainingSeconds <= 0) {
      if (!completionCalledRef.current) {
        completionCalledRef.current = true
        // eslint-disable-next-line react-hooks/set-state-in-effect -- Intentional: completing countdown triggers state change
        setHasCompleted(true)
        onComplete?.()
      }
      return
    }

    // Set up interval
    const intervalId = setInterval(() => {
      setRemainingSeconds((prev) => {
        const next = prev - 1
        return next >= 0 ? next : 0
      })
    }, 1000)

    // Cleanup on unmount or when deps change
    return () => clearInterval(intervalId)
  }, [isPaused, hasCompleted, remainingSeconds, onComplete])

  // Separate effect to handle completion when seconds reach 0 (from interval decrement)
  useEffect(() => {
    if (remainingSeconds === 0 && !hasCompleted && !isPaused && !completionCalledRef.current) {
      completionCalledRef.current = true
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Intentional: completing countdown triggers state change
      setHasCompleted(true)
      onComplete?.()
    }
  }, [remainingSeconds, hasCompleted, isPaused, onComplete])

  // Reset if initialSeconds changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Intentional: syncing state with prop change
    setRemainingSeconds(initialSeconds)
    setHasCompleted(false)
    completionCalledRef.current = false
  }, [initialSeconds])

  // Format time display
  const formatTime = (secs: number): string => {
    if (secs < 60) {
      return `${secs}s`
    }
    const minutes = Math.floor(secs / 60)
    const remainingSecs = secs % 60
    return `${minutes}m ${remainingSecs}s`
  }

  if (hasCompleted) {
    return null
  }

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="h-4 w-4" aria-hidden="true" />
        <span>
          {label} <span className="font-medium text-foreground">{formatTime(remainingSeconds)}</span>
        </span>
      </div>

      {showProgress && (
        <Progress
          value={progressPercent}
          className="h-1.5"
          aria-label={`${remainingSeconds} seconds remaining`}
        />
      )}
    </div>
  )
}

/**
 * Hook for countdown timer logic.
 * Useful when you need countdown state without the UI component.
 */
export function useCountdown(
  initialSeconds: number,
  options?: {
    onComplete?: () => void
    autoStart?: boolean
  }
) {
  const [seconds, setSeconds] = useState(initialSeconds)
  const [isRunning, setIsRunning] = useState(options?.autoStart ?? true)
  const [hasCompleted, setHasCompleted] = useState(false)
  const completionCalledRef = useRef(false)

  const start = useCallback(() => {
    setIsRunning(true)
    setHasCompleted(false)
    completionCalledRef.current = false
  }, [])

  const pause = useCallback(() => {
    setIsRunning(false)
  }, [])

  const reset = useCallback(() => {
    setSeconds(initialSeconds)
    setHasCompleted(false)
    setIsRunning(false)
    completionCalledRef.current = false
  }, [initialSeconds])

  useEffect(() => {
    if (!isRunning || hasCompleted) {
      return
    }

    if (seconds <= 0) {
      if (!completionCalledRef.current) {
        completionCalledRef.current = true
        // eslint-disable-next-line react-hooks/set-state-in-effect -- Intentional: completing countdown triggers state change
        setHasCompleted(true)
        options?.onComplete?.()
      }
      return
    }

    const intervalId = setInterval(() => {
      setSeconds((prev) => {
        const next = prev - 1
        if (next <= 0) {
          clearInterval(intervalId)
          return 0
        }
        return next
      })
    }, 1000)

    return () => clearInterval(intervalId)
  }, [seconds, isRunning, hasCompleted, options])

  return {
    seconds,
    isRunning,
    hasCompleted,
    start,
    pause,
    reset,
  }
}
