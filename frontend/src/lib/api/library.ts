/**
 * Library API Client for Shared Legal Library
 *
 * Provides typed API functions for library operations including:
 * - Listing and searching library documents
 * - Linking/unlinking documents to matters
 * - Checking for duplicates before upload
 *
 * Phase 2: Shared Legal Library feature.
 */

import { api } from './client';
import type {
  DuplicateCheckRequest,
  DuplicateCheckResponse,
  LibraryDocument,
  LibraryDocumentListResponse,
  LibraryListOptions,
  LibraryLinkRequest,
  LinkedLibraryDocumentsResponse,
  LinkSuccessResponse,
  UnlinkSuccessResponse,
} from '@/types/library';

/**
 * Build query string from options object.
 */
function buildQueryString(options: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(options)) {
    if (value !== undefined) {
      // Convert camelCase to snake_case for API
      const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
      params.append(snakeKey, String(value));
    }
  }
  const queryString = params.toString();
  return queryString ? `?${queryString}` : '';
}

// =============================================================================
// Library Document Operations
// =============================================================================

/**
 * Get paginated list of library documents with optional filters.
 *
 * @param options - Filter and pagination options
 * @returns Paginated list of library documents
 *
 * @example
 * ```ts
 * const result = await getLibraryDocuments({
 *   documentType: 'act',
 *   search: 'Contract',
 *   page: 1,
 *   perPage: 20,
 * });
 * console.log(result.documents); // LibraryDocumentListItem[]
 * ```
 */
export async function getLibraryDocuments(
  options: LibraryListOptions = {}
): Promise<LibraryDocumentListResponse> {
  const queryString = buildQueryString({
    documentType: options.documentType,
    year: options.year,
    jurisdiction: options.jurisdiction,
    status: options.status,
    search: options.search,
    page: options.page,
    perPage: options.perPage,
  });

  return api.get<LibraryDocumentListResponse>(`/api/library/documents${queryString}`);
}

/**
 * Get a single library document by ID.
 *
 * @param documentId - Library document UUID
 * @returns Library document details
 *
 * @example
 * ```ts
 * const doc = await getLibraryDocument('doc-123');
 * console.log(doc.title); // "Indian Contract Act, 1872"
 * ```
 */
export async function getLibraryDocument(documentId: string): Promise<LibraryDocument> {
  return api.get<LibraryDocument>(`/api/library/documents/${documentId}`);
}

/**
 * Check for potential duplicate library documents before upload.
 *
 * @param request - Title and optional year to check
 * @returns Duplicate check result with potential matches
 *
 * @example
 * ```ts
 * const check = await checkLibraryDuplicates({
 *   title: 'Indian Contract Act, 1872',
 *   year: 1872,
 * });
 * if (check.hasDuplicates) {
 *   console.log('Potential duplicates:', check.duplicates);
 * }
 * ```
 */
export async function checkLibraryDuplicates(
  request: DuplicateCheckRequest
): Promise<DuplicateCheckResponse> {
  return api.post<DuplicateCheckResponse>('/api/library/documents/check-duplicates', request);
}

// =============================================================================
// Matter Library Link Operations
// =============================================================================

/**
 * Get library documents linked to a matter.
 *
 * @param matterId - Matter UUID
 * @returns List of linked library documents
 *
 * @example
 * ```ts
 * const linked = await getLinkedLibraryDocuments('matter-123');
 * console.log(linked.documents); // LibraryDocumentListItem[]
 * ```
 */
export async function getLinkedLibraryDocuments(
  matterId: string
): Promise<LinkedLibraryDocumentsResponse> {
  return api.get<LinkedLibraryDocumentsResponse>(`/api/matters/${matterId}/library/documents`);
}

/**
 * Link a library document to a matter.
 *
 * @param matterId - Matter UUID
 * @param request - Link request with library document ID
 * @returns Link success response
 *
 * @example
 * ```ts
 * const result = await linkLibraryDocument('matter-123', {
 *   libraryDocumentId: 'doc-456',
 * });
 * console.log(result.link.linkedAt); // Timestamp
 * ```
 */
export async function linkLibraryDocument(
  matterId: string,
  request: LibraryLinkRequest
): Promise<LinkSuccessResponse> {
  return api.post<LinkSuccessResponse>(`/api/matters/${matterId}/library/documents`, request);
}

/**
 * Unlink a library document from a matter.
 *
 * @param matterId - Matter UUID
 * @param documentId - Library document UUID to unlink
 * @returns Unlink success response
 *
 * @example
 * ```ts
 * await unlinkLibraryDocument('matter-123', 'doc-456');
 * console.log('Document unlinked');
 * ```
 */
export async function unlinkLibraryDocument(
  matterId: string,
  documentId: string
): Promise<UnlinkSuccessResponse> {
  return api.delete<UnlinkSuccessResponse>(
    `/api/matters/${matterId}/library/documents/${documentId}`
  );
}
