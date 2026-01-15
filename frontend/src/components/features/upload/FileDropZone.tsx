'use client';

import { useCallback, useState, useRef } from 'react';
import { Upload, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
  validateFiles,
  MAX_FILE_SIZE,
  MAX_FILES_PER_UPLOAD,
} from '@/lib/utils/upload-validation';
import type { ValidationError, ValidationWarning } from '@/types/document';

/**
 * FileDropZone Component
 *
 * Drag-drop zone for file selection in Stage 1 of upload wizard.
 * Features animated icon on drag-over and validation error display.
 *
 * Note: ZIP file validation checks MIME type and extension only.
 * ZIP content inspection (verifying PDFs inside) is not implemented
 * in the MVP - the backend will handle ZIP extraction and content
 * validation during upload processing.
 */

interface FileDropZoneProps {
  /** Callback when valid files are selected */
  onFilesSelected: (files: File[]) => void;
  /** Optional className for styling */
  className?: string;
}

/** Validation display component */
function ValidationDisplay({
  errors,
  warnings,
}: {
  errors: ValidationError[];
  warnings: ValidationWarning[];
}) {
  if (errors.length === 0 && warnings.length === 0) return null;

  return (
    <div className="mt-4 space-y-2">
      {warnings.map((warning, index) => (
        <div
          key={`warning-${index}`}
          className="flex items-start gap-2 p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-800"
          role="alert"
        >
          <span className="text-sm">
            {warning.code === 'MAX_FILES_EXCEEDED' && (
              <>
                <strong>Maximum 100 files per upload</strong>
                <br />
                First {warning.acceptedCount} files accepted. {warning.rejectedCount} files
                were not added.
              </>
            )}
          </span>
        </div>
      ))}
      {errors.map((error, index) => (
        <div
          key={`error-${index}`}
          className="flex items-start gap-2 p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive"
          role="alert"
        >
          <span className="text-sm">
            {error.code === 'INVALID_TYPE' && (
              <>
                <strong>Can&apos;t upload &quot;{error.file.name}&quot;</strong>
                <br />
                LDIP supports PDF files only. Tip: Convert your file to PDF first.
              </>
            )}
            {error.code === 'FILE_TOO_LARGE' && (
              <>
                <strong>File too large</strong>
                <br />
                &quot;{error.file.name}&quot; exceeds the {MAX_FILE_SIZE / (1024 * 1024)}MB
                limit. Try compressing or splitting the file.
              </>
            )}
            {error.code === 'EMPTY_FILE' && (
              <>
                <strong>Empty file</strong>
                <br />
                &quot;{error.file.name}&quot; appears to be empty.
              </>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

export function FileDropZone({ onFilesSelected, className }: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<ValidationWarning[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;

      const files = Array.from(fileList);
      const result = validateFiles(files);

      setValidationErrors(result.errors);
      setValidationWarnings(result.warnings);

      // Get valid files and pass them up
      if (result.valid || result.warnings.length > 0) {
        const validFiles = files
          .slice(0, MAX_FILES_PER_UPLOAD)
          .filter(
            (file) =>
              !result.errors.some((err) => err.file.name === file.name && err.file.size === file.size)
          );
        if (validFiles.length > 0) {
          onFilesSelected(validFiles);
        }
      }
    },
    [onFilesSelected]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleBrowseClick();
    }
  };

  return (
    <div className={className}>
      <Card
        className={cn(
          'border-2 border-dashed transition-all duration-200 cursor-pointer',
          isDragOver
            ? 'border-primary bg-primary/5 scale-[1.02]'
            : 'border-muted-foreground/25 hover:border-muted-foreground/50'
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleBrowseClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="button"
        aria-label="Drop files here or click to browse"
      >
        <CardContent className="flex flex-col items-center justify-center py-16 px-8 text-center">
          {/* Animated icon container */}
          <div
            className={cn(
              'relative mb-6 transition-transform duration-200',
              isDragOver && 'animate-pulse scale-110'
            )}
          >
            <div className="rounded-full bg-primary/10 p-6">
              {isDragOver ? (
                <FolderOpen className="size-12 text-primary animate-bounce" />
              ) : (
                <Upload className="size-12 text-primary" />
              )}
            </div>
          </div>

          {/* Instructions */}
          <h3 className="text-lg font-semibold mb-2">
            {isDragOver ? 'Drop to upload' : 'Drag & drop your case files here'}
          </h3>
          <p className="text-muted-foreground mb-6">or</p>

          {/* Browse button */}
          <Button
            type="button"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              handleBrowseClick();
            }}
            className="mb-6"
          >
            Browse Files
          </Button>

          {/* File format info */}
          <div className="space-y-1 text-sm text-muted-foreground">
            <p>Supported: PDF, ZIP (containing PDFs)*</p>
            <p>Maximum: 500MB per file &bull; 100 files per matter</p>
            <p className="text-xs mt-2">*ZIP contents validated during processing</p>
          </div>
        </CardContent>
      </Card>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.zip,application/pdf,application/zip,application/x-zip-compressed"
        onChange={handleFileInputChange}
        className="hidden"
        aria-hidden="true"
      />

      {/* Validation errors and warnings */}
      <ValidationDisplay errors={validationErrors} warnings={validationWarnings} />
    </div>
  );
}
