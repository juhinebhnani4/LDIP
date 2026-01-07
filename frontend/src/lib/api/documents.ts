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
  UploadResponse,
} from '@/types/document';
import { createClient } from '@/lib/supabase/client';
import { useUploadStore } from '@/stores/uploadStore';

/** Backend API base URL */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Upload API endpoint */
const UPLOAD_ENDPOINT = `${API_BASE_URL}/api/documents/upload`;

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
 * Upload multiple files sequentially
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
    const results = await Promise.allSettled(
      files.map(({ id, file }) =>
        uploadFile(file, id, { matterId, documentType })
      )
    );
    return results;
  } finally {
    useUploadStore.getState().setUploading(false);
  }
}

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
