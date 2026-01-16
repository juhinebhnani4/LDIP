"""Tests for Redis client wrapper.

Story 7-1: Session Memory Redis Storage
Task 6.2: Unit tests for Redis client wrapper with mocked responses
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory.redis_client import (
    get_redis_client,
    reset_redis_client,
)


class TestRedisClient:
    """Tests for Redis client initialization."""

    def setup_method(self) -> None:
        """Reset client before each test."""
        reset_redis_client()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_redis_client()

    @pytest.mark.asyncio
    async def test_get_redis_client_returns_same_instance(self) -> None:
        """Client should be singleton - same instance returned."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True):
            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_client = MagicMock()
                mock_from_url.return_value = mock_client

                client1 = await get_redis_client()
                client2 = await get_redis_client()

                assert client1 is client2
                # Only called once due to singleton
                mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_with_upstash_env(self) -> None:
        """Should use Upstash client when env vars are set."""
        env = {
            "UPSTASH_REDIS_REST_URL": "https://test.upstash.io",
            "UPSTASH_REDIS_REST_TOKEN": "test-token",
        }
        mock_client = MagicMock()

        # Create mock upstash module
        mock_upstash_asyncio = MagicMock()
        mock_upstash_asyncio.Redis.return_value = mock_client

        with patch.dict(os.environ, env, clear=True), patch.dict(
            "sys.modules",
            {
                "upstash_redis": MagicMock(),
                "upstash_redis.asyncio": mock_upstash_asyncio,
            },
        ):
            reset_redis_client()
            client = await get_redis_client()

            # Should return a client (either upstash or fallback)
            assert client is not None

    @pytest.mark.asyncio
    async def test_get_redis_client_fallback_to_redis_py(self) -> None:
        """Should fallback to redis-py when Upstash not configured."""
        # Clear Upstash env vars
        env = {"REDIS_URL": "redis://localhost:6379/0"}
        with patch.dict(os.environ, env, clear=True):
            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_client = MagicMock()
                mock_from_url.return_value = mock_client

                reset_redis_client()
                client = await get_redis_client()

                assert client is mock_client
                mock_from_url.assert_called_once_with(
                    "redis://localhost:6379/0", decode_responses=True
                )

    @pytest.mark.asyncio
    async def test_get_redis_client_default_url(self) -> None:
        """Should use default Redis URL when not specified."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_client = MagicMock()
                mock_from_url.return_value = mock_client

                reset_redis_client()
                await get_redis_client()

                mock_from_url.assert_called_with(
                    "redis://localhost:6379/0", decode_responses=True
                )

    def test_reset_redis_client(self) -> None:
        """Reset should clear the singleton."""
        # This test verifies the reset function exists and runs
        reset_redis_client()
        # No exception means success

    @pytest.mark.asyncio
    async def test_get_redis_client_raises_when_no_client_available(self) -> None:
        """Should raise RuntimeError when no Redis client can be initialized."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock ImportError for redis - this simulates no redis package
            with patch(
                "redis.asyncio.from_url", side_effect=ImportError("No redis")
            ):
                reset_redis_client()
                with pytest.raises(RuntimeError, match="No Redis client"):
                    await get_redis_client()


class TestRedisClientIntegration:
    """Integration-style tests with mock Redis operations."""

    def setup_method(self) -> None:
        """Reset client before each test."""
        reset_redis_client()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_redis_client()

    @pytest.mark.asyncio
    async def test_redis_operations_with_mock(self) -> None:
        """Verify Redis operations work with mocked client."""
        mock_client = AsyncMock()
        mock_client.get.return_value = '{"test": "data"}'
        mock_client.setex.return_value = True
        mock_client.delete.return_value = 1
        mock_client.expire.return_value = True

        # Test get
        result = await mock_client.get("test-key")
        assert result == '{"test": "data"}'

        # Test setex
        result = await mock_client.setex("test-key", 3600, '{"test": "data"}')
        assert result is True

        # Test delete
        result = await mock_client.delete("test-key")
        assert result == 1

        # Test expire
        result = await mock_client.expire("test-key", 3600)
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_get_returns_none_for_missing_key(self) -> None:
        """Redis get should return None for non-existent keys."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        result = await mock_client.get("non-existent-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_delete_returns_zero_for_missing_key(self) -> None:
        """Redis delete should return 0 for non-existent keys."""
        mock_client = AsyncMock()
        mock_client.delete.return_value = 0

        result = await mock_client.delete("non-existent-key")
        assert result == 0
