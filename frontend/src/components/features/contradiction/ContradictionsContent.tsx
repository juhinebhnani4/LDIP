'use client';

/**
 * ContradictionsContent Component
 *
 * Client component that orchestrates contradictions data fetching and composition.
 * Follows the Content component pattern used by other workspace tabs.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 2: Create ContradictionsContent component
 */

import { useState, useCallback, useMemo } from 'react';
import { AlertTriangle, FileWarning, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { EntityContradictionGroup } from './EntityContradictionGroup';
import { ContradictionsFilters } from './ContradictionsFilters';
import { ContradictionsPagination } from './ContradictionsPagination';
import {
  useContradictions,
  type ContradictionSeverity,
  type ContradictionType,
} from '@/hooks/useContradictions';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';
import { useBoundingBoxes } from '@/hooks';
import { fetchDocument } from '@/lib/api/documents';

interface ContradictionsContentProps {
  /** Matter ID */
  matterId: string;
  /** Optional callback when document is clicked (opens PDF viewer) */
  onDocumentClick?: (documentId: string, page: number | null) => void;
  /** Optional callback when evidence is clicked (opens split view with bbox) */
  onEvidenceClick?: (documentId: string, page: number | null, bboxIds: string[]) => void;
}

/**
 * Loading skeleton for the contradictions page.
 */
function ContradictionsSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
      </div>

      {/* Filters skeleton */}
      <div className="flex flex-wrap items-center gap-3">
        <Skeleton className="h-10 w-36" />
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-44" />
      </div>

      {/* Entity groups skeleton */}
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-5" />
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-24" />
            </div>
            <div className="space-y-3 pl-8">
              {Array.from({ length: 2 }).map((_, j) => (
                <div key={j} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-5 w-20" />
                    <Skeleton className="h-5 w-28" />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Skeleton className="h-3 w-24" />
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="h-12 w-full" />
                    </div>
                    <div className="space-y-2">
                      <Skeleton className="h-3 w-24" />
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="h-12 w-full" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state display.
 */
function ContradictionsError({ message }: { message?: string }) {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {message ?? 'Failed to load contradictions. Please try refreshing the page.'}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Empty state display — only shown when processing is complete and no contradictions exist.
 */
function ContradictionsEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileWarning className="h-12 w-12 text-muted-foreground/50 mb-4" />
      <h3 className="text-lg font-medium mb-2">No Contradictions Found</h3>
      <p className="text-muted-foreground max-w-md">
        No contradictions have been detected in the documents for this matter.
        The documents appear to be consistent.
      </p>
    </div>
  );
}

/**
 * Processing state display — shown when contradiction detection is still running.
 */
function ContradictionsProcessing() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Loader2 className="h-12 w-12 text-muted-foreground/50 mb-4 animate-spin" />
      <h3 className="text-lg font-medium mb-2">Analyzing Documents</h3>
      <p className="text-muted-foreground max-w-md">
        Contradiction detection is still running. Results will appear here as they are found.
      </p>
    </div>
  );
}

/**
 * ContradictionsContent component.
 *
 * Provides the complete contradictions workflow UI:
 * - Header with total count
 * - Filter controls for severity, type, and entity
 * - Entity-grouped contradiction cards
 * - Pagination controls
 * - PDF split view integration for evidence source viewing
 *
 * @example
 * ```tsx
 * <ContradictionsContent matterId="matter-123" />
 * ```
 */
export function ContradictionsContent({
  matterId,
  onDocumentClick,
  onEvidenceClick,
}: ContradictionsContentProps) {
  // Filter state
  const [severity, setSeverity] = useState<ContradictionSeverity | undefined>(undefined);
  const [contradictionType, setContradictionType] = useState<ContradictionType | undefined>(
    undefined
  );
  const [entityId, setEntityId] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);

  // PDF split view integration
  const openPdfSplitView = usePdfSplitViewStore((state) => state.openPdfSplitView);
  const setBoundingBoxes = usePdfSplitViewStore((state) => state.setBoundingBoxes);
  const { fetchByBboxIds } = useBoundingBoxes();

  // Check if contradiction detection is still running on the backend
  const contradictionsProcessing = useWorkspaceStore(
    (state) => state.tabProcessingStatus.contradictions === 'processing'
  );

  // Fetch contradictions data - use default perPage=100 from hook for comprehensive view
  const { data, meta, isLoading, error, totalCount, uniqueEntities } = useContradictions(
    matterId,
    {
      severity,
      contradictionType,
      entityId,
      page,
    }
  );

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return severity !== undefined || contradictionType !== undefined || entityId !== undefined;
  }, [severity, contradictionType, entityId]);

  // Reset all filters
  const handleReset = useCallback(() => {
    setSeverity(undefined);
    setContradictionType(undefined);
    setEntityId(undefined);
    setPage(1);
  }, []);

  // Handle page change
  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // Handle severity change
  const handleSeverityChange = useCallback((newSeverity: ContradictionSeverity | undefined) => {
    setSeverity(newSeverity);
    setPage(1); // Reset to first page on filter change
  }, []);

  // Handle type change
  const handleTypeChange = useCallback((newType: ContradictionType | undefined) => {
    setContradictionType(newType);
    setPage(1); // Reset to first page on filter change
  }, []);

  // Handle entity change
  const handleEntityChange = useCallback((newEntityId: string | undefined) => {
    setEntityId(newEntityId);
    setPage(1); // Reset to first page on filter change
  }, []);

  /**
   * Handle document click from contradiction statements.
   * Opens PDF split view at the specified page.
   */
  const handleDocumentClick = useCallback(
    async (documentId: string, documentPage: number | null) => {
      if (onDocumentClick) {
        onDocumentClick(documentId, documentPage);
        return;
      }

      try {
        const document = await fetchDocument(documentId);
        const documentUrl = document.storagePath;

        if (!documentUrl) {
          throw new Error('Document URL not found');
        }

        openPdfSplitView(
          {
            documentId,
            documentName: document.filename || 'Document',
            page: documentPage ?? undefined,
          },
          matterId,
          documentUrl
        );
      } catch {
        toast.error('Unable to open document. Please try again.');
      }
    },
    [matterId, onDocumentClick, openPdfSplitView]
  );

  /**
   * Handle evidence click from contradiction cards.
   * Opens PDF split view with bounding box highlighting.
   */
  const handleEvidenceClick = useCallback(
    async (documentId: string, documentPage: number | null, bboxIds: string[]) => {
      if (onEvidenceClick) {
        onEvidenceClick(documentId, documentPage, bboxIds);
        return;
      }

      try {
        const document = await fetchDocument(documentId);
        const documentUrl = document.storagePath;

        if (!documentUrl) {
          throw new Error('Document URL not found');
        }

        openPdfSplitView(
          {
            documentId,
            documentName: document.filename || 'Document',
            page: documentPage ?? undefined,
            bboxIds: bboxIds || [],
          },
          matterId,
          documentUrl
        );

        // Fetch bounding boxes for highlighting
        if (bboxIds && bboxIds.length > 0) {
          try {
            const result = await fetchByBboxIds(bboxIds, matterId);
            const bboxes = result.bboxes.map((bbox) => ({
              x: bbox.x,
              y: bbox.y,
              width: bbox.width,
              height: bbox.height,
            }));

            if (bboxes.length > 0) {
              const pageNumber = result.pageNumber ?? documentPage ?? 1;
              setBoundingBoxes(bboxes, pageNumber);
            }
          } catch {
            console.warn('Failed to fetch bounding boxes for evidence highlight');
          }
        }
      } catch {
        toast.error('Unable to open document. Please try again.');
      }
    },
    [matterId, onEvidenceClick, openPdfSplitView, fetchByBboxIds, setBoundingBoxes]
  );

  // Show loading state
  if (isLoading && data.length === 0) {
    return <ContradictionsSkeleton />;
  }

  // Show error state
  if (error && data.length === 0) {
    return <ContradictionsError message={error.message} />;
  }

  // Show processing state if backend is still detecting contradictions
  if (!isLoading && data.length === 0 && !hasActiveFilters && contradictionsProcessing) {
    return <ContradictionsProcessing />;
  }

  // Show empty state only when processing is complete and no contradictions exist
  if (!isLoading && data.length === 0 && !hasActiveFilters) {
    return <ContradictionsEmpty />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">
          {totalCount} contradiction{totalCount !== 1 ? 's' : ''} found
        </h2>
        {isLoading && (
          <span className="text-sm text-muted-foreground">Updating...</span>
        )}
      </div>

      {/* Filters */}
      <ContradictionsFilters
        severity={severity}
        contradictionType={contradictionType}
        entityId={entityId}
        entities={uniqueEntities}
        hasActiveFilters={hasActiveFilters}
        onSeverityChange={handleSeverityChange}
        onTypeChange={handleTypeChange}
        onEntityChange={handleEntityChange}
        onReset={handleReset}
      />

      {/* Empty state with filters */}
      {data.length === 0 && hasActiveFilters && (
        <div className="text-center py-8 text-muted-foreground">
          No contradictions match the current filters.
        </div>
      )}

      {/* Entity groups */}
      <div className="space-y-4">
        {data.map((group, index) => (
          <EntityContradictionGroup
            key={group.entityId}
            group={group}
            defaultExpanded={index < 3}
            onDocumentClick={handleDocumentClick}
            onEvidenceClick={handleEvidenceClick}
          />
        ))}
      </div>

      {/* Pagination */}
      {meta && (
        <ContradictionsPagination
          currentPage={meta.page}
          totalPages={meta.totalPages}
          totalItems={meta.total}
          perPage={meta.perPage}
          isLoading={isLoading}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
}
