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

import { useCallback, useState } from 'react';
import { Info } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { UploadDropzone } from './UploadDropzone';
import type { DocumentType, UploadFile } from '@/types/document';

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
  const [documentType, setDocumentType] = useState<DocumentType>('case_file');

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
      <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Documents</DialogTitle>
          <DialogDescription>
            Upload additional documents to this matter
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Document type selector */}
          <div className="space-y-2">
            <Label htmlFor="add-doc-type">Document Type</Label>
            <Select
              value={documentType}
              onValueChange={(value: string) => setDocumentType(value as DocumentType)}
            >
              <SelectTrigger id="add-doc-type" className="w-full">
                <SelectValue placeholder="Select document type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="case_file">Case File</SelectItem>
                <SelectItem value="act">Act / Statute</SelectItem>
                <SelectItem value="annexure">Annexure</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
            {documentType === 'act' && (
              <p className="text-xs text-muted-foreground">
                Acts are stored in the shared library and linked to this matter.
              </p>
            )}
          </div>

          {/* Upload dropzone */}
          <UploadDropzone
            matterId={matterId}
            documentType={documentType}
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
