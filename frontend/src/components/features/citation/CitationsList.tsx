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
import { cn } from '@/lib/utils';
import {
  Eye,
  AlertTriangle,
  CheckCircle,
  CheckCircle2,
  Clock,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Wrench,
  FileText,
  Scale,
  Flag,
  Loader2,
  Layers,
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Checkbox } from '@/components/ui/checkbox';
import type { CitationListItem, GroupedCitation, VerificationStatus, PaginationMeta } from '@/types/citation';
import { groupCitations, groupHasIssues, getGroupDocumentSummary } from '@/lib/utils/citationGrouping';

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
  /** Enable grouping of duplicate citations */
  enableGrouping?: boolean;
  /** Enable bulk selection mode */
  enableBulkSelection?: boolean;
  /** Currently selected citation IDs */
  selectedIds?: Set<string>;
  /** Callback when selection changes */
  onSelectionChange?: (selectedIds: Set<string>) => void;
  /** Callback when page changes */
  onPageChange?: (page: number) => void;
  /** Callback when document name is clicked */
  onDocumentClick?: (documentId: string, page: number) => void;
  /** Callback when view citation button is clicked */
  onViewCitation?: (citationId: string) => void;
  /** Callback when verify button is clicked */
  onVerifyCitation?: (citationId: string) => Promise<void>;
  /** Callback when flag issue button is clicked */
  onFlagCitation?: (citationId: string, status: 'mismatch' | 'section_not_found') => Promise<void>;
}

type SortField = 'actName' | 'sectionNumber' | 'verificationStatus' | 'confidence' | 'sourcePage';
type SortDirection = 'asc' | 'desc';

/**
 * Get status badge variant, icon, and tooltip for verification status.
 * Clearly distinguishes between:
 * - Issues requiring review (mismatch, section_not_found)
 * - Awaiting action (act_unavailable, pending)
 * - Complete (verified)
 */
function getStatusBadge(status: VerificationStatus): {
  variant: 'default' | 'destructive' | 'outline' | 'secondary';
  icon: React.ReactNode;
  label: string;
  tooltip: string;
} {
  switch (status) {
    case 'verified':
      return {
        variant: 'default',
        icon: <CheckCircle className="h-3 w-3" />,
        label: 'Verified',
        tooltip: 'Citation text matches the Act section',
      };
    case 'mismatch':
      return {
        variant: 'destructive',
        icon: <AlertTriangle className="h-3 w-3" />,
        label: 'Mismatch',
        tooltip: 'Citation text differs from Act - review needed',
      };
    case 'section_not_found':
      return {
        variant: 'destructive',
        icon: <Wrench className="h-3 w-3" />,
        label: 'Section Missing',
        tooltip: 'Section not found in Act document - verify section number',
      };
    case 'act_unavailable':
      return {
        variant: 'outline',
        icon: <Scale className="h-3 w-3" />,
        label: 'Awaiting Act',
        tooltip: 'Upload the Act document to enable verification',
      };
    case 'pending':
    default:
      return {
        variant: 'outline',
        icon: <Clock className="h-3 w-3" />,
        label: 'Pending',
        tooltip: 'Verification in progress',
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
  enableGrouping = false,
  enableBulkSelection = false,
  selectedIds = new Set(),
  onSelectionChange,
  onPageChange,
  onDocumentClick,
  onViewCitation,
  onVerifyCitation,
  onFlagCitation,
}: CitationsListProps) {
  const [sortField, setSortField] = useState<SortField>('actName');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  // Track which citations are currently being updated
  const [updatingCitations, setUpdatingCitations] = useState<Set<string>>(new Set());
  // Confirmation dialog state for low-confidence verifications
  const [confirmVerify, setConfirmVerify] = useState<{ citationId: string; confidence: number } | null>(null);
  // Track expanded groups
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  // Toggle group expansion
  const toggleGroupExpanded = useCallback((groupKey: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  }, []);

  // Group citations when grouping is enabled
  const groupedCitations = useMemo(() => {
    if (!enableGrouping) return null;
    return groupCitations(citations);
  }, [citations, enableGrouping]);

  // Selection handlers
  const handleSelectAll = useCallback(() => {
    if (!onSelectionChange) return;
    const allIds = citations.map((c) => c.id);
    const allSelected = allIds.every((id) => selectedIds.has(id));
    if (allSelected) {
      // Deselect all
      onSelectionChange(new Set());
    } else {
      // Select all
      onSelectionChange(new Set(allIds));
    }
  }, [citations, selectedIds, onSelectionChange]);

  const handleSelectOne = useCallback(
    (citationId: string, checked: boolean) => {
      if (!onSelectionChange) return;
      const newSelection = new Set(selectedIds);
      if (checked) {
        newSelection.add(citationId);
      } else {
        newSelection.delete(citationId);
      }
      onSelectionChange(newSelection);
    },
    [selectedIds, onSelectionChange]
  );

  // Check if all current citations are selected
  const allSelected = useMemo(() => {
    if (citations.length === 0) return false;
    return citations.every((c) => selectedIds.has(c.id));
  }, [citations, selectedIds]);

  const someSelected = useMemo(() => {
    return citations.some((c) => selectedIds.has(c.id)) && !allSelected;
  }, [citations, selectedIds, allSelected]);

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

  // Handle verify citation with confirmation for low confidence
  const handleVerifyCitation = useCallback(
    async (citationId: string, confidence: number) => {
      if (!onVerifyCitation) return;

      // Show confirmation for low confidence citations
      if (confidence < 70) {
        setConfirmVerify({ citationId, confidence });
        return;
      }

      setUpdatingCitations((prev) => new Set(prev).add(citationId));
      try {
        await onVerifyCitation(citationId);
      } finally {
        setUpdatingCitations((prev) => {
          const next = new Set(prev);
          next.delete(citationId);
          return next;
        });
      }
    },
    [onVerifyCitation]
  );

  // Confirm verification after dialog
  const handleConfirmVerify = useCallback(async () => {
    if (!confirmVerify || !onVerifyCitation) return;

    const { citationId } = confirmVerify;
    setConfirmVerify(null);
    setUpdatingCitations((prev) => new Set(prev).add(citationId));
    try {
      await onVerifyCitation(citationId);
    } finally {
      setUpdatingCitations((prev) => {
        const next = new Set(prev);
        next.delete(citationId);
        return next;
      });
    }
  }, [confirmVerify, onVerifyCitation]);

  // Handle flag citation
  const handleFlagCitation = useCallback(
    async (citationId: string, status: 'mismatch' | 'section_not_found') => {
      if (!onFlagCitation) return;

      setUpdatingCitations((prev) => new Set(prev).add(citationId));
      try {
        await onFlagCitation(citationId, status);
      } finally {
        setUpdatingCitations((prev) => {
          const next = new Set(prev);
          next.delete(citationId);
          return next;
        });
      }
    },
    [onFlagCitation]
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
              {/* Checkbox column for bulk selection */}
              {enableBulkSelection && (
                <TableHead className="w-[40px]">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={handleSelectAll}
                    aria-label="Select all citations on this page"
                    className={someSelected ? 'data-[state=checked]:bg-primary/50' : ''}
                  />
                </TableHead>
              )}
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
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="flex items-center hover:text-foreground"
                      onClick={() => handleSort('confidence')}
                    >
                      Conf.
                      <HelpCircle className="h-3 w-3 ml-1 text-muted-foreground" />
                      {getSortIcon('confidence')}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="font-medium mb-1">Confidence Score Legend</p>
                    <ul className="text-xs space-y-1">
                      <li><span className="text-green-600">90-100%</span>: High - Text closely matches</li>
                      <li><span className="text-amber-600">70-89%</span>: Medium - Review recommended</li>
                      <li><span className="text-destructive">Below 70%</span>: Low - Manual check needed</li>
                    </ul>
                  </TooltipContent>
                </Tooltip>
              </TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* Grouped view */}
            {enableGrouping && groupedCitations ? (
              groupedCitations.map((group) => {
                const isExpanded = expandedGroups.has(group.groupKey);
                const hasMultiple = group.count > 1;
                const statusBadge = getStatusBadge(group.aggregateStatus);
                const isIssue = groupHasIssues(group);
                const rep = group.representative;

                return (
                  <>
                    {/* Group header row */}
                    <TableRow
                      key={group.groupKey}
                      className={cn(
                        'cursor-pointer hover:bg-muted/50',
                        isIssue && 'bg-destructive/5'
                      )}
                      onClick={hasMultiple ? () => toggleGroupExpanded(group.groupKey) : undefined}
                    >
                      {/* Checkbox for bulk selection - selects representative */}
                      {enableBulkSelection && (
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={selectedIds.has(rep.id)}
                            onCheckedChange={(checked) => handleSelectOne(rep.id, !!checked)}
                            aria-label={`Select ${rep.actName} Section ${rep.sectionNumber}`}
                          />
                        </TableCell>
                      )}
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {hasMultiple && (
                            <span className="text-muted-foreground">
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </span>
                          )}
                          {rep.actName}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {rep.sectionNumber}
                          {rep.subsection && `.${rep.subsection}`}
                          {rep.clause && `(${rep.clause})`}
                          {hasMultiple && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Badge variant="secondary" className="gap-1">
                                  <Layers className="h-3 w-3" />
                                  {group.count}
                                </Badge>
                              </TooltipTrigger>
                              <TooltipContent>
                                {group.count} occurrences across {group.documentNames.length} document{group.documentNames.length !== 1 ? 's' : ''}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-[300px]">
                        {rep.rawCitationText ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="line-clamp-2 text-sm cursor-default">
                                {rep.rawCitationText}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-md">
                              <p className="text-sm whitespace-pre-wrap">{rep.rawCitationText}</p>
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-sm text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {hasMultiple ? (
                          <span className="text-sm text-muted-foreground">
                            {getGroupDocumentSummary(group)}
                          </span>
                        ) : rep.documentName ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                className="flex items-center gap-1 text-sm text-primary hover:underline max-w-[140px]"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDocumentClick(rep.documentId, rep.sourcePage);
                                }}
                              >
                                <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                                <span className="truncate">{rep.documentName}</span>
                                <span className="text-muted-foreground flex-shrink-0">p.{rep.sourcePage}</span>
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>{rep.documentName}</p>
                              <p className="text-xs opacity-75">Page {rep.sourcePage}</p>
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-muted-foreground">Page {rep.sourcePage}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant={statusBadge.variant} className="gap-1 cursor-help">
                              {statusBadge.icon}
                              {statusBadge.label}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="text-sm">{statusBadge.tooltip}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                      <TableCell>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className={`font-medium cursor-help ${getConfidenceColor(group.averageConfidence)}`}>
                              {group.averageConfidence.toFixed(0)}%
                            </span>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="font-medium mb-1">
                              {hasMultiple ? 'Average Confidence' : 'Confidence Score'}
                            </p>
                            <p className="text-xs opacity-90">
                              {hasMultiple
                                ? `Average across ${group.count} citations`
                                : group.averageConfidence >= 90
                                ? 'High confidence: Citation text closely matches the Act section.'
                                : group.averageConfidence >= 70
                                ? 'Medium confidence: Citation text partially matches.'
                                : 'Low confidence: Manual verification needed.'}
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          {/* View button */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleViewCitation(rep.id)}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>View in split view</TooltipContent>
                          </Tooltip>

                          {/* Verify button - show for non-verified citations */}
                          {rep.verificationStatus !== 'verified' && onVerifyCitation && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleVerifyCitation(rep.id, rep.confidence)}
                                  disabled={updatingCitations.has(rep.id)}
                                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                >
                                  {updatingCitations.has(rep.id) ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <CheckCircle2 className="h-4 w-4" />
                                  )}
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                {hasMultiple ? `Mark verified (applies to this occurrence)` : 'Mark as verified'}
                              </TooltipContent>
                            </Tooltip>
                          )}

                          {/* Flag Issue dropdown - show for non-issue citations */}
                          {!isIssue && onFlagCitation && (
                            <DropdownMenu>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <DropdownMenuTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      disabled={updatingCitations.has(rep.id)}
                                      className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                                    >
                                      <Flag className="h-4 w-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                </TooltipTrigger>
                                <TooltipContent>Flag an issue</TooltipContent>
                              </Tooltip>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onClick={() => handleFlagCitation(rep.id, 'mismatch')}
                                  className="text-destructive"
                                >
                                  <AlertTriangle className="h-4 w-4 mr-2" />
                                  Text Mismatch
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => handleFlagCitation(rep.id, 'section_not_found')}
                                  className="text-destructive"
                                >
                                  <Wrench className="h-4 w-4 mr-2" />
                                  Section Not Found
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}

                          {/* Fix issue button - show for issues */}
                          {isIssue && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleViewCitation(rep.id)}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <Wrench className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Review and fix issue</TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>

                    {/* Expanded individual rows */}
                    {isExpanded && hasMultiple && group.citations.map((citation) => {
                      const citStatusBadge = getStatusBadge(citation.verificationStatus);
                      const citIsIssue = ['mismatch', 'section_not_found'].includes(citation.verificationStatus);

                      return (
                        <TableRow
                          key={citation.id}
                          className={cn(
                            'bg-muted/30',
                            citIsIssue && 'bg-destructive/5'
                          )}
                        >
                          {/* Checkbox for bulk selection */}
                          {enableBulkSelection && (
                            <TableCell>
                              <Checkbox
                                checked={selectedIds.has(citation.id)}
                                onCheckedChange={(checked) => handleSelectOne(citation.id, !!checked)}
                                aria-label={`Select citation ${citation.id}`}
                              />
                            </TableCell>
                          )}
                          <TableCell className="pl-10 text-muted-foreground">
                            └─
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {citation.sectionNumber}
                          </TableCell>
                          <TableCell className="max-w-[300px]">
                            {citation.rawCitationText ? (
                              <span className="line-clamp-1 text-sm text-muted-foreground">
                                {citation.rawCitationText}
                              </span>
                            ) : (
                              <span className="text-sm text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {citation.documentName ? (
                              <button
                                type="button"
                                className="flex items-center gap-1 text-sm text-primary hover:underline max-w-[140px]"
                                onClick={() => handleDocumentClick(citation.documentId, citation.sourcePage)}
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
                            <Badge variant={citStatusBadge.variant} className="gap-1">
                              {citStatusBadge.icon}
                              {citStatusBadge.label}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <span className={`font-medium ${getConfidenceColor(citation.confidence)}`}>
                              {citation.confidence.toFixed(0)}%
                            </span>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleViewCitation(citation.id)}
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>View in split view</TooltipContent>
                              </Tooltip>

                              {citation.verificationStatus !== 'verified' && onVerifyCitation && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleVerifyCitation(citation.id, citation.confidence)}
                                  disabled={updatingCitations.has(citation.id)}
                                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                >
                                  {updatingCitations.has(citation.id) ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <CheckCircle2 className="h-4 w-4" />
                                  )}
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </>
                );
              })
            ) : (
              /* Non-grouped view (original) */
              sortedCitations.map((citation) => {
                const statusBadge = getStatusBadge(citation.verificationStatus);
                const isIssue = ['mismatch', 'section_not_found'].includes(citation.verificationStatus);

                return (
                  <TableRow key={citation.id} className={isIssue ? 'bg-destructive/5' : ''}>
                    {/* Checkbox for bulk selection */}
                    {enableBulkSelection && (
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(citation.id)}
                          onCheckedChange={(checked) => handleSelectOne(citation.id, !!checked)}
                          aria-label={`Select citation for ${citation.actName} Section ${citation.sectionNumber}`}
                        />
                      </TableCell>
                    )}
                    <TableCell className="font-medium">
                      {citation.actName}
                    </TableCell>
                    <TableCell>
                      {citation.sectionNumber}
                      {citation.subsection && `.${citation.subsection}`}
                      {citation.clause && `(${citation.clause})`}
                    </TableCell>
                    <TableCell className="max-w-[300px]">
                      {citation.rawCitationText ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="line-clamp-2 text-sm cursor-default">
                              {citation.rawCitationText}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-md">
                            <p className="text-sm whitespace-pre-wrap">{citation.rawCitationText}</p>
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {citation.documentName ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="flex items-center gap-1 text-sm text-primary hover:underline max-w-[140px]"
                              onClick={() => handleDocumentClick(citation.documentId, citation.sourcePage)}
                            >
                              <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                              <span className="truncate">{citation.documentName}</span>
                              <span className="text-muted-foreground flex-shrink-0">p.{citation.sourcePage}</span>
                            </button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{citation.documentName}</p>
                            <p className="text-xs opacity-75">Page {citation.sourcePage}</p>
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <span className="text-muted-foreground">Page {citation.sourcePage}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Badge variant={statusBadge.variant} className="gap-1 cursor-help">
                            {statusBadge.icon}
                            {statusBadge.label}
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-sm">{statusBadge.tooltip}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className={`font-medium cursor-help ${getConfidenceColor(citation.confidence)}`}>
                            {citation.confidence.toFixed(0)}%
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="font-medium mb-1">Confidence Score</p>
                          <p className="text-xs opacity-90">
                            {citation.confidence >= 90
                              ? 'High confidence: Citation text closely matches the Act section.'
                              : citation.confidence >= 70
                              ? 'Medium confidence: Citation text partially matches. Review recommended.'
                              : 'Low confidence: Significant differences detected. Manual verification needed.'}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {/* View button */}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleViewCitation(citation.id)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>View in split view</TooltipContent>
                        </Tooltip>

                        {/* Verify button - show for non-verified citations */}
                        {citation.verificationStatus !== 'verified' && onVerifyCitation && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleVerifyCitation(citation.id, citation.confidence)}
                                disabled={updatingCitations.has(citation.id)}
                                className="text-green-600 hover:text-green-700 hover:bg-green-50"
                              >
                                {updatingCitations.has(citation.id) ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <CheckCircle2 className="h-4 w-4" />
                                )}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Mark as verified</TooltipContent>
                          </Tooltip>
                        )}

                        {/* Flag Issue dropdown - show for non-issue citations */}
                        {!isIssue && onFlagCitation && (
                          <DropdownMenu>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <DropdownMenuTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    disabled={updatingCitations.has(citation.id)}
                                    className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                                  >
                                    <Flag className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                              </TooltipTrigger>
                              <TooltipContent>Flag an issue</TooltipContent>
                            </Tooltip>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => handleFlagCitation(citation.id, 'mismatch')}
                                className="text-destructive"
                              >
                                <AlertTriangle className="h-4 w-4 mr-2" />
                                Text Mismatch
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleFlagCitation(citation.id, 'section_not_found')}
                                className="text-destructive"
                              >
                                <Wrench className="h-4 w-4 mr-2" />
                                Section Not Found
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}

                        {/* Fix issue button - show for issues */}
                        {isIssue && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleViewCitation(citation.id)}
                                className="text-destructive hover:text-destructive"
                              >
                                <Wrench className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Review and fix issue</TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Confirmation dialog for low-confidence verifications */}
      <AlertDialog open={!!confirmVerify} onOpenChange={(open) => !open && setConfirmVerify(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Verify Low-Confidence Citation?</AlertDialogTitle>
            <AlertDialogDescription>
              This citation has a confidence score of {confirmVerify?.confidence?.toFixed(0)}%,
              which suggests significant differences from the Act text. Are you sure you want to
              mark it as verified after manual review?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmVerify}>
              Yes, Mark as Verified
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

CitationsList.displayName = 'CitationsList';
