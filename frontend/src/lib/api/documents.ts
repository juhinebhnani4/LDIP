/**
 * Document API Functions
 *
 * Handles document upload to backend API.
 * All operations MUST include matter_id for isolation.
 */

import type { DocumentType, UploadResponse } from '@/types/document';
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
