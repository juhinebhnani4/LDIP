/**
 * useWebSocket Hook
 *
 * Core React hook for WebSocket connection to a matter.
 * Manages connection lifecycle and provides subscription capabilities.
 *
 * Features:
 * - Automatic connect/disconnect based on matterId
 * - Connection state tracking
 * - Type-safe message subscriptions
 * - Error handling
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  getWSClient,
  type WSConnectionState,
  type WSMessageType,
  type WSMessage,
  type WSSubscriber,
  type WSUnsubscribe,
  type WSReconnectInfo,
} from '@/lib/ws/client';

// =============================================================================
// Types
// =============================================================================

export interface UseWebSocketOptions {
  /** Whether WebSocket is enabled (default: true) */
  enabled?: boolean;
  /** Connect automatically when matterId changes (default: true) */
  autoConnect?: boolean;
}

export interface UseWebSocketResult {
  /** Current connection state */
  connectionState: WSConnectionState;
  /** Whether currently connected */
  isConnected: boolean;
  /** Whether currently reconnecting */
  isReconnecting: boolean;
  /** Reconnect info (attempts, maxAttempts) */
  reconnectInfo: WSReconnectInfo;
  /** Last error message */
  error: string | null;
  /** Subscribe to a message type */
  subscribe: <T = unknown>(type: WSMessageType | 'all', callback: WSSubscriber<T>) => WSUnsubscribe;
  /** Manually connect (if autoConnect is false) */
  connect: () => Promise<void>;
  /** Manually disconnect */
  disconnect: () => void;
}

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook to manage WebSocket connection for a matter.
 *
 * @param matterId - Matter ID to connect to, null to disable
 * @param options - Connection options
 * @returns WebSocket connection state and methods
 *
 * @example
 * // Basic usage - auto connects when matterId is provided
 * const { isConnected, subscribe } = useWebSocket(matterId);
 *
 * // Subscribe to job progress updates
 * useEffect(() => {
 *   if (!isConnected) return;
 *
 *   const unsubscribe = subscribe<WSJobProgress>('job_progress', (msg) => {
 *     console.log('Job progress:', msg.data);
 *   });
 *
 *   return unsubscribe;
 * }, [isConnected, subscribe]);
 */
export function useWebSocket(
  matterId: string | null,
  options: UseWebSocketOptions = {}
): UseWebSocketResult {
  const { enabled = true, autoConnect = true } = options;

  const [connectionState, setConnectionState] = useState<WSConnectionState>('disconnected');
  const [error, setError] = useState<string | null>(null);
  const [reconnectInfo, setReconnectInfo] = useState<WSReconnectInfo>({
    attempts: 0,
    maxAttempts: 5,
    isReconnecting: false,
  });

  // Track matter ID to detect changes
  const matterIdRef = useRef<string | null>(null);

  // Get WebSocket client
  const wsClient = getWSClient();

  /**
   * Subscribe to connection state changes
   */
  useEffect(() => {
    const unsubscribe = wsClient.onStateChange((state) => {
      setConnectionState(state);
    });

    return unsubscribe;
  }, [wsClient]);

  /**
   * Subscribe to reconnect info changes
   */
  useEffect(() => {
    let previousInfo: WSReconnectInfo | null = null;
    const isDev = process.env.NODE_ENV === 'development';

    const unsubscribe = wsClient.onReconnectChange((info) => {
      setReconnectInfo(info);

      // Log reconnection events for monitoring (NFR13) - only in development
      const logEvent = (event: string, details: Record<string, unknown> = {}) => {
        if (!isDev) return;
        console.info(`[WS] ${event}`, {
          event_type: `websocket_${event.toLowerCase().replace(/\s+/g, '_')}`,
          matter_id: matterId,
          timestamp: new Date().toISOString(),
          ...details,
        });
      };

      // Log reconnection attempt start
      if (info.isReconnecting && info.attempts > 0) {
        logEvent('reconnection_attempt', {
          attempt: info.attempts,
          max_attempts: info.maxAttempts,
        });
      }

      // Log reconnection success (was reconnecting, now not, and attempts reset)
      if (previousInfo?.isReconnecting && !info.isReconnecting && info.attempts === 0) {
        logEvent('reconnection_success', {
          previous_attempts: previousInfo.attempts,
        });
      }

      // Log max attempts reached
      if (
        previousInfo?.isReconnecting &&
        !info.isReconnecting &&
        info.attempts >= info.maxAttempts
      ) {
        logEvent('reconnection_failed', {
          attempts: info.attempts,
          reason: 'max_attempts_reached',
        });
      }

      previousInfo = { ...info };
    });

    return unsubscribe;
  }, [wsClient, matterId]);

  /**
   * Subscribe to error messages
   */
  useEffect(() => {
    const unsubscribe = wsClient.subscribe('error', (msg: WSMessage) => {
      if (msg.error) {
        setError(msg.error);
      }
    });

    return unsubscribe;
  }, [wsClient]);

  /**
   * Auto-connect when matterId changes
   */
  useEffect(() => {
    // Skip if disabled or no autoConnect
    if (!enabled || !autoConnect) return;

    // Skip if matterId hasn't changed
    if (matterIdRef.current === matterId) return;
    matterIdRef.current = matterId;

    // Disconnect if matterId is null
    if (!matterId) {
      wsClient.disconnect();
      setError(null);
      return;
    }

    // Connect to new matter
    setError(null);
    void wsClient.connect(matterId);

    // Cleanup on unmount
    return () => {
      // Don't disconnect on unmount if another component might be using the connection
      // The connection will persist and be reused by other components
    };
  }, [matterId, enabled, autoConnect, wsClient]);

  /**
   * Manual connect function
   */
  const connect = useCallback(async () => {
    if (!matterId) return;
    setError(null);
    await wsClient.connect(matterId);
  }, [matterId, wsClient]);

  /**
   * Manual disconnect function
   */
  const disconnect = useCallback(() => {
    wsClient.disconnect();
    setError(null);
  }, [wsClient]);

  /**
   * Subscribe to message type
   */
  const subscribe = useCallback(
    <T = unknown>(type: WSMessageType | 'all', callback: WSSubscriber<T>): WSUnsubscribe => {
      return wsClient.subscribe(type, callback);
    },
    [wsClient]
  );

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    isReconnecting: connectionState === 'reconnecting',
    reconnectInfo,
    error,
    subscribe,
    connect,
    disconnect,
  };
}

export default useWebSocket;
