/**
 * Entity Types for MIG (Matter Identity Graph)
 *
 * Types for entities extracted from legal documents.
 * Matches backend Pydantic models in app/models/entity.py
 */

import type { Node, Edge } from '@xyflow/react';

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
  /** Story 3.3: If merged, references target entity */
  mergedIntoId?: string | null;
  /** Story 3.3: When entity was merged */
  mergedAt?: string | null;
  /** Story 3.3: User who performed merge */
  mergedBy?: string | null;
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


// =============================================================================
// Alias Management Types (Story 2c-2)
// =============================================================================

/** Request to add an alias to an entity */
export interface AddAliasRequest {
  alias: string;
}

/** Request to remove an alias from an entity */
export interface RemoveAliasRequest {
  alias: string;
}

/** Request to merge two entities */
export interface MergeEntitiesRequest {
  sourceEntityId: string;
  targetEntityId: string;
  reason?: string;
}

/** Response containing an entity's aliases */
export interface AliasesListResponse {
  data: string[];
  entityId: string;
  canonicalName: string;
}

/** Result of entity merge operation */
export interface MergeResultResponse {
  success: boolean;
  keptEntityId: string;
  deletedEntityId: string;
  aliasesAdded: string[];
}

/**
 * Story 3.3: Request to unmerge a previously merged entity
 */
export interface UnmergeEntityRequest {
  entityId: string;
}

/**
 * Story 3.3: Result of entity unmerge operation
 */
export interface UnmergeResultResponse {
  success: boolean;
  restoredEntityId: string;
  previouslyMergedIntoId: string;
}


// =============================================================================
// Alias-Expanded Search Types (Story 2c-2)
// =============================================================================

/** Request for alias-expanded search */
export interface AliasExpandedSearchRequest {
  query: string;
  limit?: number;
  expandAliases?: boolean;
  bm25Weight?: number;
  semanticWeight?: number;
  rerank?: boolean;
  rerankTopN?: number;
}

/** Single search result item */
export interface SearchResultItem {
  id: string;
  documentId: string;
  content: string;
  pageNumber: number | null;
  chunkType: 'parent' | 'child';
  tokenCount: number;
  bm25Rank: number | null;
  semanticRank: number | null;
  rrfScore: number;
  relevanceScore: number | null;
}

/** Metadata for alias-expanded search */
export interface AliasExpandedSearchMeta {
  query: string;
  expandedQuery: string | null;
  matterId: string;
  totalCandidates: number;
  bm25Weight: number;
  semanticWeight: number;
  aliasesFound: string[];
  entitiesMatched: string[];
  rerankUsed: boolean | null;
  fallbackReason: string | null;
}

/** Response for alias-expanded search */
export interface AliasExpandedSearchResponse {
  data: SearchResultItem[];
  meta: AliasExpandedSearchMeta;
}


// =============================================================================
// Graph Visualization Types (Story 10C.1)
// =============================================================================

/**
 * React Flow node data for entity
 * Uses index signature to satisfy @xyflow/react's Record<string, unknown> constraint
 */
export interface EntityNodeData extends Record<string, unknown> {
  id: string;
  canonicalName: string;
  entityType: EntityType;
  mentionCount: number;
  aliases: string[];
  metadata: EntityMetadata;
  isSelected?: boolean;
  isConnected?: boolean;
  isDimmed?: boolean;
  /** Whether this node is selected for merge operation */
  isSelectedForMerge?: boolean;
}

/**
 * React Flow node with entity data
 */
export type EntityGraphNode = Node<EntityNodeData, 'entity'>;

/**
 * React Flow edge data for relationship
 * Uses index signature to satisfy @xyflow/react's Record<string, unknown> constraint
 */
export interface EntityEdgeData extends Record<string, unknown> {
  relationshipType: RelationshipType;
  confidence: number;
  metadata: Record<string, unknown>;
}

/**
 * React Flow edge with relationship data
 */
export type EntityGraphEdge = Edge<EntityEdgeData>;

/**
 * Full graph data structure
 */
export interface EntityGraphData {
  nodes: EntityGraphNode[];
  edges: EntityGraphEdge[];
}

/**
 * View modes for entities tab
 */
export type EntityViewMode = 'graph' | 'list' | 'grid';

/**
 * Filter state for entities
 */
export interface EntityFilterState {
  entityTypes: EntityType[];
  roles: string[];
  verificationStatus: 'all' | 'verified' | 'pending' | 'flagged';
  minMentionCount: number;
  searchQuery: string;
}

/**
 * Default filter state
 */
export const DEFAULT_ENTITY_FILTERS: EntityFilterState = {
  entityTypes: [],
  roles: [],
  verificationStatus: 'all',
  minMentionCount: 0,
  searchQuery: '',
};


// =============================================================================
// Merge Suggestions Types (Lawyer UX - Entity Auto-Merge)
// =============================================================================

/** A single merge suggestion for two potentially duplicate entities */
export interface MergeSuggestionItem {
  entityAId: string;
  entityAName: string;
  entityBId: string;
  entityBName: string;
  entityType: EntityType;
  similarityScore: number;
  sharedDocuments: number;
  reason: string;
}

/** Response for merge suggestions */
export interface MergeSuggestionsResponse {
  data: MergeSuggestionItem[];
  total: number;
}


// =============================================================================
// Story 3.4: Merged Entities Types (for Unmerge/Split UI)
// =============================================================================

/** An entity that was merged into another entity */
export interface MergedEntityItem {
  id: string;
  canonicalName: string;
  entityType: EntityType;
  mergedAt: string | null;
}

/** Response containing entities merged into a specific entity */
export interface MergedEntitiesResponse {
  data: MergedEntityItem[];
  total: number;
}


// =============================================================================
// Bulk Relationships (Performance Optimization)
// =============================================================================

/** A single relationship edge from bulk endpoint */
export interface BulkRelationshipEdge {
  id: string;
  sourceEntityId: string;
  targetEntityId: string;
  relationshipType: RelationshipType;
  sourceEntityName: string | null;
  targetEntityName: string | null;
  weight: number;
}

/** Response for bulk relationships endpoint */
export interface BulkRelationshipsResponse {
  data: BulkRelationshipEdge[];
  total: number;
}
