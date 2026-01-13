'use client';

/**
 * Citations List Component
 *
 * Story 3-4: Split-View Citation Highlighting
 *
 * Displays a list of citations with ability to open split view.
 * This is the basic integration component for the Citations Tab.
 */

import { useState, useEffect, useCallback } from 'react';
import { Eye, AlertTriangle, CheckCircle, Clock, HelpCircle, ChevronLeft, ChevronRight } from 'lucide-react';
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
import { getCitations } from '@/lib/api/citations';
import { useSplitView } from '@/hooks/useSplitView';
import { SplitViewCitationPanel } from './SplitViewCitationPanel';
import { SplitViewModal } from './SplitViewModal';
import type { CitationListItem, VerificationStatus } from '@/types/citation';

export interface CitationsListProps {
  /** Matter ID to list citations for */
  matterId: string;
  /** Optional Act name filter */
  actName?: string;
}

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
 * Citations List component.
 *
 * Displays citations in a table with ability to open split view for each.
 *
 * @example
 * ```tsx
 * <CitationsList matterId="matter-123" />
 * ```
 */
const ITEMS_PER_PAGE = 20;

export function CitationsList({ matterId, actName }: CitationsListProps) {
  const [citations, setCitations] = useState<CitationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const {
    isOpen,
    isFullScreen,
    splitViewData,
    isLoading: splitViewLoading,
    error: splitViewError,
    navigationInfo,
    openSplitView,
    closeSplitView,
    toggleFullScreen,
    navigateToPrev,
    navigateToNext,
    setCitationIds,
  } = useSplitView({ enableKeyboardShortcuts: true });

  // Load citations with pagination
  const loadCitations = useCallback(async (page: number) => {
    setLoading(true);
    setError(null);

    try {
      const response = await getCitations(matterId, {
        page,
        perPage: ITEMS_PER_PAGE,
        actName,
      });
      setCitations(response.data);
      setTotalCount(response.meta.total);
      setTotalPages(response.meta.totalPages ?? Math.ceil(response.meta.total / ITEMS_PER_PAGE));
      setCurrentPage(page);

      // Set citation IDs for navigation
      setCitationIds(response.data.map((c) => c.id));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load citations';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [matterId, actName, setCitationIds]);

  // Initial load and reload on filter change
  useEffect(() => {
    loadCitations(1);
  }, [loadCitations]);

  // Handle page change
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      loadCitations(newPage);
    }
  };

  // Handle view citation click
  const handleViewCitation = (citationId: string) => {
    openSplitView(citationId, matterId);
  };

  if (loading) {
    return (
      <div className="space-y-4">
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
        {totalCount > ITEMS_PER_PAGE && (
          <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
            <span className="text-sm text-muted-foreground">
              Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, totalCount)} of {totalCount} citations
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
              <TableHead className="w-[200px]">Act</TableHead>
              <TableHead className="w-[100px]">Section</TableHead>
              <TableHead>Citation Text</TableHead>
              <TableHead className="w-[80px]">Page</TableHead>
              <TableHead className="w-[120px]">Status</TableHead>
              <TableHead className="w-[80px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {citations.map((citation) => {
              const statusBadge = getStatusBadge(citation.verificationStatus);

              return (
                <TableRow key={citation.id}>
                  <TableCell className="font-medium">
                    {citation.actName}
                  </TableCell>
                  <TableCell>
                    {citation.sectionNumber}
                    {citation.subsection && `.${citation.subsection}`}
                    {citation.clause && `(${citation.clause})`}
                  </TableCell>
                  <TableCell className="max-w-[300px] truncate">
                    {citation.rawCitationText || '-'}
                  </TableCell>
                  <TableCell>{citation.sourcePage}</TableCell>
                  <TableCell>
                    <Badge variant={statusBadge.variant} className="gap-1">
                      {statusBadge.icon}
                      {statusBadge.label}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleViewCitation(citation.id)}
                      title="View in split view"
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Split View Panel (conditional) */}
      {isOpen && !isFullScreen && splitViewData && (
        <SplitViewCitationPanel
          data={splitViewData}
          isFullScreen={false}
          isLoading={splitViewLoading}
          error={splitViewError}
          navigationInfo={navigationInfo}
          onClose={closeSplitView}
          onToggleFullScreen={toggleFullScreen}
          onPrev={navigateToPrev}
          onNext={navigateToNext}
        />
      )}

      {/* Full Screen Modal (conditional) */}
      {isOpen && isFullScreen && (
        <SplitViewModal
          data={splitViewData}
          isOpen={isFullScreen}
          isLoading={splitViewLoading}
          error={splitViewError}
          navigationInfo={navigationInfo}
          onClose={closeSplitView}
          onExitFullScreen={toggleFullScreen}
          onPrev={navigateToPrev}
          onNext={navigateToNext}
        />
      )}
    </div>
  );
}
