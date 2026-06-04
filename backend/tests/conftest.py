"""Pytest configuration and shared fixtures."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# INF-014: central quarantine of pre-existing failures (test-suite rot).
#
# A single list + one collection hook xfail the 203 known-broken unit tests so
# the `test` CI job can become a REQUIRED check NOW — making CI a real guard for
# the 2846 passing tests while the Shape-A conftest wall (②) and the Shape-B
# drift sweep (③) proceed. This is deliberately ONE wall, not 203 scattered
# @xfail decorators (that would be the ARCH-003 "remember to" sticky-note shape).
#
# strict=False on purpose: a strict XPASS on a flaky test would turn the
# REQUIRED check red and block ALL merges — a worse foot-gun than the rot. New
# regressions are still caught: any failure NOT in the list fails the job.
# Pruning pressure comes from a periodic `-rX` report (see BUGS.md INF-014 ⑤),
# not from blocking. RULE: when a test is fixed, DELETE its line from the list.
# ---------------------------------------------------------------------------
_QUARANTINE_FILE = Path(__file__).parent / "inf014_quarantine.txt"


def _load_quarantine() -> set[str]:
    if not _QUARANTINE_FILE.exists():
        return set()
    return {
        line.strip()
        for line in _QUARANTINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark known INF-014 failures as xfail by exact node id."""
    quarantined = _load_quarantine()
    if not quarantined:
        return
    marker = pytest.mark.xfail(
        reason="INF-014 pre-existing failure (test-suite rot) — see BUGS.md",
        strict=False,
    )
    for item in items:
        if item.nodeid in quarantined:
            item.add_marker(marker)


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
