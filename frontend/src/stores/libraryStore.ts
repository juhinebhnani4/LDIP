/**
 * Library Store
 *
 * Zustand store for managing shared legal library state.
 * Phase 2: Shared Legal Library feature.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const documents = useLibraryStore((state) => state.documents);
 *   const linkedDocuments = useLibraryStore((state) => state.linkedDocuments);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { documents, linkedDocuments } = useLibraryStore();
 */

import { create } from 'zustand';
import type {
  LibraryDocumentListItem,
  LibraryDocumentType,
  LibraryDocumentStatus,
  LibraryPaginationMeta,
} from '@/types/library';
import {
  getLibraryDocuments,
  getLinkedLibraryDocuments,
  linkLibraryDocument,
  unlinkLibraryDocument,
} from '@/lib/api/library';

// =============================================================================
// Store Types
// =============================================================================

/** Filter options for library list */
interface LibraryFilters {
  documentType: LibraryDocumentType | null;
  year: number | null;
  jurisdiction: string | null;
  status: LibraryDocumentStatus | null;
  search: string;
}

interface LibraryState {
  /** All library documents (global list) */
  documents: LibraryDocumentListItem[];

  /** Pagination metadata for global list */
  pagination: LibraryPaginationMeta | null;

  /** Library documents linked to current matter */
  linkedDocuments: LibraryDocumentListItem[];

  /** Current matter ID for linked documents context */
  matterId: string | null;

  /** Current filter state */
  filters: LibraryFilters;

  /** Current page number */
  currentPage: number;

  /** Loading state for global list */
  isLoading: boolean;

  /** Loading state for linked documents */
  isLoadingLinked: boolean;

  /** Error message if any operation failed */
  error: string | null;

  /** Whether the library browser modal is open */
  isBrowserOpen: boolean;
}

interface LibraryActions {
  /** Set current matter ID */
  setMatterId: (matterId: string | null) => void;

  /** Load library documents with current filters */
  loadDocuments: (page?: number) => Promise<void>;

  /** Load linked documents for current matter */
  loadLinkedDocuments: (matterId: string) => Promise<void>;

  /** Update filter state */
  setFilters: (filters: Partial<LibraryFilters>) => void;

  /** Reset filters to defaults */
  resetFilters: () => void;

  /** Link a document to the current matter */
  linkDocument: (documentId: string) => Promise<boolean>;

  /** Unlink a document from the current matter */
  unlinkDocument: (documentId: string) => Promise<boolean>;

  /** Open library browser modal */
  openBrowser: () => void;

  /** Close library browser modal */
  closeBrowser: () => void;

  /** Set loading state */
  setLoading: (isLoading: boolean) => void;

  /** Set error state */
  setError: (error: string | null) => void;

  /** Reset all state */
  reset: () => void;
}

type LibraryStore = LibraryState & LibraryActions;

// =============================================================================
// Initial State
// =============================================================================

const DEFAULT_FILTERS: LibraryFilters = {
  documentType: null,
  year: null,
  jurisdiction: null,
  status: null,
  search: '',
};

const initialState: LibraryState = {
  documents: [],
  pagination: null,
  linkedDocuments: [],
  matterId: null,
  filters: { ...DEFAULT_FILTERS },
  currentPage: 1,
  isLoading: false,
  isLoadingLinked: false,
  error: null,
  isBrowserOpen: false,
};

// =============================================================================
// Store
// =============================================================================

export const useLibraryStore = create<LibraryStore>((set, get) => ({
  ...initialState,

  setMatterId: (matterId) => {
    const currentMatterId = get().matterId;

    // Clear linked documents when switching matters
    if (currentMatterId !== matterId) {
      set({
        matterId,
        linkedDocuments: [],
        error: null,
      });
    } else {
      set({ matterId });
    }
  },

  loadDocuments: async (page = 1) => {
    const { filters, matterId } = get();

    set({ isLoading: true, error: null, currentPage: page });

    try {
      const response = await getLibraryDocuments({
        documentType: filters.documentType ?? undefined,
        year: filters.year ?? undefined,
        jurisdiction: filters.jurisdiction ?? undefined,
        status: filters.status ?? undefined,
        search: filters.search || undefined,
        page,
        perPage: 20,
      });

      // Mark documents as linked if we have a matter context
      let documents = response.documents;
      if (matterId) {
        const linkedIds = new Set(get().linkedDocuments.map((d) => d.id));
        documents = documents.map((doc) => ({
          ...doc,
          isLinked: linkedIds.has(doc.id),
        }));
      }

      set({
        documents,
        pagination: response.pagination,
        isLoading: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load library documents';
      set({
        error: message,
        isLoading: false,
      });
    }
  },

  loadLinkedDocuments: async (matterId) => {
    set({ isLoadingLinked: true, error: null, matterId });

    try {
      const response = await getLinkedLibraryDocuments(matterId);

      set({
        linkedDocuments: response.documents,
        isLoadingLinked: false,
      });

      // Update isLinked status in main documents list if loaded
      const { documents } = get();
      if (documents.length > 0) {
        const linkedIds = new Set(response.documents.map((d) => d.id));
        set({
          documents: documents.map((doc) => ({
            ...doc,
            isLinked: linkedIds.has(doc.id),
          })),
        });
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to load linked library documents';
      set({
        error: message,
        isLoadingLinked: false,
      });
    }
  },

  setFilters: (newFilters) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      currentPage: 1, // Reset to first page on filter change
    }));
  },

  resetFilters: () => {
    set({
      filters: { ...DEFAULT_FILTERS },
      currentPage: 1,
    });
  },

  linkDocument: async (documentId) => {
    const { matterId, documents, linkedDocuments } = get();

    if (!matterId) {
      set({ error: 'No matter selected' });
      return false;
    }

    try {
      const response = await linkLibraryDocument(matterId, {
        libraryDocumentId: documentId,
      });

      if (response.success) {
        // Find the document to add to linked list
        const docToLink = documents.find((d) => d.id === documentId);

        if (docToLink) {
          // Update linked documents list
          set({
            linkedDocuments: [
              ...linkedDocuments,
              {
                ...docToLink,
                isLinked: true,
                linkedAt: response.link.linkedAt,
              },
            ],
          });
        }

        // Update isLinked in main documents list
        set({
          documents: documents.map((doc) =>
            doc.id === documentId
              ? { ...doc, isLinked: true, linkedAt: response.link.linkedAt }
              : doc
          ),
        });

        return true;
      }

      return false;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to link document';
      set({ error: message });
      return false;
    }
  },

  unlinkDocument: async (documentId) => {
    const { matterId, documents, linkedDocuments } = get();

    if (!matterId) {
      set({ error: 'No matter selected' });
      return false;
    }

    try {
      const response = await unlinkLibraryDocument(matterId, documentId);

      if (response.success) {
        // Remove from linked documents list
        set({
          linkedDocuments: linkedDocuments.filter((d) => d.id !== documentId),
        });

        // Update isLinked in main documents list
        set({
          documents: documents.map((doc) =>
            doc.id === documentId ? { ...doc, isLinked: false, linkedAt: null } : doc
          ),
        });

        return true;
      }

      return false;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to unlink document';
      set({ error: message });
      return false;
    }
  },

  openBrowser: () => {
    set({ isBrowserOpen: true });
  },

  closeBrowser: () => {
    set({ isBrowserOpen: false });
  },

  setLoading: (isLoading) => {
    set({ isLoading });
  },

  setError: (error) => {
    set({ error });
  },

  reset: () => {
    set(initialState);
  },
}));

// =============================================================================
// Selectors
// =============================================================================

/**
 * Selector for getting linked document count
 */
export const selectLinkedCount = (state: LibraryStore): number => state.linkedDocuments.length;

/**
 * Selector for checking if a document is linked
 */
export const selectIsDocumentLinked =
  (documentId: string) =>
  (state: LibraryStore): boolean =>
    state.linkedDocuments.some((d) => d.id === documentId);

/**
 * Selector for getting documents filtered by type
 */
export const selectDocumentsByType =
  (type: LibraryDocumentType) =>
  (state: LibraryStore): LibraryDocumentListItem[] =>
    state.documents.filter((d) => d.documentType === type);

/**
 * Selector for checking if library is empty
 */
export const selectIsEmpty = (state: LibraryStore): boolean =>
  state.documents.length === 0 && !state.isLoading;

/**
 * Selector for checking if linked library is empty
 */
export const selectIsLinkedEmpty = (state: LibraryStore): boolean =>
  state.linkedDocuments.length === 0 && !state.isLoadingLinked;
