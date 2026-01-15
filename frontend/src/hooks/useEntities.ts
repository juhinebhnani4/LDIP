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
