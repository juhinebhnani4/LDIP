import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import {
  SessionExpiredDialog,
  storeReturnUrl,
  getAndClearReturnUrl,
} from './SessionExpiredDialog'

// Mock next/navigation
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('SessionExpiredDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  describe('rendering', () => {
    it('renders dialog when open', () => {
      render(<SessionExpiredDialog open={true} />)

      expect(screen.getByRole('alertdialog')).toBeInTheDocument()
      expect(screen.getByText('Session Expired')).toBeInTheDocument()
    })

    it('does not render dialog when closed', () => {
      render(<SessionExpiredDialog open={false} />)

      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })

    it('shows session expired message', () => {
      render(<SessionExpiredDialog open={true} />)

      expect(
        screen.getByText(/your session has expired/i)
      ).toBeInTheDocument()
    })

    it('shows Log In Again button', () => {
      render(<SessionExpiredDialog open={true} />)

      expect(
        screen.getByRole('button', { name: /log in again/i })
      ).toBeInTheDocument()
    })

    it('shows Dismiss button when onClose provided', () => {
      render(<SessionExpiredDialog open={true} onClose={() => {}} />)

      expect(
        screen.getByRole('button', { name: /dismiss/i })
      ).toBeInTheDocument()
    })

    it('does not show Dismiss button when onClose not provided', () => {
      render(<SessionExpiredDialog open={true} />)

      expect(
        screen.queryByRole('button', { name: /dismiss/i })
      ).not.toBeInTheDocument()
    })
  })

  describe('login action', () => {
    it('navigates to login page on Log In Again click', () => {
      render(<SessionExpiredDialog open={true} />)

      const loginButton = screen.getByRole('button', { name: /log in again/i })
      fireEvent.click(loginButton)

      expect(mockPush).toHaveBeenCalledWith('/login?session_expired=true')
    })

    it('stores return URL before navigating', () => {
      Object.defineProperty(window, 'location', {
        value: { href: 'http://localhost/matters/123' },
        writable: true,
      })

      render(<SessionExpiredDialog open={true} />)

      const loginButton = screen.getByRole('button', { name: /log in again/i })
      fireEvent.click(loginButton)

      expect(sessionStorage.getItem('returnUrl')).toBe('http://localhost/matters/123')
    })
  })

  describe('dismiss action', () => {
    it('calls onClose when Dismiss clicked', () => {
      const onClose = vi.fn()
      render(<SessionExpiredDialog open={true} onClose={onClose} />)

      const dismissButton = screen.getByRole('button', { name: /dismiss/i })
      fireEvent.click(dismissButton)

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })
})

describe('storeReturnUrl', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('stores current URL in sessionStorage', () => {
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost/matters/123' },
      writable: true,
    })

    storeReturnUrl()

    expect(sessionStorage.getItem('returnUrl')).toBe('http://localhost/matters/123')
  })

  it('does not store login page URL', () => {
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost/login' },
      writable: true,
    })

    storeReturnUrl()

    expect(sessionStorage.getItem('returnUrl')).toBeNull()
  })

  it('does not store signup page URL', () => {
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost/signup' },
      writable: true,
    })

    storeReturnUrl()

    expect(sessionStorage.getItem('returnUrl')).toBeNull()
  })
})

describe('getAndClearReturnUrl', () => {
  beforeEach(() => {
    sessionStorage.clear()
    Object.defineProperty(window, 'location', {
      value: { origin: 'http://localhost' },
      writable: true,
    })
  })

  it('returns stored URL and clears it', () => {
    sessionStorage.setItem('returnUrl', 'http://localhost/matters/123')

    const returnUrl = getAndClearReturnUrl()

    expect(returnUrl).toBe('/matters/123')
    expect(sessionStorage.getItem('returnUrl')).toBeNull()
  })

  it('returns dashboard when no URL stored', () => {
    const returnUrl = getAndClearReturnUrl()

    expect(returnUrl).toBe('/dashboard')
  })

  it('returns dashboard for invalid URL', () => {
    sessionStorage.setItem('returnUrl', 'not-a-valid-url')

    const returnUrl = getAndClearReturnUrl()

    expect(returnUrl).toBe('/dashboard')
  })

  it('returns dashboard for cross-origin URL (security)', () => {
    sessionStorage.setItem('returnUrl', 'http://evil.com/phishing')

    const returnUrl = getAndClearReturnUrl()

    expect(returnUrl).toBe('/dashboard')
  })

  it('preserves query string and hash', () => {
    sessionStorage.setItem('returnUrl', 'http://localhost/matters/123?tab=documents#section')

    const returnUrl = getAndClearReturnUrl()

    expect(returnUrl).toBe('/matters/123?tab=documents#section')
  })
})
