'use client';

/**
 * Citations Tab Component
 *
 * Story 3-4: Split-View Citation Highlighting
 *
 * Tab component for the matter workspace that displays citations
 * and provides access to split-view verification.
 */

import { CitationsList } from './CitationsList';

export interface CitationsTabProps {
  /** Matter ID */
  matterId: string;
}

/**
 * Citations Tab for matter workspace.
 *
 * Displays the citations list with split view integration.
 * This is the main entry point for viewing and verifying citations.
 *
 * @example
 * ```tsx
 * <CitationsTab matterId="matter-123" />
 * ```
 */
export function CitationsTab({ matterId }: CitationsTabProps) {
  return (
    <div className="p-4">
      <div className="mb-6">
        <h2 className="text-xl font-semibold">Citations</h2>
        <p className="text-sm text-muted-foreground">
          View and verify citations extracted from case documents
        </p>
      </div>

      <CitationsList matterId={matterId} />
    </div>
  );
}
