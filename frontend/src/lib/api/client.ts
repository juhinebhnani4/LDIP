'use client'

import { createClient } from '@/lib/supabase/client'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Custom error class for API errors with structured information.
 */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * API client with automatic auth token injection and refresh.
 *
 * Features:
 * - Automatically adds Authorization header from Supabase session
 * - Retries with fresh token on 401 response
 * - Redirects to login on session expiration
 * - Handles structured API error responses
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
        throw new ApiError(
          error.error?.code || 'UNKNOWN_ERROR',
          error.error?.message || 'Request failed',
          retryResponse.status
        )
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
    throw new ApiError(
      error.error?.code || 'UNKNOWN_ERROR',
      error.error?.message || 'Request failed',
      response.status
    )
  }

  return response.json()
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
  delete: <T>(endpoint: string) => apiClient<T>(endpoint, { method: 'DELETE' }),
}



