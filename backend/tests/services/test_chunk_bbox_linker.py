"""Tests for chunk-to-bounding-box linking service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.chunk_bbox_linker import (
    ChunkBBoxLinker,
    ChunkBBoxLinkerError,
)


class TestChunkBBoxLinker:
    """Tests for ChunkBBoxLinker class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.fixture
    def mock_bbox_service(self) -> MagicMock:
        """Create mock BoundingBoxService."""
        return MagicMock()

    @pytest.fixture
    def linker(
        self,
        mock_client: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> ChunkBBoxLinker:
        """Create linker with mock dependencies."""
        return ChunkBBoxLinker(client=mock_client, bbox_service=mock_bbox_service)

    def test_link_chunk_to_bboxes_success(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should link chunk to bounding boxes successfully."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "chunk-123"}]
        )

        result = linker.link_chunk_to_bboxes("chunk-123", ["bbox-1", "bbox-2"])

        assert result is True
        mock_client.table.assert_called_with("chunks")
        mock_client.table.return_value.update.assert_called_with(
            {"bbox_ids": ["bbox-1", "bbox-2"]}
        )

    def test_link_chunk_to_bboxes_empty_list(
        self,
        linker: ChunkBBoxLinker,
    ) -> None:
        """Should return True for empty bbox_ids list."""
        result = linker.link_chunk_to_bboxes("chunk-123", [])

        assert result is True

    def test_link_chunk_to_bboxes_raises_on_error(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should raise ChunkBBoxLinkerError on database error."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.link_chunk_to_bboxes("chunk-123", ["bbox-1"])

        assert exc_info.value.code == "LINK_FAILED"

    def test_add_bboxes_to_chunk_merges_existing(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should merge new bbox_ids with existing ones."""
        # Mock getting existing bbox_ids
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"bbox_ids": ["bbox-1", "bbox-2"]}]
        )
        # Mock updating with merged list
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "chunk-123"}]
        )

        result = linker.add_bboxes_to_chunk("chunk-123", ["bbox-2", "bbox-3"])

        assert result is True
        # Should have called update with merged, deduplicated list
        update_call = mock_client.table.return_value.update.call_args
        updated_ids = set(update_call.args[0]["bbox_ids"])
        assert updated_ids == {"bbox-1", "bbox-2", "bbox-3"}

    def test_add_bboxes_to_chunk_raises_on_not_found(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should raise when chunk not found."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.add_bboxes_to_chunk("nonexistent", ["bbox-1"])

        assert exc_info.value.code == "CHUNK_NOT_FOUND"

    def test_get_bboxes_for_chunk_success(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Should get bounding boxes for a chunk."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"bbox_ids": ["bbox-1", "bbox-2"]}]
        )
        mock_bbox_service.get_bounding_boxes_by_ids.return_value = [
            {"id": "bbox-1", "text": "Hello"},
            {"id": "bbox-2", "text": "World"},
        ]

        result = linker.get_bboxes_for_chunk("chunk-123")

        assert len(result) == 2
        mock_bbox_service.get_bounding_boxes_by_ids.assert_called_with(
            ["bbox-1", "bbox-2"]
        )

    def test_get_bboxes_for_chunk_empty_bbox_ids(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should return empty list when chunk has no bbox_ids."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"bbox_ids": []}]
        )

        result = linker.get_bboxes_for_chunk("chunk-123")

        assert result == []

    def test_get_bboxes_for_chunk_raises_on_not_found(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should raise when chunk not found."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.get_bboxes_for_chunk("nonexistent")

        assert exc_info.value.code == "CHUNK_NOT_FOUND"

    def test_clear_chunk_bboxes_success(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should clear all bbox links from a chunk."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "chunk-123"}]
        )

        result = linker.clear_chunk_bboxes("chunk-123")

        assert result is True
        mock_client.table.return_value.update.assert_called_with({"bbox_ids": []})

    def test_clear_chunk_bboxes_raises_on_error(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should raise ChunkBBoxLinkerError on database error."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.clear_chunk_bboxes("chunk-123")

        assert exc_info.value.code == "CLEAR_FAILED"

    def test_clear_chunk_bboxes_returns_false_on_no_match(
        self,
        linker: ChunkBBoxLinker,
        mock_client: MagicMock,
    ) -> None:
        """Should return False when chunk not found (no data returned)."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = linker.clear_chunk_bboxes("nonexistent")

        assert result is False


class TestChunkBBoxLinkerClientNotConfigured:
    """Tests for when client is not configured."""

    @patch("app.services.chunk_bbox_linker.get_service_client", return_value=None)
    @patch("app.services.chunk_bbox_linker.get_bounding_box_service")
    def test_link_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        linker = ChunkBBoxLinker()
        linker.client = None

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.link_chunk_to_bboxes("chunk-123", ["bbox-1"])

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @patch("app.services.chunk_bbox_linker.get_service_client", return_value=None)
    @patch("app.services.chunk_bbox_linker.get_bounding_box_service")
    def test_get_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        linker = ChunkBBoxLinker()
        linker.client = None

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.get_bboxes_for_chunk("chunk-123")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @patch("app.services.chunk_bbox_linker.get_service_client", return_value=None)
    @patch("app.services.chunk_bbox_linker.get_bounding_box_service")
    def test_clear_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        linker = ChunkBBoxLinker()
        linker.client = None

        with pytest.raises(ChunkBBoxLinkerError) as exc_info:
            linker.clear_chunk_bboxes("chunk-123")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"
