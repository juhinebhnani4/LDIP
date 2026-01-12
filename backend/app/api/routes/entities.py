"""Entity (MIG) API routes for Matter Identity Graph operations.

Provides endpoints for:
- Listing entities in a matter
- Getting entity details with relationships
- Getting entity mentions with document locations
"""

import math

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.entity import (
    EntitiesListResponse,
    EntityListItem,
    EntityMentionsResponse,
    EntityNode,
    EntityNodeWithRelations,
    EntityResponse,
    EntityType,
    PaginationMeta,
)
from app.services.mig import MIGGraphService, get_mig_graph_service

router = APIRouter(prefix="/matters/{matter_id}/entities", tags=["entities"])
logger = structlog.get_logger(__name__)


def _get_mig_service() -> MIGGraphService:
    """Get MIG graph service instance."""
    return get_mig_graph_service()


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
