/**
 * Document API Functions
 *
 * Handles document upload and management via backend API.
 * All operations MUST include matter_id for isolation.
 */

import type {
  BulkDocumentUpdateRequest,
  BulkUpdateResponse,
  Document,
  DocumentDetailResponse,
  DocumentFilters,
  DocumentListResponse,
  DocumentSort,
  DocumentType,
  DocumentUpdateRequest,
  ManualReviewResponse,
  OCRConfidenceResult,
  OCRQualityResponse,
  UploadResponse,
} from '@/types/document';
import { createClient } from '@/lib/supabase/client';
import { useUploadStore } from '@/stores/uploadStore';
import {
  compressPdfIfNeeded,
  needsCompression,
  getCompressionStats,
  compressionExceedsLimit,
  COMPRESSION_THRESHOLD_BYTES,
  SUPABASE_FILE_LIMIT_BYTES,
} from '@/lib/utils/pdf-compression';

/** Backend API base URL */
const API_BASE_URL = (() => {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url && process.env.NODE_ENV === 'production') {
    throw new Error('NEXT_PUBLIC_API_URL environment variable is required in production');
  }
  return url || 'http://localhost:8000';
})();

/** Upload API endpoint */
const UPLOAD_ENDPOINT = `${API_BASE_URL}/api/documents/upload`;

/** Maximum concurrent uploads to prevent browser/network saturation */
const MAX_CONCURRENT_UPLOADS = 3;

interface UploadOptions {
  matterId: string;
  documentType?: DocumentType;
  onProgress?: (progress: number) => void;
  abortSignal?: AbortSignal;
}

/**
 * Get the current auth token from Supabase session
 *
 * @returns JWT access token or null if not authenticated
 */
async function getAuthToken(): Promise<string | null> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

/**
 * Upload a single file to the backend
 *
 * Uses XMLHttpRequest for progress tracking (fetch doesn't support upload progress).
 * Updates Zustand store with progress automatically.
 *
 * @param file - File to upload
 * @param fileId - ID in upload store for progress tracking
 * @param options - Upload options including matterId
 * @returns Upload response from backend
 */
export async function uploadFile(
  file: File,
  fileId: string,
  options: UploadOptions
): Promise<UploadResponse> {
  const { matterId, documentType = 'case_file', onProgress, abortSignal } = options;

  // Get auth token before starting upload
  const token = await getAuthToken();
  if (!token) {
    const error = new Error('Not authenticated');
    useUploadStore.getState().updateStatus(fileId, 'error', error.message);
    throw error;
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();

    formData.append('file', file);
    formData.append('matter_id', matterId);
    formData.append('document_type', documentType);

    // Handle abort signal
    if (abortSignal) {
      abortSignal.addEventListener('abort', () => {
        xhr.abort();
        reject(new Error('Upload cancelled'));
      });
    }

    // Track upload progress
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const progress = Math.round((event.loaded / event.total) * 100);

        // Update store
        useUploadStore.getState().updateProgress(fileId, progress);

        // Call optional callback
        onProgress?.(progress);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText) as UploadResponse;
          useUploadStore.getState().updateStatus(fileId, 'completed');
          resolve(response);
        } catch {
          const error = new Error('Invalid response format');
          useUploadStore.getState().updateStatus(fileId, 'error', error.message);
          reject(error);
        }
      } else {
        let errorMessage = `Upload failed: ${xhr.statusText}`;
        try {
          const errorResponse = JSON.parse(xhr.responseText);
          errorMessage = errorResponse.error?.message ?? errorMessage;
        } catch {
          // Use default error message
        }
        useUploadStore.getState().updateStatus(fileId, 'error', errorMessage);
        reject(new Error(errorMessage));
      }
    };

    xhr.onerror = () => {
      const error = new Error('Network error during upload');
      useUploadStore.getState().updateStatus(fileId, 'error', error.message);
      reject(error);
    };

    xhr.onabort = () => {
      useUploadStore.getState().updateStatus(fileId, 'error', 'Upload cancelled');
      reject(new Error('Upload cancelled'));
    };

    xhr.open('POST', UPLOAD_ENDPOINT);

    // Add authentication header
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    xhr.send(formData);
  });
}

/**
 * Error thrown when a file exceeds the Supabase upload limit even after compression.
 */
export class FileTooLargeError extends Error {
  constructor(
    public filename: string,
    public fileSize: number,
    public limit: number = SUPABASE_FILE_LIMIT_BYTES
  ) {
    const sizeMB = (fileSize / (1024 * 1024)).toFixed(1);
    const limitMB = (limit / (1024 * 1024)).toFixed(0);
    super(
      `File "${filename}" is ${sizeMB}MB which exceeds the ${limitMB}MB upload limit. Please split this document into smaller parts.`
    );
    this.name = 'FileTooLargeError';
  }
}

/**
 * Compress a file if it exceeds the size threshold.
 * Updates the upload store with compression status.
 * Throws FileTooLargeError if file still exceeds limit after compression.
 *
 * @param fileId - ID in upload store
 * @param file - File to potentially compress
 * @returns The file (compressed or original)
 * @throws FileTooLargeError if file exceeds 50MB limit after compression
 */
async function compressFileIfNeeded(fileId: string, file: File): Promise<File> {
  if (!needsCompression(file)) {
    // Even files under compression threshold need to be checked against Supabase limit
    if (file.size > SUPABASE_FILE_LIMIT_BYTES) {
      throw new FileTooLargeError(file.name, file.size);
    }
    return file;
  }

  const store = useUploadStore.getState();

  // Update status to compressing
  store.updateStatus(fileId, 'compressing');

  try {
    const result = await compressPdfIfNeeded(file, (progress) => {
      // Could add more granular progress here if needed
      console.log(`[Compression] ${file.name}: ${progress.message}`);
    });

    if (result.wasCompressed) {
      const compressionInfo = getCompressionStats(result);
      store.updateFileAfterCompression(
        fileId,
        result.file,
        result.originalSize,
        compressionInfo
      );
      console.log(`[Compression] ${file.name}: ${compressionInfo}`);
    } else if (result.warning) {
      // File couldn't be compressed or is still too large
      console.warn(`[Compression] ${file.name}: ${result.warning}`);
    }

    // Check if file still exceeds Supabase limit after compression
    if (compressionExceedsLimit(result)) {
      store.updateStatus(
        fileId,
        'error',
        `File exceeds 50MB limit after compression (${(result.finalSize / (1024 * 1024)).toFixed(1)}MB). Please split this document.`
      );
      throw new FileTooLargeError(file.name, result.finalSize);
    }

    return result.file;
  } catch (error) {
    // Re-throw FileTooLargeError
    if (error instanceof FileTooLargeError) {
      throw error;
    }

    console.error(`[Compression] Failed for ${file.name}:`, error);
    // Continue with original file if compression fails
    store.updateStatus(fileId, 'pending');

    // But still check if original file exceeds limit
    if (file.size > SUPABASE_FILE_LIMIT_BYTES) {
      store.updateStatus(
        fileId,
        'error',
        `File exceeds 50MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB). Please split this document.`
      );
      throw new FileTooLargeError(file.name, file.size);
    }

    return file;
  }
}

/**
 * Upload multiple files with concurrency throttling
 *
 * Automatically compresses PDF files larger than 50MB before uploading
 * to comply with Supabase storage limits.
 *
 * Limits concurrent uploads to MAX_CONCURRENT_UPLOADS to prevent
 * browser/network saturation when uploading many files at once.
 *
 * @param files - Array of UploadFile objects from store
 * @param matterId - Matter ID for isolation
 * @param documentType - Document type for all files
 * @returns Array of upload results
 */
export async function uploadFiles(
  files: { id: string; file: File }[],
  matterId: string,
  documentType: DocumentType = 'case_file'
): Promise<PromiseSettledResult<UploadResponse>[]> {
  useUploadStore.getState().setUploading(true);

  try {
    // First, compress any large files
    const filesToUpload: { id: string; file: File }[] = [];

    for (const { id, file } of files) {
      const processedFile = await compressFileIfNeeded(id, file);
      filesToUpload.push({ id, file: processedFile });
    }

    const results: PromiseSettledResult<UploadResponse>[] = [];

    // Process files in batches of MAX_CONCURRENT_UPLOADS
    for (let i = 0; i < filesToUpload.length; i += MAX_CONCURRENT_UPLOADS) {
      const batch = filesToUpload.slice(i, i + MAX_CONCURRENT_UPLOADS);
      const batchResults = await Promise.allSettled(
        batch.map(({ id, file }) =>
          uploadFile(file, id, { matterId, documentType })
        )
      );
      results.push(...batchResults);
    }

    return results;
  } finally {
    useUploadStore.getState().setUploading(false);
  }
}

/** Re-export compression constants for UI display */
export { COMPRESSION_THRESHOLD_BYTES, SUPABASE_FILE_LIMIT_BYTES };

// =============================================================================
// Document List and Management API Functions
// =============================================================================

interface FetchDocumentsOptions {
  page?: number;
  perPage?: number;
  filters?: DocumentFilters;
  sort?: DocumentSort;
}

/**
 * Convert object keys from snake_case to camelCase
 */
function toCamelCase<T>(obj: Record<string, unknown>): T {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter: string) =>
      letter.toUpperCase()
    );
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      result[camelKey] = toCamelCase(value as Record<string, unknown>);
    } else if (Array.isArray(value)) {
      result[camelKey] = value.map((item) =>
        typeof item === 'object' && item !== null
          ? toCamelCase(item as Record<string, unknown>)
          : item
      );
    } else {
      result[camelKey] = value;
    }
  }
  return result as T;
}

/**
 * Fetch documents for a matter with pagination and filtering
 *
 * @param matterId - Matter ID
 * @param options - Pagination and filter options
 * @returns Paginated document list
 */
export async function fetchDocuments(
  matterId: string,
  options: FetchDocumentsOptions = {}
): Promise<DocumentListResponse> {
  const { page = 1, perPage = 20, filters = {}, sort } = options;

  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  // Build query params
  const params = new URLSearchParams({
    page: page.toString(),
    per_page: perPage.toString(),
  });

  if (filters.documentType) {
    params.set('document_type', filters.documentType);
  }
  if (filters.status) {
    params.set('status', filters.status);
  }
  if (filters.isReferenceMaterial !== undefined) {
    params.set('is_reference_material', filters.isReferenceMaterial.toString());
  }

  // Add sorting params
  if (sort) {
    params.set('sort_by', sort.column);
    params.set('sort_order', sort.order);
  }

  const url = `${API_BASE_URL}/api/matters/${matterId}/documents?${params.toString()}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to fetch documents: ${response.statusText}`
    );
  }

  const data = await response.json();
  return toCamelCase<DocumentListResponse>(data);
}

/**
 * Fetch a single document's details with signed URL
 *
 * @param documentId - Document ID
 * @returns Document details
 */
export async function fetchDocument(documentId: string): Promise<Document> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/documents/${documentId}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to fetch document: ${response.statusText}`
    );
  }

  const data = await response.json();
  const result = toCamelCase<DocumentDetailResponse>(data);
  return result.data;
}

/**
 * Update a document's metadata
 *
 * @param documentId - Document ID
 * @param update - Fields to update
 * @returns Updated document
 */
export async function updateDocument(
  documentId: string,
  update: DocumentUpdateRequest
): Promise<Document> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/documents/${documentId}`;

  // Convert to snake_case for API
  const body: Record<string, unknown> = {};
  if (update.documentType !== undefined) {
    body.document_type = update.documentType;
  }
  if (update.isReferenceMaterial !== undefined) {
    body.is_reference_material = update.isReferenceMaterial;
  }
  if (update.filename !== undefined) {
    body.filename = update.filename;
  }

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to update document: ${response.statusText}`
    );
  }

  const data = await response.json();
  const result = toCamelCase<DocumentDetailResponse>(data);
  return result.data;
}

/**
 * Bulk update document types
 *
 * @param update - Bulk update request
 * @returns Update result
 */
export async function bulkUpdateDocuments(
  update: BulkDocumentUpdateRequest
): Promise<BulkUpdateResponse['data']> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/documents/bulk`;

  // Convert to snake_case for API
  const body = {
    document_ids: update.documentIds,
    document_type: update.documentType,
  };

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to bulk update documents: ${response.statusText}`
    );
  }

  const data = await response.json();
  const result = toCamelCase<BulkUpdateResponse>(data);
  return result.data;
}

// =============================================================================
// OCR Quality Assessment API Functions
// =============================================================================

/**
 * Fetch OCR quality metrics for a document
 *
 * @param documentId - Document ID
 * @returns OCR confidence result with per-page breakdown
 */
export async function fetchOCRQuality(documentId: string): Promise<OCRConfidenceResult> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/documents/${documentId}/ocr-quality`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to fetch OCR quality: ${response.statusText}`
    );
  }

  const data = await response.json();
  const result = toCamelCase<OCRQualityResponse>(data);
  return result.data;
}

/**
 * Request manual review for specific pages
 *
 * @param documentId - Document ID
 * @param pages - List of page numbers to flag for review
 * @returns Manual review response
 */
export async function requestManualReview(
  documentId: string,
  pages: number[]
): Promise<ManualReviewResponse['data']> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/documents/${documentId}/request-manual-review`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ pages }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to request manual review: ${response.statusText}`
    );
  }

  const data = await response.json();
  const result = toCamelCase<ManualReviewResponse>(data);
  return result.data;
}

// =============================================================================
// Document Action API Functions (Story 10D.4)
// =============================================================================

/**
 * Delete a document (soft-delete with 30-day retention)
 *
 * @param documentId - Document ID to delete
 * @returns Delete response with message
 */
export async function deleteDocument(
  documentId: string
): Promise<{ success: boolean; message: string; deletedAt: string }> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/documents/${documentId}`;

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to delete document: ${response.statusText}`
    );
  }

  const data = await response.json();
  return toCamelCase<{ success: boolean; message: string; deletedAt: string }>(data.data);
}

/**
 * Rename a document
 *
 * @param documentId - Document ID to rename
 * @param filename - New filename
 * @returns Updated document
 */
export async function renameDocument(
  documentId: string,
  filename: string
): Promise<Document> {
  return updateDocument(documentId, { filename });
}

// =============================================================================
// Document Retry API Functions
// =============================================================================

export interface RetryResponse {
  success: boolean;
  documentId: string;
  taskId: string | null;
  message: string;
  retryType: 'full' | 'rag';
}

/**
 * Retry processing for a stuck or failed document
 *
 * @param matterId - Matter ID
 * @param documentId - Document ID to retry
 * @param retryType - 'full' (full OCR), 'rag' (RAG only), 'auto' (detect)
 * @returns Retry response with task details
 */
export async function retryDocumentProcessing(
  matterId: string,
  documentId: string,
  retryType: 'full' | 'rag' | 'auto' = 'auto'
): Promise<RetryResponse> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/matters/${matterId}/documents/${documentId}/retry?retry_type=${retryType}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to retry document: ${response.statusText}`
    );
  }

  const data = await response.json();
  return toCamelCase<{ data: RetryResponse }>(data).data;
}

/**
 * Retry all stuck documents in a matter
 *
 * @param matterId - Matter ID
 * @returns Summary of retry operations
 */
export async function retryAllStuckDocuments(
  matterId: string
): Promise<{
  totalChecked: number;
  retried: number;
  skipped: number;
  errors: Array<{ documentId: string; error: string }>;
}> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/matters/${matterId}/documents/retry-all-stuck`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error?.message ?? `Failed to retry stuck documents: ${response.statusText}`
    );
  }

  const data = await response.json();
  return toCamelCase<{ data: {
    totalChecked: number;
    retried: number;
    skipped: number;
    errors: Array<{ documentId: string; error: string }>;
  }}>(data).data;
}

// =============================================================================
// Health Check API Functions
// =============================================================================

export interface CeleryStatus {
  status: 'healthy' | 'unhealthy' | 'error';
  workers: Record<string, { ok: string }>;
  workerCount: number;
  queues: string[];
  message?: string;
}

/**
 * Check Celery worker health status
 *
 * @returns Celery status with worker info
 */
export async function checkCeleryHealth(): Promise<CeleryStatus> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const url = `${API_BASE_URL}/api/health/celery`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    // Return unhealthy status instead of throwing
    return {
      status: 'error',
      workers: {},
      workerCount: 0,
      queues: [],
      message: `Health check failed: ${response.statusText}`,
    };
  }

  const data = await response.json();
  return toCamelCase<{ data: CeleryStatus }>(data).data;
}
