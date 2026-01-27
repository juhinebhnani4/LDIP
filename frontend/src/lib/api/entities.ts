/**
 * Entity API Client for MIG (Matter Identity Graph)
 *
 * Provides typed API functions for entity operations.
 */

import { api } from './client';
import type {
  EntitiesListResponse,
  EntityListOptions,
  EntityMention,
  EntityMentionsOptions,
  EntityMentionsResponse,
  EntityResponse,
} from '@/types';

/**
 * Build query string from options object.
 */
function buildQueryString(options: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(options)) {
    if (value !== undefined) {
      // Convert camelCase to snake_case for API
      const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
      params.append(snakeKey, String(value));
    }
  }
  const queryString = params.toString();
  return queryString ? `?${queryString}` : '';
}

/**
 * Get paginated list of entities in a matter.
 *
 * @param matterId - Matter UUID
 * @param options - Query options (entityType, page, perPage)
 * @returns Paginated list of entities
 *
 * @example
 * ```ts
 * const entities = await getEntities('matter-123', {
 *   entityType: 'PERSON',
 *   page: 1,
 *   perPage: 20,
 * });
 * console.log(entities.data); // EntityListItem[]
 * console.log(entities.meta.total); // Total count
 * ```
 */
export async function getEntities(
  matterId: string,
  options: EntityListOptions = {}
): Promise<EntitiesListResponse> {
  const queryString = buildQueryString({
    entityType: options.entityType,
    page: options.page,
    perPage: options.perPage,
  });

  return api.get<EntitiesListResponse>(`/api/matters/${matterId}/entities${queryString}`);
}

/**
 * Get a single entity with relationships and recent mentions.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID
 * @returns Entity with relationships and mentions
 *
 * @example
 * ```ts
 * const entity = await getEntity('matter-123', 'entity-456');
 * console.log(entity.data.canonicalName); // "Nirav Jobalia"
 * console.log(entity.data.relationships); // EntityEdge[]
 * console.log(entity.data.recentMentions); // EntityMention[]
 * ```
 */
export async function getEntity(
  matterId: string,
  entityId: string
): Promise<EntityResponse> {
  return api.get<EntityResponse>(`/api/matters/${matterId}/entities/${entityId}`);
}

/**
 * Get paginated list of mentions for an entity.
 *
 * Mentions include document references, page numbers, and bounding box IDs
 * for highlighting the entity in the document viewer.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID
 * @param options - Query options (page, perPage)
 * @returns Paginated list of entity mentions
 *
 * @example
 * ```ts
 * const mentions = await getEntityMentions('matter-123', 'entity-456', {
 *   page: 1,
 *   perPage: 20,
 * });
 * for (const mention of mentions.data) {
 *   console.log(`${mention.mentionText} on page ${mention.pageNumber}`);
 * }
 * ```
 */
export async function getEntityMentions(
  matterId: string,
  entityId: string,
  options: EntityMentionsOptions = {}
): Promise<EntityMentionsResponse> {
  const queryString = buildQueryString({
    page: options.page,
    perPage: options.perPage,
  });

  return api.get<EntityMentionsResponse>(
    `/api/matters/${matterId}/entities/${entityId}/mentions${queryString}`
  );
}

/**
 * Get all mentions for an entity (auto-paginates).
 *
 * Warning: Use with caution for entities with many mentions.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID
 * @param maxPages - Maximum pages to fetch (default 10)
 * @returns All entity mentions
 */
export async function getAllEntityMentions(
  matterId: string,
  entityId: string,
  maxPages: number = 10
): Promise<EntityMention[]> {
  const allMentions: EntityMention[] = [];
  let page = 1;
  const perPage = 100;

  while (page <= maxPages) {
    const response = await getEntityMentions(matterId, entityId, { page, perPage });
    allMentions.push(...response.data);

    if (page >= response.meta.totalPages) {
      break;
    }
    page++;
  }

  return allMentions;
}

// =============================================================================
// Entity Merge & Alias Operations (Story 10C.2)
// =============================================================================

import type {
  MergeEntitiesRequest,
  MergeResultResponse,
  AliasesListResponse,
  MergeSuggestionsResponse,
  UnmergeResultResponse,
  MergedEntitiesResponse,
} from '@/types/entity';

/**
 * Merge two entities.
 * Source entity is deleted; its aliases are added to target.
 *
 * @param matterId - Matter UUID
 * @param request - Merge request with source/target entity IDs
 * @returns Merge result with kept entity ID and added aliases
 *
 * @example
 * ```ts
 * const result = await mergeEntities('matter-123', {
 *   sourceEntityId: 'entity-456',  // Will be deleted
 *   targetEntityId: 'entity-789',  // Will be kept
 *   reason: 'Same person with different name variations',
 * });
 * console.log(result.keptEntityId); // 'entity-789'
 * console.log(result.aliasesAdded); // ['J. Doe']
 * ```
 */
export async function mergeEntities(
  matterId: string,
  request: MergeEntitiesRequest
): Promise<MergeResultResponse> {
  return api.post<MergeResultResponse>(
    `/api/matters/${matterId}/entities/merge`,
    request
  );
}

/**
 * Add an alias to an entity.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID
 * @param alias - Alias string to add
 * @returns Updated aliases list
 *
 * @example
 * ```ts
 * const result = await addAlias('matter-123', 'entity-456', 'Johnny D');
 * console.log(result.data); // ['J. Doe', 'Johnny', 'Johnny D']
 * ```
 */
export async function addAlias(
  matterId: string,
  entityId: string,
  alias: string
): Promise<AliasesListResponse> {
  return api.post<AliasesListResponse>(
    `/api/matters/${matterId}/entities/${entityId}/aliases`,
    { alias }
  );
}

/**
 * Remove an alias from an entity.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID
 * @param alias - Alias string to remove
 * @returns Updated aliases list
 *
 * @example
 * ```ts
 * const result = await removeAlias('matter-123', 'entity-456', 'Johnny');
 * console.log(result.data); // ['J. Doe']
 * ```
 */
export async function removeAlias(
  matterId: string,
  entityId: string,
  alias: string
): Promise<AliasesListResponse> {
  return api.delete<AliasesListResponse>(
    `/api/matters/${matterId}/entities/${entityId}/aliases`,
    { data: { alias } }
  );
}


// =============================================================================
// Merge Suggestions (Lawyer UX - Entity Auto-Merge)
// =============================================================================

export interface MergeSuggestionsOptions {
  entityType?: string;
  minSimilarity?: number;
  limit?: number;
}

/**
 * Get suggested entity pairs that may be duplicates.
 *
 * Uses name similarity algorithms to detect entities that might be
 * the same person/organization with different name variants.
 *
 * @param matterId - Matter UUID
 * @param options - Filter options
 * @returns List of merge suggestions
 *
 * @example
 * ```ts
 * const suggestions = await getMergeSuggestions('matter-123', {
 *   minSimilarity: 0.7,
 *   limit: 10,
 * });
 * for (const s of suggestions.data) {
 *   console.log(`${s.entityAName} may be the same as ${s.entityBName}`);
 * }
 * ```
 */
export async function getMergeSuggestions(
  matterId: string,
  options: MergeSuggestionsOptions = {}
): Promise<MergeSuggestionsResponse> {
  const queryString = buildQueryString({
    entityType: options.entityType,
    minSimilarity: options.minSimilarity,
    limit: options.limit,
  });

  return api.get<MergeSuggestionsResponse>(
    `/api/matters/${matterId}/entities/merge-suggestions${queryString}`
  );
}


// =============================================================================
// Story 3.4: Entity Unmerge (Split)
// =============================================================================

/**
 * Unmerge (split) a previously merged entity.
 *
 * Story 3.4: Reverses a soft merge operation, restoring the entity
 * to active status. The entity starts fresh (mentions remain with
 * the merged-into entity).
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID to unmerge (must be a merged entity)
 * @returns Unmerge result with restored entity ID
 *
 * @example
 * ```ts
 * const result = await unmergeEntity('matter-123', 'entity-456');
 * console.log(result.restoredEntityId); // 'entity-456'
 * console.log(result.previouslyMergedIntoId); // 'entity-789'
 * ```
 */
export async function unmergeEntity(
  matterId: string,
  entityId: string
): Promise<UnmergeResultResponse> {
  return api.post<UnmergeResultResponse>(
    `/api/matters/${matterId}/entities/unmerge`,
    { entityId }
  );
}

/**
 * Get entities that were merged into a specific entity.
 *
 * Story 3.4: Returns entities that can be unmerged (split) from
 * the target entity.
 *
 * @param matterId - Matter UUID
 * @param entityId - Entity UUID to check for merged entities
 * @returns List of entities merged into this entity
 *
 * @example
 * ```ts
 * const merged = await getMergedEntities('matter-123', 'entity-456');
 * for (const e of merged.data) {
 *   console.log(`${e.canonicalName} was merged at ${e.mergedAt}`);
 * }
 * ```
 */
export async function getMergedEntities(
  matterId: string,
  entityId: string
): Promise<MergedEntitiesResponse> {
  return api.get<MergedEntitiesResponse>(
    `/api/matters/${matterId}/entities/${entityId}/merged-from`
  );
}
