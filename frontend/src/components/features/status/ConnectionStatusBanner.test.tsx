import { render, screen, fireEvent, act } from '@testing-library/react'
import { vi, type Mock } from 'vitest'
import { ConnectionStatusBanner } from './ConnectionStatusBanner'
import * as wsClientModule from '@/lib/ws/client'
import type { WSConnectionState, WSReconnectInfo } from '@/lib/ws/client'

// Mock the ws client
vi.mock('@/lib/ws/client', () => ({
  getWSClient: vi.fn(),
}))

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}))

const mockGetWSClient = wsClientModule.getWSClient as Mock

describe('ConnectionStatusBanner', () => {
  let stateCallback: ((state: WSConnectionState) => void) | null = null
  let reconnectCallback: ((info: WSReconnectInfo) => void) | null = null

  const createMockClient = (initialState: WSConnectionState = 'disconnected', initialReconnectInfo?: WSReconnectInfo) => ({
    onStateChange: vi.fn((cb: (state: WSConnectionState) => void) => {
      stateCallback = cb
      cb(initialState)
      return () => { stateCallback = null }
    }),
    onReconnectChange: vi.fn((cb: (info: WSReconnectInfo) => void) => {
      reconnectCallback = cb
      cb(initialReconnectInfo || { attempts: 0, maxAttempts: 5, isReconnecting: false })
      return () => { reconnectCallback = null }
    }),
    getReconnectInfo: vi.fn(() => initialReconnectInfo || { attempts: 0, maxAttempts: 5, isReconnecting: false }),
  })

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    stateCallback = null
    reconnectCallback = null
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not render when disconnected with no reconnect attempts', () => {
    mockGetWSClient.mockReturnValue(createMockClient('disconnected'))

    const { container } = render(<ConnectionStatusBanner />)

    expect(container.firstChild).toBeNull()
  })

  it('does not render when connected', () => {
    mockGetWSClient.mockReturnValue(createMockClient('connected'))

    const { container } = render(<ConnectionStatusBanner />)

    expect(container.firstChild).toBeNull()
  })

  it('renders reconnecting banner with attempt count', () => {
    mockGetWSClient.mockReturnValue(createMockClient('reconnecting', {
      attempts: 2,
      maxAttempts: 5,
      isReconnecting: true,
    }))

    render(<ConnectionStatusBanner />)

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText(/Reconnecting.../)).toBeInTheDocument()
    expect(screen.getByText(/attempt 2\/5/)).toBeInTheDocument()
  })

  it('renders disconnected banner after max attempts', () => {
    mockGetWSClient.mockReturnValue(createMockClient('disconnected', {
      attempts: 5,
      maxAttempts: 5,
      isReconnecting: false,
    }))

    render(<ConnectionStatusBanner />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/Connection lost/)).toBeInTheDocument()
    expect(screen.getByText(/Real-time updates unavailable/)).toBeInTheDocument()
  })

  it('shows connected banner briefly after reconnection', async () => {
    const mockClient = createMockClient('reconnecting', {
      attempts: 1,
      maxAttempts: 5,
      isReconnecting: true,
    })
    mockGetWSClient.mockReturnValue(mockClient)

    render(<ConnectionStatusBanner />)

    // Verify reconnecting state
    expect(screen.getByText(/Reconnecting.../)).toBeInTheDocument()

    // Simulate reconnection success
    act(() => {
      stateCallback?.('connected')
    })

    // Should show "Connected" banner
    expect(screen.getByText('Connected')).toBeInTheDocument()

    // Fast-forward 3 seconds
    act(() => {
      vi.advanceTimersByTime(3000)
    })

    // Banner should be gone
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
  })

  it('can be dismissed when reconnecting', () => {
    mockGetWSClient.mockReturnValue(createMockClient('reconnecting', {
      attempts: 1,
      maxAttempts: 5,
      isReconnecting: true,
    }))

    render(<ConnectionStatusBanner />)

    expect(screen.getByRole('status')).toBeInTheDocument()

    // Click dismiss button
    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('can be dismissed when disconnected', () => {
    mockGetWSClient.mockReturnValue(createMockClient('disconnected', {
      attempts: 5,
      maxAttempts: 5,
      isReconnecting: false,
    }))

    render(<ConnectionStatusBanner />)

    expect(screen.getByRole('alert')).toBeInTheDocument()

    // Click dismiss button
    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reappears when reconnection starts after being dismissed', () => {
    const mockClient = createMockClient('disconnected', {
      attempts: 5,
      maxAttempts: 5,
      isReconnecting: false,
    })
    mockGetWSClient.mockReturnValue(mockClient)

    render(<ConnectionStatusBanner />)

    // Dismiss the banner
    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    // Simulate reconnection starting
    act(() => {
      stateCallback?.('reconnecting')
    })

    // Banner should reappear
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('has refresh button when disconnected', () => {
    mockGetWSClient.mockReturnValue(createMockClient('disconnected', {
      attempts: 5,
      maxAttempts: 5,
      isReconnecting: false,
    }))

    render(<ConnectionStatusBanner />)

    const refreshButton = screen.getByRole('button', { name: /refresh/i })
    expect(refreshButton).toBeInTheDocument()
  })

  it('applies custom className', () => {
    mockGetWSClient.mockReturnValue(createMockClient('reconnecting', {
      attempts: 1,
      maxAttempts: 5,
      isReconnecting: true,
    }))

    render(<ConnectionStatusBanner className="custom-class" />)

    expect(screen.getByRole('status')).toHaveClass('custom-class')
  })

  it('has correct accessibility attributes for reconnecting state', () => {
    mockGetWSClient.mockReturnValue(createMockClient('reconnecting', {
      attempts: 1,
      maxAttempts: 5,
      isReconnecting: true,
    }))

    render(<ConnectionStatusBanner />)

    const banner = screen.getByRole('status')
    expect(banner).toHaveAttribute('aria-live', 'polite')
  })

  it('has correct accessibility attributes for disconnected state', () => {
    mockGetWSClient.mockReturnValue(createMockClient('disconnected', {
      attempts: 5,
      maxAttempts: 5,
      isReconnecting: false,
    }))

    render(<ConnectionStatusBanner />)

    const banner = screen.getByRole('alert')
    expect(banner).toHaveAttribute('aria-live', 'assertive')
  })

  it('cleans up subscriptions on unmount', () => {
    const mockClient = createMockClient('disconnected')
    mockGetWSClient.mockReturnValue(mockClient)

    const { unmount } = render(<ConnectionStatusBanner />)

    unmount()

    // Callbacks should be nullified by cleanup
    expect(stateCallback).toBeNull()
    expect(reconnectCallback).toBeNull()
  })
})
