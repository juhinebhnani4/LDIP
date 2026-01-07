/**
 * Document Types
 *
 * Types for document upload and management.
 * All document operations MUST include matter_id for isolation.
 */

/** Document types matching backend enum */
export type DocumentType = 'case_file' | 'act' | 'annexure' | 'other';

/** Document status from processing pipeline */
export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

/** Upload file status for UI tracking */
export type UploadStatus = 'pending' | 'uploading' | 'completed' | 'error';

/** Tracked file in upload queue */
export interface UploadFile {
  id: string;
  file: File;
  progress: number;
  status: UploadStatus;
  error?: string;
}

/** Validation result for file upload */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

/** Validation error structure */
export interface ValidationError {
  file: File;
  code: 'INVALID_TYPE' | 'FILE_TOO_LARGE' | 'EMPTY_FILE';
  message: string;
}

/** Validation warning structure */
export interface ValidationWarning {
  code: 'MAX_FILES_EXCEEDED';
  message: string;
  acceptedCount: number;
  rejectedCount: number;
}

/** Upload request to backend */
export interface UploadRequest {
  matterId: string;
  file: File;
  documentType: DocumentType;
}

/** Upload response from backend */
export interface UploadResponse {
  data: {
    documentId: string;
    filename: string;
    storagePath: string;
    status: DocumentStatus;
  };
}

/** Document record from database */
export interface Document {
  id: string;
  matterId: string;
  filename: string;
  storagePath: string;
  fileSize: number;
  pageCount: number | null;
  documentType: DocumentType;
  isReferenceMaterial: boolean;
  uploadedBy: string;
  uploadedAt: string;
  status: DocumentStatus;
  processingStartedAt: string | null;
  processingCompletedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

/** Document list item (subset of Document for list views) */
export interface DocumentListItem {
  id: string;
  matterId: string;
  filename: string;
  fileSize: number;
  documentType: DocumentType;
  isReferenceMaterial: boolean;
  status: DocumentStatus;
  uploadedAt: string;
  uploadedBy: string;
}

/** Pagination metadata */
export interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/** Paginated document list response */
export interface DocumentListResponse {
  data: DocumentListItem[];
  meta: PaginationMeta;
}

/** Document detail response (includes signed URL) */
export interface DocumentDetailResponse {
  data: Document;
}

/** Document update request */
export interface DocumentUpdateRequest {
  documentType?: DocumentType;
  isReferenceMaterial?: boolean;
}

/** Bulk update request */
export interface BulkDocumentUpdateRequest {
  documentIds: string[];
  documentType: DocumentType;
}

/** Bulk update response */
export interface BulkUpdateResponse {
  data: {
    updatedCount: number;
    requestedCount: number;
    documentType: DocumentType;
  };
}

/** Document list filters */
export interface DocumentFilters {
  documentType?: DocumentType;
  status?: DocumentStatus;
  isReferenceMaterial?: boolean;
}

/** Sortable columns for document list */
export type DocumentSortColumn = 'uploaded_at' | 'filename' | 'file_size' | 'document_type' | 'status';

/** Sort direction */
export type SortOrder = 'asc' | 'desc';

/** Sorting state for document list */
export interface DocumentSort {
  column: DocumentSortColumn;
  order: SortOrder;
}
