'use client';

import { FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { SourceReference as SourceReferenceType } from '@/types/chat';

interface SourceReferenceProps {
  /** The source reference data */
  source: SourceReferenceType;
  /** Callback when the source is clicked */
  onClick?: () => void;
}

/**
 * SourceReference Component
 *
 * Displays a clickable source reference link for citations in assistant messages.
 * Shows document name and page number (if available).
 * Hover shows context snippet preview for lawyer convenience.
 * Clicking opens the PDF viewer to that location (Story 11.5).
 *
 * Story 11.2: Implement Q&A Conversation History (AC: #2)
 */
export function SourceReference({ source, onClick }: SourceReferenceProps) {
  const label = source.page
    ? `${source.documentName} (p. ${source.page})`
    : source.documentName;

  const button = (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      className="h-auto max-w-full gap-1 px-2 py-1 text-xs font-normal text-primary hover:text-primary/80 hover:underline"
      data-testid="source-reference"
    >
      <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </Button>
  );

  // Show tooltip with context snippet if available
  if (source.contextSnippet) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{button}</TooltipTrigger>
          <TooltipContent side="top" className="max-w-sm text-xs">
            <p className="font-medium mb-1">{label}</p>
            <p className="text-muted-foreground italic">
              &quot;...{source.contextSnippet}...&quot;
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return button;
}
