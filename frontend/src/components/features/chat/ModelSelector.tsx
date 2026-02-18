'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useModelStore, type EmbeddingProvider, type RerankProvider } from '@/stores/modelStore';

/**
 * ModelSelector - Two compact dropdowns for embedding and reranker A/B testing.
 *
 * Kill switch: Returns null when VOYAGE_AB_TESTING_ENABLED is false (checked
 * via the abTestingEnabled prop from the parent, which reads it from the
 * backend config or feature flag).
 *
 * For now, visibility is controlled by the `visible` prop. The backend
 * kill switch (`voyage_ab_testing_enabled`) ensures API always ignores
 * provider params when disabled.
 */

interface ModelSelectorProps {
  /** Set to false to hide the selector entirely (kill switch) */
  visible?: boolean;
}

export function ModelSelector({ visible = true }: ModelSelectorProps) {
  const embeddingProvider = useModelStore((state) => state.embeddingProvider);
  const rerankProvider = useModelStore((state) => state.rerankProvider);
  const setEmbeddingProvider = useModelStore((state) => state.setEmbeddingProvider);
  const setRerankProvider = useModelStore((state) => state.setRerankProvider);

  if (!visible) return null;

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 border-b bg-muted/30">
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-medium text-muted-foreground">Embedding</span>
        <Select
          value={embeddingProvider}
          onValueChange={(v) => setEmbeddingProvider(v as EmbeddingProvider)}
        >
          <SelectTrigger className="h-7 text-xs min-w-[120px]" size="sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="openai">OpenAI Small</SelectItem>
            <SelectItem value="voyage">Voyage Law-2</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-medium text-muted-foreground">Rerank</span>
        <Select
          value={rerankProvider}
          onValueChange={(v) => setRerankProvider(v as RerankProvider)}
        >
          <SelectTrigger className="h-7 text-xs min-w-[110px]" size="sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="cohere">Cohere v3.5</SelectItem>
            <SelectItem value="voyage">Voyage 2.5</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
