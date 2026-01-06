/**
 * Document API Functions
 *
 * Handles document upload to backend API.
 * All operations MUST include matter_id for isolation.
 *
 * NOTE: Actual backend endpoint will be implemented in Story 2a-2.
 * This file provides the frontend upload integration with progress tracking.
 */

import type { DocumentType, UploadResponse } from '@/types/document';
import { useUploadStore } from '@/stores/uploadStore';

/** Upload API endpoint (to be implemented in Story 2a-2) */
const UPLOAD_ENDPOINT = '/api/documents/upload';

interface UploadOptions {
  matterId: string;
  documentType?: DocumentType;
  onProgress?: (progress: number) => void;
  abortSignal?: AbortSignal;
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

    // TODO(Story 2a-2): Add auth header when integrating with real backend
    // Authentication will be handled via JWT token from Supabase auth.
    // See: frontend/src/lib/supabase/client.ts for getSupabaseClient()
    // const token = await getAuthToken();
    // xhr.setRequestHeader('Authorization', `Bearer ${token}`);

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
