/**
 * Entity Types for MIG (Matter Identity Graph)
 *
 * Types for entities extracted from legal documents.
 * Matches backend Pydantic models in app/models/entity.py
 */

/** Entity type classification */
export type EntityType = 'PERSON' | 'ORG' | 'INSTITUTION' | 'ASSET';

/** Relationship type between entities */
export type RelationshipType = 'ALIAS_OF' | 'HAS_ROLE' | 'RELATED_TO';

/** Entity metadata structure */
export interface EntityMetadata {
  roles?: string[];
  aliasesFound?: string[];
  firstExtractionConfidence?: number;
  [key: string]: unknown;
}

/** Base entity properties */
export interface EntityBase {
  canonicalName: string;
  entityType: EntityType;
}

/** Entity list item (summary view) */
export interface EntityListItem extends EntityBase {
  id: string;
  mentionCount: number;
  metadata: EntityMetadata;
}

/** Complete entity model from API */
export interface Entity extends EntityListItem {
  matterId: string;
  aliases: string[];
  createdAt: string;
  updatedAt: string;
}

/** Entity with relationships and mentions (detail view) */
export interface EntityWithRelations extends Entity {
  relationships: EntityEdge[];
  recentMentions: EntityMention[];
}

/** Relationship edge between entities */
export interface EntityEdge {
  id: string;
  matterId: string;
  sourceEntityId: string;
  targetEntityId: string;
  relationshipType: RelationshipType;
  confidence: number;
  metadata: Record<string, unknown>;
  createdAt: string;
  /** Populated when fetching edges with entity details */
  sourceEntityName?: string;
  targetEntityName?: string;
}

/** Entity mention in a document */
export interface EntityMention {
  id: string;
  entityId: string;
  documentId: string;
  chunkId: string | null;
  pageNumber: number | null;
  bboxIds: string[];
  mentionText: string;
  context: string | null;
  confidence: number;
  createdAt: string;
  /** Populated when fetching mentions with document details */
  documentName?: string;
}

/** Pagination metadata */
export interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/** Paginated entities response */
export interface EntitiesListResponse {
  data: EntityListItem[];
  meta: PaginationMeta;
}

/** Single entity response */
export interface EntityResponse {
  data: EntityWithRelations;
}

/** Paginated entity mentions response */
export interface EntityMentionsResponse {
  data: EntityMention[];
  meta: PaginationMeta;
}

/** Query options for listing entities */
export interface EntityListOptions {
  entityType?: EntityType;
  page?: number;
  perPage?: number;
}

/** Query options for listing entity mentions */
export interface EntityMentionsOptions {
  page?: number;
  perPage?: number;
}
