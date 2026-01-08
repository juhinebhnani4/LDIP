"""Tests for citation service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.citation_service import (
    CitationService,
    CitationServiceError,
)


class TestCitationService:
    """Tests for CitationService class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.fixture
    def mock_bbox_service(self) -> MagicMock:
        """Create mock BoundingBoxService."""
        return MagicMock()

    @pytest.fixture
    def service(
        self,
        mock_client: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> CitationService:
        """Create service with mock dependencies."""
        return CitationService(client=mock_client, bbox_service=mock_bbox_service)

    def test_link_citation_to_source_bboxes_success(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should link source bounding boxes to citation successfully."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "citation-123"}]
        )

        result = service.link_citation_to_source_bboxes(
            "citation-123", ["bbox-1", "bbox-2"]
        )

        assert result is True
        mock_client.table.assert_called_with("citations")
        mock_client.table.return_value.update.assert_called_with(
            {"source_bbox_ids": ["bbox-1", "bbox-2"]}
        )

    def test_link_citation_to_source_bboxes_empty_list(
        self,
        service: CitationService,
    ) -> None:
        """Should return True for empty bbox_ids list."""
        result = service.link_citation_to_source_bboxes("citation-123", [])

        assert result is True

    def test_link_citation_to_source_bboxes_raises_on_error(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise CitationServiceError on database error."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(CitationServiceError) as exc_info:
            service.link_citation_to_source_bboxes("citation-123", ["bbox-1"])

        assert exc_info.value.code == "SOURCE_LINK_FAILED"

    def test_link_citation_to_target_bboxes_success(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should link target bounding boxes to citation successfully."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "citation-123"}]
        )

        result = service.link_citation_to_target_bboxes(
            "citation-123", ["bbox-3", "bbox-4"]
        )

        assert result is True
        mock_client.table.return_value.update.assert_called_with(
            {"target_bbox_ids": ["bbox-3", "bbox-4"]}
        )

    def test_link_citation_to_target_bboxes_empty_list(
        self,
        service: CitationService,
    ) -> None:
        """Should return True for empty bbox_ids list."""
        result = service.link_citation_to_target_bboxes("citation-123", [])

        assert result is True

    def test_link_citation_to_target_bboxes_raises_on_error(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise CitationServiceError on database error."""
        mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(CitationServiceError) as exc_info:
            service.link_citation_to_target_bboxes("citation-123", ["bbox-1"])

        assert exc_info.value.code == "TARGET_LINK_FAILED"

    def test_get_source_bboxes_for_citation_success(
        self,
        service: CitationService,
        mock_client: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Should get source bounding boxes for a citation."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"source_bbox_ids": ["bbox-1", "bbox-2"]}]
        )
        mock_bbox_service.get_bounding_boxes_by_ids.return_value = [
            {"id": "bbox-1", "text": "Citation"},
            {"id": "bbox-2", "text": "Text"},
        ]

        result = service.get_source_bboxes_for_citation("citation-123")

        assert len(result) == 2
        mock_bbox_service.get_bounding_boxes_by_ids.assert_called_with(
            ["bbox-1", "bbox-2"]
        )

    def test_get_source_bboxes_for_citation_empty(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should return empty list when citation has no source bbox_ids."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"source_bbox_ids": []}]
        )

        result = service.get_source_bboxes_for_citation("citation-123")

        assert result == []

    def test_get_source_bboxes_for_citation_raises_on_not_found(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise when citation not found."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(CitationServiceError) as exc_info:
            service.get_source_bboxes_for_citation("nonexistent")

        assert exc_info.value.code == "CITATION_NOT_FOUND"

    def test_get_target_bboxes_for_citation_success(
        self,
        service: CitationService,
        mock_client: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Should get target bounding boxes for a citation."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"target_bbox_ids": ["bbox-3", "bbox-4"]}]
        )
        mock_bbox_service.get_bounding_boxes_by_ids.return_value = [
            {"id": "bbox-3", "text": "Act"},
            {"id": "bbox-4", "text": "Section"},
        ]

        result = service.get_target_bboxes_for_citation("citation-123")

        assert len(result) == 2
        mock_bbox_service.get_bounding_boxes_by_ids.assert_called_with(
            ["bbox-3", "bbox-4"]
        )

    def test_get_target_bboxes_for_citation_empty(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should return empty list when citation has no target bbox_ids."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"target_bbox_ids": []}]
        )

        result = service.get_target_bboxes_for_citation("citation-123")

        assert result == []

    def test_get_target_bboxes_for_citation_raises_on_not_found(
        self,
        service: CitationService,
        mock_client: MagicMock,
    ) -> None:
        """Should raise when citation not found."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(CitationServiceError) as exc_info:
            service.get_target_bboxes_for_citation("nonexistent")

        assert exc_info.value.code == "CITATION_NOT_FOUND"

    def test_get_bboxes_for_citation_returns_both(
        self,
        service: CitationService,
        mock_client: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Should return both source and target bboxes."""
        # Setup mock for sequential calls
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"source_bbox_ids": ["bbox-1"]}]),
            MagicMock(data=[{"target_bbox_ids": ["bbox-2"]}]),
        ]
        mock_bbox_service.get_bounding_boxes_by_ids.side_effect = [
            [{"id": "bbox-1", "text": "Source"}],
            [{"id": "bbox-2", "text": "Target"}],
        ]

        result = service.get_bboxes_for_citation("citation-123")

        assert "source" in result
        assert "target" in result
        assert len(result["source"]) == 1
        assert len(result["target"]) == 1


class TestCitationServiceClientNotConfigured:
    """Tests for when client is not configured."""

    @patch("app.services.citation_service.get_service_client", return_value=None)
    @patch("app.services.citation_service.get_bounding_box_service")
    def test_link_source_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        service = CitationService()
        service.client = None

        with pytest.raises(CitationServiceError) as exc_info:
            service.link_citation_to_source_bboxes("citation-123", ["bbox-1"])

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @patch("app.services.citation_service.get_service_client", return_value=None)
    @patch("app.services.citation_service.get_bounding_box_service")
    def test_link_target_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        service = CitationService()
        service.client = None

        with pytest.raises(CitationServiceError) as exc_info:
            service.link_citation_to_target_bboxes("citation-123", ["bbox-1"])

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @patch("app.services.citation_service.get_service_client", return_value=None)
    @patch("app.services.citation_service.get_bounding_box_service")
    def test_get_source_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        service = CitationService()
        service.client = None

        with pytest.raises(CitationServiceError) as exc_info:
            service.get_source_bboxes_for_citation("citation-123")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @patch("app.services.citation_service.get_service_client", return_value=None)
    @patch("app.services.citation_service.get_bounding_box_service")
    def test_get_target_raises_when_client_none(
        self,
        mock_get_bbox_service: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise when client is None."""
        service = CitationService()
        service.client = None

        with pytest.raises(CitationServiceError) as exc_info:
            service.get_target_bboxes_for_citation("citation-123")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"
