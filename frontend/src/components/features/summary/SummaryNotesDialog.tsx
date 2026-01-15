'use client';

/**
 * SummaryNotesDialog Component
 *
 * Modal dialog for adding notes to summary sections.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #1)
 */

import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import type { SummarySectionType } from '@/types/summary';

interface SummaryNotesDialogProps {
  /** Whether dialog is open */
  isOpen: boolean;
  /** Callback when dialog is closed */
  onClose: () => void;
  /** Callback when note is saved */
  onSave: (note: string) => Promise<void>;
  /** Section type for context */
  sectionType: SummarySectionType;
  /** Section ID */
  sectionId: string;
  /** Existing note text to edit */
  existingNote?: string;
}

export function SummaryNotesDialog({
  isOpen,
  onClose,
  onSave,
  existingNote = '',
}: SummaryNotesDialogProps) {
  const [note, setNote] = useState(existingNote);
  const [isSaving, setIsSaving] = useState(false);

  // Reset note when dialog opens/closes or existingNote changes
  useEffect(() => {
    setNote(existingNote);
  }, [existingNote, isOpen]);

  const handleSave = async () => {
    if (!note.trim()) return;

    setIsSaving(true);
    try {
      await onSave(note);
      onClose();
    } catch {
      // Error handling delegated to parent
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Note</DialogTitle>
          <DialogDescription>
            Add a note to this section for reference.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="note-textarea">Note</Label>
            <Textarea
              id="note-textarea"
              placeholder="Enter your note about this section..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="min-h-[120px]"
            />
          </div>
        </div>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || !note.trim()}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Note'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
