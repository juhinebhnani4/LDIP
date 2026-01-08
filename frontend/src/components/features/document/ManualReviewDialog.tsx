'use client';

import { useState } from 'react';
import type { PageConfidence } from '@/types/document';
import { requestManualReview } from '@/lib/api/documents';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { OCR_PAGE_REVIEW_THRESHOLD } from '@/lib/constants/ocr';

interface ManualReviewDialogProps {
  documentId: string;
  pageConfidences: PageConfidence[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export function ManualReviewDialog({
  documentId,
  pageConfidences,
  open,
  onOpenChange,
  onSuccess,
}: ManualReviewDialogProps) {
  const [selectedPages, setSelectedPages] = useState<Set<number>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Pages below review threshold are auto-highlighted
  const lowConfidencePages = pageConfidences
    .filter((p) => p.confidence < OCR_PAGE_REVIEW_THRESHOLD)
    .map((p) => p.pageNumber);

  const handleTogglePage = (pageNumber: number) => {
    setSelectedPages((prev) => {
      const next = new Set(prev);
      if (next.has(pageNumber)) {
        next.delete(pageNumber);
      } else {
        next.add(pageNumber);
      }
      return next;
    });
  };

  const handleSelectLowConfidence = () => {
    setSelectedPages(new Set(lowConfidencePages));
  };

  const handleSelectAll = () => {
    setSelectedPages(new Set(pageConfidences.map((p) => p.pageNumber)));
  };

  const handleClearAll = () => {
    setSelectedPages(new Set());
  };

  const handleSubmit = async () => {
    if (selectedPages.size === 0) {
      toast.error('Please select at least one page');
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await requestManualReview(
        documentId,
        Array.from(selectedPages).sort((a, b) => a - b)
      );

      toast.success(
        `${result.pagesAdded} page${result.pagesAdded !== 1 ? 's' : ''} added to review queue`
      );
      setSelectedPages(new Set());
      onOpenChange(false);
      onSuccess?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to request manual review';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Request Manual Review</DialogTitle>
          <DialogDescription>
            Select pages that need manual review. Pages with poor OCR quality (&lt;60%)
            are highlighted in red.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Quick actions */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleSelectLowConfidence}
              disabled={lowConfidencePages.length === 0}
            >
              Select Low Quality ({lowConfidencePages.length})
            </Button>
            <Button variant="outline" size="sm" onClick={handleSelectAll}>
              Select All
            </Button>
            <Button variant="outline" size="sm" onClick={handleClearAll}>
              Clear All
            </Button>
          </div>

          {/* Page grid */}
          <div className="grid grid-cols-6 gap-2 max-h-64 overflow-y-auto p-2 border rounded">
            {pageConfidences.map((page) => {
              const isLowConfidence = page.confidence < OCR_PAGE_REVIEW_THRESHOLD;
              const isSelected = selectedPages.has(page.pageNumber);
              const percentage = Math.round(page.confidence * 100);

              return (
                <label
                  key={page.pageNumber}
                  className={cn(
                    'flex flex-col items-center p-2 rounded border cursor-pointer transition-colors',
                    isSelected
                      ? 'bg-primary/10 border-primary'
                      : isLowConfidence
                        ? 'bg-red-50 border-red-200 hover:bg-red-100'
                        : 'hover:bg-muted'
                  )}
                >
                  <div className="flex items-center gap-1 mb-1">
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => handleTogglePage(page.pageNumber)}
                    />
                  </div>
                  <span className="text-sm font-medium">Page {page.pageNumber}</span>
                  <span
                    className={cn(
                      'text-xs',
                      isLowConfidence ? 'text-red-600' : 'text-muted-foreground'
                    )}
                  >
                    {percentage}%
                  </span>
                </label>
              );
            })}
          </div>

          <p className="text-sm text-muted-foreground">
            {selectedPages.size} page{selectedPages.size !== 1 ? 's' : ''} selected
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={selectedPages.size === 0 || isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : 'Request Review'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
