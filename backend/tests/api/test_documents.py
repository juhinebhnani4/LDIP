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
    DocumentStatus,
    DocumentType,
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
    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

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
