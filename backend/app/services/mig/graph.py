"""MIG Graph Service for entity CRUD operations.

Provides database operations for the Matter Identity Graph:
- Entity nodes (identity_nodes table)
- Entity edges/relationships (identity_edges table)
- Entity mentions (entity_mentions table)

CRITICAL: Always validates matter_id for Layer 4 matter isolation.

NOTE: Uses asyncio.to_thread() to run synchronous Supabase client calls
without blocking the event loop.
"""

import asyncio
import math
from datetime import datetime
from functools import lru_cache

import structlog

from app.models.entity import (
    EntityEdge,
    EntityEdgeCreate,
    EntityExtractionResult,
    EntityMention,
    EntityMentionCreate,
    EntityNode,
    EntityNodeCreate,
    EntityType,
    ExtractedEntity,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class MIGGraphError(Exception):
    """Base exception for MIG graph operations."""

    def __init__(
        self,
        message: str,
        code: str = "MIG_GRAPH_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


class MIGNotFoundError(MIGGraphError):
    """Raised when entity is not found."""

    def __init__(self, message: str):
        super().__init__(message, code="ENTITY_NOT_FOUND")


# =============================================================================
# Service Implementation
# =============================================================================


class MIGGraphService:
    """Service for MIG (Matter Identity Graph) database operations.

    Handles CRUD operations for:
    - identity_nodes: Canonical entities
    - identity_edges: Relationships between entities
    - entity_mentions: Where entities appear in documents

    CRITICAL: All operations validate matter_id for security.

    All async methods use asyncio.to_thread() to run synchronous Supabase
    client calls without blocking the event loop.

    Example:
        >>> service = MIGGraphService()
        >>> nodes = await service.save_entities(
        ...     matter_id="matter-123",
        ...     extraction_result=result,
        ... )
        >>> len(nodes)
        3
    """

    def __init__(self) -> None:
        """Initialize MIG graph service."""
        self._client = None

    @property
    def client(self):
        """Get Supabase client.

        Raises:
            MIGGraphError: If Supabase is not configured.
        """
        if self._client is None:
            self._client = get_supabase_client()
            if self._client is None:
                raise MIGGraphError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                )
        return self._client

    # =========================================================================
    # Entity Node Operations
    # =========================================================================

    async def save_entities(
        self,
        matter_id: str,
        extraction_result: EntityExtractionResult,
    ) -> list[EntityNode]:
        """Save extracted entities to identity_nodes table.

        Handles deduplication: if entity with same canonical_name+type exists
        in matter, increments mention_count instead of creating duplicate.

        Args:
            matter_id: Matter UUID for isolation.
            extraction_result: Extraction result from Gemini.

        Returns:
            List of created/updated EntityNode objects.
        """
        if not extraction_result.entities:
            return []

        saved_nodes: list[EntityNode] = []

        for extracted in extraction_result.entities:
            try:
                # Check if entity already exists (deduplication)
                existing = await self._find_existing_entity(
                    matter_id=matter_id,
                    canonical_name=extracted.canonical_name,
                    entity_type=extracted.type,
                )

                if existing:
                    # Update existing entity
                    updated = await self._update_entity_mention_count(
                        entity_id=existing["id"],
                        matter_id=matter_id,
                        additional_mentions=len(extracted.mentions) or 1,
                    )
                    if updated:
                        saved_nodes.append(self._db_row_to_entity_node(updated))

                        # Save mentions for existing entity
                        await self._save_entity_mentions(
                            entity_id=existing["id"],
                            extracted=extracted,
                            extraction_result=extraction_result,
                        )
                else:
                    # Create new entity
                    node = await self._create_entity_node(
                        matter_id=matter_id,
                        extracted=extracted,
                    )
                    if node:
                        saved_nodes.append(node)

                        # Save mentions for new entity
                        await self._save_entity_mentions(
                            entity_id=node.id,
                            extracted=extracted,
                            extraction_result=extraction_result,
                        )

            except Exception as e:
                logger.warning(
                    "mig_save_entity_failed",
                    entity_name=extracted.canonical_name,
                    error=str(e),
                )
                continue

        logger.info(
            "mig_entities_saved",
            matter_id=matter_id,
            input_count=len(extraction_result.entities),
            saved_count=len(saved_nodes),
        )

        return saved_nodes

    async def _find_existing_entity(
        self,
        matter_id: str,
        canonical_name: str,
        entity_type: EntityType,
    ) -> dict | None:
        """Find existing entity by canonical name and type."""
        def _query():
            return (
                self.client.table("identity_nodes")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("entity_type", entity_type.value)
                .ilike("canonical_name", canonical_name)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return response.data[0]
        return None

    async def _create_entity_node(
        self,
        matter_id: str,
        extracted: ExtractedEntity,
    ) -> EntityNode | None:
        """Create new entity node in database."""
        metadata = {
            "roles": extracted.roles,
            "aliases_found": [m.text for m in extracted.mentions if m.text != extracted.canonical_name],
            "first_extraction_confidence": extracted.confidence,
        }

        def _insert():
            return (
                self.client.table("identity_nodes")
                .insert({
                    "matter_id": matter_id,
                    "canonical_name": extracted.canonical_name,
                    "entity_type": extracted.type.value,
                    "metadata": metadata,
                    "mention_count": len(extracted.mentions) or 1,
                })
                .execute()
            )

        response = await asyncio.to_thread(_insert)

        if response.data:
            return self._db_row_to_entity_node(response.data[0])

        logger.warning(
            "mig_create_entity_failed",
            canonical_name=extracted.canonical_name,
        )
        return None

    async def _update_entity_mention_count(
        self,
        entity_id: str,
        matter_id: str,
        additional_mentions: int,
    ) -> dict | None:
        """Increment mention count for existing entity."""
        # First get current count
        def _get_current():
            return (
                self.client.table("identity_nodes")
                .select("mention_count")
                .eq("id", entity_id)
                .eq("matter_id", matter_id)
                .limit(1)
                .execute()
            )

        current = await asyncio.to_thread(_get_current)

        if not current.data:
            return None

        new_count = (current.data[0].get("mention_count", 0) or 0) + additional_mentions

        def _update():
            return (
                self.client.table("identity_nodes")
                .update({
                    "mention_count": new_count,
                    "updated_at": datetime.utcnow().isoformat(),
                })
                .eq("id", entity_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            return response.data[0]
        return None

    async def _save_entity_mentions(
        self,
        entity_id: str,
        extracted: ExtractedEntity,
        extraction_result: EntityExtractionResult,
    ) -> None:
        """Save entity mentions to entity_mentions table."""
        if not extracted.mentions:
            return

        mentions_to_insert = []
        for mention in extracted.mentions:
            mentions_to_insert.append({
                "entity_id": entity_id,
                "document_id": extraction_result.source_document_id,
                "chunk_id": extraction_result.source_chunk_id,
                "page_number": extraction_result.page_number,
                "mention_text": mention.text,
                "context": mention.context,
                "confidence": extracted.confidence,
                "bbox_ids": [],  # Will be linked later if available
            })

        if mentions_to_insert:
            try:
                def _insert_mentions():
                    return self.client.table("entity_mentions").insert(mentions_to_insert).execute()

                await asyncio.to_thread(_insert_mentions)
            except Exception as e:
                logger.warning(
                    "mig_save_mentions_failed",
                    entity_id=entity_id,
                    error=str(e),
                )

    def _db_row_to_entity_node(self, row: dict) -> EntityNode:
        """Convert database row to EntityNode model."""
        return EntityNode(
            id=row["id"],
            matter_id=row["matter_id"],
            canonical_name=row["canonical_name"],
            entity_type=EntityType(row["entity_type"]),
            metadata=row.get("metadata", {}),
            mention_count=row.get("mention_count", 0) or 0,
            aliases=row.get("aliases", []) or [],
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )

    # =========================================================================
    # Entity Edge Operations
    # =========================================================================

    async def save_edges(
        self,
        matter_id: str,
        edges: list[EntityEdgeCreate],
    ) -> list[EntityEdge]:
        """Save relationship edges to identity_edges table.

        Args:
            matter_id: Matter UUID for isolation.
            edges: List of edges to create.

        Returns:
            List of created EntityEdge objects.
        """
        if not edges:
            return []

        saved_edges: list[EntityEdge] = []

        for edge in edges:
            try:
                def _insert_edge():
                    return (
                        self.client.table("identity_edges")
                        .insert({
                            "matter_id": matter_id,
                            "source_node_id": edge.source_entity_id,
                            "target_node_id": edge.target_entity_id,
                            "relationship_type": edge.relationship_type.value,
                            "confidence": edge.confidence,
                            "metadata": edge.metadata,
                        })
                        .execute()
                    )

                response = await asyncio.to_thread(_insert_edge)

                if response.data:
                    saved_edges.append(self._db_row_to_entity_edge(response.data[0]))

            except Exception as e:
                # Likely duplicate edge (unique constraint)
                logger.debug(
                    "mig_save_edge_skipped",
                    source=edge.source_entity_id,
                    target=edge.target_entity_id,
                    error=str(e),
                )
                continue

        logger.info(
            "mig_edges_saved",
            matter_id=matter_id,
            input_count=len(edges),
            saved_count=len(saved_edges),
        )

        return saved_edges

    def _db_row_to_entity_edge(self, row: dict) -> EntityEdge:
        """Convert database row to EntityEdge model."""
        from app.models.entity import RelationshipType

        return EntityEdge(
            id=row["id"],
            matter_id=row["matter_id"],
            source_entity_id=row["source_node_id"],
            target_entity_id=row["target_node_id"],
            relationship_type=RelationshipType(row["relationship_type"]),
            confidence=row.get("confidence", 1.0) or 1.0,
            metadata=row.get("metadata", {}),
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        )

    # =========================================================================
    # Entity Mention Operations
    # =========================================================================

    async def save_mentions(
        self,
        entity_id: str,
        mentions: list[EntityMentionCreate],
    ) -> list[EntityMention]:
        """Save entity mentions to entity_mentions table.

        Args:
            entity_id: Entity UUID.
            mentions: List of mentions to create.

        Returns:
            List of created EntityMention objects.
        """
        if not mentions:
            return []

        mentions_to_insert = [
            {
                "entity_id": entity_id,
                "document_id": m.document_id,
                "chunk_id": m.chunk_id,
                "page_number": m.page_number,
                "bbox_ids": m.bbox_ids,
                "mention_text": m.mention_text,
                "context": m.context,
                "confidence": m.confidence,
            }
            for m in mentions
        ]

        try:
            def _insert_mentions():
                return (
                    self.client.table("entity_mentions")
                    .insert(mentions_to_insert)
                    .execute()
                )

            response = await asyncio.to_thread(_insert_mentions)

            if response.data:
                return [self._db_row_to_entity_mention(row) for row in response.data]

        except Exception as e:
            logger.warning(
                "mig_save_mentions_failed",
                entity_id=entity_id,
                count=len(mentions),
                error=str(e),
            )

        return []

    def _db_row_to_entity_mention(self, row: dict) -> EntityMention:
        """Convert database row to EntityMention model."""
        return EntityMention(
            id=row["id"],
            entity_id=row["entity_id"],
            document_id=row["document_id"],
            chunk_id=row.get("chunk_id"),
            page_number=row.get("page_number"),
            bbox_ids=row.get("bbox_ids", []) or [],
            mention_text=row["mention_text"],
            context=row.get("context"),
            confidence=row.get("confidence", 1.0) or 1.0,
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        )

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_entity(
        self,
        entity_id: str,
        matter_id: str,
    ) -> EntityNode | None:
        """Get single entity by ID with matter validation.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.

        Returns:
            EntityNode if found, None otherwise.
        """
        def _query():
            return (
                self.client.table("identity_nodes")
                .select("*")
                .eq("id", entity_id)
                .eq("matter_id", matter_id)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return self._db_row_to_entity_node(response.data[0])
        return None

    async def get_entities_by_matter(
        self,
        matter_id: str,
        entity_type: EntityType | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[EntityNode], int]:
        """Get all entities in a matter with optional type filter.

        Args:
            matter_id: Matter UUID for isolation.
            entity_type: Optional filter by entity type.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (entities list, total count).
        """
        def _query():
            # Build query
            query = (
                self.client.table("identity_nodes")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
            )

            if entity_type:
                query = query.eq("entity_type", entity_type.value)

            # Order by mention_count descending (most mentioned first)
            query = query.order("mention_count", desc=True)

            # Pagination
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        entities = [self._db_row_to_entity_node(row) for row in (response.data or [])]
        total = response.count or 0

        return entities, total

    async def get_entity_mentions(
        self,
        entity_id: str,
        matter_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[EntityMention], int]:
        """Get all mentions of an entity with matter validation.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation (validated via entity).
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (mentions list, total count).
        """
        # First validate entity belongs to matter
        entity = await self.get_entity(entity_id, matter_id)
        if not entity:
            return [], 0

        # Get mentions
        offset = (page - 1) * per_page

        def _query():
            return (
                self.client.table("entity_mentions")
                .select("*", count="exact")
                .eq("entity_id", entity_id)
                .order("created_at", desc=True)
                .range(offset, offset + per_page - 1)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        mentions = [self._db_row_to_entity_mention(row) for row in (response.data or [])]
        total = response.count or 0

        return mentions, total

    async def get_entity_relationships(
        self,
        entity_id: str,
        matter_id: str,
    ) -> list[EntityEdge]:
        """Get all relationships involving an entity.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.

        Returns:
            List of EntityEdge objects.
        """
        # First validate entity belongs to matter
        entity = await self.get_entity(entity_id, matter_id)
        if not entity:
            return []

        # Get edges where entity is source or target
        def _query_source():
            return (
                self.client.table("identity_edges")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("source_node_id", entity_id)
                .execute()
            )

        def _query_target():
            return (
                self.client.table("identity_edges")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("target_node_id", entity_id)
                .execute()
            )

        # Run both queries concurrently
        source_response, target_response = await asyncio.gather(
            asyncio.to_thread(_query_source),
            asyncio.to_thread(_query_target),
        )

        edges = []
        seen_ids = set()

        for row in (source_response.data or []) + (target_response.data or []):
            if row["id"] not in seen_ids:
                edges.append(self._db_row_to_entity_edge(row))
                seen_ids.add(row["id"])

        return edges

    async def increment_mention_count(
        self,
        entity_id: str,
        matter_id: str,
        increment: int = 1,
    ) -> None:
        """Increment mention count for an entity.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            increment: Amount to increment (default 1).
        """
        await self._update_entity_mention_count(
            entity_id=entity_id,
            matter_id=matter_id,
            additional_mentions=increment,
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_mig_graph_service() -> MIGGraphService:
    """Get singleton MIG graph service instance.

    Returns:
        MIGGraphService instance.
    """
    return MIGGraphService()
