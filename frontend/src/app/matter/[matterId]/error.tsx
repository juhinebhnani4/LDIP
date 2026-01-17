'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Matter Error Boundary
 *
 * Catches errors in matter routes and displays a user-friendly message.
 * Common scenarios:
 * - User doesn't have access to the matter (403/404)
 * - Matter doesn't exist
 * - Network/API errors
 */
export default function MatterError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log error for debugging (dev only)
    if (process.env.NODE_ENV !== 'production') {
      console.error('[MatterError] Error in matter route:', error);
    }
  }, [error]);

  // Check if this is an access denied error
  const isAccessDenied =
    error.message?.toLowerCase().includes('not found') ||
    error.message?.toLowerCase().includes('access') ||
    error.message?.toLowerCase().includes('permission') ||
    error.message?.toLowerCase().includes('unauthorized');

  return (
    <div className="min-h-screen bg-background">
      {/* Simple header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center gap-4 px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="text-sm font-medium">Dashboard</span>
          </Link>
        </div>
      </header>

      {/* Error content */}
      <main className="container mx-auto px-4 py-16 max-w-2xl">
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>
            {isAccessDenied ? 'Access Denied' : 'Something went wrong'}
          </AlertTitle>
          <AlertDescription>
            {isAccessDenied
              ? "You don't have access to this matter. You may have been removed from this matter, or the matter may have been deleted."
              : 'There was an error loading this matter. Please try again or return to the dashboard.'}
          </AlertDescription>
        </Alert>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button variant="outline" onClick={reset}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Try Again
          </Button>
          <Button asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Dashboard
            </Link>
          </Button>
        </div>

        {/* Debug info (dev only) */}
        {process.env.NODE_ENV !== 'production' && (
          <div className="mt-8 p-4 bg-muted rounded-lg">
            <p className="text-xs text-muted-foreground font-mono">
              Error: {error.message}
            </p>
            {error.digest && (
              <p className="text-xs text-muted-foreground font-mono mt-1">
                Digest: {error.digest}
              </p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
