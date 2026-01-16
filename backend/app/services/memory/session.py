"""Session Memory Service for conversation context.

Story 7-1: Session Memory Redis Storage
Story 7-2: Session TTL and Context Restoration

Manages user session context in Redis with:
- 7-day TTL with auto-extension on access (max 30 days)
- Sliding window message history (configurable, default 20)
- Entity tracking for pronoun resolution (configurable limit, default 50)
- Session archival to Matter Memory on expiry/end
- Context restoration from archived sessions

CRITICAL: All session data is scoped by matter_id + user_id
for Layer 3 isolation (Redis key prefix).

Key format: session:{matter_id}:{user_id}:context
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import structlog

from app.core.config import get_settings
from app.models.memory import (
    ArchivedSession,
    SessionContext,
    SessionEntityMention,
    SessionMessage,
)
from app.services.memory.redis_client import get_redis_client
from app.services.memory.redis_keys import (
    MAX_SESSION_LIFETIME,
    SESSION_TTL,
    session_key,
    validate_key_access,
)

if TYPE_CHECKING:
    from app.services.memory.matter import MatterMemoryRepository

logger = structlog.get_logger(__name__)


class SessionMemoryService:
    """Manages session context in Redis.

    Story 7-1: Provides conversation context persistence
    for follow-up questions without repeating context.

    Story 7-2: Adds session archival/restoration and TTL max limit.

    Features:
    - Session creation with 7-day TTL (AC #1)
    - Message history with sliding window (AC #2, #3)
    - Entity tracking for pronoun resolution (AC #4)
    - Auto-extend TTL on session access (max 30 days - Story 7-2)
    - Session archival to Matter Memory on expiry/end (Story 7-2)
    - Context restoration from archived sessions (Story 7-2)
    """

    def __init__(
        self,
        redis_client: Any = None,
        matter_memory: MatterMemoryRepository | None = None,
    ) -> None:
        """Initialize session memory service.

        Args:
            redis_client: Optional Redis client (injected for testing).
            matter_memory: Optional MatterMemoryRepository (injected for testing).
        """
        self._redis = redis_client
        self._matter_memory = matter_memory
        self._initialized = False

    async def _ensure_client(self) -> None:
        """Ensure Redis client is initialized."""
        if self._redis is None:
            self._redis = await get_redis_client()
        self._initialized = True

    async def _ensure_matter_memory(self) -> MatterMemoryRepository:
        """Ensure MatterMemoryRepository is initialized.

        Story 7-2: Lazy initialization of matter memory repository.

        Returns:
            MatterMemoryRepository instance.
        """
        if self._matter_memory is None:
            from app.services.memory.matter import get_matter_memory_repository

            self._matter_memory = get_matter_memory_repository()
        return self._matter_memory

    def _check_max_lifetime(self, context: SessionContext) -> bool:
        """Check if session has reached max lifetime (30 days).

        Story 7-2: Task 2.3 - Helper method to check cumulative lifetime.

        Args:
            context: Session context to check.

        Returns:
            True if max lifetime reached, False otherwise.
        """
        created_at = datetime.fromisoformat(context.created_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        lifetime_seconds = (now - created_at).total_seconds()

        return lifetime_seconds >= MAX_SESSION_LIFETIME

    async def create_session(
        self,
        matter_id: str,
        user_id: str,
    ) -> SessionContext:
        """Create a new session in Redis (AC #1).

        Args:
            matter_id: Matter UUID for isolation.
            user_id: User UUID who owns this session.

        Returns:
            Newly created SessionContext.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        session_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        context = SessionContext(
            session_id=session_id,
            matter_id=matter_id,
            user_id=user_id,
            created_at=now,
            last_activity=now,
            messages=[],
            entities_mentioned={},
            query_count=0,
            ttl_extended_count=0,
        )

        # Store in Redis with 7-day TTL
        key = session_key(matter_id, user_id, "context")
        try:
            await self._redis.setex(
                key,
                SESSION_TTL,
                context.model_dump_json(),
            )
        except Exception as e:
            logger.error(
                "redis_create_session_failed",
                session_id=session_id,
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to create session in Redis: {e}") from e

        logger.info(
            "session_created",
            session_id=session_id,
            matter_id=matter_id,
            user_id=user_id,
            ttl_days=SESSION_TTL // 86400,
        )

        return context

    async def get_session(
        self,
        matter_id: str,
        user_id: str,
        auto_create: bool = True,
        extend_ttl: bool = True,
        restore_from_archive: bool = True,
    ) -> SessionContext | None:
        """Retrieve session context from Redis.

        Story 7-1: Basic session retrieval.
        Story 7-2: Added max lifetime check and archive restoration.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            auto_create: Create new session if not found.
            extend_ttl: Auto-extend TTL on access (sliding expiration).
            restore_from_archive: Try to restore from archive if session not found.

        Returns:
            SessionContext if found, None otherwise.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        key = session_key(matter_id, user_id, "context")

        # Defense-in-depth: validate key belongs to requested matter
        if not validate_key_access(key, matter_id):
            logger.error(
                "session_key_validation_failed",
                key=key,
                matter_id=matter_id,
            )
            raise ValueError("Session key does not match requested matter")

        # Get session data
        try:
            data = await self._redis.get(key)
        except Exception as e:
            logger.error(
                "redis_get_session_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get session from Redis: {e}") from e

        if data is None:
            # Session expired or doesn't exist
            if restore_from_archive:
                # Story 7-2: Try to restore from archived session
                restored = await self.restore_context(matter_id, user_id)
                if restored:
                    return restored

            if auto_create:
                logger.info(
                    "session_not_found_creating",
                    matter_id=matter_id,
                    user_id=user_id,
                )
                return await self.create_session(matter_id, user_id)
            return None

        # Parse session context
        context = SessionContext.model_validate_json(data)

        # Story 7-2: Auto-extend TTL on access (with max lifetime check)
        if extend_ttl and not context.max_ttl_reached:
            # Check if max lifetime reached before extending
            max_lifetime_just_reached = self._check_max_lifetime(context)

            if max_lifetime_just_reached:
                # Max lifetime reached - mark it but DON'T extend TTL
                context.max_ttl_reached = True
                logger.info(
                    "session_max_lifetime_reached",
                    session_id=context.session_id,
                    matter_id=matter_id,
                    ttl_extended_count=context.ttl_extended_count,
                )
                # Update context in Redis WITHOUT extending TTL (use current TTL)
                # Note: We still save the updated max_ttl_reached flag
                try:
                    # Get remaining TTL and use that instead of extending
                    remaining_ttl = await self._redis.ttl(key)
                    if remaining_ttl and remaining_ttl > 0:
                        await self._redis.setex(
                            key,
                            remaining_ttl,  # Keep existing TTL, don't extend
                            context.model_dump_json(),
                        )
                except Exception as e:
                    logger.error(
                        "redis_save_max_ttl_flag_failed",
                        session_id=context.session_id,
                        matter_id=matter_id,
                        error=str(e),
                    )
                    # Non-fatal: flag will be set again on next access
            else:
                # Normal TTL extension
                context.ttl_extended_count += 1
                context.last_activity = datetime.now(UTC).isoformat()

                # Update total_lifetime_days
                created_at = datetime.fromisoformat(
                    context.created_at.replace("Z", "+00:00")
                )
                now = datetime.now(UTC)
                context.total_lifetime_days = (now - created_at).days

                # Update stored context with extended TTL
                try:
                    await self._redis.setex(
                        key,
                        SESSION_TTL,
                        context.model_dump_json(),
                    )
                except Exception as e:
                    logger.error(
                        "redis_extend_ttl_failed",
                        session_id=context.session_id,
                        matter_id=matter_id,
                        error=str(e),
                    )
                    raise RuntimeError(f"Failed to extend session TTL: {e}") from e

                logger.debug(
                    "session_ttl_extended",
                    session_id=context.session_id,
                    matter_id=matter_id,
                    extend_count=context.ttl_extended_count,
                )

        return context

    async def add_message(
        self,
        matter_id: str,
        user_id: str,
        role: str,
        content: str,
        entity_refs: list[str] | None = None,
    ) -> SessionContext:
        """Add a message to session history with sliding window (AC #2, #3).

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            role: Message role ('user' or 'assistant').
            content: Message content.
            entity_refs: Optional entity IDs mentioned.

        Returns:
            Updated SessionContext.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        # Get or create session (extend_ttl=False to avoid duplicate timestamp update)
        context = await self.get_session(
            matter_id, user_id, auto_create=True, extend_ttl=False
        )
        # Note: auto_create=True guarantees non-None return

        # Create message with current timestamp
        now = datetime.now(UTC).isoformat()
        message = SessionMessage(
            role=role,
            content=content,
            timestamp=now,
            entity_refs=entity_refs or [],
        )

        # Add to messages list
        context.messages.append(message)

        # Apply sliding window (max 20 messages)
        context = self._apply_sliding_window(context)

        # Update activity and query count
        context.last_activity = now
        if role == "user":
            context.query_count += 1

        # Save to Redis
        key = session_key(matter_id, user_id, "context")
        try:
            await self._redis.setex(
                key,
                SESSION_TTL,
                context.model_dump_json(),
            )
        except Exception as e:
            logger.error(
                "redis_add_message_failed",
                session_id=context.session_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to add message to session: {e}") from e

        logger.debug(
            "message_added_to_session",
            session_id=context.session_id,
            role=role,
            message_count=len(context.messages),
            query_count=context.query_count,
        )

        return context

    def _apply_sliding_window(
        self,
        context: SessionContext,
    ) -> SessionContext:
        """Apply sliding window to keep max messages (configurable, default 20).

        Task 4: Implements sliding window logic.

        Args:
            context: Session context to modify.

        Returns:
            Modified context with window applied.

        Note:
            This is a local operation on the context object.
            Caller is responsible for persisting changes.
        """
        settings = get_settings()
        max_messages = settings.session_max_messages

        if len(context.messages) <= max_messages:
            return context

        # Remove oldest messages
        removed_count = len(context.messages) - max_messages
        context.messages = context.messages[-max_messages:]

        logger.info(
            "sliding_window_applied",
            session_id=context.session_id,
            removed_count=removed_count,
            retained_count=len(context.messages),
        )

        return context

    def _apply_entity_limit(
        self,
        context: SessionContext,
    ) -> SessionContext:
        """Apply entity limit to prevent unbounded dictionary growth.

        Epic 7 Code Review Fix: Issue #4 & #7 - entities_mentioned dict grows indefinitely.
        Keep only the most recently mentioned entities up to the configured limit.

        Args:
            context: Session context to modify.

        Returns:
            Modified context with entity limit applied.
        """
        settings = get_settings()
        max_entities = settings.session_max_entities

        if len(context.entities_mentioned) <= max_entities:
            return context

        # Sort by last_mentioned timestamp (newest first) and keep top N
        sorted_entities = sorted(
            context.entities_mentioned.items(),
            key=lambda x: x[1].last_mentioned,
            reverse=True,
        )

        # Keep only the most recent entities
        removed_count = len(context.entities_mentioned) - max_entities
        context.entities_mentioned = dict(sorted_entities[:max_entities])

        logger.info(
            "entity_limit_applied",
            session_id=context.session_id,
            removed_count=removed_count,
            retained_count=len(context.entities_mentioned),
            max_entities=max_entities,
        )

        return context

    async def update_entities(
        self,
        matter_id: str,
        user_id: str,
        entities: list[dict[str, Any]],
    ) -> SessionContext:
        """Update entity mentions for pronoun resolution (AC #4).

        Task 5: Implements entity tracking.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            entities: List of entity dicts with id, name, type, aliases.

        Returns:
            Updated SessionContext.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        # Get or create session (extend_ttl=False, we'll update last_activity here)
        context = await self.get_session(
            matter_id, user_id, auto_create=True, extend_ttl=False
        )
        # Note: auto_create=True guarantees non-None return

        now = datetime.now(UTC).isoformat()

        for entity in entities:
            entity_id = entity.get("id", entity.get("entity_id"))
            if not entity_id:
                continue

            if entity_id in context.entities_mentioned:
                # Update existing mention
                mention = context.entities_mentioned[entity_id]
                mention.mention_count += 1
                mention.last_mentioned = now
            else:
                # Add new mention
                context.entities_mentioned[entity_id] = SessionEntityMention(
                    entity_id=entity_id,
                    entity_name=entity.get(
                        "name", entity.get("entity_name", "Unknown")
                    ),
                    entity_type=entity.get(
                        "type", entity.get("entity_type", "unknown")
                    ),
                    aliases=entity.get("aliases", []),
                    mention_count=1,
                    last_mentioned=now,
                )

        # Apply entity limit to prevent unbounded growth (Epic 7 Code Review Fix)
        context = self._apply_entity_limit(context)

        # Update last activity
        context.last_activity = now

        # Save to Redis
        key = session_key(matter_id, user_id, "context")
        try:
            await self._redis.setex(
                key,
                SESSION_TTL,
                context.model_dump_json(),
            )
        except Exception as e:
            logger.error(
                "redis_update_entities_failed",
                session_id=context.session_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to update entities in session: {e}") from e

        logger.debug(
            "entities_updated",
            session_id=context.session_id,
            entity_count=len(context.entities_mentioned),
        )

        return context

    async def get_entities_mentioned(
        self,
        matter_id: str,
        user_id: str,
    ) -> dict[str, SessionEntityMention]:
        """Get entities mentioned in session for context (AC #4).

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.

        Returns:
            Dict of entity_id -> SessionEntityMention.
        """
        context = await self.get_session(matter_id, user_id, auto_create=False)
        if context is None:
            return {}
        return context.entities_mentioned

    async def resolve_pronoun(
        self,
        matter_id: str,
        user_id: str,
        pronoun: str,
    ) -> SessionEntityMention | None:
        """Resolve a pronoun to the most recently mentioned entity (AC #4).

        Task 5: Implements pronoun resolution with recency-weighted selection.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            pronoun: Pronoun to resolve (he, she, they, it, etc.).

        Returns:
            Most relevant SessionEntityMention or None.
        """
        entities = await self.get_entities_mentioned(matter_id, user_id)
        if not entities:
            return None

        # Filter by pronoun type (gender/plurality)
        pronoun_lower = pronoun.lower()
        candidates: list[SessionEntityMention] = []

        for mention in entities.values():
            entity_type = mention.entity_type.lower()

            # Match pronouns to entity types
            if pronoun_lower in ("he", "him", "his"):
                if entity_type in ("person", "male", "unknown"):
                    candidates.append(mention)
            elif pronoun_lower in ("she", "her", "hers"):
                if entity_type in ("person", "female", "unknown"):
                    candidates.append(mention)
            elif pronoun_lower in ("they", "them", "their"):
                # Can refer to groups or individuals
                candidates.append(mention)
            elif pronoun_lower in ("it", "its"):
                if entity_type in ("organization", "thing", "document", "unknown"):
                    candidates.append(mention)
            else:
                # Unknown pronoun - include all
                candidates.append(mention)

        if not candidates:
            return None

        # Return most recently mentioned (recency-weighted resolution)
        return max(candidates, key=lambda m: m.last_mentioned)

    async def archive_session(
        self,
        matter_id: str,
        user_id: str,
        reason: Literal["expired", "manual_end", "logout"],
    ) -> ArchivedSession | None:
        """Archive session to Matter Memory before deletion.

        Story 7-2: Task 3 - Session archival service.
        AC #1: Archive on expiry, AC #3: Archive on manual end.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            reason: Why session is being archived.

        Returns:
            ArchivedSession if archived, None if no session to archive.

        Raises:
            RuntimeError: If archival fails.
        """
        await self._ensure_client()

        # Get session without extending TTL or restoring from archive
        context = await self.get_session(
            matter_id,
            user_id,
            auto_create=False,
            extend_ttl=False,
            restore_from_archive=False,
        )

        if context is None:
            logger.info(
                "archive_session_no_session_found",
                matter_id=matter_id,
                user_id=user_id,
            )
            return None

        now = datetime.now(UTC).isoformat()

        # Create archived session with last N messages (configurable)
        settings = get_settings()
        max_archived = settings.archived_session_max_messages
        last_messages = context.messages[-max_archived:]

        archive = ArchivedSession(
            session_id=context.session_id,
            matter_id=context.matter_id,
            user_id=context.user_id,
            created_at=context.created_at,
            archived_at=now,
            last_activity=context.last_activity,
            entities_mentioned=context.entities_mentioned,
            last_messages=last_messages,
            total_query_count=context.query_count,
            total_messages=len(context.messages),
            ttl_extended_count=context.ttl_extended_count,
            archival_reason=reason,
        )

        # Store in Matter Memory
        try:
            matter_memory = await self._ensure_matter_memory()
            await matter_memory.save_archived_session(archive)
        except Exception as e:
            logger.error(
                "archive_session_save_failed",
                session_id=context.session_id,
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to archive session: {e}") from e

        logger.info(
            "session_archived",
            session_id=context.session_id,
            matter_id=matter_id,
            user_id=user_id,
            reason=reason,
            entities_archived=len(archive.entities_mentioned),
            messages_archived=len(archive.last_messages),
        )

        return archive

    async def restore_context(
        self,
        matter_id: str,
        user_id: str,
        restore_messages: bool = True,
        message_limit: int = 5,
    ) -> SessionContext | None:
        """Restore context from most recent archived session.

        Story 7-2: Task 4 - Context restoration.
        AC #4: Restore context when returning to matter.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            restore_messages: Whether to restore last messages.
            message_limit: How many messages to restore (max 10).

        Returns:
            New SessionContext with restored context, or None if no archive.
        """
        try:
            matter_memory = await self._ensure_matter_memory()
            archive = await matter_memory.get_latest_archived_session(
                matter_id, user_id
            )
        except Exception as e:
            logger.error(
                "restore_context_query_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            return None

        if archive is None:
            logger.info(
                "no_archived_session_found",
                matter_id=matter_id,
                user_id=user_id,
            )
            return None

        # Create new session
        context = await self.create_session(matter_id, user_id)

        # Restore entities (critical for pronoun resolution)
        context.entities_mentioned = archive.entities_mentioned

        # Optionally restore last messages
        if restore_messages and archive.last_messages:
            # Limit to requested number (max from config)
            settings = get_settings()
            max_archived = settings.archived_session_max_messages
            limit = min(message_limit, max_archived)
            restored = archive.last_messages[-limit:]
            context.messages = restored

        logger.info(
            "context_restored_from_archive",
            session_id=context.session_id,
            original_session_id=archive.session_id,
            entities_restored=len(context.entities_mentioned),
            messages_restored=len(context.messages),
        )

        # Save updated context
        key = session_key(matter_id, user_id, "context")
        try:
            await self._redis.setex(key, SESSION_TTL, context.model_dump_json())
        except Exception as e:
            logger.error(
                "restore_context_save_failed",
                session_id=context.session_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to save restored context: {e}") from e

        return context

    async def end_session(
        self,
        matter_id: str,
        user_id: str,
        archive: bool = True,
    ) -> bool:
        """End and clear a session from Redis.

        Story 7-2: Updated to archive before deletion.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            archive: Whether to archive session before deletion.

        Returns:
            True if session was deleted, False if not found.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        # Story 7-2: Archive before deletion
        if archive:
            await self.archive_session(matter_id, user_id, reason="manual_end")

        key = session_key(matter_id, user_id, "context")
        try:
            result = await self._redis.delete(key)
        except Exception as e:
            logger.error(
                "redis_end_session_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to end session in Redis: {e}") from e

        logger.info(
            "session_ended",
            matter_id=matter_id,
            user_id=user_id,
            deleted=result > 0,
        )

        return result > 0


# Singleton instance
_session_memory_service: SessionMemoryService | None = None


def get_session_memory_service(
    redis_client: Any = None,
    matter_memory: MatterMemoryRepository | None = None,
) -> SessionMemoryService:
    """Get or create SessionMemoryService instance.

    Factory function following project pattern.

    Args:
        redis_client: Optional Redis client for injection.
        matter_memory: Optional MatterMemoryRepository for injection.

    Returns:
        SessionMemoryService instance.
    """
    global _session_memory_service

    if _session_memory_service is None:
        _session_memory_service = SessionMemoryService(redis_client, matter_memory)
    else:
        if redis_client is not None and _session_memory_service._redis is None:
            _session_memory_service._redis = redis_client
        if matter_memory is not None and _session_memory_service._matter_memory is None:
            _session_memory_service._matter_memory = matter_memory

    return _session_memory_service


def reset_session_memory_service() -> None:
    """Reset singleton (for testing).

    Note: This creates a fresh instance on next get_session_memory_service() call,
    which resets _initialized flag implicitly.
    """
    global _session_memory_service
    _session_memory_service = None
    logger.debug("session_memory_service_reset")
