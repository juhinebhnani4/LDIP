import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { ContactSupport, buildErrorContext, type ErrorContext } from './ContactSupport'

// Mock window.open
const mockWindowOpen = vi.fn()
Object.defineProperty(window, 'open', { value: mockWindowOpen, writable: true })

// Mock clipboard API
const mockWriteText = vi.fn().mockResolvedValue(undefined)
Object.assign(navigator, {
  clipboard: { writeText: mockWriteText },
})

const mockErrorContext: ErrorContext = {
  errorCode: 'NETWORK_ERROR',
  errorMessage: 'Unable to connect to the server.',
  timestamp: '2026-01-16T12:00:00.000Z',
  userId: 'user-abc1...',
  matterId: 'matt-xyz2...',
  matterTitle: 'Test Matter',
  browserInfo: 'Mozilla/5.0 Test Browser',
  currentUrl: 'http://localhost/test',
  correlationId: 'corr-123',
}

describe('ContactSupport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockWriteText.mockResolvedValue(undefined)
  })

  describe('rendering', () => {
    it('renders dialog with error details when open', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('Contact Support')).toBeInTheDocument()
      // Error code appears in multiple places - use getAllByText
      expect(screen.getAllByText('NETWORK_ERROR').length).toBeGreaterThan(0)
    })

    it('does not render dialog when closed', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={false}
          onClose={() => {}}
        />
      )

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('displays error code and message', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      expect(screen.getAllByText('NETWORK_ERROR').length).toBeGreaterThan(0)
      expect(screen.getByText('Unable to connect to the server.')).toBeInTheDocument()
    })

    it('displays correlation ID when present', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      expect(screen.getByText('corr-123')).toBeInTheDocument()
    })

    it('displays matter title when present', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      expect(screen.getByText('Test Matter')).toBeInTheDocument()
    })

    it('displays timestamp', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      expect(screen.getByText('2026-01-16T12:00:00.000Z')).toBeInTheDocument()
    })
  })

  describe('copy functionality', () => {
    it('copies error details to clipboard on button click', async () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      const copyButton = screen.getByRole('button', { name: /copy/i })
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(mockWriteText).toHaveBeenCalledTimes(1)
      })
      expect(mockWriteText).toHaveBeenCalledWith(
        expect.stringContaining('NETWORK_ERROR')
      )
    })

    it('shows "Copied" feedback after copying', async () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      const copyButton = screen.getByRole('button', { name: /copy/i })
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(screen.getByText('Copied')).toBeInTheDocument()
      })
    })

    it('includes error code in copied text', async () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      fireEvent.click(screen.getByRole('button', { name: /copy/i }))

      await waitFor(() => {
        expect(mockWriteText).toHaveBeenCalledWith(
          expect.stringContaining('Error Code: NETWORK_ERROR')
        )
      })
    })

    it('includes correlation ID in copied text', async () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      fireEvent.click(screen.getByRole('button', { name: /copy/i }))

      await waitFor(() => {
        expect(mockWriteText).toHaveBeenCalledWith(
          expect.stringContaining('Reference ID: corr-123')
        )
      })
    })
  })

  describe('email functionality', () => {
    it('opens mailto link on email support click', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      const emailButton = screen.getByRole('button', { name: /email support/i })
      fireEvent.click(emailButton)

      expect(mockWindowOpen).toHaveBeenCalledTimes(1)
      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining('mailto:support@jaanch.ai'),
        '_blank'
      )
    })

    it('uses custom support email when provided', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
          supportEmail="help@custom.com"
        />
      )

      const emailButton = screen.getByRole('button', { name: /email support/i })
      fireEvent.click(emailButton)

      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining('mailto:help@custom.com'),
        '_blank'
      )
    })

    it('includes error code in email subject', () => {
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={() => {}}
        />
      )

      const emailButton = screen.getByRole('button', { name: /email support/i })
      fireEvent.click(emailButton)

      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining('subject='),
        '_blank'
      )
      // Check for encoded NETWORK_ERROR in URL
      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining('NETWORK_ERROR'),
        '_blank'
      )
    })
  })

  describe('close functionality', () => {
    it('calls onClose when close button clicked', () => {
      const onClose = vi.fn()
      render(
        <ContactSupport
          errorContext={mockErrorContext}
          open={true}
          onClose={onClose}
        />
      )

      const closeButton = screen.getByRole('button', { name: /close/i })
      fireEvent.click(closeButton)

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })
})

describe('buildErrorContext', () => {
  it('masks user ID to show only first 8 characters', () => {
    const context = buildErrorContext({
      errorCode: 'TEST_ERROR',
      errorMessage: 'Test message',
      userId: '12345678-1234-1234-1234-123456789012',
    })

    expect(context.userId).toBe('12345678...')
  })

  it('masks matter ID to show only first 8 characters', () => {
    const context = buildErrorContext({
      errorCode: 'TEST_ERROR',
      errorMessage: 'Test message',
      matterId: 'abcdefgh-ijkl-mnop-qrst-uvwxyz123456',
    })

    expect(context.matterId).toBe('abcdefgh...')
  })

  it('includes timestamp', () => {
    const context = buildErrorContext({
      errorCode: 'TEST_ERROR',
      errorMessage: 'Test message',
    })

    expect(context.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })

  it('includes error code and message', () => {
    const context = buildErrorContext({
      errorCode: 'TEST_ERROR',
      errorMessage: 'Test message',
    })

    expect(context.errorCode).toBe('TEST_ERROR')
    expect(context.errorMessage).toBe('Test message')
  })

  it('handles undefined optional fields', () => {
    const context = buildErrorContext({
      errorCode: 'TEST_ERROR',
      errorMessage: 'Test message',
    })

    expect(context.userId).toBeUndefined()
    expect(context.matterId).toBeUndefined()
    expect(context.correlationId).toBeUndefined()
  })

  it('preserves correlation ID', () => {
    const context = buildErrorContext({
      errorCode: 'TEST_ERROR',
      errorMessage: 'Test message',
      correlationId: 'corr-xyz-123',
    })

    expect(context.correlationId).toBe('corr-xyz-123')
  })
})
