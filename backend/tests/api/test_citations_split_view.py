"""API integration tests for citation split-view endpoint.

Story 3-4: Split-View Citation Highlighting
Tests the split-view API endpoint for citation display.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.citation import (
    Citation,
    VerificationStatus,
)
from app.models.matter import MatterRole

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
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def create_mock_citation(
    citation_id: str = "citation-123",
    verification_status: VerificationStatus = VerificationStatus.VERIFIED,
) -> Citation:
    """Create a mock Citation for testing."""
    return Citation(
        id=citation_id,
        matter_id="matter-456",
        document_id="doc-789",
        document_name="Case File.pdf",
        act_name="Negotiable Instruments Act, 1881",
        section_number="138",
        subsection=None,
        clause=None,
        raw_citation_text="Section 138 of the NI Act",
        confidence=95.5,
        source_page=45,
        source_bbox_ids=["bbox-1", "bbox-2"],
        target_page=89,
        target_bbox_ids=["bbox-3", "bbox-4"],
        verification_status=verification_status,
        extraction_metadata={
            "verification_explanation": "Text matches exactly",
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_matter_service() -> MagicMock:
    """Create a mock MatterService."""
    return MagicMock()


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock CitationStorageService."""
    return AsyncMock()


@pytest.fixture
def mock_discovery_service() -> AsyncMock:
    """Create a mock ActDiscoveryService."""
    return AsyncMock()


@pytest_asyncio.fixture
async def test_client(
    mock_matter_service: MagicMock,
    mock_storage_service: AsyncMock,
    mock_discovery_service: AsyncMock,
):
    """Create an async test client with mocked dependencies."""
    from app.api.deps import get_matter_service
    from app.api.routes.citations import _get_discovery_service, _get_storage_service
    from app.core.config import get_settings

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
    app.dependency_overrides[_get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


class TestCitationSplitViewEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations/{citation_id}/split-view"""

    @pytest.mark.asyncio
    async def test_split_view_returns_source_and_target_data(
        self,
        test_client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: AsyncMock,
        mock_discovery_service: AsyncMock,
    ):
        """Test that split view returns both source and target document data."""
        citation = create_mock_citation()

        # Mock matter access (sync method)
        mock_matter_service.get_user_role = MagicMock(return_value=MatterRole.EDITOR)

        # Mock citation storage service
        mock_storage_service.get_citation.return_value = citation

        # Mock discovery service
        mock_discovery_service.get_act_resolution_by_name.return_value = MagicMock(
            act_document_id="act-doc-123"
        )

        # We need to also mock the inline imports in the endpoint
        from unittest.mock import patch

        with (
            patch(
                "app.api.routes.citations.get_storage_service"
            ) as mock_file_storage,
            patch(
                "app.api.routes.citations.get_bounding_box_service"
            ) as mock_bbox_service,
            patch(
                "app.api.routes.citations.get_service_client"
            ) as mock_client,
        ):
            # Mock file storage
            file_storage = MagicMock()
            file_storage.get_signed_url.return_value = "https://signed-url.example.com"
            mock_file_storage.return_value = file_storage

            # Mock bbox service
            bbox_service = MagicMock()
            bbox_service.get_bounding_boxes_by_ids.return_value = [
                {
                    "id": "bbox-1",
                    "x": 0.1,
                    "y": 0.2,
                    "width": 0.3,
                    "height": 0.05,
                    "text": "Section",
                },
            ]
            mock_bbox_service.return_value = bbox_service

            # Mock Supabase client
            supabase_client = MagicMock()
            table_mock = MagicMock()
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.single.return_value = table_mock
            table_mock.execute.return_value = MagicMock(
                data={
                    "storage_path": "matter-456/uploads/file.pdf",
                    "filename": "file.pdf",
                }
            )
            supabase_client.table.return_value = table_mock
            mock_client.return_value = supabase_client

            token = create_test_token()
            response = await test_client.get(
                "/api/matters/matter-456/citations/citation-123/split-view",
                headers={"Authorization": f"Bearer {token}"},
            )

            # Should return 200 with data
            assert response.status_code == 200
            data = response.json()

            assert "data" in data
            assert "citation" in data["data"]
            assert "sourceDocument" in data["data"]

    @pytest.mark.asyncio
    async def test_split_view_citation_not_found(
        self,
        test_client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: AsyncMock,
        mock_discovery_service: AsyncMock,
    ):
        """Test that 404 is returned when citation not found."""
        # Mock matter access (sync method)
        mock_matter_service.get_user_role = MagicMock(return_value=MatterRole.EDITOR)

        # Mock citation storage service - return None
        mock_storage_service.get_citation.return_value = None

        token = create_test_token()
        response = await test_client.get(
            "/api/matters/matter-456/citations/nonexistent-citation/split-view",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "CITATION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_split_view_returns_null_target_when_act_unavailable(
        self,
        test_client: AsyncClient,
        mock_matter_service: MagicMock,
        mock_storage_service: AsyncMock,
        mock_discovery_service: AsyncMock,
    ):
        """Test that targetDocument is null when Act is unavailable (AC: #4)."""
        citation = create_mock_citation(
            verification_status=VerificationStatus.ACT_UNAVAILABLE
        )
        citation.target_page = None
        citation.target_bbox_ids = None

        # Mock matter access (sync method)
        mock_matter_service.get_user_role = MagicMock(return_value=MatterRole.VIEWER)

        # Mock citation storage service
        mock_storage_service.get_citation.return_value = citation

        # We need to also mock the inline imports in the endpoint
        from unittest.mock import patch

        with (
            patch(
                "app.api.routes.citations.get_storage_service"
            ) as mock_file_storage,
            patch(
                "app.api.routes.citations.get_bounding_box_service"
            ) as mock_bbox_service,
            patch(
                "app.api.routes.citations.get_service_client"
            ) as mock_client,
        ):
            # Mock file storage
            file_storage = MagicMock()
            file_storage.get_signed_url.return_value = "https://signed-url.example.com"
            mock_file_storage.return_value = file_storage

            # Mock bbox service - no source bboxes for this test
            bbox_service = MagicMock()
            bbox_service.get_bounding_boxes_by_ids.return_value = []
            mock_bbox_service.return_value = bbox_service

            # Mock Supabase client
            supabase_client = MagicMock()
            table_mock = MagicMock()
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.single.return_value = table_mock
            table_mock.execute.return_value = MagicMock(
                data={
                    "storage_path": "matter-456/uploads/file.pdf",
                    "filename": "file.pdf",
                }
            )
            supabase_client.table.return_value = table_mock
            mock_client.return_value = supabase_client

            token = create_test_token()
            response = await test_client.get(
                "/api/matters/matter-456/citations/citation-123/split-view",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()

            # targetDocument should be null when act is unavailable
            assert data["data"]["targetDocument"] is None

    @pytest.mark.asyncio
    async def test_split_view_requires_authentication(self, test_client: AsyncClient):
        """Test that authentication is required."""
        response = await test_client.get(
            "/api/matters/matter-456/citations/citation-123/split-view",
        )

        assert response.status_code == 401
