'use client';

/**
 * CitationsContent Component
 *
 * Main container for the Citations tab, managing view modes, filters,
 * and integrating all citation-related components including split-view.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 * @see Story 10C.4 - Split-View Verification Integration
 */

import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { CitationsHeader, CitationsViewMode, CitationsFilterState } from './CitationsHeader';
import { CitationsAttentionBanner } from './CitationsAttentionBanner';
import { CitationsList } from './CitationsList';
import { CitationsByActView } from './CitationsByActView';
import { CitationsByDocumentView } from './CitationsByDocumentView';
import { MissingActsCard } from './MissingActsCard';
import { SplitViewCitationPanel } from './SplitViewCitationPanel';
import { SplitViewModal } from './SplitViewModal';
import { PdfErrorBoundary } from '../pdf';
import {
  useCitationsList,
  useCitationStats,
  useCitationSummaryByAct,
  useActDiscoveryReport,
  useActMutations,
  getActNamesFromSummary,
} from '@/hooks/useCitations';
import { useSplitView } from '@/hooks/useSplitView';
import type { SplitViewData } from '@/types/citation';

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
  const [debouncedFilters, setDebouncedFilters] = useState<CitationsFilterState>(DEFAULT_FILTERS);
  const [currentPage, setCurrentPage] = useState(1);
  const [showMissingActsCard, setShowMissingActsCard] = useState(false);
  const filterDebounceRef = useRef<NodeJS.Timeout | null>(null);

  // Debounce filter changes to avoid excessive API calls
  useEffect(() => {
    if (filterDebounceRef.current) {
      clearTimeout(filterDebounceRef.current);
    }
    filterDebounceRef.current = setTimeout(() => {
      setDebouncedFilters(filters);
    }, 300);

    return () => {
      if (filterDebounceRef.current) {
        clearTimeout(filterDebounceRef.current);
      }
    };
  }, [filters]);

  // Split view hook - all state and actions at CitationsContent level (Story 10C.4)
  const {
    isOpen: isSplitViewOpen,
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
    filters: debouncedFilters,
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

  // Set citation IDs for split-view navigation when citations change (Story 10C.4)
  useEffect(() => {
    if (citations.length > 0) {
      setCitationIds(citations.map((c) => c.id));
    }
  }, [citations, setCitationIds]);

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

  // Render citations content based on viewMode
  const renderCitationsContent = () => (
    <div className="flex gap-4 h-full">
      {/* Main content - view based on viewMode */}
      <div className="flex-1 min-w-0 overflow-auto">
        {viewMode === 'list' && (
          <CitationsList
            citations={citations}
            meta={meta}
            isLoading={citationsLoading}
            error={citationsError?.message}
            currentPage={currentPage}
            onPageChange={handlePageChange}
            onDocumentClick={handleDocumentClick}
            onViewCitation={handleViewCitation}
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
  );

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

      {/* Main content area - with split-view when open */}
      <div className="flex-1 min-h-0">
        {isSplitViewOpen && !isFullScreen && (splitViewData || splitViewLoading || splitViewError) ? (
          // Split layout: citations content + split-view panels side by side
          <PanelGroup direction="horizontal" className="h-full">
            {/* Citations content panel (resizable) */}
            <Panel defaultSize={35} minSize={20} className="overflow-auto">
              {renderCitationsContent()}
            </Panel>

            {/* Resize handle */}
            <PanelResizeHandle className="w-2 bg-border hover:bg-primary/20 transition-colors flex items-center justify-center group">
              <GripVertical className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </PanelResizeHandle>

            {/* Split-view panel */}
            <Panel defaultSize={65} minSize={40}>
              {splitViewLoading && !splitViewData ? (
                // Show dedicated loading state when data hasn't loaded yet
                <div className="h-full flex flex-col items-center justify-center border-l bg-background">
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    <p className="text-sm text-muted-foreground">Loading citation view...</p>
                  </div>
                </div>
              ) : splitViewError && !splitViewData ? (
                // Show error state when there's an error and no data
                <div className="h-full flex flex-col items-center justify-center border-l bg-background">
                  <div className="flex flex-col items-center gap-2 text-center px-4">
                    <p className="text-sm text-destructive">{splitViewError}</p>
                    <button
                      onClick={closeSplitView}
                      className="text-sm text-primary hover:underline"
                    >
                      Close
                    </button>
                  </div>
                </div>
              ) : splitViewData ? (
                // Show the panel only when data is available, wrapped in error boundary
                <PdfErrorBoundary
                  fallbackMessage="Failed to load citation split view. Please try again."
                  onRetry={() => {
                    // Re-open the split view to trigger a reload
                    if (splitViewData?.citation?.id) {
                      openSplitView(splitViewData.citation.id, matterId);
                    }
                  }}
                >
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
                </PdfErrorBoundary>
              ) : null}
            </Panel>
          </PanelGroup>
        ) : (
          // Normal layout: citations content without split-view
          renderCitationsContent()
        )}
      </div>

      {/* Full-screen modal */}
      <SplitViewModal
        isOpen={isSplitViewOpen && isFullScreen}
        data={splitViewData}
        navigationInfo={navigationInfo}
        isLoading={splitViewLoading}
        error={splitViewError}
        onClose={closeSplitView}
        onExitFullScreen={toggleFullScreen}
        onPrev={navigateToPrev}
        onNext={navigateToNext}
      />
    </div>
  );
}

CitationsContent.displayName = 'CitationsContent';
