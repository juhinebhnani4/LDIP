import { render, screen } from '@testing-library/react'
import { LoadingSpinner } from './loading-spinner'

describe('LoadingSpinner', () => {
  it('renders without message', () => {
    render(<LoadingSpinner />)

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Loading...')).toHaveClass('sr-only')
  })

  it('renders with message', () => {
    render(<LoadingSpinner message="Fetching data..." />)

    expect(screen.getByText('Fetching data...')).toBeInTheDocument()
    // Screen reader text should also include the message
    expect(screen.getByText('Fetching data...')).not.toHaveClass('sr-only')
  })

  it('renders small size', () => {
    const { container } = render(<LoadingSpinner size="sm" />)

    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toHaveClass('h-4', 'w-4')
  })

  it('renders medium size (default)', () => {
    const { container } = render(<LoadingSpinner />)

    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toHaveClass('h-6', 'w-6')
  })

  it('renders large size', () => {
    const { container } = render(<LoadingSpinner size="lg" />)

    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toHaveClass('h-8', 'w-8')
  })

  it('applies custom className', () => {
    render(<LoadingSpinner className="custom-class" />)

    expect(screen.getByRole('status')).toHaveClass('custom-class')
  })

  it('has correct accessibility attributes', () => {
    render(<LoadingSpinner />)

    const status = screen.getByRole('status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status).toHaveAttribute('aria-busy', 'true')
  })
})
