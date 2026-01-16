import { renderHook, waitFor, act } from '@testing-library/react'
import { useServiceHealth } from './useServiceHealth'

// Mock fetch
const mockFetch = jest.fn()
global.fetch = mockFetch

// Mock document.visibilityState
let visibilityState = 'visible'
Object.defineProperty(document, 'visibilityState', {
  get: () => visibilityState,
  configurable: true,
})

describe('useServiceHealth', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    jest.useFakeTimers()
    visibilityState = 'visible'
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  const mockCircuitsResponse = {
    data: {
      circuits: [
        {
          circuit_name: 'openai_chat',
          state: 'closed',
          failure_count: 0,
          success_count: 100,
          last_failure: null,
          cooldown_remaining: 0,
        },
        {
          circuit_name: 'documentai_ocr',
          state: 'open',
          failure_count: 5,
          success_count: 50,
          last_failure: '2024-01-15T10:00:00Z',
          cooldown_remaining: 120,
        },
      ],
      summary: {
        total: 2,
        open: 1,
        closed: 1,
        half_open: 0,
      },
    },
  }

  it('fetches circuits on mount', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCircuitsResponse),
    })

    const { result } = renderHook(() => useServiceHealth())

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/health/circuits')
    )
    expect(result.current.circuits).toHaveLength(2)
  })

  it('identifies open circuits', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCircuitsResponse),
    })

    const { result } = renderHook(() => useServiceHealth())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.hasOpenCircuits).toBe(true)
  })

  it('maps affected features correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCircuitsResponse),
    })

    const { result } = renderHook(() => useServiceHealth())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.affectedFeatures).toContain('Document Processing')
  })

  it('handles fetch errors', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useServiceHealth())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toBeTruthy()
    expect(result.current.error?.message).toBe('Network error')
  })

  it('handles non-OK response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    })

    const { result } = renderHook(() => useServiceHealth())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toBeTruthy()
  })

  it('polls at specified interval', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockCircuitsResponse),
    })

    renderHook(() => useServiceHealth(5000))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1)
    })

    // Advance time by poll interval
    act(() => {
      jest.advanceTimersByTime(5000)
    })

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2)
    })
  })

  it('provides manual refresh function', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockCircuitsResponse),
    })

    const { result } = renderHook(() => useServiceHealth())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockFetch).toHaveBeenCalledTimes(1)

    // Manually refresh
    await act(async () => {
      await result.current.refresh()
    })

    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('returns hasOpenCircuits false when all circuits closed', async () => {
    const allClosedResponse = {
      data: {
        circuits: [
          {
            circuit_name: 'openai_chat',
            state: 'closed',
            failure_count: 0,
            success_count: 100,
            last_failure: null,
            cooldown_remaining: 0,
          },
        ],
        summary: { total: 1, open: 0, closed: 1, half_open: 0 },
      },
    }

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(allClosedResponse),
    })

    const { result } = renderHook(() => useServiceHealth())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.hasOpenCircuits).toBe(false)
    expect(result.current.affectedFeatures).toHaveLength(0)
  })
})
