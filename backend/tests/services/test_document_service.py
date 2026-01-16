"""Unit tests for DocumentService.

Tests the document database operations including:
- Document creation
- Document retrieval by ID
- Document listing by matter
- Document deletion
- Error handling
"""

from unittest.mock import MagicMock

import pytest

from app.models.document import (
    DocumentStatus,
    DocumentType,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    DocumentServiceError,
)


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Create a mock Supabase client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def document_service(mock_supabase_client: MagicMock) -> DocumentService:
    """Create a DocumentService with mocked client."""
    return DocumentService(client=mock_supabase_client)


@pytest.fixture
def sample_document_data() -> dict:
    """Sample document data as returned from database."""
    return {
        "id": "doc-12345",
        "matter_id": "matter-123",
        "filename": "test.pdf",
        "storage_path": "matter-123/uploads/test_abc123.pdf",
        "file_size": 1024,
        "page_count": None,
        "document_type": "case_file",
        "is_reference_material": False,
        "uploaded_by": "user-123",
        "uploaded_at": "2026-01-07T10:00:00Z",
        "status": "pending",
        "processing_started_at": None,
        "processing_completed_at": None,
        "created_at": "2026-01-07T10:00:00Z",
        "updated_at": "2026-01-07T10:00:00Z",
    }


class TestDocumentServiceInit:
    """Tests for DocumentService initialization."""

    def test_init_with_provided_client(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Test initialization with provided client."""
        service = DocumentService(client=mock_supabase_client)
        assert service.client == mock_supabase_client


class TestCreateDocument:
    """Tests for create_document method."""

    def test_create_document_success(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
        sample_document_data: dict,
    ) -> None:
        """Test successful document creation."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[sample_document_data])

        # Execute
        result = document_service.create_document(
            matter_id="matter-123",
            filename="test.pdf",
            storage_path="matter-123/uploads/test_abc123.pdf",
            file_size=1024,
            document_type=DocumentType.CASE_FILE,
            uploaded_by="user-123",
        )

        # Verify
        assert result.document_id == "doc-12345"
        assert result.filename == "test.pdf"
        assert result.status == DocumentStatus.PENDING

    def test_create_document_act_sets_reference_material(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that creating an Act document sets is_reference_material=True."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{
            "id": "doc-act",
            "matter_id": "matter-123",
            "filename": "contract_act.pdf",
            "storage_path": "matter-123/acts/contract_act_abc.pdf",
            "file_size": 2048,
            "document_type": "act",
            "is_reference_material": True,
            "uploaded_by": "user-123",
            "status": "pending",
        }])

        # Execute
        document_service.create_document(
            matter_id="matter-123",
            filename="contract_act.pdf",
            storage_path="matter-123/acts/contract_act_abc.pdf",
            file_size=2048,
            document_type=DocumentType.ACT,
            uploaded_by="user-123",
        )

        # Verify insert was called with is_reference_material=True
        insert_call = mock_table.insert.call_args
        assert insert_call[0][0]["is_reference_material"] is True

    def test_create_document_case_file_not_reference_material(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
        sample_document_data: dict,
    ) -> None:
        """Test that case files have is_reference_material=False by default."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[sample_document_data])

        # Execute
        document_service.create_document(
            matter_id="matter-123",
            filename="petition.pdf",
            storage_path="matter-123/uploads/petition_abc.pdf",
            file_size=1024,
            document_type=DocumentType.CASE_FILE,
            uploaded_by="user-123",
        )

        # Verify insert was called with is_reference_material=False
        insert_call = mock_table.insert.call_args
        assert insert_call[0][0]["is_reference_material"] is False

    def test_create_document_handles_error(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that database errors are handled properly."""
        # Setup mock to raise error
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.side_effect = Exception("Database error")

        # Execute and verify
        with pytest.raises(DocumentServiceError) as exc_info:
            document_service.create_document(
                matter_id="matter-123",
                filename="test.pdf",
                storage_path="path",
                file_size=1024,
                document_type=DocumentType.CASE_FILE,
                uploaded_by="user-123",
            )

        assert exc_info.value.code == "CREATE_FAILED"

    def test_create_document_without_client_raises_error(self) -> None:
        """Test that creating document without client raises error."""
        service = DocumentService.__new__(DocumentService)
        service.client = None

        with pytest.raises(DocumentServiceError) as exc_info:
            service.create_document(
                matter_id="matter-123",
                filename="test.pdf",
                storage_path="path",
                file_size=1024,
                document_type=DocumentType.CASE_FILE,
                uploaded_by="user-123",
            )

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"


class TestGetDocument:
    """Tests for get_document method."""

    def test_get_document_success(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
        sample_document_data: dict,
    ) -> None:
        """Test successful document retrieval."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[sample_document_data])

        # Execute
        result = document_service.get_document("doc-12345")

        # Verify
        assert result.id == "doc-12345"
        assert result.filename == "test.pdf"
        assert result.matter_id == "matter-123"

    def test_get_document_not_found(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that non-existent document raises DocumentNotFoundError."""
        # Setup mock to return empty
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        # Execute and verify
        with pytest.raises(DocumentNotFoundError):
            document_service.get_document("non-existent-id")

    def test_get_document_handles_error(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that query errors are handled properly."""
        # Setup mock to raise error
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.side_effect = Exception("Query error")

        # Execute and verify
        with pytest.raises(DocumentServiceError) as exc_info:
            document_service.get_document("doc-123")

        assert exc_info.value.code == "GET_FAILED"


class TestGetDocumentsByMatter:
    """Tests for get_documents_by_matter method."""

    def test_get_documents_by_matter_success(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
        sample_document_data: dict,
    ) -> None:
        """Test successful document listing by matter."""
        # Setup mock with multiple documents
        doc2 = sample_document_data.copy()
        doc2["id"] = "doc-67890"
        doc2["filename"] = "test2.pdf"

        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.execute.return_value = MagicMock(
            data=[sample_document_data, doc2]
        )

        # Execute
        results = document_service.get_documents_by_matter("matter-123")

        # Verify
        assert len(results) == 2
        assert results[0].id == "doc-12345"
        assert results[1].id == "doc-67890"

    def test_get_documents_by_matter_empty(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test listing documents for matter with no documents."""
        # Setup mock to return empty
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        # Execute
        results = document_service.get_documents_by_matter("matter-123")

        # Verify
        assert results == []


class TestDeleteDocument:
    """Tests for delete_document method."""

    def test_delete_document_success(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test successful document deletion."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.delete.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"id": "doc-123"}])

        # Execute
        result = document_service.delete_document("doc-123")

        # Verify
        assert result is True

    def test_delete_document_not_found(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test deleting non-existent document raises error."""
        # Setup mock to return empty on existence check
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        # Execute and verify
        with pytest.raises(DocumentNotFoundError):
            document_service.delete_document("non-existent-id")


class TestSoftDeleteDocument:
    """Tests for soft_delete_document method."""

    def test_soft_delete_document_success(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test successful soft deletion."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"id": "doc-123"}])
        mock_table.update.return_value = mock_table
        mock_table.update.return_value.eq.return_value = mock_table
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "doc-123", "deleted_at": "2026-01-15T10:00:00+00:00"}]
        )

        # Execute
        result = document_service.soft_delete_document("doc-123")

        # Verify
        assert result["document_id"] == "doc-123"
        assert "deleted_at" in result

    def test_soft_delete_document_not_found(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test soft deleting non-existent document raises error."""
        # Setup mock to return empty on existence check
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        # Execute and verify
        with pytest.raises(DocumentNotFoundError):
            document_service.soft_delete_document("non-existent-id")

    def test_soft_delete_document_update_fails(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test soft delete update failure raises error."""
        # Setup mock with separate select and update chains
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table

        # Mock for select chain (existence check)
        mock_select_chain = MagicMock()
        mock_table.select.return_value = mock_select_chain
        mock_select_chain.eq.return_value = mock_select_chain
        mock_select_chain.execute.return_value = MagicMock(data=[{"id": "doc-123"}])

        # Mock for update chain (update fails)
        mock_update_chain = MagicMock()
        mock_table.update.return_value = mock_update_chain
        mock_update_chain.eq.return_value = mock_update_chain
        mock_update_chain.execute.return_value = MagicMock(data=[])  # Empty = failure

        # Execute and verify
        with pytest.raises(DocumentServiceError) as exc_info:
            document_service.soft_delete_document("doc-123")

        assert exc_info.value.code == "SOFT_DELETE_FAILED"


class TestUpdateDocumentFilename:
    """Tests for update_document with filename field."""

    def test_update_document_filename_success(
        self,
        document_service: DocumentService,
        mock_supabase_client: MagicMock,
        sample_document_data: dict,
    ) -> None:
        """Test successful filename update."""
        # Setup mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[sample_document_data])

        # Update returns new filename
        updated_data = sample_document_data.copy()
        updated_data["filename"] = "new-name.pdf"
        mock_table.update.return_value = mock_table
        mock_table.update.return_value.eq.return_value = mock_table
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        # Execute
        result = document_service.update_document("doc-12345", filename="new-name.pdf")

        # Verify
        assert result.filename == "new-name.pdf"


class TestDatetimeParsing:
    """Tests for datetime parsing helper."""

    def test_parse_datetime_with_value(
        self,
        document_service: DocumentService,
    ) -> None:
        """Test parsing valid datetime string."""
        result = document_service._parse_datetime("2026-01-07T10:00:00Z")

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 7

    def test_parse_datetime_with_none(
        self,
        document_service: DocumentService,
    ) -> None:
        """Test parsing None returns None."""
        result = document_service._parse_datetime(None)

        assert result is None
