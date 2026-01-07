'use client';

import { useCallback, useEffect, useState } from 'react';
import type {
  DocumentFilters,
  DocumentListItem,
  DocumentSort,
  DocumentSortColumn,
  DocumentStatus,
  DocumentType,
  PaginationMeta,
  SortOrder,
} from '@/types/document';
import {
  bulkUpdateDocuments,
  fetchDocuments,
  updateDocument,
} from '@/lib/api/documents';
import { DocumentTypeBadge } from './DocumentTypeBadge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from 'sonner';

interface DocumentListProps {
  matterId: string;
  onDocumentClick?: (doc: DocumentListItem) => void;
}

const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
  { value: 'case_file', label: 'Case File' },
  { value: 'act', label: 'Act' },
  { value: 'annexure', label: 'Annexure' },
  { value: 'other', label: 'Other' },
];

const STATUS_LABELS: Record<DocumentStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
};

/** Column definitions for sortable headers */
const SORTABLE_COLUMNS: { key: DocumentSortColumn; label: string }[] = [
  { key: 'filename', label: 'Filename' },
  { key: 'document_type', label: 'Type' },
  { key: 'status', label: 'Status' },
  { key: 'file_size', label: 'Size' },
  { key: 'uploaded_at', label: 'Uploaded' },
];

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format date in localized format
 */
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Document list skeleton for loading state
 */
function DocumentListSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-40" />
      </div>
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Skeleton className="h-4 w-4" />
              </TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
              <TableHead><Skeleton className="h-4 w-16" /></TableHead>
              <TableHead><Skeleton className="h-4 w-16" /></TableHead>
              <TableHead><Skeleton className="h-4 w-12" /></TableHead>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i}>
                <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                <TableCell><Skeleton className="h-4 w-20" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/**
 * Empty state when no documents found
 */
function DocumentListEmpty() {
  return (
    <div className="text-center py-12 border rounded-lg bg-muted/50">
      <p className="text-muted-foreground">No documents found</p>
      <p className="text-sm text-muted-foreground mt-1">
        Upload documents to get started
      </p>
    </div>
  );
}

/**
 * Document list with sorting, filtering, and bulk operations
 */
export function DocumentList({ matterId, onDocumentClick }: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<DocumentFilters>({});
  const [sort, setSort] = useState<DocumentSort>({ column: 'uploaded_at', order: 'desc' });
  const [page, setPage] = useState(1);

  // Fetch documents when matterId, page, filters, or sort change
  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchDocuments(matterId, {
        page,
        perPage: 20,
        filters,
        sort,
      });
      setDocuments(response.data);
      setPagination(response.meta);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load documents';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, [matterId, page, filters, sort]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Sort handler - toggle between asc/desc or change column
  const handleSort = (column: DocumentSortColumn) => {
    setPage(1); // Reset to first page on sort change
    setSort((prev) => {
      if (prev.column === column) {
        // Toggle direction
        return { column, order: prev.order === 'asc' ? 'desc' : 'asc' };
      }
      // New column, default to descending
      return { column, order: 'desc' };
    });
  };

  // Selection handlers
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(documents.map((d) => d.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  // Bulk type change handler
  const handleBulkTypeChange = async (type: DocumentType) => {
    if (selectedIds.size === 0) return;

    try {
      const result = await bulkUpdateDocuments({
        documentIds: Array.from(selectedIds),
        documentType: type,
      });

      toast.success(
        `Updated ${result.updatedCount} document${result.updatedCount !== 1 ? 's' : ''}`
      );
      setSelectedIds(new Set());
      loadDocuments();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update documents';
      toast.error(message);
    }
  };

  // Single document type change handler
  const handleTypeChange = async (docId: string, type: DocumentType) => {
    try {
      await updateDocument(docId, { documentType: type });
      toast.success('Document type updated');
      loadDocuments();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update document';
      toast.error(message);
    }
  };

  // Filter handlers
  const handleFilterChange = (key: keyof DocumentFilters, value: string | undefined) => {
    setPage(1); // Reset to first page on filter change
    setFilters((prev) => {
      const newFilters = { ...prev };
      if (value === undefined || value === '') {
        delete newFilters[key];
      } else {
        if (key === 'documentType') {
          newFilters.documentType = value as DocumentType;
        } else if (key === 'status') {
          newFilters.status = value as DocumentStatus;
        }
      }
      return newFilters;
    });
  };

  if (isLoading && documents.length === 0) {
    return <DocumentListSkeleton />;
  }

  if (error && documents.length === 0) {
    return (
      <div className="text-center py-12 border rounded-lg bg-destructive/10">
        <p className="text-destructive">{error}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={loadDocuments}
        >
          Try Again
        </Button>
      </div>
    );
  }

  const allSelected = documents.length > 0 && selectedIds.size === documents.length;
  const someSelected = selectedIds.size > 0 && !allSelected;

  return (
    <div className="space-y-4">
      {/* Filters and bulk actions */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Type filter */}
        <Select
          value={filters.documentType ?? 'all'}
          onValueChange={(v) => handleFilterChange('documentType', v === 'all' ? undefined : v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {DOCUMENT_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Status filter */}
        <Select
          value={filters.status ?? 'all'}
          onValueChange={(v) => handleFilterChange('status', v === 'all' ? undefined : v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>

        {/* Bulk actions - only show when items are selected */}
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-sm text-muted-foreground">
              {selectedIds.size} selected
            </span>
            <Select onValueChange={(v) => handleBulkTypeChange(v as DocumentType)}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Change type" />
              </SelectTrigger>
              <SelectContent>
                {DOCUMENT_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {/* Document table */}
      {documents.length === 0 ? (
        <DocumentListEmpty />
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={handleSelectAll}
                    aria-label="Select all"
                    data-state={someSelected ? 'indeterminate' : undefined}
                  />
                </TableHead>
                {SORTABLE_COLUMNS.map((col) => (
                  <TableHead
                    key={col.key}
                    className="cursor-pointer hover:bg-muted/50 select-none"
                    onClick={() => handleSort(col.key)}
                  >
                    <div className="flex items-center gap-1">
                      {col.label}
                      {sort.column === col.key && (
                        <span className="text-xs">
                          {sort.order === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow
                  key={doc.id}
                  className={`cursor-pointer hover:bg-muted/50 ${
                    selectedIds.has(doc.id) ? 'bg-muted/30' : ''
                  }`}
                  onClick={() => onDocumentClick?.(doc)}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={selectedIds.has(doc.id)}
                      onCheckedChange={(checked) =>
                        handleSelectOne(doc.id, checked as boolean)
                      }
                      aria-label={`Select ${doc.filename}`}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <div className="flex flex-col">
                      <span className="truncate max-w-xs" title={doc.filename}>
                        {doc.filename}
                      </span>
                      {doc.status === 'pending' && (
                        <span className="text-xs text-amber-600">
                          Needs classification
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Select
                      value={doc.documentType}
                      onValueChange={(v) => handleTypeChange(doc.id, v as DocumentType)}
                    >
                      <SelectTrigger className="h-auto p-0 border-0 shadow-none focus:ring-0">
                        <DocumentTypeBadge type={doc.documentType} />
                      </SelectTrigger>
                      <SelectContent>
                        {DOCUMENT_TYPES.map((t) => (
                          <SelectItem key={t.value} value={t.value}>
                            {t.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <span
                      className={`text-sm ${
                        doc.status === 'failed'
                          ? 'text-destructive'
                          : doc.status === 'completed'
                            ? 'text-green-600'
                            : 'text-muted-foreground'
                      }`}
                    >
                      {STATUS_LABELS[doc.status]}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatFileSize(doc.fileSize)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(doc.uploadedAt)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {pagination && pagination.totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Showing {documents.length} of {pagination.total} documents
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <span className="flex items-center px-3 text-sm">
              Page {page} of {pagination.totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page === pagination.totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
