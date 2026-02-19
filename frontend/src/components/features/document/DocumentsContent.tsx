'use client';

/**
 * Documents Content Component
 *
 * Client component that orchestrates document list data fetching
 * and composition. Follows the Content component pattern used by other
 * workspace tabs (VerificationContent, SummaryContent, etc.).
 *
 * Story 10D.3: Documents Tab File List
 * Task 1: Create DocumentsContent container component
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { AlertTriangle, FileText } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { DocumentList } from './DocumentList';
import { DocumentsHeader } from './DocumentsHeader';
import { AddDocumentsDialog } from './AddDocumentsDialog';
import { LinkedLibraryPanel } from '../library/LinkedLibraryPanel';
import { PdfViewerModal } from '../pdf/PdfViewerModal';
import { useDocuments } from '@/hooks/useDocuments';
import { fetchDocument, retryAllStuckDocuments } from '@/lib/api/documents';
import type { DocumentListItem } from '@/types/document';

interface DocumentsContentProps {
  /** Matter ID - required for document isolation */
  matterId: string;
  /** Optional callback when a document is clicked */
  onDocumentClick?: (document: DocumentListItem) => void;
  /** Optional className for styling */
  className?: string;
}

/**
 * Loading skeleton for the documents page
 */
export function DocumentsSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="space-y-4 p-4 rounded-lg border bg-card">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-9 w-32" />
        </div>
        <div className="flex items-center gap-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>

      {/* Filters skeleton */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-10 w-40" />
      </div>

      {/* Table skeleton */}
      <div className="rounded-md border">
        <div className="p-4 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Error state display
 */
export function DocumentsError({ message }: { message?: string }) {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {message || 'Failed to load documents. Please try refreshing the page.'}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Documents Content component.
 *
 * Provides the complete documents management UI:
 * - Statistics header with processing indicator
 * - Document list with sorting and filtering
 * - Add documents dialog
 *
 * @example
 * ```tsx
 * <DocumentsContent matterId="matter-123" />
 * ```
 */
export function DocumentsContent({
  matterId,
  onDocumentClick,
  className,
}: DocumentsContentProps) {
  // Dialog state for adding documents
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  // Retry all stuck state
  const [isRetryingAll, setIsRetryingAll] = useState(false);

  // In-app document viewer state (BUG-LT3-G / BUG-LT3-H fix)
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerDocId, setViewerDocId] = useState<string | undefined>(undefined);
  const [viewerDocName, setViewerDocName] = useState('Document');
  const [viewerInitialPage, setViewerInitialPage] = useState(1);

  // Fetch documents using hook
  const { documents, isLoading, error, refresh } = useDocuments(matterId);

  // Cross-tab navigation: read ?doc=...&page=... from URL
  const searchParams = useSearchParams();
  const docParam = searchParams.get('doc');
  const pageParam = searchParams.get('page') || searchParams.get('pages')?.split('-')[0];

  // Find the document matching the URL param (by filename or ID)
  const targetDoc = useMemo(() => {
    if (!docParam || !documents.length) return null;
    const decoded = decodeURIComponent(docParam);
    return documents.find(
      (d) => d.filename === docParam || d.filename === decoded || d.id === docParam
    ) || null;
  }, [docParam, documents]);

  // Open a document in the in-app viewer (with optional page)
  const handleOpenDocument = useCallback(async (doc: DocumentListItem, page?: string) => {
    try {
      const fullDoc = await fetchDocument(doc.id);
      setViewerUrl(fullDoc.storagePath);
      setViewerDocId(doc.id);
      setViewerDocName(doc.filename);
      setViewerInitialPage(page ? parseInt(page, 10) || 1 : 1);
      setViewerOpen(true);
    } catch {
      toast.error('Failed to open document');
    }
  }, []);

  // Auto-open document viewer when ?doc= param matches a document (BUG-LT3-H fix)
  const [autoOpenAttempted, setAutoOpenAttempted] = useState(false);
  useEffect(() => {
    if (targetDoc && !autoOpenAttempted && !viewerOpen) {
      setAutoOpenAttempted(true);
      handleOpenDocument(targetDoc, pageParam || undefined);
    }
  }, [targetDoc, autoOpenAttempted, viewerOpen, handleOpenDocument, pageParam]);

  // Calculate processing documents count
  const processingStats = useMemo(() => {
    if (!documents.length) {
      return { processingCount: 0, totalCount: 0, processingPercent: 0, stuckCount: 0 };
    }

    const processingDocs = documents.filter(
      (d) => d.status === 'processing' || d.status === 'pending'
    );

    // Stuck documents: failed status (we can't tell time here, so just count failed)
    const stuckDocs = documents.filter(
      (d) => d.status === 'failed' || d.status === 'ocr_failed'
    );

    const processingCount = processingDocs.length;
    const totalCount = documents.length;
    const processingPercent =
      totalCount > 0 ? Math.round((processingCount / totalCount) * 100) : 0;
    const stuckCount = stuckDocs.length;

    return { processingCount, totalCount, processingPercent, stuckCount };
  }, [documents]);

  // Calculate document type breakdown
  const typeBreakdown = useMemo(() => {
    const breakdown = {
      case_file: 0,
      act: 0,
      annexure: 0,
      other: 0,
    };

    for (const doc of documents) {
      breakdown[doc.documentType]++;
    }

    return breakdown;
  }, [documents]);

  // Handle add files button click
  const handleAddFiles = useCallback(() => {
    setAddDialogOpen(true);
  }, []);

  // Handle upload complete
  const handleUploadComplete = useCallback(() => {
    setAddDialogOpen(false);
    refresh();
  }, [refresh]);

  // Handle retry all stuck documents
  const handleRetryAllStuck = useCallback(async () => {
    setIsRetryingAll(true);
    try {
      const result = await retryAllStuckDocuments(matterId);
      if (result.retried > 0) {
        toast.success(`Retrying ${result.retried} document${result.retried !== 1 ? 's' : ''}`);
      } else {
        toast.info('No documents needed retry');
      }
      if (result.errors.length > 0) {
        toast.warning(`${result.errors.length} document${result.errors.length !== 1 ? 's' : ''} failed to retry`);
      }
      refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to retry documents';
      toast.error(message);
    } finally {
      setIsRetryingAll(false);
    }
  }, [matterId, refresh]);

  // Show loading state
  if (isLoading && !documents.length) {
    return <DocumentsSkeleton />;
  }

  // Show error state
  if (error && !documents.length) {
    return <DocumentsError message={error} />;
  }

  return (
    <div className={className} data-testid="documents-content">
      <div className="space-y-6">
        {/* Header with stats and add button */}
        <DocumentsHeader
          totalCount={processingStats.totalCount}
          processingCount={processingStats.processingCount}
          processingPercent={processingStats.processingPercent}
          stuckCount={processingStats.stuckCount}
          typeBreakdown={typeBreakdown}
          onAddFiles={handleAddFiles}
          onRetryAllStuck={handleRetryAllStuck}
          isRetryingAll={isRetryingAll}
        />

        {/* Error Display (inline, when data exists) */}
        {error && documents.length > 0 && (
          <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
            {error}
          </div>
        )}

        {/* Cross-tab navigation: prompt to open the targeted document */}
        {targetDoc && (
          <div className="flex items-center justify-between p-3 rounded-lg border bg-primary/5 border-primary/20">
            <span className="text-sm font-medium">
              {targetDoc.filename}{pageParam ? `, page ${pageParam}` : ''}
            </span>
            <button
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
              onClick={() => handleOpenDocument(targetDoc, pageParam || undefined)}
            >
              <FileText className="h-3.5 w-3.5" />
              View Document
            </button>
          </div>
        )}

        {/* Document List - pass documents to avoid double fetching */}
        <DocumentList
          matterId={matterId}
          documents={documents}
          onRefresh={refresh}
          onDocumentClick={onDocumentClick || ((doc) => handleOpenDocument(doc))}
        />

        {/* Linked Library Panel - Phase 2: Shared Legal Library */}
        <LinkedLibraryPanel matterId={matterId} />

        {/* Add Documents Dialog */}
        <AddDocumentsDialog
          open={addDialogOpen}
          onOpenChange={setAddDialogOpen}
          matterId={matterId}
          onComplete={handleUploadComplete}
        />

        {/* In-app PDF Viewer (BUG-LT3-G / BUG-LT3-H / BUG-LT3-I fix) */}
        <PdfViewerModal
          open={viewerOpen}
          onOpenChange={setViewerOpen}
          documentUrl={viewerUrl}
          documentId={viewerDocId}
          documentName={viewerDocName}
          initialPage={viewerInitialPage}
        />
      </div>
    </div>
  );
}
