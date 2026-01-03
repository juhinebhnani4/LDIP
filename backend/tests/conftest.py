"""Pytest configuration and shared fixtures."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client.

    Yields:
        Configured AsyncClient for testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def mock_user() -> dict[str, Any]:
    """Create a mock authenticated user.

    Returns:
        Mock user dictionary.
    """
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "role": "user",
    }


@pytest.fixture
def mock_matter_id() -> str:
    """Create a mock matter ID.

    Returns:
        Mock matter UUID.
    """
    return "test-matter-id-12345"
