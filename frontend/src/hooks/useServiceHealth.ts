'use client'

import { useCallback, useEffect, useState } from 'react'

import { getAffectedFeatures } from '@/lib/utils/error-messages'

/** Circuit breaker status for a single service */
export interface CircuitStatus {
  /** Circuit name identifier */
  name: string
  /** Current state of the circuit */
  state: 'closed' | 'open' | 'half_open'
  /** Number of failures recorded */
  failureCount: number
  /** Number of successful calls */
  successCount: number
  /** Timestamp of last failure */
  lastFailure: string | null
  /** Seconds remaining in cooldown (if open) */
  cooldownRemaining: number
}

/** Service health state returned by the hook */
export interface ServiceHealthState {
  /** All circuit statuses */
  circuits: CircuitStatus[]
  /** Whether any circuit is currently open */
  hasOpenCircuits: boolean
  /** Loading state for initial fetch */
  isLoading: boolean
  /** Error from last fetch attempt */
  error: Error | null
  /** User-friendly names of affected features */
  affectedFeatures: string[]
  /** Manually trigger a refresh */
  refresh: () => Promise<void>
}

/** API response structure */
interface CircuitsApiResponse {
  data: {
    circuits: Array<{
      circuit_name: string
      state: 'closed' | 'open' | 'half_open'
      failure_count: number
      success_count: number
      last_failure: string | null
      cooldown_remaining: number
    }>
    summary: {
      total: number
      open: number
      closed: number
      half_open: number
    }
  }
}

const DEFAULT_POLL_INTERVAL = 30000 // 30 seconds

/**
 * Hook to poll circuit breaker health status.
 * Story 13.4: Graceful Degradation and Error States (AC #3)
 *
 * Features:
 * - Polls /api/health/circuits every 30 seconds by default
 * - Only polls when document is visible (saves resources)
 * - Returns affected features for UI display
 * - Supports manual refresh
 *
 * @param pollIntervalMs - Polling interval in milliseconds (default: 30000)
 */
export function useServiceHealth(pollIntervalMs: number = DEFAULT_POLL_INTERVAL): ServiceHealthState {
  const [circuits, setCircuits] = useState<CircuitStatus[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchCircuits = useCallback(async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/health/circuits`)

      if (!response.ok) {
        throw new Error(`Failed to fetch circuit status: ${response.status}`)
      }

      const data: CircuitsApiResponse = await response.json()

      const mappedCircuits: CircuitStatus[] = data.data.circuits.map((c) => ({
        name: c.circuit_name,
        state: c.state,
        failureCount: c.failure_count,
        successCount: c.success_count,
        lastFailure: c.last_failure,
        cooldownRemaining: c.cooldown_remaining,
      }))

      setCircuits(mappedCircuits)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Set up polling with visibility handling
  useEffect(() => {
    // Initial fetch
    fetchCircuits()

    // Only poll when document is visible
    let intervalId: NodeJS.Timeout | null = null

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(fetchCircuits, pollIntervalMs)
      }
    }

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // Fetch immediately when becoming visible, then resume polling
        fetchCircuits()
        startPolling()
      } else {
        stopPolling()
      }
    }

    // Start polling if document is visible
    if (document.visibilityState === 'visible') {
      startPolling()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [fetchCircuits, pollIntervalMs])

  // Calculate derived state
  const openCircuitNames = circuits.filter((c) => c.state === 'open').map((c) => c.name)
  const hasOpenCircuits = openCircuitNames.length > 0
  const affectedFeatures = getAffectedFeatures(openCircuitNames)

  return {
    circuits,
    hasOpenCircuits,
    isLoading,
    error,
    affectedFeatures,
    refresh: fetchCircuits,
  }
}
