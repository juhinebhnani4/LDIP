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
  EntityWithRelations,
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
