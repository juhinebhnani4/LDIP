'use client';

import { useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

export interface DeleteMatterDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  matterTitle: string;
  onDelete: () => Promise<void>;
}

/**
 * Confirmation dialog for deleting a matter.
 *
 * Shows matter title and 30-day retention info.
 * Only matter owners can delete matters.
 */
export function DeleteMatterDialog({
  open,
  onOpenChange,
  matterTitle,
  onDelete,
}: DeleteMatterDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete();
      onOpenChange(false);
    } catch {
      // Error is handled by parent via toast
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Delete Matter
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                Are you sure you want to delete <span className="font-medium text-foreground">&quot;{matterTitle}&quot;</span>?
              </p>
              <div className="rounded-md bg-muted p-3 text-sm">
                <p className="text-muted-foreground">
                  This will delete all documents, citations, and timeline events associated with this matter.
                </p>
              </div>
              <p className="text-muted-foreground">
                The matter will be retained for 30 days before permanent deletion.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={isDeleting}
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting...
              </>
            ) : (
              'Delete Matter'
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
