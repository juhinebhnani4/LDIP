/**
 * Export Builder Hook
 *
 * Manages state for the Export Builder modal.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { useState, useCallback, useMemo } from 'react';
import { arrayMove } from '@dnd-kit/sortable';
import {
  DEFAULT_EXPORT_SECTIONS,
  type ExportFormat,
  type ExportSection,
  type ExportSectionId,
  type ExportSectionEdit,
  type ExportPreviewMode,
} from '@/types/export';

export interface UseExportBuilderOptions {
  /** Initial export format */
  initialFormat?: ExportFormat;
  /** Initial sections configuration */
  initialSections?: ExportSection[];
}

export interface UseExportBuilderReturn {
  /** Ordered list of sections */
  sections: ExportSection[];
  /** Currently selected format */
  format: ExportFormat;
  /** Toggle section enabled state */
  toggleSection: (sectionId: ExportSectionId) => void;
  /** Set section enabled state explicitly */
  setSectionEnabled: (sectionId: ExportSectionId, enabled: boolean) => void;
  /** Reorder sections after drag */
  reorderSections: (activeId: string, overId: string) => void;
  /** Select all sections */
  selectAll: () => void;
  /** Deselect all sections */
  deselectAll: () => void;
  /** Update section count */
  updateSectionCount: (sectionId: ExportSectionId, count: number) => void;
  /** Set loading state for a section */
  setSectionLoading: (sectionId: ExportSectionId, loading: boolean) => void;
  /** Number of selected sections */
  selectedCount: number;
  /** Check if at least one section is selected */
  hasSelection: boolean;
  /** Get IDs of selected sections in order */
  selectedSectionIds: ExportSectionId[];
  /** Reset to default state */
  reset: () => void;

  // Story 12.2 - Edit state management
  /** Current preview mode (sections list vs preview) */
  previewMode: ExportPreviewMode;
  /** Set preview mode */
  setPreviewMode: (mode: ExportPreviewMode) => void;
  /** Map of section edits keyed by section ID */
  sectionEdits: Map<ExportSectionId, ExportSectionEdit>;
  /** Update text content edit for a section */
  updateSectionEdit: (sectionId: ExportSectionId, textContent: string) => void;
  /** Remove an item from a section (for list sections) */
  removeSectionItem: (sectionId: ExportSectionId, itemId: string) => void;
  /** Restore a removed item to a section */
  restoreSectionItem: (sectionId: ExportSectionId, itemId: string) => void;
  /** Add a note to a section */
  addSectionNote: (sectionId: ExportSectionId, note: string) => void;
  /** Remove a note from a section */
  removeSectionNote: (sectionId: ExportSectionId, noteIndex: number) => void;
  /** Reset all edits */
  resetSectionEdits: () => void;
  /** Check if there are any unsaved edits */
  hasEdits: boolean;
  /** Section currently being edited inline */
  editingSection: ExportSectionId | null;
  /** Set the section currently being edited */
  setEditingSection: (sectionId: ExportSectionId | null) => void;
}

/**
 * Create default sections with runtime properties
 */
function createDefaultSections(): ExportSection[] {
  return DEFAULT_EXPORT_SECTIONS.map((s) => ({
    ...s,
    count: undefined,
    isLoadingCount: false,
  }));
}

/**
 * Create a default edit object for a section
 */
function createDefaultEdit(sectionId: ExportSectionId): ExportSectionEdit {
  return {
    sectionId,
    textContent: undefined,
    removedItemIds: [],
    addedNotes: [],
  };
}

/**
 * Hook for managing Export Builder state
 *
 * @param options - Optional initial configuration
 * @returns Export builder state and actions
 *
 * @example
 * ```tsx
 * const {
 *   sections,
 *   toggleSection,
 *   reorderSections,
 *   hasSelection,
 *   // Story 12.2 additions
 *   previewMode,
 *   setPreviewMode,
 *   sectionEdits,
 *   updateSectionEdit,
 *   hasEdits,
 * } = useExportBuilder({ initialFormat: 'pdf' });
 * ```
 */
export function useExportBuilder(
  options: UseExportBuilderOptions = {}
): UseExportBuilderReturn {
  const { initialFormat = 'pdf', initialSections } = options;

  const [sections, setSections] = useState<ExportSection[]>(
    () => initialSections ?? createDefaultSections()
  );
  const [format] = useState<ExportFormat>(initialFormat);

  // Story 12.2 - Edit state
  const [previewMode, setPreviewMode] = useState<ExportPreviewMode>('sections');
  const [sectionEdits, setSectionEdits] = useState<Map<ExportSectionId, ExportSectionEdit>>(
    () => new Map()
  );
  const [editingSection, setEditingSection] = useState<ExportSectionId | null>(null);

  const toggleSection = useCallback((sectionId: ExportSectionId) => {
    setSections((prev) =>
      prev.map((section) =>
        section.id === sectionId
          ? { ...section, enabled: !section.enabled }
          : section
      )
    );
  }, []);

  const setSectionEnabled = useCallback(
    (sectionId: ExportSectionId, enabled: boolean) => {
      setSections((prev) =>
        prev.map((section) =>
          section.id === sectionId ? { ...section, enabled } : section
        )
      );
    },
    []
  );

  const reorderSections = useCallback((activeId: string, overId: string) => {
    setSections((prev) => {
      const oldIndex = prev.findIndex((s) => s.id === activeId);
      const newIndex = prev.findIndex((s) => s.id === overId);
      if (oldIndex === -1 || newIndex === -1) return prev;
      return arrayMove(prev, oldIndex, newIndex);
    });
  }, []);

  const selectAll = useCallback(() => {
    setSections((prev) => prev.map((section) => ({ ...section, enabled: true })));
  }, []);

  const deselectAll = useCallback(() => {
    setSections((prev) => prev.map((section) => ({ ...section, enabled: false })));
  }, []);

  const updateSectionCount = useCallback(
    (sectionId: ExportSectionId, count: number) => {
      setSections((prev) =>
        prev.map((section) =>
          section.id === sectionId
            ? { ...section, count, isLoadingCount: false }
            : section
        )
      );
    },
    []
  );

  const setSectionLoading = useCallback(
    (sectionId: ExportSectionId, loading: boolean) => {
      setSections((prev) =>
        prev.map((section) =>
          section.id === sectionId
            ? { ...section, isLoadingCount: loading }
            : section
        )
      );
    },
    []
  );

  const selectedCount = useMemo(
    () => sections.filter((s) => s.enabled).length,
    [sections]
  );

  const hasSelection = selectedCount > 0;

  const selectedSectionIds = useMemo(
    () => sections.filter((s) => s.enabled).map((s) => s.id),
    [sections]
  );

  // Story 12.2 - Edit functions
  const updateSectionEdit = useCallback(
    (sectionId: ExportSectionId, textContent: string) => {
      setSectionEdits((prev) => {
        const newMap = new Map(prev);
        const existing = newMap.get(sectionId) ?? createDefaultEdit(sectionId);
        newMap.set(sectionId, { ...existing, textContent });
        return newMap;
      });
    },
    []
  );

  const removeSectionItem = useCallback(
    (sectionId: ExportSectionId, itemId: string) => {
      setSectionEdits((prev) => {
        const newMap = new Map(prev);
        const existing = newMap.get(sectionId) ?? createDefaultEdit(sectionId);
        if (!existing.removedItemIds.includes(itemId)) {
          newMap.set(sectionId, {
            ...existing,
            removedItemIds: [...existing.removedItemIds, itemId],
          });
        }
        return newMap;
      });
    },
    []
  );

  const restoreSectionItem = useCallback(
    (sectionId: ExportSectionId, itemId: string) => {
      setSectionEdits((prev) => {
        const newMap = new Map(prev);
        const existing = newMap.get(sectionId);
        if (existing) {
          newMap.set(sectionId, {
            ...existing,
            removedItemIds: existing.removedItemIds.filter((id) => id !== itemId),
          });
        }
        return newMap;
      });
    },
    []
  );

  const addSectionNote = useCallback(
    (sectionId: ExportSectionId, note: string) => {
      setSectionEdits((prev) => {
        const newMap = new Map(prev);
        const existing = newMap.get(sectionId) ?? createDefaultEdit(sectionId);
        newMap.set(sectionId, {
          ...existing,
          addedNotes: [...existing.addedNotes, note],
        });
        return newMap;
      });
    },
    []
  );

  const removeSectionNote = useCallback(
    (sectionId: ExportSectionId, noteIndex: number) => {
      setSectionEdits((prev) => {
        const newMap = new Map(prev);
        const existing = newMap.get(sectionId);
        if (existing) {
          newMap.set(sectionId, {
            ...existing,
            addedNotes: existing.addedNotes.filter((_, i) => i !== noteIndex),
          });
        }
        return newMap;
      });
    },
    []
  );

  const resetSectionEdits = useCallback(() => {
    setSectionEdits(new Map());
    setEditingSection(null);
  }, []);

  const hasEdits = useMemo(() => {
    for (const edit of sectionEdits.values()) {
      if (edit.textContent !== undefined) return true;
      if (edit.removedItemIds.length > 0) return true;
      if (edit.addedNotes.length > 0) return true;
    }
    return false;
  }, [sectionEdits]);

  const reset = useCallback(() => {
    setSections(createDefaultSections());
    setSectionEdits(new Map());
    setEditingSection(null);
    setPreviewMode('sections');
  }, []);

  return {
    sections,
    format,
    toggleSection,
    setSectionEnabled,
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
  };
}
