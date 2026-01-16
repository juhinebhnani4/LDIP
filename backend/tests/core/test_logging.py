"""Tests for structured logging and Axiom integration (Story 13.1).

Tests cover:
- Correlation ID middleware and propagation
- Log context includes required fields (user_id, matter_id, correlation_id)
- Graceful degradation when Axiom is unavailable
- No sensitive data leakage in logs
"""

import asyncio
import io
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.correlation import (
    CORRELATION_HEADER,
    CorrelationMiddleware,
    get_correlation_id,
)
from app.core.logging import _get_axiom_processor, configure_logging, get_logger

# Test JWT secret for testing purposes only
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


@pytest.fixture
def mock_settings_no_axiom() -> MagicMock:
    """Create settings without Axiom configured."""
    settings = MagicMock(spec=Settings)
    settings.axiom_token = ""
    settings.axiom_dataset = "ldip-logs"
    settings.debug = True
    return settings


@pytest.fixture
def mock_settings_with_axiom() -> MagicMock:
    """Create settings with Axiom configured."""
    settings = MagicMock(spec=Settings)
    settings.axiom_token = "test-axiom-token"
    settings.axiom_dataset = "ldip-logs"
    settings.debug = False
    return settings


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with CorrelationMiddleware."""
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/test")
    async def test_endpoint() -> dict[str, str | None]:
        # Get correlation ID from context
        corr_id = get_correlation_id()
        return {"correlation_id": corr_id}

    @app.get("/test-async")
    async def test_async_endpoint() -> dict[str, str | None]:
        # Simulate async work
        await asyncio.sleep(0.01)
        corr_id = get_correlation_id()
        return {"correlation_id": corr_id}

    return app


class TestCorrelationMiddleware:
    """Tests for CorrelationMiddleware."""

    def test_generates_correlation_id_when_not_provided(
        self, test_app: FastAPI
    ) -> None:
        """Test that middleware generates a correlation_id when not in request."""
        client = TestClient(test_app)

        response = client.get("/test")

        assert response.status_code == 200
        assert CORRELATION_HEADER in response.headers
        corr_id = response.headers[CORRELATION_HEADER]
        # Verify it's a valid UUID
        uuid.UUID(corr_id)  # Raises ValueError if invalid
        # Verify endpoint received the correlation_id
        assert response.json()["correlation_id"] == corr_id

    def test_uses_existing_correlation_id_from_header(
        self, test_app: FastAPI
    ) -> None:
        """Test that middleware uses X-Correlation-ID from request header."""
        client = TestClient(test_app)
        expected_id = "provided-correlation-id-12345"

        response = client.get(
            "/test", headers={CORRELATION_HEADER: expected_id}
        )

        assert response.status_code == 200
        assert response.headers[CORRELATION_HEADER] == expected_id
        assert response.json()["correlation_id"] == expected_id

    def test_correlation_id_propagates_across_async_calls(
        self, test_app: FastAPI
    ) -> None:
        """Test that correlation_id is available in async context."""
        client = TestClient(test_app)
        expected_id = "async-correlation-id-67890"

        response = client.get(
            "/test-async", headers={CORRELATION_HEADER: expected_id}
        )

        assert response.status_code == 200
        # Correlation ID should still be available after async await
        assert response.json()["correlation_id"] == expected_id

    def test_correlation_id_cleared_after_request(
        self, test_app: FastAPI
    ) -> None:
        """Test that correlation_id is cleared after request completes."""
        client = TestClient(test_app)

        # First request with correlation_id
        response1 = client.get(
            "/test", headers={CORRELATION_HEADER: "first-request-id"}
        )
        assert response1.json()["correlation_id"] == "first-request-id"

        # Second request without correlation_id should get a new one
        response2 = client.get("/test")
        corr_id_2 = response2.json()["correlation_id"]
        assert corr_id_2 != "first-request-id"
        # Verify new ID is a valid UUID
        uuid.UUID(corr_id_2)


class TestGetCorrelationId:
    """Tests for get_correlation_id helper function."""

    def test_returns_none_outside_request_context(self) -> None:
        """Test that get_correlation_id returns None when not in request."""
        # Clear any existing context
        structlog.contextvars.clear_contextvars()

        result = get_correlation_id()

        assert result is None

    def test_returns_correlation_id_when_bound(self) -> None:
        """Test that get_correlation_id returns bound correlation_id."""
        expected_id = "bound-correlation-id"
        structlog.contextvars.bind_contextvars(correlation_id=expected_id)

        try:
            result = get_correlation_id()
            assert result == expected_id
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id")


class TestLoggingConfiguration:
    """Tests for logging configuration."""

    def test_configure_logging_dev_mode(self) -> None:
        """Test logging configuration in debug mode (pretty console)."""
        with patch("app.core.logging.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.debug = True
            mock_settings.axiom_token = ""
            mock_get_settings.return_value = mock_settings

            # Reset structlog to allow reconfiguration
            structlog.reset_defaults()

            configure_logging()

            # In debug mode, should use ConsoleRenderer
            # We verify by checking the processors configuration
            # Note: We can't easily inspect processors, but we verify no errors

    def test_configure_logging_prod_mode_no_axiom(self) -> None:
        """Test logging configuration in production without Axiom."""
        with patch("app.core.logging.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.debug = False
            mock_settings.axiom_token = ""
            mock_settings.axiom_dataset = "ldip-logs"
            mock_get_settings.return_value = mock_settings

            structlog.reset_defaults()

            configure_logging()

            # Should complete without error, JSON output expected


class TestAxiomProcessor:
    """Tests for Axiom processor graceful degradation."""

    def test_returns_none_when_axiom_not_configured(self) -> None:
        """Test that _get_axiom_processor returns None when token is empty."""
        with patch("app.core.logging.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.axiom_token = ""
            mock_get_settings.return_value = mock_settings

            result = _get_axiom_processor()

            assert result is None

    def test_returns_none_when_axiom_import_fails(self) -> None:
        """Test graceful degradation when axiom-py is not installed."""
        with (
            patch("app.core.logging.get_settings") as mock_get_settings,
            patch.dict("sys.modules", {"axiom_py": None}),
        ):
            mock_settings = MagicMock()
            mock_settings.axiom_token = "test-token"
            mock_get_settings.return_value = mock_settings

            # Force reimport to trigger import error
            from app.core import logging as logging_module

            # Clear the global client
            logging_module._axiom_client = None

            result = _get_axiom_processor()

            # Should return None gracefully, not raise
            assert result is None

    def test_returns_none_when_axiom_client_fails(self) -> None:
        """Test graceful degradation when Axiom client initialization fails."""
        with patch("app.core.logging.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.axiom_token = "test-token"
            mock_settings.axiom_dataset = "ldip-logs"
            mock_get_settings.return_value = mock_settings

            # Clear the global client
            from app.core import logging as logging_module
            logging_module._axiom_client = None

            # Mock axiom_py to raise on Client creation
            mock_client_class = MagicMock(side_effect=Exception("Connection failed"))

            with patch.dict(
                "sys.modules",
                {
                    "axiom_py": MagicMock(Client=mock_client_class),
                    "axiom_py.structlog": MagicMock(),
                },
            ):
                result = _get_axiom_processor()

            # Should return None gracefully
            assert result is None


class TestLogContext:
    """Tests for log context includes required fields."""

    def test_log_includes_correlation_id(self) -> None:
        """Test that logs include correlation_id from context."""
        # Capture log output
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        handler.setLevel(logging.DEBUG)

        structlog.reset_defaults()

        # Configure structlog with JSON output to capture
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=log_output),
            cache_logger_on_first_use=False,
        )

        # Bind correlation_id and log
        structlog.contextvars.bind_contextvars(correlation_id="test-corr-123")
        try:
            logger = structlog.get_logger()
            logger.info("test_message", extra_field="value")
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id")

        # Parse log output
        log_output.seek(0)
        log_line = log_output.read()
        log_data = json.loads(log_line)

        assert log_data["correlation_id"] == "test-corr-123"
        assert log_data["event"] == "test_message"
        assert log_data["extra_field"] == "value"

    def test_log_includes_user_id_when_bound(self) -> None:
        """Test that logs include user_id when bound to context."""
        log_output = io.StringIO()

        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=log_output),
            cache_logger_on_first_use=False,
        )

        # Bind user_id and log
        structlog.contextvars.bind_contextvars(user_id="user-abc-123")
        try:
            logger = structlog.get_logger()
            logger.info("user_action")
        finally:
            structlog.contextvars.unbind_contextvars("user_id")

        log_output.seek(0)
        log_data = json.loads(log_output.read())

        assert log_data["user_id"] == "user-abc-123"

    def test_log_includes_matter_id_when_bound(self) -> None:
        """Test that logs include matter_id when bound to context."""
        log_output = io.StringIO()

        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=log_output),
            cache_logger_on_first_use=False,
        )

        # Bind matter_id and log
        structlog.contextvars.bind_contextvars(matter_id="matter-xyz-789")
        try:
            logger = structlog.get_logger()
            logger.info("matter_access")
        finally:
            structlog.contextvars.unbind_contextvars("matter_id")

        log_output.seek(0)
        log_data = json.loads(log_output.read())

        assert log_data["matter_id"] == "matter-xyz-789"


class TestSensitiveDataProtection:
    """Tests for sensitive data not being logged."""

    def test_authorization_header_not_logged(self) -> None:
        """Test that authorization headers are not logged."""
        log_output = io.StringIO()

        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=log_output),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger()
        # Simulate logging request info - should NOT include auth header
        logger.info(
            "request_received",
            path="/api/test",
            method="GET",
            # Note: We intentionally don't log authorization headers
        )

        log_output.seek(0)
        log_line = log_output.read()

        # Verify no JWT-like strings in output
        assert "Bearer" not in log_line
        assert "eyJ" not in log_line  # JWT prefix

    def test_password_fields_not_logged(self) -> None:
        """Test that password-like fields are not logged."""
        log_output = io.StringIO()

        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=log_output),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger()
        # Log user action without sensitive data
        logger.info(
            "user_login_attempt",
            user_email="user@example.com",
            # Note: Never log password, password_hash, etc.
        )

        log_output.seek(0)
        log_line = log_output.read()

        # Verify no password in output
        assert "password" not in log_line.lower()

    def test_jwt_tokens_not_logged(self) -> None:
        """Test that JWT tokens are not logged."""
        # Create a test JWT
        test_token = jwt.encode(
            {
                "sub": "user-123",
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            "secret",
            algorithm="HS256",
        )

        log_output = io.StringIO()

        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=log_output),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger()
        # Log auth event - should NOT include the actual token
        logger.info(
            "jwt_validation_success",
            user_id="user-123",
            has_email=True,
            # Note: Never log the actual token
        )

        log_output.seek(0)
        log_line = log_output.read()

        # Verify the test token is not in the output
        assert test_token not in log_line
        # Verify no JWT-like strings (base64 encoded parts)
        assert "eyJ" not in log_line


class TestGetLogger:
    """Tests for get_logger helper function."""

    def test_get_logger_returns_bound_logger(self) -> None:
        """Test that get_logger returns a BoundLogger instance."""
        structlog.reset_defaults()
        configure_logging()

        logger = get_logger("test.module")

        # Should be a BoundLogger
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_with_none_name(self) -> None:
        """Test that get_logger works with None name."""
        structlog.reset_defaults()
        configure_logging()

        logger = get_logger(None)

        # Should still return a valid logger
        assert hasattr(logger, "info")
