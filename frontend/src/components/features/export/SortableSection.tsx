'use client';

/**
 * SortableSection Component
 *
 * Draggable section item for the Export Builder.
 * Uses @dnd-kit/sortable for drag-and-drop functionality.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection - Task 3
 */

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { ExportSection, ExportSectionId } from '@/types/export';

export interface SortableSectionProps {
  /** Section data */
  section: ExportSection;
  /** Handler for toggling section */
  onToggle: (sectionId: ExportSectionId) => void;
  /** Whether the section is being dragged */
  isDragging?: boolean;
}

/**
 * Format count for display
 */
function formatCount(count: number | undefined, sectionId: ExportSectionId): string {
  if (count === undefined) return '';

  const labels: Record<ExportSectionId, { singular: string; plural: string }> = {
    'executive-summary': { singular: 'section', plural: 'sections' },
    timeline: { singular: 'event', plural: 'events' },
    entities: { singular: 'entity', plural: 'entities' },
    citations: { singular: 'citation', plural: 'citations' },
    contradictions: { singular: 'issue', plural: 'issues' },
    'key-findings': { singular: 'finding', plural: 'findings' },
  };

  const label = count === 1 ? labels[sectionId].singular : labels[sectionId].plural;
  return `${count} ${label}`;
}

/**
 * SortableSection renders a draggable section item with checkbox.
 *
 * Features:
 * - Drag handle for reordering
 * - Checkbox for enabling/disabling
 * - Content count preview
 * - Visual feedback during drag
 */
export function SortableSection({
  section,
  onToggle,
  isDragging = false,
}: SortableSectionProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: section.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const isCurrentlyDragging = isDragging || isSortableDragging;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border bg-card transition-colors',
        isCurrentlyDragging && 'opacity-50 shadow-lg border-primary',
        !section.enabled && 'opacity-60'
      )}
      data-testid={`sortable-section-${section.id}`}
    >
      {/* Drag handle */}
      <button
        type="button"
        className="touch-none cursor-grab active:cursor-grabbing p-1 rounded hover:bg-muted"
        aria-label={`Drag to reorder ${section.label}`}
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4 text-muted-foreground" />
      </button>

      {/* Checkbox */}
      <Checkbox
        id={`section-${section.id}`}
        checked={section.enabled}
        onCheckedChange={() => onToggle(section.id)}
        aria-describedby={`section-${section.id}-desc`}
      />

      {/* Label and description */}
      <div className="flex-1 min-w-0">
        <Label
          htmlFor={`section-${section.id}`}
          className={cn(
            'font-medium cursor-pointer',
            !section.enabled && 'text-muted-foreground'
          )}
        >
          {section.label}
        </Label>
        <p
          id={`section-${section.id}-desc`}
          className="text-xs text-muted-foreground truncate"
        >
          {section.description}
        </p>
      </div>

      {/* Content count */}
      <div className="text-xs text-muted-foreground whitespace-nowrap">
        {section.isLoadingCount ? (
          <Skeleton className="h-4 w-16" />
        ) : (
          formatCount(section.count, section.id)
        )}
      </div>
    </div>
  );
}
