/**
 * Library Types for Shared Legal Library
 *
 * Types for shared library documents (Acts, Statutes, Judgments) that can
 * be linked to multiple matters.
 *
 * Phase 2: Shared Legal Library feature.
 */

// =============================================================================
// Enums
// =============================================================================

/** Type of library document */
export type LibraryDocumentType =
  | 'act'
  | 'statute'
  | 'judgment'
  | 'regulation'
  | 'commentary'
  | 'circular';

/** Source of library document */
export type LibraryDocumentSource = 'user_upload' | 'india_code' | 'manual_import';

/** Processing status of library document */
export type LibraryDocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

// =============================================================================
// Library Document Types
// =============================================================================

/** Library document list item (summary view) */
export interface LibraryDocumentListItem {
  id: string;
  title: string;
  shortTitle: string | null;
  documentType: LibraryDocumentType;
  year: number | null;
  jurisdiction: string | null;
  status: LibraryDocumentStatus;
  source: LibraryDocumentSource;
  pageCount: number | null;
  createdAt: string;
  /** Whether document is linked to the current matter context */
  isLinked: boolean;
  /** When the document was linked to current matter */
  linkedAt: string | null;
}

/** Full library document model */
export interface LibraryDocument {
  id: string;
  filename: string;
  storagePath: string;
  fileSize: number;
  pageCount: number | null;
  documentType: LibraryDocumentType;
  title: string;
  shortTitle: string | null;
  year: number | null;
  jurisdiction: string | null;
  source: LibraryDocumentSource;
  sourceUrl: string | null;
  status: LibraryDocumentStatus;
  processingStartedAt: string | null;
  processingCompletedAt: string | null;
  qualityFlags: string[];
  addedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

/** Request to create a library document */
export interface LibraryDocumentCreateRequest {
  filename: string;
  title: string;
  shortTitle?: string;
  documentType: LibraryDocumentType;
  year?: number;
  jurisdiction?: string;
}

// =============================================================================
// Link Types
// =============================================================================

/** Link between a matter and library document */
export interface MatterLibraryLink {
  id: string;
  matterId: string;
  libraryDocumentId: string;
  linkedBy: string;
  linkedAt: string;
}

/** Request to link a library document to a matter */
export interface LibraryLinkRequest {
  libraryDocumentId: string;
}

// =============================================================================
// Duplicate Detection Types
// =============================================================================

/** Potential duplicate library document */
export interface LibraryDuplicate {
  id: string;
  title: string;
  year: number | null;
  documentType: LibraryDocumentType;
  similarity: number;
}

/** Request to check for duplicates */
export interface DuplicateCheckRequest {
  title: string;
  year?: number;
}

/** Response for duplicate check */
export interface DuplicateCheckResponse {
  hasDuplicates: boolean;
  duplicates: LibraryDuplicate[];
}

// =============================================================================
// Response Types
// =============================================================================

/** Pagination metadata */
export interface LibraryPaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/** Paginated library document list response */
export interface LibraryDocumentListResponse {
  documents: LibraryDocumentListItem[];
  pagination: LibraryPaginationMeta;
}

/** Response for linked library documents in a matter */
export interface LinkedLibraryDocumentsResponse {
  documents: LibraryDocumentListItem[];
  total: number;
}

/** Response for successful link operation */
export interface LinkSuccessResponse {
  success: boolean;
  link: MatterLibraryLink;
}

/** Response for successful unlink operation */
export interface UnlinkSuccessResponse {
  success: boolean;
  message: string;
}

// =============================================================================
// Query Options
// =============================================================================

/** Options for listing library documents */
export interface LibraryListOptions {
  documentType?: LibraryDocumentType;
  year?: number;
  jurisdiction?: string;
  status?: LibraryDocumentStatus;
  search?: string;
  page?: number;
  perPage?: number;
}
