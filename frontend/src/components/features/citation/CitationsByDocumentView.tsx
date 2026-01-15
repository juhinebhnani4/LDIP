'use client';

/**
 * CitationsByDocumentView Component
 *
 * Displays citations grouped by document in expandable sections.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Eye,
  Wrench,
  AlertTriangle,
  CheckCircle,
  Clock,
  HelpCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Skeleton } from '@/components/ui/skeleton';
import type { CitationListItem, VerificationStatus } from '@/types/citation';

export interface CitationsByDocumentViewProps {
  /** Citations to display */
  citations: CitationListItem[];
  /** Whether data is loading */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
  /** Callback when View button is clicked */
  onViewCitation?: (citationId: string) => void;
  /** Callback when Fix button is clicked */
  onFixCitation?: (citationId: string) => void;
  /** Callback when document name is clicked */
  onDocumentClick?: (documentId: string, page: number) => void;
  className?: string;
}

/**
 * Get status icon for verification status.
 */
function getStatusIcon(status: VerificationStatus): {
  icon: React.ReactNode;
  className: string;
  label: string;
} {
  switch (status) {
    case 'verified':
      return {
        icon: <CheckCircle className="h-4 w-4" />,
        className: 'text-green-600 dark:text-green-400',
        label: 'Verified',
      };
    case 'mismatch':
      return {
        icon: <AlertTriangle className="h-4 w-4" />,
        className: 'text-destructive',
        label: 'Mismatch',
      };
    case 'section_not_found':
      return {
        icon: <HelpCircle className="h-4 w-4" />,
        className: 'text-amber-600 dark:text-amber-400',
        label: 'Not Found',
      };
    case 'act_unavailable':
    case 'pending':
    default:
      return {
        icon: <Clock className="h-4 w-4" />,
        className: 'text-muted-foreground',
        label: 'Pending',
      };
  }
}

/**
 * Check if any citation in the list has an issue.
 */
function hasIssues(citations: CitationListItem[]): boolean {
  return citations.some((c) =>
    ['mismatch', 'section_not_found'].includes(c.verificationStatus)
  );
}

/**
 * Get unique pages from citations.
 */
function getUniquePages(citations: CitationListItem[]): number[] {
  const pages = new Set(citations.map((c) => c.sourcePage));
  return Array.from(pages).sort((a, b) => a - b);
}

/**
 * CitationsByDocumentView - Displays citations grouped by document.
 *
 * @example
 * ```tsx
 * <CitationsByDocumentView
 *   citations={citations}
 *   onViewCitation={handleView}
 * />
 * ```
 */
export function CitationsByDocumentView({
  citations,
  isLoading = false,
  error = null,
  onViewCitation,
  onFixCitation,
  onDocumentClick,
  className,
}: CitationsByDocumentViewProps) {
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  // Group citations by document
  const citationsByDocument = useMemo(() => {
    const groups = new Map<string, { name: string; citations: CitationListItem[] }>();

    citations.forEach((citation) => {
      const docId = citation.documentId;
      const existing = groups.get(docId);

      if (existing) {
        existing.citations.push(citation);
      } else {
        groups.set(docId, {
          name: citation.documentName ?? 'Unknown Document',
          citations: [citation],
        });
      }
    });

    // Sort citations within each document by page
    groups.forEach((group) => {
      group.citations.sort((a, b) => a.sourcePage - b.sourcePage);
    });

    return groups;
  }, [citations]);

  // Toggle document expansion
  const toggleDocument = (docId: string) => {
    setExpandedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className={cn('space-y-4', className)}>
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('rounded-lg border border-destructive/20 bg-destructive/5 p-4', className)}>
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  if (citations.length === 0) {
    return (
      <div className={cn('rounded-lg border border-muted bg-muted/50 p-8 text-center', className)}>
        <p className="text-muted-foreground">No citations found</p>
      </div>
    );
  }

  // Get sorted document IDs (by document name)
  const sortedDocs = Array.from(citationsByDocument.entries()).sort((a, b) =>
    a[1].name.localeCompare(b[1].name)
  );

  return (
    <div className={cn('space-y-2', className)}>
      {sortedDocs.map(([docId, { name, citations: docCitations }]) => {
        const isExpanded = expandedDocs.has(docId);
        const uniquePages = getUniquePages(docCitations);
        const docHasIssues = hasIssues(docCitations);

        return (
          <Collapsible
            key={docId}
            open={isExpanded}
            onOpenChange={() => toggleDocument(docId)}
          >
            <div className="rounded-lg border">
              {/* Document Header */}
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    'flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/50 rounded-lg transition-colors',
                    docHasIssues && 'bg-destructive/5'
                  )}
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-5 w-5 text-muted-foreground" />
                    )}
                    <FileText className="h-5 w-5 text-primary" />
                    <div className="flex flex-col">
                      <span className="font-medium">{name}</span>
                      <span className="text-sm text-muted-foreground">
                        {docCitations.length} citation{docCitations.length !== 1 ? 's' : ''} on {uniquePages.length} page{uniquePages.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {docHasIssues && (
                      <Badge variant="destructive" className="gap-1">
                        <AlertTriangle className="h-3 w-3" />
                        Issues
                      </Badge>
                    )}
                    <Badge variant="secondary">
                      Pages: {uniquePages[0]}-{uniquePages[uniquePages.length - 1]}
                    </Badge>
                  </div>
                </button>
              </CollapsibleTrigger>

              {/* Document Content */}
              <CollapsibleContent>
                <div className="border-t">
                  {/* Citations table */}
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/30">
                        <th className="px-4 py-2 text-left font-medium w-16">Page</th>
                        <th className="px-4 py-2 text-left font-medium">Citation</th>
                        <th className="px-4 py-2 text-left font-medium w-32">Status</th>
                        <th className="px-4 py-2 text-left font-medium w-24">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {docCitations.map((citation) => {
                        const statusInfo = getStatusIcon(citation.verificationStatus);
                        const isIssue = ['mismatch', 'section_not_found'].includes(citation.verificationStatus);

                        return (
                          <tr
                            key={citation.id}
                            className={cn(
                              'border-b last:border-b-0',
                              isIssue && 'bg-destructive/5'
                            )}
                          >
                            <td className="px-4 py-2">
                              <button
                                type="button"
                                className="text-primary hover:underline"
                                onClick={() => onDocumentClick?.(docId, citation.sourcePage)}
                              >
                                {citation.sourcePage}
                              </button>
                            </td>
                            <td className="px-4 py-2">
                              <div className="flex flex-col">
                                <span className="font-medium">
                                  {citation.actName} § {citation.sectionNumber}
                                  {citation.subsection && `.${citation.subsection}`}
                                  {citation.clause && `(${citation.clause})`}
                                </span>
                                <span className="text-muted-foreground text-xs line-clamp-1">
                                  {citation.rawCitationText || '-'}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-2">
                              <div className={cn('flex items-center gap-1.5', statusInfo.className)}>
                                {statusInfo.icon}
                                <span>{statusInfo.label}</span>
                              </div>
                            </td>
                            <td className="px-4 py-2">
                              <div className="flex items-center gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2"
                                  onClick={() => onViewCitation?.(citation.id)}
                                >
                                  <Eye className="h-3.5 w-3.5" />
                                </Button>
                                {isIssue && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2 text-destructive hover:text-destructive"
                                    onClick={() => onFixCitation?.(citation.id)}
                                  >
                                    <Wrench className="h-3.5 w-3.5" />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}

CitationsByDocumentView.displayName = 'CitationsByDocumentView';
