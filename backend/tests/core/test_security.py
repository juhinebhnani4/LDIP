"""Tests for JWT validation and security functions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import Settings
from app.core.security import get_current_user, get_optional_user
from app.models.auth import AuthenticatedUser


# Test JWT secret for testing purposes only
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with JWT secret."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.supabase_url = "https://test.supabase.co"
    return settings


@pytest.fixture
def valid_token_payload() -> dict:
    """Create a valid JWT payload matching Supabase structure."""
    return {
        "sub": "test-user-id-12345",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "session_id": "test-session-id",
    }


@pytest.fixture
def valid_token(valid_token_payload: dict) -> str:
    """Create a valid JWT token."""
    return jwt.encode(valid_token_payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def expired_token() -> str:
    """Create an expired JWT token."""
    payload = {
        "sub": "test-user-id",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def invalid_audience_token() -> str:
    """Create a token with wrong audience."""
    payload = {
        "sub": "test-user-id",
        "aud": "wrong-audience",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def invalid_signature_token() -> str:
    """Create a token with invalid signature."""
    payload = {
        "sub": "test-user-id",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "wrong-secret", algorithm="HS256")


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    async def test_valid_token_returns_user(
        self, valid_token: str, test_settings: Settings
    ) -> None:
        """Test that a valid token extracts correct user claims."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_token
        )

        user = await get_current_user(credentials, test_settings)

        assert isinstance(user, AuthenticatedUser)
        assert user.id == "test-user-id-12345"
        assert user.email == "test@example.com"
        assert user.role == "authenticated"
        assert user.session_id == "test-session-id"

    async def test_missing_token_raises_401(self, test_settings: Settings) -> None:
        """Test that missing token returns 401 Unauthorized."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None, test_settings)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "UNAUTHORIZED"
        assert "Missing authentication token" in exc_info.value.detail["error"]["message"]

    async def test_expired_token_raises_401(
        self, expired_token: str, test_settings: Settings
    ) -> None:
        """Test that expired token returns 401 with TOKEN_EXPIRED code."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=expired_token
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, test_settings)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "TOKEN_EXPIRED"

    async def test_invalid_signature_raises_401(
        self, invalid_signature_token: str, test_settings: Settings
    ) -> None:
        """Test that token with invalid signature returns 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=invalid_signature_token
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, test_settings)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    async def test_invalid_audience_raises_401(
        self, invalid_audience_token: str, test_settings: Settings
    ) -> None:
        """Test that token with wrong audience returns 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=invalid_audience_token
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, test_settings)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    async def test_malformed_token_raises_401(self, test_settings: Settings) -> None:
        """Test that malformed token returns 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="not-a-valid-jwt-token"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, test_settings)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    async def test_missing_jwt_secret_raises_401(self, valid_token: str) -> None:
        """Test that missing JWT secret returns 401 (treated as invalid token)."""
        settings = MagicMock(spec=Settings)
        settings.supabase_jwt_secret = ""
        settings.supabase_url = "https://test.supabase.co"

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_token
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, settings)

        # Missing secret causes decode failure, treated as invalid token
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"]["code"] == "INVALID_TOKEN"

    async def test_token_without_email_still_works(
        self, test_settings: Settings
    ) -> None:
        """Test that token without email claim still returns valid user."""
        payload = {
            "sub": "test-user-id",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        user = await get_current_user(credentials, test_settings)

        assert user.id == "test-user-id"
        assert user.email is None
        assert user.role == "authenticated"  # Default role


class TestGetOptionalUser:
    """Tests for get_optional_user dependency."""

    async def test_valid_token_returns_user(
        self, valid_token: str, test_settings: Settings
    ) -> None:
        """Test that valid token returns user."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_token
        )

        user = await get_optional_user(credentials, test_settings)

        assert isinstance(user, AuthenticatedUser)
        assert user.id == "test-user-id-12345"

    async def test_missing_token_returns_none(self, test_settings: Settings) -> None:
        """Test that missing token returns None (not exception)."""
        user = await get_optional_user(None, test_settings)

        assert user is None

    async def test_invalid_token_returns_none(
        self, expired_token: str, test_settings: Settings
    ) -> None:
        """Test that invalid token returns None (not exception)."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=expired_token
        )

        user = await get_optional_user(credentials, test_settings)

        assert user is None
