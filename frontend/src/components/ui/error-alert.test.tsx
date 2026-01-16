import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorAlert } from './error-alert'
import { ApiError } from '@/lib/api/client'

describe('ErrorAlert', () => {
  it('renders error message from string', () => {
    render(<ErrorAlert error="Something went wrong" />)

    expect(screen.getByText('Something Went Wrong')).toBeInTheDocument()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders error message from Error object', () => {
    const error = new Error('Custom error message')
    render(<ErrorAlert error={error} />)

    expect(screen.getByText('Something Went Wrong')).toBeInTheDocument()
    expect(screen.getByText('Custom error message')).toBeInTheDocument()
  })

  it('renders user-friendly message for ApiError', () => {
    const error = new ApiError('RATE_LIMIT_EXCEEDED', 'Rate limit exceeded', 429)
    render(<ErrorAlert error={error} />)

    expect(screen.getByText('Too Many Requests')).toBeInTheDocument()
    expect(
      screen.getByText(
        "You're making requests too quickly. Please wait a moment and try again."
      )
    ).toBeInTheDocument()
  })

  it('shows retry button for retryable errors', () => {
    const error = new ApiError('RATE_LIMIT_EXCEEDED', 'Rate limit exceeded', 429)
    const onRetry = jest.fn()

    render(<ErrorAlert error={error} onRetry={onRetry} />)

    const retryButton = screen.getByRole('button', { name: /try again/i })
    expect(retryButton).toBeInTheDocument()

    fireEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('hides retry button for non-retryable errors', () => {
    const error = new ApiError('UNAUTHORIZED', 'Not authorized', 401)
    const onRetry = jest.fn()

    render(<ErrorAlert error={error} onRetry={onRetry} />)

    expect(
      screen.queryByRole('button', { name: /try again/i })
    ).not.toBeInTheDocument()
  })

  it('shows dismiss button when onDismiss is provided', () => {
    const onDismiss = jest.fn()

    render(<ErrorAlert error="Test error" onDismiss={onDismiss} />)

    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    expect(dismissButton).toBeInTheDocument()

    fireEvent.click(dismissButton)
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('shows retrying state on retry button', () => {
    const error = new ApiError('NETWORK_ERROR', 'Network error', 0)

    render(<ErrorAlert error={error} onRetry={() => {}} isRetrying />)

    expect(screen.getByRole('button', { name: /retrying/i })).toBeDisabled()
    expect(screen.getByText('Retrying...')).toBeInTheDocument()
  })

  it('has correct accessibility attributes', () => {
    render(<ErrorAlert error="Test error" />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveAttribute('aria-live', 'polite')
  })
})
