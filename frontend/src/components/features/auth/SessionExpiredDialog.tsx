'use client'

import { useRouter } from 'next/navigation'
import { LogIn, X } from 'lucide-react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface SessionExpiredDialogProps {
  /** Whether the dialog is open */
  open: boolean
  /** Callback when dialog is closed (only via X button, not login) */
  onClose?: () => void
}

/**
 * Stores the current URL for returning after login.
 * Used by session expiry flow to preserve user's place.
 */
export function storeReturnUrl(): void {
  if (typeof window !== 'undefined') {
    const currentUrl = window.location.href
    // Don't store login/signup pages as return URLs
    if (!currentUrl.includes('/login') && !currentUrl.includes('/signup')) {
      sessionStorage.setItem('returnUrl', currentUrl)
    }
  }
}

/**
 * Gets and clears the stored return URL.
 * Returns the dashboard as fallback.
 */
export function getAndClearReturnUrl(): string {
  if (typeof window !== 'undefined') {
    const returnUrl = sessionStorage.getItem('returnUrl')
    sessionStorage.removeItem('returnUrl')

    if (returnUrl) {
      // Validate return URL is on same domain for security
      try {
        const url = new URL(returnUrl)
        const currentOrigin = window.location.origin
        if (url.origin === currentOrigin) {
          return url.pathname + url.search + url.hash
        }
      } catch {
        // Invalid URL, use fallback
      }
    }
  }
  return '/dashboard'
}

/**
 * SessionExpiredDialog component.
 * Story 13.6: User-Facing Error Messages with Actionable Guidance (AC #5)
 *
 * Features:
 * - Modal dialog informing user their session expired
 * - "Log In Again" button that preserves return URL
 * - Dismissible but recommends logging in
 */
export function SessionExpiredDialog({ open, onClose }: SessionExpiredDialogProps) {
  const router = useRouter()

  const handleLogin = () => {
    storeReturnUrl()
    router.push('/login?session_expired=true')
  }

  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <LogIn className="h-5 w-5 text-amber-500" />
            Session Expired
          </AlertDialogTitle>
          <AlertDialogDescription>
            Your session has expired for security reasons. Please log in again to continue where you left off.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          {onClose && (
            <AlertDialogCancel onClick={onClose} className="gap-1">
              <X className="h-4 w-4" />
              Dismiss
            </AlertDialogCancel>
          )}
          <AlertDialogAction onClick={handleLogin} className="gap-1">
            <LogIn className="h-4 w-4" />
            Log In Again
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
