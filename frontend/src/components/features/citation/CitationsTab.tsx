'use client';

/**
 * Citations Tab Component
 *
 * Tab component for the matter workspace that displays citations
 * with full Act Discovery Report UI and verification features.
 *
 * @see Story 3-4: Split-View Citation Highlighting
 * @see Story 10C.3: Citations Tab List and Act Discovery
 */

import { CitationsContent } from './CitationsContent';

export interface CitationsTabProps {
  /** Matter ID */
  matterId: string;
  /** Callback when user wants to view in document */
  onViewInDocument?: (documentId: string, page: number) => void;
}

/**
 * Citations Tab for matter workspace.
 *
 * Displays citations list with filtering, multiple view modes,
 * Act Discovery Report, and split view integration.
 *
 * @example
 * ```tsx
 * <CitationsTab matterId="matter-123" />
 * ```
 */
export function CitationsTab({ matterId, onViewInDocument }: CitationsTabProps) {
  return (
    <div className="h-full p-4">
      <CitationsContent
        matterId={matterId}
        onViewInDocument={onViewInDocument}
      />
    </div>
  );
}

CitationsTab.displayName = 'CitationsTab';
