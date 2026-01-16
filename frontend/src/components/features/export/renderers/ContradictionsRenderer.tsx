'use client';

/**
 * ContradictionsRenderer Component
 *
 * Placeholder for Contradictions section in export preview.
 * Full implementation is deferred to Phase 2.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { AlertTriangle } from 'lucide-react';

/**
 * ContradictionsRenderer displays a placeholder message.
 * Contradictions feature is planned for Phase 2.
 */
export function ContradictionsRenderer() {
  return (
    <div className="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-dashed border-gray-300 dark:border-gray-600">
      <AlertTriangle className="h-5 w-5 text-muted-foreground" />
      <div>
        <p className="text-sm text-muted-foreground">
          No contradictions analyzed for this matter.
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Contradiction analysis is available in Phase 2.
        </p>
      </div>
    </div>
  );
}
