import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { RateLimitError } from './rate-limit-error'
import { ApiError } from '@/lib/api/client'

function createRateLimitError(retryAfter: number = 30): ApiError {
  return new ApiError('RATE_LIMIT_EXCEEDED', 'Rate limit exceeded', 429, {
    retryAfter,
    limit: 100,
    remaining: 0,
  })
}

describe('RateLimitError', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('rendering', () => {
    it('renders error alert', () => {
      const error = createRateLimitError()
      render(<RateLimitError error={error} onRetry={() => {}} />)

      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText('Too Many Requests')).toBeInTheDocument()
    })

    it('shows countdown timer with retry after seconds', () => {
      const error = createRateLimitError(45)
      render(<RateLimitError error={error} onRetry={() => {}} />)

      expect(screen.getByText('45s')).toBeInTheDocument()
    })

    it('shows Skip Wait button while countdown active', () => {
      const error = createRateLimitError()
      render(<RateLimitError error={error} onRetry={() => {}} />)

      expect(screen.getByRole('button', { name: /skip wait/i })).toBeInTheDocument()
    })

    it('shows dismiss button when onDismiss provided', () => {
      const error = createRateLimitError()
      render(<RateLimitError error={error} onRetry={() => {}} onDismiss={() => {}} />)

      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument()
    })
  })

  describe('countdown behavior', () => {
    it('counts down from retry after value', () => {
      const error = createRateLimitError(10)
      render(<RateLimitError error={error} onRetry={() => {}} />)

      expect(screen.getByText('10s')).toBeInTheDocument()

      act(() => {
        vi.advanceTimersByTime(3000)
      })

      expect(screen.getByText('7s')).toBeInTheDocument()
    })

    it('auto-retries when countdown completes by default', async () => {
      const onRetry = vi.fn()
      const error = createRateLimitError(2)
      render(<RateLimitError error={error} onRetry={onRetry} autoRetry />)

      await act(async () => {
        vi.advanceTimersByTime(2000)
      })

      // Allow microtasks to flush for the async onRetry callback
      await act(async () => {
        await Promise.resolve()
      })

      expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it('does not auto-retry when autoRetry is false', () => {
      const onRetry = vi.fn()
      const error = createRateLimitError(2)
      render(<RateLimitError error={error} onRetry={onRetry} autoRetry={false} />)

      act(() => {
        vi.advanceTimersByTime(2000)
      })

      // Give time for any potential async calls
      act(() => {
        vi.advanceTimersByTime(100)
      })

      expect(onRetry).not.toHaveBeenCalled()
    })
  })

  describe('manual retry', () => {
    it('calls onRetry when Skip Wait clicked', async () => {
      const onRetry = vi.fn()
      const error = createRateLimitError(60)
      render(<RateLimitError error={error} onRetry={onRetry} />)

      const skipButton = screen.getByRole('button', { name: /skip wait/i })
      await act(async () => {
        fireEvent.click(skipButton)
      })

      // Allow microtasks to flush for the async onRetry callback
      await act(async () => {
        await Promise.resolve()
      })

      expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it('shows Try Again Now button after countdown completes', () => {
      const error = createRateLimitError(1)
      render(<RateLimitError error={error} onRetry={() => {}} autoRetry={false} />)

      act(() => {
        vi.advanceTimersByTime(1000)
      })

      expect(screen.getByRole('button', { name: /try again now/i })).toBeInTheDocument()
    })
  })

  describe('dismiss', () => {
    it('calls onDismiss when dismiss clicked', () => {
      const onDismiss = vi.fn()
      const error = createRateLimitError()
      render(<RateLimitError error={error} onRetry={() => {}} onDismiss={onDismiss} />)

      fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))

      expect(onDismiss).toHaveBeenCalledTimes(1)
    })
  })

  describe('accessibility', () => {
    it('has alert role', () => {
      const error = createRateLimitError()
      render(<RateLimitError error={error} onRetry={() => {}} />)

      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('has aria-live polite', () => {
      const error = createRateLimitError()
      render(<RateLimitError error={error} onRetry={() => {}} />)

      expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'polite')
    })
  })
})
