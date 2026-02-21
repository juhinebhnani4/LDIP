'use client';

/**
 * CitationLink Component
 *
 * Inline citation link with hover preview tooltip that navigates to PDF viewer.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #4)
 */

import { useParams } from 'next/navigation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { openDocumentByName } from '@/lib/utils/openDocument';

interface CitationLinkProps {
  /** Document name */
  documentName: string;
  /** Page number (null when page is unknown) */
  pageNumber: number | null;
  /** Optional excerpt to show in tooltip */
  excerpt?: string;
  /** Display text (defaults to "pg. {pageNumber}") */
  displayText?: string;
  /** Additional className */
  className?: string;
}

/** Truncate a filename to maxLen chars, preserving the extension. */
function truncateName(name: string, maxLen = 30): string {
  if (name.length <= maxLen) return name;
  const dot = name.lastIndexOf('.');
  const ext = dot !== -1 ? name.slice(dot) : '';
  return name.slice(0, maxLen - ext.length - 1) + '\u2026' + ext;
}

export function CitationLink({
  documentName,
  pageNumber,
  excerpt,
  displayText,
  className,
}: CitationLinkProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // Build link text: displayText > "pg. N" > truncated filename
  const linkText = displayText
    ?? (pageNumber != null ? `pg. ${pageNumber}` : truncateName(documentName));

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              openDocumentByName(matterId, documentName, pageNumber ?? undefined);
            }}
            className={cn(
              'text-blue-600 hover:text-blue-800 underline underline-offset-2 inline-flex items-center gap-1 cursor-pointer',
              className
            )}
          >
            {linkText}
          </a>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <p className="font-medium">{documentName}</p>
          {excerpt && (
            <p className="text-sm text-muted-foreground mt-1">{excerpt}</p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
