'use client';

/**
 * EditableSectionContent Component
 *
 * Wrapper component for editable text blocks in export preview.
 * Provides edit toggle and text editing functionality.
 *
 * @see Story 12.2 - Export Inline Editing and Preview - Task 4.1
 */

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Pencil, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExportSectionId } from '@/types/export';
import type { ReactNode } from 'react';

export interface EditableSectionContentProps {
  /** Section ID for identification */
  sectionId: ExportSectionId;
  /** Content to display when not editing */
  content: ReactNode;
  /** Whether this section is in edit mode */
  isEditing: boolean;
  /** Current text content for editing */
  textContent?: string;
  /** Default text content when entering edit mode */
  defaultText?: string;
  /** Handler for text content changes */
  onUpdateText: (text: string) => void;
  /** Handler for toggling edit mode */
  onToggleEdit: () => void;
  /** Placeholder text for textarea */
  placeholder?: string;
  /** Minimum height for textarea */
  minHeight?: string;
}

/**
 * EditableSectionContent provides a toggle between view and edit modes.
 *
 * Features:
 * - Pencil icon button to enter edit mode (shows on hover)
 * - Check icon button to exit edit mode
 * - Controlled textarea for text editing
 * - Real-time updates via onUpdateText callback
 */
export function EditableSectionContent({
  sectionId,
  content,
  isEditing,
  textContent,
  defaultText = '',
  onUpdateText,
  onToggleEdit,
  placeholder = 'Enter content...',
  minHeight = '200px',
}: EditableSectionContentProps) {
  // Local state for textarea value - controlled sync pattern
  const [localText, setLocalText] = useState(textContent ?? defaultText);

  // Sync local text when textContent prop changes (controlled component pattern)
  // This is intentional - we need to sync state when prop changes
  useEffect(() => {
    if (textContent !== undefined) {
      setLocalText(textContent);
    }
  }, [textContent]);

  // Initialize local text with default when entering edit mode
  useEffect(() => {
    if (isEditing && !textContent && defaultText) {
      setLocalText(defaultText);
    }
  }, [isEditing, textContent, defaultText]);

  const handleTextChange = (value: string) => {
    setLocalText(value);
    onUpdateText(value);
  };

  return (
    <div className="relative group">
      {/* Edit toggle button */}
      <Button
        variant="ghost"
        size="sm"
        className={cn(
          'absolute top-0 right-0 z-10 transition-opacity',
          isEditing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        )}
        onClick={onToggleEdit}
        aria-label={isEditing ? 'Done editing' : 'Edit section'}
        data-testid={`editable-toggle-${sectionId}`}
      >
        {isEditing ? <Check className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
      </Button>

      {/* Content area */}
      <div className="pr-8">
        {isEditing ? (
          <textarea
            value={localText}
            onChange={(e) => handleTextChange(e.target.value)}
            placeholder={placeholder}
            className={cn(
              'w-full p-3 border rounded font-serif text-sm leading-relaxed resize-none',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent'
            )}
            style={{ minHeight }}
            data-testid={`editable-textarea-${sectionId}`}
          />
        ) : (
          content
        )}
      </div>
    </div>
  );
}
