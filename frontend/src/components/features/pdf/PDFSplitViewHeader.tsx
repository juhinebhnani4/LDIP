'use client';

/**
 * PDF Split View Header Component
 *
 * Header bar for the PDF split view panel with document name,
 * expand to full screen button, and close button.
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode (AC: #2, #5)
 */

import { X, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface PDFSplitViewHeaderProps {
  /** Document filename to display */
  documentName: string;
  /** Callback when close button is clicked */
  onClose: () => void;
  /** Callback when expand button is clicked */
  onExpand: () => void;
}

/**
 * Header component for PDF split view panel.
 * Displays document name with expand and close controls.
 */
export function PDFSplitViewHeader({
  documentName,
  onClose,
  onExpand,
}: PDFSplitViewHeaderProps) {
  return (
    <div
      className="flex items-center justify-between border-b bg-muted/50 px-3 py-2"
      role="banner"
      aria-label="PDF viewer header"
    >
      <span
        className="truncate text-sm font-medium"
        title={documentName}
        aria-label={`Document: ${documentName}`}
      >
        {documentName}
      </span>

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onExpand}
          title="Open full screen (F)"
          aria-label="Open document in full screen"
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onClose}
          title="Close (Esc)"
          aria-label="Close PDF viewer"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
