'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, FileIcon, X } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useUploadStore } from '@/stores/uploadStore';
import {
  validateFiles,
  getValidFiles,
  MAX_FILES_PER_UPLOAD,
} from '@/lib/utils/upload-validation';
import { uploadFiles } from '@/lib/api/documents';
import { UploadProgressList } from './UploadProgress';
import type { DocumentType, UploadFile } from '@/types/document';

/** Duration to show invalid state before returning to default (ms) */
const INVALID_STATE_DISPLAY_MS = 2000;

export interface UploadDropzoneProps {
  /** Matter ID - REQUIRED for document isolation */
  matterId: string;

  /** Callback when uploads complete */
  onUploadComplete?: (uploadedFiles: UploadFile[]) => void;

  /** Optional max files override (default: 100) */
  maxFiles?: number;

  /** Optional document type (default: 'case_file') */
  documentType?: DocumentType;

  /** Additional CSS classes */
  className?: string;
}

type DropzoneState = 'default' | 'drag-over' | 'invalid' | 'uploading';

/**
 * Upload Dropzone Component
 *
 * Provides drag-and-drop and file picker for uploading documents.
 * Validates file types (PDF, ZIP only) and enforces limits.
 *
 * Features:
 * - Drag-and-drop with visual feedback
 * - Browse Files button for file picker
 * - File type validation (PDF, ZIP only)
 * - File size limit (500MB per file)
 * - File count limit (100 files per upload)
 * - Progress tracking via Zustand store
 * - Accessibility support (keyboard, screen readers)
 */
export function UploadDropzone({
  matterId,
  onUploadComplete,
  maxFiles = MAX_FILES_PER_UPLOAD,
  documentType = 'case_file',
  className,
}: UploadDropzoneProps) {
  const [dropzoneState, setDropzoneState] = useState<DropzoneState>('default');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);

  // Cleanup on unmount - abort any in-progress uploads
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // Abort any pending uploads when component unmounts
      abortControllerRef.current?.abort();
    };
  }, []);

  // Zustand store with selectors (CORRECT pattern)
  const addFiles = useUploadStore((state) => state.addFiles);
  const uploadQueue = useUploadStore((state) => state.uploadQueue);
  const isUploading = useUploadStore((state) => state.isUploading);

  /**
   * Process files from drop or file input
   */
  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const fileArray = Array.from(files);

      if (fileArray.length === 0) return;

      // Validate files
      const validation = validateFiles(fileArray);

      // Show warnings (file count exceeded)
      for (const warning of validation.warnings) {
        toast.warning(warning.message);
      }

      // Show errors (invalid types, sizes)
      for (const error of validation.errors) {
        toast.error(error.message);
      }

      // Get valid files only
      const validFiles = getValidFiles(fileArray);

      if (validFiles.length === 0) {
        setDropzoneState('invalid');
        setTimeout(() => {
          if (isMountedRef.current) {
            setDropzoneState('default');
          }
        }, INVALID_STATE_DISPLAY_MS);
        return;
      }

      // Add valid files to store
      addFiles(validFiles);

      // Get added file IDs from store
      const currentQueue = useUploadStore.getState().uploadQueue;
      const pendingFiles = currentQueue.filter((f) => f.status === 'pending');

      // Create new AbortController for this upload batch
      abortControllerRef.current = new AbortController();

      // Start upload
      if (isMountedRef.current) {
        setDropzoneState('uploading');
      }

      try {
        await uploadFiles(
          pendingFiles.map((f) => ({ id: f.id, file: f.file })),
          matterId,
          documentType
        );

        // Only update state if still mounted
        if (!isMountedRef.current) return;

        // Get final state and notify
        const finalQueue = useUploadStore.getState().uploadQueue;
        const completedFiles = finalQueue.filter(
          (f) => f.status === 'completed'
        );

        if (completedFiles.length > 0) {
          toast.success(`Uploaded ${completedFiles.length} files successfully`);
          onUploadComplete?.(completedFiles);
        }
      } catch (error) {
        // Only show error if still mounted and not aborted
        if (!isMountedRef.current) return;

        const message =
          error instanceof Error ? error.message : 'Upload failed';
        // Don't show error toast for aborted uploads
        if (message !== 'Upload cancelled') {
          toast.error(message);
        }
      } finally {
        if (isMountedRef.current) {
          setDropzoneState('default');
        }
        abortControllerRef.current = null;
      }
    },
    [matterId, documentType, addFiles, onUploadComplete]
  );

  /**
   * Handle drag enter event
   */
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDropzoneState('drag-over');
  }, []);

  /**
   * Handle drag leave event
   */
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Only set default if we're leaving the dropzone entirely
    const relatedTarget = e.relatedTarget as Node | null;
    if (!e.currentTarget.contains(relatedTarget)) {
      setDropzoneState('default');
    }
  }, []);

  /**
   * Handle drag over event (required for drop to work)
   */
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  /**
   * Handle drop event
   */
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const { files } = e.dataTransfer;
      handleFiles(files);
    },
    [handleFiles]
  );

  /**
   * Handle file input change
   */
  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const { files } = e.target;
      if (files) {
        handleFiles(files);
      }
      // Reset input so same file can be selected again
      e.target.value = '';
    },
    [handleFiles]
  );

  /**
   * Open file picker
   */
  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Handle keyboard activation
   */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleBrowseClick();
      }
    },
    [handleBrowseClick]
  );

  // Determine visual state classes
  const stateClasses = {
    default: 'border-dashed border-muted-foreground/25 hover:border-muted-foreground/50',
    'drag-over': 'border-dashed border-primary bg-primary/5',
    invalid: 'border-dashed border-destructive bg-destructive/5',
    uploading: 'border-solid border-primary',
  };

  const hasFiles = uploadQueue.length > 0;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Dropzone */}
      <Card
        className={cn(
          'relative cursor-pointer transition-colors',
          stateClasses[dropzoneState]
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleBrowseClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="button"
        aria-label="Drop files here or click to browse"
        aria-describedby="dropzone-description"
      >
        <CardContent className="flex flex-col items-center justify-center py-12">
          {/* Icon */}
          <div
            className={cn(
              'mb-4 rounded-full p-3',
              dropzoneState === 'drag-over' && 'animate-bounce bg-primary/10',
              dropzoneState === 'invalid' && 'bg-destructive/10',
              dropzoneState === 'uploading' && 'animate-pulse bg-primary/10',
              dropzoneState === 'default' && 'bg-muted'
            )}
          >
            {dropzoneState === 'invalid' ? (
              <X className="size-6 text-destructive" aria-hidden="true" />
            ) : (
              <Upload
                className={cn(
                  'size-6',
                  dropzoneState === 'drag-over' || dropzoneState === 'uploading'
                    ? 'text-primary'
                    : 'text-muted-foreground'
                )}
                aria-hidden="true"
              />
            )}
          </div>

          {/* Text */}
          <p className="mb-1 text-sm font-medium">
            {dropzoneState === 'drag-over'
              ? 'Drop files here'
              : dropzoneState === 'invalid'
                ? 'Invalid files'
                : dropzoneState === 'uploading'
                  ? 'Uploading...'
                  : 'Drag & drop files here'}
          </p>

          <p
            id="dropzone-description"
            className="mb-4 text-xs text-muted-foreground"
          >
            {dropzoneState === 'invalid'
              ? 'Only PDF and ZIP files are supported'
              : `PDF and ZIP files only (max ${maxFiles} files)`}
          </p>

          {/* Browse button */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              handleBrowseClick();
            }}
            disabled={isUploading}
          >
            <FileIcon className="mr-2 size-4" aria-hidden="true" />
            Browse Files
          </Button>

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.zip,application/pdf,application/zip,application/x-zip-compressed"
            multiple
            onChange={handleFileInputChange}
            className="hidden"
            aria-hidden="true"
          />
        </CardContent>
      </Card>

      {/* Progress list */}
      {hasFiles && <UploadProgressList />}
    </div>
  );
}
