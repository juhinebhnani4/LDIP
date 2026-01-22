"""Tests for table extraction service.

Story: RAG Production Gaps - Feature 1: Table Extraction
Tests the TableExtractor service with mocked Docling.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.table_extraction.extractor import TableExtractor, get_table_extractor
from app.services.table_extraction.models import ExtractedTable, TableExtractionResult


class TestTableExtractor:
    """Tests for TableExtractor class."""

    @pytest.fixture
    def extractor(self) -> TableExtractor:
        """Create a fresh TableExtractor instance."""
        return TableExtractor()

    @pytest.fixture
    def mock_table_data(self) -> list[list[str]]:
        """Sample table data for testing."""
        return [
            ["Name", "Amount", "Date"],
            ["John Doe", "1000.00", "2024-01-15"],
            ["Jane Smith", "2500.50", "2024-02-20"],
        ]

    @pytest.fixture
    def mock_docling_table(self, mock_table_data: list[list[str]]) -> MagicMock:
        """Create a mock Docling table object."""
        table = MagicMock()
        table.data = mock_table_data
        table.score = 0.95

        # Mock provenance for bounding box
        prov = MagicMock()
        prov.page_no = 1
        prov.bbox = MagicMock()
        prov.bbox.l = 0.1
        prov.bbox.t = 0.2
        prov.bbox.r = 0.9
        prov.bbox.b = 0.5
        table.prov = [prov]
        table.caption = None

        return table

    @pytest.mark.anyio
    async def test_extract_tables_returns_result(self, extractor: TableExtractor) -> None:
        """Should return TableExtractionResult even with no tables."""
        # Mock the converter
        mock_doc = MagicMock()
        mock_doc.tables = []
        mock_result = MagicMock()
        mock_result.document = mock_doc

        # Mock file existence
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda x: "/tmp/test.pdf"

        with patch.object(extractor, "_converter", MagicMock()) as mock_converter:
            mock_converter.convert.return_value = mock_result

            result = await extractor.extract_tables(
                file_path=mock_path,
                matter_id="matter-123",
                document_id="doc-456",
            )

            assert result.document_id == "doc-456"
            assert result.matter_id == "matter-123"
            assert result.total_tables == 0
            assert result.error is None
            assert result.success is True

    @pytest.mark.anyio
    async def test_extract_tables_with_tables(
        self,
        extractor: TableExtractor,
        mock_docling_table: MagicMock,
    ) -> None:
        """Should extract tables and convert to markdown."""
        mock_doc = MagicMock()
        mock_doc.tables = [mock_docling_table]
        mock_result = MagicMock()
        mock_result.document = mock_doc

        # Mock file existence
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda x: "/tmp/test.pdf"

        with patch.object(extractor, "_converter", MagicMock()) as mock_converter:
            mock_converter.convert.return_value = mock_result

            result = await extractor.extract_tables(
                file_path=mock_path,
                matter_id="matter-123",
                document_id="doc-456",
            )

            assert result.total_tables == 1
            assert result.success is True
            assert len(result.tables) == 1

            table = result.tables[0]
            assert table.table_index == 0
            assert table.row_count == 3
            assert table.col_count == 3
            assert table.confidence == 0.95
            assert table.page_number == 1
            assert "Name" in table.markdown_content
            assert "John Doe" in table.markdown_content

    @pytest.mark.anyio
    async def test_extract_tables_handles_error_gracefully(
        self, extractor: TableExtractor
    ) -> None:
        """Should return empty result on error, not raise."""
        # Mock file existence
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda x: "/tmp/test.pdf"

        with patch.object(extractor, "_converter", MagicMock()) as mock_converter:
            mock_converter.convert.side_effect = Exception("Docling failed")

            result = await extractor.extract_tables(
                file_path=mock_path,
                matter_id="matter-123",
                document_id="doc-456",
            )

            assert result.total_tables == 0
            assert result.error == "Docling failed"
            assert result.success is False

    @pytest.mark.anyio
    async def test_extract_tables_file_not_found(self, extractor: TableExtractor) -> None:
        """Should return error result when file not found."""
        result = await extractor.extract_tables(
            file_path=Path("/nonexistent/path/test.pdf"),
            matter_id="matter-123",
            document_id="doc-456",
        )

        assert result.total_tables == 0
        assert result.error is not None
        assert "not found" in result.error.lower()

    @pytest.mark.anyio
    async def test_extract_tables_disabled_by_config(
        self, extractor: TableExtractor
    ) -> None:
        """Should skip extraction when disabled in config."""
        with patch("app.services.table_extraction.extractor.get_settings") as mock_settings:
            mock_settings.return_value.table_extraction_enabled = False

            # Create new extractor with mocked settings
            new_extractor = TableExtractor()

            result = await new_extractor.extract_tables(
                file_path=Path("/tmp/test.pdf"),
                matter_id="matter-123",
                document_id="doc-456",
            )

            assert result.total_tables == 0
            assert result.error is None

    @pytest.mark.anyio
    async def test_extract_tables_skips_empty_tables(
        self, extractor: TableExtractor
    ) -> None:
        """Should skip tables with insufficient data."""
        # Table with only header row (no data)
        empty_table = MagicMock()
        empty_table.data = [["Header1", "Header2"]]  # Only header, no data rows
        empty_table.score = 0.9
        empty_table.prov = []
        empty_table.caption = None

        mock_doc = MagicMock()
        mock_doc.tables = [empty_table]
        mock_result = MagicMock()
        mock_result.document = mock_doc

        with patch.object(extractor, "_converter", MagicMock()) as mock_converter:
            mock_converter.convert.return_value = mock_result

            result = await extractor.extract_tables(
                file_path=Path("/tmp/test.pdf"),
                matter_id="matter-123",
                document_id="doc-456",
            )

            # Empty table should be skipped
            assert result.total_tables == 0

    def test_process_table_extracts_bounding_box(
        self,
        extractor: TableExtractor,
        mock_docling_table: MagicMock,
    ) -> None:
        """Should extract bounding box coordinates correctly."""
        extracted = extractor._process_table(mock_docling_table, 0)

        assert extracted is not None
        assert extracted.bounding_box is not None
        assert extracted.bounding_box.page == 1
        assert extracted.bounding_box.x == 0.1
        assert extracted.bounding_box.y == 0.2
        assert extracted.bounding_box.width == pytest.approx(0.8)
        assert extracted.bounding_box.height == pytest.approx(0.3)


class TestTableFormatter:
    """Tests for TableFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create a TableFormatter instance."""
        from app.services.table_extraction.formatter import TableFormatter

        return TableFormatter()

    def test_to_markdown_basic(self, formatter) -> None:
        """Should convert basic table to markdown."""
        table_data = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ]

        markdown = formatter.to_markdown(table_data)

        assert "| Name | Age |" in markdown
        assert "| --- | --- |" in markdown
        assert "| Alice | 30 |" in markdown
        assert "| Bob | 25 |" in markdown

    def test_to_markdown_escapes_pipes(self, formatter) -> None:
        """Should escape pipe characters in cell values."""
        table_data = [
            ["Formula", "Result"],
            ["a|b", "value"],
        ]

        markdown = formatter.to_markdown(table_data)

        assert "a\\|b" in markdown

    def test_to_markdown_empty_table(self, formatter) -> None:
        """Should return empty string for empty table."""
        assert formatter.to_markdown([]) == ""
        assert formatter.to_markdown([[]]) == ""

    def test_to_json_basic(self, formatter) -> None:
        """Should convert table to list of dicts."""
        table_data = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ]

        json_data = formatter.to_json(table_data)

        assert len(json_data) == 2
        assert json_data[0] == {"Name": "Alice", "Age": "30"}
        assert json_data[1] == {"Name": "Bob", "Age": "25"}

    def test_to_json_empty_table(self, formatter) -> None:
        """Should return empty list for empty/header-only table."""
        assert formatter.to_json([]) == []
        assert formatter.to_json([["Header"]]) == []


class TestGetTableExtractor:
    """Tests for singleton factory function."""

    def test_returns_singleton(self) -> None:
        """Should return the same instance on multiple calls."""
        # Clear cache first
        get_table_extractor.cache_clear()

        extractor1 = get_table_extractor()
        extractor2 = get_table_extractor()

        assert extractor1 is extractor2

    def test_returns_table_extractor_instance(self) -> None:
        """Should return TableExtractor instance."""
        get_table_extractor.cache_clear()
        extractor = get_table_extractor()
        assert isinstance(extractor, TableExtractor)
