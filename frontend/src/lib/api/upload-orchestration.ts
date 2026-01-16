/**
 * Upload Orchestration
 *
 * Orchestrates the real upload flow:
 * 1. Create matter via POST /api/matters
 * 2. Upload files via POST /api/documents/upload
 * 3. Track progress via callbacks
 *
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 */

import { api, ApiError } from '@/lib/api/client';
import { uploadFile } from '@/lib/api/documents';
// UploadResponse type used by uploadFile function
import type { UploadProgress } from '@/types/upload';

// =============================================================================
// Types
// =============================================================================

/** Matter creation response from POST /api/matters */
interface CreateMatterResponse {
  data: {
    id: string;
    title: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
}

/** Callbacks for upload progress tracking */
export interface UploadOrchestrationCallbacks {
  /** Called when a matter is successfully created */
  onMatterCreated?: (matterId: string) => void;
  /** Called when file upload progress updates */
  onUploadProgress?: (fileName: string, progress: UploadProgress) => void;
  /** Called when a file upload completes successfully */
  onFileUploaded?: (fileName: string, documentId: string) => void;
  /** Called when a file upload fails */
  onFileError?: (fileName: string, error: string) => void;
  /** Called when all uploads are complete */
  onAllUploadsComplete?: (successCount: number, failedCount: number) => void;
}

/** Result of the upload orchestration */
export interface UploadOrchestrationResult {
  /** Created matter ID */
  matterId: string;
  /** Map of file names to document IDs */
  uploadedDocuments: Map<string, string>;
  /** Map of failed file names to error messages */
  failedUploads: Map<string, string>;
  /** Whether all uploads succeeded */
  allSucceeded: boolean;
}

// =============================================================================
// Main Function
// =============================================================================

/**
 * Create a matter and upload all files.
 *
 * This function:
 * 1. Creates a new matter with the given name
 * 2. Uploads each file to the matter
 * 3. Reports progress via callbacks
 * 4. Returns the matter ID and upload results
 *
 * @param matterName - Name for the new matter
 * @param files - Files to upload
 * @param callbacks - Progress callbacks
 * @param abortSignal - Optional signal to abort the operation
 * @returns Upload result with matter ID and document IDs
 *
 * @throws Error if matter creation fails
 *
 * @example
 * const result = await createMatterAndUpload(
 *   'Smith v. Jones',
 *   files,
 *   {
 *     onMatterCreated: (id) => setMatterId(id),
 *     onUploadProgress: (name, progress) => setProgress(name, progress),
 *     onFileUploaded: (name, docId) => addDocument(docId),
 *     onFileError: (name, error) => setError(name, error),
 *   }
 * );
 */
export async function createMatterAndUpload(
  matterName: string,
  files: File[],
  callbacks: UploadOrchestrationCallbacks = {},
  abortSignal?: AbortSignal
): Promise<UploadOrchestrationResult> {
  const {
    onMatterCreated,
    onUploadProgress,
    onFileUploaded,
    onFileError,
    onAllUploadsComplete,
  } = callbacks;

  // Track results
  const uploadedDocuments = new Map<string, string>();
  const failedUploads = new Map<string, string>();

  // Step 1: Create matter
  let matterId: string;
  try {
    const response = await api.post<CreateMatterResponse>('/api/matters', {
      title: matterName,
    });
    matterId = response.data.id;
    onMatterCreated?.(matterId);
  } catch (err) {
    const errorMessage =
      err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : 'Failed to create matter';
    throw new Error(`Matter creation failed: ${errorMessage}`);
  }

  // Check if aborted
  if (abortSignal?.aborted) {
    throw new Error('Upload cancelled');
  }

  // Step 2: Upload each file
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (!file) continue;

    // Check if aborted before each file
    if (abortSignal?.aborted) {
      // Mark remaining files as cancelled
      for (let j = i; j < files.length; j++) {
        const remainingFile = files[j];
        if (remainingFile) {
          failedUploads.set(remainingFile.name, 'Upload cancelled');
          onFileError?.(remainingFile.name, 'Upload cancelled');
        }
      }
      break;
    }

    // Initialize progress for this file
    onUploadProgress?.(file.name, {
      fileName: file.name,
      fileSize: file.size,
      progressPct: 0,
      status: 'pending',
    });

    try {
      // Start uploading
      onUploadProgress?.(file.name, {
        fileName: file.name,
        fileSize: file.size,
        progressPct: 0,
        status: 'uploading',
      });

      // Upload file using existing uploadFile function
      // Note: uploadFile uses its own store updates, but we also call our callbacks
      const response = await uploadFile(file, `file-${i}-${Date.now()}`, {
        matterId,
        onProgress: (pct) => {
          onUploadProgress?.(file.name, {
            fileName: file.name,
            fileSize: file.size,
            progressPct: pct,
            status: pct >= 100 ? 'complete' : 'uploading',
          });
        },
        abortSignal,
      });

      // Success
      uploadedDocuments.set(file.name, response.data.documentId);
      onUploadProgress?.(file.name, {
        fileName: file.name,
        fileSize: file.size,
        progressPct: 100,
        status: 'complete',
      });
      onFileUploaded?.(file.name, response.data.documentId);
    } catch (err) {
      // Failed
      const errorMessage =
        err instanceof Error ? err.message : 'Upload failed';
      failedUploads.set(file.name, errorMessage);
      onUploadProgress?.(file.name, {
        fileName: file.name,
        fileSize: file.size,
        progressPct: 0,
        status: 'error',
        errorMessage,
      });
      onFileError?.(file.name, errorMessage);
      // Continue with other files - don't abort the whole batch
    }
  }

  // Notify completion
  const successCount = uploadedDocuments.size;
  const failedCount = failedUploads.size;
  onAllUploadsComplete?.(successCount, failedCount);

  return {
    matterId,
    uploadedDocuments,
    failedUploads,
    allSucceeded: failedCount === 0,
  };
}

/**
 * Upload files to an existing matter.
 *
 * Use this when you already have a matter ID and just need to upload files.
 *
 * @param matterId - Existing matter ID
 * @param files - Files to upload
 * @param callbacks - Progress callbacks (excluding onMatterCreated)
 * @param abortSignal - Optional signal to abort the operation
 * @returns Upload results
 */
export async function uploadToExistingMatter(
  matterId: string,
  files: File[],
  callbacks: Omit<UploadOrchestrationCallbacks, 'onMatterCreated'> = {},
  abortSignal?: AbortSignal
): Promise<Omit<UploadOrchestrationResult, 'matterId'>> {
  const {
    onUploadProgress,
    onFileUploaded,
    onFileError,
    onAllUploadsComplete,
  } = callbacks;

  const uploadedDocuments = new Map<string, string>();
  const failedUploads = new Map<string, string>();

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (!file) continue;

    if (abortSignal?.aborted) {
      for (let j = i; j < files.length; j++) {
        const remainingFile = files[j];
        if (remainingFile) {
          failedUploads.set(remainingFile.name, 'Upload cancelled');
          onFileError?.(remainingFile.name, 'Upload cancelled');
        }
      }
      break;
    }

    onUploadProgress?.(file.name, {
      fileName: file.name,
      fileSize: file.size,
      progressPct: 0,
      status: 'pending',
    });

    try {
      onUploadProgress?.(file.name, {
        fileName: file.name,
        fileSize: file.size,
        progressPct: 0,
        status: 'uploading',
      });

      const response = await uploadFile(file, `file-${i}-${Date.now()}`, {
        matterId,
        onProgress: (pct) => {
          onUploadProgress?.(file.name, {
            fileName: file.name,
            fileSize: file.size,
            progressPct: pct,
            status: pct >= 100 ? 'complete' : 'uploading',
          });
        },
        abortSignal,
      });

      uploadedDocuments.set(file.name, response.data.documentId);
      onUploadProgress?.(file.name, {
        fileName: file.name,
        fileSize: file.size,
        progressPct: 100,
        status: 'complete',
      });
      onFileUploaded?.(file.name, response.data.documentId);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Upload failed';
      failedUploads.set(file.name, errorMessage);
      onUploadProgress?.(file.name, {
        fileName: file.name,
        fileSize: file.size,
        progressPct: 0,
        status: 'error',
        errorMessage,
      });
      onFileError?.(file.name, errorMessage);
    }
  }

  const successCount = uploadedDocuments.size;
  const failedCount = failedUploads.size;
  onAllUploadsComplete?.(successCount, failedCount);

  return {
    uploadedDocuments,
    failedUploads,
    allSucceeded: failedCount === 0,
  };
}
