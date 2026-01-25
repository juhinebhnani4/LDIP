"""Unit tests for SSE error reporting API routes.

Story 6.2: Add SSE Error Rate Logging

Uses FastAPI dependency_overrides pattern for proper test isolation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import app

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
    # Rate limiting settings
    settings.rate_limit_enabled = False  # Disable for tests
    settings.rate_limit_default = 100
    settings.rate_limit_critical = 30
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


class TestReportSSEError:
    """Tests for POST /api/chat/report-sse-error endpoint."""

    @pytest_asyncio.fixture
    async def authorized_client(self) -> AsyncClient:
        """Create an authorized async test client."""
        # Override settings
        app.dependency_overrides[get_settings] = get_test_settings

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_report_sse_error_success(self, authorized_client: AsyncClient):
        """Test successful SSE error report submission."""
        token = create_test_token()

        with patch("app.api.routes.chat.log_sse_parse_error") as mock_log:
            response = await authorized_client.post(
                "/api/chat/report-sse-error",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "matter_id": "matter-456",
                    "error_type": "sse_json_parse_failed",
                    "error_message": "Unexpected token at position 42",
                    "raw_chunk": '{"incomplete": true',
                    "timestamp": "2024-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "logged"}
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_sse_error_without_optional_fields(
        self, authorized_client: AsyncClient
    ):
        """Test SSE error report without optional fields."""
        token = create_test_token()

        with patch("app.api.routes.chat.log_sse_parse_error") as mock_log:
            response = await authorized_client.post(
                "/api/chat/report-sse-error",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "error_type": "sse_json_parse_failed",
                    "error_message": "Parse error",
                    "timestamp": "2024-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 200
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_sse_error_max_errors_exceeded(
        self, authorized_client: AsyncClient
    ):
        """Test reporting max errors exceeded event."""
        token = create_test_token()

        with patch("app.api.routes.chat.log_sse_parse_error") as mock_log:
            response = await authorized_client.post(
                "/api/chat/report-sse-error",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "matter_id": "matter-456",
                    "error_type": "sse_max_errors_exceeded",
                    "error_message": "Aborted after 5 parse errors",
                    "timestamp": "2024-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 200
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_sse_error_requires_auth(self, authorized_client: AsyncClient):
        """Test that SSE error report requires authentication."""
        response = await authorized_client.post(
            "/api/chat/report-sse-error",
            json={
                "session_id": "sse_abc123",
                "error_type": "sse_json_parse_failed",
                "error_message": "Parse error",
                "timestamp": "2024-01-15T10:30:00Z",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_report_sse_error_missing_required_fields(
        self, authorized_client: AsyncClient
    ):
        """Test validation for missing required fields."""
        token = create_test_token()

        response = await authorized_client.post(
            "/api/chat/report-sse-error",
            headers={"Authorization": f"Bearer {token}"},
            json={
                # Missing session_id, error_type, error_message, timestamp
            },
        )

        assert response.status_code == 422  # Validation error


class TestReportSSEStatus:
    """Tests for POST /api/chat/report-sse-status endpoint."""

    @pytest_asyncio.fixture
    async def authorized_client(self) -> AsyncClient:
        """Create an authorized async test client."""
        app.dependency_overrides[get_settings] = get_test_settings

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_report_sse_status_complete(self, authorized_client: AsyncClient):
        """Test reporting stream completion."""
        token = create_test_token()

        with patch("app.api.routes.chat.log_sse_stream_status") as mock_log:
            response = await authorized_client.post(
                "/api/chat/report-sse-status",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "matter_id": "matter-456",
                    "status": "complete",
                    "parse_error_count": 0,
                    "total_chunks": 42,
                    "duration_ms": 3500,
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "logged"}
        mock_log.assert_called_once_with(
            user_id="test-user-id",
            matter_id="matter-456",
            session_id="sse_abc123",
            status="complete",
            parse_error_count=0,
            total_chunks=42,
            duration_ms=3500,
        )

    @pytest.mark.asyncio
    async def test_report_sse_status_interrupted(self, authorized_client: AsyncClient):
        """Test reporting stream interruption."""
        token = create_test_token()

        with patch("app.api.routes.chat.log_sse_stream_status") as mock_log:
            response = await authorized_client.post(
                "/api/chat/report-sse-status",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "status": "interrupted",
                    "parse_error_count": 3,
                    "total_chunks": 15,
                },
            )

        assert response.status_code == 200
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["status"] == "interrupted"
        assert call_kwargs["parse_error_count"] == 3

    @pytest.mark.asyncio
    async def test_report_sse_status_requires_auth(
        self, authorized_client: AsyncClient
    ):
        """Test that SSE status report requires authentication."""
        response = await authorized_client.post(
            "/api/chat/report-sse-status",
            json={
                "session_id": "sse_abc123",
                "status": "complete",
                "parse_error_count": 0,
                "total_chunks": 10,
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_report_sse_status_missing_required_fields(
        self, authorized_client: AsyncClient
    ):
        """Test validation for missing required fields."""
        token = create_test_token()

        response = await authorized_client.post(
            "/api/chat/report-sse-status",
            headers={"Authorization": f"Bearer {token}"},
            json={
                # Missing session_id, status
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_report_sse_status_with_duration(
        self, authorized_client: AsyncClient
    ):
        """Test reporting stream status with duration."""
        token = create_test_token()

        with patch("app.api.routes.chat.log_sse_stream_status") as mock_log:
            response = await authorized_client.post(
                "/api/chat/report-sse-status",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "status": "complete",
                    "parse_error_count": 1,
                    "total_chunks": 100,
                    "duration_ms": 5000,
                },
            )

        assert response.status_code == 200
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["duration_ms"] == 5000


class TestSSEReportingLogsCorrectUserId:
    """Tests verifying user_id is correctly extracted from auth token."""

    @pytest_asyncio.fixture
    async def authorized_client(self) -> AsyncClient:
        """Create an authorized async test client."""
        app.dependency_overrides[get_settings] = get_test_settings

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_error_report_logs_correct_user_id(
        self, authorized_client: AsyncClient
    ):
        """Test that error report logs the authenticated user's ID."""
        user_id = "specific-user-123"
        token = create_test_token(user_id=user_id)

        with patch("app.api.routes.chat.log_sse_parse_error") as mock_log:
            await authorized_client.post(
                "/api/chat/report-sse-error",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "error_type": "sse_json_parse_failed",
                    "error_message": "Error",
                    "timestamp": "2024-01-15T10:30:00Z",
                },
            )

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_status_report_logs_correct_user_id(
        self, authorized_client: AsyncClient
    ):
        """Test that status report logs the authenticated user's ID."""
        user_id = "another-user-456"
        token = create_test_token(user_id=user_id)

        with patch("app.api.routes.chat.log_sse_stream_status") as mock_log:
            await authorized_client.post(
                "/api/chat/report-sse-status",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": "sse_abc123",
                    "status": "complete",
                    "parse_error_count": 0,
                    "total_chunks": 10,
                },
            )

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] == user_id
