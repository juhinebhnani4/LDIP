"""API integration tests for matter endpoints.

Tests the matter API endpoints including:
- Matter CRUD operations
- Role-based access control
- Member management
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
from app.models.matter import (
    Matter,
    MatterMember,
    MatterRole,
    MatterStatus,
    MatterWithMembers,
)
from app.services.matter_service import (
    InsufficientPermissionsError,
    MatterNotFoundError,
    MatterService,
    MemberAlreadyExistsError,
    UserNotFoundError,
)


# Test JWT secret - same as in other test files
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.is_configured = True
    settings.debug = True
    return settings


def create_test_token(user_id: str = "test-user-id", email: str = "test@example.com") -> str:
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
def valid_token() -> str:
    """Create a valid JWT token for tests."""
    return create_test_token()


@pytest.fixture
def sample_matter() -> Matter:
    """Create a sample matter for tests."""
    return Matter(
        id="matter-12345",
        title="Test Matter",
        description="Test description",
        status=MatterStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        role=MatterRole.OWNER,
        member_count=1,
    )


@pytest.fixture
def sample_matter_with_members() -> MatterWithMembers:
    """Create a sample matter with members for tests."""
    return MatterWithMembers(
        id="matter-12345",
        title="Test Matter",
        description="Test description",
        status=MatterStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        role=MatterRole.OWNER,
        member_count=1,
        members=[
            MatterMember(
                id="member-1",
                user_id="test-user-id",
                email="test@example.com",
                full_name="Test User",
                role=MatterRole.OWNER,
                invited_by=None,
                invited_at=datetime.now(timezone.utc),
            )
        ],
    )


@pytest_asyncio.fixture
async def client(
    mock_matter_service: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with mocked dependencies."""
    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestCreateMatter:
    """Tests for POST /api/matters."""

    @pytest.mark.asyncio
    async def test_create_matter_returns_201(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_matter: Matter,
    ) -> None:
        """Test that creating a matter returns 201 with the matter."""
        mock_matter_service.create_matter.return_value = sample_matter

        response = await client.post(
            "/api/matters",
            json={"title": "Test Matter", "description": "Test description"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["title"] == "Test Matter"
        assert data["data"]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_create_matter_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that creating a matter requires authentication."""
        response = await client.post(
            "/api/matters",
            json={"title": "Test Matter"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_matter_validates_title(
        self,
        client: AsyncClient,
        valid_token: str,
    ) -> None:
        """Test that creating a matter validates required fields."""
        response = await client.post(
            "/api/matters",
            json={},  # Missing title
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422  # Validation error


class TestListMatters:
    """Tests for GET /api/matters."""

    @pytest.mark.asyncio
    async def test_list_matters_returns_paginated_list(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_matter: Matter,
    ) -> None:
        """Test that listing matters returns paginated results."""
        mock_matter_service.get_user_matters.return_value = ([sample_matter], 1)

        response = await client.get(
            "/api/matters",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["meta"]["total"] == 1

    @pytest.mark.asyncio
    async def test_list_matters_returns_only_users_matters(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that listing matters only returns user's accessible matters."""
        mock_matter_service.get_user_matters.return_value = ([], 0)

        response = await client.get(
            "/api/matters",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0


class TestGetMatter:
    """Tests for GET /api/matters/{matter_id}."""

    @pytest.mark.asyncio
    async def test_get_matter_returns_matter_with_members(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_matter_with_members: MatterWithMembers,
    ) -> None:
        """Test that getting a matter returns it with members."""
        mock_matter_service.get_matter.return_value = sample_matter_with_members

        response = await client.get(
            "/api/matters/matter-12345",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == "matter-12345"
        assert len(data["data"]["members"]) == 1

    @pytest.mark.asyncio
    async def test_get_matter_returns_404_when_not_found(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that getting a non-existent matter returns 404."""
        mock_matter_service.get_matter.side_effect = MatterNotFoundError("nonexistent")

        response = await client.get(
            "/api/matters/nonexistent",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "MATTER_NOT_FOUND"


class TestUpdateMatter:
    """Tests for PATCH /api/matters/{matter_id}."""

    @pytest.mark.asyncio
    async def test_update_matter_returns_updated_matter(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
        sample_matter: Matter,
    ) -> None:
        """Test that updating a matter returns the updated matter."""
        # Mock role check for editor/owner
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER
        mock_matter_service.update_matter.return_value = sample_matter

        response = await client.patch(
            "/api/matters/matter-12345",
            json={"title": "Updated Title"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_update_matter(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that viewer cannot update matter (403)."""
        # Mock role check returning viewer
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        response = await client.patch(
            "/api/matters/matter-12345",
            json={"title": "Updated Title"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 403


class TestDeleteMatter:
    """Tests for DELETE /api/matters/{matter_id}."""

    @pytest.mark.asyncio
    async def test_owner_can_delete_matter(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that owner can delete matter."""
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER
        mock_matter_service.delete_matter.return_value = None

        response = await client.delete(
            "/api/matters/matter-12345",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_editor_cannot_delete_matter(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that editor cannot delete matter (403)."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.delete(
            "/api/matters/matter-12345",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 403


class TestInviteMember:
    """Tests for POST /api/matters/{matter_id}/members."""

    @pytest.mark.asyncio
    async def test_owner_can_invite_member(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that owner can invite a member."""
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER
        mock_matter_service.invite_member.return_value = MatterMember(
            id="member-new",
            user_id="new-user-id",
            email="new@example.com",
            full_name="New User",
            role=MatterRole.EDITOR,
            invited_by="test-user-id",
            invited_at=datetime.now(timezone.utc),
        )

        response = await client.post(
            "/api/matters/matter-12345/members",
            json={"email": "new@example.com", "role": "editor"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_non_owner_cannot_invite(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that non-owner cannot invite (403)."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.post(
            "/api/matters/matter-12345/members",
            json={"email": "new@example.com", "role": "viewer"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 403


class TestRemoveMember:
    """Tests for DELETE /api/matters/{matter_id}/members/{user_id}."""

    @pytest.mark.asyncio
    async def test_owner_can_remove_member(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that owner can remove a member."""
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER
        mock_matter_service.remove_member.return_value = None

        response = await client.delete(
            "/api/matters/matter-12345/members/other-user-id",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_editor_cannot_remove_member(
        self,
        client: AsyncClient,
        mock_matter_service: MagicMock,
        valid_token: str,
    ) -> None:
        """Test that editor cannot remove member (403)."""
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        response = await client.delete(
            "/api/matters/matter-12345/members/other-user-id",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 403
