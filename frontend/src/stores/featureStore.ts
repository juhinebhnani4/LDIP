/**
 * Feature Availability Store
 *
 * Tracks which document features are ready for use as processing completes.
 * Enables progressive UI - show features as they become available rather than
 * waiting for full pipeline completion.
 *
 * Features:
 * - search: Basic text search (after chunking)
 * - semantic_search: Vector search (after embedding)
 * - entities: Entity search and timeline (after entity extraction)
 * - timeline: Timeline view (after date extraction)
 * - citations: Citation lookup (after citation extraction)
 * - bbox_highlighting: Click-to-highlight in PDF (after bbox linking)
 */

import { create } from 'zustand';

// Feature types matching backend FeatureType enum
export type FeatureType =
  | 'search'
  | 'semantic_search'
  | 'entities'
  | 'timeline'
  | 'citations'
  | 'bbox_highlighting';

export interface DocumentFeatures {
  search: boolean;
  semantic_search: boolean;
  entities: boolean;
  timeline: boolean;
  citations: boolean;
  bbox_highlighting: boolean;
  // Metadata for features (counts, etc.)
  metadata?: {
    chunk_count?: number;
    embedded_count?: number;
    entities_count?: number;
    citations_count?: number;
    unique_acts?: number;
    linked_count?: number;
  };
}

// Default features - all disabled
const DEFAULT_FEATURES: DocumentFeatures = {
  search: false,
  semantic_search: false,
  entities: false,
  timeline: false,
  citations: false,
  bbox_highlighting: false,
  metadata: {},
};

interface FeatureState {
  // Map of document_id -> features
  documents: Map<string, DocumentFeatures>;

  // Actions
  setFeatureReady: (
    documentId: string,
    feature: FeatureType,
    metadata?: Record<string, unknown>
  ) => void;
  setFeaturesBatch: (
    documentId: string,
    features: Partial<Record<FeatureType, boolean>>
  ) => void;
  getFeatures: (documentId: string) => DocumentFeatures;
  isFeatureReady: (documentId: string, feature: FeatureType) => boolean;
  clearDocument: (documentId: string) => void;
  clearAll: () => void;

  // Real-time event handlers
  handleFeatureReadyEvent: (event: FeatureReadyEvent) => void;
  handleFeaturesUpdateEvent: (event: FeaturesUpdateEvent) => void;
}

// Event types from backend broadcasts
export interface FeatureReadyEvent {
  event: 'feature_ready';
  matter_id: string;
  document_id: string;
  feature: FeatureType;
  ready: boolean;
  metadata?: Record<string, unknown>;
}

export interface FeaturesUpdateEvent {
  event: 'features_update';
  matter_id: string;
  document_id: string;
  features: Partial<Record<FeatureType, boolean>>;
}

export const useFeatureStore = create<FeatureState>((set, get) => ({
  documents: new Map(),

  setFeatureReady: (documentId, feature, metadata) => {
    set((state) => {
      const newMap = new Map(state.documents);
      const current = newMap.get(documentId) || { ...DEFAULT_FEATURES };

      newMap.set(documentId, {
        ...current,
        [feature]: true,
        metadata: {
          ...current.metadata,
          ...metadata,
        },
      });

      return { documents: newMap };
    });
  },

  setFeaturesBatch: (documentId, features) => {
    set((state) => {
      const newMap = new Map(state.documents);
      const current = newMap.get(documentId) || { ...DEFAULT_FEATURES };

      newMap.set(documentId, {
        ...current,
        ...features,
      });

      return { documents: newMap };
    });
  },

  getFeatures: (documentId) => {
    return get().documents.get(documentId) || { ...DEFAULT_FEATURES };
  },

  isFeatureReady: (documentId, feature) => {
    const features = get().documents.get(documentId);
    return features ? features[feature] : false;
  },

  clearDocument: (documentId) => {
    set((state) => {
      const newMap = new Map(state.documents);
      newMap.delete(documentId);
      return { documents: newMap };
    });
  },

  clearAll: () => {
    set({ documents: new Map() });
  },

  // Handle real-time feature_ready events
  handleFeatureReadyEvent: (event) => {
    if (event.ready) {
      get().setFeatureReady(
        event.document_id,
        event.feature,
        event.metadata as Record<string, unknown>
      );
    }
  },

  // Handle real-time features_update batch events
  handleFeaturesUpdateEvent: (event) => {
    get().setFeaturesBatch(event.document_id, event.features);
  },
}));

// Selectors for optimized re-renders
export const selectDocumentFeatures = (documentId: string) => (state: FeatureState) =>
  state.documents.get(documentId) || DEFAULT_FEATURES;

export const selectIsSearchReady = (documentId: string) => (state: FeatureState) =>
  state.documents.get(documentId)?.search || false;

export const selectIsSemanticSearchReady = (documentId: string) => (state: FeatureState) =>
  state.documents.get(documentId)?.semantic_search || false;

export const selectIsEntitiesReady = (documentId: string) => (state: FeatureState) =>
  state.documents.get(documentId)?.entities || false;

export const selectIsCitationsReady = (documentId: string) => (state: FeatureState) =>
  state.documents.get(documentId)?.citations || false;

export const selectIsBboxReady = (documentId: string) => (state: FeatureState) =>
  state.documents.get(documentId)?.bbox_highlighting || false;
