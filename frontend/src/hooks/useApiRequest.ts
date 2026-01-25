'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  ApiError,
  isTimeoutError,
  getErrorUserMessage,
  canRetryError,
  type ApiMethodOptions,
} from '@/lib/api/client'

/**
 * Epic 5: Bounded Request Handling
 *
 * Hook for making API requests with automatic timeout handling,
 * slow request feedback, and retry capability.
 *
 * Story 5.2: Display slow request feedback (>5s indicator)
 * Story 5.3: Display timeout error message with retry option
 * Story 5.4: Proper request cleanup on timeout
 */

// =============================================================================
// F6: Toast Duration Constants
// =============================================================================

/** Duration for error toasts with retry action (10 seconds as per AC) */
const ERROR_TOAST_WITH_RETRY_DURATION_MS = 10_000

/** Duration for non-retryable error toasts */
const ERROR_TOAST_DURATION_MS = 5_000

// =============================================================================
// Types
// =============================================================================

/** Result of an API request */
export interface ApiRequestResult<T> {
  data: T | null
  error: ApiError | Error | null
  isLoading: boolean
  isSlowRequest: boolean
}

/** Options for useApiRequest hook */
export interface UseApiRequestOptions {
  /** Whether to show toast notifications. Defaults to true. */
  showToasts?: boolean
  /** Custom timeout in milliseconds. Defaults to 30s (from apiClient). */
  timeout?: number
  /** Auto-dismiss slow request toast when request completes. Defaults to true. */
  autoDismissSlowToast?: boolean
}

/** Return type for useApiRequest hook */
export interface UseApiRequestReturn<T> {
  /**
   * Execute the request with timeout and slow request handling.
   *
   * F7: Return behavior documentation:
   * - Returns the data on success
   * - Returns `null` on error (check `result.error` for details)
   * - The request function should use api.get/post/etc with the options
   *   from this hook for proper timeout/cancellation integration
   *
   * @param requestFn - Async function that performs the API call
   * @returns The response data, or null if an error occurred
   */
  execute: (requestFn: () => Promise<T>) => Promise<T | null>
  /** Current request state */
  result: ApiRequestResult<T>
  /** Cancel the current request */
  cancel: () => void
  /** Retry the last failed request */
  retry: () => Promise<T | null>
  /**
   * Reset state and clear the stored request function.
   * F11: This clears lastRequestFnRef, releasing any closures it holds.
   * Call this when the component no longer needs the retry capability.
   */
  reset: () => void
  /**
   * API options to pass to api.get/post/etc for proper integration.
   * Includes timeout and onSlowRequest callback.
   * Note: Signal is managed internally by execute() - do not pass external signals.
   */
  apiOptions: Omit<ApiMethodOptions, 'signal'>
}

/**
 * Hook for making API requests with bounded wait times and user feedback.
 *
 * Features:
 * - Story 5.2: Shows "Still loading..." toast after 5 seconds
 * - Story 5.3: Shows timeout error toast with retry action
 * - Story 5.4: Proper cleanup with AbortController
 * - F1: Automatically aborts in-flight requests on unmount
 * - F4: Prevents state updates after abort/unmount
 *
 * @example
 * ```tsx
 * const { execute, result, apiOptions } = useApiRequest<MatterData>();
 *
 * const handleFetch = async () => {
 *   // F3: Pass apiOptions to integrate timeout/cancel/slow request
 *   const data = await execute(() => api.get('/api/matters/123', apiOptions));
 *   if (data) {
 *     // Handle success
 *   }
 * };
 * ```
 */
export function useApiRequest<T>(
  options: UseApiRequestOptions = {}
): UseApiRequestReturn<T> {
  const { showToasts = true, timeout, autoDismissSlowToast = true } = options

  const [result, setResult] = useState<ApiRequestResult<T>>({
    data: null,
    error: null,
    isLoading: false,
    isSlowRequest: false,
  })

  // Store the last request function for retry
  // F11: This ref holds a closure - call reset() to release it when done
  const lastRequestFnRef = useRef<(() => Promise<T>) | null>(null)
  // AbortController for current request
  const abortControllerRef = useRef<AbortController | null>(null)
  // Toast ID for slow request (to dismiss it)
  const slowToastIdRef = useRef<string | number | null>(null)
  // F14: Use ref with stable identity for retry to avoid race conditions
  const retryRef = useRef<() => Promise<T | null>>(() => Promise.resolve(null))
  // F4: Track if component is mounted to prevent state updates after unmount
  const isMountedRef = useRef(true)

  // F1: Cleanup on unmount - abort any in-flight request
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      // Abort any in-flight request when component unmounts
      abortControllerRef.current?.abort()
      // Dismiss any lingering slow toast
      if (slowToastIdRef.current !== null) {
        toast.dismiss(slowToastIdRef.current)
      }
    }
  }, [])

  /**
   * Dismiss slow request toast
   */
  const dismissSlowToast = useCallback(() => {
    if (slowToastIdRef.current !== null) {
      toast.dismiss(slowToastIdRef.current)
      slowToastIdRef.current = null
    }
  }, [])

  /**
   * F2: Show slow request toast and update state
   */
  const handleSlowRequest = useCallback(() => {
    // F4: Don't update state if unmounted or aborted
    if (!isMountedRef.current || abortControllerRef.current?.signal.aborted) {
      return
    }

    setResult((prev) => ({ ...prev, isSlowRequest: true }))

    if (showToasts) {
      slowToastIdRef.current = toast.loading('Still loading...', {
        description: 'The request is taking longer than expected.',
        duration: Infinity,
      })
    }
  }, [showToasts])

  /**
   * Cancel the current request (Story 5.4)
   */
  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    dismissSlowToast()
    // F4: Only update state if mounted
    if (isMountedRef.current) {
      setResult((prev) => ({
        ...prev,
        isLoading: false,
        isSlowRequest: false,
      }))
    }
  }, [dismissSlowToast])

  /**
   * Reset state and clear stored request function.
   * F11: Call this to release closures held by lastRequestFnRef.
   */
  const reset = useCallback(() => {
    cancel()
    if (isMountedRef.current) {
      setResult({
        data: null,
        error: null,
        isLoading: false,
        isSlowRequest: false,
      })
    }
    lastRequestFnRef.current = null
  }, [cancel])

  /**
   * Execute the request with timeout and slow request handling.
   * F7: Returns data on success, null on error. Check result.error for details.
   */
  const execute = useCallback(
    async (requestFn: () => Promise<T>): Promise<T | null> => {
      // Store for retry
      lastRequestFnRef.current = requestFn

      // Cancel any existing request
      abortControllerRef.current?.abort()

      // Create new AbortController for this request
      const controller = new AbortController()
      abortControllerRef.current = controller

      // F4: Only update state if mounted
      if (isMountedRef.current) {
        setResult({
          data: null,
          error: null,
          isLoading: true,
          isSlowRequest: false,
        })
      }

      try {
        const data = await requestFn()

        // F4: Check if aborted or unmounted before updating state
        if (controller.signal.aborted || !isMountedRef.current) {
          return null
        }

        // Story 5.2: Dismiss slow toast on success
        if (autoDismissSlowToast) {
          dismissSlowToast()
        }

        setResult({
          data,
          error: null,
          isLoading: false,
          isSlowRequest: false,
        })

        return data
      } catch (error) {
        // F4: Check if aborted or unmounted before updating state
        if (controller.signal.aborted || !isMountedRef.current) {
          return null
        }

        // Dismiss slow toast on error too
        if (autoDismissSlowToast) {
          dismissSlowToast()
        }

        const apiError =
          error instanceof ApiError || error instanceof Error
            ? error
            : new Error(String(error))

        setResult({
          data: null,
          error: apiError,
          isLoading: false,
          isSlowRequest: false,
        })

        // Story 5.3: Show appropriate error toast
        if (showToasts) {
          if (isTimeoutError(error)) {
            // Story 5.3: Timeout-specific error with retry (NFR3: appear within 500ms)
            toast.error('Request timed out', {
              description: 'The server took too long to respond. Please try again.',
              action: {
                label: 'Retry',
                onClick: () => {
                  // F14: Use ref to get latest retry function
                  retryRef.current()
                },
              },
              duration: ERROR_TOAST_WITH_RETRY_DURATION_MS,
            })
          } else if (error instanceof ApiError && canRetryError(error)) {
            // Retryable error
            toast.error(getErrorUserMessage(error), {
              action: {
                label: 'Retry',
                onClick: () => {
                  retryRef.current()
                },
              },
              duration: ERROR_TOAST_WITH_RETRY_DURATION_MS,
            })
          } else {
            // Non-retryable error
            toast.error(getErrorUserMessage(error), {
              duration: ERROR_TOAST_DURATION_MS,
            })
          }
        }

        return null
      }
    },
    [showToasts, autoDismissSlowToast, dismissSlowToast]
  )

  /**
   * Retry the last failed request (Story 5.3)
   */
  const retry = useCallback(async (): Promise<T | null> => {
    if (!lastRequestFnRef.current) {
      console.warn('[useApiRequest] No request to retry')
      return null
    }
    return execute(lastRequestFnRef.current)
  }, [execute])

  // F14: Update ref immediately when retry changes to avoid stale closures
  useEffect(() => {
    retryRef.current = retry
  }, [retry])

  // F2 & F3: Create API options with timeout and slow request callback
  // Note: signal is managed internally by execute() via abortControllerRef
  const apiOptions: Omit<ApiMethodOptions, 'signal'> = {
    timeout,
    onSlowRequest: handleSlowRequest,
  }

  return {
    execute,
    result,
    cancel,
    retry,
    reset,
    apiOptions,
  }
}
