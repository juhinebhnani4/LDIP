/**
 * Upload Orchestration Tests
 *
 * Tests for the real upload orchestration module.
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMatterAndUpload, uploadToExistingMatter } from './upload-orchestration';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public code: string,
      message: string,
      public status: number
    ) {
      super(message);
    }
  },
}));

// Mock the uploadFile function
vi.mock('@/lib/api/documents', () => ({
  uploadFile: vi.fn(),
}));

import { api, ApiError } from '@/lib/api/client';
import { uploadFile } from '@/lib/api/documents';

describe('createMatterAndUpload', () => {
  const mockFile1 = new File(['content1'], 'document1.pdf', { type: 'application/pdf' });
  const mockFile2 = new File(['content2'], 'document2.pdf', { type: 'application/pdf' });

  beforeEach(() => {
    vi.clearAllMocks();

    // Default successful matter creation
    vi.mocked(api.post).mockResolvedValue({
      data: {
        id: 'matter-123',
        name: 'Test Matter',
        status: 'active',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    });

    // Default successful file upload
    vi.mocked(uploadFile).mockImplementation(async (file, _fileId, options) => {
      // Simulate progress callback
      options.onProgress?.(50);
      options.onProgress?.(100);
      return {
        data: {
          documentId: `doc-${file.name}`,
          filename: file.name,
          storagePath: `/uploads/${file.name}`,
          status: 'uploaded' as const,
        },
      };
    });
  });

  it('creates a matter with the given name', async () => {
    await createMatterAndUpload('Test Matter', [mockFile1], {});

    expect(api.post).toHaveBeenCalledWith('/api/matters', {
      name: 'Test Matter',
    });
  });

  it('calls onMatterCreated callback with matter ID', async () => {
    const onMatterCreated = vi.fn();

    await createMatterAndUpload('Test Matter', [mockFile1], {
      onMatterCreated,
    });

    expect(onMatterCreated).toHaveBeenCalledWith('matter-123');
  });

  it('uploads all files to the created matter', async () => {
    await createMatterAndUpload('Test Matter', [mockFile1, mockFile2], {});

    expect(uploadFile).toHaveBeenCalledTimes(2);
    expect(uploadFile).toHaveBeenCalledWith(
      mockFile1,
      expect.any(String),
      expect.objectContaining({ matterId: 'matter-123' })
    );
    expect(uploadFile).toHaveBeenCalledWith(
      mockFile2,
      expect.any(String),
      expect.objectContaining({ matterId: 'matter-123' })
    );
  });

  it('calls onUploadProgress for each file', async () => {
    const onUploadProgress = vi.fn();

    await createMatterAndUpload('Test Matter', [mockFile1], {
      onUploadProgress,
    });

    // Should be called for pending, uploading, and complete states
    expect(onUploadProgress).toHaveBeenCalledWith(
      'document1.pdf',
      expect.objectContaining({ status: 'pending' })
    );
    expect(onUploadProgress).toHaveBeenCalledWith(
      'document1.pdf',
      expect.objectContaining({ status: 'uploading' })
    );
    expect(onUploadProgress).toHaveBeenCalledWith(
      'document1.pdf',
      expect.objectContaining({ status: 'complete', progressPct: 100 })
    );
  });

  it('calls onFileUploaded for each successful upload', async () => {
    const onFileUploaded = vi.fn();

    await createMatterAndUpload('Test Matter', [mockFile1, mockFile2], {
      onFileUploaded,
    });

    expect(onFileUploaded).toHaveBeenCalledWith('document1.pdf', 'doc-document1.pdf');
    expect(onFileUploaded).toHaveBeenCalledWith('document2.pdf', 'doc-document2.pdf');
  });

  it('returns matter ID and uploaded document IDs', async () => {
    const result = await createMatterAndUpload(
      'Test Matter',
      [mockFile1, mockFile2],
      {}
    );

    expect(result.matterId).toBe('matter-123');
    expect(result.uploadedDocuments.size).toBe(2);
    expect(result.uploadedDocuments.get('document1.pdf')).toBe('doc-document1.pdf');
    expect(result.uploadedDocuments.get('document2.pdf')).toBe('doc-document2.pdf');
    expect(result.allSucceeded).toBe(true);
  });

  it('handles file upload failures gracefully', async () => {
    const onFileError = vi.fn();

    vi.mocked(uploadFile)
      .mockResolvedValueOnce({
        data: { documentId: 'doc-1', filename: 'document1.pdf', storagePath: '/uploads/document1.pdf', status: 'uploaded' as const },
      })
      .mockRejectedValueOnce(new Error('Upload failed'));

    const result = await createMatterAndUpload(
      'Test Matter',
      [mockFile1, mockFile2],
      { onFileError }
    );

    expect(onFileError).toHaveBeenCalledWith('document2.pdf', 'Upload failed');
    expect(result.uploadedDocuments.size).toBe(1);
    expect(result.failedUploads.size).toBe(1);
    expect(result.failedUploads.get('document2.pdf')).toBe('Upload failed');
    expect(result.allSucceeded).toBe(false);
  });

  it('throws error if matter creation fails', async () => {
    vi.mocked(api.post).mockRejectedValue(
      new ApiError('MATTER_CREATE_FAILED', 'Failed to create matter', 500)
    );

    await expect(
      createMatterAndUpload('Test Matter', [mockFile1], {})
    ).rejects.toThrow('Matter creation failed: Failed to create matter');
  });

  it('calls onAllUploadsComplete with success and failure counts', async () => {
    const onAllUploadsComplete = vi.fn();

    vi.mocked(uploadFile)
      .mockResolvedValueOnce({
        data: { documentId: 'doc-1', filename: 'document1.pdf', storagePath: '/uploads/document1.pdf', status: 'uploaded' as const },
      })
      .mockRejectedValueOnce(new Error('Upload failed'));

    await createMatterAndUpload('Test Matter', [mockFile1, mockFile2], {
      onAllUploadsComplete,
    });

    expect(onAllUploadsComplete).toHaveBeenCalledWith(1, 1);
  });

  it('respects abort signal when aborted before uploads', async () => {
    const abortController = new AbortController();

    // Abort before any uploads
    abortController.abort();

    // When signal is already aborted, it throws immediately after matter creation
    await expect(
      createMatterAndUpload(
        'Test Matter',
        [mockFile1, mockFile2],
        {},
        abortController.signal
      )
    ).rejects.toThrow('Upload cancelled');
  });

  it('marks remaining files as cancelled when aborted during uploads', async () => {
    const abortController = new AbortController();
    const onFileError = vi.fn();
    let uploadCount = 0;

    vi.mocked(uploadFile).mockImplementation(async (file, _fileId, options) => {
      uploadCount++;
      // Abort after first file starts
      if (uploadCount === 1) {
        abortController.abort();
      }
      if (options.abortSignal?.aborted) {
        throw new Error('Upload cancelled');
      }
      return { data: { documentId: `doc-${uploadCount}`, filename: file.name, storagePath: `/uploads/${file.name}`, status: 'uploaded' as const } };
    });

    const result = await createMatterAndUpload(
      'Test Matter',
      [mockFile1, mockFile2],
      { onFileError },
      abortController.signal
    );

    // First file should have tried (and possibly failed), second file should be cancelled
    expect(result.failedUploads.size).toBeGreaterThan(0);
  });
});

describe('uploadToExistingMatter', () => {
  const mockFile = new File(['content'], 'document.pdf', { type: 'application/pdf' });

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(uploadFile).mockResolvedValue({
      data: {
        documentId: 'doc-123',
        filename: 'document.pdf',
        storagePath: '/uploads/document.pdf',
        status: 'uploaded' as const,
      },
    });
  });

  it('uploads files to the specified matter', async () => {
    await uploadToExistingMatter('existing-matter-id', [mockFile], {});

    expect(uploadFile).toHaveBeenCalledWith(
      mockFile,
      expect.any(String),
      expect.objectContaining({ matterId: 'existing-matter-id' })
    );
  });

  it('returns upload results without matterId', async () => {
    const result = await uploadToExistingMatter('existing-matter-id', [mockFile], {});

    expect(result.uploadedDocuments.size).toBe(1);
    expect(result.uploadedDocuments.get('document.pdf')).toBe('doc-123');
    expect(result.allSucceeded).toBe(true);
    // Should not have matterId in result
    expect((result as Record<string, unknown>).matterId).toBeUndefined();
  });

  it('handles upload failures', async () => {
    vi.mocked(uploadFile).mockRejectedValue(new Error('Network error'));

    const result = await uploadToExistingMatter('existing-matter-id', [mockFile], {});

    expect(result.failedUploads.size).toBe(1);
    expect(result.failedUploads.get('document.pdf')).toBe('Network error');
    expect(result.allSucceeded).toBe(false);
  });
});
