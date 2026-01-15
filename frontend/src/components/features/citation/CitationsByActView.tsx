'use client';

/**
 * CitationsByActView Component
 *
 * Displays citations grouped by Act in expandable sections.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Scale,
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
import type { CitationListItem, CitationSummaryItem, VerificationStatus } from '@/types/citation';

export interface CitationsByActViewProps {
  /** Citations to display */
  citations: CitationListItem[];
  /** Summary data for Act headers */
  summary: CitationSummaryItem[];
  /** Whether data is loading */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
  /** Callback when View button is clicked */
  onViewCitation?: (citationId: string) => void;
  /** Callback when Fix button is clicked */
  onFixCitation?: (citationId: string) => void;
  className?: string;
}

/**
 * Get status icon for verification status.
 */
function getStatusIcon(status: VerificationStatus): {
  icon: React.ReactNode;
  className: string;
} {
  switch (status) {
    case 'verified':
      return {
        icon: <CheckCircle className="h-4 w-4" />,
        className: 'text-green-600 dark:text-green-400',
      };
    case 'mismatch':
      return {
        icon: <AlertTriangle className="h-4 w-4" />,
        className: 'text-destructive',
      };
    case 'section_not_found':
      return {
        icon: <HelpCircle className="h-4 w-4" />,
        className: 'text-amber-600 dark:text-amber-400',
      };
    case 'act_unavailable':
    case 'pending':
    default:
      return {
        icon: <Clock className="h-4 w-4" />,
        className: 'text-muted-foreground',
      };
  }
}

/**
 * Group citations by section within an Act.
 */
function groupCitationsBySection(citations: CitationListItem[]): Map<string, CitationListItem[]> {
  const groups = new Map<string, CitationListItem[]>();

  citations.forEach((citation) => {
    let sectionKey = citation.sectionNumber;
    if (citation.subsection) {
      sectionKey += `.${citation.subsection}`;
    }
    if (citation.clause) {
      sectionKey += `(${citation.clause})`;
    }

    const existing = groups.get(sectionKey) ?? [];
    groups.set(sectionKey, [...existing, citation]);
  });

  return groups;
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
 * CitationsByActView - Displays citations grouped by Act.
 *
 * @example
 * ```tsx
 * <CitationsByActView
 *   citations={citations}
 *   summary={summary}
 *   onViewCitation={handleView}
 * />
 * ```
 */
export function CitationsByActView({
  citations,
  summary,
  isLoading = false,
  error = null,
  onViewCitation,
  onFixCitation,
  className,
}: CitationsByActViewProps) {
  const [expandedActs, setExpandedActs] = useState<Set<string>>(new Set());

  // Group citations by Act
  const citationsByAct = useMemo(() => {
    const groups = new Map<string, CitationListItem[]>();

    citations.forEach((citation) => {
      const existing = groups.get(citation.actName) ?? [];
      groups.set(citation.actName, [...existing, citation]);
    });

    return groups;
  }, [citations]);

  // Toggle Act expansion
  const toggleAct = (actName: string) => {
    setExpandedActs((prev) => {
      const next = new Set(prev);
      if (next.has(actName)) {
        next.delete(actName);
      } else {
        next.add(actName);
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

  // Get sorted act names
  const actNames = Array.from(citationsByAct.keys()).sort();

  return (
    <div className={cn('space-y-2', className)}>
      {actNames.map((actName) => {
        const actCitations = citationsByAct.get(actName) ?? [];
        const isExpanded = expandedActs.has(actName);
        const summaryItem = summary.find((s) => s.actName === actName);
        const sectionGroups = groupCitationsBySection(actCitations);
        const actHasIssues = hasIssues(actCitations);

        return (
          <Collapsible
            key={actName}
            open={isExpanded}
            onOpenChange={() => toggleAct(actName)}
          >
            <div className="rounded-lg border">
              {/* Act Header */}
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    'flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/50 rounded-lg transition-colors',
                    actHasIssues && 'bg-destructive/5'
                  )}
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-5 w-5 text-muted-foreground" />
                    )}
                    <Scale className="h-5 w-5 text-primary" />
                    <div className="flex flex-col">
                      <span className="font-medium">{actName}</span>
                      <span className="text-sm text-muted-foreground">
                        {actCitations.length} citation{actCitations.length !== 1 ? 's' : ''} in {sectionGroups.size} section{sectionGroups.size !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {actHasIssues && (
                      <Badge variant="destructive" className="gap-1">
                        <AlertTriangle className="h-3 w-3" />
                        Issues
                      </Badge>
                    )}
                    {summaryItem && (
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <span className="text-green-600">{summaryItem.verifiedCount} verified</span>
                        {summaryItem.pendingCount > 0 && (
                          <>
                            <span>|</span>
                            <span>{summaryItem.pendingCount} pending</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              </CollapsibleTrigger>

              {/* Act Content */}
              <CollapsibleContent>
                <div className="border-t px-4 py-3 space-y-4">
                  {/* Section breakdown */}
                  {Array.from(sectionGroups.entries()).map(([sectionKey, sectionCitations]) => {
                    const sectionHasIssues = hasIssues(sectionCitations);

                    return (
                      <div key={sectionKey} className="space-y-2">
                        <div className={cn(
                          'flex items-center justify-between px-2 py-1.5 rounded bg-muted/30',
                          sectionHasIssues && 'bg-destructive/10'
                        )}>
                          <span className="font-medium text-sm">
                            Section {sectionKey}
                            <span className="text-muted-foreground ml-2">
                              ({sectionCitations.length} citation{sectionCitations.length !== 1 ? 's' : ''})
                            </span>
                          </span>
                          {sectionHasIssues && (
                            <span className="text-xs text-destructive flex items-center gap-1">
                              <AlertTriangle className="h-3 w-3" />
                              Section may have issues
                            </span>
                          )}
                        </div>

                        {/* Citations in this section */}
                        <div className="space-y-1 pl-4">
                          {sectionCitations.map((citation) => {
                            const statusInfo = getStatusIcon(citation.verificationStatus);
                            const isIssue = ['mismatch', 'section_not_found'].includes(citation.verificationStatus);

                            return (
                              <div
                                key={citation.id}
                                className={cn(
                                  'flex items-center justify-between p-2 rounded text-sm',
                                  isIssue && 'bg-destructive/5'
                                )}
                              >
                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                  <span className={statusInfo.className}>
                                    {statusInfo.icon}
                                  </span>
                                  <span className="truncate">
                                    {citation.rawCitationText || `Section ${sectionKey}`}
                                  </span>
                                  <span className="text-muted-foreground text-xs flex-shrink-0">
                                    p.{citation.sourcePage}
                                  </span>
                                </div>
                                <div className="flex items-center gap-1 ml-2">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2"
                                    onClick={() => onViewCitation?.(citation.id)}
                                  >
                                    <Eye className="h-3.5 w-3.5 mr-1" />
                                    View
                                  </Button>
                                  {isIssue && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-7 px-2 text-destructive hover:text-destructive"
                                      onClick={() => onFixCitation?.(citation.id)}
                                    >
                                      <Wrench className="h-3.5 w-3.5 mr-1" />
                                      Fix
                                    </Button>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}

CitationsByActView.displayName = 'CitationsByActView';
