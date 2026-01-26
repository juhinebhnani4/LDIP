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
import { GripVertical, CheckCircle2, AlertTriangle, Wrench, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
import { updateCitationStatus, bulkUpdateCitationStatus } from '@/lib/api/citations';
import type { SplitViewData, VerificationStatus } from '@/types/citation';

export interface CitationsContentProps {
  matterId: string;
  onViewInDocument?: (documentId: string, page: number) => void;
  className?: string;
}

const DEFAULT_FILTERS: CitationsFilterState = {
  verificationStatus: null,
  actName: null,
  showOnlyIssues: false,
  searchQuery: '',
};

const STORAGE_KEY_VIEW_MODE = 'citations-view-mode';
const STORAGE_KEY_GROUPING = 'citations-grouping-enabled';

// Get initial view mode from localStorage or default to 'byAct'
function getInitialViewMode(): CitationsViewMode {
  if (typeof window === 'undefined') return 'byAct';
  const stored = localStorage.getItem(STORAGE_KEY_VIEW_MODE);
  if (stored === 'list' || stored === 'byAct' || stored === 'byDocument') {
    return stored;
  }
  return 'byAct'; // New default
}

export function CitationsContent({
  matterId,
  onViewInDocument,
  className,
}: CitationsContentProps) {
  // View state - default to 'byAct' with localStorage persistence
  const [viewMode, setViewMode] = useState<CitationsViewMode>(getInitialViewMode);
  const [filters, setFilters] = useState<CitationsFilterState>(DEFAULT_FILTERS);
  const [debouncedFilters, setDebouncedFilters] = useState<CitationsFilterState>(DEFAULT_FILTERS);
  const [currentPage, setCurrentPage] = useState(1);
  const [showMissingActsCard, setShowMissingActsCard] = useState(false);
  const filterDebounceRef = useRef<NodeJS.Timeout | null>(null);

  // Grouping state - default to true with localStorage persistence
  const [enableGrouping, setEnableGrouping] = useState(() => {
    if (typeof window === 'undefined') return true;
    const stored = localStorage.getItem(STORAGE_KEY_GROUPING);
    return stored === null ? true : stored === 'true';
  });

  // Bulk selection state
  const [selectedCitations, setSelectedCitations] = useState<Set<string>>(new Set());
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);

  // Track if filters are being debounced (for loading indicator)
  const isFilterDebouncing =
    filters.verificationStatus !== debouncedFilters.verificationStatus ||
    filters.actName !== debouncedFilters.actName ||
    filters.showOnlyIssues !== debouncedFilters.showOnlyIssues ||
    filters.searchQuery !== debouncedFilters.searchQuery;

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
    filters: debouncedFilters,
  });

  // Callback to refresh data after status changes (e.g., marking verified)
  const handleStatusChange = useCallback(() => {
    refreshCitations();
    refreshStats();
  }, [refreshCitations, refreshStats]);

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
    markVerified,
    isMarkingVerified,
    currentCitationId,
  } = useSplitView({ enableKeyboardShortcuts: true, onStatusChange: handleStatusChange });

  // Retry loading the split view data
  const handleSplitViewRetry = useCallback(() => {
    if (currentCitationId) {
      openSplitView(currentCitationId, matterId);
    }
  }, [currentCitationId, openSplitView, matterId]);

  // Act mutations
  const { markUploadedAndVerify, markSkipped, isLoading: mutationLoading } = useActMutations(matterId);

  // Computed values
  const actNames = useMemo(() => getActNamesFromSummary(summary), [summary]);
  const issueCount = useMemo(() => {
    if (!stats) return 0;
    return Math.max(0, stats.totalCitations - stats.verifiedCount - stats.pendingCount);
  }, [stats]);

  // Client-side search filtering
  const filteredCitations = useMemo(() => {
    if (!debouncedFilters.searchQuery.trim()) {
      return citations;
    }
    const query = debouncedFilters.searchQuery.toLowerCase().trim();
    return citations.filter((citation) => {
      // Search in act name
      if (citation.actName.toLowerCase().includes(query)) return true;
      // Search in section number
      if (citation.sectionNumber.toLowerCase().includes(query)) return true;
      // Search in raw citation text
      if (citation.rawCitationText?.toLowerCase().includes(query)) return true;
      return false;
    });
  }, [citations, debouncedFilters.searchQuery]);

  const isLoading = statsLoading || summaryLoading || actsLoading;

  // Set citation IDs for split-view navigation when citations change (Story 10C.4)
  // Only update when we have citations to avoid unnecessary store updates
  useEffect(() => {
    if (filteredCitations.length > 0) {
      setCitationIds(filteredCitations.map((c) => c.id));
    }
  }, [filteredCitations, setCitationIds]);

  // Close split view if current citation is no longer in the filtered list
  // This ensures the split view respects active filters
  // Use a ref to store the close action to avoid dependency on closeSplitView
  const closeSplitViewRef = useRef(closeSplitView);
  closeSplitViewRef.current = closeSplitView;

  useEffect(() => {
    // Only check when split view is open and we have data loaded
    if (!isSplitViewOpen || !splitViewData || filteredCitations.length === 0) {
      return;
    }

    const currentCitationInList = filteredCitations.some(
      (c) => c.id === splitViewData.citation.id
    );

    // If the current citation is not in the filtered list, close the split view
    // This handles cases like: viewing a "pending" citation then filtering to "mismatch"
    if (!currentCitationInList) {
      closeSplitViewRef.current();
    }
  }, [citations, isSplitViewOpen, splitViewData]);

  // Handle view mode change with localStorage persistence
  const handleViewModeChange = useCallback((mode: CitationsViewMode) => {
    setViewMode(mode);
    localStorage.setItem(STORAGE_KEY_VIEW_MODE, mode);
  }, []);

  // Handle grouping toggle with localStorage persistence
  const handleGroupingToggle = useCallback((enabled: boolean) => {
    setEnableGrouping(enabled);
    localStorage.setItem(STORAGE_KEY_GROUPING, String(enabled));
  }, []);

  // Handle filter change
  const handleFiltersChange = useCallback((newFilters: CitationsFilterState) => {
    setFilters(newFilters);
    setCurrentPage(1); // Reset to page 1 when filters change
  }, []);

  // Handle page change - clear selection when changing pages
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
    setSelectedCitations(new Set()); // Clear selection on page change
  }, []);

  // Handle selection change from CitationsList
  const handleSelectionChange = useCallback((newSelection: Set<string>) => {
    setSelectedCitations(newSelection);
  }, []);

  // Clear selection
  const handleClearSelection = useCallback(() => {
    setSelectedCitations(new Set());
  }, []);

  // Bulk verify selected citations
  const handleBulkVerify = useCallback(async () => {
    if (selectedCitations.size === 0) return;
    setIsBulkUpdating(true);
    try {
      await bulkUpdateCitationStatus(
        matterId,
        Array.from(selectedCitations),
        'verified' as VerificationStatus
      );
      handleStatusChange();
      setSelectedCitations(new Set());
    } finally {
      setIsBulkUpdating(false);
    }
  }, [selectedCitations, matterId, handleStatusChange]);

  // Bulk flag selected citations
  const handleBulkFlag = useCallback(async (status: 'mismatch' | 'section_not_found') => {
    if (selectedCitations.size === 0) return;
    setIsBulkUpdating(true);
    try {
      await bulkUpdateCitationStatus(
        matterId,
        Array.from(selectedCitations),
        status as VerificationStatus
      );
      handleStatusChange();
      setSelectedCitations(new Set());
    } finally {
      setIsBulkUpdating(false);
    }
  }, [selectedCitations, matterId, handleStatusChange]);

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

  // Handle verify citation from list
  const handleVerifyCitation = useCallback(
    async (citationId: string) => {
      await updateCitationStatus(matterId, citationId, 'verified' as VerificationStatus);
      handleStatusChange();
    },
    [matterId, handleStatusChange]
  );

  // Handle flag citation from list
  const handleFlagCitation = useCallback(
    async (citationId: string, status: 'mismatch' | 'section_not_found') => {
      await updateCitationStatus(matterId, citationId, status as VerificationStatus);
      handleStatusChange();
    },
    [matterId, handleStatusChange]
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
            citations={filteredCitations}
            meta={meta}
            isLoading={citationsLoading || isFilterDebouncing}
            error={citationsError?.message}
            currentPage={currentPage}
            enableGrouping={enableGrouping}
            enableBulkSelection={true}
            selectedIds={selectedCitations}
            onSelectionChange={handleSelectionChange}
            onPageChange={handlePageChange}
            onDocumentClick={handleDocumentClick}
            onViewCitation={handleViewCitation}
            onVerifyCitation={handleVerifyCitation}
            onFlagCitation={handleFlagCitation}
          />
        )}

        {viewMode === 'byAct' && (
          <CitationsByActView
            citations={filteredCitations}
            summary={summary}
            isLoading={citationsLoading || isFilterDebouncing}
            error={citationsError?.message}
            onViewCitation={handleViewCitation}
            onFixCitation={handleFixCitation}
          />
        )}

        {viewMode === 'byDocument' && (
          <CitationsByDocumentView
            citations={filteredCitations}
            isLoading={citationsLoading || isFilterDebouncing}
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
        enableGrouping={enableGrouping}
        onGroupingToggle={handleGroupingToggle}
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
                    onMarkVerified={markVerified}
                    isMarkingVerified={isMarkingVerified}
                    onRetry={handleSplitViewRetry}
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
        onMarkVerified={markVerified}
        isMarkingVerified={isMarkingVerified}
        onRetry={handleSplitViewRetry}
      />

      {/* Floating bulk action bar */}
      {selectedCitations.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50">
          <div className="flex items-center gap-3 bg-background border rounded-lg shadow-lg px-4 py-3">
            <span className="text-sm font-medium">
              {selectedCitations.size} selected
            </span>
            <div className="h-4 w-px bg-border" />
            <Button
              size="sm"
              variant="outline"
              onClick={handleBulkVerify}
              disabled={isBulkUpdating}
              className="gap-1.5 text-green-600 border-green-200 hover:bg-green-50"
            >
              {isBulkUpdating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              Mark Verified
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isBulkUpdating}
                  className="gap-1.5 text-amber-600 border-amber-200 hover:bg-amber-50"
                >
                  <AlertTriangle className="h-4 w-4" />
                  Flag Issue
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem
                  onClick={() => handleBulkFlag('mismatch')}
                  className="text-destructive"
                >
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  Text Mismatch
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => handleBulkFlag('section_not_found')}
                  className="text-destructive"
                >
                  <Wrench className="h-4 w-4 mr-2" />
                  Section Not Found
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <div className="h-4 w-px bg-border" />
            <Button
              size="sm"
              variant="ghost"
              onClick={handleClearSelection}
              disabled={isBulkUpdating}
              className="gap-1"
            >
              <X className="h-4 w-4" />
              Clear
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

CitationsContent.displayName = 'CitationsContent';
