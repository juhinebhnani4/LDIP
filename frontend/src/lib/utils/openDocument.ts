/**
 * Utility to open a document directly by filename.
 *
 * Resolves filename → documentId → signed URL, then opens in a new tab.
 * Used by summary components (PartiesSection, CitationLink, etc.) to
 * open source documents without navigating to the Documents tab first.
 */

import { toast } from 'sonner';
import { fetchDocuments, fetchDocument } from '@/lib/api/documents';

/**
 * Open a document in a new browser tab, given its filename.
 *
 * @param matterId - Matter the document belongs to
 * @param documentName - Filename to look up
 * @param page - Optional page number to scroll to via #page= anchor
 */
export async function openDocumentByName(
  matterId: string,
  documentName: string,
  page?: number | string
): Promise<void> {
  const toastId = toast.loading('Opening document…');
  try {
    // Resolve filename → document ID
    const response = await fetchDocuments(matterId, { perPage: 100 });
    const decoded = decodeURIComponent(documentName);
    const doc = response.data.find(
      (d) => d.filename === documentName || d.filename === decoded
    );

    if (!doc) {
      toast.error('Document not found', { id: toastId });
      return;
    }

    // Fetch signed URL
    const fullDoc = await fetchDocument(doc.id);
    const url = page
      ? `${fullDoc.storagePath}#page=${page}`
      : fullDoc.storagePath;

    window.open(url, '_blank');
    toast.dismiss(toastId);
  } catch {
    toast.error('Failed to open document', { id: toastId });
  }
}
