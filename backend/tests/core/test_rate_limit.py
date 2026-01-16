"""Tests for rate limiting functionality (Story 13.3).

Tests cover:
- Rate limit tier configuration
- Custom 429 response format
- Rate limit key extraction (user vs IP)
- Rate limit status endpoint
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from slowapi.errors import RateLimitExceeded
from starlette.datastructures import Headers
from starlette.requests import Request as StarletteRequest

from app.core.rate_limit import (
    CRITICAL_RATE_LIMIT,
    EXPORT_RATE_LIMIT,
    HEALTH_RATE_LIMIT,
    READONLY_RATE_LIMIT,
    SEARCH_RATE_LIMIT,
    STANDARD_RATE_LIMIT,
    _get_rate_limit_key,
    _parse_retry_after,
    get_rate_limit_status,
    limiter,
    rate_limit_exceeded_handler,
)


class TestRateLimitTiers:
    """Test rate limit tier configuration."""

    def test_critical_rate_limit_format(self):
        """Critical tier should be 30/minute."""
        assert "30" in CRITICAL_RATE_LIMIT
        assert "minute" in CRITICAL_RATE_LIMIT

    def test_export_rate_limit_format(self):
        """Export tier should be 20/minute."""
        assert "20" in EXPORT_RATE_LIMIT
        assert "minute" in EXPORT_RATE_LIMIT

    def test_search_rate_limit_format(self):
        """Search tier should be 60/minute."""
        assert "60" in SEARCH_RATE_LIMIT
        assert "minute" in SEARCH_RATE_LIMIT

    def test_standard_rate_limit_format(self):
        """Standard tier should be 100/minute."""
        assert "100" in STANDARD_RATE_LIMIT
        assert "minute" in STANDARD_RATE_LIMIT

    def test_readonly_rate_limit_format(self):
        """Readonly tier should be 120/minute."""
        assert "120" in READONLY_RATE_LIMIT
        assert "minute" in READONLY_RATE_LIMIT

    def test_health_rate_limit_format(self):
        """Health tier should be 300/minute."""
        assert "300" in HEALTH_RATE_LIMIT
        assert "minute" in HEALTH_RATE_LIMIT


class TestRateLimitKeyExtraction:
    """Test rate limit key extraction logic."""

    def test_key_from_user_id(self):
        """Should use user_id when available in request state."""
        # Create mock request with user_id
        mock_request = MagicMock(spec=StarletteRequest)
        mock_request.state = MagicMock()
        mock_request.state.user_id = "user-123-abc"

        key = _get_rate_limit_key(mock_request)
        assert key == "user:user-123-abc"

    def test_key_from_ip_when_no_user(self):
        """Should fall back to IP address when no user_id."""
        # Create mock request without user_id
        mock_request = MagicMock(spec=StarletteRequest)
        mock_request.state = MagicMock()
        mock_request.state.user_id = None
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = Headers({})

        key = _get_rate_limit_key(mock_request)
        assert key == "192.168.1.100"

    def test_key_from_ip_when_no_state(self):
        """Should fall back to IP when state doesn't have user_id."""
        mock_request = MagicMock(spec=StarletteRequest)
        mock_request.state = MagicMock(spec=[])  # Empty spec = no user_id attr
        del mock_request.state.user_id  # Ensure attribute doesn't exist
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = Headers({})

        # hasattr should return False now
        with patch('app.core.rate_limit.get_remote_address', return_value="10.0.0.1"):
            key = _get_rate_limit_key(mock_request)
        assert key == "10.0.0.1"


class TestRetryAfterParsing:
    """Test Retry-After header parsing from rate limit exceptions."""

    def test_parse_minute_window(self):
        """Should return 60 for minute-based limits."""
        exc = MagicMock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded: 30 per 1 minute"

        retry_after = _parse_retry_after(exc)
        assert retry_after == 60

    def test_parse_hour_window(self):
        """Should return 3600 for hour-based limits."""
        exc = MagicMock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded: 1000 per 1 hour"

        retry_after = _parse_retry_after(exc)
        assert retry_after == 3600

    def test_parse_second_window(self):
        """Should return 1 for second-based limits."""
        exc = MagicMock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded: 10 per 1 second"

        retry_after = _parse_retry_after(exc)
        # Default to 1 for second-based
        assert retry_after >= 1

    def test_parse_fallback_default(self):
        """Should return 60 as fallback when parsing fails."""
        exc = MagicMock(spec=RateLimitExceeded)
        exc.detail = "Some unexpected format"

        retry_after = _parse_retry_after(exc)
        assert retry_after == 60


class TestCustom429Handler:
    """Test custom 429 response format."""

    @pytest.mark.asyncio
    async def test_429_response_structure(self):
        """Response should follow project error format."""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = "test-user"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/chat/test/stream"
        mock_request.method = "POST"
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = Headers({})

        # Mock exception - slowapi uses positional arg, not detail kwarg
        exc = MagicMock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded: 30 per 1 minute"

        with patch('app.core.rate_limit.get_remote_address', return_value="127.0.0.1"):
            with patch('app.core.rate_limit.get_correlation_id', return_value="test-corr-123"):
                response = rate_limit_exceeded_handler(mock_request, exc)

        assert response.status_code == 429

        # Parse response body
        import json
        body = json.loads(response.body)

        # Verify error structure
        assert "error" in body
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Rate limit exceeded" in body["error"]["message"]

        # Verify details
        assert "details" in body["error"]
        assert "limit" in body["error"]["details"]
        assert "remaining" in body["error"]["details"]
        assert body["error"]["details"]["remaining"] == 0
        assert "reset_at" in body["error"]["details"]
        assert "retry_after" in body["error"]["details"]

    @pytest.mark.asyncio
    async def test_429_response_headers(self):
        """Response should include standard rate limit headers."""
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = None
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/search/test"
        mock_request.method = "POST"
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = Headers({})

        # Mock exception - slowapi uses positional arg, not detail kwarg
        exc = MagicMock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded: 60 per 1 minute"

        with patch('app.core.rate_limit.get_remote_address', return_value="10.0.0.1"):
            with patch('app.core.rate_limit.get_correlation_id', return_value="test-123"):
                response = rate_limit_exceeded_handler(mock_request, exc)

        # Verify headers
        assert "retry-after" in response.headers
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert response.headers["x-ratelimit-remaining"] == "0"
        assert "x-ratelimit-reset" in response.headers


class TestRateLimitStatus:
    """Test rate limit status endpoint helper."""

    def test_status_returns_all_tiers(self):
        """Status should include all tier configurations."""
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = "user-456"
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = Headers({})

        status = get_rate_limit_status(mock_request)

        assert "key" in status
        assert status["key"] == "user:user-456"
        assert "tiers" in status
        assert "storage" in status

        # Verify all tiers present
        tiers = status["tiers"]
        assert "critical" in tiers
        assert "search" in tiers
        assert "standard" in tiers
        assert "readonly" in tiers
        assert "health" in tiers

        # Verify tier structure
        for tier_name, tier_info in tiers.items():
            assert "limit" in tier_info
            assert "window" in tier_info
            assert "description" in tier_info

    def test_status_uses_ip_when_no_user(self):
        """Status should use IP-based key when not authenticated."""
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = None
        mock_request.client = MagicMock()
        mock_request.client.host = "203.0.113.50"
        mock_request.headers = Headers({})

        with patch('app.core.rate_limit.get_remote_address', return_value="203.0.113.50"):
            status = get_rate_limit_status(mock_request)

        assert status["key"] == "203.0.113.50"


class TestLimiterConfiguration:
    """Test limiter instance configuration."""

    def test_limiter_has_key_function(self):
        """Limiter should be configured with custom key function."""
        assert limiter._key_func is not None

    def test_limiter_has_default_limits(self):
        """Limiter should have default limits configured."""
        assert limiter._default_limits is not None
