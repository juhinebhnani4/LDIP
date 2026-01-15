'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Pencil, Check, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { useMatterStore } from '@/stores/matterStore';

/** Maximum length for matter name */
const MAX_MATTER_NAME_LENGTH = 100;

/** State machine for edit mode */
type EditState = 'viewing' | 'editing' | 'saving';

interface EditableMatterNameProps {
  /** Matter ID for the current workspace */
  matterId: string;
}

/**
 * Editable Matter Name Component
 *
 * Displays the matter name with inline editing capability.
 * - Hover shows subtle pencil icon
 * - Click activates inline input
 * - Enter or blur outside saves
 * - Escape cancels and reverts
 * - Shows loading spinner while saving
 * - Shows error toast on failure
 * - Optimistic update for responsiveness
 *
 * Story 10A.1: Workspace Shell Header - AC #2
 */
export function EditableMatterName({ matterId }: EditableMatterNameProps) {
  // Use selector pattern for Zustand (MANDATORY from project-context.md)
  const matters = useMatterStore((state) => state.matters);
  const currentMatter = useMatterStore((state) => state.currentMatter);
  const updateMatterName = useMatterStore((state) => state.updateMatterName);
  const fetchMatter = useMatterStore((state) => state.fetchMatter);

  // Find matter from either currentMatter or matters list
  const matter = currentMatter?.id === matterId ? currentMatter : matters.find((m) => m.id === matterId);

  const [editState, setEditState] = useState<EditState>('viewing');
  const [editValue, setEditValue] = useState('');
  const [isHovered, setIsHovered] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const previousNameRef = useRef<string>('');
  const isMountedRef = useRef(true);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup on unmount to prevent state updates on unmounted component
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (blurTimeoutRef.current) {
        clearTimeout(blurTimeoutRef.current);
      }
    };
  }, []);

  // Get the current name from store or use a placeholder
  const matterName = matter?.title ?? 'Untitled Matter';

  // Fetch matter data on mount if not already loaded
  useEffect(() => {
    if (!matter) {
      fetchMatter(matterId);
    }
  }, [matter, matterId, fetchMatter]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (editState === 'editing' && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editState]);

  const startEditing = useCallback(() => {
    previousNameRef.current = matterName;
    setEditValue(matterName);
    setEditState('editing');
  }, [matterName]);

  const cancelEditing = useCallback(() => {
    setEditValue(previousNameRef.current);
    setEditState('viewing');
  }, []);

  const saveName = useCallback(async () => {
    const trimmedValue = editValue.trim();

    // Validate: not empty
    if (!trimmedValue) {
      toast.error('Matter name cannot be empty');
      setEditValue(previousNameRef.current);
      setEditState('viewing');
      return;
    }

    // Validate: not too long
    if (trimmedValue.length > MAX_MATTER_NAME_LENGTH) {
      toast.error(`Matter name cannot exceed ${MAX_MATTER_NAME_LENGTH} characters`);
      return;
    }

    // No change, just exit edit mode
    if (trimmedValue === previousNameRef.current) {
      setEditState('viewing');
      return;
    }

    setEditState('saving');

    try {
      // Use store action for optimistic update and API call
      await updateMatterName(matterId, trimmedValue);

      // Only update state if component is still mounted
      if (isMountedRef.current) {
        toast.success('Matter name updated');
        previousNameRef.current = trimmedValue;
        setEditState('viewing');
      }
    } catch (error) {
      // Log error for debugging (structured logging pattern from project-context.md)
      console.error('[EditableMatterName] Failed to update matter name:', {
        matterId,
        attemptedName: trimmedValue,
        error: error instanceof Error ? error.message : 'Unknown error',
      });

      // Only update state if component is still mounted
      if (isMountedRef.current) {
        toast.error('Failed to update matter name. Please try again.');
        setEditValue(previousNameRef.current);
        setEditState('viewing');
      }
    }
  }, [editValue, matterId, updateMatterName]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        saveName();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        cancelEditing();
      }
    },
    [saveName, cancelEditing]
  );

  const handleBlur = useCallback(() => {
    // Small delay to allow button clicks to register
    // Store timeout ref for cleanup on unmount
    blurTimeoutRef.current = setTimeout(() => {
      if (isMountedRef.current && editState === 'editing') {
        saveName();
      }
    }, 100);
  }, [editState, saveName]);

  // Viewing state
  if (editState === 'viewing') {
    return (
      <div
        className="flex items-center gap-2 cursor-pointer group"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={startEditing}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            startEditing();
          }
        }}
        aria-label={`Edit matter name: ${matterName}`}
      >
        <h1 className="text-lg font-semibold truncate max-w-[300px] sm:max-w-[400px] md:max-w-[500px]">
          {matterName}
        </h1>
        <Pencil
          className={`h-4 w-4 text-muted-foreground transition-opacity ${
            isHovered ? 'opacity-100' : 'opacity-0'
          }`}
          aria-hidden="true"
        />
      </div>
    );
  }

  // Saving state
  if (editState === 'saving') {
    return (
      <div className="flex items-center gap-2" role="status" aria-live="polite">
        <span className="text-lg font-semibold truncate max-w-[300px] sm:max-w-[400px] md:max-w-[500px]">
          {editValue}
        </span>
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-label="Saving..." />
        <span className="sr-only">Saving matter name...</span>
      </div>
    );
  }

  // Editing state
  return (
    <div className="flex items-center gap-2">
      <Input
        ref={inputRef}
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        className="h-9 w-[200px] sm:w-[300px] md:w-[400px] text-lg font-semibold"
        maxLength={MAX_MATTER_NAME_LENGTH}
        aria-label="Matter name"
      />
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9 min-w-[36px]"
        onClick={saveName}
        aria-label="Save name"
      >
        <Check className="h-4 w-4 text-green-600" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9 min-w-[36px]"
        onClick={cancelEditing}
        aria-label="Cancel editing"
      >
        <X className="h-4 w-4 text-red-600" />
      </Button>
    </div>
  );
}
