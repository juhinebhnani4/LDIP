"""Unit tests for entity API routes."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.entity import (
    EntityEdge,
    EntityMention,
    EntityNode,
    EntityType,
    RelationshipType,
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
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def create_mock_entity(matter_id: str, entity_id: str | None = None) -> EntityNode:
    """Create a mock entity node for testing."""
    return EntityNode(
        id=entity_id or str(uuid4()),
        matter_id=matter_id,
        canonical_name="Nirav Jobalia",
        entity_type=EntityType.PERSON,
        metadata={"roles": ["plaintiff"]},
        mention_count=5,
        aliases=["Mr. Jobalia", "N.D. Jobalia"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def create_mock_edge(matter_id: str) -> EntityEdge:
    """Create a mock entity edge for testing."""
    return EntityEdge(
        id=str(uuid4()),
        matter_id=matter_id,
        source_entity_id=str(uuid4()),
        target_entity_id=str(uuid4()),
        relationship_type=RelationshipType.HAS_ROLE,
        confidence=0.9,
        metadata={"description": "Director of"},
        created_at=datetime.now(timezone.utc),
    )


def create_mock_mention(entity_id: str) -> EntityMention:
    """Create a mock entity mention for testing."""
    return EntityMention(
        id=str(uuid4()),
        entity_id=entity_id,
        document_id=str(uuid4()),
        chunk_id=str(uuid4()),
        page_number=5,
        bbox_ids=[str(uuid4())],
        mention_text="Mr. Jobalia",
        context="...filed by Mr. Jobalia...",
        confidence=0.95,
        created_at=datetime.now(timezone.utc),
    )


class TestListEntitiesEndpoint:
    """Tests for GET /api/matters/{matter_id}/entities endpoint."""

    @pytest.mark.anyio
    async def test_returns_entities_on_success(self) -> None:
        """Should return entities when authorized."""
        from app.api.deps import get_matter_service
        from app.api.routes.entities import _get_mig_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "test-user-id"

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock MIG service
        mock_mig_service = MagicMock()
        mock_entities = [create_mock_entity(matter_id), create_mock_entity(matter_id)]
        mock_mig_service.get_entities_by_matter = AsyncMock(
            return_value=(mock_entities, 2)
        )

        # Override dependencies
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities",
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
    async def test_filters_by_entity_type(self) -> None:
        """Should filter entities by type when specified."""
        from app.api.deps import get_matter_service
        from app.api.routes.entities import _get_mig_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "test-user-id"

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock MIG service
        mock_mig_service = MagicMock()
        mock_entity = create_mock_entity(matter_id)
        mock_mig_service.get_entities_by_matter = AsyncMock(
            return_value=([mock_entity], 1)
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities?entity_type=PERSON",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200

            # Verify filter was passed to service
            mock_mig_service.get_entities_by_matter.assert_called_once()
            call_args = mock_mig_service.get_entities_by_matter.call_args
            assert call_args.kwargs.get("entity_type") == EntityType.PERSON
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_403_when_not_member(self) -> None:
        """Should return 403 when user is not a matter member."""
        from app.api.deps import get_matter_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "test-user-id"

        # Mock matter access - user has no role
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = None

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            # Returns 404 to hide matter existence (security best practice)
            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "MATTER_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


class TestGetEntityEndpoint:
    """Tests for GET /api/matters/{matter_id}/entities/{entity_id} endpoint."""

    @pytest.mark.anyio
    async def test_returns_entity_with_relations(self) -> None:
        """Should return entity with relationships and mentions."""
        from app.api.deps import get_matter_service
        from app.api.routes.entities import _get_mig_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        entity_id = "660e8400-e29b-41d4-a716-446655440111"
        user_id = "test-user-id"

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock MIG service
        mock_mig_service = MagicMock()
        mock_entity = create_mock_entity(matter_id, entity_id)
        mock_edges = [create_mock_edge(matter_id)]
        mock_mentions = [create_mock_mention(entity_id)]

        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)
        mock_mig_service.get_entity_relationships = AsyncMock(return_value=mock_edges)
        mock_mig_service.get_entity_mentions = AsyncMock(
            return_value=(mock_mentions, 1)
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities/{entity_id}",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["data"]["id"] == entity_id
            assert data["data"]["canonical_name"] == "Nirav Jobalia"
            assert "relationships" in data["data"]
            assert "recent_mentions" in data["data"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_404_when_entity_not_found(self) -> None:
        """Should return 404 when entity does not exist."""
        from app.api.deps import get_matter_service
        from app.api.routes.entities import _get_mig_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        entity_id = "660e8400-e29b-41d4-a716-446655440111"
        user_id = "test-user-id"

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock MIG service - entity not found
        mock_mig_service = MagicMock()
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities/{entity_id}",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "ENTITY_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


class TestGetEntityMentionsEndpoint:
    """Tests for GET /api/matters/{matter_id}/entities/{entity_id}/mentions endpoint."""

    @pytest.mark.anyio
    async def test_returns_paginated_mentions(self) -> None:
        """Should return paginated list of entity mentions."""
        from app.api.deps import get_matter_service
        from app.api.routes.entities import _get_mig_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        entity_id = "660e8400-e29b-41d4-a716-446655440111"
        user_id = "test-user-id"

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock MIG service
        mock_mig_service = MagicMock()
        mock_entity = create_mock_entity(matter_id, entity_id)
        mock_mentions = [
            create_mock_mention(entity_id),
            create_mock_mention(entity_id),
        ]

        mock_mig_service.get_entity = AsyncMock(return_value=mock_entity)
        mock_mig_service.get_entity_mentions = AsyncMock(
            return_value=(mock_mentions, 2)
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities/{entity_id}/mentions",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "meta" in data
            assert len(data["data"]) == 2
            assert data["meta"]["total"] == 2
            assert data["data"][0]["mention_text"] == "Mr. Jobalia"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_404_when_entity_not_found(self) -> None:
        """Should return 404 when entity does not exist."""
        from app.api.deps import get_matter_service
        from app.api.routes.entities import _get_mig_service
        from app.core.config import get_settings

        matter_id = "550e8400-e29b-41d4-a716-446655440000"
        entity_id = "660e8400-e29b-41d4-a716-446655440111"
        user_id = "test-user-id"

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock MIG service - entity not found
        mock_mig_service = MagicMock()
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/matters/{matter_id}/entities/{entity_id}/mentions",
                    headers={"Authorization": f"Bearer {create_test_token(user_id)}"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
