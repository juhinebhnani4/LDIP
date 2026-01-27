"""Entity (MIG) API routes for Matter Identity Graph operations.

Provides endpoints for:
- Listing entities in a matter
- Getting entity details with relationships
- Getting entity mentions with document locations
- Managing entity aliases (add, remove, merge)
"""

import asyncio
import math

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.entity import (
    EntitiesListResponse,
    EntityListItem,
    EntityMentionsResponse,
    EntityNodeWithRelations,
    EntityResponse,
    EntityType,
    PaginationMeta,
)
from app.services.mig import (
    CorrectionLearningService,
    MIGGraphService,
    get_correction_learning_service,
    get_mig_graph_service,
)
from app.services.mig.entity_resolver import get_entity_resolver, EntityResolver

# =============================================================================
# Request/Response Models for Alias Management
# =============================================================================


class AddAliasRequest(BaseModel):
    """Request to add an alias to an entity."""

    alias: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Alias name to add",
        examples=["N.D. Jobalia"],
    )


class RemoveAliasRequest(BaseModel):
    """Request to remove an alias from an entity."""

    alias: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Alias name to remove",
        examples=["N.D. Jobalia"],
    )


class MergeEntitiesRequest(BaseModel):
    """Request to merge two entities."""

    model_config = ConfigDict(populate_by_name=True)

    source_entity_id: str = Field(
        ...,
        alias="sourceEntityId",
        description="Entity ID to merge (will be deleted)",
    )
    target_entity_id: str = Field(
        ...,
        alias="targetEntityId",
        description="Entity ID to keep (will receive aliases)",
    )
    reason: str | None = Field(
        None,
        max_length=500,
        description="Optional reason for the merge",
    )


class AliasesListResponse(BaseModel):
    """Response containing a list of aliases."""

    model_config = ConfigDict(populate_by_name=True)

    data: list[str] = Field(..., description="List of alias names")
    entity_id: str = Field(..., alias="entityId", description="Entity UUID")
    canonical_name: str = Field(..., alias="canonicalName", description="Entity canonical name")


class MergeResultResponse(BaseModel):
    """Response for entity merge operation."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(..., description="Whether merge was successful")
    kept_entity_id: str = Field(..., alias="keptEntityId", description="ID of kept entity")
    deleted_entity_id: str = Field(..., alias="deletedEntityId", description="ID of deleted entity")
    aliases_added: list[str] = Field(..., alias="aliasesAdded", description="Aliases added to kept entity")


class UnmergeEntityRequest(BaseModel):
    """Request to unmerge a previously merged entity (Story 3.4)."""

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(
        ...,
        alias="entityId",
        description="Entity ID to unmerge (must be a merged entity)",
    )


class UnmergeResultResponse(BaseModel):
    """Response for entity unmerge operation (Story 3.4)."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(..., description="Whether unmerge was successful")
    restored_entity_id: str = Field(..., alias="restoredEntityId", description="ID of restored entity")
    previously_merged_into_id: str = Field(
        ..., alias="previouslyMergedIntoId", description="ID of entity it was merged into"
    )


class MergeSuggestionItem(BaseModel):
    """A single merge suggestion for two potentially duplicate entities."""

    model_config = ConfigDict(populate_by_name=True)

    entity_a_id: str = Field(..., alias="entityAId", description="First entity ID")
    entity_a_name: str = Field(..., alias="entityAName", description="First entity canonical name")
    entity_b_id: str = Field(..., alias="entityBId", description="Second entity ID")
    entity_b_name: str = Field(..., alias="entityBName", description="Second entity canonical name")
    entity_type: str = Field(..., alias="entityType", description="Entity type (PERSON, ORG, etc.)")
    similarity_score: float = Field(..., alias="similarityScore", description="Similarity score 0-1")
    shared_documents: int = Field(0, alias="sharedDocuments", description="Documents mentioning both")
    reason: str = Field(..., description="Human-readable reason for suggestion")


class MergeSuggestionsResponse(BaseModel):
    """Response containing merge suggestions."""

    model_config = ConfigDict(populate_by_name=True)

    data: list[MergeSuggestionItem] = Field(..., description="List of merge suggestions")
    total: int = Field(..., description="Total suggestions found")

router = APIRouter(prefix="/matters/{matter_id}/entities", tags=["entities"])
logger = structlog.get_logger(__name__)


def _get_mig_service() -> MIGGraphService:
    """Get MIG graph service instance."""
    return get_mig_graph_service()


def _get_correction_service() -> CorrectionLearningService:
    """Get correction learning service instance."""
    return get_correction_learning_service()


def _get_entity_resolver() -> EntityResolver:
    """Get entity resolver instance."""
    return get_entity_resolver()


# =============================================================================
# List Entities
# =============================================================================


@router.get("", response_model=EntitiesListResponse, response_model_by_alias=True)
async def list_entities(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_type: EntityType | None = Query(
        None,
        description="Filter by entity type (PERSON, ORG, INSTITUTION, ASSET)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
) -> EntitiesListResponse:
    """List all entities in a matter.

    Returns paginated list of entities with mention counts.
    Results are sorted by mention_count descending (most mentioned first).

    Args:
        matter_id: Matter UUID.
        entity_type: Optional filter by entity type.
        page: Page number (1-indexed).
        per_page: Items per page.
        membership: Validated matter membership.
        mig_service: MIG graph service.

    Returns:
        Paginated list of entities.
    """
    logger.info(
        "list_entities_request",
        matter_id=matter_id,
        entity_type=entity_type.value if entity_type else None,
        page=page,
        per_page=per_page,
        user_id=membership.user_id,
    )

    try:
        entities, total = await mig_service.get_entities_by_matter(
            matter_id=matter_id,
            entity_type=entity_type,
            page=page,
            per_page=per_page,
        )

        # Convert to list items
        items = [
            EntityListItem(
                id=e.id,
                canonical_name=e.canonical_name,
                entity_type=e.entity_type,
                mention_count=e.mention_count,
                metadata=e.metadata,
            )
            for e in entities
        ]

        total_pages = math.ceil(total / per_page) if total > 0 else 0

        logger.info(
            "list_entities_success",
            matter_id=matter_id,
            entity_count=len(items),
            total=total,
        )

        return EntitiesListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    except Exception as e:
        logger.error(
            "list_entities_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list entities",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Bulk Relationships Endpoint (Performance Optimization)
# Returns all entity relationships in a single call to avoid N+1 queries
# MUST be before /{entity_id} to avoid route conflict
# =============================================================================


class BulkRelationshipEdge(BaseModel):
    """A single relationship edge between two entities."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Relationship UUID")
    source_entity_id: str = Field(..., alias="sourceEntityId", description="Source entity UUID")
    target_entity_id: str = Field(..., alias="targetEntityId", description="Target entity UUID")
    relationship_type: str = Field(..., alias="relationshipType", description="Type of relationship")
    source_entity_name: str | None = Field(None, alias="sourceEntityName", description="Source entity name")
    target_entity_name: str | None = Field(None, alias="targetEntityName", description="Target entity name")
    weight: float = Field(1.0, description="Relationship weight/strength")


class BulkRelationshipsResponse(BaseModel):
    """Response containing all relationships for a matter."""

    model_config = ConfigDict(populate_by_name=True)

    data: list[BulkRelationshipEdge] = Field(..., description="List of relationship edges")
    total: int = Field(..., description="Total relationships")


@router.get("/relationships", response_model=BulkRelationshipsResponse, response_model_by_alias=True)
async def get_all_relationships(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> BulkRelationshipsResponse:
    """Get all entity relationships for a matter in a single call.

    Performance optimization endpoint that returns all relationship edges
    at once, avoiding N+1 queries when building entity graphs.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.

    Returns:
        All relationship edges for the matter.
    """
    logger.info(
        "get_all_relationships_request",
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    try:
        from app.services.supabase.client import get_service_client

        client = get_service_client()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "DATABASE_NOT_CONFIGURED",
                        "message": "Database client not configured",
                        "details": {},
                    }
                },
            )

        # Query all relationships for this matter
        # Schema: source_node_id, target_node_id, relationship_type, confidence
        result = client.table("identity_edges").select(
            "id, source_node_id, target_node_id, relationship_type, confidence"
        ).eq("matter_id", matter_id).execute()

        if not result.data:
            return BulkRelationshipsResponse(data=[], total=0)

        # Collect all entity IDs to fetch names in one query
        entity_ids = set()
        for row in result.data:
            entity_ids.add(row["source_node_id"])
            entity_ids.add(row["target_node_id"])

        # Fetch entity names in a single query
        entity_names: dict[str, str] = {}
        if entity_ids:
            entities_result = client.table("identity_nodes").select(
                "id, canonical_name"
            ).in_("id", list(entity_ids)).execute()
            for e in (entities_result.data or []):
                entity_names[e["id"]] = e["canonical_name"]

        edges = [
            BulkRelationshipEdge(
                id=row["id"],
                source_entity_id=row["source_node_id"],
                target_entity_id=row["target_node_id"],
                relationship_type=row["relationship_type"],
                source_entity_name=entity_names.get(row["source_node_id"]),
                target_entity_name=entity_names.get(row["target_node_id"]),
                weight=row.get("confidence", 1.0) or 1.0,
            )
            for row in result.data
        ]

        logger.info(
            "get_all_relationships_success",
            matter_id=matter_id,
            edge_count=len(edges),
        )

        return BulkRelationshipsResponse(
            data=edges,
            total=len(edges),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_all_relationships_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get relationships",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Merge Suggestions Endpoint (Lawyer UX - Entity Auto-Merge)
# MUST be before /{entity_id} to avoid route conflict
# =============================================================================


@router.get("/merge-suggestions", response_model=MergeSuggestionsResponse, response_model_by_alias=True)
async def get_merge_suggestions(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_type: EntityType | None = Query(
        None,
        description="Filter by entity type",
    ),
    min_similarity: float = Query(
        0.6,
        ge=0.4,
        le=1.0,
        description="Minimum similarity score (0.4-1.0)",
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum suggestions to return"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
    resolver: EntityResolver = Depends(_get_entity_resolver),
) -> MergeSuggestionsResponse:
    """Get suggested entity pairs that may be duplicates.

    Uses name similarity algorithms to detect entities that might be
    the same person/organization with different name variants.

    Examples:
    - "Ramesh Kumar" and "R. Kumar" (same person)
    - "HDFC Bank" and "HDFC Bank Ltd" (same organization)

    Args:
        matter_id: Matter UUID.
        entity_type: Optional filter by entity type.
        min_similarity: Minimum similarity threshold.
        limit: Maximum number of suggestions.
        membership: Validated matter membership.
        mig_service: MIG graph service.
        resolver: Entity resolver for similarity calculations.

    Returns:
        List of merge suggestions sorted by similarity score.
    """
    logger.info(
        "get_merge_suggestions_request",
        matter_id=matter_id,
        entity_type=entity_type.value if entity_type else None,
        min_similarity=min_similarity,
        limit=limit,
        user_id=membership.user_id,
    )

    try:
        # Get all entities for the matter (we need all for comparison)
        entities, _ = await mig_service.get_entities_by_matter(
            matter_id=matter_id,
            entity_type=entity_type,
            page=1,
            per_page=500,  # Get up to 500 entities for comparison
        )

        if len(entities) < 2:
            return MergeSuggestionsResponse(data=[], total=0)

        # Find potential alias pairs using the resolver
        suggestions: list[MergeSuggestionItem] = []
        seen_pairs: set[tuple[str, str]] = set()

        for entity in entities:
            candidates = resolver.find_potential_aliases(entity, entities)

            for candidate in candidates:
                # Skip if below threshold
                if candidate.similarity_score < min_similarity:
                    continue

                # Avoid duplicates (A,B and B,A)
                pair_key = tuple(sorted([candidate.entity_id, candidate.candidate_entity_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Generate human-readable reason
                if candidate.similarity_score >= 0.85:
                    reason = f'"{candidate.entity_name}" and "{candidate.candidate_name}" appear to be the same {entity.entity_type.value.lower()}'
                elif candidate.initial_match_score > 0.7:
                    reason = f'"{candidate.entity_name}" may be an abbreviated form of "{candidate.candidate_name}"'
                else:
                    reason = f'Similar names: "{candidate.entity_name}" and "{candidate.candidate_name}"'

                suggestions.append(
                    MergeSuggestionItem(
                        entity_a_id=candidate.entity_id,
                        entity_a_name=candidate.entity_name,
                        entity_b_id=candidate.candidate_entity_id,
                        entity_b_name=candidate.candidate_name,
                        entity_type=entity.entity_type.value,
                        similarity_score=round(candidate.similarity_score, 2),
                        shared_documents=0,  # Could query mentions to find shared docs
                        reason=reason,
                    )
                )

        # Sort by similarity score descending and limit
        suggestions.sort(key=lambda x: x.similarity_score, reverse=True)
        suggestions = suggestions[:limit]

        logger.info(
            "get_merge_suggestions_success",
            matter_id=matter_id,
            suggestions_count=len(suggestions),
        )

        return MergeSuggestionsResponse(
            data=suggestions,
            total=len(suggestions),
        )

    except Exception as e:
        logger.error(
            "get_merge_suggestions_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get merge suggestions",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Get Single Entity
# =============================================================================


@router.get("/{entity_id}", response_model=EntityResponse, response_model_by_alias=True)
async def get_entity(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
) -> EntityResponse:
    """Get a single entity with relationships and mentions.

    Returns entity details including:
    - Basic info (canonical_name, entity_type, mention_count)
    - Relationships (edges to/from this entity)
    - Recent mentions (with document/page references)

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        membership: Validated matter membership.
        mig_service: MIG graph service.

    Returns:
        Entity with relationships and mentions.

    Raises:
        HTTPException 404: If entity not found.
    """
    logger.info(
        "get_entity_request",
        matter_id=matter_id,
        entity_id=entity_id,
        user_id=membership.user_id,
    )

    try:
        # Get entity
        entity = await mig_service.get_entity(entity_id, matter_id)

        if entity is None:
            logger.warning(
                "get_entity_not_found",
                matter_id=matter_id,
                entity_id=entity_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": f"Entity {entity_id} not found",
                        "details": {},
                    }
                },
            )

        # Get relationships
        relationships = await mig_service.get_entity_relationships(entity_id, matter_id)

        # Get recent mentions (first page)
        mentions, _ = await mig_service.get_entity_mentions(
            entity_id=entity_id,
            matter_id=matter_id,
            page=1,
            per_page=10,
        )

        # Build response with relations
        entity_with_relations = EntityNodeWithRelations(
            id=entity.id,
            matter_id=entity.matter_id,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type,
            metadata=entity.metadata,
            mention_count=entity.mention_count,
            aliases=entity.aliases,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            relationships=relationships,
            recent_mentions=mentions,
        )

        logger.info(
            "get_entity_success",
            matter_id=matter_id,
            entity_id=entity_id,
            relationship_count=len(relationships),
            mention_count=len(mentions),
        )

        return EntityResponse(data=entity_with_relations)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_entity_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get entity",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Get Entity Mentions
# =============================================================================


@router.get("/{entity_id}/mentions", response_model=EntityMentionsResponse, response_model_by_alias=True)
async def get_entity_mentions(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
) -> EntityMentionsResponse:
    """Get all mentions of an entity.

    Returns paginated list of mentions with:
    - Document ID and name
    - Page number
    - Bounding box IDs for highlighting
    - Context text around the mention

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        page: Page number (1-indexed).
        per_page: Items per page.
        membership: Validated matter membership.
        mig_service: MIG graph service.

    Returns:
        Paginated list of entity mentions.

    Raises:
        HTTPException 404: If entity not found.
    """
    logger.info(
        "get_entity_mentions_request",
        matter_id=matter_id,
        entity_id=entity_id,
        page=page,
        per_page=per_page,
        user_id=membership.user_id,
    )

    try:
        # Validate entity exists
        entity = await mig_service.get_entity(entity_id, matter_id)

        if entity is None:
            logger.warning(
                "get_entity_mentions_entity_not_found",
                matter_id=matter_id,
                entity_id=entity_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": f"Entity {entity_id} not found",
                        "details": {},
                    }
                },
            )

        # Get mentions
        mentions, total = await mig_service.get_entity_mentions(
            entity_id=entity_id,
            matter_id=matter_id,
            page=page,
            per_page=per_page,
        )

        total_pages = math.ceil(total / per_page) if total > 0 else 0

        logger.info(
            "get_entity_mentions_success",
            matter_id=matter_id,
            entity_id=entity_id,
            mention_count=len(mentions),
            total=total,
        )

        return EntityMentionsResponse(
            data=mentions,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_entity_mentions_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get entity mentions",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Alias Management Endpoints (Story 2c-2)
# =============================================================================


@router.get("/{entity_id}/aliases", response_model=AliasesListResponse, response_model_by_alias=True)
async def get_entity_aliases(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
) -> AliasesListResponse:
    """Get all aliases for an entity.

    Returns the list of known aliases for the entity, including
    both manually added aliases and auto-detected name variants.

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        membership: Validated matter membership.
        mig_service: MIG graph service.

    Returns:
        List of aliases for the entity.

    Raises:
        HTTPException 404: If entity not found.
    """
    logger.info(
        "get_entity_aliases_request",
        matter_id=matter_id,
        entity_id=entity_id,
        user_id=membership.user_id,
    )

    try:
        entity = await mig_service.get_entity(entity_id, matter_id)

        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": f"Entity {entity_id} not found",
                        "details": {},
                    }
                },
            )

        return AliasesListResponse(
            data=entity.aliases or [],
            entity_id=entity.id,
            canonical_name=entity.canonical_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_entity_aliases_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get entity aliases",
                    "details": {},
                }
            },
        ) from e


@router.post("/{entity_id}/aliases", response_model=AliasesListResponse, response_model_by_alias=True)
async def add_entity_alias(
    request: AddAliasRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
    correction_service: CorrectionLearningService = Depends(_get_correction_service),
) -> AliasesListResponse:
    """Add an alias to an entity.

    Adds a name variant to the entity's aliases list. This enables
    search to find documents containing this alias when searching
    for the entity.

    Args:
        request: Alias to add.
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        membership: Validated matter membership (editor/owner required).
        mig_service: MIG graph service.

    Returns:
        Updated list of aliases.

    Raises:
        HTTPException 404: If entity not found.
        HTTPException 400: If alias already exists.
    """
    logger.info(
        "add_entity_alias_request",
        matter_id=matter_id,
        entity_id=entity_id,
        alias=request.alias,
        user_id=membership.user_id,
    )

    try:
        # Validate entity exists
        entity = await mig_service.get_entity(entity_id, matter_id)

        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": f"Entity {entity_id} not found",
                        "details": {},
                    }
                },
            )

        # Check if alias already exists
        current_aliases = entity.aliases or []
        if request.alias in current_aliases:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "ALIAS_EXISTS",
                        "message": f"Alias '{request.alias}' already exists for this entity",
                        "details": {},
                    }
                },
            )

        # Add alias
        updated_entity = await mig_service.add_alias_to_entity(
            entity_id=entity_id,
            matter_id=matter_id,
            alias=request.alias,
        )

        if updated_entity is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "ADD_ALIAS_FAILED",
                        "message": "Failed to add alias to entity",
                        "details": {},
                    }
                },
            )

        # Record the correction for learning (AC #4)
        try:
            await correction_service.record_correction(
                matter_id=matter_id,
                entity_id=entity_id,
                correction_type="add",
                alias_name=request.alias,
                corrected_by=membership.user_id,
            )
        except Exception as correction_error:
            # Log but don't fail the main operation
            logger.warning(
                "add_entity_alias_correction_recording_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(correction_error),
            )

        logger.info(
            "add_entity_alias_success",
            matter_id=matter_id,
            entity_id=entity_id,
            alias=request.alias,
        )

        return AliasesListResponse(
            data=updated_entity.aliases or [],
            entity_id=updated_entity.id,
            canonical_name=updated_entity.canonical_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "add_entity_alias_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to add alias",
                    "details": {},
                }
            },
        ) from e


@router.delete("/{entity_id}/aliases", response_model=AliasesListResponse, response_model_by_alias=True)
async def remove_entity_alias(
    request: RemoveAliasRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
    correction_service: CorrectionLearningService = Depends(_get_correction_service),
) -> AliasesListResponse:
    """Remove an alias from an entity.

    Removes a name variant from the entity's aliases list. The entity's
    canonical name cannot be removed.

    Args:
        request: Alias to remove.
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        membership: Validated matter membership (editor/owner required).
        mig_service: MIG graph service.

    Returns:
        Updated list of aliases.

    Raises:
        HTTPException 404: If entity not found.
        HTTPException 404: If alias not found.
    """
    logger.info(
        "remove_entity_alias_request",
        matter_id=matter_id,
        entity_id=entity_id,
        alias=request.alias,
        user_id=membership.user_id,
    )

    try:
        # Validate entity exists
        entity = await mig_service.get_entity(entity_id, matter_id)

        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": f"Entity {entity_id} not found",
                        "details": {},
                    }
                },
            )

        # Check if alias exists
        current_aliases = entity.aliases or []
        if request.alias not in current_aliases:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ALIAS_NOT_FOUND",
                        "message": f"Alias '{request.alias}' not found for this entity",
                        "details": {},
                    }
                },
            )

        # Remove alias
        updated_entity = await mig_service.remove_alias_from_entity(
            entity_id=entity_id,
            matter_id=matter_id,
            alias=request.alias,
        )

        if updated_entity is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "REMOVE_ALIAS_FAILED",
                        "message": "Failed to remove alias from entity",
                        "details": {},
                    }
                },
            )

        # Record the correction for learning (AC #4)
        try:
            await correction_service.record_correction(
                matter_id=matter_id,
                entity_id=entity_id,
                correction_type="remove",
                alias_name=request.alias,
                corrected_by=membership.user_id,
            )
        except Exception as correction_error:
            # Log but don't fail the main operation
            logger.warning(
                "remove_entity_alias_correction_recording_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(correction_error),
            )

        logger.info(
            "remove_entity_alias_success",
            matter_id=matter_id,
            entity_id=entity_id,
            alias=request.alias,
        )

        return AliasesListResponse(
            data=updated_entity.aliases or [],
            entity_id=updated_entity.id,
            canonical_name=updated_entity.canonical_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "remove_entity_alias_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to remove alias",
                    "details": {},
                }
            },
        ) from e


@router.post("/merge", response_model=MergeResultResponse, response_model_by_alias=True)
async def merge_entities(
    request: MergeEntitiesRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER])  # Only owners can merge
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
    correction_service: CorrectionLearningService = Depends(_get_correction_service),
) -> MergeResultResponse:
    """Merge two entities into one.

    Merges the source entity into the target entity:
    - Target entity receives source's canonical name as an alias
    - Target entity receives all of source's aliases
    - All relationships pointing to source are updated to target
    - Source entity is deleted

    This is a destructive operation that requires owner permission.

    Args:
        request: Merge parameters.
        matter_id: Matter UUID.
        membership: Validated matter membership (owner required).
        mig_service: MIG graph service.

    Returns:
        Merge result with details.

    Raises:
        HTTPException 404: If either entity not found.
        HTTPException 400: If trying to merge entity with itself.
    """
    logger.info(
        "merge_entities_request",
        matter_id=matter_id,
        source_id=request.source_entity_id,
        target_id=request.target_entity_id,
        reason=request.reason,
        user_id=membership.user_id,
    )

    try:
        # Validate not merging with self
        if request.source_entity_id == request.target_entity_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_MERGE",
                        "message": "Cannot merge entity with itself",
                        "details": {},
                    }
                },
            )

        # LATENCY FIX: Parallelize independent entity lookups
        source, target = await asyncio.gather(
            mig_service.get_entity(request.source_entity_id, matter_id),
            mig_service.get_entity(request.target_entity_id, matter_id),
        )

        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "SOURCE_ENTITY_NOT_FOUND",
                        "message": f"Source entity {request.source_entity_id} not found",
                        "details": {},
                    }
                },
            )

        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "TARGET_ENTITY_NOT_FOUND",
                        "message": f"Target entity {request.target_entity_id} not found",
                        "details": {},
                    }
                },
            )

        # Validate same entity type
        if source.entity_type != target.entity_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "TYPE_MISMATCH",
                        "message": f"Cannot merge {source.entity_type} with {target.entity_type}",
                        "details": {},
                    }
                },
            )

        # Collect aliases being added
        source_aliases = [source.canonical_name] + (source.aliases or [])

        # Call the merge_entities SQL function via RPC
        from app.services.supabase.client import get_service_client

        client = get_service_client()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "DATABASE_NOT_CONFIGURED",
                        "message": "Database client not configured",
                        "details": {},
                    }
                },
            )

        # Call the merge function with user_id for auth
        client.rpc(
            "merge_entities",
            {
                "p_matter_id": matter_id,
                "p_keep_id": request.target_entity_id,
                "p_merge_id": request.source_entity_id,
                "p_user_id": membership.user_id,
            },
        ).execute()

        # Record the correction for learning (AC #4)
        try:
            await correction_service.record_correction(
                matter_id=matter_id,
                entity_id=request.target_entity_id,
                correction_type="merge",
                merged_entity_id=request.source_entity_id,
                merged_entity_name=source.canonical_name,
                corrected_by=membership.user_id,
                reason=request.reason,
            )
        except Exception as correction_error:
            # Log but don't fail the main operation
            logger.warning(
                "merge_entities_correction_recording_failed",
                matter_id=matter_id,
                entity_id=request.target_entity_id,
                error=str(correction_error),
            )

        logger.info(
            "merge_entities_success",
            matter_id=matter_id,
            kept_id=request.target_entity_id,
            deleted_id=request.source_entity_id,
            aliases_added=source_aliases,
        )

        return MergeResultResponse(
            success=True,
            kept_entity_id=request.target_entity_id,
            deleted_entity_id=request.source_entity_id,
            aliases_added=source_aliases,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merge_entities_error",
            matter_id=matter_id,
            source_id=request.source_entity_id,
            target_id=request.target_entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "MERGE_FAILED",
                    "message": "Failed to merge entities",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 3.4: Unmerge Entity (Split) Endpoint
# =============================================================================


@router.post("/unmerge", response_model=UnmergeResultResponse, response_model_by_alias=True)
async def unmerge_entity(
    request: UnmergeEntityRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER])  # Only owners can unmerge
    ),
    mig_service: MIGGraphService = Depends(_get_mig_service),
    correction_service: CorrectionLearningService = Depends(_get_correction_service),
) -> UnmergeResultResponse:
    """Unmerge (split) a previously merged entity.

    Story 3.4: Implement Entity Split UI

    Reverses a soft merge operation:
    - Restores the entity to active status
    - Removes the entity's canonical name from the target entity's aliases
    - Entity starts fresh (mentions remain with the merged-into entity)

    This requires owner permission as it's a significant data change.

    Args:
        request: Unmerge parameters.
        matter_id: Matter UUID.
        membership: Validated matter membership (owner required).
        mig_service: MIG graph service.

    Returns:
        Unmerge result with details.

    Raises:
        HTTPException 404: If entity not found or not merged.
        HTTPException 400: If entity is not in a merged state.
    """
    logger.info(
        "unmerge_entity_request",
        matter_id=matter_id,
        entity_id=request.entity_id,
        user_id=membership.user_id,
    )

    try:
        from app.services.supabase.client import get_service_client

        client = get_service_client()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "DATABASE_NOT_CONFIGURED",
                        "message": "Database client not configured",
                        "details": {},
                    }
                },
            )

        # Check if entity exists and is merged
        entity_result = client.table("identity_nodes").select(
            "id, canonical_name, merged_into_id, matter_id"
        ).eq("id", request.entity_id).eq("matter_id", matter_id).execute()

        if not entity_result.data or len(entity_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": f"Entity {request.entity_id} not found",
                        "details": {},
                    }
                },
            )

        entity_data = entity_result.data[0]
        merged_into_id = entity_data.get("merged_into_id")

        if merged_into_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "ENTITY_NOT_MERGED",
                        "message": "Entity is not in a merged state and cannot be unmerged",
                        "details": {},
                    }
                },
            )

        # Call the unmerge function with user_id for auth
        client.rpc(
            "unmerge_entity",
            {
                "p_matter_id": matter_id,
                "p_merged_id": request.entity_id,
                "p_user_id": membership.user_id,
            },
        ).execute()

        # Code Review Fix: Record the unmerge correction for audit trail
        try:
            await correction_service.record_correction(
                matter_id=matter_id,
                entity_id=request.entity_id,
                correction_type="unmerge",
                merged_entity_id=merged_into_id,  # The entity it was previously merged into
                merged_entity_name=entity_data.get("canonical_name"),
                corrected_by=membership.user_id,
                reason="Entity split/unmerge operation",
            )
        except Exception as correction_error:
            # Log but don't fail the main operation
            logger.warning(
                "unmerge_entity_correction_recording_failed",
                matter_id=matter_id,
                entity_id=request.entity_id,
                error=str(correction_error),
            )

        logger.info(
            "unmerge_entity_success",
            matter_id=matter_id,
            entity_id=request.entity_id,
            previously_merged_into=merged_into_id,
        )

        return UnmergeResultResponse(
            success=True,
            restored_entity_id=request.entity_id,
            previously_merged_into_id=merged_into_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "unmerge_entity_error",
            matter_id=matter_id,
            entity_id=request.entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "UNMERGE_FAILED",
                    "message": "Failed to unmerge entity",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 3.4: Get Entities Merged Into This Entity
# =============================================================================


class MergedEntityItem(BaseModel):
    """An entity that was merged into another entity."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Merged entity ID")
    canonical_name: str = Field(..., alias="canonicalName", description="Entity canonical name")
    entity_type: str = Field(..., alias="entityType", description="Entity type")
    merged_at: str | None = Field(None, alias="mergedAt", description="When the merge occurred")


class MergedEntitiesResponse(BaseModel):
    """Response containing entities merged into a specific entity."""

    model_config = ConfigDict(populate_by_name=True)

    data: list[MergedEntityItem] = Field(..., description="List of merged entities")
    total: int = Field(..., description="Total merged entities")


@router.get("/{entity_id}/merged-from", response_model=MergedEntitiesResponse, response_model_by_alias=True)
async def get_merged_entities(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> MergedEntitiesResponse:
    """Get entities that were merged into this entity.

    Story 3.4: Implement Entity Split UI

    Returns a list of entities that were previously merged into the specified
    entity. These entities can be unmerged (split) to restore them to active status.

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID to check for merged entities.
        membership: Validated matter membership.

    Returns:
        List of entities merged into this entity.
    """
    logger.info(
        "get_merged_entities_request",
        matter_id=matter_id,
        entity_id=entity_id,
        user_id=membership.user_id,
    )

    try:
        from app.services.supabase.client import get_service_client

        client = get_service_client()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "DATABASE_NOT_CONFIGURED",
                        "message": "Database client not configured",
                        "details": {},
                    }
                },
            )

        # Query entities where merged_into_id = entity_id
        result = client.table("identity_nodes").select(
            "id, canonical_name, entity_type, merged_at"
        ).eq("merged_into_id", entity_id).eq("matter_id", matter_id).execute()

        merged_entities = [
            MergedEntityItem(
                id=row["id"],
                canonical_name=row["canonical_name"],
                entity_type=row["entity_type"],
                merged_at=row.get("merged_at"),
            )
            for row in (result.data or [])
        ]

        logger.info(
            "get_merged_entities_success",
            matter_id=matter_id,
            entity_id=entity_id,
            merged_count=len(merged_entities),
        )

        return MergedEntitiesResponse(
            data=merged_entities,
            total=len(merged_entities),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_merged_entities_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get merged entities",
                    "details": {},
                }
            },
        ) from e

