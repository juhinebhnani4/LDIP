'use client';

/**
 * Documents Header Component
 *
 * Header section for the Documents tab showing:
 * - Total document count
 * - Document type breakdown
 * - Processing banner with progress
 * - Add Files button
 *
 * Story 10D.3: Documents Tab File List
 * Task 2: Create DocumentsHeader with statistics and processing banner
 */

import { FileText, FolderOpen, Gavel, Paperclip, Plus, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import type { DocumentType } from '@/types/document';
import { CeleryStatusIndicator } from '@/components/features/system/CeleryStatusIndicator';

interface DocumentsHeaderProps {
  /** Total document count */
  totalCount: number;
  /** Number of documents currently processing */
  processingCount: number;
  /** Percentage of documents processing */
  processingPercent: number;
  /** Breakdown by document type */
  typeBreakdown: Record<DocumentType, number>;
  /** Callback when Add Files button is clicked */
  onAddFiles: () => void;
}

/**
 * Type badge display configuration
 */
const TYPE_CONFIG: Record<
  DocumentType,
  { label: string; icon: React.ComponentType<{ className?: string }> }
> = {
  case_file: { label: 'Case Files', icon: FileText },
  act: { label: 'Acts', icon: Gavel },
  annexure: { label: 'Annexures', icon: Paperclip },
  other: { label: 'Other', icon: FolderOpen },
};

/**
 * Documents Header component.
 *
 * Displays document statistics, type breakdown, and processing status.
 *
 * @example
 * ```tsx
 * <DocumentsHeader
 *   totalCount={42}
 *   processingCount={3}
 *   processingPercent={7}
 *   typeBreakdown={{ case_file: 20, act: 10, annexure: 10, other: 2 }}
 *   onAddFiles={() => setDialogOpen(true)}
 * />
 * ```
 */
export function DocumentsHeader({
  totalCount,
  processingCount,
  processingPercent,
  typeBreakdown,
  onAddFiles,
}: DocumentsHeaderProps) {
  return (
    <div className="space-y-4">
      {/* Main header with count and add button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Documents</h2>
          <p className="text-sm text-muted-foreground">
            {totalCount} {totalCount === 1 ? 'document' : 'documents'} in this matter
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Celery status indicator */}
          <CeleryStatusIndicator showLabel />
          <Button onClick={onAddFiles}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            Add Files
          </Button>
        </div>
      </div>

      {/* Type breakdown badges */}
      {totalCount > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          {(Object.keys(TYPE_CONFIG) as DocumentType[]).map((type) => {
            const count = typeBreakdown[type];
            if (count === 0) return null;

            const config = TYPE_CONFIG[type];
            const Icon = config.icon;

            return (
              <div
                key={type}
                className="flex items-center gap-1.5 px-2.5 py-1 bg-muted rounded-md text-sm"
              >
                <Icon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                <span className="text-muted-foreground">{config.label}:</span>
                <span className="font-medium">{count}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Processing banner - AC #2 */}
      {processingCount > 0 && (
        <Alert className="bg-primary/5 border-primary/20 dark:bg-primary/10 dark:border-primary/30">
          <div className="flex items-center gap-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary dark:text-primary/80" aria-hidden="true" />
            <div className="flex-1">
              <AlertDescription className="text-primary dark:text-primary/90">
                Processing NEW DOCUMENTS: {processingCount} {processingCount === 1 ? 'file' : 'files'} ({100 - processingPercent}% complete)
              </AlertDescription>
              <Progress
                value={100 - processingPercent}
                className="mt-2 h-1.5"
                aria-label={`${100 - processingPercent}% of documents indexed`}
              />
            </div>
          </div>
        </Alert>
      )}
    </div>
  );
}
