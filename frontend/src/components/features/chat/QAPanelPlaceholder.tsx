'use client';

import { JaanchIcon } from '@/components/ui/jaanch-logo';

/**
 * Q&A Panel Placeholder
 *
 * Placeholder content shown when the Q&A panel cannot load
 * (e.g., no matter selected or user not authenticated).
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 */
export function QAPanelPlaceholder() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
      <JaanchIcon size="lg" className="mb-4 opacity-50" />
      <h3 className="mb-2 text-lg font-medium">Ask jaanch</h3>
      <p className="max-w-xs text-sm text-muted-foreground">
        Ask questions about your matter. The AI will analyze documents and
        provide answers with citations.
      </p>
    </div>
  );
}
