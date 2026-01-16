"""Unit tests for the embedding service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag.embedder import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingService,
    EmbeddingServiceError,
)


class TestEmbeddingServiceInit:
    """Tests for EmbeddingService initialization."""

    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    def test_creates_client_with_api_key(
        self, mock_openai: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should create OpenAI client with API key from settings."""
        mock_settings.return_value.openai_api_key = "test-api-key"

        EmbeddingService()

        mock_openai.assert_called_once_with(api_key="test-api-key")

    def test_accepts_redis_client(self) -> None:
        """Should accept optional Redis client for caching."""
        mock_redis = MagicMock()

        with patch("app.services.rag.embedder.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = "test-key"
            with patch("app.services.rag.embedder.AsyncOpenAI"):
                service = EmbeddingService(redis_client=mock_redis)

        assert service._redis is mock_redis


class TestEmbeddingServiceHashText:
    """Tests for text hashing."""

    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    def test_generates_consistent_hash(
        self, mock_openai: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should generate same hash for same text."""
        mock_settings.return_value.openai_api_key = "test-key"
        service = EmbeddingService()

        hash1 = service._hash_text("test content")
        hash2 = service._hash_text("test content")

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    def test_generates_different_hash_for_different_text(
        self, mock_openai: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should generate different hash for different text."""
        mock_settings.return_value.openai_api_key = "test-key"
        service = EmbeddingService()

        hash1 = service._hash_text("text one")
        hash2 = service._hash_text("text two")

        assert hash1 != hash2


class TestEmbeddingServiceEmbedText:
    """Tests for single text embedding."""

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_generates_embedding(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should generate embedding for text."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_embedding = [0.1] * EMBEDDING_DIMENSIONS
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding)]
        mock_response.usage.total_tokens = 10

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        service = EmbeddingService()
        result = await service.embed_text("test text")

        assert result == mock_embedding
        assert len(result) == EMBEDDING_DIMENSIONS

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_calls_api_with_correct_params(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should call OpenAI API with correct parameters."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * EMBEDDING_DIMENSIONS)]
        mock_response.usage.total_tokens = 10

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        service = EmbeddingService()
        await service.embed_text("test text")

        mock_client.embeddings.create.assert_called_once_with(
            model=EMBEDDING_MODEL,
            input="test text",
            dimensions=EMBEDDING_DIMENSIONS,
        )

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_strips_whitespace(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should strip whitespace from text."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * EMBEDDING_DIMENSIONS)]
        mock_response.usage.total_tokens = 10

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        service = EmbeddingService()
        await service.embed_text("  test text  ")

        mock_client.embeddings.create.assert_called_once()
        call_args = mock_client.embeddings.create.call_args
        assert call_args[1]["input"] == "test text"

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_raises_on_empty_text(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should raise ValueError for empty text."""
        mock_settings.return_value.openai_api_key = "test-key"
        mock_openai_class.return_value = MagicMock()

        service = EmbeddingService()

        with pytest.raises(ValueError, match="Cannot embed empty text"):
            await service.embed_text("")

        with pytest.raises(ValueError, match="Cannot embed empty text"):
            await service.embed_text("   ")

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_raises_service_error_on_api_failure(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should raise EmbeddingServiceError on API failure."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=Exception("API Error"))
        mock_openai_class.return_value = mock_client

        service = EmbeddingService()

        with pytest.raises(EmbeddingServiceError) as exc_info:
            await service.embed_text("test text")

        assert exc_info.value.code == "EMBEDDING_GENERATION_FAILED"


class TestEmbeddingServiceEmbedBatch:
    """Tests for batch embedding."""

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_generates_batch_embeddings(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should generate embeddings for batch of texts."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_embeddings = [
            MagicMock(embedding=[0.1] * EMBEDDING_DIMENSIONS),
            MagicMock(embedding=[0.2] * EMBEDDING_DIMENSIONS),
        ]
        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        mock_response.usage.total_tokens = 20

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        service = EmbeddingService()
        results = await service.embed_batch(["text 1", "text 2"])

        assert len(results) == 2
        assert results[0][0] == 0.1
        assert results[1][0] == 0.2

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_handles_empty_strings_with_skip(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should return None for empty strings when skip_empty=True."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_embeddings = [
            MagicMock(embedding=[0.1] * EMBEDDING_DIMENSIONS),
        ]
        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        mock_response.usage.total_tokens = 10

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        service = EmbeddingService()
        results = await service.embed_batch(["", "valid text", "  "], skip_empty=True)

        assert len(results) == 3
        assert results[0] is None
        assert results[1] is not None
        assert results[2] is None

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_raises_on_empty_string_without_skip(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should raise ValueError for empty strings when skip_empty=False."""
        mock_settings.return_value.openai_api_key = "test-key"
        mock_openai_class.return_value = MagicMock()

        service = EmbeddingService()

        with pytest.raises(ValueError, match="Empty text at index 1"):
            await service.embed_batch(["valid", "", "also valid"], skip_empty=False)

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_raises_on_batch_too_large(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should raise ValueError when batch exceeds limit."""
        mock_settings.return_value.openai_api_key = "test-key"
        mock_openai_class.return_value = MagicMock()

        service = EmbeddingService()

        with pytest.raises(ValueError, match="exceeds max"):
            await service.embed_batch(["text"] * 101)

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_returns_all_none_for_all_empty(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should return all None for batch of empty strings."""
        mock_settings.return_value.openai_api_key = "test-key"
        mock_openai_class.return_value = MagicMock()

        service = EmbeddingService()
        results = await service.embed_batch(["", "  ", ""], skip_empty=True)

        assert results == [None, None, None]


class TestEmbeddingServiceCaching:
    """Tests for embedding caching."""

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_returns_cached_embedding(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should return cached embedding if available."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock Redis with cached value
        mock_redis = AsyncMock()
        cached_embedding = [0.5] * EMBEDDING_DIMENSIONS
        mock_redis.get.return_value = str(cached_embedding)

        service = EmbeddingService(redis_client=mock_redis)

        # Patch json.loads to handle the cached value
        with patch("json.loads", return_value=cached_embedding):
            result = await service.embed_text("cached text")

        # Should not call OpenAI API
        mock_client.embeddings.create.assert_not_called()
        assert result == cached_embedding

    @pytest.mark.asyncio
    @patch("app.services.rag.embedder.get_settings")
    @patch("app.services.rag.embedder.AsyncOpenAI")
    async def test_caches_new_embedding(
        self, mock_openai_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should cache newly generated embedding."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_embedding = [0.1] * EMBEDDING_DIMENSIONS
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding)]
        mock_response.usage.total_tokens = 10

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No cached value

        service = EmbeddingService(redis_client=mock_redis)
        await service.embed_text("new text")

        # Should have cached the result
        mock_redis.setex.assert_called_once()
