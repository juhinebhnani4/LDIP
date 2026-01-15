"""Entity (MIG) API routes for Matter Identity Graph operations.

Provides endpoints for:
- Listing entities in a matter
- Getting entity details with relationships
- Getting entity mentions with document locations
- Managing entity aliases (add, remove, merge)
"""

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

    source_entity_id: str = Field(
        ...,
        description="Entity ID to merge (will be deleted)",
    )
    target_entity_id: str = Field(
        ...,
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

router = APIRouter(prefix="/matters/{matter_id}/entities", tags=["entities"])
logger = structlog.get_logger(__name__)


def _get_mig_service() -> MIGGraphService:
    """Get MIG graph service instance."""
    return get_mig_graph_service()


def _get_correction_service() -> CorrectionLearningService:
    """Get correction learning service instance."""
    return get_correction_learning_service()


# =============================================================================
# List Entities
# =============================================================================


@router.get("", response_model=EntitiesListResponse)
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
# Get Single Entity
# =============================================================================


@router.get("/{entity_id}", response_model=EntityResponse)
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


@router.get("/{entity_id}/mentions", response_model=EntityMentionsResponse)
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


@router.get("/{entity_id}/aliases", response_model=AliasesListResponse)
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


@router.post("/{entity_id}/aliases", response_model=AliasesListResponse)
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


@router.delete("/{entity_id}/aliases", response_model=AliasesListResponse)
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


@router.post("/merge", response_model=MergeResultResponse)
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

        # Validate both entities exist
        source = await mig_service.get_entity(request.source_entity_id, matter_id)
        target = await mig_service.get_entity(request.target_entity_id, matter_id)

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

        # Call the merge function
        client.rpc(
            "merge_entities",
            {
                "p_matter_id": matter_id,
                "p_keep_id": request.target_entity_id,
                "p_merge_id": request.source_entity_id,
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
