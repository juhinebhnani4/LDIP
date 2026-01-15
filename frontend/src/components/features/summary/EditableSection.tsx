'use client';

/**
 * EditableSection Component
 *
 * Wrapper component that makes summary sections editable with view/edit mode toggle.
 * Preserves original AI content and allows regeneration.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #3)
 */

import { useState, type ReactNode } from 'react';
import { Pencil, RotateCcw, Save, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { SummarySectionType } from '@/types/summary';

interface EditableSectionProps {
  /** Section type for tracking edits */
  sectionType: SummarySectionType;
  /** Section ID */
  sectionId: string;
  /** Current content */
  content: string;
  /** Original AI-generated content for comparison */
  originalContent?: string;
  /** Callback when content is saved */
  onSave: (newContent: string) => Promise<void>;
  /** Callback to regenerate AI content */
  onRegenerate: () => Promise<void>;
  /** Render function for view mode */
  children: ReactNode;
  /** Additional className */
  className?: string;
}

export function EditableSection({
  content,
  onSave,
  onRegenerate,
  children,
  className,
}: EditableSectionProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [editedContent, setEditedContent] = useState(content);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const handleEdit = () => {
    setEditedContent(content);
    setIsEditing(true);
  };

  const handleCancel = () => {
    setEditedContent(content);
    setIsEditing(false);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(editedContent);
      setIsEditing(false);
    } catch {
      // Error handling delegated to parent
    } finally {
      setIsSaving(false);
    }
  };

  const handleRegenerate = async () => {
    setIsRegenerating(true);
    try {
      await onRegenerate();
    } catch {
      // Error handling delegated to parent
    } finally {
      setIsRegenerating(false);
    }
  };

  if (isEditing) {
    return (
      <div
        data-testid="editable-section"
        className={cn('space-y-4', className)}
      >
        <Textarea
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          className="min-h-[120px]"
          placeholder="Enter content..."
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving || isRegenerating}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" aria-hidden="true" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-1.5" aria-hidden="true" />
                Save
              </>
            )}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancel}
            disabled={isSaving || isRegenerating}
          >
            <X className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Cancel
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRegenerate}
            disabled={isSaving || isRegenerating}
            className="ml-auto"
          >
            {isRegenerating ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" aria-hidden="true" />
                Regenerating...
              </>
            ) : (
              <>
                <RotateCcw className="h-4 w-4 mr-1.5" aria-hidden="true" />
                Regenerate
              </>
            )}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="editable-section"
      className={cn('relative group', className)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {children}
      <div
        className={cn(
          'absolute top-2 right-2 transition-opacity',
          isHovered ? 'opacity-100' : 'opacity-0'
        )}
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={handleEdit}
          className="h-7 px-2"
        >
          <Pencil className="h-4 w-4 mr-1" aria-hidden="true" />
          Edit
        </Button>
      </div>
    </div>
  );
}
