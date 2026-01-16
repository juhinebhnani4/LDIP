"""Tests for bounding box API routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.matter import MatterRole
from app.services.bounding_box_service import BoundingBoxService
from app.services.document_service import DocumentService
from app.services.matter_service import MatterService

# Test JWT secret
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


@pytest.fixture
def mock_document() -> MagicMock:
    """Create mock document."""
    doc = MagicMock()
    doc.matter_id = "matter-456"
    doc.id = "doc-789"
    return doc


@pytest.fixture
def sample_bbox_data() -> list[dict]:
    """Sample bounding box data."""
    return [
        {
            "id": "bbox-1",
            "document_id": "doc-789",
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
            "document_id": "doc-789",
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


@pytest_asyncio.fixture
async def authorized_client(
    mock_document: MagicMock,
    sample_bbox_data: list[dict],
) -> AsyncClient:
    """Create an authorized async test client with all mocks configured."""
    from app.api.deps import get_matter_service
    from app.core.config import get_settings
    from app.services.bounding_box_service import get_bounding_box_service
    from app.services.document_service import get_document_service

    mock_matter_service = MagicMock(spec=MatterService)
    mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

    mock_doc_service = MagicMock(spec=DocumentService)
    mock_doc_service.get_document.return_value = mock_document

    mock_bbox_service = MagicMock(spec=BoundingBoxService)
    mock_bbox_service.get_bounding_boxes_for_document.return_value = (
        sample_bbox_data,
        100,
    )
    mock_bbox_service.get_bounding_boxes_for_page.return_value = sample_bbox_data
    mock_bbox_service.get_bounding_boxes_by_ids.return_value = sample_bbox_data

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
    app.dependency_overrides[get_document_service] = lambda: mock_doc_service
    app.dependency_overrides[get_bounding_box_service] = lambda: mock_bbox_service

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


class TestGetDocumentBoundingBoxes:
    """Tests for GET /api/documents/{document_id}/bounding-boxes."""

    @pytest.mark.anyio
    async def test_returns_bounding_boxes(
        self,
        authorized_client: AsyncClient,
    ) -> None:
        """Should return bounding boxes for a document."""
        token = create_test_token()
        response = await authorized_client.get(
            "/api/documents/doc-789/bounding-boxes",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "bbox-1"
        assert data["meta"]["total"] == 100

    @pytest.mark.anyio
    async def test_returns_401_without_token(
        self,
        authorized_client: AsyncClient,
    ) -> None:
        """Should return 401 without auth token."""
        response = await authorized_client.get(
            "/api/documents/doc-789/bounding-boxes",
        )

        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_returns_404_for_unauthorized_matter(
        self,
        mock_document: MagicMock,
        sample_bbox_data: list[dict],
    ) -> None:
        """Should return 404 when user doesn't have access to document's matter."""
        from app.api.deps import get_matter_service
        from app.core.config import get_settings
        from app.services.bounding_box_service import get_bounding_box_service
        from app.services.document_service import get_document_service

        mock_matter_service = MagicMock(spec=MatterService)
        mock_matter_service.get_user_role.return_value = None  # No access

        mock_doc_service = MagicMock(spec=DocumentService)
        mock_doc_service.get_document.return_value = mock_document

        mock_bbox_service = MagicMock(spec=BoundingBoxService)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_document_service] = lambda: mock_doc_service
        app.dependency_overrides[get_bounding_box_service] = lambda: mock_bbox_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/documents/doc-789/bounding-boxes",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"


class TestGetPageBoundingBoxes:
    """Tests for GET /api/documents/{document_id}/pages/{page_number}/bounding-boxes."""

    @pytest.mark.anyio
    async def test_returns_page_bounding_boxes(
        self,
        authorized_client: AsyncClient,
    ) -> None:
        """Should return bounding boxes for a specific page."""
        token = create_test_token()
        response = await authorized_client.get(
            "/api/documents/doc-789/pages/1/bounding-boxes",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    @pytest.mark.anyio
    async def test_validates_page_number(
        self,
        authorized_client: AsyncClient,
    ) -> None:
        """Should validate page number is positive."""
        token = create_test_token()
        response = await authorized_client.get(
            "/api/documents/doc-789/pages/0/bounding-boxes",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422  # Validation error


class TestGetChunkBoundingBoxes:
    """Tests for GET /api/chunks/{chunk_id}/bounding-boxes."""

    @pytest.mark.anyio
    async def test_returns_chunk_bounding_boxes(
        self,
        sample_bbox_data: list[dict],
    ) -> None:
        """Should return bounding boxes for a chunk."""
        from app.api.deps import get_matter_service
        from app.api.routes.bounding_boxes import get_supabase_client
        from app.core.config import get_settings
        from app.services.bounding_box_service import get_bounding_box_service

        mock_chunk_data = {
            "matter_id": "matter-456",
            "bbox_ids": ["bbox-1", "bbox-2"],
        }

        mock_matter_service = MagicMock(spec=MatterService)
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        mock_bbox_service = MagicMock(spec=BoundingBoxService)
        mock_bbox_service.get_bounding_boxes_by_ids.return_value = sample_bbox_data

        # Mock Supabase client via DI
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[mock_chunk_data]
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_bounding_box_service] = lambda: mock_bbox_service
        app.dependency_overrides[get_supabase_client] = lambda: mock_client

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/chunks/chunk-123/bounding-boxes",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    @pytest.mark.anyio
    async def test_returns_404_for_nonexistent_chunk(self) -> None:
        """Should return 404 for nonexistent chunk."""
        from app.api.deps import get_matter_service
        from app.api.routes.bounding_boxes import get_supabase_client
        from app.core.config import get_settings
        from app.services.bounding_box_service import get_bounding_box_service

        mock_matter_service = MagicMock(spec=MatterService)
        mock_bbox_service = MagicMock(spec=BoundingBoxService)

        # Mock Supabase client returning no data via DI
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_bounding_box_service] = lambda: mock_bbox_service
        app.dependency_overrides[get_supabase_client] = lambda: mock_client

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/chunks/nonexistent/bounding-boxes",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_returns_404_for_unauthorized_matter(
        self,
        sample_bbox_data: list[dict],
    ) -> None:
        """Should return 404 when user doesn't have access to chunk's matter."""
        from app.api.deps import get_matter_service
        from app.api.routes.bounding_boxes import get_supabase_client
        from app.core.config import get_settings
        from app.services.bounding_box_service import get_bounding_box_service

        mock_chunk_data = {
            "matter_id": "matter-456",
            "bbox_ids": ["bbox-1", "bbox-2"],
        }

        mock_matter_service = MagicMock(spec=MatterService)
        mock_matter_service.get_user_role.return_value = None  # No access

        mock_bbox_service = MagicMock(spec=BoundingBoxService)

        # Mock Supabase client returning chunk data via DI
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[mock_chunk_data]
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_bounding_box_service] = lambda: mock_bbox_service
        app.dependency_overrides[get_supabase_client] = lambda: mock_client

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/chunks/chunk-123/bounding-boxes",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "CHUNK_NOT_FOUND"
