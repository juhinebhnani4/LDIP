import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { ActionableError, type ErrorContext } from './actionable-error'
import { ApiError } from '@/lib/api/client'

// Mock next/navigation
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

// Mock window.open
const mockWindowOpen = vi.fn()
Object.defineProperty(window, 'open', { value: mockWindowOpen, writable: true })

// Mock window.location.reload
const mockReload = vi.fn()
Object.defineProperty(window, 'location', {
  value: { reload: mockReload, href: 'http://localhost/test' },
  writable: true,
})

describe('ActionableError', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  describe('rendering', () => {
    it('renders error title and description for string error', () => {
      render(<ActionableError error="Something went wrong" />)

      expect(screen.getByText('Something Went Wrong')).toBeInTheDocument()
      expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    })

    it('renders error title and description for ApiError', () => {
      const error = new ApiError('NETWORK_ERROR', 'Connection failed', 0)
      render(<ActionableError error={error} />)

      expect(screen.getByText('Connection Error')).toBeInTheDocument()
      expect(screen.getByText(/Unable to connect/)).toBeInTheDocument()
    })

    it('uses explicit errorCode over ApiError code', () => {
      const error = new ApiError('NETWORK_ERROR', 'Connection failed', 0)
      render(<ActionableError error={error} errorCode="SESSION_EXPIRED" />)

      expect(screen.getByText('Session Expired')).toBeInTheDocument()
    })

    it('renders dismiss button when onDismiss provided', () => {
      const onDismiss = vi.fn()
      render(<ActionableError error="Error" onDismiss={onDismiss} />)

      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument()
    })
  })

  describe('retry action', () => {
    it('shows retry button for retryable errors with onRetry', () => {
      const onRetry = vi.fn()
      const error = new ApiError('NETWORK_ERROR', 'Connection failed', 0)
      render(<ActionableError error={error} onRetry={onRetry} />)

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    })

    it('calls onRetry when retry button clicked', async () => {
      const user = userEvent.setup()
      const onRetry = vi.fn()
      const error = new ApiError('NETWORK_ERROR', 'Connection failed', 0)
      render(<ActionableError error={error} onRetry={onRetry} />)

      await user.click(screen.getByRole('button', { name: /try again/i }))

      expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it('shows loading state during retry', async () => {
      const user = userEvent.setup()
      let resolveRetry: () => void
      const onRetry = vi.fn().mockImplementation(
        () => new Promise<void>((resolve) => { resolveRetry = resolve })
      )
      const error = new ApiError('NETWORK_ERROR', 'Connection failed', 0)
      render(<ActionableError error={error} onRetry={onRetry} />)

      await user.click(screen.getByRole('button', { name: /try again/i }))

      expect(screen.getByRole('button', { name: /retrying/i })).toBeDisabled()

      // Resolve the promise
      resolveRetry!()
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).not.toBeDisabled()
      })
    })

    it('does not show retry button without onRetry callback', () => {
      const error = new ApiError('NETWORK_ERROR', 'Connection failed', 0)
      render(<ActionableError error={error} />)

      expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument()
    })
  })

  describe('login action', () => {
    it('shows login button for session expired error', () => {
      const error = new ApiError('SESSION_EXPIRED', 'Session expired', 401)
      render(<ActionableError error={error} />)

      expect(screen.getByRole('button', { name: /log in again/i })).toBeInTheDocument()
    })

    it('stores return URL and navigates to login', async () => {
      const user = userEvent.setup()
      const error = new ApiError('SESSION_EXPIRED', 'Session expired', 401)
      render(<ActionableError error={error} />)

      await user.click(screen.getByRole('button', { name: /log in again/i }))

      expect(sessionStorage.getItem('returnUrl')).toBe('http://localhost/test')
      expect(mockPush).toHaveBeenCalledWith('/login?session_expired=true')
    })
  })

  describe('contact support action', () => {
    it('shows contact support button for permission errors', () => {
      const error = new ApiError('INSUFFICIENT_PERMISSIONS', 'Permission denied', 403)
      render(<ActionableError error={error} />)

      expect(screen.getByRole('button', { name: /request access/i })).toBeInTheDocument()
    })

    it('calls onContactSupport callback when provided', async () => {
      const user = userEvent.setup()
      const onContactSupport = vi.fn()
      const error = new ApiError('INSUFFICIENT_PERMISSIONS', 'Permission denied', 403)
      render(
        <ActionableError
          error={error}
          onContactSupport={onContactSupport}
          matterId="matter-123"
        />
      )

      await user.click(screen.getByRole('button', { name: /request access/i }))

      expect(onContactSupport).toHaveBeenCalledTimes(1)
      const context = onContactSupport.mock.calls[0]![0] as ErrorContext
      expect(context.errorCode).toBe('INSUFFICIENT_PERMISSIONS')
      expect(context.matterId).toBe('matter-123')
    })

    it('opens mailto link as fallback', async () => {
      const user = userEvent.setup()
      const error = new ApiError('INSUFFICIENT_PERMISSIONS', 'Permission denied', 403)
      render(<ActionableError error={error} />)

      await user.click(screen.getByRole('button', { name: /request access/i }))

      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining('mailto:support@jaanch.ai'),
        '_blank'
      )
    })
  })

  describe('navigate action', () => {
    it('shows navigate button for matter not found error', () => {
      const error = new ApiError('MATTER_NOT_FOUND', 'Matter not found', 404)
      render(<ActionableError error={error} />)

      expect(screen.getByRole('button', { name: /go to dashboard/i })).toBeInTheDocument()
    })

    it('navigates to specified URL', async () => {
      const user = userEvent.setup()
      const error = new ApiError('MATTER_NOT_FOUND', 'Matter not found', 404)
      render(<ActionableError error={error} />)

      await user.click(screen.getByRole('button', { name: /go to dashboard/i }))

      expect(mockPush).toHaveBeenCalledWith('/dashboard')
    })
  })

  describe('refresh action', () => {
    it('shows refresh button for entity not found error', () => {
      const error = new ApiError('ENTITY_NOT_FOUND', 'Entity not found', 404)
      render(<ActionableError error={error} />)

      expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument()
    })

    it('reloads the page', async () => {
      const user = userEvent.setup()
      const error = new ApiError('ENTITY_NOT_FOUND', 'Entity not found', 404)
      render(<ActionableError error={error} />)

      await user.click(screen.getByRole('button', { name: /refresh page/i }))

      expect(mockReload).toHaveBeenCalledTimes(1)
    })
  })

  describe('secondary action', () => {
    it('shows secondary action for errors with both primary and secondary', () => {
      const onRetry = vi.fn()
      const error = new ApiError('INTERNAL_SERVER_ERROR', 'Server error', 500)
      render(<ActionableError error={error} onRetry={onRetry} />)

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /report issue/i })).toBeInTheDocument()
    })
  })

  describe('dismiss functionality', () => {
    it('calls onDismiss when dismiss button clicked', async () => {
      const user = userEvent.setup()
      const onDismiss = vi.fn()
      render(<ActionableError error="Error" onDismiss={onDismiss} />)

      await user.click(screen.getByRole('button', { name: /dismiss/i }))

      expect(onDismiss).toHaveBeenCalledTimes(1)
    })
  })

  describe('accessibility', () => {
    it('has alert role', () => {
      render(<ActionableError error="Error" />)

      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('has aria-live polite', () => {
      render(<ActionableError error="Error" />)

      expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'polite')
    })

    it('dismiss button has aria-label', () => {
      render(<ActionableError error="Error" onDismiss={() => {}} />)

      expect(screen.getByRole('button', { name: /dismiss error/i })).toBeInTheDocument()
    })
  })
})
