/**
 * useEntities Hook
 *
 * SWR-based hook for fetching and caching entity data.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import useSWR from 'swr';
import useSWRImmutable from 'swr/immutable';
import {
  getEntities,
  getEntity,
  getEntityMentions,
} from '@/lib/api/entities';
import type {
  EntitiesListResponse,
  EntityListOptions,
  EntityResponse,
  EntityMentionsResponse,
  EntityType,
  EntityWithRelations,
  EntityListItem,
  EntityEdge,
} from '@/types/entity';

export interface UseEntitiesOptions extends EntityListOptions {
  enabled?: boolean;
}

export interface UseEntitiesReturn {
  entities: EntityListItem[];
  total: number;
  isLoading: boolean;
  isValidating: boolean;
  error: Error | null;
  mutate: () => void;
}

/**
 * Fetch paginated entities for a matter.
 */
export function useEntities(
  matterId: string | null,
  options: UseEntitiesOptions = {}
): UseEntitiesReturn {
  const { enabled = true, entityType, page = 1, perPage = 100 } = options;

  const { data, error, isLoading, isValidating, mutate } = useSWR<EntitiesListResponse>(
    enabled && matterId
      ? ['entities', matterId, entityType, page, perPage]
      : null,
    () =>
      getEntities(matterId!, {
        entityType,
        page,
        perPage,
      }),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds
    }
  );

  return {
    entities: data?.data ?? [],
    total: data?.meta.total ?? 0,
    isLoading,
    isValidating,
    error: error ?? null,
    mutate,
  };
}

export interface UseEntityDetailReturn {
  entity: EntityWithRelations | null;
  isLoading: boolean;
  error: Error | null;
  mutate: () => void;
}

/**
 * Fetch single entity with relationships and mentions.
 */
export function useEntityDetail(
  matterId: string | null,
  entityId: string | null
): UseEntityDetailReturn {
  const { data, error, isLoading, mutate } = useSWR<EntityResponse>(
    matterId && entityId ? ['entity', matterId, entityId] : null,
    () => getEntity(matterId!, entityId!),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    entity: data?.data ?? null,
    isLoading,
    error: error ?? null,
    mutate,
  };
}

export interface UseEntityMentionsOptions {
  page?: number;
  perPage?: number;
  enabled?: boolean;
}

export interface UseEntityMentionsReturn {
  mentions: EntityMentionsResponse['data'];
  total: number;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Fetch paginated mentions for an entity.
 */
export function useEntityMentions(
  matterId: string | null,
  entityId: string | null,
  options: UseEntityMentionsOptions = {}
): UseEntityMentionsReturn {
  const { page = 1, perPage = 20, enabled = true } = options;

  const { data, error, isLoading } = useSWR<EntityMentionsResponse>(
    enabled && matterId && entityId
      ? ['entityMentions', matterId, entityId, page, perPage]
      : null,
    () => getEntityMentions(matterId!, entityId!, { page, perPage }),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    mentions: data?.data ?? [],
    total: data?.meta.total ?? 0,
    isLoading,
    error: error ?? null,
  };
}

/**
 * Fetch all entity relationships for graph visualization.
 * Returns edges for all entities in a matter.
 *
 * TODO: Optimize with dedicated bulk endpoint (e.g., GET /matters/:id/relationships)
 * to avoid N+1 queries. Current implementation fetches each entity individually.
 */
export function useEntityRelationships(
  matterId: string | null,
  entities: EntityListItem[]
): {
  edges: EntityEdge[];
  isLoading: boolean;
  error: Error | null;
} {
  const { data, error, isLoading } = useSWRImmutable<EntityEdge[]>(
    matterId && entities.length > 0
      ? ['entityRelationships', matterId, entities.map((e) => e.id).join(',')]
      : null,
    async () => {
      // Fetch relationships for each entity and deduplicate
      const edgeMap = new Map<string, EntityEdge>();

      // Fetch in batches - larger batch size (20) to reduce sequential waits
      // TODO: Replace with bulk endpoint when available
      const batchSize = 20;
      for (let i = 0; i < entities.length; i += batchSize) {
        const batch = entities.slice(i, i + batchSize);
        const results = await Promise.all(
          batch.map((entity) => getEntity(matterId!, entity.id))
        );

        for (const result of results) {
          for (const edge of result.data.relationships) {
            if (!edgeMap.has(edge.id)) {
              edgeMap.set(edge.id, edge);
            }
          }
        }
      }

      return Array.from(edgeMap.values());
    },
    {
      revalidateOnFocus: false,
    }
  );

  return {
    edges: data ?? [],
    isLoading,
    error: error ?? null,
  };
}

/**
 * Get entity statistics by type.
 */
export function useEntityStats(entities: EntityListItem[]): {
  total: number;
  byType: Record<EntityType, number>;
} {
  const byType: Record<EntityType, number> = {
    PERSON: 0,
    ORG: 0,
    INSTITUTION: 0,
    ASSET: 0,
  };

  for (const entity of entities) {
    byType[entity.entityType]++;
  }

  return {
    total: entities.length,
    byType,
  };
}

// =============================================================================
// Entity Mutation Hooks (Story 10C.2)
// =============================================================================

import { useCallback, useState } from 'react';
import { useSWRConfig } from 'swr';
import {
  mergeEntities as mergeEntitiesApi,
  addAlias as addAliasApi,
  removeAlias as removeAliasApi,
} from '@/lib/api/entities';
import type {
  MergeEntitiesRequest,
  MergeResultResponse,
  AliasesListResponse,
} from '@/types/entity';

export interface UseEntityMergeReturn {
  merge: (request: MergeEntitiesRequest) => Promise<MergeResultResponse>;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook for merging two entities.
 * Invalidates entity caches after successful merge.
 */
export function useEntityMerge(matterId: string | null): UseEntityMergeReturn {
  const { mutate } = useSWRConfig();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const merge = useCallback(
    async (request: MergeEntitiesRequest): Promise<MergeResultResponse> => {
      if (!matterId) {
        throw new Error('Matter ID is required');
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await mergeEntitiesApi(matterId, request);

        // Invalidate all entity-related caches for this matter
        await mutate(
          (key: unknown) =>
            Array.isArray(key) &&
            (key[0] === 'entities' || key[0] === 'entity' || key[0] === 'entityRelationships') &&
            key[1] === matterId,
          undefined,
          { revalidate: true }
        );

        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to merge entities');
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, mutate]
  );

  return { merge, isLoading, error };
}

export interface UseEntityAliasReturn {
  addAlias: (entityId: string, alias: string) => Promise<AliasesListResponse>;
  removeAlias: (entityId: string, alias: string) => Promise<AliasesListResponse>;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook for managing entity aliases.
 * Invalidates entity caches after successful alias operations.
 */
export function useEntityAlias(matterId: string | null): UseEntityAliasReturn {
  const { mutate } = useSWRConfig();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const addAlias = useCallback(
    async (entityId: string, alias: string): Promise<AliasesListResponse> => {
      if (!matterId) {
        throw new Error('Matter ID is required');
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await addAliasApi(matterId, entityId, alias);

        // Invalidate entity detail cache
        await mutate(['entity', matterId, entityId]);

        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to add alias');
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, mutate]
  );

  const removeAlias = useCallback(
    async (entityId: string, alias: string): Promise<AliasesListResponse> => {
      if (!matterId) {
        throw new Error('Matter ID is required');
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await removeAliasApi(matterId, entityId, alias);

        // Invalidate entity detail cache
        await mutate(['entity', matterId, entityId]);

        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to remove alias');
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, mutate]
  );

  return { addAlias, removeAlias, isLoading, error };
}


// =============================================================================
// Merge Suggestions Hook (Lawyer UX - Entity Auto-Merge)
// =============================================================================

import { getMergeSuggestions, MergeSuggestionsOptions } from '@/lib/api/entities';
import type { MergeSuggestionsResponse, MergeSuggestionItem } from '@/types/entity';

export interface UseMergeSuggestionsOptions extends MergeSuggestionsOptions {
  enabled?: boolean;
}

export interface UseMergeSuggestionsReturn {
  suggestions: MergeSuggestionItem[];
  total: number;
  isLoading: boolean;
  error: Error | null;
  mutate: () => void;
}

/**
 * Hook for fetching merge suggestions (potential duplicate entities).
 *
 * @example
 * ```tsx
 * const { suggestions, isLoading } = useMergeSuggestions(matterId, {
 *   minSimilarity: 0.7,
 *   limit: 10,
 * });
 *
 * if (suggestions.length > 0) {
 *   return <MergeSuggestionsBanner suggestions={suggestions} />;
 * }
 * ```
 */
export function useMergeSuggestions(
  matterId: string | null,
  options: UseMergeSuggestionsOptions = {}
): UseMergeSuggestionsReturn {
  const { enabled = true, entityType, minSimilarity, limit } = options;

  const { data, error, isLoading, mutate } = useSWR<MergeSuggestionsResponse>(
    enabled && matterId
      ? ['mergeSuggestions', matterId, entityType, minSimilarity, limit]
      : null,
    () =>
      getMergeSuggestions(matterId!, {
        entityType,
        minSimilarity,
        limit,
      }),
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000, // 1 minute - suggestions don't change often
    }
  );

  return {
    suggestions: data?.data ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error ?? null,
    mutate,
  };
}
