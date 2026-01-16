"""Integration tests for entity alias management API endpoints.

Tests the alias management endpoints:
- GET /matters/{matter_id}/entities/{entity_id}/aliases
- POST /matters/{matter_id}/entities/{entity_id}/aliases
- DELETE /matters/{matter_id}/entities/{entity_id}/aliases
- POST /matters/{matter_id}/entities/merge

Story: 2c-2 Alias Resolution
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_matter_service
from app.api.routes.entities import _get_mig_service
from app.core.config import Settings, get_settings
from app.main import app
from app.models.entity import EntityNode, EntityType
from app.models.matter import MatterRole

# Fixed timestamp for test data
TEST_TIMESTAMP = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)

# Test JWT secret
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


# =============================================================================
# Test Helpers
# =============================================================================


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


def create_mock_matter_service(role: MatterRole | None = MatterRole.EDITOR) -> MagicMock:
    """Create a mock matter service for testing."""
    mock_service = MagicMock()
    mock_service.get_user_role.return_value = role
    return mock_service


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_entity() -> EntityNode:
    """Create a mock entity for testing."""
    return EntityNode(
        id="entity-123",
        matter_id="matter-456",
        canonical_name="Nirav Dineshbhai Jobalia",
        entity_type=EntityType.PERSON,
        metadata={},
        mention_count=5,
        aliases=["N.D. Jobalia", "Mr. Jobalia"],
        created_at=TEST_TIMESTAMP,
        updated_at=TEST_TIMESTAMP,
    )


# =============================================================================
# Get Aliases Tests
# =============================================================================


class TestGetEntityAliases:
    """Tests for GET /matters/{matter_id}/entities/{entity_id}/aliases."""

    @pytest.mark.anyio
    async def test_get_aliases_success(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test successful alias retrieval."""
        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.return_value = mock_entity

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/matters/matter-456/entities/entity-123/aliases",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["entityId"] == "entity-123"
            assert "N.D. Jobalia" in data["data"]
            assert "Mr. Jobalia" in data["data"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_aliases_entity_not_found(self) -> None:
        """Test 404 when entity not found."""
        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.return_value = None

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.VIEWER)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/matters/matter-456/entities/nonexistent/aliases",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Add Alias Tests
# =============================================================================


class TestAddEntityAlias:
    """Tests for POST /matters/{matter_id}/entities/{entity_id}/aliases."""

    @pytest.mark.anyio
    async def test_add_alias_success(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test successful alias addition."""
        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.return_value = mock_entity

        # Updated entity with new alias
        updated_entity = EntityNode(
            id=mock_entity.id,
            matter_id=mock_entity.matter_id,
            canonical_name=mock_entity.canonical_name,
            entity_type=mock_entity.entity_type,
            metadata={},
            mention_count=mock_entity.mention_count,
            aliases=mock_entity.aliases + ["Nirav J."],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        mock_mig_service.add_alias_to_entity.return_value = updated_entity

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.EDITOR)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/matters/matter-456/entities/entity-123/aliases",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"alias": "Nirav J."},
                )

            assert response.status_code == 200
            data = response.json()
            assert "Nirav J." in data["data"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_add_alias_already_exists(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test 400 when alias already exists."""
        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.return_value = mock_entity

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.EDITOR)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/matters/matter-456/entities/entity-123/aliases",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"alias": "N.D. Jobalia"},  # Already exists
                )

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Remove Alias Tests
# =============================================================================


class TestRemoveEntityAlias:
    """Tests for DELETE /matters/{matter_id}/entities/{entity_id}/aliases."""

    @pytest.mark.anyio
    async def test_remove_alias_success(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test successful alias removal."""
        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.return_value = mock_entity

        # Updated entity without removed alias
        updated_entity = EntityNode(
            id=mock_entity.id,
            matter_id=mock_entity.matter_id,
            canonical_name=mock_entity.canonical_name,
            entity_type=mock_entity.entity_type,
            metadata={},
            mention_count=mock_entity.mention_count,
            aliases=["Mr. Jobalia"],  # N.D. Jobalia removed
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        mock_mig_service.remove_alias_from_entity.return_value = updated_entity

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.EDITOR)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # DELETE with body requires using request() method
                response = await client.request(
                    "DELETE",
                    "/api/matters/matter-456/entities/entity-123/aliases",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"alias": "N.D. Jobalia"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "N.D. Jobalia" not in data["data"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_remove_alias_not_found(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test 404 when alias not found."""
        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.return_value = mock_entity

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.EDITOR)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # DELETE with body requires using request() method
                response = await client.request(
                    "DELETE",
                    "/api/matters/matter-456/entities/entity-123/aliases",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"alias": "Nonexistent Alias"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Merge Entities Tests
# =============================================================================


class TestMergeEntities:
    """Tests for POST /matters/{matter_id}/entities/merge."""

    @pytest.mark.anyio
    async def test_merge_entities_success(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test successful entity merge."""
        source_entity = EntityNode(
            id="source-entity",
            matter_id="matter-456",
            canonical_name="N.D. Jobalia",
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=3,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )

        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.side_effect = [source_entity, mock_entity]

        # Mock database RPC call
        mock_db_client = MagicMock()
        mock_db_client.rpc.return_value.execute.return_value = MagicMock()

        app.dependency_overrides[get_settings] = get_test_settings
        # Merge requires OWNER role
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.OWNER)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            # Patch at source module where get_service_client is imported from
            with patch(
                "app.services.supabase.client.get_service_client",
                return_value=mock_db_client,
            ):
                token = create_test_token()
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        "/api/matters/matter-456/entities/merge",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "source_entity_id": "source-entity",
                            "target_entity_id": "entity-123",
                            "reason": "Same person",
                        },
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["keptEntityId"] == "entity-123"
            assert data["deletedEntityId"] == "source-entity"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_merge_self_not_allowed(self) -> None:
        """Test 400 when trying to merge entity with itself."""
        app.dependency_overrides[get_settings] = get_test_settings
        # Merge requires OWNER role
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.OWNER)

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/matters/matter-456/entities/merge",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "source_entity_id": "entity-123",
                        "target_entity_id": "entity-123",  # Same ID
                    },
                )

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_merge_type_mismatch(
        self,
        mock_entity: EntityNode,
    ) -> None:
        """Test 400 when merging entities of different types."""
        org_entity = EntityNode(
            id="org-entity",
            matter_id="matter-456",
            canonical_name="ABC Corp",
            entity_type=EntityType.ORG,  # Different type
            metadata={},
            mention_count=10,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )

        mock_mig_service = AsyncMock()
        mock_mig_service.get_entity.side_effect = [org_entity, mock_entity]

        app.dependency_overrides[get_settings] = get_test_settings
        # Merge requires OWNER role
        app.dependency_overrides[get_matter_service] = lambda: create_mock_matter_service(MatterRole.OWNER)
        app.dependency_overrides[_get_mig_service] = lambda: mock_mig_service

        try:
            token = create_test_token()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/matters/matter-456/entities/merge",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "source_entity_id": "org-entity",
                        "target_entity_id": "entity-123",
                    },
                )

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()
