'use client';

/**
 * Citations List Component
 *
 * Displays citations in a sortable table with enhanced columns.
 * Split-view rendering is now handled at CitationsContent level (Story 10C.4).
 *
 * @see Story 3-4: Split-View Citation Highlighting
 * @see Story 10C.3: Citations Tab List and Act Discovery
 * @see Story 10C.4: Split-View Verification Integration
 */

import { useState, useCallback, useMemo } from 'react';
import {
  Eye,
  AlertTriangle,
  CheckCircle,
  Clock,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Wrench,
  FileText,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import type { CitationListItem, VerificationStatus, PaginationMeta } from '@/types/citation';

export interface CitationsListProps {
  /** Citations to display */
  citations: CitationListItem[];
  /** Pagination metadata */
  meta: PaginationMeta | null;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
  /** Current page */
  currentPage?: number;
  /** Callback when page changes */
  onPageChange?: (page: number) => void;
  /** Callback when document name is clicked */
  onDocumentClick?: (documentId: string, page: number) => void;
  /** Callback when view citation button is clicked */
  onViewCitation?: (citationId: string) => void;
}

type SortField = 'actName' | 'sectionNumber' | 'verificationStatus' | 'confidence' | 'sourcePage';
type SortDirection = 'asc' | 'desc';

/**
 * Get status badge variant and icon for verification status.
 */
function getStatusBadge(status: VerificationStatus): {
  variant: 'default' | 'destructive' | 'outline' | 'secondary';
  icon: React.ReactNode;
  label: string;
} {
  switch (status) {
    case 'verified':
      return {
        variant: 'default',
        icon: <CheckCircle className="h-3 w-3" />,
        label: 'Verified',
      };
    case 'mismatch':
      return {
        variant: 'destructive',
        icon: <AlertTriangle className="h-3 w-3" />,
        label: 'Mismatch',
      };
    case 'section_not_found':
      return {
        variant: 'secondary',
        icon: <HelpCircle className="h-3 w-3" />,
        label: 'Not Found',
      };
    case 'act_unavailable':
      return {
        variant: 'outline',
        icon: <Clock className="h-3 w-3" />,
        label: 'No Act',
      };
    case 'pending':
    default:
      return {
        variant: 'outline',
        icon: <Clock className="h-3 w-3" />,
        label: 'Pending',
      };
  }
}

/**
 * Get confidence color based on value.
 */
function getConfidenceColor(confidence: number): string {
  if (confidence >= 90) return 'text-green-600 dark:text-green-400';
  if (confidence >= 70) return 'text-amber-600 dark:text-amber-400';
  return 'text-destructive';
}

const ITEMS_PER_PAGE = 20;

/**
 * Citations List component with sortable columns and split view integration.
 *
 * @example
 * ```tsx
 * <CitationsList
 *   matterId="matter-123"
 *   citations={citations}
 *   meta={meta}
 *   isLoading={isLoading}
 *   onPageChange={setPage}
 *   onDocumentClick={handleDocClick}
 * />
 * ```
 */
export function CitationsList({
  citations,
  meta,
  isLoading = false,
  error = null,
  currentPage = 1,
  onPageChange,
  onDocumentClick,
  onViewCitation,
}: CitationsListProps) {
  const [sortField, setSortField] = useState<SortField>('actName');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Sort citations client-side
  const sortedCitations = useMemo(() => {
    return [...citations].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'actName':
          comparison = a.actName.localeCompare(b.actName);
          break;
        case 'sectionNumber':
          comparison = a.sectionNumber.localeCompare(b.sectionNumber, undefined, { numeric: true });
          break;
        case 'verificationStatus':
          comparison = a.verificationStatus.localeCompare(b.verificationStatus);
          break;
        case 'confidence':
          comparison = a.confidence - b.confidence;
          break;
        case 'sourcePage':
          comparison = a.sourcePage - b.sourcePage;
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [citations, sortField, sortDirection]);

  // Handle sort click
  const handleSort = useCallback((field: SortField) => {
    setSortField((prevField) => {
      if (prevField === field) {
        setSortDirection((prevDir) => (prevDir === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortDirection('asc');
      }
      return field;
    });
  }, []);

  // Handle page change
  const totalPages = meta?.totalPages ?? Math.ceil((meta?.total ?? 0) / ITEMS_PER_PAGE);
  const handlePageChange = (newPage: number) => {
    if (onPageChange && newPage >= 1 && newPage <= totalPages) {
      onPageChange(newPage);
    }
  };

  // Handle view citation click - delegate to parent (Story 10C.4)
  const handleViewCitation = useCallback(
    (citationId: string) => {
      onViewCitation?.(citationId);
    },
    [onViewCitation]
  );

  // Handle document click
  const handleDocumentClick = (documentId: string, page: number) => {
    if (onDocumentClick) {
      onDocumentClick(documentId, page);
    }
  };

  // Get sort icon for column header
  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-4 w-4 ml-1 text-muted-foreground/50" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="h-4 w-4 ml-1" />
    ) : (
      <ArrowDown className="h-4 w-4 ml-1" />
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  if (citations.length === 0) {
    return (
      <div className="rounded-lg border border-muted bg-muted/50 p-8 text-center">
        <p className="text-muted-foreground">No citations found</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Citations Table */}
      <div className="rounded-lg border">
        {/* Pagination header */}
        {meta && meta.total > ITEMS_PER_PAGE && (
          <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
            <span className="text-sm text-muted-foreground">
              Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, meta.total)} of {meta.total} citations
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage >= totalPages}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                className="w-[200px]"
                aria-sort={sortField === 'actName' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button
                  type="button"
                  className="flex items-center hover:text-foreground"
                  onClick={() => handleSort('actName')}
                >
                  Act Name
                  {getSortIcon('actName')}
                </button>
              </TableHead>
              <TableHead
                className="w-[100px]"
                aria-sort={sortField === 'sectionNumber' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button
                  type="button"
                  className="flex items-center hover:text-foreground"
                  onClick={() => handleSort('sectionNumber')}
                >
                  Section
                  {getSortIcon('sectionNumber')}
                </button>
              </TableHead>
              <TableHead>Citation Text</TableHead>
              <TableHead className="w-[150px]">Source Doc</TableHead>
              <TableHead
                className="w-[120px]"
                aria-sort={sortField === 'verificationStatus' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button
                  type="button"
                  className="flex items-center hover:text-foreground"
                  onClick={() => handleSort('verificationStatus')}
                >
                  Status
                  {getSortIcon('verificationStatus')}
                </button>
              </TableHead>
              <TableHead
                className="w-[80px]"
                aria-sort={sortField === 'confidence' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button
                  type="button"
                  className="flex items-center hover:text-foreground"
                  onClick={() => handleSort('confidence')}
                >
                  Conf.
                  {getSortIcon('confidence')}
                </button>
              </TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedCitations.map((citation) => {
              const statusBadge = getStatusBadge(citation.verificationStatus);
              const isIssue = ['mismatch', 'section_not_found'].includes(citation.verificationStatus);

              return (
                <TableRow key={citation.id} className={isIssue ? 'bg-destructive/5' : ''}>
                  <TableCell className="font-medium">
                    {citation.actName}
                  </TableCell>
                  <TableCell>
                    {citation.sectionNumber}
                    {citation.subsection && `.${citation.subsection}`}
                    {citation.clause && `(${citation.clause})`}
                  </TableCell>
                  <TableCell className="max-w-[300px]">
                    <span className="line-clamp-2 text-sm">
                      {citation.rawCitationText || '-'}
                    </span>
                  </TableCell>
                  <TableCell>
                    {citation.documentName ? (
                      <button
                        type="button"
                        className="flex items-center gap-1 text-sm text-primary hover:underline max-w-[140px]"
                        onClick={() => handleDocumentClick(citation.documentId, citation.sourcePage)}
                        title={`${citation.documentName}, Page ${citation.sourcePage}`}
                      >
                        <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate">{citation.documentName}</span>
                        <span className="text-muted-foreground flex-shrink-0">p.{citation.sourcePage}</span>
                      </button>
                    ) : (
                      <span className="text-muted-foreground">Page {citation.sourcePage}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusBadge.variant} className="gap-1">
                      {statusBadge.icon}
                      {statusBadge.label}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className={`font-medium ${getConfidenceColor(citation.confidence)}`}>
                      {citation.confidence.toFixed(0)}%
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleViewCitation(citation.id)}
                        title="View in split view"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      {isIssue && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleViewCitation(citation.id)}
                          title="Fix issue"
                          className="text-destructive hover:text-destructive"
                        >
                          <Wrench className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

CitationsList.displayName = 'CitationsList';
