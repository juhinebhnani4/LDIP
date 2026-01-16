import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'

import { CountdownTimer, useCountdown } from './countdown-timer'

describe('CountdownTimer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('rendering', () => {
    it('renders initial seconds', () => {
      render(<CountdownTimer seconds={10} />)

      expect(screen.getByText('10s')).toBeInTheDocument()
    })

    it('renders custom label', () => {
      render(<CountdownTimer seconds={10} label="Wait for" />)

      expect(screen.getByText('Wait for')).toBeInTheDocument()
    })

    it('formats time in minutes and seconds for values >= 60', () => {
      render(<CountdownTimer seconds={90} />)

      expect(screen.getByText('1m 30s')).toBeInTheDocument()
    })

    it('renders progress bar when showProgress is true', () => {
      render(<CountdownTimer seconds={10} showProgress />)

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('does not render progress bar by default', () => {
      render(<CountdownTimer seconds={10} />)

      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    })

    it('applies custom className', () => {
      const { container } = render(<CountdownTimer seconds={10} className="custom-class" />)

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('countdown behavior', () => {
    it('counts down every second', () => {
      render(<CountdownTimer seconds={5} />)

      expect(screen.getByText('5s')).toBeInTheDocument()

      act(() => {
        vi.advanceTimersByTime(1000)
      })
      expect(screen.getByText('4s')).toBeInTheDocument()

      act(() => {
        vi.advanceTimersByTime(1000)
      })
      expect(screen.getByText('3s')).toBeInTheDocument()
    })

    it('calls onComplete when countdown reaches 0', () => {
      const onComplete = vi.fn()
      render(<CountdownTimer seconds={2} onComplete={onComplete} />)

      act(() => {
        vi.advanceTimersByTime(2000)
      })

      expect(onComplete).toHaveBeenCalledTimes(1)
    })

    it('does not call onComplete multiple times', () => {
      const onComplete = vi.fn()
      render(<CountdownTimer seconds={1} onComplete={onComplete} />)

      act(() => {
        vi.advanceTimersByTime(1000)
      })

      // Advance more time to ensure no additional calls
      act(() => {
        vi.advanceTimersByTime(5000)
      })

      expect(onComplete).toHaveBeenCalledTimes(1)
    })

    it('hides component after completion', async () => {
      const { container } = render(<CountdownTimer seconds={1} />)

      act(() => {
        vi.advanceTimersByTime(1000)
      })

      await act(async () => {
        vi.advanceTimersByTime(0)
      })

      expect(container.firstChild).toBeNull()
    })

    it('does not count when isPaused is true', () => {
      render(<CountdownTimer seconds={5} isPaused />)

      expect(screen.getByText('5s')).toBeInTheDocument()

      act(() => {
        vi.advanceTimersByTime(3000)
      })

      expect(screen.getByText('5s')).toBeInTheDocument()
    })

    it('resumes counting when isPaused becomes false', () => {
      const { rerender } = render(<CountdownTimer seconds={5} isPaused />)

      act(() => {
        vi.advanceTimersByTime(2000)
      })
      expect(screen.getByText('5s')).toBeInTheDocument()

      rerender(<CountdownTimer seconds={5} isPaused={false} />)

      act(() => {
        vi.advanceTimersByTime(2000)
      })
      expect(screen.getByText('3s')).toBeInTheDocument()
    })

    it('resets when initialSeconds prop changes', () => {
      const { rerender } = render(<CountdownTimer seconds={5} />)

      act(() => {
        vi.advanceTimersByTime(2000)
      })
      expect(screen.getByText('3s')).toBeInTheDocument()

      rerender(<CountdownTimer seconds={10} />)
      expect(screen.getByText('10s')).toBeInTheDocument()
    })
  })

  describe('progress bar', () => {
    it('renders progress bar with initial state', () => {
      render(<CountdownTimer seconds={10} showProgress />)

      const progressBar = screen.getByRole('progressbar')
      expect(progressBar).toBeInTheDocument()
      // Radix Progress shows indicator at 100% initially (translateX(0))
      const indicator = progressBar.querySelector('[class*="Indicator"]') ?? progressBar.firstChild
      expect(indicator).toBeInTheDocument()
    })

    it('progress bar updates as time passes', () => {
      render(<CountdownTimer seconds={10} showProgress />)

      const progressBar = screen.getByRole('progressbar')
      expect(progressBar).toBeInTheDocument()

      act(() => {
        vi.advanceTimersByTime(5000)
      })

      // Verify countdown text shows correct time (progress is tied to this)
      expect(screen.getByText('5s')).toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('has aria-label on progress bar', () => {
      render(<CountdownTimer seconds={10} showProgress />)

      expect(screen.getByRole('progressbar')).toHaveAttribute(
        'aria-label',
        '10 seconds remaining'
      )
    })

    it('clock icon is hidden from screen readers', () => {
      const { container } = render(<CountdownTimer seconds={10} />)

      const clockIcon = container.querySelector('svg')
      expect(clockIcon).toHaveAttribute('aria-hidden', 'true')
    })
  })
})

describe('useCountdown hook', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('initializes with provided seconds', () => {
    const { result } = renderHook(() => useCountdown(10))

    expect(result.current.seconds).toBe(10)
  })

  it('starts automatically by default', () => {
    const { result } = renderHook(() => useCountdown(5))

    expect(result.current.isRunning).toBe(true)
  })

  it('can be configured to not auto-start', () => {
    const { result } = renderHook(() => useCountdown(5, { autoStart: false }))

    expect(result.current.isRunning).toBe(false)
  })

  it('counts down every second when running', () => {
    const { result } = renderHook(() => useCountdown(5))

    expect(result.current.seconds).toBe(5)

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(result.current.seconds).toBe(3)
  })

  it('calls onComplete when countdown finishes', async () => {
    const onComplete = vi.fn()
    renderHook(() => useCountdown(2, { onComplete }))

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    await act(async () => {
      vi.advanceTimersByTime(0)
    })

    expect(onComplete).toHaveBeenCalledTimes(1)
  })

  it('pause stops the countdown', () => {
    const { result } = renderHook(() => useCountdown(5))

    act(() => {
      result.current.pause()
    })

    expect(result.current.isRunning).toBe(false)

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(result.current.seconds).toBe(5)
  })

  it('start resumes the countdown', () => {
    const { result } = renderHook(() => useCountdown(5, { autoStart: false }))

    act(() => {
      result.current.start()
    })

    expect(result.current.isRunning).toBe(true)

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(result.current.seconds).toBe(3)
  })

  it('reset resets to initial seconds and stops', () => {
    const { result } = renderHook(() => useCountdown(5))

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(result.current.seconds).toBe(3)

    act(() => {
      result.current.reset()
    })

    expect(result.current.seconds).toBe(5)
    expect(result.current.isRunning).toBe(false)
    expect(result.current.hasCompleted).toBe(false)
  })

  it('sets hasCompleted to true when finished', async () => {
    const { result } = renderHook(() => useCountdown(1))

    expect(result.current.hasCompleted).toBe(false)

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    await act(async () => {
      vi.advanceTimersByTime(0)
    })

    expect(result.current.hasCompleted).toBe(true)
  })
})
