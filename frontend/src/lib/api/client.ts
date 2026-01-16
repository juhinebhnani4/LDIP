'use client'

import { createClient } from '@/lib/supabase/client'
import { getErrorMessage, isRetryableError, getErrorCodeFromStatus } from '@/lib/utils/error-messages'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** Rate limit details from API response */
export interface RateLimitDetails {
  /** Seconds to wait before retrying */
  retryAfter: number
  /** Current rate limit ceiling */
  limit: number
  /** Remaining requests in current window */
  remaining: number
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

/**
 * API client with automatic auth token injection and refresh.
 *
 * Features:
 * - Automatically adds Authorization header from Supabase session
 * - Retries with fresh token on 401 response
 * - Redirects to login on session expiration
 * - Handles structured API error responses
 * - Story 13.4: Enhanced error handling with rate limit and circuit breaker details
 */
export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const supabase = createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()

  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')

  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  // Handle 401 - try refresh and retry once
  if (response.status === 401 && session) {
    const {
      data: { session: newSession },
    } = await supabase.auth.refreshSession()

    if (newSession?.access_token) {
      headers.set('Authorization', `Bearer ${newSession.access_token}`)

      const retryResponse = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
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
    throw createApiError(response, error)
  }

  return response.json()
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

/**
 * Typed API methods for common operations.
 */
export const api = {
  get: <T>(endpoint: string) => apiClient<T>(endpoint, { method: 'GET' }),
  post: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, { method: 'POST', body: JSON.stringify(data) }),
  put: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, { method: 'PUT', body: JSON.stringify(data) }),
  patch: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: <T>(endpoint: string, data?: unknown) =>
    apiClient<T>(endpoint, {
      method: 'DELETE',
      body: data ? JSON.stringify(data) : undefined,
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
 * Convert snake_case response to camelCase
 */
function fromSnakeCaseManualEvent(response: Record<string, unknown>): ManualEventResponse {
  return {
    id: response.id as string,
    eventDate: response.event_date as string,
    eventDatePrecision: response.event_date_precision as TimelineEvent['eventDatePrecision'],
    eventDateText: (response.event_date_text as string | null) ?? null,
    eventType: response.event_type as TimelineEvent['eventType'],
    description: response.description as string,
    documentId: (response.document_id as string | null) ?? null,
    sourcePage: (response.source_page as number | null) ?? null,
    confidence: response.confidence as number,
    entities: Array.isArray(response.entities)
      ? response.entities.map((e: Record<string, unknown>) => ({
          entityId: e.entity_id as string,
          canonicalName: e.canonical_name as string,
          entityType: e.entity_type as string,
          role: (e.role as string | null) ?? null,
        }))
      : [],
    isAmbiguous: (response.is_ambiguous as boolean) ?? false,
    isVerified: (response.is_verified as boolean) ?? false,
    isManual: true,
    createdBy: response.created_by as string,
    createdAt: response.created_at as string,
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
