"""Unit tests for StorageService.

Tests the Supabase Storage service operations including:
- File uploads
- File deletion
- Signed URL generation
- Filename uniqueness handling
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.storage_service import (
    StorageError,
    StorageService,
    VALID_SUBFOLDERS,
)


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Create a mock Supabase client."""
    mock = MagicMock()

    # Mock storage bucket operations
    mock_bucket = MagicMock()
    mock.storage.from_.return_value = mock_bucket

    # Default successful upload
    mock_bucket.upload.return_value = {"path": "test/path"}

    # Default successful signed URL
    mock_bucket.create_signed_url.return_value = {
        "signedURL": "https://example.com/signed-url"
    }

    # Default successful delete
    mock_bucket.remove.return_value = []

    return mock


@pytest.fixture
def storage_service(mock_supabase_client: MagicMock) -> StorageService:
    """Create a StorageService with mocked client."""
    service = StorageService(client=mock_supabase_client)
    return service


class TestStorageServiceInit:
    """Tests for StorageService initialization."""

    def test_init_with_provided_client(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Test initialization with provided client."""
        service = StorageService(client=mock_supabase_client)
        assert service.client == mock_supabase_client
        assert service.bucket == "documents"

    @patch("app.services.storage_service.get_service_client")
    def test_init_without_client_uses_default(
        self, mock_get_client: MagicMock
    ) -> None:
        """Test initialization without client uses service client."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        service = StorageService()
        assert service.client == mock_client


class TestUploadFile:
    """Tests for upload_file method."""

    def test_upload_file_success(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test successful file upload."""
        storage_path, signed_url = storage_service.upload_file(
            matter_id="matter-123",
            subfolder="uploads",
            file_content=b"PDF content",
            filename="document.pdf",
        )

        # Verify storage path format
        assert "matter-123/uploads/" in storage_path
        assert storage_path.endswith(".pdf")

        # Verify signed URL returned
        assert signed_url == "https://example.com/signed-url"

        # Verify upload was called
        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.upload.assert_called_once()

    def test_upload_file_generates_unique_filename(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that upload generates unique filename."""
        storage_path, _ = storage_service.upload_file(
            matter_id="matter-123",
            subfolder="uploads",
            file_content=b"PDF content",
            filename="document.pdf",
        )

        # Filename should have UUID suffix
        assert "document_" in storage_path
        assert storage_path.endswith(".pdf")
        # Should not be exactly the original filename
        assert storage_path != "matter-123/uploads/document.pdf"

    def test_upload_file_invalid_subfolder_raises_error(
        self,
        storage_service: StorageService,
    ) -> None:
        """Test that invalid subfolder raises StorageError."""
        with pytest.raises(StorageError) as exc_info:
            storage_service.upload_file(
                matter_id="matter-123",
                subfolder="invalid_folder",
                file_content=b"content",
                filename="file.pdf",
            )

        assert exc_info.value.code == "INVALID_SUBFOLDER"

    def test_upload_file_all_valid_subfolders(
        self,
        storage_service: StorageService,
    ) -> None:
        """Test that all valid subfolders are accepted."""
        for subfolder in VALID_SUBFOLDERS:
            storage_path, _ = storage_service.upload_file(
                matter_id="matter-123",
                subfolder=subfolder,
                file_content=b"content",
                filename="file.pdf",
            )
            assert f"/{subfolder}/" in storage_path

    def test_upload_file_handles_upload_error(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that upload errors are handled properly."""
        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.upload.side_effect = Exception("Network error")

        with pytest.raises(StorageError) as exc_info:
            storage_service.upload_file(
                matter_id="matter-123",
                subfolder="uploads",
                file_content=b"content",
                filename="file.pdf",
            )

        assert exc_info.value.code == "UPLOAD_FAILED"
        assert "Network error" in exc_info.value.message

    def test_upload_file_without_client_raises_error(self) -> None:
        """Test that upload without client raises error."""
        service = StorageService.__new__(StorageService)
        service.client = None
        service.bucket = "documents"

        with pytest.raises(StorageError) as exc_info:
            service.upload_file(
                matter_id="matter-123",
                subfolder="uploads",
                file_content=b"content",
                filename="file.pdf",
            )

        assert exc_info.value.code == "STORAGE_NOT_CONFIGURED"


class TestDeleteFile:
    """Tests for delete_file method."""

    def test_delete_file_success(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test successful file deletion."""
        result = storage_service.delete_file("matter-123/uploads/file.pdf")

        assert result is True

        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.remove.assert_called_once_with(["matter-123/uploads/file.pdf"])

    def test_delete_file_handles_error(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that deletion errors are handled properly."""
        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.remove.side_effect = Exception("Delete failed")

        with pytest.raises(StorageError) as exc_info:
            storage_service.delete_file("matter-123/uploads/file.pdf")

        assert exc_info.value.code == "DELETE_FAILED"


class TestGetSignedUrl:
    """Tests for get_signed_url method."""

    def test_get_signed_url_success(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test successful signed URL generation."""
        url = storage_service.get_signed_url("matter-123/uploads/file.pdf")

        assert url == "https://example.com/signed-url"

        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.create_signed_url.assert_called_once()

    def test_get_signed_url_custom_expiry(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test signed URL with custom expiry time."""
        storage_service.get_signed_url(
            "matter-123/uploads/file.pdf",
            expires_in=7200,
        )

        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.create_signed_url.assert_called_once_with(
            path="matter-123/uploads/file.pdf",
            expires_in=7200,
        )

    def test_get_signed_url_handles_error(
        self,
        storage_service: StorageService,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that URL generation errors are handled properly."""
        mock_bucket = mock_supabase_client.storage.from_.return_value
        mock_bucket.create_signed_url.side_effect = Exception("URL error")

        with pytest.raises(StorageError) as exc_info:
            storage_service.get_signed_url("matter-123/uploads/file.pdf")

        assert exc_info.value.code == "SIGNED_URL_FAILED"


class TestFilenameGeneration:
    """Tests for unique filename generation."""

    def test_generate_unique_filename_with_extension(
        self,
        storage_service: StorageService,
    ) -> None:
        """Test unique filename generation with extension."""
        filename = storage_service._generate_unique_filename("document.pdf")

        assert filename.startswith("document_")
        assert filename.endswith(".pdf")
        assert len(filename) > len("document.pdf")

    def test_generate_unique_filename_without_extension(
        self,
        storage_service: StorageService,
    ) -> None:
        """Test unique filename generation without extension."""
        filename = storage_service._generate_unique_filename("document")

        assert filename.startswith("document_")
        assert "." not in filename.split("_")[-1]

    def test_generate_unique_filename_multiple_dots(
        self,
        storage_service: StorageService,
    ) -> None:
        """Test unique filename with multiple dots in name."""
        filename = storage_service._generate_unique_filename("my.document.v2.pdf")

        assert filename.endswith(".pdf")
        assert "my.document.v2_" in filename
