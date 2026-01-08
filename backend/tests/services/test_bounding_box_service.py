"""Tests for bounding box service."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.ocr import OCRBoundingBox
from app.services.bounding_box_service import (
    BoundingBoxService,
    BoundingBoxServiceError,
)


class TestBoundingBoxService:
    """Tests for BoundingBoxService class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def service(self, mock_client: MagicMock) -> BoundingBoxService:
        """Create service with mock client."""
        return BoundingBoxService(client=mock_client)

    def test_save_bounding_boxes_empty_list(
        self,
        service: BoundingBoxService,
    ) -> None:
        """Should return 0 for empty bounding box list."""
        result = service.save_bounding_boxes(
            document_id="doc-123",
            matter_id="matter-456",
            bounding_boxes=[],
        )

        assert result == 0

    def test_save_bounding_boxes_single_box(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should save single bounding box."""
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[{"id": "bbox-1"}])
        )

        boxes = [
            OCRBoundingBox(
                page=1,
                x=10.0,
                y=20.0,
                width=30.0,
                height=10.0,
                text="Test",
                confidence=0.95,
            ),
        ]

        result = service.save_bounding_boxes(
            document_id="doc-123",
            matter_id="matter-456",
            bounding_boxes=boxes,
        )

        assert result == 1
        mock_client.table.assert_called_with("bounding_boxes")

    def test_save_bounding_boxes_batched(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should save bounding boxes in batches."""
        # Create 150 boxes (should be 2 batches with default 100)
        boxes = [
            OCRBoundingBox(
                page=1,
                x=(i % 50) * 1.0,  # Keep x under 100
                y=20.0,
                width=10.0,
                height=10.0,
                text=f"Box {i}",
                confidence=0.95,
            )
            for i in range(150)
        ]

        # Mock returns data for each batch
        mock_client.table.return_value.insert.return_value.execute.side_effect = [
            MagicMock(data=[{"id": f"bbox-{i}"} for i in range(100)]),
            MagicMock(data=[{"id": f"bbox-{i}"} for i in range(50)]),
        ]

        result = service.save_bounding_boxes(
            document_id="doc-123",
            matter_id="matter-456",
            bounding_boxes=boxes,
            batch_size=100,
        )

        assert result == 150
        assert mock_client.table.return_value.insert.call_count == 2

    def test_save_bounding_boxes_includes_required_fields(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should include all required fields in insert."""
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[{"id": "bbox-1"}])
        )

        boxes = [
            OCRBoundingBox(
                page=1,
                x=10.0,
                y=20.0,
                width=30.0,
                height=10.0,
                text="Test text",
                confidence=0.95,
                reading_order_index=0,
            ),
        ]

        service.save_bounding_boxes(
            document_id="doc-123",
            matter_id="matter-456",
            bounding_boxes=boxes,
        )

        # Get the records that were inserted
        insert_call = mock_client.table.return_value.insert.call_args
        records = insert_call.args[0]

        assert len(records) == 1
        record = records[0]
        assert record["document_id"] == "doc-123"
        assert record["matter_id"] == "matter-456"
        assert record["page_number"] == 1
        assert record["x"] == 10.0
        assert record["y"] == 20.0
        assert record["width"] == 30.0
        assert record["height"] == 10.0
        assert record["text"] == "Test text"
        assert record["confidence"] == 0.95
        assert record["reading_order_index"] == 0

    def test_save_bounding_boxes_raises_on_error(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise BoundingBoxServiceError on database error."""
        mock_client.table.return_value.insert.return_value.execute.side_effect = (
            Exception("Database error")
        )

        boxes = [
            OCRBoundingBox(
                page=1,
                x=10.0,
                y=20.0,
                width=30.0,
                height=10.0,
                text="Test",
                confidence=0.95,
            ),
        ]

        with pytest.raises(BoundingBoxServiceError) as exc_info:
            service.save_bounding_boxes(
                document_id="doc-123",
                matter_id="matter-456",
                bounding_boxes=boxes,
            )

        assert exc_info.value.code == "SAVE_FAILED"

    def test_delete_bounding_boxes(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should delete bounding boxes by document ID."""
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": "bbox-1"}, {"id": "bbox-2"}])
        )

        result = service.delete_bounding_boxes("doc-123")

        assert result == 2
        mock_client.table.assert_called_with("bounding_boxes")
        mock_client.table.return_value.delete.return_value.eq.assert_called_with(
            "document_id", "doc-123"
        )

    def test_delete_bounding_boxes_raises_on_error(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise BoundingBoxServiceError on delete error."""
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = (
            Exception("Delete failed")
        )

        with pytest.raises(BoundingBoxServiceError) as exc_info:
            service.delete_bounding_boxes("doc-123")

        assert exc_info.value.code == "DELETE_FAILED"


class TestBoundingBoxServiceClientNotConfigured:
    """Tests for when client is not configured."""

    @patch("app.services.bounding_box_service.get_service_client", return_value=None)
    def test_save_raises_when_client_none(
        self,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        service = BoundingBoxService()
        service.client = None  # Explicitly set to None

        boxes = [
            OCRBoundingBox(
                page=1, x=10.0, y=20.0, width=30.0, height=10.0, text="Test"
            ),
        ]

        with pytest.raises(BoundingBoxServiceError) as exc_info:
            service.save_bounding_boxes(
                document_id="doc-123",
                matter_id="matter-456",
                bounding_boxes=boxes,
            )

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @patch("app.services.bounding_box_service.get_service_client", return_value=None)
    def test_delete_raises_when_client_none(
        self,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        service = BoundingBoxService()
        service.client = None  # Explicitly set to None

        with pytest.raises(BoundingBoxServiceError) as exc_info:
            service.delete_bounding_boxes("doc-123")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"


class TestBoundingBoxServiceRetrievalMethods:
    """Tests for bounding box retrieval methods."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_client: MagicMock) -> BoundingBoxService:
        """Create service with mock client."""
        return BoundingBoxService(client=mock_client)

    @pytest.fixture
    def sample_bbox_rows(self) -> list[dict]:
        """Sample bounding box database rows."""
        return [
            {
                "id": "bbox-1",
                "document_id": "doc-123",
                "page_number": 1,
                "x": 10.0,
                "y": 20.0,
                "width": 30.0,
                "height": 10.0,
                "text": "Hello",
                "confidence": 0.95,
                "reading_order_index": 0,
            },
            {
                "id": "bbox-2",
                "document_id": "doc-123",
                "page_number": 1,
                "x": 50.0,
                "y": 20.0,
                "width": 30.0,
                "height": 10.0,
                "text": "World",
                "confidence": 0.90,
                "reading_order_index": 1,
            },
        ]

    def test_get_bounding_boxes_for_page(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
        sample_bbox_rows: list[dict],
    ) -> None:
        """Should get bounding boxes for a page ordered by reading order."""
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=sample_bbox_rows)

        result = service.get_bounding_boxes_for_page("doc-123", 1)

        assert len(result) == 2
        assert result[0]["id"] == "bbox-1"
        assert result[0]["reading_order_index"] == 0
        assert result[1]["id"] == "bbox-2"
        mock_client.table.assert_called_with("bounding_boxes")

    def test_get_bounding_boxes_for_document(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
        sample_bbox_rows: list[dict],
    ) -> None:
        """Should get bounding boxes for document with pagination."""
        # Mock count query
        mock_count_query = MagicMock()
        mock_count_query.eq.return_value = mock_count_query
        mock_count_query.execute.return_value = MagicMock(count=100)

        # Mock data query
        mock_data_query = MagicMock()
        mock_data_query.eq.return_value = mock_data_query
        mock_data_query.order.return_value = mock_data_query
        mock_data_query.limit.return_value = mock_data_query
        mock_data_query.range.return_value = mock_data_query
        mock_data_query.execute.return_value = MagicMock(data=sample_bbox_rows)

        mock_client.table.return_value.select.side_effect = [
            mock_count_query,
            mock_data_query,
        ]

        boxes, total = service.get_bounding_boxes_for_document("doc-123", page=1)

        assert len(boxes) == 2
        assert total == 100
        assert boxes[0]["id"] == "bbox-1"

    def test_get_bounding_boxes_by_ids(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
        sample_bbox_rows: list[dict],
    ) -> None:
        """Should get bounding boxes by their IDs."""
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.in_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=sample_bbox_rows)

        result = service.get_bounding_boxes_by_ids(["bbox-1", "bbox-2"])

        assert len(result) == 2
        mock_query.in_.assert_called_with("id", ["bbox-1", "bbox-2"])

    def test_get_bounding_boxes_by_ids_empty_list(
        self,
        service: BoundingBoxService,
    ) -> None:
        """Should return empty list for empty bbox_ids."""
        result = service.get_bounding_boxes_by_ids([])
        assert result == []

    def test_get_bounding_boxes_for_page_raises_on_error(
        self,
        service: BoundingBoxService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise BoundingBoxServiceError on retrieval error."""
        mock_client.table.return_value.select.side_effect = Exception("DB error")

        with pytest.raises(BoundingBoxServiceError) as exc_info:
            service.get_bounding_boxes_for_page("doc-123", 1)

        assert exc_info.value.code == "GET_PAGE_FAILED"
