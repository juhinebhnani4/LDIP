'use client'

import { RefreshCw, WifiOff, X, CheckCircle } from 'lucide-react'
import { useState, useEffect, useCallback, useRef } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  getWSClient,
  type WSConnectionState,
  type WSReconnectInfo,
} from '@/lib/ws/client'

export interface ConnectionStatusBannerProps {
  /** Additional CSS classes */
  className?: string
}

/**
 * Global banner showing WebSocket connection status.
 * Epic 4: Resilient Real-time Updates
 *
 * Features:
 * - Shows "Reconnecting..." with attempt count during reconnection
 * - Shows brief "Connected" confirmation after successful reconnection
 * - Shows "Connection lost" when max attempts reached
 * - Can be dismissed (reappears on new reconnection attempts)
 */
export function ConnectionStatusBanner({ className }: ConnectionStatusBannerProps) {
  const [connectionState, setConnectionState] = useState<WSConnectionState>('disconnected')
  const [reconnectInfo, setReconnectInfo] = useState<WSReconnectInfo>(() => {
    // Initialize from client to stay in sync with RECONNECT_MAX_ATTEMPTS constant
    const wsClient = getWSClient()
    return wsClient.getReconnectInfo()
  })
  const [isDismissed, setIsDismissed] = useState(false)
  const [showConnected, setShowConnected] = useState(false)

  // Track previous state to detect reconnection success
  const prevStateRef = useRef<WSConnectionState>('disconnected')
  // Track timeout for cleanup (F2)
  const connectedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const wsClient = getWSClient()

    const unsubState = wsClient.onStateChange((state) => {
      // Track if we were reconnecting before this state change (F1 - use ref instead of stale closure)
      const wasReconnecting = prevStateRef.current === 'reconnecting'

      if (wasReconnecting && state === 'connected') {
        setShowConnected(true)
        // Clear any existing timeout (F2)
        if (connectedTimeoutRef.current) {
          clearTimeout(connectedTimeoutRef.current)
        }
        // Hide "Connected" confirmation after 3 seconds
        connectedTimeoutRef.current = setTimeout(() => {
          setShowConnected(false)
        }, 3000)
      }

      setConnectionState(state)
      prevStateRef.current = state

      // Reset dismiss when reconnection starts
      if (state === 'reconnecting') {
        setIsDismissed(false)
      }
    })

    const unsubReconnect = wsClient.onReconnectChange((info) => {
      setReconnectInfo(info)

      // Show toast when max attempts reached (use info values, not stale state)
      if (
        info.attempts >= info.maxAttempts &&
        !info.isReconnecting
      ) {
        toast.error('Connection lost', {
          description: 'Please refresh the page to reconnect',
          duration: 10000,
          action: {
            label: 'Refresh',
            onClick: () => {
              if (typeof window !== 'undefined') {
                window.location.reload()
              }
            },
          },
        })
      }
    })

    return () => {
      unsubState()
      unsubReconnect()
      // Cleanup timeout on unmount (F2)
      if (connectedTimeoutRef.current) {
        clearTimeout(connectedTimeoutRef.current)
      }
    }
  }, []) // Empty deps - subscriptions are stable

  const handleRefresh = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.location.reload()
    }
  }, [])

  // Show connected confirmation briefly after reconnection (F6 - showConnected is sufficient)
  if (showConnected) {
    return (
      <div
        className={cn(
          'bg-green-50 dark:bg-green-950/30 border-b border-green-200 dark:border-green-800',
          'px-4 py-2',
          className
        )}
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center justify-center gap-3 max-w-7xl mx-auto">
          <CheckCircle
            className="h-4 w-4 text-green-600 dark:text-green-500 shrink-0"
            aria-hidden="true"
          />
          <p className="text-sm text-green-800 dark:text-green-200 font-medium">
            Connected
          </p>
        </div>
      </div>
    )
  }

  // Don't show if connected, dismissed, or never attempted reconnection
  if (
    isDismissed ||
    connectionState === 'connected' ||
    (connectionState === 'disconnected' && reconnectInfo.attempts === 0)
  ) {
    return null
  }

  // Reconnecting state
  if (connectionState === 'reconnecting') {
    return (
      <div
        className={cn(
          'bg-blue-50 dark:bg-blue-950/30 border-b border-blue-200 dark:border-blue-800',
          'px-4 py-2',
          className
        )}
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center justify-between gap-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-3 text-sm">
            <RefreshCw
              className="h-4 w-4 text-blue-600 dark:text-blue-500 shrink-0 animate-spin"
              aria-hidden="true"
            />
            <p className="text-blue-800 dark:text-blue-200">
              <span className="font-medium">Reconnecting...</span>{' '}
              <span className="text-blue-600 dark:text-blue-400">
                (attempt {reconnectInfo.attempts}/{reconnectInfo.maxAttempts})
              </span>
            </p>
          </div>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setIsDismissed(true)}
            className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 shrink-0"
            aria-label="Dismiss connection status banner"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }

  // Disconnected state (after max attempts)
  if (connectionState === 'disconnected' && reconnectInfo.attempts >= reconnectInfo.maxAttempts) {
    return (
      <div
        className={cn(
          'bg-red-50 dark:bg-red-950/30 border-b border-red-200 dark:border-red-800',
          'px-4 py-2',
          className
        )}
        role="alert"
        aria-live="assertive"
      >
        <div className="flex items-center justify-between gap-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-3 text-sm">
            <WifiOff
              className="h-4 w-4 text-red-600 dark:text-red-500 shrink-0"
              aria-hidden="true"
            />
            <p className="text-red-800 dark:text-red-200">
              <span className="font-medium">Connection lost</span>{' '}
              <span className="text-red-600 dark:text-red-400">
                — Real-time updates unavailable
              </span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              className="text-red-600 border-red-300 hover:bg-red-100 dark:text-red-400 dark:border-red-700 dark:hover:bg-red-900/50"
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Refresh
            </Button>

            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setIsDismissed(true)}
              className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 shrink-0"
              aria-label="Dismiss connection status banner"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return null
}
