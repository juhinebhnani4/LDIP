'use client';

import { X, FileIcon, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { useUploadStore } from '@/stores/uploadStore';
import { formatFileSize } from '@/lib/utils/upload-validation';
import type { UploadFile } from '@/types/document';

interface UploadProgressItemProps {
  file: UploadFile;
  onCancel: (id: string) => void;
}

function UploadProgressItem({ file, onCancel }: UploadProgressItemProps) {
  const { id, file: fileData, progress, status, error } = file;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border bg-background p-3"
      role="listitem"
      aria-label={`${fileData.name} - ${status}`}
    >
      {/* File icon */}
      <div className="flex-shrink-0">
        {status === 'completed' ? (
          <CheckCircle2 className="size-5 text-green-500" aria-hidden="true" />
        ) : status === 'error' ? (
          <AlertCircle className="size-5 text-destructive" aria-hidden="true" />
        ) : status === 'uploading' ? (
          <Loader2 className="size-5 animate-spin text-primary" aria-hidden="true" />
        ) : (
          <FileIcon className="size-5 text-muted-foreground" aria-hidden="true" />
        )}
      </div>

      {/* File info and progress */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-medium">{fileData.name}</p>
          <span className="flex-shrink-0 text-xs text-muted-foreground">
            {formatFileSize(fileData.size)}
          </span>
        </div>

        {status === 'error' ? (
          <p className="mt-1 text-xs text-destructive">{error}</p>
        ) : status === 'uploading' ? (
          <div className="mt-2">
            {/* Radix Progress component handles aria-valuenow/min/max internally */}
            <Progress
              value={progress}
              className="h-1.5"
              aria-label={`Upload progress: ${progress}%`}
            />
            <p className="mt-1 text-xs text-muted-foreground">{progress}%</p>
          </div>
        ) : status === 'completed' ? (
          <p className="mt-1 text-xs text-green-600">Uploaded successfully</p>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">Waiting...</p>
        )}
      </div>

      {/* Cancel button (only show for pending/uploading) */}
      {(status === 'pending' || status === 'uploading') && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => onCancel(id)}
          aria-label={`Cancel upload for ${fileData.name}`}
          className="flex-shrink-0"
        >
          <X className="size-4" />
        </Button>
      )}
    </div>
  );
}

interface UploadProgressListProps {
  /** Optional callback when user cancels a file upload */
  onCancelFile?: (id: string) => void;
}

/**
 * Upload Progress List
 *
 * Displays files in upload queue with progress indicators.
 * Uses Zustand store with selectors for state management.
 */
export function UploadProgressList({ onCancelFile }: UploadProgressListProps) {
  const uploadQueue = useUploadStore((state) => state.uploadQueue);
  const removeFile = useUploadStore((state) => state.removeFile);
  const clearCompleted = useUploadStore((state) => state.clearCompleted);

  const handleCancel = (id: string) => {
    removeFile(id);
    onCancelFile?.(id);
  };

  if (uploadQueue.length === 0) {
    return null;
  }

  const hasCompletedFiles = uploadQueue.some((f) => f.status === 'completed');

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">
          Uploads ({uploadQueue.length})
        </h3>
        {hasCompletedFiles && (
          <Button variant="ghost" size="sm" onClick={clearCompleted}>
            Clear completed
          </Button>
        )}
      </div>

      <div
        className="max-h-64 space-y-2 overflow-y-auto"
        role="list"
        aria-label="Upload queue"
      >
        {uploadQueue.map((file) => (
          <UploadProgressItem
            key={file.id}
            file={file}
            onCancel={handleCancel}
          />
        ))}
      </div>
    </div>
  );
}
