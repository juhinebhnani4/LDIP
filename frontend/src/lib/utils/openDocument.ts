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
 * Resolve a document filename to its ID, filename, and signed storage URL.
 * Uses server-side filename filter for O(1) lookup regardless of document count.
 *
 * @param matterId - Matter the document belongs to
 * @param documentName - Filename to look up
 * @returns Resolved document info, or null if not found
 */
export async function resolveDocumentByName(
  matterId: string,
  documentName: string
): Promise<{ id: string; filename: string; storagePath: string } | null> {
  // Try exact match first, then URL-decoded form
  let response = await fetchDocuments(matterId, {
    perPage: 1,
    filters: { filename: documentName },
  });
  if (response.data.length === 0) {
    const decoded = decodeURIComponent(documentName);
    if (decoded !== documentName) {
      response = await fetchDocuments(matterId, {
        perPage: 1,
        filters: { filename: decoded },
      });
    }
  }
  const doc = response.data[0];
  if (!doc) return null;

  const fullDoc = await fetchDocument(doc.id);
  if (!fullDoc.storagePath) return null;

  return { id: doc.id, filename: doc.filename, storagePath: fullDoc.storagePath };
}

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
    const resolved = await resolveDocumentByName(matterId, documentName);
    if (!resolved) {
      toast.error('Document not found', { id: toastId });
      return;
    }

    const url = page
      ? `${resolved.storagePath}#page=${page}`
      : resolved.storagePath;

    window.open(url, '_blank');
    toast.dismiss(toastId);
  } catch {
    toast.error('Failed to open document', { id: toastId });
  }
}
