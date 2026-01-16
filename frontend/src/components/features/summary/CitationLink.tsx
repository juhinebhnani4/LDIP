'use client';

/**
 * CitationLink Component
 *
 * Inline citation link with hover preview tooltip that navigates to PDF viewer.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #4)
 */

import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

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

  const href = `/matter/${matterId}/documents?doc=${encodeURIComponent(documentName)}&page=${pageNumber}`;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Link
            href={href}
            className={cn(
              'text-blue-600 hover:text-blue-800 underline underline-offset-2 inline-flex items-center gap-1',
              className
            )}
          >
            {displayText ?? `pg. ${pageNumber}`}
          </Link>
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
