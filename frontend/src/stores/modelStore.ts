/**
 * Model Preference Store
 *
 * Zustand store for A/B testing model selection (embedding + reranker providers).
 * Persisted to localStorage per session.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const embeddingProvider = useModelStore((state) => state.embeddingProvider);
 *   const setEmbeddingProvider = useModelStore((state) => state.setEmbeddingProvider);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { embeddingProvider, setEmbeddingProvider } = useModelStore();
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ============================================================================
// Types
// ============================================================================

export type EmbeddingProvider = 'openai' | 'voyage';
export type RerankProvider = 'cohere' | 'voyage';

interface ModelState {
  embeddingProvider: EmbeddingProvider;
  rerankProvider: RerankProvider;
}

interface ModelActions {
  setEmbeddingProvider: (provider: EmbeddingProvider) => void;
  setRerankProvider: (provider: RerankProvider) => void;
}

type ModelStore = ModelState & ModelActions;

// ============================================================================
// Store
// ============================================================================

export const useModelStore = create<ModelStore>()(
  persist(
    (set) => ({
      // Defaults: current production stack
      embeddingProvider: 'openai',
      rerankProvider: 'cohere',

      setEmbeddingProvider: (provider) => set({ embeddingProvider: provider }),
      setRerankProvider: (provider) => set({ rerankProvider: provider }),
    }),
    {
      name: 'ldip-model-preferences',
    }
  )
);
