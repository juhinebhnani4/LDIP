'use client';

/**
 * ExportBuilder Modal Component
 *
 * Modal for configuring export sections and order before generating a document.
 * Story 12.2 adds two-panel layout with section list and preview.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection
 * @see Story 12.2 - Export Inline Editing and Preview
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

import { useEffect, useState, useRef } from 'react';
import { FileText, FileType, Presentation, List, Eye, RotateCcw } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { toast } from 'sonner';
import { ExportSectionList } from './ExportSectionList';
import { ExportPreviewPanel } from './ExportPreviewPanel';
import { useExportBuilder } from '@/hooks/useExportBuilder';
import { useMatterSummary } from '@/hooks/useMatterSummary';
import { useTimeline } from '@/hooks/useTimeline';
import { useEntities } from '@/hooks/useEntities';
import { useCitationStats, useCitationsList } from '@/hooks/useCitations';
import type { ExportFormat, ExportPreviewMode } from '@/types/export';

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
 * - Two-panel layout with preview (Story 12.2)
 * - Inline editing capability (Story 12.2)
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
    // Story 12.2
    previewMode,
    setPreviewMode,
    sectionEdits,
    updateSectionEdit,
    removeSectionItem,
    restoreSectionItem,
    addSectionNote,
    removeSectionNote,
    resetSectionEdits,
    hasEdits,
    editingSection,
    setEditingSection,
  } = useExportBuilder({ initialFormat: format });

  // Unsaved changes dialog state
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);
  const [pendingClose, setPendingClose] = useState(false);

  // Fetch content counts from existing hooks
  const { summary, isLoading: summaryLoading, isError: summaryError } = useMatterSummary(matterId);
  const { events, isLoading: timelineLoading, isError: timelineError } = useTimeline(matterId);
  const { entities, total: entitiesTotal, isLoading: entitiesLoading, error: entitiesError } = useEntities(matterId);
  const { stats: citationStats, isLoading: citationsLoading, error: citationsError } = useCitationStats(matterId);
  // Fetch full citations list for preview
  const { citations } = useCitationsList(matterId, { perPage: 100 });

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

  // Track if the modal was previously open to know when to reset
  const wasOpenRef = useRef(open);

  // Reset state when modal opens (from closed state)
  useEffect(() => {
    // Only reset when transitioning from closed to open, not on initial render
    if (open && !wasOpenRef.current) {
      reset();
    }
    wasOpenRef.current = open;
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
    if (hasEdits) {
      setPendingClose(true);
      setShowUnsavedDialog(true);
    } else {
      onOpenChange(false);
    }
  };

  const handleConfirmClose = () => {
    setShowUnsavedDialog(false);
    setPendingClose(false);
    onOpenChange(false);
  };

  const handleCancelClose = () => {
    setShowUnsavedDialog(false);
    setPendingClose(false);
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && hasEdits) {
      setPendingClose(true);
      setShowUnsavedDialog(true);
    } else {
      onOpenChange(newOpen);
    }
  };

  const handleResetEdits = () => {
    resetSectionEdits();
    toast.info('All edits have been reset');
  };

  // Suppress unused variable warning - pendingClose is used for dialog state tracking
  void pendingClose;

  const FormatIcon = FORMAT_CONFIG[format].icon;

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent
          className="sm:max-w-[900px] lg:max-w-[1100px] h-[80vh] flex flex-col"
          aria-describedby="export-builder-description"
        >
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle className="flex items-center gap-2">
                <FormatIcon className="h-5 w-5" />
                Export as {FORMAT_CONFIG[format].label}
              </DialogTitle>

              {/* View mode tabs */}
              <Tabs
                value={previewMode}
                onValueChange={(v) => setPreviewMode(v as ExportPreviewMode)}
                className="ml-4"
              >
                <TabsList className="h-8">
                  <TabsTrigger value="sections" className="h-7 px-3 text-xs gap-1">
                    <List className="h-3 w-3" />
                    Sections
                  </TabsTrigger>
                  <TabsTrigger value="preview" className="h-7 px-3 text-xs gap-1">
                    <Eye className="h-3 w-3" />
                    Preview
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <DialogDescription id="export-builder-description">
              Select and reorder sections to include in your export
              {previewMode === 'preview' && ' • Click sections to edit'}
            </DialogDescription>
          </DialogHeader>

          {/* Two-panel layout */}
          <div className="flex-1 overflow-hidden -mx-1 px-1">
            {previewMode === 'sections' ? (
              /* Section list only view */
              <div className="h-full overflow-y-auto py-2">
                <ExportSectionList
                  sections={sections}
                  onToggleSection={toggleSection}
                  onReorder={reorderSections}
                  onSelectAll={selectAll}
                  onDeselectAll={deselectAll}
                  selectedCount={selectedCount}
                />
              </div>
            ) : (
              /* Preview with resizable panels */
              <ResizablePanelGroup direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={35} minSize={25} maxSize={50}>
                  <div className="h-full overflow-y-auto py-2 pr-2">
                    <ExportSectionList
                      sections={sections}
                      onToggleSection={toggleSection}
                      onReorder={reorderSections}
                      onSelectAll={selectAll}
                      onDeselectAll={deselectAll}
                      selectedCount={selectedCount}
                    />
                  </div>
                </ResizablePanel>

                <ResizableHandle withHandle />

                <ResizablePanel defaultSize={65} minSize={40}>
                  <div className="h-full overflow-hidden pl-2 border-l">
                    <ExportPreviewPanel
                      matterId={matterId}
                      selectedSectionIds={selectedSectionIds}
                      sectionEdits={sectionEdits}
                      editingSection={editingSection}
                      onRemoveItem={removeSectionItem}
                      onRestoreItem={restoreSectionItem}
                      onAddNote={addSectionNote}
                      onRemoveNote={removeSectionNote}
                      onSetEditingSection={setEditingSection}
                      onUpdateText={updateSectionEdit}
                      summary={summary}
                      summaryLoading={summaryLoading}
                      events={events}
                      timelineLoading={timelineLoading}
                      entities={entities}
                      entitiesLoading={entitiesLoading}
                      citations={citations}
                      citationsLoading={citationsLoading}
                    />
                  </div>
                </ResizablePanel>
              </ResizablePanelGroup>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            {hasEdits && (
              <Button
                variant="outline"
                onClick={handleResetEdits}
                className="mr-auto gap-1"
                data-testid="reset-edits-button"
              >
                <RotateCcw className="h-4 w-4" />
                Reset Edits
              </Button>
            )}
            <Button variant="outline" onClick={handleCancel}>
              Cancel
            </Button>
            <Button onClick={handleContinue} disabled={!hasSelection}>
              Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unsaved changes confirmation dialog */}
      <AlertDialog open={showUnsavedDialog} onOpenChange={setShowUnsavedDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved edits that will be lost if you close this dialog.
              Are you sure you want to continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelClose}>
              Keep Editing
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmClose}>
              Discard Changes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
