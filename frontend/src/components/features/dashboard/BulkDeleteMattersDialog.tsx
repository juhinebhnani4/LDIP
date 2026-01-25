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

/** Max number of matter titles to show in dialog */
const MAX_TITLES_SHOWN = 5;

export interface BulkDeleteMattersDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Titles of matters to be deleted */
  matterTitles: string[];
  /** Callback to perform deletion */
  onDelete: () => Promise<void>;
}

/**
 * Confirmation dialog for bulk deleting matters.
 *
 * Shows list of matter titles (truncated if many) and 30-day retention info.
 * Only matter owners can delete matters.
 */
export function BulkDeleteMattersDialog({
  open,
  onOpenChange,
  matterTitles,
  onDelete,
}: BulkDeleteMattersDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const count = matterTitles.length;

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

  // Show first few titles, then "and X more"
  const titlesToShow = matterTitles.slice(0, MAX_TITLES_SHOWN);
  const remainingCount = count - titlesToShow.length;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Delete {count} Matter{count !== 1 ? 's' : ''}
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                Are you sure you want to delete {count === 1 ? 'this matter' : `these ${count} matters`}?
              </p>

              {/* List of matter titles */}
              <div className="rounded-md bg-muted p-3 text-sm max-h-40 overflow-y-auto">
                <ul className="space-y-1">
                  {titlesToShow.map((title, index) => (
                    <li key={index} className="text-foreground">
                      • {title}
                    </li>
                  ))}
                  {remainingCount > 0 && (
                    <li className="text-muted-foreground italic">
                      ... and {remainingCount} more matter{remainingCount !== 1 ? 's' : ''}
                    </li>
                  )}
                </ul>
              </div>

              <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm">
                <p className="text-destructive">
                  This will delete all documents, citations, and timeline events associated with {count === 1 ? 'this matter' : 'these matters'}.
                </p>
              </div>

              <p className="text-muted-foreground">
                {count === 1 ? 'The matter' : 'The matters'} will be retained for 30 days before permanent deletion.
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
              `Delete ${count} Matter${count !== 1 ? 's' : ''}`
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
