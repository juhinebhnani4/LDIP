'use client';

/**
 * ExportPreviewPanel Component
 *
 * Displays a preview of the export document with all selected sections.
 * Supports inline editing and real-time preview updates.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { useMemo } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { ExportSectionPreview } from './ExportSectionPreview';
import type { ExportSectionId, ExportSectionEdit } from '@/types/export';
import type { MatterSummary } from '@/types/summary';
import type { TimelineEvent } from '@/types/timeline';
import type { EntityListItem } from '@/types/entity';
import type { CitationListItem } from '@/types/citation';

export interface ExportPreviewPanelProps {
  /** Matter ID for fetching data */
  matterId: string;
  /** IDs of selected sections in order */
  selectedSectionIds: ExportSectionId[];
  /** Section edits map */
  sectionEdits: Map<ExportSectionId, ExportSectionEdit>;
  /** Section currently being edited */
  editingSection: ExportSectionId | null;
  /** Handler for removing an item from a section */
  onRemoveItem: (sectionId: ExportSectionId, itemId: string) => void;
  /** Handler for restoring a removed item */
  onRestoreItem: (sectionId: ExportSectionId, itemId: string) => void;
  /** Handler for adding a note to a section */
  onAddNote: (sectionId: ExportSectionId, note: string) => void;
  /** Handler for removing a note */
  onRemoveNote: (sectionId: ExportSectionId, noteIndex: number) => void;
  /** Handler for setting the editing section */
  onSetEditingSection: (sectionId: ExportSectionId | null) => void;
  /** Handler for updating text content */
  onUpdateText: (sectionId: ExportSectionId, text: string) => void;
  /** Summary data */
  summary?: MatterSummary;
  /** Summary loading state */
  summaryLoading?: boolean;
  /** Timeline events */
  events?: TimelineEvent[];
  /** Timeline loading state */
  timelineLoading?: boolean;
  /** Entities data */
  entities?: EntityListItem[];
  /** Entities loading state */
  entitiesLoading?: boolean;
  /** Citations data */
  citations?: CitationListItem[];
  /** Citations loading state */
  citationsLoading?: boolean;
}

/**
 * Section labels for display
 */
const SECTION_LABELS: Record<ExportSectionId, string> = {
  'executive-summary': 'Executive Summary',
  'timeline': 'Timeline',
  'entities': 'Entities',
  'citations': 'Citations',
  'contradictions': 'Contradictions',
  'key-findings': 'Key Findings',
};

/**
 * ExportPreviewPanel renders a document-like preview of selected sections.
 */
export function ExportPreviewPanel({
  matterId,
  selectedSectionIds,
  sectionEdits,
  editingSection,
  onRemoveItem,
  onRestoreItem,
  onAddNote,
  onRemoveNote,
  onSetEditingSection,
  onUpdateText,
  summary,
  summaryLoading,
  events,
  timelineLoading,
  entities,
  entitiesLoading,
  citations,
  citationsLoading,
}: ExportPreviewPanelProps) {
  // Check if data is loading for any section
  const isLoading = summaryLoading || timelineLoading || entitiesLoading || citationsLoading;

  // Memoize section data mapping
  const sectionData = useMemo(() => {
    return {
      'executive-summary': {
        data: summary,
        isLoading: summaryLoading,
      },
      'timeline': {
        data: events,
        isLoading: timelineLoading,
      },
      'entities': {
        data: entities,
        isLoading: entitiesLoading,
      },
      'citations': {
        data: citations,
        isLoading: citationsLoading,
      },
      'contradictions': {
        data: null, // Phase 2 placeholder
        isLoading: false,
      },
      'key-findings': {
        data: summary?.keyIssues,
        isLoading: summaryLoading,
      },
    };
  }, [summary, summaryLoading, events, timelineLoading, entities, entitiesLoading, citations, citationsLoading]);

  if (selectedSectionIds.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>Select sections to preview</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="export-preview-container p-6" data-testid="export-preview-panel">
        {/* Document preview - styled to look like a PDF */}
        <div className="export-preview-page bg-white dark:bg-slate-900 rounded-lg shadow-md p-8 space-y-8">
          {selectedSectionIds.map((sectionId) => {
            const section = sectionData[sectionId];
            const edit = sectionEdits.get(sectionId);
            const isEditing = editingSection === sectionId;

            return (
              <section
                key={sectionId}
                id={`preview-${sectionId}`}
                className="export-preview-section"
                data-testid={`preview-section-${sectionId}`}
              >
                <h2 className="export-section-header text-lg font-bold mb-4 pb-2 border-b border-gray-200 dark:border-gray-700">
                  {SECTION_LABELS[sectionId]}
                </h2>

                {section.isLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                ) : (
                  <ExportSectionPreview
                    sectionId={sectionId}
                    data={section.data}
                    edit={edit}
                    isEditing={isEditing}
                    onRemoveItem={(itemId) => onRemoveItem(sectionId, itemId)}
                    onRestoreItem={(itemId) => onRestoreItem(sectionId, itemId)}
                    onAddNote={(note) => onAddNote(sectionId, note)}
                    onRemoveNote={(noteIndex) => onRemoveNote(sectionId, noteIndex)}
                    onSetEditing={(editing) => onSetEditingSection(editing ? sectionId : null)}
                    onUpdateText={(text) => onUpdateText(sectionId, text)}
                  />
                )}
              </section>
            );
          })}
        </div>
      </div>
    </ScrollArea>
  );
}
