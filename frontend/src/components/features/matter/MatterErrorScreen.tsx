'use client';

import Link from 'next/link';
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface MatterErrorScreenProps {
  /** Headline (e.g. "Matter not available") */
  title: string;
  /** User-facing explanation */
  description: string;
  /** Optional retry handler — shows a "Try Again" button when provided */
  onRetry?: () => void;
  /** Optional technical detail, rendered only in non-production for debugging */
  details?: string;
}

/**
 * Shared presentational error screen for the matter workspace.
 *
 * Single source of truth for the "can't open this matter" UI, used by BOTH:
 * - `MatterGate` — the convergence point, for the EXPECTED 404/403 case (FE-ARCH-01)
 * - `app/matter/[matterId]/error.tsx` — the route boundary, for UNEXPECTED render throws
 *
 * Keeping one component avoids two hand-synced copies of the same error UI drifting
 * apart (the FE-ARCH-03 duplication shape). Fills its parent; the caller provides the
 * height context (`min-h-screen` for the route boundary, `flex-1` inside the gate).
 */
export function MatterErrorScreen({ title, description, onRetry, details }: MatterErrorScreenProps) {
  return (
    <div className="flex w-full flex-1 flex-col bg-background">
      {/* Minimal header with a way back to the dashboard */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center gap-4 px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="text-sm font-medium">Dashboard</span>
          </Link>
        </div>
      </header>

      <main className="container mx-auto max-w-2xl px-4 py-16">
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>{description}</AlertDescription>
        </Alert>

        <div className="flex flex-col justify-center gap-4 sm:flex-row">
          {onRetry && (
            <Button variant="outline" onClick={onRetry}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
          )}
          <Button asChild>
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Dashboard
            </Link>
          </Button>
        </div>

        {details && process.env.NODE_ENV !== 'production' && (
          <div className="mt-8 rounded-lg bg-muted p-4">
            <p className="whitespace-pre-wrap font-mono text-xs text-muted-foreground">{details}</p>
          </div>
        )}
      </main>
    </div>
  );
}
