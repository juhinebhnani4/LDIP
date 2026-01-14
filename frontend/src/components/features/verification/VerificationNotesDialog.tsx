'use client';

/**
 * Verification Notes Dialog Component
 *
 * Modal dialog for entering notes when rejecting or flagging verifications.
 *
 * Story 8-5: Implement Verification Queue UI (Task 4)
 * Implements AC #3: Notes required for rejection
 */

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Loader2 } from 'lucide-react';

interface VerificationNotesDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Type of action (reject or flag) */
  action: 'reject' | 'flag';
  /** Number of items being actioned (for bulk) */
  itemCount: number;
  /** Whether the action is in progress */
  isLoading?: boolean;
  /** Callback when notes are submitted */
  onSubmit: (notes: string) => void;
}

/**
 * Dialog for entering notes when rejecting or flagging verifications.
 *
 * Notes are required for both reject and flag actions.
 *
 * @example
 * ```tsx
 * <VerificationNotesDialog
 *   open={dialogOpen}
 *   onOpenChange={setDialogOpen}
 *   action="reject"
 *   itemCount={1}
 *   onSubmit={handleReject}
 * />
 * ```
 */
export function VerificationNotesDialog({
  open,
  onOpenChange,
  action,
  itemCount,
  isLoading = false,
  onSubmit,
}: VerificationNotesDialogProps) {
  const [notes, setNotes] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (notes.trim()) {
      onSubmit(notes.trim());
      setNotes('');
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setNotes('');
      onOpenChange(false);
    }
  };

  const title = action === 'reject' ? 'Reject Verification' : 'Flag for Review';
  const description =
    action === 'reject'
      ? itemCount > 1
        ? `Please provide a reason for rejecting ${itemCount} verifications. This is required for audit trail.`
        : 'Please provide a reason for rejection. This is required for audit trail.'
      : itemCount > 1
        ? `Please explain why ${itemCount} verifications need further review.`
        : 'Please explain why this verification needs further review.';

  const placeholder =
    action === 'reject'
      ? 'e.g., Finding is incorrect - source document misread...'
      : 'e.g., Need senior attorney review - complex legal point...';

  const submitLabel = action === 'reject' ? 'Reject' : 'Flag';

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="notes">Notes (required)</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNotes(e.target.value)}
                placeholder={placeholder}
                required
                minLength={1}
                maxLength={2000}
                disabled={isLoading}
                autoFocus
                rows={4}
                className="resize-none"
              />
              <p className="text-xs text-muted-foreground">
                {notes.length}/2000 characters
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant={action === 'reject' ? 'destructive' : 'outline'}
              disabled={!notes.trim() || isLoading}
            >
              {isLoading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
