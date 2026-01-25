'use client'

import { createClient } from '@/lib/supabase/client'
import { getErrorMessage, isRetryableError, getErrorCodeFromStatus } from '@/lib/utils/error-messages'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Debug mode for API calls - enable to see detailed logging
const DEBUG_API = process.env.NODE_ENV === 'development'

// =============================================================================
// Epic 5: Bounded Request Handling - Configuration
// =============================================================================
// Story 5.1: Global fetch timeout (NFR1: 30 seconds maximum)
// Story 5.2: Slow request threshold for feedback
// =============================================================================

/** Default timeout for all API requests in milliseconds (NFR1: 30s max) */
export const DEFAULT_TIMEOUT_MS = 30_000

/** Threshold after which "slow request" feedback should be shown (Story 5.2) */
export const SLOW_REQUEST_THRESHOLD_MS = 5_000

// =============================================================================
// Singleton Supabase Client (Performance Fix)
// =============================================================================
// Creating a new Supabase client on every API call causes:
// 1. Extra memory allocation
// 2. Repeated auth.getSession() calls
// 3. Potential race conditions with session refresh
//
// Solution: Cache the client instance and reuse it.
// =============================================================================

let cachedSupabaseClient: ReturnType<typeof createClient> | null = null

/**
 * Get or create a singleton Supabase client for API calls.
 * This prevents creating a new client instance on every request.
 */
function getSupabaseClient(): ReturnType<typeof createClient> {
  if (!cachedSupabaseClient) {
    cachedSupabaseClient = createClient()
  }
  return cachedSupabaseClient
}

/** Rate limit details from API response */
export interface RateLimitDetails {
  /** Seconds to wait before retrying */
  retryAfter: number
  /** Current rate limit ceiling */
  limit: number
  /** Remaining requests in current window */
  remaining: number
}

// =============================================================================
// Epic 5: Timeout Error Handling
// =============================================================================

/**
 * Check if an error is a timeout/abort error.
 * Story 5.3: Helps distinguish timeout errors for user-friendly messaging.
 */
export function isTimeoutError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true
  }
  if (error instanceof ApiError && error.code === 'TIMEOUT') {
    return true
  }
  return false
}

/**
 * Custom error class for API errors with structured information.
 * Story 13.4: Enhanced with isRetryable, userMessage, and rate limit details
 */
export class ApiError extends Error {
  /** Whether this error can be retried */
  public readonly isRetryable: boolean
  /** User-friendly message suitable for display */
  public readonly userMessage: string
  /** Rate limit details (only present for 429 errors) */
  public readonly rateLimitDetails?: RateLimitDetails

  constructor(
    public code: string,
    message: string,
    public status: number,
    details?: { retryAfter?: number; limit?: number; remaining?: number }
  ) {
    super(message)
    this.name = 'ApiError'

    // Derive isRetryable and userMessage from error code
    this.isRetryable = isRetryableError(code)
    this.userMessage = getErrorMessage(code).description

    // Store rate limit details if present
    if (details?.retryAfter !== undefined) {
      this.rateLimitDetails = {
        retryAfter: details.retryAfter,
        limit: details.limit ?? 0,
        remaining: details.remaining ?? 0,
      }
    }
  }
}

/**
 * Parse error response and create ApiError with proper details.
 * Story 13.4: Enhanced error parsing for rate limits and circuit breakers
 */
function createApiError(response: Response, errorBody: Record<string, unknown>): ApiError {
  const errorData = errorBody.error as Record<string, unknown> | undefined
  const code = (errorData?.code as string) ?? getErrorCodeFromStatus(response.status)
  const message = (errorData?.message as string) ?? 'Request failed'
  const details = errorData?.details as Record<string, unknown> | undefined

  // Extract rate limit details from response
  let rateLimitDetails: { retryAfter?: number; limit?: number; remaining?: number } | undefined

  if (response.status === 429) {
    // Try Retry-After header first
    const retryAfterHeader = response.headers.get('Retry-After')
    const retryAfter = retryAfterHeader
      ? parseInt(retryAfterHeader, 10)
      : (details?.retry_after as number | undefined)

    rateLimitDetails = {
      retryAfter: retryAfter ?? 60,
      limit: (details?.limit as number | undefined) ?? 0,
      remaining: (details?.remaining as number | undefined) ?? 0,
    }
  }

  return new ApiError(code, message, response.status, rateLimitDetails)
}

/** Options for API client requests */
export interface ApiClientOptions extends Omit<RequestInit, 'signal'> {
  /**
   * Custom timeout in milliseconds. Defaults to DEFAULT_TIMEOUT_MS (30s).
   * Story 5.1: All requests have bounded wait times.
   */
  timeout?: number
  /**
   * Optional AbortSignal for external cancellation.
   * Story 5.4: Allows callers to cancel requests.
   */
  signal?: AbortSignal
  /**
   * Callback fired when request exceeds SLOW_REQUEST_THRESHOLD_MS.
   * Story 5.2: Enables "Still loading..." feedback.
   */
  onSlowRequest?: () => void
}

/**
 * API client with automatic auth token injection and refresh.
 *
 * Features:
 * - Automatically adds Authorization header from Supabase session
 * - Retries with fresh token on 401 response
 * - Redirects to login on session expiration
 * - Handles structured API error responses
 * - Story 13.4: Enhanced error handling with rate limit and circuit breaker details
 * - Story 5.1: 30-second timeout enforced on all requests (NFR1)
 * - Story 5.2: Slow request callback after 5 seconds
 * - Story 5.4: Proper request cleanup with AbortController
 */
export async function apiClient<T>(endpoint: string, options: ApiClientOptions = {}): Promise<T> {
  const {
    timeout = DEFAULT_TIMEOUT_MS,
    signal: externalSignal,
    onSlowRequest,
    ...fetchOptions
  } = options

  const supabase = getSupabaseClient()

  // Story 5.4: Create AbortController for timeout management
  // Each request has its own AbortController (FR22)
  const timeoutController = new AbortController()

  // Combine external signal with timeout signal if both provided
  const combinedSignal = externalSignal
    ? combineAbortSignals(externalSignal, timeoutController.signal)
    : timeoutController.signal

  // Story 5.1: Set up timeout (NFR1: 30s max)
  const timeoutId = setTimeout(() => {
    if (DEBUG_API) {
      console.warn(`[API] Request timeout after ${timeout}ms:`, endpoint)
    }
    timeoutController.abort()
  }, timeout)

  // Story 5.2: Set up slow request callback (>5s threshold)
  let slowRequestTimeoutId: ReturnType<typeof setTimeout> | undefined
  if (onSlowRequest) {
    slowRequestTimeoutId = setTimeout(() => {
      if (DEBUG_API) {
        console.log(`[API] Slow request detected (>${SLOW_REQUEST_THRESHOLD_MS}ms):`, endpoint)
      }
      onSlowRequest()
    }, SLOW_REQUEST_THRESHOLD_MS)
  }

  // Cleanup function for both timeouts
  const clearTimeouts = () => {
    clearTimeout(timeoutId)
    if (slowRequestTimeoutId) {
      clearTimeout(slowRequestTimeoutId)
    }
  }

  try {
    // First try getSession() - this works when cookies are accessible
    let { data: { session } } = await supabase.auth.getSession()

    // If no session from getSession(), try refreshSession() which can recover from cookies
    // This handles the case where browser storage is empty but cookies exist (incognito, new tabs)
    if (!session) {
      const { data: { session: refreshedSession } } = await supabase.auth.refreshSession()
      session = refreshedSession
    }

    if (DEBUG_API) {
      console.log(`[API] ${fetchOptions.method || 'GET'} ${endpoint}`, {
        hasSession: !!session,
        userId: session?.user?.id,
        timeout,
      })
    }

    const headers = new Headers(fetchOptions.headers)
    headers.set('Content-Type', 'application/json')

    if (session?.access_token) {
      headers.set('Authorization', `Bearer ${session.access_token}`)
    } else if (DEBUG_API) {
      console.warn('[API] No auth token available - request will be unauthenticated')
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
      signal: combinedSignal,
    })

    if (DEBUG_API) {
      console.log(`[API] Response: ${response.status} ${response.statusText}`, endpoint)
    }

    // Handle 401 - try refresh and retry once
    if (response.status === 401) {
      const {
        data: { session: newSession },
      } = await supabase.auth.refreshSession()

      if (newSession?.access_token) {
        headers.set('Authorization', `Bearer ${newSession.access_token}`)

        const retryResponse = await fetch(`${API_BASE_URL}${endpoint}`, {
          ...fetchOptions,
          headers,
          signal: combinedSignal,
        })

        if (!retryResponse.ok) {
          const error = await retryResponse.json()
          throw createApiError(retryResponse, error)
        }

        return retryResponse.json()
      }

      // Refresh failed - redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login?session_expired=true'
      }
      throw new ApiError('SESSION_EXPIRED', 'Session expired', 401)
    }

    if (!response.ok) {
      const error = await response.json()
      if (DEBUG_API) {
        console.error(`[API] Error ${response.status}:`, error, endpoint)
      }
      throw createApiError(response, error)
    }

    const data = await response.json()
    if (DEBUG_API && Array.isArray(data?.data)) {
      console.log(`[API] Received ${data.data.length} items`, endpoint)
    }
    return data
  } catch (error) {
    // Story 5.3: Convert AbortError to ApiError with TIMEOUT code
    if (error instanceof DOMException && error.name === 'AbortError') {
      // Check if it was due to external signal or our timeout
      if (externalSignal?.aborted) {
        // External cancellation - rethrow as-is
        throw error
      }
      // Our timeout triggered - throw ApiError with TIMEOUT code
      throw new ApiError('TIMEOUT', 'Request timed out', 408)
    }
    throw error
  } finally {
    // Story 5.4: Clean up timeouts (FR22)
    clearTimeouts()
  }
}

/**
 * Combine multiple AbortSignals into one.
 * Story 5.4: Allows external cancellation while maintaining timeout behavior.
 */
function combineAbortSignals(...signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController()

  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason)
      break
    }
    signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true })
  }

  return controller.signal
}

/**
 * Get a user-friendly error message from an error.
 * Story 13.4: Helper for displaying errors in UI
 *
 * @param error - The error to get a message for
 * @returns User-friendly error message
 */
export function getErrorUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    // For rate limit errors, include the countdown
    if (error.rateLimitDetails?.retryAfter) {
      return `You're making requests too quickly. Please wait ${error.rateLimitDetails.retryAfter} seconds.`
    }
    return error.userMessage
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'An unexpected error occurred. Please try again.'
}

/**
 * Check if an error is retryable.
 * Story 13.4: Helper for retry logic
 *
 * @param error - The error to check
 * @returns Whether the error can be retried
 */
export function canRetryError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.isRetryable
  }
  return false
}

/** Options for typed API methods */
export interface ApiMethodOptions {
  /** Custom timeout in milliseconds */
  timeout?: number
  /** External abort signal */
  signal?: AbortSignal
  /** Callback when request is slow (>5s) */
  onSlowRequest?: () => void
}

/**
 * Typed API methods for common operations.
 * Story 5.1: All methods now support timeout option (defaults to 30s)
 * Story 5.2: All methods support onSlowRequest callback
 * Story 5.4: All methods support external signal for cancellation
 */
export const api = {
  get: <T>(endpoint: string, options?: ApiMethodOptions) =>
    apiClient<T>(endpoint, { method: 'GET', ...options }),
  post: <T>(endpoint: string, data: unknown, options?: ApiMethodOptions) =>
    apiClient<T>(endpoint, { method: 'POST', body: JSON.stringify(data), ...options }),
  put: <T>(endpoint: string, data: unknown, options?: ApiMethodOptions) =>
    apiClient<T>(endpoint, { method: 'PUT', body: JSON.stringify(data), ...options }),
  patch: <T>(endpoint: string, data: unknown, options?: ApiMethodOptions) =>
    apiClient<T>(endpoint, { method: 'PATCH', body: JSON.stringify(data), ...options }),
  delete: <T>(endpoint: string, data?: unknown, options?: ApiMethodOptions) =>
    apiClient<T>(endpoint, {
      method: 'DELETE',
      body: data ? JSON.stringify(data) : undefined,
      ...options,
    }),
}


// =============================================================================
// Entity Alias Management API (Story 2c-2)
// =============================================================================

import type {
  AddAliasRequest,
  AliasesListResponse,
  AliasExpandedSearchRequest,
  AliasExpandedSearchResponse,
  MergeEntitiesRequest,
  MergeResultResponse,
  RemoveAliasRequest,
} from '@/types/entity'

/**
 * Entity alias management API methods.
 */
export const entityAliasApi = {
  /**
   * Get all aliases for an entity.
   */
  getAliases: (matterId: string, entityId: string) =>
    api.get<AliasesListResponse>(
      `/api/v1/matters/${matterId}/entities/${entityId}/aliases`
    ),

  /**
   * Add an alias to an entity.
   */
  addAlias: (matterId: string, entityId: string, alias: string) =>
    api.post<AliasesListResponse>(
      `/api/v1/matters/${matterId}/entities/${entityId}/aliases`,
      { alias } as AddAliasRequest
    ),

  /**
   * Remove an alias from an entity.
   */
  removeAlias: (matterId: string, entityId: string, alias: string) =>
    api.delete<AliasesListResponse>(
      `/api/v1/matters/${matterId}/entities/${entityId}/aliases`,
      { alias } as RemoveAliasRequest
    ),

  /**
   * Merge two entities (source into target).
   * Requires owner permission.
   */
  mergeEntities: (matterId: string, request: MergeEntitiesRequest) =>
    api.post<MergeResultResponse>(
      `/api/v1/matters/${matterId}/entities/merge`,
      {
        source_entity_id: request.sourceEntityId,
        target_entity_id: request.targetEntityId,
        reason: request.reason,
      }
    ),
}

/**
 * Alias-expanded search API.
 */
export const aliasSearchApi = {
  /**
   * Execute search with automatic alias expansion.
   */
  search: (matterId: string, request: AliasExpandedSearchRequest) =>
    api.post<AliasExpandedSearchResponse>(
      `/api/v1/matters/${matterId}/search/alias-expanded`,
      {
        query: request.query,
        limit: request.limit ?? 20,
        expand_aliases: request.expandAliases ?? true,
        bm25_weight: request.bm25Weight ?? 1.0,
        semantic_weight: request.semanticWeight ?? 1.0,
        rerank: request.rerank ?? false,
        rerank_top_n: request.rerankTopN ?? 3,
      }
    ),
}

// =============================================================================
// Timeline Manual Event API (Story 10B.5)
// =============================================================================

import type {
  TimelineEvent,
  ManualEventCreateRequest,
  ManualEventUpdateRequest,
  ManualEventResponse,
} from '@/types/timeline'

/**
 * Convert camelCase request to snake_case for API
 */
function toSnakeCaseManualEvent(request: ManualEventCreateRequest): Record<string, unknown> {
  return {
    event_date: request.eventDate,
    event_type: request.eventType,
    title: request.title,
    description: request.description,
    entity_ids: request.entityIds,
    source_document_id: request.sourceDocumentId ?? null,
    source_page: request.sourcePage ?? null,
  }
}

/**
 * Convert camelCase update request to snake_case for API
 */
function toSnakeCaseManualEventUpdate(
  request: ManualEventUpdateRequest
): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if (request.eventDate !== undefined) result.event_date = request.eventDate
  if (request.eventType !== undefined) result.event_type = request.eventType
  if (request.title !== undefined) result.title = request.title
  if (request.description !== undefined) result.description = request.description
  if (request.entityIds !== undefined) result.entity_ids = request.entityIds
  return result
}

/**
 * Convert API response to camelCase.
 * Handles both snake_case and camelCase responses for backward compatibility.
 */
function fromSnakeCaseManualEvent(response: Record<string, unknown>): ManualEventResponse {
  return {
    id: response.id as string,
    eventDate: (response.eventDate ?? response.event_date) as string,
    eventDatePrecision: (response.eventDatePrecision ?? response.event_date_precision) as TimelineEvent['eventDatePrecision'],
    eventDateText: ((response.eventDateText ?? response.event_date_text) as string | null) ?? null,
    eventType: (response.eventType ?? response.event_type) as TimelineEvent['eventType'],
    description: response.description as string,
    documentId: ((response.documentId ?? response.document_id) as string | null) ?? null,
    sourcePage: ((response.sourcePage ?? response.source_page) as number | null) ?? null,
    confidence: response.confidence as number,
    entities: Array.isArray(response.entities)
      ? response.entities.map((e: Record<string, unknown>) => ({
          entityId: (e.entityId ?? e.entity_id) as string,
          canonicalName: (e.canonicalName ?? e.canonical_name) as string,
          entityType: (e.entityType ?? e.entity_type) as string,
          role: ((e.role) as string | null) ?? null,
        }))
      : [],
    isAmbiguous: ((response.isAmbiguous ?? response.is_ambiguous) as boolean) ?? false,
    isVerified: ((response.isVerified ?? response.is_verified) as boolean) ?? false,
    isManual: true,
    createdBy: (response.createdBy ?? response.created_by) as string,
    createdAt: (response.createdAt ?? response.created_at) as string,
  }
}

/**
 * Timeline manual event management API methods.
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */
export const timelineEventApi = {
  /**
   * Create a new manual timeline event.
   */
  create: async (
    matterId: string,
    request: ManualEventCreateRequest
  ): Promise<ManualEventResponse> => {
    const response = await api.post<Record<string, unknown>>(
      `/api/matters/${matterId}/timeline/events`,
      toSnakeCaseManualEvent(request)
    )
    return fromSnakeCaseManualEvent(response)
  },

  /**
   * Update a timeline event.
   * For manual events: all fields can be edited.
   * For auto-extracted events: only eventType can be edited (classification correction).
   */
  update: async (
    matterId: string,
    eventId: string,
    request: ManualEventUpdateRequest
  ): Promise<ManualEventResponse> => {
    const response = await api.patch<Record<string, unknown>>(
      `/api/matters/${matterId}/timeline/events/${eventId}`,
      toSnakeCaseManualEventUpdate(request)
    )
    return fromSnakeCaseManualEvent(response)
  },

  /**
   * Delete a manual timeline event.
   * Only manual events can be deleted.
   */
  delete: async (matterId: string, eventId: string): Promise<void> => {
    await api.delete<void>(`/api/matters/${matterId}/timeline/events/${eventId}`)
  },

  /**
   * Verify or unverify a timeline event.
   */
  setVerified: async (
    matterId: string,
    eventId: string,
    isVerified: boolean
  ): Promise<ManualEventResponse> => {
    const response = await api.patch<Record<string, unknown>>(
      `/api/matters/${matterId}/timeline/events/${eventId}/verify`,
      { is_verified: isVerified }
    )
    return fromSnakeCaseManualEvent(response)
  },
}


// =============================================================================
// Story 6.2: SSE Error Reporting API
// =============================================================================

/**
 * SSE error context for backend reporting.
 */
export interface SSEErrorReport {
  sessionId: string
  matterId?: string
  errorType: string
  errorMessage: string
  rawChunk?: string
  timestamp: string
}

/**
 * SSE stream status for backend reporting.
 */
export interface SSEStreamStatusReport {
  sessionId: string
  matterId?: string
  status: 'complete' | 'interrupted'
  parseErrorCount: number
  totalChunks: number
  durationMs?: number
}

/**
 * SSE error and status reporting API.
 * Story 6.2: Add SSE Error Rate Logging
 */
export const sseReportingApi = {
  /**
   * Report an SSE parse error to the backend for monitoring.
   * NFR12: SSE parse errors trackable per user session.
   */
  reportError: async (report: SSEErrorReport): Promise<void> => {
    try {
      await api.post('/api/chat/report-sse-error', {
        session_id: report.sessionId,
        matter_id: report.matterId,
        error_type: report.errorType,
        error_message: report.errorMessage,
        raw_chunk: report.rawChunk,
        timestamp: report.timestamp,
      })
    } catch (error) {
      // Don't throw - error reporting should be fire-and-forget
      if (DEBUG_API) {
        console.warn('[API] Failed to report SSE error:', error)
      }
    }
  },

  /**
   * Report SSE stream completion status to the backend.
   */
  reportStatus: async (report: SSEStreamStatusReport): Promise<void> => {
    try {
      await api.post('/api/chat/report-sse-status', {
        session_id: report.sessionId,
        matter_id: report.matterId,
        status: report.status,
        parse_error_count: report.parseErrorCount,
        total_chunks: report.totalChunks,
        duration_ms: report.durationMs,
      })
    } catch (error) {
      // Don't throw - status reporting should be fire-and-forget
      if (DEBUG_API) {
        console.warn('[API] Failed to report SSE status:', error)
      }
    }
  },
}
