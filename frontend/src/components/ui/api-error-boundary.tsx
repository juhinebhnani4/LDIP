'use client'

import { Component, type ReactNode } from 'react'

import { ErrorAlert } from '@/components/ui/error-alert'
import { ApiError } from '@/lib/api/client'

interface ApiErrorBoundaryProps {
  /** Child components to render */
  children: ReactNode
  /** Optional fallback render function for custom error UI */
  fallback?: (error: Error, reset: () => void) => ReactNode
  /** Optional callback when an error is caught */
  onError?: (error: Error) => void
  /** Additional CSS classes for the error alert */
  className?: string
}

interface ApiErrorBoundaryState {
  error: Error | null
  hasError: boolean
}

/**
 * Error boundary for catching API and render errors in sections.
 * Story 13.4: Graceful Degradation and Error States (AC #1)
 *
 * Features:
 * - Catches errors in child components
 * - Shows user-friendly error alert with retry option
 * - Supports custom fallback UI via render prop
 * - Isolates failures to prevent app-wide crashes
 *
 * Usage:
 * ```tsx
 * <ApiErrorBoundary onError={logError}>
 *   <SummaryContent />
 * </ApiErrorBoundary>
 * ```
 */
export class ApiErrorBoundary extends Component<ApiErrorBoundaryProps, ApiErrorBoundaryState> {
  constructor(props: ApiErrorBoundaryProps) {
    super(props)
    this.state = { error: null, hasError: false }
  }

  static getDerivedStateFromError(error: Error): ApiErrorBoundaryState {
    return { error, hasError: true }
  }

  componentDidCatch(error: Error): void {
    this.props.onError?.(error)
  }

  reset = (): void => {
    this.setState({ error: null, hasError: false })
  }

  render(): ReactNode {
    const { children, fallback, className } = this.props
    const { error, hasError } = this.state

    if (hasError && error) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback(error, this.reset)
      }

      // Default error alert UI
      return (
        <ErrorAlert
          error={error instanceof ApiError ? error : error.message}
          onRetry={this.reset}
          className={className}
        />
      )
    }

    return children
  }
}

/**
 * Functional wrapper for ApiErrorBoundary with common patterns.
 * Provides a simpler API for common use cases.
 */
export function withApiErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  options?: {
    onError?: (error: Error) => void
    className?: string
  }
): React.FC<P> {
  const WithBoundary: React.FC<P> = (props) => (
    <ApiErrorBoundary onError={options?.onError} className={options?.className}>
      <WrappedComponent {...props} />
    </ApiErrorBoundary>
  )

  WithBoundary.displayName = `WithApiErrorBoundary(${WrappedComponent.displayName ?? WrappedComponent.name ?? 'Component'})`

  return WithBoundary
}
