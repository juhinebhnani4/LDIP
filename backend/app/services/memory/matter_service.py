"""Matter Memory Service - High-level facade for matter-level memory.

Story 7-3: Matter Memory PostgreSQL JSONB Storage
Story 7-4: Key Findings and Research Notes

Provides high-level orchestration for matter memory operations:
- Query history logging
- Timeline cache management
- Entity graph cache management
- Cache invalidation on document uploads
- Key findings management (Story 7-4)
- Research notes management (Story 7-4)

This service sits above MatterMemoryRepository and adds business logic.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog

from app.models.memory import (
    CachedEntity,
    EntityGraphCache,
    EntityRelationship,
    FindingEvidence,
    FindingType,
    KeyFinding,
    KeyFindings,
    QueryHistory,
    QueryHistoryEntry,
    ResearchNote,
    ResearchNotes,
    TimelineCache,
    TimelineCacheEntry,
)
from app.services.memory.matter import (
    MatterMemoryRepository,
    get_matter_memory_repository,
    is_cache_stale,
)

logger = structlog.get_logger(__name__)


class MatterMemoryService:
    """High-level service for matter memory operations.

    Story 7-3: Facade providing business logic over repository.

    This service:
    - Orchestrates repository calls with business logic
    - Handles cache staleness detection
    - Provides convenience methods for common patterns
    - Manages cache invalidation hooks
    """

    def __init__(
        self,
        repository: MatterMemoryRepository | None = None,
    ) -> None:
        """Initialize matter memory service.

        Args:
            repository: Optional repository instance (injected for testing).
        """
        self._repository = repository or get_matter_memory_repository()

    # =========================================================================
    # Query History Methods (AC #2)
    # =========================================================================

    async def log_query(
        self,
        matter_id: str,
        query_id: str,
        query_text: str,
        asked_by: str,
        *,
        normalized_query: str | None = None,
        response_summary: str = "",
        engines_used: list[str] | None = None,
        confidence: float | None = None,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> str:
        """Log a query to matter history.

        Story 7-3: Convenience method for query logging.
        Creates QueryHistoryEntry and appends to history.

        Args:
            matter_id: Matter UUID.
            query_id: Unique query UUID.
            query_text: Original query text.
            asked_by: User UUID who asked.
            normalized_query: Optional normalized query for cache.
            response_summary: Brief response summary.
            engines_used: List of engines used.
            confidence: Response confidence 0-100.
            tokens_used: Total tokens consumed.
            cost_usd: Total cost in USD.

        Returns:
            Record UUID from database.
        """
        entry = QueryHistoryEntry(
            query_id=query_id,
            query_text=query_text,
            normalized_query=normalized_query,
            asked_by=asked_by,
            asked_at=datetime.now(UTC).isoformat(),
            response_summary=response_summary,
            engines_used=engines_used or [],
            confidence=confidence,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        result = await self._repository.append_query(matter_id, entry)

        logger.info(
            "query_logged",
            matter_id=matter_id,
            query_id=query_id,
            engines=engines_used,
        )

        return result

    async def get_query_history(
        self,
        matter_id: str,
        limit: int = 100,
    ) -> QueryHistory:
        """Get query history for a matter.

        Args:
            matter_id: Matter UUID.
            limit: Maximum entries to return.

        Returns:
            QueryHistory with entries.
        """
        return await self._repository.get_query_history(matter_id, limit)

    async def mark_query_verified(
        self,
        matter_id: str,
        query_id: str,
        verified_by: str,
    ) -> bool:
        """Mark a query as verified by attorney.

        Story 7-3: Updates verification status in query history.

        Warning: This uses read-modify-write pattern which is not atomic.
        For high-concurrency scenarios, consider implementing a DB function
        like `update_query_entry(p_matter_id, p_query_id, p_updates jsonb)`
        that atomically updates a specific entry in the JSONB array.

        TODO: If verification volume becomes high (>10 verifications/minute),
        create atomic DB function to prevent race conditions.

        Args:
            matter_id: Matter UUID.
            query_id: Query UUID to verify.
            verified_by: User UUID who verified.

        Returns:
            True if found and updated, False if not found.
        """
        # Fetch full history - limited to prevent memory issues
        # TODO: For very large histories, consider DB-side update
        history = await self._repository.get_query_history(matter_id, limit=10000)

        found = False
        for entry in history.entries:
            if entry.query_id == query_id:
                entry.verified = True
                entry.verified_by = verified_by
                entry.verified_at = datetime.now(UTC).isoformat()
                found = True
                break

        if not found:
            logger.warning(
                "query_not_found_for_verification",
                matter_id=matter_id,
                query_id=query_id,
            )
            return False

        # Update the full history (upsert)
        await self._repository.set_memory(
            matter_id,
            "query_history",
            {"entries": [e.model_dump(mode="json") for e in history.entries]},
        )

        logger.info(
            "query_marked_verified",
            matter_id=matter_id,
            query_id=query_id,
            verified_by=verified_by,
        )

        return True

    # =========================================================================
    # Timeline Cache Methods (AC #3)
    # =========================================================================

    async def get_or_build_timeline(
        self,
        matter_id: str,
        last_document_upload: str | None = None,
        *,
        builder_fn: Callable[[str], Awaitable[list[TimelineCacheEntry]]] | None = None,
    ) -> TimelineCache | None:
        """Get timeline cache, building if stale or missing.

        Story 7-3: Check cache, rebuild if stale/missing.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp for staleness.
            builder_fn: Optional async function to build timeline.
                        Should return list of TimelineCacheEntry.

        Returns:
            TimelineCache if available, None if no cache and no builder.
        """
        cache = await self._repository.get_timeline_cache(matter_id)

        # Check if cache is valid
        if cache and not is_cache_stale(cache.cached_at, last_document_upload):
            logger.debug(
                "timeline_cache_hit",
                matter_id=matter_id,
                event_count=cache.event_count,
            )
            return cache

        # Cache is stale or missing
        if builder_fn is None:
            logger.debug(
                "timeline_cache_miss_no_builder",
                matter_id=matter_id,
            )
            return None

        # Build new cache
        logger.info(
            "timeline_cache_building",
            matter_id=matter_id,
            reason="stale" if cache else "missing",
        )

        events: list[TimelineCacheEntry] = await builder_fn(matter_id)

        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.event_date)

        new_cache = TimelineCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=(cache.version + 1) if cache else 1,
            events=sorted_events,
            date_range_start=sorted_events[0].event_date if sorted_events else None,
            date_range_end=sorted_events[-1].event_date if sorted_events else None,
            event_count=len(sorted_events),
        )

        await self._repository.set_timeline_cache(matter_id, new_cache)

        logger.info(
            "timeline_cache_built",
            matter_id=matter_id,
            event_count=new_cache.event_count,
        )

        return new_cache

    async def set_timeline_cache(
        self,
        matter_id: str,
        events: list[TimelineCacheEntry],
        last_document_upload: str | None = None,
    ) -> TimelineCache:
        """Set timeline cache with provided events.

        Args:
            matter_id: Matter UUID.
            events: Timeline events to cache.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            Created TimelineCache.
        """
        # Get current version if exists
        current = await self._repository.get_timeline_cache(matter_id)
        version = (current.version + 1) if current else 1

        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.event_date)

        cache = TimelineCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=version,
            events=sorted_events,
            date_range_start=sorted_events[0].event_date if sorted_events else None,
            date_range_end=sorted_events[-1].event_date if sorted_events else None,
            event_count=len(sorted_events),
        )

        await self._repository.set_timeline_cache(matter_id, cache)

        return cache

    # =========================================================================
    # Entity Graph Cache Methods (AC #4)
    # =========================================================================

    async def get_or_build_entity_graph(
        self,
        matter_id: str,
        last_document_upload: str | None = None,
        *,
        builder_fn: Callable[
            [str], Awaitable[tuple[dict[str, CachedEntity], list[EntityRelationship]]]
        ]
        | None = None,
    ) -> EntityGraphCache | None:
        """Get entity graph cache, building if stale or missing.

        Story 7-3: Check cache, rebuild if stale/missing.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp for staleness.
            builder_fn: Optional async function to build graph.
                        Should return tuple (entities_dict, relationships_list).

        Returns:
            EntityGraphCache if available, None if no cache and no builder.
        """
        cache = await self._repository.get_entity_graph_cache(matter_id)

        # Check if cache is valid
        if cache and not is_cache_stale(cache.cached_at, last_document_upload):
            logger.debug(
                "entity_graph_cache_hit",
                matter_id=matter_id,
                entity_count=cache.entity_count,
            )
            return cache

        # Cache is stale or missing
        if builder_fn is None:
            logger.debug(
                "entity_graph_cache_miss_no_builder",
                matter_id=matter_id,
            )
            return None

        # Build new cache
        logger.info(
            "entity_graph_cache_building",
            matter_id=matter_id,
            reason="stale" if cache else "missing",
        )

        entities, relationships = await builder_fn(matter_id)

        new_cache = EntityGraphCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=(cache.version + 1) if cache else 1,
            entities=entities,
            relationships=relationships,
            entity_count=len(entities),
            relationship_count=len(relationships),
        )

        await self._repository.set_entity_graph_cache(matter_id, new_cache)

        logger.info(
            "entity_graph_cache_built",
            matter_id=matter_id,
            entity_count=new_cache.entity_count,
            relationship_count=new_cache.relationship_count,
        )

        return new_cache

    async def set_entity_graph_cache(
        self,
        matter_id: str,
        entities: dict[str, CachedEntity],
        relationships: list[EntityRelationship],
        last_document_upload: str | None = None,
    ) -> EntityGraphCache:
        """Set entity graph cache with provided data.

        Args:
            matter_id: Matter UUID.
            entities: Map of entity_id -> CachedEntity.
            relationships: List of EntityRelationship.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            Created EntityGraphCache.
        """
        # Get current version if exists
        current = await self._repository.get_entity_graph_cache(matter_id)
        version = (current.version + 1) if current else 1

        cache = EntityGraphCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=version,
            entities=entities,
            relationships=relationships,
            entity_count=len(entities),
            relationship_count=len(relationships),
        )

        await self._repository.set_entity_graph_cache(matter_id, cache)

        return cache

    # =========================================================================
    # Cache Invalidation (Task 4)
    # =========================================================================
    #
    # INTEGRATION POINT (Task 4.2 Documentation):
    # This method should be called by the Document Upload Service after successful
    # document upload to invalidate stale caches. Integration example:
    #
    #   from app.services.memory import get_matter_memory_service
    #
    #   async def upload_document(matter_id: str, file: UploadFile) -> Document:
    #       # ... upload logic ...
    #       doc = await save_document(matter_id, file)
    #
    #       # Invalidate caches after successful upload
    #       memory_service = get_matter_memory_service()
    #       await memory_service.invalidate_matter_caches(matter_id)
    #
    #       return doc
    #
    # TODO: Wire this into app/api/routes/documents.py upload_document endpoint
    # =========================================================================

    async def invalidate_matter_caches(
        self,
        matter_id: str,
    ) -> dict[str, bool]:
        """Invalidate all matter caches (timeline and entity graph).

        Story 7-3: Task 4.1 - Called when documents are uploaded.

        Integration Point:
            Document upload service should call this after successful uploads.
            See Task 4.2 documentation in class comment above.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dict with deletion status for each cache type.
        """
        timeline_deleted = await self._repository.invalidate_timeline_cache(matter_id)
        entity_graph_deleted = await self._repository.invalidate_entity_graph_cache(
            matter_id
        )

        logger.info(
            "matter_caches_invalidated",
            matter_id=matter_id,
            timeline_deleted=timeline_deleted,
            entity_graph_deleted=entity_graph_deleted,
        )

        return {
            "timeline_cache": timeline_deleted,
            "entity_graph_cache": entity_graph_deleted,
        }

    async def is_timeline_stale(
        self,
        matter_id: str,
        last_document_upload: str,
    ) -> bool:
        """Check if timeline cache is stale.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            True if cache is stale or missing.
        """
        cache = await self._repository.get_timeline_cache(matter_id)
        if not cache:
            return True
        return is_cache_stale(cache.cached_at, last_document_upload)

    async def is_entity_graph_stale(
        self,
        matter_id: str,
        last_document_upload: str,
    ) -> bool:
        """Check if entity graph cache is stale.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            True if cache is stale or missing.
        """
        cache = await self._repository.get_entity_graph_cache(matter_id)
        if not cache:
            return True
        return is_cache_stale(cache.cached_at, last_document_upload)

    # =========================================================================
    # Story 7-4: Key Findings Methods (AC #1)
    # =========================================================================

    async def create_key_finding(
        self,
        matter_id: str,
        finding_type: FindingType,
        description: str,
        created_by: str,
        *,
        evidence: list[FindingEvidence] | None = None,
        notes: str = "",
        confidence: float = 0.0,
        source_engine: str | None = None,
        source_query_id: str | None = None,
    ) -> KeyFinding:
        """Create a new key finding.

        Story 7-4: AC #1 - High-level convenience method.

        Args:
            matter_id: Matter UUID.
            finding_type: Type of finding.
            description: Finding description.
            created_by: User UUID who created.
            evidence: Optional list of evidence items.
            notes: Optional attorney notes.
            confidence: Finding confidence 0-100.
            source_engine: Engine that generated finding (if automated).
            source_query_id: Query that generated finding.

        Returns:
            Created KeyFinding.
        """
        finding = KeyFinding(
            finding_id=str(uuid.uuid4()),
            finding_type=finding_type,
            description=description,
            evidence=evidence or [],
            notes=notes,
            confidence=confidence,
            created_at=datetime.now(UTC).isoformat(),
            created_by=created_by,
            source_engine=source_engine,
            source_query_id=source_query_id,
        )

        await self._repository.add_key_finding(matter_id, finding)

        logger.info(
            "key_finding_created",
            matter_id=matter_id,
            finding_id=finding.finding_id,
            finding_type=finding_type,
        )

        return finding

    async def get_key_findings(
        self,
        matter_id: str,
    ) -> KeyFindings:
        """Get all key findings for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            KeyFindings container.
        """
        return await self._repository.get_key_findings(matter_id)

    async def get_key_finding(
        self,
        matter_id: str,
        finding_id: str,
    ) -> KeyFinding | None:
        """Get a single key finding by ID.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding UUID.

        Returns:
            KeyFinding if found, None otherwise.
        """
        return await self._repository.get_key_finding_by_id(matter_id, finding_id)

    async def verify_key_finding(
        self,
        matter_id: str,
        finding_id: str,
        verified_by: str,
    ) -> bool:
        """Mark a key finding as verified.

        Story 7-4: AC #1 - Attorney verification workflow.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding to verify.
            verified_by: User UUID who verified.

        Returns:
            True if updated, False if not found.
        """
        result = await self._repository.update_key_finding(
            matter_id,
            finding_id,
            {
                "verified_by": verified_by,
                "verified_at": datetime.now(UTC).isoformat(),
            },
        )

        if result:
            logger.info(
                "key_finding_verified",
                matter_id=matter_id,
                finding_id=finding_id,
                verified_by=verified_by,
            )

        return result

    async def update_key_finding(
        self,
        matter_id: str,
        finding_id: str,
        *,
        description: str | None = None,
        notes: str | None = None,
        confidence: float | None = None,
        evidence: list[FindingEvidence] | None = None,
    ) -> bool:
        """Update a key finding.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding to update.
            description: New description (optional).
            notes: New notes (optional).
            confidence: New confidence (optional).
            evidence: New evidence list (optional).

        Returns:
            True if updated, False if not found.
        """
        updates: dict = {}
        if description is not None:
            updates["description"] = description
        if notes is not None:
            updates["notes"] = notes
        if confidence is not None:
            updates["confidence"] = confidence
        if evidence is not None:
            updates["evidence"] = [e.model_dump() for e in evidence]

        if not updates:
            return False

        return await self._repository.update_key_finding(matter_id, finding_id, updates)

    async def delete_key_finding(
        self,
        matter_id: str,
        finding_id: str,
    ) -> bool:
        """Delete a key finding.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding to delete.

        Returns:
            True if deleted, False if not found.
        """
        return await self._repository.delete_key_finding(matter_id, finding_id)

    async def get_verified_findings(
        self,
        matter_id: str,
    ) -> list[KeyFinding]:
        """Get only verified key findings.

        Story 7-4: Convenience method for verified findings.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of verified KeyFinding objects.
        """
        findings = await self._repository.get_key_findings(matter_id)
        return [f for f in findings.findings if f.verified_by is not None]

    async def get_findings_by_type(
        self,
        matter_id: str,
        finding_type: FindingType,
    ) -> list[KeyFinding]:
        """Get key findings filtered by type.

        Args:
            matter_id: Matter UUID.
            finding_type: Type to filter by.

        Returns:
            List of matching KeyFinding objects.
        """
        findings = await self._repository.get_key_findings(matter_id)
        return [f for f in findings.findings if f.finding_type == finding_type]

    # =========================================================================
    # Story 7-4: Research Notes Methods (AC #2)
    # =========================================================================

    async def create_research_note(
        self,
        matter_id: str,
        title: str,
        created_by: str,
        *,
        content: str = "",
        tags: list[str] | None = None,
        linked_findings: list[str] | None = None,
    ) -> ResearchNote:
        """Create a new research note.

        Story 7-4: AC #2 - High-level convenience method.

        Args:
            matter_id: Matter UUID.
            title: Note title.
            created_by: User UUID who created.
            content: Note content (markdown).
            tags: Optional tags for categorization.
            linked_findings: Optional finding IDs to link.

        Returns:
            Created ResearchNote.
        """
        note = ResearchNote(
            note_id=str(uuid.uuid4()),
            title=title,
            content=content,
            created_by=created_by,
            created_at=datetime.now(UTC).isoformat(),
            tags=tags or [],
            linked_findings=linked_findings or [],
        )

        await self._repository.add_research_note(matter_id, note)

        logger.info(
            "research_note_created",
            matter_id=matter_id,
            note_id=note.note_id,
            title=title,
        )

        return note

    async def get_research_notes(
        self,
        matter_id: str,
    ) -> ResearchNotes:
        """Get all research notes for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            ResearchNotes container.
        """
        return await self._repository.get_research_notes(matter_id)

    async def get_research_note(
        self,
        matter_id: str,
        note_id: str,
    ) -> ResearchNote | None:
        """Get a single research note by ID.

        Args:
            matter_id: Matter UUID.
            note_id: Note UUID.

        Returns:
            ResearchNote if found, None otherwise.
        """
        return await self._repository.get_research_note_by_id(matter_id, note_id)

    async def update_research_note(
        self,
        matter_id: str,
        note_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        linked_findings: list[str] | None = None,
    ) -> bool:
        """Update a research note.

        Args:
            matter_id: Matter UUID.
            note_id: Note to update.
            title: New title (optional).
            content: New content (optional).
            tags: New tags (optional).
            linked_findings: New linked findings (optional).

        Returns:
            True if updated, False if not found.
        """
        updates: dict = {}
        if title is not None:
            updates["title"] = title
        if content is not None:
            updates["content"] = content
        if tags is not None:
            updates["tags"] = tags
        if linked_findings is not None:
            updates["linked_findings"] = linked_findings

        if not updates:
            return False

        return await self._repository.update_research_note(matter_id, note_id, updates)

    async def delete_research_note(
        self,
        matter_id: str,
        note_id: str,
    ) -> bool:
        """Delete a research note.

        Args:
            matter_id: Matter UUID.
            note_id: Note to delete.

        Returns:
            True if deleted, False if not found.
        """
        return await self._repository.delete_research_note(matter_id, note_id)

    async def search_research_notes(
        self,
        matter_id: str,
        *,
        tag: str | None = None,
        title_contains: str | None = None,
    ) -> list[ResearchNote]:
        """Search research notes by tag or title.

        Args:
            matter_id: Matter UUID.
            tag: Tag to filter by.
            title_contains: Substring to search in title.

        Returns:
            List of matching ResearchNote objects.
        """
        return await self._repository.search_research_notes(
            matter_id, tag=tag, title_contains=title_contains
        )

    async def get_notes_for_finding(
        self,
        matter_id: str,
        finding_id: str,
    ) -> list[ResearchNote]:
        """Get research notes linked to a specific finding.

        Story 7-4: AC #3 - Cross-reference support.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding UUID to search for.

        Returns:
            List of ResearchNote objects that reference this finding.
        """
        notes = await self._repository.get_research_notes(matter_id)
        return [n for n in notes.notes if finding_id in n.linked_findings]


# =============================================================================
# Factory Function
# =============================================================================

_matter_memory_service: MatterMemoryService | None = None


def get_matter_memory_service(
    repository: MatterMemoryRepository | None = None,
) -> MatterMemoryService:
    """Get or create MatterMemoryService instance.

    Factory function following project pattern.

    Args:
        repository: Optional repository for injection (only used on first call).

    Returns:
        MatterMemoryService instance.

    Note:
        Repository injection only works on first call. To inject a different
        repository, call reset_matter_memory_service() first.
    """
    global _matter_memory_service

    if _matter_memory_service is None:
        _matter_memory_service = MatterMemoryService(repository)
    elif repository is not None:
        logger.warning(
            "matter_memory_service_repository_injection_ignored",
            reason="singleton already created - call reset_matter_memory_service() first",
        )

    return _matter_memory_service


def reset_matter_memory_service() -> None:
    """Reset singleton (for testing)."""
    global _matter_memory_service
    _matter_memory_service = None
    logger.debug("matter_memory_service_reset")
