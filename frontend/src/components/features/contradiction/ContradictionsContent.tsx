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
import { AlertTriangle, FileWarning } from 'lucide-react';
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
      <div className="flex items-center gap-3">
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
                  <div className="grid grid-cols-2 gap-4">
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
 * Empty state display.
 */
function ContradictionsEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileWarning className="h-12 w-12 text-muted-foreground/50 mb-4" />
      <h3 className="text-lg font-medium mb-2">No Contradictions Found</h3>
      <p className="text-muted-foreground max-w-md">
        No contradictions have been detected in the documents for this matter.
        This could mean the documents are consistent, or document processing is still in progress.
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
 *
 * @example
 * ```tsx
 * <ContradictionsContent
 *   matterId="matter-123"
 *   onDocumentClick={(docId, page) => openPdfViewer(docId, page)}
 * />
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

  // Fetch contradictions data
  const { data, meta, isLoading, error, totalCount, uniqueEntities } = useContradictions(
    matterId,
    {
      severity,
      contradictionType,
      entityId,
      page,
      perPage: 20,
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

  // Show loading state
  if (isLoading && data.length === 0) {
    return <ContradictionsSkeleton />;
  }

  // Show error state
  if (error && data.length === 0) {
    return <ContradictionsError message={error.message} />;
  }

  // Show empty state
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
            onDocumentClick={onDocumentClick}
            onEvidenceClick={onEvidenceClick}
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
