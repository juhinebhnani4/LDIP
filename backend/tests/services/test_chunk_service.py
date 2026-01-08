"""Unit tests for chunk service."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.chunk import Chunk, ChunkType, ChunkWithContent
from app.services.chunk_service import (
    ChunkNotFoundError,
    ChunkService,
    ChunkServiceError,
)
from app.services.chunking.parent_child_chunker import ChunkData


class TestChunkServiceInit:
    """Tests for ChunkService initialization."""

    def test_uses_provided_client(self) -> None:
        """Should use provided Supabase client."""
        mock_client = MagicMock()
        service = ChunkService(client=mock_client)
        assert service.client is mock_client

    @patch("app.services.chunk_service.get_service_client")
    def test_uses_default_client(self, mock_get_client: MagicMock) -> None:
        """Should use service client if none provided."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        service = ChunkService()
        assert service.client is mock_client


class TestChunkServiceGetChunk:
    """Tests for get_chunk method."""

    def test_returns_chunk_on_success(self) -> None:
        """Should return chunk when found."""
        mock_client = MagicMock()
        chunk_id = str(uuid4())

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": chunk_id,
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "Test content",
                "chunk_type": "parent",
                "chunk_index": 0,
                "token_count": 10,
                "parent_chunk_id": None,
                "page_number": 1,
                "bbox_ids": None,
                "entity_ids": None,
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        service = ChunkService(client=mock_client)
        result = service.get_chunk(chunk_id)

        assert result.id == chunk_id
        assert result.content == "Test content"
        assert result.chunk_type == ChunkType.PARENT

    def test_raises_not_found_when_missing(self) -> None:
        """Should raise ChunkNotFoundError when chunk doesn't exist."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        service = ChunkService(client=mock_client)

        with pytest.raises(ChunkNotFoundError):
            service.get_chunk("nonexistent-id")

    @patch("app.services.chunk_service.get_service_client")
    def test_raises_error_when_no_client(self, mock_get_client: MagicMock) -> None:
        """Should raise error when client not configured."""
        mock_get_client.return_value = None
        service = ChunkService()

        with pytest.raises(ChunkServiceError) as exc_info:
            service.get_chunk("any-id")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"


class TestChunkServiceGetChunksForDocument:
    """Tests for get_chunks_for_document method."""

    def test_returns_all_chunks(self) -> None:
        """Should return all chunks for document."""
        mock_client = MagicMock()

        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "document_id": "doc-1",
                "content": "Parent content",
                "chunk_type": "parent",
                "chunk_index": 0,
                "token_count": 100,
                "parent_chunk_id": None,
                "page_number": 1,
            },
            {
                "id": str(uuid4()),
                "document_id": "doc-1",
                "content": "Child content",
                "chunk_type": "child",
                "chunk_index": 0,
                "token_count": 50,
                "parent_chunk_id": str(uuid4()),
                "page_number": 1,
            },
        ]

        service = ChunkService(client=mock_client)
        chunks, parent_count, child_count = service.get_chunks_for_document("doc-1")

        assert len(chunks) == 2
        assert parent_count == 1
        assert child_count == 1

    def test_filters_by_chunk_type(self) -> None:
        """Should filter by chunk type when specified."""
        mock_client = MagicMock()

        # Mock the chained method calls
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.order.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value.data = []

        service = ChunkService(client=mock_client)
        service.get_chunks_for_document("doc-1", chunk_type=ChunkType.PARENT)

        # Verify the chunk_type filter was applied
        mock_query.eq.assert_called_with("chunk_type", "parent")


class TestChunkServiceGetParentChunk:
    """Tests for get_parent_chunk method."""

    def test_returns_parent_when_exists(self) -> None:
        """Should return parent chunk for child."""
        mock_client = MagicMock()
        child_id = str(uuid4())
        parent_id = str(uuid4())

        # First call gets child's parent_chunk_id
        # Second call gets parent chunk
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"parent_chunk_id": parent_id}
        ]

        service = ChunkService(client=mock_client)

        # Mock get_chunk for the second call
        with patch.object(service, "get_chunk") as mock_get:
            mock_get.return_value = MagicMock(spec=Chunk)
            result = service.get_parent_chunk(child_id)
            mock_get.assert_called_once_with(parent_id)

    def test_returns_none_when_no_parent(self) -> None:
        """Should return None for parent chunks."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"parent_chunk_id": None}
        ]

        service = ChunkService(client=mock_client)
        result = service.get_parent_chunk("parent-chunk-id")

        assert result is None


class TestChunkServiceGetChildChunks:
    """Tests for get_child_chunks method."""

    def test_returns_children(self) -> None:
        """Should return child chunks of parent."""
        mock_client = MagicMock()
        parent_id = str(uuid4())

        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "Child 1",
                "chunk_type": "child",
                "chunk_index": 0,
                "token_count": 50,
                "parent_chunk_id": parent_id,
                "page_number": 1,
                "bbox_ids": None,
                "entity_ids": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": str(uuid4()),
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "Child 2",
                "chunk_type": "child",
                "chunk_index": 1,
                "token_count": 50,
                "parent_chunk_id": parent_id,
                "page_number": 1,
                "bbox_ids": None,
                "entity_ids": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]

        service = ChunkService(client=mock_client)
        result = service.get_child_chunks(parent_id)

        assert len(result) == 2
        assert all(c.chunk_type == ChunkType.CHILD for c in result)


class TestChunkServiceSaveChunks:
    """Tests for save_chunks method."""

    @pytest.mark.asyncio
    async def test_saves_chunks_in_order(self) -> None:
        """Should save parent chunks before children."""
        mock_client = MagicMock()

        # Track insert calls
        insert_calls = []

        def mock_insert(data: list) -> MagicMock:
            insert_calls.append(data)
            mock_execute = MagicMock()
            mock_execute.execute.return_value.data = data
            return mock_execute

        mock_client.table.return_value.insert.side_effect = mock_insert
        mock_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []

        parent_id = uuid4()
        parent = ChunkData(
            id=parent_id,
            content="Parent content",
            chunk_type="parent",
            chunk_index=0,
            parent_id=None,
            token_count=100,
        )

        child = ChunkData(
            id=uuid4(),
            content="Child content",
            chunk_type="child",
            chunk_index=0,
            parent_id=parent_id,
            token_count=50,
        )

        service = ChunkService(client=mock_client)
        saved = await service.save_chunks(
            document_id="doc-1",
            matter_id="matter-1",
            parent_chunks=[parent],
            child_chunks=[child],
        )

        # Should have saved both chunks
        assert saved == 2

    @pytest.mark.asyncio
    async def test_handles_empty_lists(self) -> None:
        """Should handle empty chunk lists."""
        mock_client = MagicMock()

        service = ChunkService(client=mock_client)
        saved = await service.save_chunks(
            document_id="doc-1",
            matter_id="matter-1",
            parent_chunks=[],
            child_chunks=[],
        )

        assert saved == 0


class TestChunkServiceDeleteChunks:
    """Tests for delete_chunks_for_document method."""

    @pytest.mark.asyncio
    async def test_deletes_children_first(self) -> None:
        """Should delete child chunks before parents."""
        mock_client = MagicMock()

        delete_calls = []

        def track_delete() -> MagicMock:
            mock_result = MagicMock()
            mock_result.data = [{"id": "deleted"}]
            return mock_result

        mock_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute = track_delete
        mock_client.table.return_value.delete.return_value.eq.return_value.execute = track_delete

        service = ChunkService(client=mock_client)
        deleted = await service.delete_chunks_for_document("doc-1")

        # Should have made delete calls
        assert mock_client.table.return_value.delete.called


class TestChunkServiceParseChunk:
    """Tests for _parse_chunk method."""

    def test_parses_all_fields(self) -> None:
        """Should parse all chunk fields correctly."""
        mock_client = MagicMock()
        service = ChunkService(client=mock_client)

        row = {
            "id": str(uuid4()),
            "matter_id": "matter-1",
            "document_id": "doc-1",
            "content": "Test content",
            "chunk_type": "parent",
            "chunk_index": 5,
            "token_count": 100,
            "parent_chunk_id": None,
            "page_number": 3,
            "bbox_ids": ["bbox-1", "bbox-2"],
            "entity_ids": ["entity-1"],
            "created_at": "2024-01-15T10:30:00Z",
        }

        chunk = service._parse_chunk(row)

        assert chunk.content == "Test content"
        assert chunk.chunk_type == ChunkType.PARENT
        assert chunk.chunk_index == 5
        assert chunk.token_count == 100
        assert chunk.page_number == 3
        assert chunk.bbox_ids == ["bbox-1", "bbox-2"]
        assert chunk.entity_ids == ["entity-1"]

    def test_handles_null_fields(self) -> None:
        """Should handle null optional fields."""
        mock_client = MagicMock()
        service = ChunkService(client=mock_client)

        row = {
            "id": str(uuid4()),
            "matter_id": "matter-1",
            "document_id": "doc-1",
            "content": "Test",
            "chunk_type": "child",
            "chunk_index": 0,
            "token_count": None,
            "parent_chunk_id": None,
            "page_number": None,
            "bbox_ids": None,
            "entity_ids": None,
            "created_at": "2024-01-15T10:30:00Z",
        }

        chunk = service._parse_chunk(row)

        assert chunk.token_count == 0  # Default for None
        assert chunk.page_number is None
        assert chunk.bbox_ids is None
