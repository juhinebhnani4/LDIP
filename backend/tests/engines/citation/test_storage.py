"""Tests for Citation Storage service.

Story 3-1: Act Citation Extraction (AC: #3, #4)
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.engines.citation.storage import (
    BATCH_SIZE,
    CitationStorageError,
    CitationStorageService,
    get_citation_storage_service,
)
from app.models.citation import (
    ActResolutionStatus,
    CitationExtractionResult,
    ExtractedCitation,
    UserAction,
    VerificationStatus,
)


class TestCitationStorageServiceInit:
    """Tests for storage service initialization."""

    def test_init_lazy_client(self) -> None:
        """Should not initialize client on construction."""
        service = CitationStorageService()

        assert service._client is None

    def test_client_property_raises_on_missing(self) -> None:
        """Should raise error when Supabase not configured."""
        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=None,
        ):
            service = CitationStorageService()

            with pytest.raises(CitationStorageError) as exc_info:
                _ = service.client

            assert "not configured" in str(exc_info.value)
            assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"


class TestSaveCitations:
    """Tests for save_citations method."""

    @pytest.mark.asyncio
    async def test_save_empty_citations(self) -> None:
        """Should return 0 for empty citations."""
        service = CitationStorageService()

        result = await service.save_citations(
            matter_id="matter-123",
            document_id="doc-456",
            extraction_result=CitationExtractionResult(
                citations=[],
                unique_acts=[],
                source_document_id="doc-456",
                extraction_timestamp=datetime.now(UTC),
            ),
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_save_citations_batch_processing(self) -> None:
        """Should process citations in batches."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "1"}] * 10)

        # For act_resolutions upsert
        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data="res-id")

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data={
            "id": "res-id",
            "matter_id": "matter-123",
            "act_name_normalized": "test",
            "act_name_display": "Test",
            "resolution_status": "missing",
            "user_action": "pending",
            "citation_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        })

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            citations = [
                ExtractedCitation(
                    act_name="NI Act",
                    section=str(i),
                    raw_text=f"Section {i}",
                    confidence=80.0,
                )
                for i in range(10)
            ]

            result = await service.save_citations(
                matter_id="matter-123",
                document_id="doc-456",
                extraction_result=CitationExtractionResult(
                    citations=citations,
                    unique_acts=["Negotiable Instruments Act, 1881"],
                    source_document_id="doc-456",
                    extraction_timestamp=datetime.now(UTC),
                ),
            )

            assert result == 10

    @pytest.mark.asyncio
    async def test_save_citations_normalizes_confidence(self) -> None:
        """Should convert confidence from 0-100 to 0-1."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        inserted_records = []

        def capture_insert(records):
            inserted_records.extend(records)
            return mock_insert

        mock_client.table.return_value = mock_table
        mock_table.insert.side_effect = capture_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "1"}])

        # For act_resolutions
        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data="res-id")

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data={
            "id": "res-id",
            "matter_id": "matter-123",
            "act_name_normalized": "test",
            "act_name_display": "Test",
            "resolution_status": "missing",
            "user_action": "pending",
            "citation_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        })

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            await service.save_citations(
                matter_id="matter-123",
                document_id="doc-456",
                extraction_result=CitationExtractionResult(
                    citations=[
                        ExtractedCitation(
                            act_name="NI Act",
                            section="138",
                            raw_text="test",
                            confidence=85.0,
                        )
                    ],
                    unique_acts=["NI Act"],
                    source_document_id="doc-456",
                    extraction_timestamp=datetime.now(UTC),
                ),
            )

            # Verify confidence was converted
            assert len(inserted_records) == 1
            assert inserted_records[0]["confidence"] == 0.85


class TestGetCitations:
    """Tests for citation retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_citations_by_document(self) -> None:
        """Should retrieve citations for document."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_order = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.execute.return_value = MagicMock(
            data=[
                {
                    "id": "cit-1",
                    "matter_id": "matter-123",
                    "source_document_id": "doc-456",
                    "act_name": "NI Act",
                    "section": "138",
                    "source_page": 1,
                    "verification_status": "pending",
                    "confidence": 0.85,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ]
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            citations = await service.get_citations_by_document("doc-456")

            assert len(citations) == 1
            assert citations[0].id == "cit-1"

    @pytest.mark.asyncio
    async def test_get_citations_by_matter_with_pagination(self) -> None:
        """Should paginate citation results."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute.return_value = MagicMock(
            data=[
                {
                    "id": f"cit-{i}",
                    "matter_id": "matter-123",
                    "source_document_id": "doc-456",
                    "act_name": "NI Act",
                    "section": "138",
                    "source_page": 1,
                    "verification_status": "pending",
                    "confidence": 0.85,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
                for i in range(10)
            ],
            count=50,
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            citations, total = await service.get_citations_by_matter(
                matter_id="matter-123",
                page=2,
                per_page=10,
            )

            assert len(citations) == 10
            assert total == 50
            # Verify correct range was called (page 2, 10 per page = offset 10)
            mock_order.range.assert_called_with(10, 19)

    @pytest.mark.asyncio
    async def test_get_citation_by_id(self) -> None:
        """Should retrieve single citation by ID."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_single = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.single.return_value = mock_single
        mock_single.execute.return_value = MagicMock(
            data={
                "id": "cit-1",
                "matter_id": "matter-123",
                "source_document_id": "doc-456",
                "act_name": "NI Act",
                "section": "138",
                "source_page": 1,
                "verification_status": "verified",
                "confidence": 0.95,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            citation = await service.get_citation("cit-1")

            assert citation is not None
            assert citation.id == "cit-1"
            assert citation.verification_status == VerificationStatus.VERIFIED


class TestActResolutions:
    """Tests for act resolution methods."""

    @pytest.mark.asyncio
    async def test_create_act_resolution(self) -> None:
        """Should create new act resolution."""
        mock_client = MagicMock()
        mock_table = MagicMock()

        # For RPC call (fails)
        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception("RPC not found")

        # For select (not found)
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[])

        # For insert
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(
            data=[
                {
                    "id": "res-1",
                    "matter_id": "matter-123",
                    "act_name_normalized": "negotiable_instruments_act_1881",
                    "act_name_display": "Negotiable Instruments Act, 1881",
                    "resolution_status": "missing",
                    "user_action": "pending",
                    "citation_count": 1,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ]
        )

        mock_client.table.return_value = mock_table

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            resolution = await service.create_or_update_act_resolution(
                matter_id="matter-123",
                act_name="NI Act",
            )

            assert resolution is not None
            assert resolution.resolution_status == ActResolutionStatus.MISSING

    @pytest.mark.asyncio
    async def test_update_act_resolution_increments_count(self) -> None:
        """Should increment citation count on existing resolution."""
        mock_client = MagicMock()
        mock_table = MagicMock()

        # For RPC call (fails)
        mock_rpc = MagicMock()
        mock_client.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception("RPC not found")

        # For select (found existing)
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.execute.return_value = MagicMock(
            data=[
                {
                    "id": "res-1",
                    "matter_id": "matter-123",
                    "act_name_normalized": "negotiable_instruments_act_1881",
                    "citation_count": 5,
                }
            ]
        )

        # For update
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock(
            data=[
                {
                    "id": "res-1",
                    "matter_id": "matter-123",
                    "act_name_normalized": "negotiable_instruments_act_1881",
                    "act_name_display": "Negotiable Instruments Act, 1881",
                    "resolution_status": "missing",
                    "user_action": "pending",
                    "citation_count": 6,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ]
        )

        mock_client.table.return_value = mock_table

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            resolution = await service.create_or_update_act_resolution(
                matter_id="matter-123",
                act_name="NI Act",
            )

            assert resolution is not None
            assert resolution.citation_count == 6

    @pytest.mark.asyncio
    async def test_get_act_resolutions(self) -> None:
        """Should retrieve act resolutions for matter."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_order = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.execute.return_value = MagicMock(
            data=[
                {
                    "id": "res-1",
                    "matter_id": "matter-123",
                    "act_name_normalized": "ni_act",
                    "act_name_display": "NI Act",
                    "resolution_status": "missing",
                    "user_action": "pending",
                    "citation_count": 10,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ]
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            resolutions = await service.get_act_resolutions("matter-123")

            assert len(resolutions) == 1
            assert resolutions[0].citation_count == 10

    @pytest.mark.asyncio
    async def test_update_act_resolution_status(self) -> None:
        """Should update act resolution status."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(
            data=[
                {
                    "id": "res-1",
                    "matter_id": "matter-123",
                    "act_name_normalized": "ni_act",
                    "act_name_display": "NI Act",
                    "act_document_id": "act-doc-1",
                    "resolution_status": "available",
                    "user_action": "uploaded",
                    "citation_count": 5,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ]
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            resolution = await service.update_act_resolution(
                matter_id="matter-123",
                act_name_normalized="ni_act",
                act_document_id="act-doc-1",
                resolution_status=ActResolutionStatus.AVAILABLE,
                user_action=UserAction.UPLOADED,
            )

            assert resolution is not None
            assert resolution.resolution_status == ActResolutionStatus.AVAILABLE
            assert resolution.user_action == UserAction.UPLOADED


class TestCitationCounts:
    """Tests for citation count aggregation."""

    @pytest.mark.asyncio
    async def test_get_citation_counts_by_act(self) -> None:
        """Should aggregate citation counts by act."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(
            data=[
                {"act_name": "NI Act", "verification_status": "verified"},
                {"act_name": "NI Act", "verification_status": "pending"},
                {"act_name": "NI Act", "verification_status": "verified"},
                {"act_name": "IPC", "verification_status": "pending"},
                {"act_name": "IPC", "verification_status": "pending"},
            ]
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            counts = await service.get_citation_counts_by_act("matter-123")

            assert len(counts) == 2

            # Find NI Act counts
            ni_act = next(c for c in counts if c["act_name"] == "NI Act")
            assert ni_act["citation_count"] == 3
            assert ni_act["verified_count"] == 2
            assert ni_act["pending_count"] == 1

            # Find IPC counts
            ipc = next(c for c in counts if c["act_name"] == "IPC")
            assert ipc["citation_count"] == 2
            assert ipc["verified_count"] == 0
            assert ipc["pending_count"] == 2

    @pytest.mark.asyncio
    async def test_citation_counts_sorted_by_count(self) -> None:
        """Should return counts sorted by citation_count descending."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(
            data=[
                {"act_name": "Act A", "verification_status": "pending"},
                {"act_name": "Act B", "verification_status": "pending"},
                {"act_name": "Act B", "verification_status": "pending"},
                {"act_name": "Act B", "verification_status": "pending"},
                {"act_name": "Act C", "verification_status": "pending"},
                {"act_name": "Act C", "verification_status": "pending"},
            ]
        )

        with patch(
            "app.engines.citation.storage.get_service_client",
            return_value=mock_client,
        ):
            service = CitationStorageService()

            counts = await service.get_citation_counts_by_act("matter-123")

            # Should be sorted: Act B (3), Act C (2), Act A (1)
            assert counts[0]["act_name"] == "Act B"
            assert counts[0]["citation_count"] == 3
            assert counts[1]["act_name"] == "Act C"
            assert counts[1]["citation_count"] == 2
            assert counts[2]["act_name"] == "Act A"
            assert counts[2]["citation_count"] == 1


class TestRowConversion:
    """Tests for database row conversion."""

    def test_row_to_citation_converts_confidence(self) -> None:
        """Should convert confidence from 0-1 to 0-100."""
        service = CitationStorageService()

        row = {
            "id": "cit-1",
            "matter_id": "matter-123",
            "source_document_id": "doc-456",
            "act_name": "NI Act",
            "section": "138",
            "source_page": 1,
            "verification_status": "pending",
            "confidence": 0.85,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        citation = service._row_to_citation(row)

        assert citation.confidence == 85.0

    def test_row_to_act_resolution_uses_display_name(self) -> None:
        """Should use get_display_name when act_name_display is missing."""
        service = CitationStorageService()

        row = {
            "id": "res-1",
            "matter_id": "matter-123",
            "act_name_normalized": "negotiable_instruments_act_1881",
            "act_name_display": None,
            "resolution_status": "missing",
            "user_action": "pending",
            "citation_count": 5,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        resolution = service._row_to_act_resolution(row)

        # Should use get_display_name to generate display name
        assert "1881" in resolution.act_name_display


class TestBatchSize:
    """Tests for batch processing configuration."""

    def test_batch_size_defined(self) -> None:
        """BATCH_SIZE should be defined."""
        assert BATCH_SIZE > 0
        assert BATCH_SIZE == 50  # As defined in storage.py


class TestGetCitationStorageService:
    """Tests for factory function."""

    def test_returns_singleton(self) -> None:
        """Should return same instance on multiple calls."""
        get_citation_storage_service.cache_clear()

        service1 = get_citation_storage_service()
        service2 = get_citation_storage_service()

        assert service1 is service2

    def test_returns_service_instance(self) -> None:
        """Should return CitationStorageService instance."""
        get_citation_storage_service.cache_clear()

        service = get_citation_storage_service()

        assert isinstance(service, CitationStorageService)
