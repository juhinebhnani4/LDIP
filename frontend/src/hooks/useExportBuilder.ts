/**
 * Export Builder Hook
 *
 * Manages state for the Export Builder modal.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection
 */

import { useState, useCallback, useMemo } from 'react';
import { arrayMove } from '@dnd-kit/sortable';
import {
  DEFAULT_EXPORT_SECTIONS,
  type ExportFormat,
  type ExportSection,
  type ExportSectionId,
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

  const reset = useCallback(() => {
    setSections(createDefaultSections());
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
  };
}
