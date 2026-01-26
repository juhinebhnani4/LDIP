'use client';

/**
 * LibraryBrowser Component
 *
 * Modal browser for the Shared Legal Library, allowing users to:
 * - Search and filter library documents (Acts, Statutes, Judgments)
 * - Link documents to the current matter
 * - Unlink documents from the current matter
 *
 * Phase 2: Shared Legal Library feature.
 *
 * @example
 * ```tsx
 * <LibraryBrowser
 *   matterId="matter-123"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */

import { useCallback, useEffect, useState } from 'react';
import {
  BookOpen,
  Check,
  FileText,
  Gavel,
  Link2,
  Link2Off,
  Loader2,
  Search,
  X,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useLibraryStore } from '@/stores/libraryStore';
import type { LibraryDocumentListItem, LibraryDocumentType } from '@/types/library';

// =============================================================================
// Props
// =============================================================================

export interface LibraryBrowserProps {
  /** Matter ID for linking context */
  matterId: string;
  /** Whether the modal is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
}

// =============================================================================
// Document Type Icons & Labels
// =============================================================================

const DOCUMENT_TYPE_CONFIG: Record<
  LibraryDocumentType,
  { icon: typeof FileText; label: string; color: string }
> = {
  act: { icon: Gavel, label: 'Act', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
  statute: { icon: BookOpen, label: 'Statute', color: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' },
  judgment: { icon: Gavel, label: 'Judgment', color: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200' },
  regulation: { icon: FileText, label: 'Regulation', color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' },
  commentary: { icon: BookOpen, label: 'Commentary', color: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200' },
  circular: { icon: FileText, label: 'Circular', color: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200' },
};

// =============================================================================
// Sub-Components
// =============================================================================

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-3 p-3 border rounded-lg">
          <Skeleton className="h-10 w-10 rounded" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-8 w-20" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ search }: { search: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="rounded-full bg-muted p-4 mb-4">
        <BookOpen className="h-8 w-8 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium mb-1">
        {search ? 'No documents found' : 'Library is empty'}
      </p>
      <p className="text-xs text-muted-foreground">
        {search
          ? `No library documents match "${search}"`
          : 'Upload Acts and Statutes to the shared library'}
      </p>
    </div>
  );
}

interface LibraryDocumentItemProps {
  document: LibraryDocumentListItem;
  isLinking: boolean;
  onLink: () => void;
  onUnlink: () => void;
}

function LibraryDocumentItem({
  document,
  isLinking,
  onLink,
  onUnlink,
}: LibraryDocumentItemProps) {
  const config = DOCUMENT_TYPE_CONFIG[document.documentType];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/50 transition-colors">
      {/* Type Icon */}
      <div className={`flex items-center justify-center h-10 w-10 rounded ${config.color}`}>
        <Icon className="h-5 w-5" />
      </div>

      {/* Document Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{document.title}</p>
          {document.isLinked && (
            <Badge variant="secondary" className="text-xs">
              <Check className="h-3 w-3 mr-1" />
              Linked
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <Badge variant="outline" className="text-xs">
            {config.label}
          </Badge>
          {document.year && (
            <span className="text-xs text-muted-foreground">{document.year}</span>
          )}
          {document.jurisdiction && (
            <span className="text-xs text-muted-foreground">
              {document.jurisdiction === 'central' ? 'Central' : document.jurisdiction}
            </span>
          )}
          {document.pageCount && (
            <span className="text-xs text-muted-foreground">
              {document.pageCount} pages
            </span>
          )}
        </div>
      </div>

      {/* Link/Unlink Button */}
      <Button
        variant={document.isLinked ? 'outline' : 'default'}
        size="sm"
        onClick={document.isLinked ? onUnlink : onLink}
        disabled={isLinking}
        className="min-w-[80px]"
      >
        {isLinking ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : document.isLinked ? (
          <>
            <Link2Off className="h-4 w-4 mr-1" />
            Unlink
          </>
        ) : (
          <>
            <Link2 className="h-4 w-4 mr-1" />
            Link
          </>
        )}
      </Button>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function LibraryBrowser({
  matterId,
  open,
  onOpenChange,
}: LibraryBrowserProps) {
  const [linkingId, setLinkingId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');

  // Store selectors
  const documents = useLibraryStore((state) => state.documents);
  const pagination = useLibraryStore((state) => state.pagination);
  const linkedDocuments = useLibraryStore((state) => state.linkedDocuments);
  const filters = useLibraryStore((state) => state.filters);
  const isLoading = useLibraryStore((state) => state.isLoading);
  const currentPage = useLibraryStore((state) => state.currentPage);
  const error = useLibraryStore((state) => state.error);

  // Store actions
  const setMatterId = useLibraryStore((state) => state.setMatterId);
  const loadDocuments = useLibraryStore((state) => state.loadDocuments);
  const loadLinkedDocuments = useLibraryStore((state) => state.loadLinkedDocuments);
  const setFilters = useLibraryStore((state) => state.setFilters);
  const linkDocument = useLibraryStore((state) => state.linkDocument);
  const unlinkDocument = useLibraryStore((state) => state.unlinkDocument);

  // Load data when modal opens
  useEffect(() => {
    if (open && matterId) {
      setMatterId(matterId);
      loadLinkedDocuments(matterId);
      loadDocuments(1);
    }
  }, [open, matterId, setMatterId, loadLinkedDocuments, loadDocuments]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== filters.search) {
        setFilters({ search: searchInput });
        loadDocuments(1);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput, filters.search, setFilters, loadDocuments]);

  const handleTypeChange = useCallback(
    (value: string) => {
      const docType = value === 'all' ? null : (value as LibraryDocumentType);
      setFilters({ documentType: docType });
      loadDocuments(1);
    },
    [setFilters, loadDocuments]
  );

  const handleLink = useCallback(
    async (documentId: string) => {
      setLinkingId(documentId);
      await linkDocument(documentId);
      setLinkingId(null);
    },
    [linkDocument]
  );

  const handleUnlink = useCallback(
    async (documentId: string) => {
      setLinkingId(documentId);
      await unlinkDocument(documentId);
      setLinkingId(null);
    },
    [unlinkDocument]
  );

  const handlePageChange = useCallback(
    (page: number) => {
      loadDocuments(page);
    },
    [loadDocuments]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Library Browser
          </DialogTitle>
          <DialogDescription>
            Browse and link shared legal documents (Acts, Statutes, Judgments) to this matter.
            Linked documents will be searchable within the matter.
          </DialogDescription>
        </DialogHeader>

        {/* Search and Filters */}
        <div className="flex gap-3 py-4 border-b">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search library..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9"
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput('')}
                className="absolute right-3 top-1/2 -translate-y-1/2"
              >
                <X className="h-4 w-4 text-muted-foreground hover:text-foreground" />
              </button>
            )}
          </div>
          <Select
            value={filters.documentType ?? 'all'}
            onValueChange={handleTypeChange}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="act">Acts</SelectItem>
              <SelectItem value="statute">Statutes</SelectItem>
              <SelectItem value="judgment">Judgments</SelectItem>
              <SelectItem value="regulation">Regulations</SelectItem>
              <SelectItem value="commentary">Commentary</SelectItem>
              <SelectItem value="circular">Circulars</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Linked Count Badge */}
        {linkedDocuments.length > 0 && (
          <div className="py-2">
            <Badge variant="secondary">
              {linkedDocuments.length} document{linkedDocuments.length === 1 ? '' : 's'} linked
              to this matter
            </Badge>
          </div>
        )}

        {/* Document List */}
        <div className="flex-1 overflow-y-auto min-h-[300px]">
          {isLoading ? (
            <LoadingSkeleton />
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-sm text-destructive mb-2">Failed to load library</p>
              <p className="text-xs text-muted-foreground mb-4">{error}</p>
              <Button variant="outline" size="sm" onClick={() => loadDocuments(currentPage)}>
                Try Again
              </Button>
            </div>
          ) : documents.length === 0 ? (
            <EmptyState search={filters.search} />
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <LibraryDocumentItem
                  key={doc.id}
                  document={doc}
                  isLinking={linkingId === doc.id}
                  onLink={() => handleLink(doc.id)}
                  onUnlink={() => handleUnlink(doc.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {pagination && pagination.totalPages > 1 && (
          <div className="flex items-center justify-between pt-4 border-t">
            <p className="text-xs text-muted-foreground">
              Page {pagination.page} of {pagination.totalPages} ({pagination.total} documents)
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage <= 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage >= pagination.totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default LibraryBrowser;
