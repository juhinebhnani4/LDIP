/**
 * DeleteEventConfirmation Component
 *
 * Alert dialog for confirming deletion of manual timeline events.
 * Only manual events can be deleted; auto-extracted events can only be reclassified.
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

'use client';

import { useState, useCallback } from 'react';
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
import { toast } from 'sonner';
import type { TimelineEvent } from '@/types/timeline';

/**
 * DeleteEventConfirmation props
 */
interface DeleteEventConfirmationProps {
  /** Whether dialog is open */
  open: boolean;
  /** Callback to change open state */
  onOpenChange: (open: boolean) => void;
  /** Event to delete */
  event: TimelineEvent | null;
  /** Callback when event is deleted */
  onConfirm: (eventId: string) => Promise<void>;
}

/**
 * DeleteEventConfirmation component
 */
export function DeleteEventConfirmation({
  open,
  onOpenChange,
  event,
  onConfirm,
}: DeleteEventConfirmationProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleConfirm = useCallback(async () => {
    if (!event) return;

    setIsDeleting(true);
    try {
      await onConfirm(event.id);
      toast.success('Event deleted successfully');
      onOpenChange(false);
    } catch {
      toast.error('Failed to delete event. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  }, [event, onConfirm, onOpenChange]);

  // Don't render if no event or event is not manual
  if (!event || !event.isManual) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Delete Event
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>Are you sure you want to delete this event?</p>
              <div className="rounded-md bg-muted p-3 text-sm">
                <p className="font-medium">{event.description}</p>
                <p className="text-muted-foreground mt-1">
                  {new Date(event.eventDate).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </p>
              </div>
              <p className="text-destructive font-medium">
                This action cannot be undone.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting...
              </>
            ) : (
              'Delete Event'
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default DeleteEventConfirmation;
