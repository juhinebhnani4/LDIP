'use client';

/**
 * CitationsContent Component
 *
 * Main container for the Citations tab, managing view modes, filters,
 * and integrating all citation-related components.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { useCallback, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { CitationsHeader, CitationsViewMode, CitationsFilterState } from './CitationsHeader';
import { CitationsAttentionBanner } from './CitationsAttentionBanner';
import { CitationsList } from './CitationsList';
import { CitationsByActView } from './CitationsByActView';
import { CitationsByDocumentView } from './CitationsByDocumentView';
import { MissingActsCard } from './MissingActsCard';
import {
  useCitationsList,
  useCitationStats,
  useCitationSummaryByAct,
  useActDiscoveryReport,
  useActMutations,
  getActNamesFromSummary,
} from '@/hooks/useCitations';
import { useSplitView } from '@/hooks/useSplitView';

export interface CitationsContentProps {
  matterId: string;
  onViewInDocument?: (documentId: string, page: number) => void;
  className?: string;
}

const DEFAULT_FILTERS: CitationsFilterState = {
  verificationStatus: null,
  actName: null,
  showOnlyIssues: false,
};

export function CitationsContent({
  matterId,
  onViewInDocument,
  className,
}: CitationsContentProps) {
  // View state
  const [viewMode, setViewMode] = useState<CitationsViewMode>('list');
  const [filters, setFilters] = useState<CitationsFilterState>(DEFAULT_FILTERS);
  const [currentPage, setCurrentPage] = useState(1);
  const [showMissingActsCard, setShowMissingActsCard] = useState(false);

  // Split view hook
  const { openSplitView } = useSplitView({ enableKeyboardShortcuts: true });

  // Fetch data
  const { stats, isLoading: statsLoading, mutate: refreshStats } = useCitationStats(matterId);
  const { summary, isLoading: summaryLoading, mutate: refreshSummary } = useCitationSummaryByAct(matterId);
  const {
    acts,
    missingCount,
    isLoading: actsLoading,
    mutate: refreshActs,
  } = useActDiscoveryReport(matterId);
  const {
    citations,
    meta,
    isLoading: citationsLoading,
    error: citationsError,
    mutate: refreshCitations,
  } = useCitationsList(matterId, {
    page: currentPage,
    perPage: 20,
    filters,
  });

  // Act mutations
  const { markUploadedAndVerify, markSkipped, isLoading: mutationLoading } = useActMutations(matterId);

  // Computed values
  const actNames = useMemo(() => getActNamesFromSummary(summary), [summary]);
  const issueCount = useMemo(() => {
    if (!stats) return 0;
    return Math.max(0, stats.totalCitations - stats.verifiedCount - stats.pendingCount);
  }, [stats]);

  const isLoading = statsLoading || summaryLoading || actsLoading;

  // Handle view mode change
  const handleViewModeChange = useCallback((mode: CitationsViewMode) => {
    setViewMode(mode);
  }, []);

  // Handle filter change
  const handleFiltersChange = useCallback((newFilters: CitationsFilterState) => {
    setFilters(newFilters);
    setCurrentPage(1); // Reset to page 1 when filters change
  }, []);

  // Handle page change
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // Handle "Review Issues" from attention banner
  const handleReviewIssues = useCallback(() => {
    setFilters({
      ...filters,
      showOnlyIssues: true,
    });
  }, [filters]);

  // Handle "Upload Missing Acts" from attention banner
  const handleUploadMissingActs = useCallback(() => {
    setShowMissingActsCard(true);
  }, []);

  // Handle view citation in split view
  const handleViewCitation = useCallback(
    (citationId: string) => {
      openSplitView(citationId, matterId);
    },
    [openSplitView, matterId]
  );

  // Handle fix citation (same as view for now)
  const handleFixCitation = useCallback(
    (citationId: string) => {
      openSplitView(citationId, matterId);
    },
    [openSplitView, matterId]
  );

  // Handle document click
  const handleDocumentClick = useCallback(
    (documentId: string, page: number) => {
      onViewInDocument?.(documentId, page);
    },
    [onViewInDocument]
  );

  // Handle Act upload and verify
  const handleActUploadedAndVerify = useCallback(
    async (actName: string, documentId: string) => {
      await markUploadedAndVerify({ actName, actDocumentId: documentId });
    },
    [markUploadedAndVerify]
  );

  // Handle Act skip
  const handleActSkipped = useCallback(
    async (actName: string) => {
      await markSkipped({ actName });
    },
    [markSkipped]
  );

  // Refresh all data
  const handleRefresh = useCallback(async () => {
    await Promise.all([
      refreshStats(),
      refreshSummary(),
      refreshActs(),
      refreshCitations(),
    ]);
  }, [refreshStats, refreshSummary, refreshActs, refreshCitations]);

  if (isLoading && !stats) {
    return (
      <div className={cn('space-y-4', className)}>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full space-y-4', className)}>
      {/* Header with stats and filters */}
      <CitationsHeader
        stats={stats}
        actNames={actNames}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        filters={filters}
        onFiltersChange={handleFiltersChange}
        isLoading={statsLoading}
      />

      {/* Attention banner for issues */}
      <CitationsAttentionBanner
        issueCount={issueCount}
        missingActsCount={missingCount}
        onReviewIssues={handleReviewIssues}
        onUploadMissingActs={handleUploadMissingActs}
      />

      {/* Main content area with sidebar layout */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Main content - view based on viewMode */}
        <div className="flex-1 min-w-0 overflow-auto">
          {viewMode === 'list' && (
            <CitationsList
              matterId={matterId}
              citations={citations}
              meta={meta}
              isLoading={citationsLoading}
              error={citationsError?.message}
              currentPage={currentPage}
              onPageChange={handlePageChange}
              onDocumentClick={handleDocumentClick}
            />
          )}

          {viewMode === 'byAct' && (
            <CitationsByActView
              citations={citations}
              summary={summary}
              isLoading={citationsLoading}
              error={citationsError?.message}
              onViewCitation={handleViewCitation}
              onFixCitation={handleFixCitation}
            />
          )}

          {viewMode === 'byDocument' && (
            <CitationsByDocumentView
              citations={citations}
              isLoading={citationsLoading}
              error={citationsError?.message}
              onViewCitation={handleViewCitation}
              onFixCitation={handleFixCitation}
              onDocumentClick={handleDocumentClick}
            />
          )}
        </div>

        {/* Sidebar - Missing Acts Card */}
        {(showMissingActsCard || missingCount > 0) && (
          <div className="w-80 flex-shrink-0">
            <MissingActsCard
              matterId={matterId}
              acts={acts}
              isLoading={actsLoading || mutationLoading}
              onActUploadedAndVerify={handleActUploadedAndVerify}
              onActSkipped={handleActSkipped}
              onRefresh={handleRefresh}
            />
          </div>
        )}
      </div>
    </div>
  );
}

CitationsContent.displayName = 'CitationsContent';
