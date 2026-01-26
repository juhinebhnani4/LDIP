/**
 * useSSE Hook
 *
 * Server-Sent Events hook for streaming chat responses.
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 5: Create frontend SSE hook (AC: #1)
 *
 * Story 6.2: SSE Error Rate Logging - added backend error reporting
 *
 * Features:
 * - POST request to SSE endpoint (uses fetch, not EventSource)
 * - Bearer token authentication from Supabase session
 * - Parses SSE events from streaming response
 * - Handles connection errors and reconnection
 * - Cleanup on unmount
 * - Reports parse errors to backend for monitoring (Story 6.2)
 *
 * USAGE PATTERN (from project-context.md):
 * const { isStreaming, startStream, abortStream } = useSSE();
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { sseReportingApi } from '@/lib/api/client';

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

/**
 * F9: SSE error types as union for extensibility.
 */
export type SSEErrorType = 'sse_json_parse_failed' | 'sse_max_errors_exceeded';

/**
 * Story 2.4: SSE parse error context for logging.
 * Includes all relevant identifiers for debugging and monitoring.
 */
export interface SSEParseErrorContext {
  /** User ID from auth session */
  userId?: string;
  /** Matter ID extracted from stream URL */
  matterId?: string;
  /** Session ID (generated per stream) */
  sessionId: string;
  /** Timestamp of error */
  timestamp: string;
  /** F9: Type of error - union type for extensibility */
  errorType: SSEErrorType;
  /** Raw chunk content (truncated to 1KB) */
  rawChunk: string;
  /** Original error message */
  errorMessage: string;
}

// F10: Maximum parse errors before aborting stream
const MAX_PARSE_ERRORS = 5;

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
  bboxIds?: string[];
}

export interface CompleteData {
  response: string;
  sources: SourceReferenceData[];
  engineTraces: EngineTraceData[];
  totalTimeMs: number;
  confidence: number;
  messageId?: string;
  // Optimistic RAG metadata
  searchMode?: 'hybrid' | 'bm25_only' | 'bm25_fallback';
  embeddingCompletionPct?: number;
  searchNotice?: string;
  // Response completeness indicators
  truncated?: boolean;
  moreAvailable?: boolean;
  totalResultsHint?: number;
  // Query safety rewrite metadata
  queryWasRewritten?: boolean;
  originalQuery?: string;
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
  /**
   * Story 2.1/2.2: Called when SSE JSON parsing fails.
   * Use this to show toast notifications to the user.
   */
  onParseError?: (context: SSEParseErrorContext) => void;
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
  /** Story 2.1: Count of JSON parse errors in current stream */
  parseErrorCount: number;
  /** Story 2.3: Whether stream was interrupted (error or abort with content) */
  wasInterrupted: boolean;
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
  // Story 2.1: Track parse errors
  const [parseErrorCount, setParseErrorCount] = useState(0);
  // Story 2.3: Track if stream was interrupted
  const [wasInterrupted, setWasInterrupted] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const optionsRef = useRef(options);
  // Story 2.4: Track session ID and user ID for logging context
  const sessionIdRef = useRef<string>('');
  const userIdRef = useRef<string | undefined>(undefined);
  // Story 6.2: Track stream metrics for accurate reporting
  const streamStartTimeRef = useRef<number>(0);
  const eventCountRef = useRef<number>(0);

  // Keep options ref updated
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

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
          // Transform API response to camelCase (handles both snake_case and camelCase)
          const rawData = eventData as Record<string, unknown>;
          // DEBUG: Log raw source data to trace document_name flow
          if (process.env.NODE_ENV === 'development') {
            console.log('[useSSE] complete event raw sources:', rawData.sources);
          }
          const completeData: CompleteData = {
            response: (rawData.response as string) ?? '',
            sources: ((rawData.sources as Array<Record<string, unknown>>) ?? []).map(
              (s) => {
                const docName = (s.documentName ?? s.document_name) as string | undefined;
                // DEBUG: Log each source's document_name
                if (process.env.NODE_ENV === 'development') {
                  console.log('[useSSE] source transform:', {
                    raw_documentName: s.documentName,
                    raw_document_name: s.document_name,
                    resolved: docName,
                  });
                }
                return {
                  documentId: ((s.documentId ?? s.document_id) as string) ?? '',
                  documentName: docName,
                  page: s.page as number | undefined,
                  chunkId: (s.chunkId ?? s.chunk_id) as string | undefined,
                  confidence: s.confidence as number | undefined,
                  bboxIds: (s.bboxIds ?? s.bbox_ids) as string[] | undefined,
                };
              }
            ),
            engineTraces: (
              ((rawData.engineTraces ?? rawData.engine_traces) as Array<Record<string, unknown>>) ?? []
            ).map((t) => ({
              engine: (t.engine as string) ?? '',
              executionTimeMs: ((t.executionTimeMs ?? t.execution_time_ms) as number) ?? 0,
              findingsCount: ((t.findingsCount ?? t.findings_count) as number) ?? 0,
              success: (t.success as boolean) ?? false,
              error: t.error as string | undefined,
            })),
            totalTimeMs: ((rawData.totalTimeMs ?? rawData.total_time_ms) as number) ?? 0,
            confidence: (rawData.confidence as number) ?? 0,
            messageId: (rawData.messageId ?? rawData.message_id) as string | undefined,
            // Optimistic RAG metadata
            searchMode: (rawData.searchMode ?? rawData.search_mode) as CompleteData['searchMode'],
            embeddingCompletionPct: (rawData.embeddingCompletionPct ?? rawData.embedding_completion_pct) as number | undefined,
            searchNotice: (rawData.searchNotice ?? rawData.search_notice) as string | undefined,
            // Response completeness indicators
            truncated: (rawData.truncated as boolean) ?? false,
            moreAvailable: (rawData.moreAvailable ?? rawData.more_available) as boolean | undefined,
            totalResultsHint: (rawData.totalResultsHint ?? rawData.total_results_hint) as number | undefined,
            // Query safety rewrite metadata
            queryWasRewritten: (rawData.queryWasRewritten ?? rawData.query_was_rewritten) as boolean | undefined,
            originalQuery: (rawData.originalQuery ?? rawData.original_query) as string | undefined,
          };
          optionsRef.current.onComplete?.(completeData);
          break;
        }

        case 'error': {
          // Transform API response to camelCase (handles both snake_case and camelCase)
          const rawData = eventData as Record<string, unknown>;
          const errorData: ErrorData = {
            error: (rawData.error as string) ?? 'Unknown error',
            code: (rawData.code as string) ?? 'UNKNOWN_ERROR',
            suggestedRewrite: (rawData.suggestedRewrite ?? rawData.suggested_rewrite) as string | undefined,
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
   * Story 2.1/2.4: Enhanced with parse error handling and logging.
   */
  const startStream = useCallback(
    async (url: string, body: unknown) => {
      // F8: Use crypto.randomUUID for guaranteed unique session ID
      sessionIdRef.current = `sse_${crypto.randomUUID()}`;

      // Story 2.4: Extract matter ID from URL (pattern: /api/chat/{matterId}/stream)
      const matterIdMatch = url.match(/\/api\/chat\/([^/]+)\/stream/);
      const matterId = matterIdMatch?.[1];

      // Reset state
      setIsStreaming(true);
      setEvents([]);
      setError(null);
      setAccumulatedText('');
      setEngineTraces([]);
      setParseErrorCount(0);
      setWasInterrupted(false);
      // Story 6.2: Reset stream metrics
      streamStartTimeRef.current = Date.now();
      eventCountRef.current = 0;

      // Create abort controller for cleanup
      abortControllerRef.current = new AbortController();
      const { signal } = abortControllerRef.current;

      // Track if we received a complete event
      let receivedComplete = false;
      // Track local parse error count for this stream
      let localParseErrorCount = 0;

      try {
        // Get auth token and user ID
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token;
        userIdRef.current = session?.user?.id;

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
                // Story 6.2: Track event count for accurate reporting
                eventCountRef.current++;
                // Track if we received a complete event
                if (currentEventType === 'complete') {
                  receivedComplete = true;
                }
              } catch (parseError) {
                // Story 2.1: Log malformed JSON with context
                localParseErrorCount++;
                setParseErrorCount(localParseErrorCount);

                // Story 2.4: Create error context for logging
                const errorContext: SSEParseErrorContext = {
                  userId: userIdRef.current,
                  matterId,
                  sessionId: sessionIdRef.current,
                  timestamp: new Date().toISOString(),
                  errorType: 'sse_json_parse_failed',
                  // Truncate raw chunk to 1KB max
                  rawChunk: jsonStr.length > 1024 ? jsonStr.substring(0, 1024) + '...' : jsonStr,
                  errorMessage: parseError instanceof Error ? parseError.message : String(parseError),
                };

                // F7: Only log to console in development
                if (process.env.NODE_ENV === 'development') {
                  console.error('[useSSE] JSON parse error:', errorContext);
                }

                // Story 2.2: Call onParseError callback for toast notification
                optionsRef.current.onParseError?.(errorContext);

                // Story 6.2: Report error to backend for monitoring (fire-and-forget)
                void sseReportingApi.reportError({
                  sessionId: sessionIdRef.current,
                  matterId,
                  errorType: 'sse_json_parse_failed',
                  errorMessage: errorContext.errorMessage,
                  rawChunk: errorContext.rawChunk,
                  timestamp: errorContext.timestamp,
                });

                // F10: Abort stream if too many parse errors
                if (localParseErrorCount >= MAX_PARSE_ERRORS) {
                  const maxErrorContext: SSEParseErrorContext = {
                    ...errorContext,
                    errorType: 'sse_max_errors_exceeded',
                    errorMessage: `Aborted after ${MAX_PARSE_ERRORS} parse errors`,
                  };
                  if (process.env.NODE_ENV === 'development') {
                    console.error('[useSSE] Max parse errors reached, aborting:', maxErrorContext);
                  }
                  optionsRef.current.onParseError?.(maxErrorContext);

                  // Story 6.2: Report max errors exceeded to backend
                  void sseReportingApi.reportError({
                    sessionId: sessionIdRef.current,
                    matterId,
                    errorType: 'sse_max_errors_exceeded',
                    errorMessage: maxErrorContext.errorMessage,
                    rawChunk: errorContext.rawChunk,
                    timestamp: new Date().toISOString(),
                  });

                  abortControllerRef.current?.abort();
                  setWasInterrupted(true);
                  return;
                }
              }
            }
          }
        }

        // Story 2.3: Check if stream ended without complete event
        // Story 6.2: Calculate stream duration for reporting
        const streamDurationMs = Date.now() - streamStartTimeRef.current;
        if (!receivedComplete && localParseErrorCount > 0) {
          setWasInterrupted(true);
          // Story 6.2: Report interrupted stream
          void sseReportingApi.reportStatus({
            sessionId: sessionIdRef.current,
            matterId,
            status: 'interrupted',
            parseErrorCount: localParseErrorCount,
            totalChunks: eventCountRef.current,
            durationMs: streamDurationMs,
          });
        } else if (receivedComplete) {
          // Story 6.2: Report successful stream completion
          void sseReportingApi.reportStatus({
            sessionId: sessionIdRef.current,
            matterId,
            status: 'complete',
            parseErrorCount: localParseErrorCount,
            totalChunks: eventCountRef.current,
            durationMs: streamDurationMs,
          });
        }
      } catch (err) {
        // Story 6.2: Calculate stream duration for error reporting
        const errorDurationMs = Date.now() - streamStartTimeRef.current;
        if (err instanceof Error && err.name === 'AbortError') {
          // Story 2.3: Mark as interrupted if we had content
          setWasInterrupted(true);
          // Story 6.2: Report aborted stream
          void sseReportingApi.reportStatus({
            sessionId: sessionIdRef.current,
            matterId,
            status: 'interrupted',
            parseErrorCount: localParseErrorCount,
            totalChunks: eventCountRef.current,
            durationMs: errorDurationMs,
          });
          return;
        }
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        setWasInterrupted(true);
        optionsRef.current.onError?.(error);
        // Story 6.2: Report error-interrupted stream
        void sseReportingApi.reportStatus({
          sessionId: sessionIdRef.current,
          matterId,
          status: 'interrupted',
          parseErrorCount: localParseErrorCount,
          totalChunks: eventCountRef.current,
          durationMs: errorDurationMs,
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [processEvent]
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
    parseErrorCount,
    wasInterrupted,
  };
}
