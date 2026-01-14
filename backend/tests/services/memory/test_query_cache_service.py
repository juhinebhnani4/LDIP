"""Tests for Query Cache Service.

Story 7-5: Query Cache Redis Storage
Tasks 4.2-4.5 / 5.3: Unit tests for QueryCacheService high-level methods.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.memory import CachedQueryResult
from app.services.memory.query_cache import QueryCacheRepository
from app.services.memory.query_cache_service import (
    QueryCacheService,
    get_query_cache_service,
    reset_query_cache_service,
)
from app.services.memory.query_normalizer import QueryNormalizer
from app.services.memory.redis_keys import CACHE_TTL


# Valid UUIDs for testing (redis_keys.py validates UUID format)
MATTER_ID = "12345678-1234-1234-1234-123456789abc"
MATTER_ID_B = "87654321-4321-4321-4321-987654321fed"


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Create a mock QueryCacheRepository."""
    mock = AsyncMock(spec=QueryCacheRepository)
    mock.get_cached_result.return_value = None
    mock.set_cached_result.return_value = None
    mock.delete_cached_result.return_value = True
    mock.invalidate_matter_cache.return_value = 0
    mock.get_cache_stats.return_value = {"count": 0, "keys": []}
    return mock


@pytest.fixture
def mock_normalizer() -> MagicMock:
    """Create a mock QueryNormalizer."""
    mock = MagicMock(spec=QueryNormalizer)
    mock.normalize.return_value = "what is sarfaesi?"
    mock.hash.return_value = "a" * 64
    mock.normalize_and_hash.return_value = ("what is sarfaesi?", "a" * 64)
    return mock


@pytest.fixture
def service(mock_repository: AsyncMock, mock_normalizer: MagicMock) -> QueryCacheService:
    """Create a QueryCacheService with mocks."""
    reset_query_cache_service()
    return QueryCacheService(mock_repository, mock_normalizer)


@pytest.fixture
def sample_cached_result() -> CachedQueryResult:
    """Create a sample cached result for testing."""
    now = datetime.now(timezone.utc)
    return CachedQueryResult(
        query_hash="a" * 64,
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


class TestCheckCache:
    """Tests for check_cache method (Task 4.2)."""

    @pytest.mark.asyncio
    async def test_check_cache_hit(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
        mock_normalizer: MagicMock,
        sample_cached_result: CachedQueryResult,
    ) -> None:
        """Should return cached result on cache hit (AC #2)."""
        mock_repository.get_cached_result.return_value = sample_cached_result

        result = await service.check_cache(MATTER_ID, "What is SARFAESI?")

        assert result is not None
        assert result.original_query == "What is SARFAESI?"
        mock_normalizer.hash.assert_called_once_with("What is SARFAESI?")
        mock_repository.get_cached_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_cache_miss(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should return None on cache miss."""
        mock_repository.get_cached_result.return_value = None

        result = await service.check_cache(MATTER_ID, "Unknown query")

        assert result is None

    @pytest.mark.asyncio
    async def test_check_cache_normalizes_query(
        self,
        service: QueryCacheService,
        mock_normalizer: MagicMock,
    ) -> None:
        """Should normalize query before cache lookup."""
        await service.check_cache(MATTER_ID, "What is SARFAESI?")

        mock_normalizer.hash.assert_called_once_with("What is SARFAESI?")


class TestCacheResult:
    """Tests for cache_result method (Task 4.3)."""

    @pytest.mark.asyncio
    async def test_cache_result_stores(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should store cached result (AC #1)."""
        result = await service.cache_result(
            matter_id=MATTER_ID,
            query="What is SARFAESI?",
            result_summary="SARFAESI is a law...",
            response_data={"answer": "..."},
            engine_used="rag_engine",
            findings_count=3,
            confidence=85.5,
        )

        assert result.matter_id == MATTER_ID
        assert result.result_summary == "SARFAESI is a law..."
        mock_repository.set_cached_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_result_sets_timestamps(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should set cached_at and expires_at timestamps."""
        result = await service.cache_result(
            matter_id=MATTER_ID,
            query="What is SARFAESI?",
            result_summary="...",
            response_data={},
        )

        assert result.cached_at is not None
        assert result.expires_at is not None
        # expires_at should be ~1 hour after cached_at
        cached = datetime.fromisoformat(result.cached_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(result.expires_at.replace("Z", "+00:00"))
        delta = (expires - cached).total_seconds()
        assert abs(delta - CACHE_TTL) < 5  # Allow 5 second tolerance

    @pytest.mark.asyncio
    async def test_cache_result_normalizes_query(
        self,
        service: QueryCacheService,
        mock_normalizer: MagicMock,
        mock_repository: AsyncMock,
    ) -> None:
        """Should normalize query and store both forms."""
        mock_normalizer.normalize_and_hash.return_value = (
            "normalized query",
            "b" * 64,
        )

        result = await service.cache_result(
            matter_id=MATTER_ID,
            query="Original Query",
            result_summary="...",
            response_data={},
        )

        assert result.original_query == "Original Query"
        assert result.normalized_query == "normalized query"
        assert result.query_hash == "b" * 64

    @pytest.mark.asyncio
    async def test_cache_result_returns_cached_object(
        self,
        service: QueryCacheService,
    ) -> None:
        """Should return the CachedQueryResult object."""
        result = await service.cache_result(
            matter_id=MATTER_ID,
            query="What is SARFAESI?",
            result_summary="SARFAESI is...",
            response_data={"answer": "..."},
            engine_used="rag_engine",
            findings_count=5,
            confidence=90.0,
        )

        assert isinstance(result, CachedQueryResult)
        assert result.engine_used == "rag_engine"
        assert result.findings_count == 5
        assert result.confidence == 90.0


class TestInvalidateOnDocumentUpload:
    """Tests for invalidate_on_document_upload method (Task 4.4)."""

    @pytest.mark.asyncio
    async def test_invalidate_calls_repository(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should call repository invalidate method (AC #4)."""
        mock_repository.invalidate_matter_cache.return_value = 5

        count = await service.invalidate_on_document_upload(MATTER_ID)

        assert count == 5
        mock_repository.invalidate_matter_cache.assert_called_once_with(MATTER_ID)

    @pytest.mark.asyncio
    async def test_invalidate_returns_count(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should return count of deleted entries."""
        mock_repository.invalidate_matter_cache.return_value = 10

        count = await service.invalidate_on_document_upload(MATTER_ID)

        assert count == 10


class TestGetCacheStats:
    """Tests for get_cache_stats method (Task 4.5)."""

    @pytest.mark.asyncio
    async def test_get_cache_stats(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should return cache statistics."""
        mock_repository.get_cache_stats.return_value = {
            "count": 5,
            "keys": ["key1", "key2", "key3", "key4", "key5"],
        }

        stats = await service.get_cache_stats(MATTER_ID)

        assert stats["matter_id"] == MATTER_ID
        assert stats["cached_queries"] == 5
        assert stats["ttl_seconds"] == CACHE_TTL
        assert len(stats["cache_keys"]) == 5


class TestDeleteCachedQuery:
    """Tests for delete_cached_query method."""

    @pytest.mark.asyncio
    async def test_delete_existing_query(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
        mock_normalizer: MagicMock,
    ) -> None:
        """Should delete cached query and return True."""
        mock_repository.delete_cached_result.return_value = True

        result = await service.delete_cached_query(MATTER_ID, "What is SARFAESI?")

        assert result is True
        mock_normalizer.hash.assert_called_once_with("What is SARFAESI?")
        mock_repository.delete_cached_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_non_existing_query(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should return False for non-existing query."""
        mock_repository.delete_cached_result.return_value = False

        result = await service.delete_cached_query(MATTER_ID, "Unknown query")

        assert result is False


class TestMatterIsolation:
    """Tests for matter isolation at service level."""

    @pytest.mark.asyncio
    async def test_check_cache_uses_matter_id(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should pass matter_id to repository."""
        await service.check_cache(MATTER_ID, "test query")
        await service.check_cache(MATTER_ID_B, "test query")

        calls = mock_repository.get_cached_result.call_args_list
        assert calls[0][0][0] == MATTER_ID
        assert calls[1][0][0] == MATTER_ID_B

    @pytest.mark.asyncio
    async def test_cache_result_uses_matter_id(
        self,
        service: QueryCacheService,
        mock_repository: AsyncMock,
    ) -> None:
        """Should include matter_id in cached result."""
        result = await service.cache_result(
            matter_id=MATTER_ID,
            query="test",
            result_summary="...",
            response_data={},
        )

        assert result.matter_id == MATTER_ID


class TestSingletonPattern:
    """Tests for singleton factory pattern."""

    def test_get_service_returns_instance(self) -> None:
        """Factory should return QueryCacheService instance."""
        reset_query_cache_service()
        service = get_query_cache_service()
        assert isinstance(service, QueryCacheService)

    def test_get_service_returns_same_instance(self) -> None:
        """Factory should return same instance on repeated calls."""
        reset_query_cache_service()
        service1 = get_query_cache_service()
        service2 = get_query_cache_service()
        assert service1 is service2

    def test_reset_creates_new_instance(self) -> None:
        """Reset should cause new instance on next call."""
        reset_query_cache_service()
        service1 = get_query_cache_service()
        reset_query_cache_service()
        service2 = get_query_cache_service()
        assert service1 is not service2


class TestLazyInitialization:
    """Tests for lazy initialization of dependencies."""

    @pytest.mark.asyncio
    async def test_creates_repository_on_demand(self) -> None:
        """Should create repository when needed."""
        reset_query_cache_service()
        service = QueryCacheService()  # No injected dependencies

        # Repository should be None initially
        assert service._repository is None

        # Should create on first use
        service._ensure_repository()
        assert service._repository is not None

    def test_creates_normalizer_on_demand(self) -> None:
        """Should create normalizer when needed."""
        reset_query_cache_service()
        service = QueryCacheService()  # No injected dependencies

        # Normalizer should be None initially
        assert service._normalizer is None

        # Should create on first use
        service._ensure_normalizer()
        assert service._normalizer is not None
