'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { DocumentListItem } from '@/types/document';

export interface RenameDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  document: DocumentListItem;
  onRename: (newFilename: string) => Promise<void>;
}

/**
 * Dialog for renaming a document.
 *
 * Validates filename:
 * - 1-255 characters
 * - No special characters: < > : " / \ | ? *
 */
export function RenameDocumentDialog({
  open,
  onOpenChange,
  document,
  onRename,
}: RenameDocumentDialogProps) {
  const [filename, setFilename] = useState(document.filename);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when dialog opens with new document
  useEffect(() => {
    if (open) {
      setFilename(document.filename);
      setError(null);
    }
  }, [open, document.filename]);

  const validateFilename = (name: string): string | null => {
    const trimmed = name.trim();
    if (trimmed.length < 1) {
      return 'Filename is required';
    }
    if (trimmed.length > 255) {
      return 'Filename must be 255 characters or less';
    }
    if (/[<>:"/\\|?*]/.test(trimmed)) {
      return 'Filename contains invalid characters (< > : " / \\ | ? *)';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedFilename = filename.trim();
    const validationError = validateFilename(trimmedFilename);
    if (validationError) {
      setError(validationError);
      return;
    }

    // Don't submit if filename hasn't changed
    if (trimmedFilename === document.filename) {
      onOpenChange(false);
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onRename(trimmedFilename);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rename document');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Rename Document</DialogTitle>
            <DialogDescription>
              Enter a new name for this document.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="filename">Filename</Label>
              <Input
                id="filename"
                value={filename}
                onChange={(e) => {
                  setFilename(e.target.value);
                  setError(null);
                }}
                placeholder="Enter new filename"
                aria-label="New filename"
                aria-invalid={error ? 'true' : 'false'}
                aria-describedby={error ? 'filename-error' : undefined}
                disabled={isSubmitting}
                autoFocus
              />
              {error && (
                <p id="filename-error" className="text-sm text-destructive">
                  {error}
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Renaming...' : 'Rename'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
