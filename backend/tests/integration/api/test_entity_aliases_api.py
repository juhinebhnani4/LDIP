"""Integration tests for entity alias management API endpoints.

Tests the alias management endpoints:
- GET /matters/{matter_id}/entities/{entity_id}/aliases
- POST /matters/{matter_id}/entities/{entity_id}/aliases
- DELETE /matters/{matter_id}/entities/{entity_id}/aliases
- POST /matters/{matter_id}/entities/merge

Story: 2c-2 Alias Resolution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.entity import EntityNode, EntityType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


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
    )


@pytest.fixture
def auth_headers() -> dict:
    """Create mock auth headers."""
    return {"Authorization": "Bearer test-token"}


# =============================================================================
# Get Aliases Tests
# =============================================================================


class TestGetEntityAliases:
    """Tests for GET /matters/{matter_id}/entities/{entity_id}/aliases."""

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_get_aliases_success(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test successful alias retrieval."""
        # Setup mocks
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )
        mock_service = AsyncMock()
        mock_service.get_entity.return_value = mock_entity
        mock_mig_service.return_value = mock_service

        response = client.get(
            "/api/v1/matters/matter-456/entities/entity-123/aliases",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["entityId"] == "entity-123"
        assert "N.D. Jobalia" in data["data"]
        assert "Mr. Jobalia" in data["data"]

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_get_aliases_entity_not_found(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        """Test 404 when entity not found."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )
        mock_service = AsyncMock()
        mock_service.get_entity.return_value = None
        mock_mig_service.return_value = mock_service

        response = client.get(
            "/api/v1/matters/matter-456/entities/nonexistent/aliases",
            headers=auth_headers,
        )

        assert response.status_code == 404


# =============================================================================
# Add Alias Tests
# =============================================================================


class TestAddEntityAlias:
    """Tests for POST /matters/{matter_id}/entities/{entity_id}/aliases."""

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_add_alias_success(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test successful alias addition."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )

        mock_service = AsyncMock()
        mock_service.get_entity.return_value = mock_entity

        # Updated entity with new alias
        updated_entity = EntityNode(
            id=mock_entity.id,
            matter_id=mock_entity.matter_id,
            canonical_name=mock_entity.canonical_name,
            entity_type=mock_entity.entity_type,
            metadata={},
            mention_count=mock_entity.mention_count,
            aliases=mock_entity.aliases + ["Nirav J."],
        )
        mock_service.add_alias_to_entity.return_value = updated_entity
        mock_mig_service.return_value = mock_service

        response = client.post(
            "/api/v1/matters/matter-456/entities/entity-123/aliases",
            headers=auth_headers,
            json={"alias": "Nirav J."},
        )

        assert response.status_code == 200
        data = response.json()
        assert "Nirav J." in data["data"]

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_add_alias_already_exists(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test 400 when alias already exists."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )
        mock_service = AsyncMock()
        mock_service.get_entity.return_value = mock_entity
        mock_mig_service.return_value = mock_service

        response = client.post(
            "/api/v1/matters/matter-456/entities/entity-123/aliases",
            headers=auth_headers,
            json={"alias": "N.D. Jobalia"},  # Already exists
        )

        assert response.status_code == 400


# =============================================================================
# Remove Alias Tests
# =============================================================================


class TestRemoveEntityAlias:
    """Tests for DELETE /matters/{matter_id}/entities/{entity_id}/aliases."""

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_remove_alias_success(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test successful alias removal."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )

        mock_service = AsyncMock()
        mock_service.get_entity.return_value = mock_entity

        # Updated entity without removed alias
        updated_entity = EntityNode(
            id=mock_entity.id,
            matter_id=mock_entity.matter_id,
            canonical_name=mock_entity.canonical_name,
            entity_type=mock_entity.entity_type,
            metadata={},
            mention_count=mock_entity.mention_count,
            aliases=["Mr. Jobalia"],  # N.D. Jobalia removed
        )
        mock_service.remove_alias_from_entity.return_value = updated_entity
        mock_mig_service.return_value = mock_service

        response = client.delete(
            "/api/v1/matters/matter-456/entities/entity-123/aliases",
            headers=auth_headers,
            json={"alias": "N.D. Jobalia"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "N.D. Jobalia" not in data["data"]

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_remove_alias_not_found(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test 404 when alias not found."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )
        mock_service = AsyncMock()
        mock_service.get_entity.return_value = mock_entity
        mock_mig_service.return_value = mock_service

        response = client.delete(
            "/api/v1/matters/matter-456/entities/entity-123/aliases",
            headers=auth_headers,
            json={"alias": "Nonexistent Alias"},
        )

        assert response.status_code == 404


# =============================================================================
# Merge Entities Tests
# =============================================================================


class TestMergeEntities:
    """Tests for POST /matters/{matter_id}/entities/merge."""

    @patch("app.services.supabase.client.get_service_client")
    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_merge_entities_success(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        mock_db_client: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test successful entity merge."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )

        source_entity = EntityNode(
            id="source-entity",
            matter_id="matter-456",
            canonical_name="N.D. Jobalia",
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=3,
            aliases=[],
        )

        mock_service = AsyncMock()
        mock_service.get_entity.side_effect = [source_entity, mock_entity]
        mock_mig_service.return_value = mock_service

        # Mock database RPC call
        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value = MagicMock()
        mock_db_client.return_value = mock_client

        response = client.post(
            "/api/v1/matters/matter-456/entities/merge",
            headers=auth_headers,
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

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_merge_self_not_allowed(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        auth_headers: dict,
    ) -> None:
        """Test 400 when trying to merge entity with itself."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )

        response = client.post(
            "/api/v1/matters/matter-456/entities/merge",
            headers=auth_headers,
            json={
                "source_entity_id": "entity-123",
                "target_entity_id": "entity-123",  # Same ID
            },
        )

        assert response.status_code == 400

    @patch("app.api.routes.entities._get_mig_service")
    @patch("app.api.deps.require_matter_role")
    def test_merge_type_mismatch(
        self,
        mock_auth: MagicMock,
        mock_mig_service: MagicMock,
        client: TestClient,
        mock_entity: EntityNode,
        auth_headers: dict,
    ) -> None:
        """Test 400 when merging entities of different types."""
        mock_auth.return_value = lambda: MagicMock(
            matter_id="matter-456",
            user_id="user-123",
        )

        org_entity = EntityNode(
            id="org-entity",
            matter_id="matter-456",
            canonical_name="ABC Corp",
            entity_type=EntityType.ORG,  # Different type
            metadata={},
            mention_count=10,
            aliases=[],
        )

        mock_service = AsyncMock()
        mock_service.get_entity.side_effect = [org_entity, mock_entity]
        mock_mig_service.return_value = mock_service

        response = client.post(
            "/api/v1/matters/matter-456/entities/merge",
            headers=auth_headers,
            json={
                "source_entity_id": "org-entity",
                "target_entity_id": "entity-123",
            },
        )

        assert response.status_code == 400
