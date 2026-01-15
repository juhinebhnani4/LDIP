'use client';

import { MessageSquare } from 'lucide-react';

/**
 * Q&A Panel Placeholder
 *
 * MVP placeholder content for the Q&A panel. The actual Q&A functionality
 * will be implemented in Epic 11.
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 */
export function QAPanelPlaceholder() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
      <MessageSquare className="mb-4 h-12 w-12 text-muted-foreground" />
      <h3 className="mb-2 text-lg font-medium">ASK LDIP</h3>
      <p className="max-w-xs text-sm text-muted-foreground">
        Ask questions about your matter. The AI will analyze documents and
        provide answers with citations.
      </p>
      <p className="mt-4 text-xs text-muted-foreground">Coming in Epic 11</p>
    </div>
  );
}
