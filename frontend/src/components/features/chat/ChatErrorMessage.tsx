'use client';

import { useState, useEffect } from 'react';
import { AlertCircle, RefreshCw, Clock } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * Chat Error Message Component
 *
 * Story 5.5: User-Friendly LLM Error Messages
 *
 * Displays user-friendly error messages for chat/LLM failures.
 * Features:
 * - Friendly error messages (not technical jargon)
 * - Retry button with cooldown countdown
 * - Different styling based on error severity
 */

export interface ChatError {
  /** Error code from backend */
  code: string;
  /** User-friendly error message */
  error: string;
  /** Whether retrying might help */
  retry_suggested?: boolean;
  /** Seconds to wait before retry */
  retry_after_seconds?: number | null;
}

interface ChatErrorMessageProps {
  /** Error object from the backend */
  error: ChatError;
  /** Callback when user clicks retry */
  onRetry?: () => void;
  /** Callback to dismiss the error */
  onDismiss?: () => void;
  /** Additional className */
  className?: string;
}

const ERROR_ICONS: Record<string, string> = {
  RATE_LIMITED: 'clock',
  QUOTA_EXCEEDED: 'alert',
  TIMEOUT: 'clock',
  default: 'alert',
};

const ERROR_VARIANTS: Record<string, 'destructive' | 'default'> = {
  RATE_LIMITED: 'default',
  TIMEOUT: 'default',
  QUOTA_EXCEEDED: 'destructive',
  API_ERROR: 'destructive',
  default: 'destructive',
};

export function ChatErrorMessage({
  error,
  onRetry,
  onDismiss,
  className,
}: ChatErrorMessageProps) {
  const [countdown, setCountdown] = useState<number | null>(
    error.retry_after_seconds ?? null
  );
  const [isRetrying, setIsRetrying] = useState(false);

  // Countdown timer
  useEffect(() => {
    if (countdown === null || countdown <= 0) return;

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          return null;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [countdown]);

  const handleRetry = async () => {
    if (!onRetry || countdown !== null) return;
    setIsRetrying(true);
    try {
      await onRetry();
    } finally {
      setIsRetrying(false);
    }
  };

  const variant = ERROR_VARIANTS[error.code] ?? ERROR_VARIANTS.default;
  const showRetryButton = error.retry_suggested !== false && onRetry;
  const isWaiting = countdown !== null && countdown > 0;

  return (
    <Alert variant={variant} className={cn('relative', className)}>
      <AlertCircle className="size-4" />
      <AlertTitle className="text-sm font-medium">
        {getErrorTitle(error.code)}
      </AlertTitle>
      <AlertDescription className="mt-2 text-sm">
        <p>{error.error}</p>

        {/* Retry section */}
        {showRetryButton && (
          <div className="mt-3 flex items-center gap-3">
            {isWaiting ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Clock className="size-3" />
                <span>Try again in {countdown} seconds</span>
              </div>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={handleRetry}
                disabled={isRetrying}
                className="gap-2"
              >
                <RefreshCw className={cn('size-3', isRetrying && 'animate-spin')} />
                Try Again
              </Button>
            )}
            {onDismiss && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onDismiss}
              >
                Dismiss
              </Button>
            )}
          </div>
        )}

        {/* Non-retryable message */}
        {error.retry_suggested === false && (
          <p className="mt-2 text-xs text-muted-foreground">
            Please try rephrasing your question or contact support if this persists.
          </p>
        )}
      </AlertDescription>
    </Alert>
  );
}

function getErrorTitle(code: string): string {
  const titles: Record<string, string> = {
    RATE_LIMITED: 'Please Wait',
    QUOTA_EXCEEDED: 'Usage Limit Reached',
    TIMEOUT: 'Request Timed Out',
    CONNECTION_ERROR: 'Connection Issue',
    CONTENT_FILTERED: 'Content Restricted',
    CONTEXT_TOO_LONG: 'Question Too Complex',
    SERVICE_UNAVAILABLE: 'Service Temporarily Unavailable',
    INVALID_RESPONSE: 'Unexpected Response',
    API_ERROR: 'Service Error',
    UNKNOWN_ERROR: 'Something Went Wrong',
    STREAM_ERROR: 'Streaming Error',
  };
  return titles[code] ?? 'Error';
}

/**
 * Compact error indicator for inline use
 */
export function ChatErrorBadge({ error }: { error: ChatError }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-destructive/10 text-destructive text-xs">
      <AlertCircle className="size-3" />
      <span>{getErrorTitle(error.code)}</span>
    </div>
  );
}
