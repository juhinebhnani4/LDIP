"""Integration tests for Citation API routes.

Story 3-1: Act Citation Extraction (AC: #4)
Story 3-3: Citation Verification
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.citation import (
    ActDiscoverySummary,
    ActResolutionStatus,
    Citation,
    UserAction,
    VerificationStatus,
)
from app.models.matter import MatterRole

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


def create_mock_citation(
    matter_id: str,
    citation_id: str | None = None,
    act_name: str = "Negotiable Instruments Act, 1881",
    section: str = "138",
) -> Citation:
    """Create a mock citation for testing."""
    return Citation(
        id=citation_id or str(uuid4()),
        matter_id=matter_id,
        document_id=str(uuid4()),
        act_name=act_name,
        section_number=section,
        subsection="(1)",
        source_page=5,
        source_bbox_ids=[str(uuid4())],
        verification_status=VerificationStatus.PENDING,
        confidence=85.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def create_mock_act_discovery_summary(
    act_name: str,
    citation_count: int = 5,
    status: ActResolutionStatus = ActResolutionStatus.MISSING,
) -> ActDiscoverySummary:
    """Create a mock act discovery summary for testing."""
    return ActDiscoverySummary(
        act_name=act_name,
        act_name_normalized=act_name.lower().replace(" ", "_").replace(",", ""),
        citation_count=citation_count,
        resolution_status=status,
        user_action=UserAction.PENDING,
    )


class TestListCitationsEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations endpoint."""

    @pytest.mark.anyio
    async def test_list_citations_success(self) -> None:
        """Should list citations for authorized user."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_citations = [
            create_mock_citation(matter_id, section="138"),
            create_mock_citation(matter_id, section="139"),
        ]

        # Mock matter service
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        # Mock storage service
        mock_storage = MagicMock()
        mock_storage.get_citations_by_matter = AsyncMock(
            return_value=(mock_citations, 2)
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "meta" in data
            assert len(data["data"]) == 2
            assert data["meta"]["total"] == 2
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_list_citations_with_filters(self) -> None:
        """Should filter citations by act name and status."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_citations = [
            create_mock_citation(matter_id, act_name="NI Act", section="138")
        ]

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citations_by_matter = AsyncMock(
            return_value=(mock_citations, 1)
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations",
                    params={
                        "act_name": "NI Act",
                        "verification_status": "pending",
                    },
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 1
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_list_citations_unauthorized(self) -> None:
        """Should return 401 for missing auth token."""
        matter_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/matters/{matter_id}/citations")

        assert response.status_code == 401


class TestGetCitationEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations/{citation_id} endpoint."""

    @pytest.mark.anyio
    async def test_get_citation_success(self) -> None:
        """Should get a single citation by ID."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        citation_id = str(uuid4())
        user_id = "test-user-id"

        mock_citation = create_mock_citation(matter_id, citation_id)

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citation = AsyncMock(return_value=mock_citation)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/{citation_id}",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["data"]["id"] == citation_id
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_citation_not_found(self) -> None:
        """Should return 404 for non-existent citation."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        citation_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citation = AsyncMock(return_value=None)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/{citation_id}",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "CITATION_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


class TestCitationSummaryEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations/summary/by-act endpoint."""

    @pytest.mark.anyio
    async def test_get_citation_summary_success(self) -> None:
        """Should get citation summary grouped by act."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_counts = [
            {
                "act_name": "NI Act",
                "citation_count": 10,
                "verified_count": 5,
                "pending_count": 5,
            },
            {
                "act_name": "IPC",
                "citation_count": 3,
                "verified_count": 0,
                "pending_count": 3,
            },
        ]

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citation_counts_by_act = AsyncMock(return_value=mock_counts)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/summary/by-act",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 2
            assert data["data"][0]["actName"] == "NI Act"
            assert data["data"][0]["citationCount"] == 10
        finally:
            app.dependency_overrides.clear()


class TestActDiscoveryEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations/acts/discovery endpoint."""

    @pytest.mark.anyio
    async def test_get_act_discovery_report_success(self) -> None:
        """Should get act discovery report."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_report = [
            create_mock_act_discovery_summary("NI Act", 10, ActResolutionStatus.MISSING),
            create_mock_act_discovery_summary("IPC", 5, ActResolutionStatus.AVAILABLE),
        ]

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_discovery = MagicMock()
        mock_discovery.get_discovery_report = AsyncMock(return_value=mock_report)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/acts/discovery",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 2
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_act_discovery_exclude_available(self) -> None:
        """Should exclude available acts when requested."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_report = [
            create_mock_act_discovery_summary("NI Act", 10, ActResolutionStatus.MISSING),
        ]

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_discovery = MagicMock()
        mock_discovery.get_discovery_report = AsyncMock(return_value=mock_report)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/acts/discovery",
                    params={"include_available": False},
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            # Verify the discovery service was called with correct param
            mock_discovery.get_discovery_report.assert_called_once_with(
                matter_id=matter_id,
                include_available=False,
            )
        finally:
            app.dependency_overrides.clear()


class TestMarkActUploadedEndpoint:
    """Tests for POST /api/matters/{matter_id}/citations/acts/mark-uploaded endpoint."""

    @pytest.mark.anyio
    async def test_mark_act_uploaded_success(self) -> None:
        """Should mark act as uploaded."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        act_document_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_discovery = MagicMock()
        mock_discovery.mark_act_uploaded = AsyncMock(return_value=True)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/acts/mark-uploaded",
                    json={
                        "act_name": "NI Act",
                        "act_document_id": act_document_id,
                    },
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["resolutionStatus"] == "available"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_mark_act_uploaded_not_found(self) -> None:
        """Should return 404 when act not found."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        act_document_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_discovery = MagicMock()
        mock_discovery.mark_act_uploaded = AsyncMock(return_value=False)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/acts/mark-uploaded",
                    json={
                        "act_name": "Unknown Act",
                        "act_document_id": act_document_id,
                    },
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "ACT_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_mark_act_uploaded_viewer_forbidden(self) -> None:
        """Viewer role should not be able to mark act as uploaded."""
        from app.api.deps import get_matter_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        act_document_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/acts/mark-uploaded",
                    json={
                        "act_name": "NI Act",
                        "act_document_id": act_document_id,
                    },
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestMarkActSkippedEndpoint:
    """Tests for POST /api/matters/{matter_id}/citations/acts/mark-skipped endpoint."""

    @pytest.mark.anyio
    async def test_mark_act_skipped_success(self) -> None:
        """Should mark act as skipped."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_discovery = MagicMock()
        mock_discovery.mark_act_skipped = AsyncMock(return_value=True)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/acts/mark-skipped",
                    json={"act_name": "NI Act"},
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["resolutionStatus"] == "skipped"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_mark_act_skipped_not_found(self) -> None:
        """Should return 404 when act not found."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_discovery = MagicMock()
        mock_discovery.mark_act_skipped = AsyncMock(return_value=False)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/acts/mark-skipped",
                    json={"act_name": "Unknown Act"},
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestVerifyCitationsBatchEndpoint:
    """Tests for POST /api/matters/{matter_id}/citations/verify endpoint."""

    @pytest.mark.anyio
    async def test_verify_citations_batch_success(self) -> None:
        """Should start batch verification for an Act."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        act_document_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citations_by_matter = AsyncMock(return_value=([], 5))

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            with patch("app.api.routes.citations.verify_citations_for_act") as mock_task:
                mock_task.delay.return_value = MagicMock(id="task-123")

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/citations/verify",
                        json={
                            "act_name": "Negotiable Instruments Act, 1881",
                            "act_document_id": act_document_id,
                        },
                        headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["taskId"] == "task-123"
                assert data["status"] == "started"
                assert data["totalCitations"] == 5
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_verify_citations_batch_viewer_forbidden(self) -> None:
        """Viewer role should not be able to trigger verification."""
        from app.api.deps import get_matter_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/verify",
                    json={
                        "act_name": "Test Act",
                        "act_document_id": str(uuid4()),
                    },
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestVerifySingleCitationEndpoint:
    """Tests for POST /api/matters/{matter_id}/citations/{citation_id}/verify endpoint."""

    @pytest.mark.anyio
    async def test_verify_single_citation_success(self) -> None:
        """Should start verification for a single citation."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        citation_id = str(uuid4())
        act_document_id = str(uuid4())
        user_id = "test-user-id"

        mock_citation = create_mock_citation(matter_id, citation_id)

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citation = AsyncMock(return_value=mock_citation)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            with patch("app.api.routes.citations.verify_single_citation") as mock_task:
                mock_task.delay.return_value = MagicMock(id="task-456")

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/citations/{citation_id}/verify",
                        json={
                            "act_document_id": act_document_id,
                            "act_name": "Negotiable Instruments Act, 1881",
                        },
                        headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["taskId"] == "task-456"
                assert data["totalCitations"] == 1
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_verify_single_citation_not_found(self) -> None:
        """Should return 404 when citation not found."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        citation_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_storage = MagicMock()
        mock_storage.get_citation = AsyncMock(return_value=None)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/matters/{matter_id}/citations/{citation_id}/verify",
                    json={
                        "act_document_id": str(uuid4()),
                        "act_name": "Test Act",
                    },
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "CITATION_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


class TestGetVerificationDetailsEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations/{citation_id}/verification endpoint."""

    @pytest.mark.anyio
    async def test_get_verification_details_success(self) -> None:
        """Should get verification details for a citation."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        citation_id = str(uuid4())
        user_id = "test-user-id"

        mock_citation = create_mock_citation(matter_id, citation_id)
        mock_citation.verification_status = VerificationStatus.VERIFIED
        mock_citation.target_page = 10
        mock_citation.confidence = 95.0

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        mock_storage = MagicMock()
        mock_storage.get_citation = AsyncMock(return_value=mock_citation)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/{citation_id}/verification",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["data"]["status"] == "verified"
            assert data["data"]["similarityScore"] == 95.0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_verification_details_not_found(self) -> None:
        """Should return 404 when citation not found."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_storage_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        citation_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        mock_storage = MagicMock()
        mock_storage.get_citation = AsyncMock(return_value=None)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/{citation_id}/verification",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestMarkActUploadedAndVerifyEndpoint:
    """Tests for POST /api/matters/{matter_id}/citations/acts/mark-uploaded-verify endpoint."""

    @pytest.mark.anyio
    async def test_mark_uploaded_and_verify_success(self) -> None:
        """Should mark act as uploaded and trigger verification."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import _get_discovery_service
        from app.core.config import get_settings

        matter_id = str(uuid4())
        act_document_id = str(uuid4())
        user_id = "test-user-id"

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        mock_discovery = MagicMock()
        mock_discovery.mark_act_uploaded = AsyncMock(return_value=True)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery

        try:
            with patch("app.api.routes.citations.trigger_verification_on_act_upload") as mock_task:
                mock_task.delay.return_value = MagicMock(id="task-789")

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        f"/api/matters/{matter_id}/citations/acts/mark-uploaded-verify",
                        json={
                            "act_name": "Negotiable Instruments Act, 1881",
                            "act_document_id": act_document_id,
                        },
                        headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["resolutionStatus"] == "available"
                mock_task.delay.assert_called_once()
        finally:
            app.dependency_overrides.clear()


class TestCitationStatsEndpoint:
    """Tests for GET /api/matters/{matter_id}/citations/stats endpoint."""

    @pytest.mark.anyio
    async def test_get_citation_stats_success(self) -> None:
        """Should get citation statistics."""
        from app.api.deps import get_matter_service
        from app.api.routes.citations import (
            _get_discovery_service,
            _get_storage_service,
        )
        from app.core.config import get_settings

        matter_id = str(uuid4())
        user_id = "test-user-id"

        mock_discovery_stats = {
            "total_acts": 5,
            "missing_count": 2,
            "available_count": 2,
            "skipped_count": 1,
            "total_citations": 25,
        }

        mock_counts = [
            {
                "act_name": "NI Act",
                "citation_count": 15,
                "verified_count": 10,
                "pending_count": 5,
            },
            {
                "act_name": "IPC",
                "citation_count": 10,
                "verified_count": 5,
                "pending_count": 5,
            },
        ]

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        mock_discovery = MagicMock()
        mock_discovery.get_discovery_stats = AsyncMock(return_value=mock_discovery_stats)

        mock_storage = MagicMock()
        mock_storage.get_citation_counts_by_act = AsyncMock(return_value=mock_counts)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_discovery_service] = lambda: mock_discovery
        app.dependency_overrides[_get_storage_service] = lambda: mock_storage

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/citations/stats",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["totalCitations"] == 25
            assert data["uniqueActs"] == 5
            assert data["verifiedCount"] == 15
            assert data["pendingCount"] == 10
            assert data["missingActsCount"] == 2
        finally:
            app.dependency_overrides.clear()
