"""Distributed locking service using Redis.

Story 16.4: Parallel Chunk Processing with Celery

Provides synchronous Redis-based distributed locks for Celery tasks.
Uses the same Redis instance as the Celery broker.
"""

from functools import lru_cache

import redis
import structlog
from redis.lock import Lock

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Lock configuration
DEFAULT_LOCK_TIMEOUT = 300  # seconds (5 min — OCR chunks can take 2-3 min)
CHUNK_LOCK_KEY_PATTERN = "chunk_lock:{document_id}:{chunk_index}"

# Pipeline deduplication lock (Stage 1.2: prevents duplicate pipeline runs)
PIPELINE_LOCK_KEY = "pipeline_lock:{document_id}"
PIPELINE_LOCK_TIMEOUT = (
    1800  # 30 min — covers longest pipeline (422-page contradiction detection)
)


class DistributedLockError(Exception):
    """Raised when lock operations fail."""

    def __init__(self, message: str, code: str = "LOCK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


@lru_cache(maxsize=1)
def get_sync_redis_client() -> redis.Redis:
    """Get synchronous Redis client for distributed locking.

    Uses the same Redis URL as the Celery broker to avoid
    requiring additional infrastructure.

    Returns:
        Synchronous Redis client instance.
    """
    settings = get_settings()
    redis_url = settings.celery_broker_url

    # Handle Upstash Redis (rediss:// protocol)
    # Upstash requires SSL but redis-py handles this via the protocol
    client = redis.from_url(
        redis_url,
        decode_responses=True,
        socket_timeout=5.0,
    )

    logger.info(
        "sync_redis_client_initialized",
        url=redis_url[:30] + "..." if len(redis_url) > 30 else redis_url,
    )

    return client


class ChunkLock:
    """Context manager for chunk processing locks.

    Ensures only one worker processes a given chunk at a time.
    Lock automatically expires after timeout to prevent deadlocks.

    Example:
        >>> with ChunkLock("doc-123", chunk_index=5) as locked:
        ...     if locked:
        ...         process_chunk(...)
        ...     else:
        ...         logger.warning("Could not acquire lock")
    """

    def __init__(
        self,
        document_id: str,
        chunk_index: int,
        timeout: int = DEFAULT_LOCK_TIMEOUT,
        blocking: bool = False,
    ):
        """Initialize chunk lock.

        Args:
            document_id: Document UUID.
            chunk_index: Chunk index (0-based).
            timeout: Lock expiry in seconds (default 120).
            blocking: Whether to block waiting for lock.
        """
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.timeout = timeout
        self.blocking = blocking

        self.lock_key = CHUNK_LOCK_KEY_PATTERN.format(
            document_id=document_id,
            chunk_index=chunk_index,
        )

        self._redis_client = get_sync_redis_client()
        self._lock = Lock(
            self._redis_client,
            self.lock_key,
            timeout=self.timeout,
        )
        self._acquired = False

    def acquire(self) -> bool:
        """Attempt to acquire the lock.

        Returns:
            True if lock acquired, False otherwise.
        """
        try:
            self._acquired = self._lock.acquire(blocking=self.blocking)

            if self._acquired:
                logger.debug(
                    "chunk_lock_acquired",
                    document_id=self.document_id,
                    chunk_index=self.chunk_index,
                )
            else:
                logger.warning(
                    "chunk_lock_not_acquired",
                    document_id=self.document_id,
                    chunk_index=self.chunk_index,
                )

            return self._acquired

        except redis.RedisError as e:
            logger.error(
                "chunk_lock_error",
                document_id=self.document_id,
                chunk_index=self.chunk_index,
                error=str(e),
            )
            return False

    def release(self) -> None:
        """Release the lock if held."""
        if self._acquired:
            try:
                self._lock.release()
                self._acquired = False
                logger.debug(
                    "chunk_lock_released",
                    document_id=self.document_id,
                    chunk_index=self.chunk_index,
                )
            except redis.lock.LockError as e:
                # Lock may have expired - not an error
                logger.warning(
                    "chunk_lock_release_failed",
                    document_id=self.document_id,
                    chunk_index=self.chunk_index,
                    error=str(e),
                )

    def __enter__(self) -> bool:
        """Context manager entry - acquire lock."""
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - release lock."""
        self.release()


class PipelineLock:
    """Prevents duplicate pipeline runs for the same document.

    Stage 1.2: Pipeline Deduplication

    Uses a Redis SET NX lock with 30-min TTL to ensure only one pipeline
    runs per document at a time. Manual retry + maintenance recovery can
    otherwise dispatch two pipelines simultaneously.

    Example:
        >>> lock = PipelineLock("doc-123")
        >>> if lock.acquire():
        ...     run_pipeline(...)
        ...     lock.release()
        ... else:
        ...     logger.info("pipeline_already_running")
    """

    def __init__(self, document_id: str, timeout: int = PIPELINE_LOCK_TIMEOUT):
        self.document_id = document_id
        self.lock_key = PIPELINE_LOCK_KEY.format(document_id=document_id)
        self._client = get_sync_redis_client()
        self._timeout = timeout

    def acquire(self) -> bool:
        """Acquire pipeline lock. Returns True if acquired, False if already locked."""
        try:
            result = self._client.set(self.lock_key, "1", nx=True, ex=self._timeout)
            acquired = bool(result)
            if acquired:
                logger.info("pipeline_lock_acquired", document_id=self.document_id)
            else:
                logger.info("pipeline_already_running", document_id=self.document_id)
            return acquired
        except redis.RedisError as e:
            logger.error(
                "pipeline_lock_acquire_error",
                document_id=self.document_id,
                error=str(e),
            )
            # Fail open: allow pipeline to proceed if Redis is down
            return True

    def release(self) -> None:
        """Release the pipeline lock."""
        try:
            self._client.delete(self.lock_key)
            logger.info("pipeline_lock_released", document_id=self.document_id)
        except redis.RedisError as e:
            logger.warning(
                "pipeline_lock_release_error",
                document_id=self.document_id,
                error=str(e),
            )

    def is_locked(self) -> bool:
        """Check if a pipeline is currently running for this document."""
        try:
            return bool(self._client.exists(self.lock_key))
        except redis.RedisError:
            return False


def acquire_chunk_lock(
    document_id: str,
    chunk_index: int,
    timeout: int = DEFAULT_LOCK_TIMEOUT,
) -> ChunkLock:
    """Factory function to create a chunk lock.

    Args:
        document_id: Document UUID.
        chunk_index: Chunk index (0-based).
        timeout: Lock expiry in seconds.

    Returns:
        ChunkLock instance (use as context manager).
    """
    return ChunkLock(
        document_id=document_id,
        chunk_index=chunk_index,
        timeout=timeout,
    )
