/**
 * WebSocket Client for Real-Time Updates
 *
 * Singleton WebSocket client that connects to the backend WebSocket endpoint
 * and routes messages to subscribers. Replaces polling for real-time updates.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - JWT authentication via query parameter
 * - Message type routing to subscribers
 * - Heartbeat ping/pong for connection health
 */

'use client';

import { createClient } from '@/lib/supabase/client';

// =============================================================================
// Types
// =============================================================================

/** WebSocket message types from server */
export type WSMessageType =
  | 'document_status'
  | 'job_progress'
  | 'citation_update'
  | 'feature_ready'
  | 'discovery_update'
  | 'pong'
  | 'error'
  | 'unknown';

/** Message from WebSocket server */
export interface WSMessage<T = unknown> {
  type: WSMessageType;
  channel?: string;
  data?: T;
  timestamp?: string;
  error?: string;
}

/** Job progress data from WebSocket */
export interface WSJobProgress {
  job_id: string;
  document_id?: string;
  status: string;
  stage?: string;
  progress_pct: number;
  message?: string;
  timestamp: string;
}

/** Document status data from WebSocket */
export interface WSDocumentStatus {
  document_id: string;
  status: string;
  processing_stage?: string;
  error_message?: string;
  timestamp: string;
}

/** Feature ready data from WebSocket */
export interface WSFeatureReady {
  document_id: string;
  feature: string;
  ready: boolean;
  count?: number;
  timestamp: string;
}

/** Citation update data from WebSocket */
export interface WSCitationUpdate {
  document_id: string;
  count: number;
  validated_count?: number;
  timestamp: string;
}

/** Entity discovery data from WebSocket */
export interface WSEntityDiscovery {
  event: 'entity_discovery';
  matter_id: string;
  total_entities: number;
  entity_counts?: Record<string, number>;
  new_entities?: Array<{ canonical_name: string; entity_type: string }>;
  timestamp: string;
}

/** Entity stream data for progressive rendering (individual entities) */
export interface WSEntityStream {
  event: 'entity_stream';
  matter_id: string;
  entity: {
    name: string;
    type: string;
  };
  current_count: number;
  document_id?: string;
  timestamp: string;
}

/** Timeline discovery data from WebSocket */
export interface WSTimelineDiscovery {
  event: 'timeline_discovery';
  matter_id: string;
  total_events: number;
  date_range_start?: string;
  date_range_end?: string;
  events_by_type?: Record<string, number>;
  timestamp: string;
}

/** Discovery update (union of entity, entity stream, and timeline discoveries) */
export type WSDiscoveryUpdate = WSEntityDiscovery | WSEntityStream | WSTimelineDiscovery;

/** Connection state */
export type WSConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

/** Subscription callback */
export type WSSubscriber<T = unknown> = (message: WSMessage<T>) => void;

/** Unsubscribe function */
export type WSUnsubscribe = () => void;

// =============================================================================
// Configuration
// =============================================================================

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL ||
  (process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws') || 'ws://localhost:8000');

/** Reconnection settings */
const RECONNECT_MIN_DELAY = 1000; // 1 second
const RECONNECT_MAX_DELAY = 30000; // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10;
const RECONNECT_BACKOFF_MULTIPLIER = 1.5;

/** Heartbeat settings */
const HEARTBEAT_INTERVAL = 30000; // 30 seconds

/** Debug mode */
const DEBUG_WS = process.env.NODE_ENV === 'development';

// =============================================================================
// WebSocket Client Class
// =============================================================================

class WebSocketClient {
  private ws: WebSocket | null = null;
  private matterId: string | null = null;
  private connectionState: WSConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private subscribers: Map<WSMessageType | 'all', Set<WSSubscriber>> = new Map();
  private stateListeners: Set<(state: WSConnectionState) => void> = new Set();

  /**
   * Connect to WebSocket for a specific matter.
   * Will disconnect from any existing connection first.
   */
  async connect(matterId: string): Promise<void> {
    // Already connected to this matter
    if (this.matterId === matterId && this.connectionState === 'connected') {
      if (DEBUG_WS) console.log('[WS] Already connected to matter:', matterId);
      return;
    }

    // Disconnect from previous matter
    if (this.ws) {
      this.disconnect();
    }

    this.matterId = matterId;
    await this.establishConnection();
  }

  /**
   * Disconnect from WebSocket.
   */
  disconnect(): void {
    this.cleanupConnection();
    this.matterId = null;
    this.reconnectAttempts = 0;
    this.setConnectionState('disconnected');
    if (DEBUG_WS) console.log('[WS] Disconnected');
  }

  /**
   * Subscribe to messages of a specific type.
   * Returns unsubscribe function.
   */
  subscribe<T = unknown>(type: WSMessageType | 'all', callback: WSSubscriber<T>): WSUnsubscribe {
    if (!this.subscribers.has(type)) {
      this.subscribers.set(type, new Set());
    }
    this.subscribers.get(type)!.add(callback as WSSubscriber);

    return () => {
      this.subscribers.get(type)?.delete(callback as WSSubscriber);
    };
  }

  /**
   * Listen for connection state changes.
   */
  onStateChange(callback: (state: WSConnectionState) => void): WSUnsubscribe {
    this.stateListeners.add(callback);
    // Immediately call with current state
    callback(this.connectionState);
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  /**
   * Get current connection state.
   */
  getConnectionState(): WSConnectionState {
    return this.connectionState;
  }

  /**
   * Get current matter ID.
   */
  getMatterId(): string | null {
    return this.matterId;
  }

  /**
   * Check if connected to a specific matter.
   */
  isConnectedTo(matterId: string): boolean {
    return this.matterId === matterId && this.connectionState === 'connected';
  }

  // ===========================================================================
  // Private Methods
  // ===========================================================================

  private async establishConnection(): Promise<void> {
    if (!this.matterId) return;

    this.setConnectionState('connecting');

    try {
      // Get auth token from Supabase
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();

      if (!session?.access_token) {
        if (DEBUG_WS) console.warn('[WS] No auth token available');
        this.setConnectionState('disconnected');
        return;
      }

      // Build WebSocket URL
      const wsUrl = `${WS_BASE_URL}/api/ws/${this.matterId}?token=${encodeURIComponent(session.access_token)}`;

      if (DEBUG_WS) console.log('[WS] Connecting to:', wsUrl.replace(/token=.*/, 'token=<redacted>'));

      this.ws = new WebSocket(wsUrl);
      this.setupEventHandlers();

    } catch (error) {
      if (DEBUG_WS) console.error('[WS] Connection error:', error);
      this.scheduleReconnect();
    }
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      if (DEBUG_WS) console.log('[WS] Connected');
      this.reconnectAttempts = 0;
      this.setConnectionState('connected');
      this.startHeartbeat();
    };

    this.ws.onclose = (event) => {
      if (DEBUG_WS) {
        console.log('[WS] Closed:', event.code, event.reason);
      }
      this.cleanupConnection();

      // Don't reconnect for auth errors (4001, 4003)
      if (event.code >= 4001 && event.code <= 4010) {
        if (DEBUG_WS) console.log('[WS] Auth error, not reconnecting');
        this.setConnectionState('disconnected');
        this.notifyError(`WebSocket auth failed: ${event.reason || 'Unknown error'}`);
        return;
      }

      // Schedule reconnect for other disconnections
      if (this.matterId) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      if (DEBUG_WS) console.error('[WS] Error:', error);
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSMessage;

        if (DEBUG_WS && message.type !== 'pong') {
          console.log('[WS] Message:', message.type, message);
        }

        // Handle pong (heartbeat response)
        if (message.type === 'pong') {
          return;
        }

        // Route to type-specific subscribers
        this.notifySubscribers(message.type, message);

        // Route to 'all' subscribers
        this.notifySubscribers('all', message);

      } catch (error) {
        if (DEBUG_WS) console.error('[WS] Parse error:', error);
      }
    };
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private cleanupConnection(): void {
    this.stopHeartbeat();

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;

      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
      if (DEBUG_WS) console.log('[WS] Max reconnect attempts reached');
      this.setConnectionState('disconnected');
      this.notifyError('WebSocket connection failed after multiple attempts');
      return;
    }

    // Exponential backoff
    const delay = Math.min(
      RECONNECT_MIN_DELAY * Math.pow(RECONNECT_BACKOFF_MULTIPLIER, this.reconnectAttempts),
      RECONNECT_MAX_DELAY
    );

    this.reconnectAttempts++;
    this.setConnectionState('reconnecting');

    if (DEBUG_WS) {
      console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${RECONNECT_MAX_ATTEMPTS})`);
    }

    this.reconnectTimeout = setTimeout(() => {
      if (this.matterId) {
        void this.establishConnection();
      }
    }, delay);
  }

  private setConnectionState(state: WSConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.stateListeners.forEach((listener) => listener(state));
    }
  }

  private notifySubscribers(type: WSMessageType | 'all', message: WSMessage): void {
    this.subscribers.get(type)?.forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        if (DEBUG_WS) console.error('[WS] Subscriber error:', error);
      }
    });
  }

  private notifyError(errorMessage: string): void {
    const errorMsg: WSMessage = {
      type: 'error',
      error: errorMessage,
      timestamp: new Date().toISOString(),
    };
    this.notifySubscribers('error', errorMsg);
    this.notifySubscribers('all', errorMsg);
  }
}

// =============================================================================
// Singleton Export
// =============================================================================

/** Singleton WebSocket client instance */
let wsClient: WebSocketClient | null = null;

/**
 * Get the singleton WebSocket client.
 * Creates one if it doesn't exist.
 */
export function getWSClient(): WebSocketClient {
  if (!wsClient) {
    wsClient = new WebSocketClient();
  }
  return wsClient;
}

/**
 * Connect to WebSocket for a matter.
 * Convenience function that uses singleton client.
 */
export async function connectWS(matterId: string): Promise<void> {
  return getWSClient().connect(matterId);
}

/**
 * Disconnect from WebSocket.
 * Convenience function that uses singleton client.
 */
export function disconnectWS(): void {
  getWSClient().disconnect();
}

/**
 * Subscribe to WebSocket messages.
 * Convenience function that uses singleton client.
 */
export function subscribeWS<T = unknown>(
  type: WSMessageType | 'all',
  callback: WSSubscriber<T>
): WSUnsubscribe {
  return getWSClient().subscribe(type, callback);
}

export default WebSocketClient;
