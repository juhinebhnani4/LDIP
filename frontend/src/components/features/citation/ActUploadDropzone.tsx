'use client';

/**
 * ActUploadDropzone Component
 *
 * Specialized dropzone for uploading Act documents.
 * Sets documents as reference material (is_reference_material=true).
 * Single file selection only (Acts are individual documents).
 *
 * Story 3-2: Act Discovery Report UI
 *
 * @example
 * ```tsx
 * <ActUploadDropzone
 *   matterId="matter-123"
 *   actName="Negotiable Instruments Act, 1881"
 *   onUploadComplete={(documentId) => console.log('Uploaded:', documentId)}
 * />
 * ```
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, FileText, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { uploadFile } from '@/lib/api/documents';
import { MAX_ACT_FILE_SIZE } from '@/lib/utils/upload-validation';

/** Generate a unique upload ID for tracking */
function generateUploadId(): string {
  return `act-upload-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export interface ActUploadDropzoneProps {
  /** Matter ID for document isolation */
  matterId: string;
  /** Name of the Act being uploaded */
  actName: string;
  /** Callback when upload completes successfully */
  onUploadComplete: (documentId: string) => void;
  /** Callback when user cancels the upload flow */
  onCancel?: () => void;
  /** Additional CSS classes */
  className?: string;
}

type DropzoneState = 'default' | 'drag-over' | 'uploading' | 'success' | 'error';

/**
 * ActUploadDropzone provides a specialized upload interface for Act documents.
 *
 * Key differences from regular UploadDropzone:
 * - Single file only (no multiple selection)
 * - Document type set to 'act' (is_reference_material=true)
 * - Smaller file size limit (100MB vs 500MB)
 * - Displays the Act name being uploaded
 */
export function ActUploadDropzone({
  matterId,
  actName,
  onUploadComplete,
  onCancel,
  className,
}: ActUploadDropzoneProps) {
  const [dropzoneState, setDropzoneState] = useState<DropzoneState>('default');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isMountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  /**
   * Validate that the file is a valid PDF
   */
  const validateFile = useCallback((file: File): string | null => {
    // Check file type
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      return 'Only PDF files are supported for Acts';
    }

    // Check file size
    if (file.size > MAX_ACT_FILE_SIZE) {
      return `File exceeds 100MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB)`;
    }

    return null;
  }, []);

  /**
   * Handle file upload
   */
  const handleFile = useCallback(
    async (file: File) => {
      // Validate the file
      const validationError = validateFile(file);
      if (validationError) {
        toast.error(validationError);
        setDropzoneState('error');
        setTimeout(() => {
          if (isMountedRef.current) {
            setDropzoneState('default');
          }
        }, 2000);
        return;
      }

      setDropzoneState('uploading');

      try {
        // Generate a unique upload ID for this Act upload
        // Note: We don't use the global upload queue for Act uploads since they're
        // single-file operations managed entirely within this component
        const uploadId = generateUploadId();

        // Upload as 'act' document type (sets is_reference_material=true)
        const response = await uploadFile(file, uploadId, {
          matterId,
          documentType: 'act',
        });

        // Get documentId from the upload response
        const documentId = response.data.documentId;

        if (!documentId) {
          throw new Error('No document ID returned from upload');
        }

        if (isMountedRef.current) {
          setDropzoneState('success');
          toast.success(`${actName} uploaded successfully`);
          onUploadComplete(documentId);
        }
      } catch (error) {
        if (isMountedRef.current) {
          const message = error instanceof Error ? error.message : 'Upload failed';
          toast.error(message);
          setDropzoneState('error');
          setTimeout(() => {
            if (isMountedRef.current) {
              setDropzoneState('default');
            }
          }, 2000);
        }
      }
    },
    [matterId, actName, validateFile, onUploadComplete]
  );

  /**
   * Handle drag events
   */
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (dropzoneState !== 'uploading' && dropzoneState !== 'success') {
      setDropzoneState('drag-over');
    }
  }, [dropzoneState]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const relatedTarget = e.relatedTarget as Node | null;
    if (!e.currentTarget.contains(relatedTarget)) {
      if (dropzoneState === 'drag-over') {
        setDropzoneState('default');
      }
    }
  }, [dropzoneState]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (dropzoneState === 'uploading' || dropzoneState === 'success') {
        return;
      }

      const { files } = e.dataTransfer;
      const firstFile = files[0];
      if (firstFile) {
        // Only take the first file (single file upload)
        handleFile(firstFile);
      }
    },
    [dropzoneState, handleFile]
  );

  /**
   * Handle file input change
   */
  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const { files } = e.target;
      const firstFile = files?.[0];
      if (firstFile) {
        handleFile(firstFile);
      }
      e.target.value = '';
    },
    [handleFile]
  );

  /**
   * Open file picker
   */
  const handleBrowseClick = useCallback(() => {
    if (dropzoneState !== 'uploading' && dropzoneState !== 'success') {
      fileInputRef.current?.click();
    }
  }, [dropzoneState]);

  const isInteractive = dropzoneState !== 'uploading' && dropzoneState !== 'success';

  return (
    <div className={cn('space-y-4', className)}>
      {/* Act name header */}
      <div className="text-center">
        <p className="text-sm font-medium">Uploading Act Document</p>
        <p className="text-xs text-muted-foreground mt-1 truncate" title={actName}>
          {actName}
        </p>
      </div>

      {/* Dropzone */}
      <Card
        className={cn(
          'relative transition-colors',
          dropzoneState === 'default' && 'border-dashed border-muted-foreground/25 hover:border-muted-foreground/50 cursor-pointer',
          dropzoneState === 'drag-over' && 'border-dashed border-primary bg-primary/5 cursor-pointer',
          dropzoneState === 'uploading' && 'border-solid border-primary',
          dropzoneState === 'success' && 'border-solid border-green-500 bg-green-50/50 dark:bg-green-950/20',
          dropzoneState === 'error' && 'border-dashed border-destructive bg-destructive/5'
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={isInteractive ? handleBrowseClick : undefined}
        tabIndex={isInteractive ? 0 : -1}
        role={isInteractive ? 'button' : undefined}
        aria-label={isInteractive ? `Drop PDF file here or click to browse for ${actName}` : undefined}
      >
        <CardContent className="flex flex-col items-center justify-center py-8">
          {/* Icon */}
          <div
            className={cn(
              'mb-3 rounded-full p-3',
              dropzoneState === 'default' && 'bg-muted',
              dropzoneState === 'drag-over' && 'animate-bounce bg-primary/10',
              dropzoneState === 'uploading' && 'animate-pulse bg-primary/10',
              dropzoneState === 'success' && 'bg-green-100 dark:bg-green-900/30',
              dropzoneState === 'error' && 'bg-destructive/10'
            )}
          >
            {dropzoneState === 'uploading' && (
              <Loader2 className="size-5 text-primary animate-spin" aria-hidden="true" />
            )}
            {dropzoneState === 'success' && (
              <CheckCircle2 className="size-5 text-green-600 dark:text-green-400" aria-hidden="true" />
            )}
            {dropzoneState === 'error' && (
              <AlertCircle className="size-5 text-destructive" aria-hidden="true" />
            )}
            {(dropzoneState === 'default' || dropzoneState === 'drag-over') && (
              <FileText
                className={cn(
                  'size-5',
                  dropzoneState === 'drag-over' ? 'text-primary' : 'text-muted-foreground'
                )}
                aria-hidden="true"
              />
            )}
          </div>

          {/* Text */}
          <p className="mb-1 text-sm font-medium">
            {dropzoneState === 'drag-over' && 'Drop PDF here'}
            {dropzoneState === 'uploading' && 'Uploading...'}
            {dropzoneState === 'success' && 'Upload complete!'}
            {dropzoneState === 'error' && 'Upload failed'}
            {dropzoneState === 'default' && 'Drop PDF here'}
          </p>

          <p className="mb-3 text-xs text-muted-foreground">
            {dropzoneState === 'success'
              ? 'The Act is now available for verification'
              : 'PDF files only (max 100MB)'}
          </p>

          {/* Browse button */}
          {isInteractive && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                handleBrowseClick();
              }}
            >
              <Upload className="mr-2 size-4" aria-hidden="true" />
              Browse Files
            </Button>
          )}

          {/* Hidden file input - single file only */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileInputChange}
            className="hidden"
            aria-hidden="true"
          />
        </CardContent>
      </Card>

      {/* Cancel button */}
      {onCancel && dropzoneState !== 'success' && (
        <div className="flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            disabled={dropzoneState === 'uploading'}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
