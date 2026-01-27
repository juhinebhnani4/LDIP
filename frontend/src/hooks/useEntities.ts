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
  // Default to 50 items for comprehensive entity mentions view
  const { page = 1, perPage = 50, enabled = true } = options;

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
 * OPTIMIZED: Uses bulk endpoint (GET /matters/:id/entities/relationships)
 * to fetch all relationships in a single API call instead of N+1 queries.
 *
 * LATENCY FIX: Removed dependency on entities array to enable parallel loading.
 * Previously waited for entities to load first (sequential waterfall).
 */
export function useEntityRelationships(
  matterId: string | null
): {
  edges: EntityEdge[];
  isLoading: boolean;
  error: Error | null;
} {
  const { data, error, isLoading } = useSWRImmutable<EntityEdge[]>(
    matterId
      ? ['entityRelationships', matterId]
      : null,
    async () => {
      // OPTIMIZATION: Single bulk API call instead of N+1 queries
      const { getBulkRelationships } = await import('@/lib/api/entities');
      const response = await getBulkRelationships(matterId!);

      // Convert bulk response format to EntityEdge format
      return response.data.map((edge) => ({
        id: edge.id,
        matterId: matterId!,
        sourceEntityId: edge.sourceEntityId,
        targetEntityId: edge.targetEntityId,
        relationshipType: edge.relationshipType as EntityEdge['relationshipType'],
        confidence: 1.0, // Bulk endpoint doesn't return confidence, default to 1.0
        metadata: {},
        createdAt: new Date().toISOString(),
        sourceEntityName: edge.sourceEntityName ?? undefined,
        targetEntityName: edge.targetEntityName ?? undefined,
      }));
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 second deduping
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
  unmergeEntity as unmergeEntityApi,
  getMergedEntities,
} from '@/lib/api/entities';
import type {
  MergeEntitiesRequest,
  MergeResultResponse,
  AliasesListResponse,
  UnmergeResultResponse,
  MergedEntitiesResponse,
  MergedEntityItem,
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

        // Invalidate all entity-related caches for this matter (including merge suggestions)
        await mutate(
          (key: unknown) =>
            Array.isArray(key) &&
            (key[0] === 'entities' ||
              key[0] === 'entity' ||
              key[0] === 'entityRelationships' ||
              key[0] === 'mergeSuggestions') &&
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


// =============================================================================
// Story 3.4: Merged Entities Hook (for Unmerge/Split UI)
// =============================================================================

export interface UseMergedEntitiesOptions {
  enabled?: boolean;
}

export interface UseMergedEntitiesReturn {
  mergedEntities: MergedEntityItem[];
  total: number;
  isLoading: boolean;
  error: Error | null;
  mutate: () => void;
}

/**
 * Hook for fetching entities that were merged into a specific entity.
 *
 * Story 3.4: Used to display "Merged From" section in entity detail panel,
 * allowing users to unmerge (split) previously merged entities.
 *
 * @example
 * ```tsx
 * const { mergedEntities, isLoading } = useMergedEntities(matterId, entityId);
 *
 * if (mergedEntities.length > 0) {
 *   return <MergedEntitiesSection entities={mergedEntities} onUnmerge={handleUnmerge} />;
 * }
 * ```
 */
export function useMergedEntities(
  matterId: string | null,
  entityId: string | null,
  options: UseMergedEntitiesOptions = {}
): UseMergedEntitiesReturn {
  const { enabled = true } = options;

  const { data, error, isLoading, mutate } = useSWR<MergedEntitiesResponse>(
    enabled && matterId && entityId
      ? ['mergedEntities', matterId, entityId]
      : null,
    () => getMergedEntities(matterId!, entityId!),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    mergedEntities: data?.data ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error ?? null,
    mutate,
  };
}


// =============================================================================
// Story 3.4: Entity Unmerge Hook
// =============================================================================

export interface UseEntityUnmergeReturn {
  unmerge: (entityId: string) => Promise<UnmergeResultResponse>;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook for unmerging (splitting) a previously merged entity.
 *
 * Story 3.4: Reverses a soft merge operation, restoring the entity
 * to active status.
 */
export function useEntityUnmerge(matterId: string | null): UseEntityUnmergeReturn {
  const { mutate } = useSWRConfig();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const unmerge = useCallback(
    async (entityId: string): Promise<UnmergeResultResponse> => {
      if (!matterId) {
        throw new Error('Matter ID is required');
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await unmergeEntityApi(matterId, entityId);

        // Invalidate all entity-related caches for this matter
        await mutate(
          (key: unknown) =>
            Array.isArray(key) &&
            (key[0] === 'entities' ||
              key[0] === 'entity' ||
              key[0] === 'entityRelationships' ||
              key[0] === 'mergedEntities' ||
              key[0] === 'mergeSuggestions') &&
            key[1] === matterId,
          undefined,
          { revalidate: true }
        );

        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to unmerge entity');
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [matterId, mutate]
  );

  return { unmerge, isLoading, error };
}
