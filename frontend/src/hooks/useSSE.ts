/**
 * useSSE Hook
 *
 * Server-Sent Events hook for streaming chat responses.
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 5: Create frontend SSE hook (AC: #1)
 *
 * Features:
 * - POST request to SSE endpoint (uses fetch, not EventSource)
 * - Bearer token authentication from Supabase session
 * - Parses SSE events from streaming response
 * - Handles connection errors and reconnection
 * - Cleanup on unmount
 *
 * USAGE PATTERN (from project-context.md):
 * const { isStreaming, startStream, abortStream } = useSSE();
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';

// ============================================================================
// Types
// ============================================================================

export type StreamEventType =
  | 'typing'
  | 'engine_start'
  | 'engine_complete'
  | 'token'
  | 'complete'
  | 'error';

export interface StreamEvent<T = unknown> {
  type: StreamEventType;
  data: T;
}

export interface EngineTraceData {
  engine: string;
  executionTimeMs: number;
  findingsCount: number;
  success: boolean;
  error?: string;
}

export interface TokenData {
  token: string;
  accumulated: string;
}

export interface SourceReferenceData {
  documentId: string;
  documentName?: string;
  page?: number;
  chunkId?: string;
  confidence?: number;
}

export interface CompleteData {
  response: string;
  sources: SourceReferenceData[];
  engineTraces: EngineTraceData[];
  totalTimeMs: number;
  confidence: number;
  messageId?: string;
}

export interface ErrorData {
  error: string;
  code: string;
  suggestedRewrite?: string;
}

interface UseSSEOptions {
  /** Called for each received event */
  onEvent?: (event: StreamEvent) => void;
  /** Called when an error occurs */
  onError?: (error: Error) => void;
  /** Called when stream completes successfully */
  onComplete?: (data: CompleteData) => void;
  /** Called when typing starts */
  onTyping?: () => void;
  /** Called for each token received */
  onToken?: (data: TokenData) => void;
  /** Called when an engine completes */
  onEngineComplete?: (data: EngineTraceData) => void;
}

interface UseSSEReturn {
  /** Whether a stream is currently active */
  isStreaming: boolean;
  /** All received events */
  events: StreamEvent[];
  /** Error if stream failed */
  error: Error | null;
  /** Start a new SSE stream */
  startStream: (url: string, body: unknown) => Promise<void>;
  /** Abort the current stream */
  abortStream: () => void;
  /** Current accumulated response text */
  accumulatedText: string;
  /** Engine traces received so far */
  engineTraces: EngineTraceData[];
}

// ============================================================================
// API Base URL
// ============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * useSSE Hook for Server-Sent Events streaming.
 *
 * Story 11.3: Task 5.1-5.6 - SSE hook implementation.
 *
 * @example
 * const {
 *   isStreaming,
 *   startStream,
 *   abortStream,
 *   accumulatedText,
 *   engineTraces,
 * } = useSSE({
 *   onToken: (data) => console.log('Token:', data.token),
 *   onComplete: (data) => console.log('Done:', data.response),
 * });
 *
 * // Start streaming
 * await startStream('/api/chat/matter-123/stream', { query: 'What is this case about?' });
 */
export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [accumulatedText, setAccumulatedText] = useState('');
  const [engineTraces, setEngineTraces] = useState<EngineTraceData[]>([]);

  const abortControllerRef = useRef<AbortController | null>(null);
  const optionsRef = useRef(options);

  // Keep options ref updated
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  /**
   * Get auth token from Supabase session.
   * Task 5.2: Implement EventSource connection with Bearer token.
   */
  const getAuthToken = useCallback(async (): Promise<string | null> => {
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      return session?.access_token ?? null;
    } catch {
      return null;
    }
  }, []);

  /**
   * Parse SSE line and extract event data.
   * Task 5.3: Parse newline-delimited JSON events.
   */
  // Note: parseSSELine kept for potential future SSE format changes
  const _parseSSELine = useCallback(
    (line: string): StreamEvent | null => {
      // Handle event type line
      if (line.startsWith('event:')) {
        // Event type is handled with data line
        return null;
      }

      // Handle data line
      if (line.startsWith('data:')) {
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) return null;

        try {
          const data = JSON.parse(jsonStr);
          // The event type should be in the previous line, but we parse it from data
          // FastAPI SSE format: event: type\ndata: {...}\n\n
          return { type: data.type || 'unknown', data };
        } catch {
          // Skip malformed JSON
          return null;
        }
      }

      return null;
    },
    []
  );

  /**
   * Process a received event.
   */
  const processEvent = useCallback(
    (eventType: StreamEventType, eventData: unknown) => {
      const event: StreamEvent = { type: eventType, data: eventData };

      setEvents((prev) => [...prev, event]);
      optionsRef.current.onEvent?.(event);

      switch (eventType) {
        case 'typing':
          optionsRef.current.onTyping?.();
          break;

        case 'engine_complete': {
          // Transform snake_case to camelCase
          const rawData = eventData as Record<string, unknown>;
          const trace: EngineTraceData = {
            engine: rawData.engine as string,
            executionTimeMs: (rawData.execution_time_ms as number) ?? 0,
            findingsCount: (rawData.findings_count as number) ?? 0,
            success: (rawData.success as boolean) ?? false,
            error: rawData.error as string | undefined,
          };
          setEngineTraces((prev) => [...prev, trace]);
          optionsRef.current.onEngineComplete?.(trace);
          break;
        }

        case 'token': {
          const rawData = eventData as Record<string, unknown>;
          const tokenData: TokenData = {
            token: (rawData.token as string) ?? '',
            accumulated: (rawData.accumulated as string) ?? '',
          };
          setAccumulatedText(tokenData.accumulated);
          optionsRef.current.onToken?.(tokenData);
          break;
        }

        case 'complete': {
          // Transform snake_case to camelCase
          const rawData = eventData as Record<string, unknown>;
          const completeData: CompleteData = {
            response: (rawData.response as string) ?? '',
            sources: ((rawData.sources as Array<Record<string, unknown>>) ?? []).map(
              (s) => ({
                documentId: (s.document_id as string) ?? '',
                documentName: s.document_name as string | undefined,
                page: s.page as number | undefined,
                chunkId: s.chunk_id as string | undefined,
                confidence: s.confidence as number | undefined,
              })
            ),
            engineTraces: (
              (rawData.engine_traces as Array<Record<string, unknown>>) ?? []
            ).map((t) => ({
              engine: (t.engine as string) ?? '',
              executionTimeMs: (t.execution_time_ms as number) ?? 0,
              findingsCount: (t.findings_count as number) ?? 0,
              success: (t.success as boolean) ?? false,
              error: t.error as string | undefined,
            })),
            totalTimeMs: (rawData.total_time_ms as number) ?? 0,
            confidence: (rawData.confidence as number) ?? 0,
            messageId: rawData.message_id as string | undefined,
          };
          optionsRef.current.onComplete?.(completeData);
          break;
        }

        case 'error': {
          const rawData = eventData as Record<string, unknown>;
          const errorData: ErrorData = {
            error: (rawData.error as string) ?? 'Unknown error',
            code: (rawData.code as string) ?? 'UNKNOWN_ERROR',
            suggestedRewrite: rawData.suggested_rewrite as string | undefined,
          };
          const err = new Error(errorData.error);
          setError(err);
          optionsRef.current.onError?.(err);
          break;
        }
      }
    },
    []
  );

  /**
   * Start SSE stream.
   * Task 5.2-5.4: Connection, parsing, and reconnection handling.
   */
  const startStream = useCallback(
    async (url: string, body: unknown) => {
      // Reset state
      setIsStreaming(true);
      setEvents([]);
      setError(null);
      setAccumulatedText('');
      setEngineTraces([]);

      // Create abort controller for cleanup
      abortControllerRef.current = new AbortController();
      const { signal } = abortControllerRef.current;

      try {
        // Get auth token
        const token = await getAuthToken();
        if (!token) {
          throw new Error('Not authenticated');
        }

        // Make POST request to SSE endpoint
        const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
        const response = await fetch(fullUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Accept: 'text/event-stream',
          },
          body: JSON.stringify(body),
          signal,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            (errorData as { error?: { message?: string } }).error?.message ||
              `HTTP ${response.status}: ${response.statusText}`
          );
        }

        // Process streaming response
        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let currentEventType: StreamEventType = 'typing';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;

            // Parse event type
            if (trimmedLine.startsWith('event:')) {
              currentEventType = trimmedLine.slice(6).trim() as StreamEventType;
              continue;
            }

            // Parse data
            if (trimmedLine.startsWith('data:')) {
              const jsonStr = trimmedLine.slice(5).trim();
              if (!jsonStr) continue;

              try {
                const data = JSON.parse(jsonStr);
                processEvent(currentEventType, data);
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          // Stream was intentionally aborted, not an error
          return;
        }
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        optionsRef.current.onError?.(error);
      } finally {
        setIsStreaming(false);
      }
    },
    [getAuthToken, processEvent]
  );

  /**
   * Abort current stream.
   * Task 5.5: Add cleanup on unmount to close connection.
   */
  const abortStream = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  return {
    isStreaming,
    events,
    error,
    startStream,
    abortStream,
    accumulatedText,
    engineTraces,
  };
}
