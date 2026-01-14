"""Session Memory Service for conversation context.

Story 7-1: Session Memory Redis Storage

Manages user session context in Redis with:
- 7-day TTL with auto-extension on access
- Sliding window message history (max 20)
- Entity tracking for pronoun resolution

CRITICAL: All session data is scoped by matter_id + user_id
for Layer 3 isolation (Redis key prefix).

Key format: session:{matter_id}:{user_id}:context
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.models.memory import SessionContext, SessionEntityMention, SessionMessage
from app.services.memory.redis_client import get_redis_client
from app.services.memory.redis_keys import (
    SESSION_TTL,
    session_key,
    validate_key_access,
)

logger = structlog.get_logger(__name__)

# Maximum messages in sliding window (AC #3)
MAX_SESSION_MESSAGES = 20


class SessionMemoryService:
    """Manages session context in Redis.

    Story 7-1: Provides conversation context persistence
    for follow-up questions without repeating context.

    Features:
    - Session creation with 7-day TTL (AC #1)
    - Message history with sliding window (AC #2, #3)
    - Entity tracking for pronoun resolution (AC #4)
    - Auto-extend TTL on session access
    """

    def __init__(self, redis_client: Any = None) -> None:
        """Initialize session memory service.

        Args:
            redis_client: Optional Redis client (injected for testing).
        """
        self._redis = redis_client
        self._initialized = False

    async def _ensure_client(self) -> None:
        """Ensure Redis client is initialized."""
        if self._redis is None:
            self._redis = await get_redis_client()
        self._initialized = True

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
        now = datetime.now(timezone.utc).isoformat()

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
    ) -> SessionContext | None:
        """Retrieve session context from Redis.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            auto_create: Create new session if not found.
            extend_ttl: Auto-extend TTL on access (sliding expiration).

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

        # Auto-extend TTL on access (sliding expiration)
        if extend_ttl:
            context.ttl_extended_count += 1
            context.last_activity = datetime.now(timezone.utc).isoformat()

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
        now = datetime.now(timezone.utc).isoformat()
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
        """Apply sliding window to keep max 20 messages (AC #3).

        Task 4: Implements sliding window logic.

        Args:
            context: Session context to modify.

        Returns:
            Modified context with window applied.

        Note:
            This is a local operation on the context object.
            Caller is responsible for persisting changes.
        """
        if len(context.messages) <= MAX_SESSION_MESSAGES:
            return context

        # Remove oldest messages
        removed_count = len(context.messages) - MAX_SESSION_MESSAGES
        context.messages = context.messages[-MAX_SESSION_MESSAGES:]

        logger.info(
            "sliding_window_applied",
            session_id=context.session_id,
            removed_count=removed_count,
            retained_count=len(context.messages),
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

        now = datetime.now(timezone.utc).isoformat()

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

    async def end_session(
        self,
        matter_id: str,
        user_id: str,
    ) -> bool:
        """End and clear a session from Redis.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.

        Returns:
            True if session was deleted, False if not found.

        Raises:
            RuntimeError: If Redis operation fails.

        Note:
            Before clearing, session should be archived to
            Matter Memory (Story 7-3 handles archival).
        """
        await self._ensure_client()

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


def get_session_memory_service(redis_client: Any = None) -> SessionMemoryService:
    """Get or create SessionMemoryService instance.

    Factory function following project pattern.

    Args:
        redis_client: Optional Redis client for injection.

    Returns:
        SessionMemoryService instance.
    """
    global _session_memory_service

    if _session_memory_service is None:
        _session_memory_service = SessionMemoryService(redis_client)
    elif redis_client is not None and _session_memory_service._redis is None:
        _session_memory_service._redis = redis_client

    return _session_memory_service


def reset_session_memory_service() -> None:
    """Reset singleton (for testing).

    Note: This creates a fresh instance on next get_session_memory_service() call,
    which resets _initialized flag implicitly.
    """
    global _session_memory_service
    _session_memory_service = None
    logger.debug("session_memory_service_reset")
