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
from datetime import UTC, datetime
from functools import lru_cache

import structlog

from app.models.entity import (
    EntityEdge,
    EntityEdgeCreate,
    EntityExtractionResult,
    EntityMention,
    EntityMentionCreate,
    EntityNode,
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
                    "updated_at": datetime.now(UTC).isoformat(),
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

    # =========================================================================
    # Alias Operations (Story 2c-2)
    # =========================================================================

    async def create_alias_edge(
        self,
        matter_id: str,
        source_id: str,
        target_id: str,
        confidence: float,
        metadata: dict | None = None,
    ) -> EntityEdge | None:
        """Create an ALIAS_OF edge between two entities.

        Args:
            matter_id: Matter UUID for isolation.
            source_id: Source entity UUID (the alias).
            target_id: Target entity UUID (the canonical entity).
            confidence: Confidence score (0-1).
            metadata: Optional metadata about the alias link.

        Returns:
            Created EntityEdge or None if failed.
        """
        from app.models.entity import RelationshipType

        def _insert():
            return (
                self.client.table("identity_edges")
                .insert({
                    "matter_id": matter_id,
                    "source_node_id": source_id,
                    "target_node_id": target_id,
                    "relationship_type": RelationshipType.ALIAS_OF.value,
                    "confidence": confidence,
                    "metadata": metadata or {},
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                logger.info(
                    "mig_alias_edge_created",
                    matter_id=matter_id,
                    source_id=source_id,
                    target_id=target_id,
                    confidence=confidence,
                )
                return self._db_row_to_entity_edge(response.data[0])

        except Exception as e:
            # Likely duplicate (unique constraint)
            logger.debug(
                "mig_alias_edge_exists",
                source_id=source_id,
                target_id=target_id,
                error=str(e),
            )

        return None

    async def get_all_aliases(
        self,
        entity_id: str,
        matter_id: str,
    ) -> list[EntityNode]:
        """Get all aliases of an entity (following ALIAS_OF edges).

        Includes both direct aliases (where entity is source/target)
        and transitive aliases.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.

        Returns:
            List of EntityNode objects representing all aliases.
        """
        from app.models.entity import RelationshipType

        # Validate entity exists in matter
        entity = await self.get_entity(entity_id, matter_id)
        if not entity:
            return []

        # Get all ALIAS_OF edges involving this entity
        def _query_aliases():
            return (
                self.client.table("identity_edges")
                .select("source_node_id, target_node_id")
                .eq("matter_id", matter_id)
                .eq("relationship_type", RelationshipType.ALIAS_OF.value)
                .or_(f"source_node_id.eq.{entity_id},target_node_id.eq.{entity_id}")
                .execute()
            )

        response = await asyncio.to_thread(_query_aliases)

        if not response.data:
            return []

        # Collect all related entity IDs
        related_ids: set[str] = set()
        for row in response.data:
            related_ids.add(row["source_node_id"])
            related_ids.add(row["target_node_id"])

        # Remove the original entity
        related_ids.discard(entity_id)

        if not related_ids:
            return []

        # Fetch all alias entities
        def _fetch_entities():
            return (
                self.client.table("identity_nodes")
                .select("*")
                .eq("matter_id", matter_id)
                .in_("id", list(related_ids))
                .execute()
            )

        entities_response = await asyncio.to_thread(_fetch_entities)

        if not entities_response.data:
            return []

        return [self._db_row_to_entity_node(row) for row in entities_response.data]

    async def get_canonical_entity(
        self,
        alias_entity_id: str,
        matter_id: str,
    ) -> EntityNode | None:
        """Get the canonical entity for an alias.

        Follows ALIAS_OF edges to find the primary/canonical entity.
        Uses a simple heuristic: entity with most mentions is canonical.

        Args:
            alias_entity_id: Alias entity UUID.
            matter_id: Matter UUID for isolation.

        Returns:
            Canonical EntityNode or the entity itself if no aliases.
        """
        # Get the entity and all its aliases
        entity = await self.get_entity(alias_entity_id, matter_id)
        if not entity:
            return None

        aliases = await self.get_all_aliases(alias_entity_id, matter_id)

        if not aliases:
            return entity

        # Find entity with most mentions (canonical)
        all_entities = [entity] + aliases
        canonical = max(all_entities, key=lambda e: e.mention_count)

        return canonical

    async def update_entity_aliases_array(
        self,
        entity_id: str,
        matter_id: str,
        aliases: list[str],
    ) -> EntityNode | None:
        """Update the aliases array on an entity.

        The aliases array stores name variants as strings
        for quick lookup without traversing edges.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            aliases: List of alias name strings.

        Returns:
            Updated EntityNode or None if failed.

        Note:
            Aliases are deduplicated before storage to prevent race condition
            duplicates from concurrent operations.
        """
        # Deduplicate aliases while preserving order (first occurrence wins)
        seen = set()
        unique_aliases = []
        for alias in aliases:
            if alias not in seen:
                seen.add(alias)
                unique_aliases.append(alias)

        def _update():
            return (
                self.client.table("identity_nodes")
                .update({
                    "aliases": unique_aliases,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", entity_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            logger.info(
                "mig_aliases_array_updated",
                entity_id=entity_id,
                alias_count=len(aliases),
            )
            return self._db_row_to_entity_node(response.data[0])

        return None

    async def add_alias_to_entity(
        self,
        entity_id: str,
        matter_id: str,
        alias: str,
    ) -> EntityNode | None:
        """Add a single alias to an entity's aliases array.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            alias: Alias name to add.

        Returns:
            Updated EntityNode or None if failed.

        Note:
            This method checks for namespace collisions - if the alias matches
            the canonical_name of another entity in the same matter, it logs
            a warning. Consider using merge_entities instead for disambiguation.
        """
        # Get current entity
        entity = await self.get_entity(entity_id, matter_id)
        if not entity:
            return None

        # Check for namespace collision: does another entity have this as canonical_name?
        existing_canonical = await self._find_existing_entity(
            matter_id=matter_id,
            canonical_name=alias,
            entity_type=entity.entity_type,
        )
        if existing_canonical and existing_canonical["id"] != entity_id:
            logger.warning(
                "mig_alias_namespace_collision",
                entity_id=entity_id,
                alias=alias,
                conflicting_entity_id=existing_canonical["id"],
                conflicting_canonical_name=existing_canonical["canonical_name"],
                matter_id=matter_id,
                hint="Consider merging entities instead of adding alias",
            )
            # Still allow the alias addition but log the collision

        # Add alias if not already present
        current_aliases = entity.aliases or []
        if alias not in current_aliases:
            current_aliases.append(alias)
            return await self.update_entity_aliases_array(
                entity_id, matter_id, current_aliases
            )

        return entity

    async def remove_alias_from_entity(
        self,
        entity_id: str,
        matter_id: str,
        alias: str,
    ) -> EntityNode | None:
        """Remove a single alias from an entity's aliases array.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            alias: Alias name to remove.

        Returns:
            Updated EntityNode or None if failed.
        """
        entity = await self.get_entity(entity_id, matter_id)
        if not entity:
            return None

        current_aliases = entity.aliases or []
        if alias in current_aliases:
            current_aliases.remove(alias)
            return await self.update_entity_aliases_array(
                entity_id, matter_id, current_aliases
            )

        return entity

    async def get_entities_by_alias(
        self,
        matter_id: str,
        alias: str,
    ) -> list[EntityNode]:
        """Find entities that have the given alias in their aliases array.

        Uses GIN index on aliases column for fast lookup.

        Args:
            matter_id: Matter UUID for isolation.
            alias: Alias name to search for.

        Returns:
            List of EntityNode objects with matching alias.
        """
        def _query():
            return (
                self.client.table("identity_nodes")
                .select("*")
                .eq("matter_id", matter_id)
                .contains("aliases", [alias])
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if not response.data:
            return []

        return [self._db_row_to_entity_node(row) for row in response.data]

    async def sync_aliases_from_edges(
        self,
        entity_id: str,
        matter_id: str,
    ) -> EntityNode | None:
        """Sync the aliases array from ALIAS_OF edges.

        Updates the aliases array on an entity to include
        the canonical_name of all linked alias entities.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.

        Returns:
            Updated EntityNode or None if failed.
        """
        entity = await self.get_entity(entity_id, matter_id)
        if not entity:
            return None

        aliases = await self.get_all_aliases(entity_id, matter_id)

        # Collect alias names
        alias_names = [a.canonical_name for a in aliases]

        # Also include existing aliases that might not be entities
        existing_aliases = entity.aliases or []
        for existing in existing_aliases:
            if existing not in alias_names:
                alias_names.append(existing)

        return await self.update_entity_aliases_array(
            entity_id, matter_id, alias_names
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
