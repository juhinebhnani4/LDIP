import { render, screen, fireEvent } from '@testing-library/react'
import { vi, type Mock } from 'vitest'
import { ServiceStatusBanner } from './ServiceStatusBanner'
import * as useServiceHealthModule from '@/hooks/useServiceHealth'

// Mock the useServiceHealth hook
vi.mock('@/hooks/useServiceHealth', () => ({
  useServiceHealth: vi.fn(),
}))

const mockUseServiceHealth = useServiceHealthModule.useServiceHealth as Mock

describe('ServiceStatusBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render when no circuits are open', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: false,
      affectedFeatures: [],
      circuits: [],
    })

    const { container } = render(<ServiceStatusBanner />)

    expect(container.firstChild).toBeNull()
  })

  it('renders when circuits are open', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: ['AI Chat', 'Document Processing'],
      circuits: [
        { name: 'openai_chat', state: 'open', cooldownRemaining: 60 },
        { name: 'documentai_ocr', state: 'open', cooldownRemaining: 120 },
      ],
    })

    render(<ServiceStatusBanner />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/some features are limited/i)).toBeInTheDocument()
  })

  it('displays affected feature names', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: ['AI Chat', 'Search'],
      circuits: [
        { name: 'openai_chat', state: 'open', cooldownRemaining: 0 },
        { name: 'openai_embeddings', state: 'open', cooldownRemaining: 0 },
      ],
    })

    render(<ServiceStatusBanner />)

    expect(screen.getByText(/AI Chat, Search/)).toBeInTheDocument()
  })

  it('shows recovery time when cooldown is present', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: ['Document Processing'],
      circuits: [
        { name: 'documentai_ocr', state: 'open', cooldownRemaining: 180 },
      ],
    })

    render(<ServiceStatusBanner />)

    expect(screen.getByText(/~3 min/)).toBeInTheDocument()
  })

  it('can be dismissed', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: ['AI Chat'],
      circuits: [
        { name: 'openai_chat', state: 'open', cooldownRemaining: 0 },
      ],
    })

    render(<ServiceStatusBanner />)

    expect(screen.getByRole('alert')).toBeInTheDocument()

    // Click dismiss button
    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows generic message when no feature names available', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: [],
      circuits: [
        { name: 'unknown_circuit', state: 'open', cooldownRemaining: 0 },
      ],
    })

    render(<ServiceStatusBanner />)

    expect(
      screen.getByText(/external services experiencing issues/i)
    ).toBeInTheDocument()
  })

  it('applies custom className', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: ['AI Chat'],
      circuits: [
        { name: 'openai_chat', state: 'open', cooldownRemaining: 0 },
      ],
    })

    render(<ServiceStatusBanner className="custom-class" />)

    expect(screen.getByRole('alert')).toHaveClass('custom-class')
  })

  it('has correct accessibility attributes', () => {
    mockUseServiceHealth.mockReturnValue({
      hasOpenCircuits: true,
      affectedFeatures: ['AI Chat'],
      circuits: [
        { name: 'openai_chat', state: 'open', cooldownRemaining: 0 },
      ],
    })

    render(<ServiceStatusBanner />)

    const banner = screen.getByRole('alert')
    expect(banner).toHaveAttribute('aria-live', 'polite')
  })
})
