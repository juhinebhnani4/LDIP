'use client';

/**
 * ContradictionsPagination Component
 *
 * Pagination controls for the contradictions list, with page numbers
 * and prev/next navigation.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 7: Create ContradictionsPagination component
 */

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ContradictionsPaginationProps {
  /** Current page (1-indexed) */
  currentPage: number;
  /** Total number of pages */
  totalPages: number;
  /** Total number of items */
  totalItems: number;
  /** Items per page */
  perPage: number;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Callback when page changes */
  onPageChange: (page: number) => void;
}

/**
 * Generate page numbers to display with ellipsis for large ranges.
 */
function getPageNumbers(currentPage: number, totalPages: number): (number | 'ellipsis')[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | 'ellipsis')[] = [];

  // Always show first page
  pages.push(1);

  if (currentPage > 3) {
    pages.push('ellipsis');
  }

  // Show pages around current
  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);

  for (let i = start; i <= end; i++) {
    if (!pages.includes(i)) {
      pages.push(i);
    }
  }

  if (currentPage < totalPages - 2) {
    pages.push('ellipsis');
  }

  // Always show last page
  if (!pages.includes(totalPages)) {
    pages.push(totalPages);
  }

  return pages;
}

/**
 * ContradictionsPagination provides pagination controls.
 *
 * @example
 * ```tsx
 * <ContradictionsPagination
 *   currentPage={filters.page ?? 1}
 *   totalPages={meta.totalPages}
 *   totalItems={meta.total}
 *   perPage={20}
 *   onPageChange={(page) => setFilters({ page })}
 * />
 * ```
 */
export function ContradictionsPagination({
  currentPage,
  totalPages,
  totalItems,
  perPage,
  isLoading,
  onPageChange,
}: ContradictionsPaginationProps) {
  if (totalPages <= 1) {
    return null;
  }

  const pageNumbers = getPageNumbers(currentPage, totalPages);
  const startItem = (currentPage - 1) * perPage + 1;
  const endItem = Math.min(currentPage * perPage, totalItems);

  return (
    <div className="flex items-center justify-between py-4">
      {/* Item count */}
      <div className="text-sm text-muted-foreground">
        Showing {startItem}-{endItem} of {totalItems}
      </div>

      {/* Pagination controls */}
      <div className="flex items-center gap-1">
        {/* Previous button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1 || isLoading}
          className="h-8 w-8 p-0"
        >
          <ChevronLeft className="h-4 w-4" />
          <span className="sr-only">Previous page</span>
        </Button>

        {/* Page numbers */}
        {pageNumbers.map((page, index) => {
          if (page === 'ellipsis') {
            return (
              <span
                key={`ellipsis-${index}`}
                className="px-2 text-muted-foreground"
                aria-hidden="true"
              >
                ...
              </span>
            );
          }

          return (
            <Button
              key={page}
              variant={page === currentPage ? 'default' : 'outline'}
              size="sm"
              onClick={() => onPageChange(page)}
              disabled={isLoading}
              className="h-8 w-8 p-0"
            >
              {page}
            </Button>
          );
        })}

        {/* Next button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages || isLoading}
          className="h-8 w-8 p-0"
        >
          <ChevronRight className="h-4 w-4" />
          <span className="sr-only">Next page</span>
        </Button>
      </div>
    </div>
  );
}
