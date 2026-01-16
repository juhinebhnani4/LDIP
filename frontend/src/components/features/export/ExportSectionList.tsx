'use client';

/**
 * ExportSectionList Component
 *
 * Sortable list of export sections with drag-and-drop reordering.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection - Task 2, 3
 */

import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  DragOverlay,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { Button } from '@/components/ui/button';
import { SortableSection } from './SortableSection';
import type { ExportSection, ExportSectionId } from '@/types/export';

export interface ExportSectionListProps {
  /** List of sections to display */
  sections: ExportSection[];
  /** Handler for toggling section enabled state */
  onToggleSection: (sectionId: ExportSectionId) => void;
  /** Handler for reordering sections */
  onReorder: (activeId: string, overId: string) => void;
  /** Handler for selecting all sections */
  onSelectAll: () => void;
  /** Handler for deselecting all sections */
  onDeselectAll: () => void;
  /** Number of currently selected sections */
  selectedCount: number;
}

/**
 * ExportSectionList displays a sortable list of export sections.
 *
 * Features:
 * - Drag-and-drop reordering
 * - Checkbox selection for each section
 * - Select all / Deselect all buttons
 * - Visual feedback during drag operations
 */
export function ExportSectionList({
  sections,
  onToggleSection,
  onReorder,
  onSelectAll,
  onDeselectAll,
  selectedCount,
}: ExportSectionListProps) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // 8px movement required before drag starts
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (over && active.id !== over.id) {
      onReorder(active.id as string, over.id as string);
    }
  };

  const handleDragCancel = () => {
    setActiveId(null);
  };

  const activeSection = activeId
    ? sections.find((s) => s.id === activeId)
    : null;

  const allSelected = selectedCount === sections.length;
  const noneSelected = selectedCount === 0;

  return (
    <div className="space-y-3">
      {/* Select all / Deselect all controls */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {selectedCount} of {sections.length} sections selected
        </span>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onSelectAll}
            disabled={allSelected}
          >
            Select all
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDeselectAll}
            disabled={noneSelected}
          >
            Deselect all
          </Button>
        </div>
      </div>

      {/* Sortable section list */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <SortableContext
          items={sections.map((s) => s.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2" role="list" aria-label="Export sections">
            {sections.map((section) => (
              <SortableSection
                key={section.id}
                section={section}
                onToggle={onToggleSection}
                isDragging={section.id === activeId}
              />
            ))}
          </div>
        </SortableContext>

        {/* Drag overlay for visual feedback */}
        <DragOverlay>
          {activeSection ? (
            <div className="flex items-center gap-3 p-3 rounded-lg border bg-card shadow-lg border-primary opacity-90">
              <div className="p-1">
                <div className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium">{activeSection.label}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {activeSection.description}
                </p>
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
