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
  /** Page number */
  pageNumber: number;
  /** Optional excerpt to show in tooltip */
  excerpt?: string;
  /** Display text (defaults to "pg. {pageNumber}") */
  displayText?: string;
  /** Additional className */
  className?: string;
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

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              openDocumentByName(matterId, documentName, pageNumber);
            }}
            className={cn(
              'text-blue-600 hover:text-blue-800 underline underline-offset-2 inline-flex items-center gap-1 cursor-pointer',
              className
            )}
          >
            {displayText ?? `pg. ${pageNumber}`}
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
