import { render, screen, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import { InlineError } from './inline-error'

describe('InlineError', () => {
  it('renders error message', () => {
    render(<InlineError message="Field is required" />)

    expect(screen.getByText('Field is required')).toBeInTheDocument()
  })

  it('renders with error severity by default', () => {
    render(<InlineError message="Error message" />)

    const container = screen.getByRole('alert')
    expect(container).toHaveClass('text-destructive')
  })

  it('renders with warning severity', () => {
    render(<InlineError message="Warning message" severity="warning" />)

    const container = screen.getByRole('status')
    expect(container).toHaveClass('text-yellow-600')
  })

  it('renders with info severity', () => {
    render(<InlineError message="Info message" severity="info" />)

    const container = screen.getByRole('status')
    expect(container).toHaveClass('text-blue-600')
  })

  it('shows retry button when onRetry is provided', () => {
    const onRetry = vi.fn()

    render(<InlineError message="Error" onRetry={onRetry} />)

    const retryButton = screen.getByRole('button', { name: /retry/i })
    expect(retryButton).toBeInTheDocument()

    fireEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('disables retry button when isRetrying', () => {
    render(<InlineError message="Error" onRetry={() => {}} isRetrying />)

    expect(screen.getByRole('button', { name: /retry/i })).toBeDisabled()
  })

  it('hides retry button when onRetry is not provided', () => {
    render(<InlineError message="Error" />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<InlineError message="Error" className="custom-class" />)

    const container = screen.getByRole('alert')
    expect(container).toHaveClass('custom-class')
  })
})
