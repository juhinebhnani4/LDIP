'use client';

import { useRef, useMemo, useState } from 'react';
import { File, X, Plus, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatFileSize, MAX_FILES_PER_UPLOAD, validateFiles } from '@/lib/utils/upload-validation';
import { cn } from '@/lib/utils';

/**
 * FileReviewList Component
 *
 * Displays selected files in Stage 2 with remove and add more options.
 * Shows total count and size summary.
 */

interface FileReviewListProps {
  /** Files to display */
  files: File[];
  /** Callback to remove a file by index */
  onRemoveFile: (index: number) => void;
  /** Callback to add more files */
  onAddFiles: (files: File[]) => void;
  /** Optional className */
  className?: string;
}

/** Generate a stable unique ID for a file based on its properties and add time */
function generateFileId(file: File, index: number, addedAt: number): string {
  // Combine file properties with a timestamp-based seed for uniqueness
  // This handles duplicate filenames with same size by using lastModified and index
  return `file-${file.name}-${file.size}-${file.lastModified}-${addedAt}-${index}`;
}

/** Single file item display */
function FileItem({
  file,
  onRemove,
}: {
  file: File;
  onRemove: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 py-2 px-3 rounded-md hover:bg-muted/50 transition-colors group">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <File className="size-5 text-muted-foreground flex-shrink-0" />
        <span className="truncate text-sm font-medium" title={file.name}>
          {file.name}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground whitespace-nowrap">
          {formatFileSize(file.size)}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
          onClick={onRemove}
          aria-label={`Remove ${file.name}`}
        >
          <X className="size-4" />
        </Button>
      </div>
    </li>
  );
}

export function FileReviewList({
  files,
  onRemoveFile,
  onAddFiles,
  className,
}: FileReviewListProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Use a stable timestamp for file ID generation to handle re-renders
  // Lazy initialization to avoid Date.now() call during render
  const [addedAt] = useState(() => Date.now());
  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  const canAddMore = files.length < MAX_FILES_PER_UPLOAD;

  // Generate stable file IDs that persist across re-renders
  const fileIds = useMemo(() => {
    return files.map((file, index) => generateFileId(file, index, addedAt));
  }, [files, addedAt]);

  const handleAddMoreClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = e.target.files;
    if (!newFiles || newFiles.length === 0) return;

    const fileArray = Array.from(newFiles);
    const result = validateFiles(fileArray);

    // Filter out invalid files
    const validFiles = fileArray.filter(
      (file) => !result.errors.some((err) => err.file.name === file.name && err.file.size === file.size)
    );

    // Respect max files limit
    const remainingSlots = MAX_FILES_PER_UPLOAD - files.length;
    const filesToAdd = validFiles.slice(0, remainingSlots);

    if (filesToAdd.length > 0) {
      onAddFiles(filesToAdd);
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center justify-between">
          <span>
            Files to Upload ({files.length} {files.length === 1 ? 'file' : 'files'} &bull;{' '}
            {formatFileSize(totalSize)})
          </span>
          {files.length >= MAX_FILES_PER_UPLOAD && (
            <span className="flex items-center gap-1 text-sm text-amber-600 font-normal">
              <AlertCircle className="size-4" />
              Maximum files reached
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {/* File list */}
        <ul
          className="max-h-[300px] overflow-y-auto divide-y divide-border -mx-3"
          role="list"
          aria-label="Selected files"
        >
          {files.map((file, index) => {
            const fileId = fileIds[index] ?? `fallback-${index}`;
            return (
              <FileItem
                key={fileId}
                file={file}
                onRemove={() => onRemoveFile(index)}
              />
            );
          })}
        </ul>

        {/* Add more files button */}
        {canAddMore && (
          <Button
            variant="ghost"
            className="mt-4 w-full"
            onClick={handleAddMoreClick}
          >
            <Plus className="size-4 mr-2" />
            Add More Files
          </Button>
        )}

        {/* Hidden file input for adding more files */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.zip,application/pdf,application/zip,application/x-zip-compressed"
          onChange={handleFileInputChange}
          className="hidden"
          aria-hidden="true"
        />
      </CardContent>
    </Card>
  );
}
