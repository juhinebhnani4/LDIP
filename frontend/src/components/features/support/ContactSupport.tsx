'use client'

import { useState } from 'react'
import { Copy, Mail, Check, AlertCircle, X } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'

/** Error context for support requests */
export interface ErrorContext {
  errorCode: string
  errorMessage: string
  timestamp: string
  userId?: string
  matterId?: string
  matterTitle?: string
  browserInfo: string
  currentUrl: string
  correlationId?: string
}

interface ContactSupportProps {
  /** Error context to include in support request */
  errorContext: ErrorContext
  /** Whether the dialog is open */
  open: boolean
  /** Callback when dialog is closed */
  onClose: () => void
  /** Support email address */
  supportEmail?: string
}

/**
 * Builds a sanitized error context for support.
 * Masks sensitive data like user IDs.
 */
export function buildErrorContext(options: {
  errorCode: string
  errorMessage: string
  userId?: string
  matterId?: string
  matterTitle?: string
  correlationId?: string
}): ErrorContext {
  // Mask user ID - only show first 8 characters
  const maskedUserId = options.userId ? `${options.userId.slice(0, 8)}...` : undefined

  // Mask matter ID - only show first 8 characters
  const maskedMatterId = options.matterId ? `${options.matterId.slice(0, 8)}...` : undefined

  return {
    errorCode: options.errorCode,
    errorMessage: options.errorMessage,
    timestamp: new Date().toISOString(),
    userId: maskedUserId,
    matterId: maskedMatterId,
    matterTitle: options.matterTitle,
    browserInfo: typeof navigator !== 'undefined' ? navigator.userAgent : 'Unknown',
    currentUrl: typeof window !== 'undefined' ? window.location.href : 'Unknown',
    correlationId: options.correlationId,
  }
}

/**
 * Formats error context as a string for copying.
 */
function formatErrorContextForCopy(context: ErrorContext): string {
  const lines = [
    '--- Error Details ---',
    `Error Code: ${context.errorCode}`,
    `Message: ${context.errorMessage}`,
    `Time: ${context.timestamp}`,
  ]

  if (context.correlationId) {
    lines.push(`Reference ID: ${context.correlationId}`)
  }

  if (context.matterId) {
    lines.push(`Matter: ${context.matterTitle ?? context.matterId}`)
  }

  lines.push(
    '',
    '--- Technical Details ---',
    `URL: ${context.currentUrl}`,
    `Browser: ${context.browserInfo}`,
  )

  if (context.userId) {
    lines.push(`User Ref: ${context.userId}`)
  }

  return lines.join('\n')
}

/**
 * Builds a mailto URL with pre-filled error context.
 */
function buildMailtoUrl(context: ErrorContext, supportEmail: string): string {
  const subject = encodeURIComponent(
    `Error Report: ${context.errorCode}${context.correlationId ? ` [${context.correlationId}]` : ''}`
  )

  const bodyLines = [
    'Hi Support Team,',
    '',
    'I encountered an error while using JaanchAI:',
    '',
    '--- Error Details ---',
    `Error Code: ${context.errorCode}`,
    `Message: ${context.errorMessage}`,
    `Time: ${context.timestamp}`,
  ]

  if (context.correlationId) {
    bodyLines.push(`Reference ID: ${context.correlationId}`)
  }

  if (context.matterId) {
    bodyLines.push(`Matter: ${context.matterTitle ?? context.matterId}`)
  }

  bodyLines.push(
    '',
    '--- What I was trying to do ---',
    '[Please describe what you were trying to do when this error occurred]',
    '',
    '--- Technical Details ---',
    `URL: ${context.currentUrl}`,
    `Browser: ${context.browserInfo}`,
  )

  const body = encodeURIComponent(bodyLines.join('\n'))

  return `mailto:${supportEmail}?subject=${subject}&body=${body}`
}

/**
 * ContactSupport component for reporting errors.
 * Story 13.6: User-Facing Error Messages with Actionable Guidance (AC #4)
 *
 * Features:
 * - Pre-fills error context for support
 * - Copy error details to clipboard
 * - Email support with pre-filled body
 * - Sanitized output (no sensitive data)
 */
export function ContactSupport({
  errorContext,
  open,
  onClose,
  supportEmail = 'support@jaanch.ai',
}: ContactSupportProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const text = formatErrorContextForCopy(errorContext)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for browsers without clipboard API
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleEmailSupport = () => {
    const mailtoUrl = buildMailtoUrl(errorContext, supportEmail)
    window.open(mailtoUrl, '_blank')
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Contact Support
          </DialogTitle>
          <DialogDescription>
            Share these error details with our support team so we can help resolve your issue.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Error Summary */}
          <Alert variant="destructive">
            <AlertDescription className="text-sm">
              <div className="font-medium">{errorContext.errorCode}</div>
              <div className="mt-1 text-xs opacity-90">{errorContext.errorMessage}</div>
            </AlertDescription>
          </Alert>

          {/* Error Details (copyable) */}
          <div className="rounded-md bg-muted p-3 font-mono text-xs">
            <div className="flex justify-between items-start mb-2">
              <span className="text-muted-foreground">Error Details</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2"
                onClick={handleCopy}
              >
                {copied ? (
                  <>
                    <Check className="mr-1 h-3 w-3 text-green-500" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="mr-1 h-3 w-3" />
                    Copy
                  </>
                )}
              </Button>
            </div>
            <div className="space-y-1">
              <div>
                <span className="text-muted-foreground">Code:</span> {errorContext.errorCode}
              </div>
              <div>
                <span className="text-muted-foreground">Time:</span> {errorContext.timestamp}
              </div>
              {errorContext.correlationId && (
                <div>
                  <span className="text-muted-foreground">Ref:</span> {errorContext.correlationId}
                </div>
              )}
              {errorContext.matterId && (
                <div>
                  <span className="text-muted-foreground">Matter:</span>{' '}
                  {errorContext.matterTitle ?? errorContext.matterId}
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={onClose}>
              <X className="mr-1 h-4 w-4" />
              Close
            </Button>
            <Button onClick={handleEmailSupport}>
              <Mail className="mr-1 h-4 w-4" />
              Email Support
            </Button>
          </div>

          {/* Support Note */}
          <p className="text-xs text-muted-foreground text-center">
            You can also reach us at{' '}
            <a
              href={`mailto:${supportEmail}`}
              className="text-primary hover:underline"
            >
              {supportEmail}
            </a>
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
