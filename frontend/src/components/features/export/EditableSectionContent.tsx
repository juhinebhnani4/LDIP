'use client';

/**
 * EditableSectionContent Component
 *
 * Wrapper component for editable text blocks in export preview.
 * Provides edit toggle and text editing functionality.
 *
 * @see Story 12.2 - Export Inline Editing and Preview - Task 4.1
 */

import { useState, useRef, useMemo } from 'react';
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
  // Track previous textContent to detect external changes
  const prevTextContentRef = useRef(textContent);
  const prevIsEditingRef = useRef(isEditing);

  // Compute local text value based on prop changes (no useEffect needed)
  const localText = useMemo(() => {
    // If textContent changed externally, use it
    if (textContent !== prevTextContentRef.current && textContent !== undefined) {
      prevTextContentRef.current = textContent;
      return textContent;
    }
    // If just entering edit mode with no textContent, use default
    if (isEditing && !prevIsEditingRef.current && !textContent && defaultText) {
      prevIsEditingRef.current = isEditing;
      return defaultText;
    }
    prevIsEditingRef.current = isEditing;
    // Return current textContent or default
    return textContent ?? defaultText;
  }, [textContent, isEditing, defaultText]);

  // Local state for textarea value (synced from computed value)
  const [editedText, setEditedText] = useState(localText);

  // Sync edited text when localText changes (prop-driven)
  if (editedText !== localText && textContent !== undefined) {
    setEditedText(localText);
  }

  const handleTextChange = (value: string) => {
    setEditedText(value);
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
            value={editedText}
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
