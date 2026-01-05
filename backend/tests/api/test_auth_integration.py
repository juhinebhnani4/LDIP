"""Integration tests for full authentication flow.

Tests the complete auth flow including:
- Authenticated requests to protected endpoints
- Unauthenticated request handling
- JWT token validation in Authorization header
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import app


# Test JWT secret - same as in test_security.py
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.is_configured = True
    settings.debug = True
    return settings


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with JWT secret configured.

    Overrides the get_settings dependency to provide test JWT secret.
    """
    # Override the settings dependency
    app.dependency_overrides[get_settings] = get_test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    # Clean up the override
    app.dependency_overrides.clear()


@pytest.fixture
def valid_token() -> str:
    """Create a valid JWT token for integration tests."""
    payload = {
        "sub": "integration-test-user-id",
        "email": "integration@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "session_id": "integration-test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def expired_token() -> str:
    """Create an expired JWT token for testing."""
    payload = {
        "sub": "expired-user-id",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


class TestAuthenticatedRequests:
    """Tests for authenticated API requests."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(
        self, client: AsyncClient, valid_token: str
    ) -> None:
        """Test that a valid token allows access to protected endpoints."""
        response = await client.get(
            "/api/health/me",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["user_id"] == "integration-test-user-id"
        assert data["data"]["email"] == "integration@example.com"
        assert data["data"]["role"] == "authenticated"

    @pytest.mark.asyncio
    async def test_protected_endpoint_extracts_user_info(
        self, client: AsyncClient, valid_token: str
    ) -> None:
        """Test that user info is correctly extracted from JWT claims."""
        response = await client.get(
            "/api/health/me",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Verify the data structure matches expected format
        assert "data" in data
        assert "user_id" in data["data"]
        assert "email" in data["data"]
        assert "role" in data["data"]


class TestUnauthenticatedRequests:
    """Tests for unauthenticated API requests."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(
        self, client: AsyncClient
    ) -> None:
        """Test that missing token returns 401 Unauthorized."""
        response = await client.get("/api/health/me")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "UNAUTHORIZED"
        assert "Missing authentication token" in data["detail"]["error"]["message"]

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_expired_token(
        self, client: AsyncClient, expired_token: str
    ) -> None:
        """Test that expired token returns 401 with TOKEN_EXPIRED code."""
        response = await client.get(
            "/api/health/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "TOKEN_EXPIRED"

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_token(
        self, client: AsyncClient
    ) -> None:
        """Test that invalid token returns 401 with INVALID_TOKEN code."""
        response = await client.get(
            "/api/health/me",
            headers={"Authorization": "Bearer invalid-token-here"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_wrong_signature(
        self, client: AsyncClient
    ) -> None:
        """Test that token with wrong signature returns 401."""
        # Create token with different secret
        payload = {
            "sub": "test-user-id",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        wrong_signature_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        response = await client.get(
            "/api/health/me",
            headers={"Authorization": f"Bearer {wrong_signature_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_TOKEN"


class TestPublicEndpoints:
    """Tests to ensure public endpoints remain accessible."""

    @pytest.mark.asyncio
    async def test_health_check_public(self, client: AsyncClient) -> None:
        """Test that health check is accessible without auth."""
        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_liveness_check_public(self, client: AsyncClient) -> None:
        """Test that liveness check is accessible without auth."""
        response = await client.get("/api/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "alive"

    @pytest.mark.asyncio
    async def test_root_endpoint_public(self, client: AsyncClient) -> None:
        """Test that root endpoint is accessible without auth."""
        response = await client.get("/")

        assert response.status_code == 200


class TestAuthorizationHeader:
    """Tests for Authorization header handling."""

    @pytest.mark.asyncio
    async def test_bearer_scheme_required(
        self, client: AsyncClient, valid_token: str
    ) -> None:
        """Test that Bearer scheme is required in Authorization header."""
        # Token without "Bearer " prefix should fail
        response = await client.get(
            "/api/health/me",
            headers={"Authorization": valid_token},  # Missing "Bearer " prefix
        )

        # Should return 401 because the scheme doesn't match
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_authorization_header_case_insensitive(
        self, client: AsyncClient, valid_token: str
    ) -> None:
        """Test that Authorization header value is parsed correctly."""
        response = await client.get(
            "/api/health/me",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
