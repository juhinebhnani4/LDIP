'use client';

/**
 * ExportBuilder Modal Component
 *
 * Modal for configuring export sections and order before generating a document.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection
 *
 * @example
 * ```tsx
 * <ExportBuilder
 *   matterId="matter-123"
 *   format="pdf"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */

import { useEffect } from 'react';
import { FileText, FileType, Presentation } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { ExportSectionList } from './ExportSectionList';
import { useExportBuilder } from '@/hooks/useExportBuilder';
import { useMatterSummary } from '@/hooks/useMatterSummary';
import { useTimeline } from '@/hooks/useTimeline';
import { useEntities } from '@/hooks/useEntities';
import { useCitationStats } from '@/hooks/useCitations';
import type { ExportFormat } from '@/types/export';

export interface ExportBuilderProps {
  /** Matter ID for fetching content counts */
  matterId: string;
  /** Selected export format */
  format: ExportFormat;
  /** Whether the modal is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
}

/** Format display configuration */
const FORMAT_CONFIG = {
  pdf: { label: 'PDF', icon: FileText },
  word: { label: 'Word', icon: FileType },
  powerpoint: { label: 'PowerPoint', icon: Presentation },
} as const;

/**
 * ExportBuilder modal for configuring document exports.
 *
 * Features:
 * - Section selection with checkboxes
 * - Drag-and-drop reordering
 * - Content count preview for each section
 * - Format-specific header
 */
export function ExportBuilder({
  matterId,
  format,
  open,
  onOpenChange,
}: ExportBuilderProps) {
  const {
    sections,
    toggleSection,
    reorderSections,
    selectAll,
    deselectAll,
    updateSectionCount,
    setSectionLoading,
    selectedCount,
    hasSelection,
    selectedSectionIds,
    reset,
  } = useExportBuilder({ initialFormat: format });

  // Fetch content counts from existing hooks
  const { summary, isLoading: summaryLoading, isError: summaryError } = useMatterSummary(matterId);
  const { events, isLoading: timelineLoading, isError: timelineError } = useTimeline(matterId);
  const { total: entitiesTotal, isLoading: entitiesLoading, error: entitiesError } = useEntities(matterId);
  const { stats: citationStats, isLoading: citationsLoading, error: citationsError } = useCitationStats(matterId);

  // Update section counts when data is loaded
  // updateSectionCount and setSectionLoading are stable (useCallback with [] deps)
  useEffect(() => {
    // Executive Summary - count key sections based on MatterSummary type
    if (summaryLoading) {
      setSectionLoading('executive-summary', true);
      setSectionLoading('key-findings', true);
    } else if (summaryError) {
      // On error, show 0 count (section still selectable)
      updateSectionCount('executive-summary', 0);
      updateSectionCount('key-findings', 0);
    } else if (summary) {
      // Count non-empty sections in summary
      // MatterSummary has: parties, subjectMatter, currentStatus, keyIssues
      let summaryCount = 0;
      if (summary.parties?.length) summaryCount++;
      if (summary.subjectMatter?.description) summaryCount++;
      if (summary.currentStatus?.description) summaryCount++;
      if (summary.attentionItems?.length) summaryCount++;
      updateSectionCount('executive-summary', summaryCount);

      // Key findings count (keyIssues)
      const findingsCount = summary.keyIssues?.length ?? 0;
      updateSectionCount('key-findings', findingsCount);
    }
  }, [summary, summaryLoading, summaryError, updateSectionCount, setSectionLoading]);

  useEffect(() => {
    // Timeline events count
    if (timelineLoading) {
      setSectionLoading('timeline', true);
    } else if (timelineError) {
      updateSectionCount('timeline', 0);
    } else {
      updateSectionCount('timeline', events.length);
    }
  }, [events, timelineLoading, timelineError, updateSectionCount, setSectionLoading]);

  useEffect(() => {
    // Entities count
    if (entitiesLoading) {
      setSectionLoading('entities', true);
    } else if (entitiesError) {
      updateSectionCount('entities', 0);
    } else {
      updateSectionCount('entities', entitiesTotal);
    }
  }, [entitiesTotal, entitiesLoading, entitiesError, updateSectionCount, setSectionLoading]);

  useEffect(() => {
    // Citations count
    if (citationsLoading) {
      setSectionLoading('citations', true);
    } else if (citationsError) {
      updateSectionCount('citations', 0);
    } else if (citationStats) {
      updateSectionCount('citations', citationStats.totalCitations);
    }
  }, [citationStats, citationsLoading, citationsError, updateSectionCount, setSectionLoading]);

  // Contradictions - Phase 2 placeholder, set to 0
  useEffect(() => {
    updateSectionCount('contradictions', 0);
  }, [updateSectionCount]);

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      reset();
    }
  }, [open, reset]);

  const handleContinue = () => {
    // TODO(Epic-12): Navigate to export generation with selected sections
    const sectionNames = selectedSectionIds
      .map((id) => sections.find((s) => s.id === id)?.label)
      .filter(Boolean)
      .join(', ');

    toast.info(
      `Export generation coming in Story 12.3. Selected: ${sectionNames}`
    );
    onOpenChange(false);
  };

  const handleCancel = () => {
    onOpenChange(false);
  };

  const FormatIcon = FORMAT_CONFIG[format].icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[600px] max-h-[80vh] flex flex-col"
        aria-describedby="export-builder-description"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FormatIcon className="h-5 w-5" />
            Export as {FORMAT_CONFIG[format].label}
          </DialogTitle>
          <DialogDescription id="export-builder-description">
            Select and reorder sections to include in your export
          </DialogDescription>
        </DialogHeader>

        {/* Section list */}
        <div className="flex-1 overflow-y-auto py-2 -mx-1 px-1">
          <ExportSectionList
            sections={sections}
            onToggleSection={toggleSection}
            onReorder={reorderSections}
            onSelectAll={selectAll}
            onDeselectAll={deselectAll}
            selectedCount={selectedCount}
          />
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleContinue} disabled={!hasSelection}>
            Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
