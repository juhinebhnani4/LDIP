'use client';

/**
 * ExportSectionPreview Component
 *
 * Renders individual export section content with inline editing support.
 * Delegates to specific renderers based on section type.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Pencil, Check, Plus, X, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExportSectionId, ExportSectionEdit } from '@/types/export';
import type { MatterSummary, KeyIssue } from '@/types/summary';
import type { TimelineEvent } from '@/types/timeline';
import type { EntityListItem } from '@/types/entity';
import type { CitationListItem } from '@/types/citation';

// Import renderers
import { ExecutiveSummaryRenderer } from './renderers/ExecutiveSummaryRenderer';
import { TimelineRenderer } from './renderers/TimelineRenderer';
import { EntitiesRenderer } from './renderers/EntitiesRenderer';
import { CitationsRenderer } from './renderers/CitationsRenderer';
import { KeyFindingsRenderer } from './renderers/KeyFindingsRenderer';
import { ContradictionsRenderer } from './renderers/ContradictionsRenderer';

export interface ExportSectionPreviewProps {
  /** Section ID */
  sectionId: ExportSectionId;
  /** Section data (varies by type) */
  data: unknown;
  /** Edit state for this section */
  edit?: ExportSectionEdit;
  /** Whether this section is being edited */
  isEditing: boolean;
  /** Handler for removing an item */
  onRemoveItem: (itemId: string) => void;
  /** Handler for restoring a removed item */
  onRestoreItem: (itemId: string) => void;
  /** Handler for adding a note */
  onAddNote: (note: string) => void;
  /** Handler for removing a note */
  onRemoveNote: (noteIndex: number) => void;
  /** Handler for toggling edit mode */
  onSetEditing: (editing: boolean) => void;
  /** Handler for updating text content */
  onUpdateText: (text: string) => void;
}

/**
 * ExportSectionPreview renders content based on section type.
 */
export function ExportSectionPreview({
  sectionId,
  data,
  edit,
  isEditing,
  onRemoveItem,
  onRestoreItem,
  onAddNote,
  onRemoveNote,
  onSetEditing,
  onUpdateText,
}: ExportSectionPreviewProps) {
  const [newNote, setNewNote] = useState('');
  const [showAddNote, setShowAddNote] = useState(false);

  const handleAddNote = () => {
    if (newNote.trim()) {
      onAddNote(newNote.trim());
      setNewNote('');
      setShowAddNote(false);
    }
  };

  // Get removed item IDs from edit state
  const removedItemIds = edit?.removedItemIds ?? [];
  const addedNotes = edit?.addedNotes ?? [];

  // Render section content based on type
  const renderContent = () => {
    switch (sectionId) {
      case 'executive-summary':
        return (
          <ExecutiveSummaryRenderer
            summary={data as MatterSummary | undefined}
            isEditing={isEditing}
            onUpdateText={onUpdateText}
            textContent={edit?.textContent}
          />
        );

      case 'timeline':
        return (
          <TimelineRenderer
            events={data as TimelineEvent[] | undefined}
            removedItemIds={removedItemIds}
            onRemoveItem={onRemoveItem}
            onRestoreItem={onRestoreItem}
            isEditing={isEditing}
          />
        );

      case 'entities':
        return (
          <EntitiesRenderer
            entities={data as EntityListItem[] | undefined}
            removedItemIds={removedItemIds}
            onRemoveItem={onRemoveItem}
            onRestoreItem={onRestoreItem}
            isEditing={isEditing}
          />
        );

      case 'citations':
        return (
          <CitationsRenderer
            citations={data as CitationListItem[] | undefined}
            removedItemIds={removedItemIds}
            onRemoveItem={onRemoveItem}
            onRestoreItem={onRestoreItem}
            isEditing={isEditing}
          />
        );

      case 'key-findings':
        return (
          <KeyFindingsRenderer
            findings={data as KeyIssue[] | undefined}
            removedItemIds={removedItemIds}
            onRemoveItem={onRemoveItem}
            onRestoreItem={onRestoreItem}
            isEditing={isEditing}
          />
        );

      case 'contradictions':
        return <ContradictionsRenderer />;

      default:
        return <p className="text-muted-foreground">Unknown section type</p>;
    }
  };

  return (
    <div className="relative group">
      {/* Edit toggle button */}
      <Button
        variant="ghost"
        size="sm"
        className={cn(
          'absolute top-0 right-0 transition-opacity',
          isEditing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        )}
        onClick={() => onSetEditing(!isEditing)}
        aria-label={isEditing ? 'Done editing' : 'Edit section'}
        data-testid={`edit-button-${sectionId}`}
      >
        {isEditing ? <Check className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
      </Button>

      {/* Section content */}
      <div className="pr-8">
        {renderContent()}

        {/* Added notes */}
        {addedNotes.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">Added Notes:</h4>
            {addedNotes.map((note, index) => (
              <div
                key={index}
                className="flex items-start gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800"
              >
                <p className="flex-1 text-sm italic">{note}</p>
                {isEditing && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 shrink-0"
                    onClick={() => onRemoveNote(index)}
                    aria-label="Remove note"
                  >
                    <X className="h-3 w-3" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Add note UI (only in edit mode) */}
        {isEditing && (
          <div className="mt-4">
            {showAddNote ? (
              <div className="space-y-2">
                <textarea
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  placeholder="Enter your note..."
                  className="w-full min-h-[60px] p-2 border rounded text-sm resize-none"
                  data-testid={`note-input-${sectionId}`}
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleAddNote} disabled={!newNote.trim()}>
                    Add Note
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowAddNote(false);
                      setNewNote('');
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddNote(true)}
                className="gap-1"
                data-testid={`add-note-button-${sectionId}`}
              >
                <Plus className="h-3 w-3" />
                Add Note
              </Button>
            )}
          </div>
        )}

        {/* Removed items indicator */}
        {removedItemIds.length > 0 && (
          <div className="mt-4 p-2 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
            <div className="flex items-center justify-between">
              <span className="text-sm text-red-600 dark:text-red-400">
                {removedItemIds.length} item{removedItemIds.length !== 1 ? 's' : ''} removed
              </span>
              {isEditing && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 gap-1 text-xs"
                  onClick={() => {
                    // Restore all removed items
                    removedItemIds.forEach((id) => onRestoreItem(id));
                  }}
                >
                  <RotateCcw className="h-3 w-3" />
                  Restore All
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
