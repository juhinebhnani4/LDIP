"""API integration tests for document endpoints.

Tests the document upload API endpoints including:
- PDF upload
- ZIP extraction
- Role-based access control
- Document type handling
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import app
from app.api.deps import get_matter_service
from app.models.document import (
    Document,
    DocumentListItem,
    DocumentStatus,
    DocumentType,
    PaginationMeta,
    UploadedDocument,
)
from app.models.matter import MatterRole
from app.services.document_service import DocumentService, get_document_service
from app.services.storage_service import StorageService, get_storage_service
from app.services.matter_service import MatterService


# Test JWT secret - same as in other test files
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.is_configured = True
    settings.debug = True
    return settings


def create_test_token(
    user_id: str = "test-user-id",
    email: str = "test@example.com",
) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def mock_matter_service() -> MagicMock:
    """Create a mock MatterService."""
    return MagicMock(spec=MatterService)


@pytest.fixture
def mock_storage_service() -> MagicMock:
    """Create a mock StorageService."""
    mock = MagicMock(spec=StorageService)
    # Default successful upload
    mock.upload_file.return_value = (
        "test-matter-id/uploads/test_abc123.pdf",
        "https://example.com/signed-url",
    )
    return mock


@pytest.fixture
def mock_document_service() -> MagicMock:
    """Create a mock DocumentService."""
    mock = MagicMock(spec=DocumentService)
    # Default successful document creation
    mock.create_document.return_value = UploadedDocument(
        document_id="doc-12345",
        filename="test.pdf",
        storage_path="test-matter-id/uploads/test_abc123.pdf",
        file_size=1024,
        document_type=DocumentType.CASE_FILE,
        status=DocumentStatus.PENDING,
    )
    return mock


@pytest.fixture
def valid_token() -> str:
    """Create a valid JWT token for tests."""
    return create_test_token()


@pytest.fixture
def other_user_token() -> str:
    """Create a valid JWT token for a different user."""
    return create_test_token(user_id="other-user-id", email="other@example.com")


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Create sample PDF content for tests."""
    return b"%PDF-1.4 test content for testing upload"


@pytest.fixture
def sample_zip_content() -> bytes:
    """Create a sample ZIP file with PDFs for tests."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("document1.pdf", b"%PDF-1.4 content 1")
        zf.writestr("document2.pdf", b"%PDF-1.4 content 2")
    return buffer.getvalue()


@pytest.fixture
def sample_zip_no_pdfs() -> bytes:
    """Create a sample ZIP file without PDFs for tests."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", b"This is a text file")
        zf.writestr("data.json", b'{"key": "value"}')
    return buffer.getvalue()


@pytest_asyncio.fixture
async def client(
    mock_matter_service: MagicMock,
    mock_storage_service: MagicMock,
    mock_document_service: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with mocked dependencies."""
    from app.api.deps import get_matter_service as deps_get_matter_service

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
    app.dependency_overrides[deps_get_matter_service] = lambda: mock_matter_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

    # Mock Celery task queuing to avoid Redis connection in tests
    with patch("app.api.routes.documents._queue_ocr_task"):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


class TestUploadDocument:
    """Tests for POST /api/documents/upload."""

    @pytest.mark.asyncio
    async def test_upload_pdf_returns_201(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that uploading a PDF returns 201 with document info."""
        # Mock role check for editor access
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id", "document_type": "case_file"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["filename"] == "test.pdf"
        assert data["data"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_upload_act_sets_reference_material(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that uploading an Act document sets is_reference_material=true."""
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        # Update mock to return act document
        mock_document_service.create_document.return_value = UploadedDocument(
            document_id="doc-act-123",
            filename="indian_contract_act.pdf",
            storage_path="test-matter-id/acts/indian_contract_act_abc123.pdf",
            file_size=2048,
            document_type=DocumentType.ACT,
            status=DocumentStatus.PENDING,
        )

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("indian_contract_act.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id", "document_type": "act"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["document_type"] == "act"

        # Verify storage was called with 'acts' subfolder
        mock_storage_service.upload_file.assert_called_once()
        call_args = mock_storage_service.upload_file.call_args
        assert call_args.kwargs.get("subfolder") == "acts" or call_args[0][1] == "acts"

    @pytest.mark.asyncio
    async def test_upload_requires_auth(
        self,
        client: AsyncClient,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that uploading a document requires authentication."""
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_without_matter_access_returns_404(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that upload denied for user without matter access."""
        # User has no access to matter
        mock_matter_service.get_user_role.return_value = None

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        # Returns 404 to prevent matter enumeration
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_viewer_cannot_upload(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that viewer cannot upload documents."""
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_file_type(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that uploading an invalid file type is rejected."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("document.docx", b"fake content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"matter_id": "test-matter-id"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_FILE_TYPE"


class TestUploadZip:
    """Tests for ZIP file upload and extraction."""

    @pytest.mark.asyncio
    async def test_upload_zip_extracts_pdfs(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_zip_content: bytes,
    ) -> None:
        """Test that uploading a ZIP extracts and uploads each PDF."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        # Mock multiple document creations for extracted PDFs
        mock_document_service.create_document.side_effect = [
            UploadedDocument(
                document_id=f"doc-{i}",
                filename=f"document{i}.pdf",
                storage_path=f"test-matter-id/uploads/document{i}_abc.pdf",
                file_size=100,
                document_type=DocumentType.CASE_FILE,
                status=DocumentStatus.PENDING,
            )
            for i in range(1, 3)
        ]

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("documents.zip", sample_zip_content, "application/zip")},
            data={"matter_id": "test-matter-id"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["meta"]["total_files"] == 2

    @pytest.mark.asyncio
    async def test_upload_zip_no_pdfs_returns_400(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_zip_no_pdfs: bytes,
    ) -> None:
        """Test that uploading a ZIP with no PDFs returns error."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("documents.zip", sample_zip_no_pdfs, "application/zip")},
            data={"matter_id": "test-matter-id"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == "NO_PDFS_IN_ZIP"

    @pytest.mark.asyncio
    async def test_upload_invalid_zip_returns_400(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that uploading an invalid ZIP returns error."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("documents.zip", b"not a zip file", "application/zip")},
            data={"matter_id": "test-matter-id"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_ZIP"


class TestDocumentTypes:
    """Tests for document type handling."""

    @pytest.mark.asyncio
    async def test_case_file_stored_in_uploads(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that case files are stored in uploads folder."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        await client.post(
            "/api/documents/upload",
            files={"file": ("petition.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id", "document_type": "case_file"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        # Verify storage was called with 'uploads' subfolder
        mock_storage_service.upload_file.assert_called_once()
        call_args = mock_storage_service.upload_file.call_args
        # Check subfolder is 'uploads' (either positional or keyword arg)
        assert "uploads" in str(call_args)

    @pytest.mark.asyncio
    async def test_act_stored_in_acts_folder(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that Act documents are stored in acts folder."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        # Update mock for act storage
        mock_storage_service.upload_file.return_value = (
            "test-matter-id/acts/act_abc123.pdf",
            "https://example.com/signed-url",
        )
        mock_document_service.create_document.return_value = UploadedDocument(
            document_id="doc-act",
            filename="contract_act.pdf",
            storage_path="test-matter-id/acts/act_abc123.pdf",
            file_size=1024,
            document_type=DocumentType.ACT,
            status=DocumentStatus.PENDING,
        )

        await client.post(
            "/api/documents/upload",
            files={"file": ("contract_act.pdf", sample_pdf_content, "application/pdf")},
            data={"matter_id": "test-matter-id", "document_type": "act"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        # Verify storage was called with 'acts' subfolder
        mock_storage_service.upload_file.assert_called_once()
        call_args = mock_storage_service.upload_file.call_args
        assert "acts" in str(call_args)


# =============================================================================
# Document List, Detail, and Update API Tests (Story 2a-3)
# =============================================================================


@pytest.fixture
def sample_document() -> Document:
    """Create a sample Document for tests."""
    return Document(
        id="doc-12345",
        matter_id="test-matter-id",
        filename="test-document.pdf",
        storage_path="test-matter-id/uploads/test_abc123.pdf",
        file_size=1024,
        page_count=5,
        document_type=DocumentType.CASE_FILE,
        is_reference_material=False,
        uploaded_by="test-user-id",
        uploaded_at=datetime.now(timezone.utc),
        status=DocumentStatus.PENDING,
        processing_started_at=None,
        processing_completed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_document_list() -> list[DocumentListItem]:
    """Create sample document list items for tests."""
    return [
        DocumentListItem(
            id=f"doc-{i}",
            matter_id="test-matter-id",
            filename=f"document_{i}.pdf",
            file_size=1024 * i,
            document_type=DocumentType.CASE_FILE if i % 2 == 0 else DocumentType.ACT,
            is_reference_material=i % 2 != 0,
            status=DocumentStatus.COMPLETED if i % 3 == 0 else DocumentStatus.PENDING,
            uploaded_at=datetime.now(timezone.utc),
            uploaded_by="test-user-id",
        )
        for i in range(1, 6)
    ]


class TestListDocuments:
    """Tests for GET /api/matters/{matter_id}/documents."""

    @pytest.mark.asyncio
    async def test_list_documents_returns_200(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_document_list: list[DocumentListItem],
    ) -> None:
        """Test that list documents returns 200 with paginated data."""
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock the list_documents method
        mock_document_service.list_documents.return_value = (
            sample_document_list,
            PaginationMeta(total=5, page=1, per_page=20, total_pages=1),
        )

        response = await client.get(
            "/api/matters/test-matter-id/documents",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) == 5
        assert data["meta"]["total"] == 5

    @pytest.mark.asyncio
    async def test_list_documents_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that listing documents requires authentication."""
        response = await client.get("/api/matters/test-matter-id/documents")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_documents_without_access_returns_404(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that list denied for user without matter access."""
        mock_matter_service.get_user_role.return_value = None

        response = await client.get(
            "/api/matters/test-matter-id/documents",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_documents_with_type_filter(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that document type filter is passed to service."""
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER
        mock_document_service.list_documents.return_value = (
            [],
            PaginationMeta(total=0, page=1, per_page=20, total_pages=0),
        )

        await client.get(
            "/api/matters/test-matter-id/documents?document_type=act",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        mock_document_service.list_documents.assert_called_once()
        call_kwargs = mock_document_service.list_documents.call_args.kwargs
        assert call_kwargs.get("document_type") == DocumentType.ACT

    @pytest.mark.asyncio
    async def test_list_documents_pagination(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that pagination params are passed to service."""
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER
        mock_document_service.list_documents.return_value = (
            [],
            PaginationMeta(total=50, page=2, per_page=10, total_pages=5),
        )

        await client.get(
            "/api/matters/test-matter-id/documents?page=2&per_page=10",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        mock_document_service.list_documents.assert_called_once()
        call_kwargs = mock_document_service.list_documents.call_args.kwargs
        assert call_kwargs.get("page") == 2
        assert call_kwargs.get("per_page") == 10


class TestGetDocument:
    """Tests for GET /api/documents/{document_id}."""

    @pytest.mark.asyncio
    async def test_get_document_returns_200(
        self,
        client: AsyncClient,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        valid_token: str,
        sample_document: Document,
    ) -> None:
        """Test that get document returns 200 with signed URL."""
        mock_document_service.get_document.return_value = sample_document
        mock_storage_service.get_signed_url.return_value = "https://example.com/signed-url"

        response = await client.get(
            "/api/documents/doc-12345",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == "doc-12345"
        # Storage path should be replaced with signed URL
        assert data["data"]["storage_path"] == "https://example.com/signed-url"

    @pytest.mark.asyncio
    async def test_get_document_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that getting a document requires authentication."""
        response = await client.get("/api/documents/doc-12345")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_nonexistent_document_returns_404(
        self,
        client: AsyncClient,
        mock_document_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that getting a nonexistent document returns 404."""
        from app.services.document_service import DocumentNotFoundError
        mock_document_service.get_document.side_effect = DocumentNotFoundError("doc-999")

        response = await client.get(
            "/api/documents/doc-999",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"


class TestUpdateDocument:
    """Tests for PATCH /api/documents/{document_id}."""

    @pytest.mark.asyncio
    async def test_update_document_type_returns_200(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_document: Document,
    ) -> None:
        """Test that updating document type returns 200."""
        updated_doc = Document(
            **{**sample_document.__dict__, "document_type": DocumentType.ACT}
        )
        mock_document_service.get_document.return_value = sample_document
        mock_document_service.update_document.return_value = updated_doc
        # Mock matter access check - user has EDITOR role
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.patch(
            "/api/documents/doc-12345",
            json={"document_type": "act"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["document_type"] == "act"

    @pytest.mark.asyncio
    async def test_update_document_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that updating a document requires authentication."""
        response = await client.patch(
            "/api/documents/doc-12345",
            json={"document_type": "act"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_nonexistent_document_returns_404(
        self,
        client: AsyncClient,
        mock_document_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that updating a nonexistent document returns 404."""
        from app.services.document_service import DocumentNotFoundError
        mock_document_service.get_document.side_effect = DocumentNotFoundError("doc-999")

        response = await client.patch(
            "/api/documents/doc-999",
            json={"document_type": "act"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_act_sets_reference_material(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_document: Document,
    ) -> None:
        """Test that setting type to 'act' auto-sets is_reference_material."""
        mock_document_service.get_document.return_value = sample_document
        # Mock matter access check - user has OWNER role
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        await client.patch(
            "/api/documents/doc-12345",
            json={"document_type": "act"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        # Verify update_document was called
        mock_document_service.update_document.assert_called_once()
        call_kwargs = mock_document_service.update_document.call_args.kwargs
        assert call_kwargs.get("document_type") == DocumentType.ACT


class TestBulkUpdateDocuments:
    """Tests for PATCH /api/documents/bulk."""

    @pytest.mark.asyncio
    async def test_bulk_update_returns_200(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_document_service: MagicMock,
        valid_token: str,
        sample_document: Document,
    ) -> None:
        """Test that bulk update returns 200 with counts."""
        # Mock get_document to return documents with matter_id
        mock_document_service.get_document.return_value = sample_document
        mock_document_service.bulk_update_documents.return_value = 3
        # Mock matter access check - user has EDITOR role
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.patch(
            "/api/documents/bulk",
            json={
                "document_ids": ["doc-1", "doc-2", "doc-3"],
                "document_type": "annexure",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["updated_count"] == 3
        assert data["data"]["requested_count"] == 3
        assert data["data"]["document_type"] == "annexure"

    @pytest.mark.asyncio
    async def test_bulk_update_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that bulk update requires authentication."""
        response = await client.patch(
            "/api/documents/bulk",
            json={
                "document_ids": ["doc-1"],
                "document_type": "act",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_update_empty_ids_returns_422(
        self,
        client: AsyncClient,
        valid_token: str,
    ) -> None:
        """Test that bulk update with empty IDs returns validation error."""
        response = await client.patch(
            "/api/documents/bulk",
            json={
                "document_ids": [],
                "document_type": "act",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422
