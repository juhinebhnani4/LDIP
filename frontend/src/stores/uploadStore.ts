/**
 * Upload Store
 *
 * Zustand store for managing file upload queue and progress.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const uploadQueue = useUploadStore((state) => state.uploadQueue);
 *   const addFiles = useUploadStore((state) => state.addFiles);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { uploadQueue, addFiles } = useUploadStore();
 */

import { create } from 'zustand';
import type { UploadFile, UploadStatus } from '@/types/document';

/** Generate unique ID for uploaded file */
function generateFileId(): string {
  return `upload_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

interface UploadState {
  /** Files currently in upload queue */
  uploadQueue: UploadFile[];

  /** Currently uploading (for UI state) */
  isUploading: boolean;
}

interface UploadActions {
  /** Add files to upload queue */
  addFiles: (files: File[]) => void;

  /** Remove file from queue by ID */
  removeFile: (id: string) => void;

  /** Update progress for a file by ID */
  updateProgress: (id: string, progress: number) => void;

  /** Update status for a file by ID */
  updateStatus: (id: string, status: UploadStatus, error?: string) => void;

  /** Update file after compression */
  updateFileAfterCompression: (
    id: string,
    compressedFile: File,
    originalSize: number,
    compressionInfo: string
  ) => void;

  /** Clear completed uploads from queue */
  clearCompleted: () => void;

  /** Clear all files from queue */
  clearAll: () => void;

  /** Set uploading state */
  setUploading: (isUploading: boolean) => void;
}

type UploadStore = UploadState & UploadActions;

export const useUploadStore = create<UploadStore>()((set) => ({
  // Initial state
  uploadQueue: [],
  isUploading: false,

  // Actions
  addFiles: (files: File[]) => {
    const newFiles: UploadFile[] = files.map((file) => ({
      id: generateFileId(),
      file,
      progress: 0,
      status: 'pending',
    }));

    set((state) => ({
      uploadQueue: [...state.uploadQueue, ...newFiles],
    }));
  },

  removeFile: (id: string) => {
    set((state) => ({
      uploadQueue: state.uploadQueue.filter((f) => f.id !== id),
    }));
  },

  updateProgress: (id: string, progress: number) => {
    set((state) => ({
      uploadQueue: state.uploadQueue.map((f) =>
        f.id === id ? { ...f, progress, status: 'uploading' as const } : f
      ),
    }));
  },

  updateStatus: (id: string, status: UploadStatus, error?: string) => {
    set((state) => ({
      uploadQueue: state.uploadQueue.map((f) =>
        f.id === id
          ? {
              ...f,
              status,
              error,
              progress: status === 'completed' ? 100 : f.progress,
            }
          : f
      ),
    }));
  },

  updateFileAfterCompression: (
    id: string,
    compressedFile: File,
    originalSize: number,
    compressionInfo: string
  ) => {
    set((state) => ({
      uploadQueue: state.uploadQueue.map((f) =>
        f.id === id
          ? {
              ...f,
              file: compressedFile,
              originalSize,
              wasCompressed: true,
              compressionInfo,
              status: 'pending' as const,
            }
          : f
      ),
    }));
  },

  clearCompleted: () => {
    set((state) => ({
      uploadQueue: state.uploadQueue.filter((f) => f.status !== 'completed'),
    }));
  },

  clearAll: () => {
    set({ uploadQueue: [] });
  },

  setUploading: (isUploading: boolean) => {
    set({ isUploading });
  },
}));
