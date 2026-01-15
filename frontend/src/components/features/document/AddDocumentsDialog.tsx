'use client';

/**
 * Add Documents Dialog Component
 *
 * Modal dialog for adding documents to an existing matter.
 * Integrates the existing UploadDropzone component with
 * a message about background processing.
 *
 * Story 10D.3: Documents Tab File List
 * Task 4: Create AddDocumentsDialog for in-matter uploads (AC #3)
 */

import { useCallback } from 'react';
import { Info } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { UploadDropzone } from './UploadDropzone';
import type { UploadFile } from '@/types/document';

interface AddDocumentsDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Matter ID for document isolation */
  matterId: string;
  /** Callback when upload completes */
  onComplete?: () => void;
}

/**
 * Add Documents Dialog component.
 *
 * Provides a modal interface for adding documents to an existing matter.
 * Uses the existing UploadDropzone component and shows a message about
 * background processing per AC #3.
 *
 * @example
 * ```tsx
 * <AddDocumentsDialog
 *   open={dialogOpen}
 *   onOpenChange={setDialogOpen}
 *   matterId="matter-123"
 *   onComplete={() => refresh()}
 * />
 * ```
 */
export function AddDocumentsDialog({
  open,
  onOpenChange,
  matterId,
  onComplete,
}: AddDocumentsDialogProps) {
  // Handle upload complete - close dialog and notify parent
  const handleUploadComplete = useCallback(
    (uploadedFiles: UploadFile[]) => {
      if (uploadedFiles.length > 0) {
        onComplete?.();
      }
    },
    [onComplete]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Documents</DialogTitle>
          <DialogDescription>
            Upload additional documents to this matter
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Upload dropzone */}
          <UploadDropzone
            matterId={matterId}
            onUploadComplete={handleUploadComplete}
          />

          {/* Background processing message - AC #3 */}
          <Alert className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-900">
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <AlertDescription className="text-blue-700 dark:text-blue-300">
              You can continue working while this processes
            </AlertDescription>
          </Alert>
        </div>
      </DialogContent>
    </Dialog>
  );
}
