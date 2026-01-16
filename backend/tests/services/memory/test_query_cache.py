"""Tests for Query Cache Repository.

Story 7-5: Query Cache Redis Storage
Tasks 5.2-5.5: Unit tests for QueryCacheRepository
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.memory import CachedQueryResult
from app.services.memory.query_cache import (
    QueryCacheRepository,
    get_query_cache_repository,
    reset_query_cache_repository,
)
from app.services.memory.redis_keys import CACHE_TTL

# Valid UUIDs for testing (redis_keys.py validates UUID format)
MATTER_ID = "12345678-1234-1234-1234-123456789abc"
MATTER_ID_B = "87654321-4321-4321-4321-987654321fed"
# Valid 64-char hex hash for testing
QUERY_HASH = "a" * 64
QUERY_HASH_2 = "b" * 64


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.scan.return_value = (0, [])  # cursor=0 means done
    return mock


@pytest.fixture
def repository(mock_redis: AsyncMock) -> QueryCacheRepository:
    """Create a repository with mock Redis."""
    reset_query_cache_repository()
    return QueryCacheRepository(mock_redis)


@pytest.fixture
def sample_cached_result() -> CachedQueryResult:
    """Create a sample cached result for testing."""
    now = datetime.now(UTC)
    return CachedQueryResult(
        query_hash=QUERY_HASH,
        matter_id=MATTER_ID,
        original_query="What is SARFAESI?",
        normalized_query="what is sarfaesi?",
        cached_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        result_summary="SARFAESI is a law...",
        engine_used="rag_engine",
        findings_count=3,
        confidence=85.5,
        response_data={"answer": "SARFAESI is...", "sources": []},
    )


class TestGetCachedResult:
    """Tests for get_cached_result method (Task 5.4, 5.5)."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should return cached result on cache hit (AC #2)."""
        mock_redis.get.return_value = sample_cached_result.model_dump_json()

        result = await repository.get_cached_result(MATTER_ID, QUERY_HASH)

        assert result is not None
        assert result.query_hash == QUERY_HASH
        assert result.matter_id == MATTER_ID
        assert result.original_query == "What is SARFAESI?"

    @pytest.mark.asyncio
    async def test_cache_miss(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should return None on cache miss (Task 5.5)."""
        mock_redis.get.return_value = None

        result = await repository.get_cached_result(MATTER_ID, QUERY_HASH)

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_key_format(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should use correct Redis key format (AC #1)."""
        await repository.get_cached_result(MATTER_ID, QUERY_HASH)

        mock_redis.get.assert_called_once()
        call_args = mock_redis.get.call_args
        key = call_args[0][0]
        assert key == f"cache:query:{MATTER_ID}:{QUERY_HASH}"

    @pytest.mark.asyncio
    async def test_corrupt_cache_entry_deleted(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should delete corrupt cache entries."""
        mock_redis.get.return_value = "invalid json {{{}"

        result = await repository.get_cached_result(MATTER_ID, QUERY_HASH)

        assert result is None
        mock_redis.delete.assert_called_once()


class TestSetCachedResult:
    """Tests for set_cached_result method (Task 5.2)."""

    @pytest.mark.asyncio
    async def test_stores_with_correct_ttl(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should store with 1-hour TTL (AC #3)."""
        await repository.set_cached_result(sample_cached_result)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == CACHE_TTL  # 1 hour = 3600 seconds

    @pytest.mark.asyncio
    async def test_stores_with_correct_key(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should use correct Redis key format (AC #1)."""
        await repository.set_cached_result(sample_cached_result)

        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        assert key == f"cache:query:{MATTER_ID}:{QUERY_HASH}"

    @pytest.mark.asyncio
    async def test_stores_serialized_json(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should store serialized JSON."""
        await repository.set_cached_result(sample_cached_result)

        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        # Should be valid JSON that can be parsed back
        parsed = CachedQueryResult.model_validate_json(stored_json)
        assert parsed.query_hash == QUERY_HASH


class TestDeleteCachedResult:
    """Tests for delete_cached_result method."""

    @pytest.mark.asyncio
    async def test_delete_existing(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should return True when deleting existing entry."""
        mock_redis.delete.return_value = 1

        result = await repository.delete_cached_result(MATTER_ID, QUERY_HASH)

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_non_existing(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should return False when entry doesn't exist."""
        mock_redis.delete.return_value = 0

        result = await repository.delete_cached_result(MATTER_ID, QUERY_HASH)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_correct_key(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should delete correct key."""
        await repository.delete_cached_result(MATTER_ID, QUERY_HASH)

        call_args = mock_redis.delete.call_args
        key = call_args[0][0]
        assert key == f"cache:query:{MATTER_ID}:{QUERY_HASH}"


class TestMatterIsolation:
    """Tests for matter isolation (CRITICAL - Task 5.7)."""

    @pytest.mark.asyncio
    async def test_cache_isolated_by_matter(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Cache should be isolated by matter (Task 5.7)."""
        # Set up mock to track keys
        stored_keys: list[str] = []

        async def track_setex(key: str, ttl: int, value: str) -> bool:
            stored_keys.append(key)
            return True

        mock_redis.setex.side_effect = track_setex

        # Create results for two different matters
        now = datetime.now(UTC)
        result_a = CachedQueryResult(
            query_hash=QUERY_HASH,
            matter_id=MATTER_ID,
            original_query="Query A",
            normalized_query="query a",
            cached_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
        )
        result_b = CachedQueryResult(
            query_hash=QUERY_HASH,
            matter_id=MATTER_ID_B,
            original_query="Query B",
            normalized_query="query b",
            cached_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
        )

        await repository.set_cached_result(result_a)
        await repository.set_cached_result(result_b)

        # Keys should include different matter IDs
        assert len(stored_keys) == 2
        assert f"cache:query:{MATTER_ID}:" in stored_keys[0]
        assert f"cache:query:{MATTER_ID_B}:" in stored_keys[1]

    @pytest.mark.asyncio
    async def test_get_validates_matter_access(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Get should validate matter access."""
        # Store a result for matter A
        now = datetime.now(UTC)
        result = CachedQueryResult(
            query_hash=QUERY_HASH,
            matter_id=MATTER_ID,
            original_query="Query",
            normalized_query="query",
            cached_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
        )
        mock_redis.get.return_value = result.model_dump_json()

        # Request should use matter-specific key
        await repository.get_cached_result(MATTER_ID, QUERY_HASH)
        call_args = mock_redis.get.call_args
        key = call_args[0][0]

        # Key should contain the requested matter ID
        assert MATTER_ID in key


class TestBulkInvalidation:
    """Tests for bulk invalidation (Task 5.8)."""

    @pytest.mark.asyncio
    async def test_invalidate_matter_cache_empty(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should return 0 when no keys to delete."""
        mock_redis.scan.return_value = (0, [])

        count = await repository.invalidate_matter_cache(MATTER_ID)

        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_matter_cache_deletes_all(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should delete all cache entries for matter (AC #4)."""
        # Mock SCAN returning keys
        mock_redis.scan.return_value = (0, [
            f"cache:query:{MATTER_ID}:{QUERY_HASH}",
            f"cache:query:{MATTER_ID}:{QUERY_HASH_2}",
        ])
        mock_redis.delete.return_value = 2

        count = await repository.invalidate_matter_cache(MATTER_ID)

        assert count == 2
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_uses_correct_pattern(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should use correct SCAN pattern."""
        mock_redis.scan.return_value = (0, [])

        await repository.invalidate_matter_cache(MATTER_ID)

        call_args = mock_redis.scan.call_args
        assert call_args[1]["match"] == f"cache:query:{MATTER_ID}:*"

    @pytest.mark.asyncio
    async def test_invalidate_handles_pagination(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should handle SCAN pagination correctly."""
        # First batch returns cursor=1, second returns cursor=0 (done)
        mock_redis.scan.side_effect = [
            (1, [f"cache:query:{MATTER_ID}:{QUERY_HASH}"]),
            (0, [f"cache:query:{MATTER_ID}:{QUERY_HASH_2}"]),
        ]
        mock_redis.delete.return_value = 1

        count = await repository.invalidate_matter_cache(MATTER_ID)

        assert count == 2
        assert mock_redis.scan.call_count == 2
        assert mock_redis.delete.call_count == 2


class TestTTLExpiry:
    """Tests for TTL expiry (Task 5.6)."""

    @pytest.mark.asyncio
    async def test_set_uses_one_hour_ttl(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should set 1-hour TTL (AC #3)."""
        await repository.set_cached_result(sample_cached_result)

        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]
        assert ttl == 3600  # 1 hour in seconds

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Expired entries should return None (handled by Redis TTL)."""
        # Redis returns None for expired keys
        mock_redis.get.return_value = None

        result = await repository.get_cached_result(MATTER_ID, QUERY_HASH)

        assert result is None


class TestCacheStats:
    """Tests for cache statistics."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_empty(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should return empty stats when no cache entries."""
        mock_redis.scan.return_value = (0, [])

        stats = await repository.get_cache_stats(MATTER_ID)

        assert stats["count"] == 0
        assert stats["keys"] == []

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_entries(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should return correct stats when entries exist."""
        mock_redis.scan.return_value = (0, [
            f"cache:query:{MATTER_ID}:{QUERY_HASH}",
            f"cache:query:{MATTER_ID}:{QUERY_HASH_2}",
        ])

        stats = await repository.get_cache_stats(MATTER_ID)

        assert stats["count"] == 2
        assert len(stats["keys"]) == 2


class TestSingletonPattern:
    """Tests for singleton factory pattern."""

    def test_get_repository_returns_instance(self) -> None:
        """Factory should return QueryCacheRepository instance."""
        reset_query_cache_repository()
        repo = get_query_cache_repository()
        assert isinstance(repo, QueryCacheRepository)

    def test_get_repository_returns_same_instance(self) -> None:
        """Factory should return same instance on repeated calls."""
        reset_query_cache_repository()
        repo1 = get_query_cache_repository()
        repo2 = get_query_cache_repository()
        assert repo1 is repo2

    def test_reset_creates_new_instance(self) -> None:
        """Reset should cause new instance on next call."""
        reset_query_cache_repository()
        repo1 = get_query_cache_repository()
        reset_query_cache_repository()
        repo2 = get_query_cache_repository()
        assert repo1 is not repo2


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_get_handles_redis_error(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should raise RuntimeError on Redis failure."""
        mock_redis.get.side_effect = Exception("Redis connection failed")

        with pytest.raises(RuntimeError, match="Failed to get cached result"):
            await repository.get_cached_result(MATTER_ID, QUERY_HASH)

    @pytest.mark.asyncio
    async def test_set_handles_redis_error(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should raise RuntimeError on Redis failure."""
        mock_redis.setex.side_effect = Exception("Redis connection failed")

        with pytest.raises(RuntimeError, match="Failed to store cached result"):
            await repository.set_cached_result(sample_cached_result)

    @pytest.mark.asyncio
    async def test_delete_handles_redis_error(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should raise RuntimeError on Redis failure."""
        mock_redis.delete.side_effect = Exception("Redis connection failed")

        with pytest.raises(RuntimeError, match="Failed to delete cached result"):
            await repository.delete_cached_result(MATTER_ID, QUERY_HASH)

    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error(
        self,
        repository: QueryCacheRepository,
        mock_redis: AsyncMock,
    ) -> None:
        """Should raise RuntimeError on Redis failure."""
        mock_redis.scan.side_effect = Exception("Redis connection failed")

        with pytest.raises(RuntimeError, match="Failed to invalidate matter cache"):
            await repository.invalidate_matter_cache(MATTER_ID)
