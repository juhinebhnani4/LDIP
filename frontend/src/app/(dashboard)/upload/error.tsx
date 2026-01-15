'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertCircle, ArrowLeft, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

/**
 * Error Boundary for Upload Page
 *
 * Displays error state and provides recovery options.
 */

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function UploadError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Structured logging would go here in production
    // structlog.error('Upload page error', { error: error.message, digest: error.digest });
  }, [error]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header with back navigation */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Error content */}
      <main className="container mx-auto px-4 py-16 max-w-md text-center">
        <div className="flex flex-col items-center gap-4">
          <div className="rounded-full bg-destructive/10 p-4">
            <AlertCircle className="size-10 text-destructive" />
          </div>

          <h1 className="text-xl font-semibold">Something went wrong</h1>

          <p className="text-muted-foreground">
            We encountered an error while loading the upload wizard. Please try again.
          </p>

          <div className="flex gap-3 mt-4">
            <Button variant="outline" asChild>
              <Link href="/">Go to Dashboard</Link>
            </Button>
            <Button onClick={reset}>
              <RefreshCw className="size-4 mr-2" />
              Try Again
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
