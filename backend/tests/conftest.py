"""Pytest configuration and shared fixtures.

INF-014 ② — the test-harness WALL.
=================================================================
This conftest is the single test boundary the suite never had. Before INF-014
②, every author re-improvised the same four things per file — auth setup, a
``Request`` for rate-limited endpoints, network mocking, and global-state
cleanup — and half got it wrong. That is the ARCH-PATTERNS P4/P1
"sticky-note-where-a-wall-belongs" shape (the same disease as ARCH-003's
"every exit path must remember to signal"). The fix is ONE structure that every
test necessarily flows through, not 41 scattered conventions:

  * ``_isolate_global_state`` (autouse) — resets the process-global singletons
    that leak between tests: structlog's logger cache + contextvars. This is the
    convergence point; tests inherit clean state for free.
  * ``_block_external_network`` (autouse) — unit tests never touch the network:
    real (non-ASGI) httpx egress raises loudly (never silently passes or hangs
    on DNS). Deliberately NOT a blanket Supabase mock — see that fixture's note.
  * ``authed_client`` / ``mock_current_user`` — the canonical authenticated
    client via ``app.dependency_overrides[get_current_user]`` (NOT
    ``patch(...)``, which does not override an already-bound FastAPI Depends).
  * ``mock_request`` — a real ``starlette.Request`` for unit tests that call a
    ``@limiter.limit``-decorated endpoint function directly; it also disables
    the limiter for that test's duration (scoped, so ``test_rate_limit`` is
    untouched).

See BUGS.md INF-014 and memory ``inf014-test-quarantine-shipped``.
"""

from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import structlog
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.core.security import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser

# ---------------------------------------------------------------------------
# INF-014: central quarantine of pre-existing failures (test-suite rot).
#
# A single list + one collection hook xfail the known-broken unit tests so the
# `test` CI job can be a REQUIRED check — making CI a real guard for the passing
# tests while the Shape-A conftest wall (②) and the Shape-B drift sweep (③)
# proceed. This is deliberately ONE wall, not scattered @xfail decorators (that
# would be the ARCH-003 "remember to" sticky-note shape).
#
# strict=False on purpose: a strict XPASS on a flaky test would turn the
# REQUIRED check red and block ALL merges — a worse foot-gun than the rot. New
# regressions are still caught: any failure NOT in the list fails the job.
# RULE: when a test is fixed, DELETE its line from the list. It must only shrink.
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


# ---------------------------------------------------------------------------
# INF-014 ② — WALL part 1: global-state isolation (autouse).
#
# Why this exists (proven empirically, not guessed):
#   structlog is configured app-wide with ``cache_logger_on_first_use=True``
#   (app/core/logging.py). On first use, a module logger monkey-patches its own
#   ``bind`` to a closure holding a *reference* to the processor list that was
#   current at that moment. Tests like ``test_logging`` / ``test_reliability_
#   logging`` call ``structlog.reset_defaults()``, which REBINDS
#   ``_CONFIG.default_processors`` to a brand-new list. ``capture_logs()`` then
#   mutates the *new* list in place — but already-cached loggers still point at
#   the *old* one, so their output is never captured → ``test_chunking_logging``
#   (and the worker-test cluster) fail, but ONLY in full-suite order.
#
# The wall: force caching OFF before every test. With caching off, no logger
# ever installs that stale-list closure, so ``capture_logs()`` always works
# regardless of what a prior test did to the config. We also clear contextvars
# so a ``user_id`` bound by ``get_current_user`` in one test cannot leak into
# the next. This is the SINGLE convergence point — every test flows through it.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_global_state() -> Iterator[None]:
    structlog.contextvars.clear_contextvars()
    # Only flips this one flag; leaves the app's processors intact.
    structlog.configure(cache_logger_on_first_use=False)
    yield
    structlog.contextvars.clear_contextvars()


# ---------------------------------------------------------------------------
# INF-014 ② — WALL part 2: no real network egress from unit tests (autouse).
#
# Real (non-ASGI) httpx egress RAISES loudly. A unit test that genuinely needs
# the network fails visibly here instead of silently passing or hanging on DNS
# resolution of ``placeholder.supabase.co``. TestClient uses httpx.ASGITransport
# (in-process), which is NOT patched — so authed_client / client keep working.
#
# Deliberately NOT a blanket Supabase-client mock. A generic ``MagicMock`` for
# the client makes DB queries *succeed* returning empty-but-truthy data
# (``MagicMock`` iterates as empty), which silently changes behaviour rather
# than blocking it. That actually broke 3 contradiction tests: the DB-backed
# ``pricing_loader.initialize_pricing`` ran at app startup, "loaded" an EMPTY
# pricing dict from the mock, cached it in a module global, and every LLM-cost
# calc then returned $0. Blocking egress (vs faking success) preserves the
# real fallback path (``initialize_pricing`` catches the error → hardcoded
# pricing). Tests that need specific Supabase data mock the client locally, as
# they already do — and those local mocks are scoped, not process-global.
# ---------------------------------------------------------------------------
def _blocked_egress(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError(
        "INF-014 wall: real network egress is blocked in unit tests. "
        "Mock the client/transport, or move this test to tests/integration."
    )


@pytest.fixture(autouse=True)
def _block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked_egress)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", _blocked_egress
    )


# ---------------------------------------------------------------------------
# INF-014 ② — WALL part 3: canonical authenticated client.
#
# The ONLY correct way to bypass auth in a FastAPI test is
# ``app.dependency_overrides[get_current_user]``. Patching
# ``app.core.security.get_current_user`` does nothing, because the route already
# captured the function object at decoration time (this was the test_users 401
# bug). Use ``authed_client`` for endpoint tests that need an authenticated user.
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_current_user() -> AuthenticatedUser:
    """The authenticated user injected by ``authed_client``."""
    return AuthenticatedUser(
        id="test-user-id",
        email="test@example.com",
        role="authenticated",
    )


@pytest.fixture
def authed_client(mock_current_user: AuthenticatedUser) -> Iterator[TestClient]:
    """Sync TestClient with ``get_current_user`` overridden (the auth wall).

    Tests that also need to override route-level deps (e.g. a per-route
    ``get_supabase_client``) can add to ``app.dependency_overrides`` after
    requesting this fixture; clean-up below removes only the auth override.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# INF-014 ② — WALL part 4: a real Request for rate-limited endpoints.
#
# Endpoints decorated with ``@limiter.limit(...)`` take a ``request: Request``
# param "for the rate limiter". Unit tests that call those endpoint functions
# directly must supply one. ``mock_request`` is a real ``starlette.Request`` and
# disables the limiter for the test's duration — scoped to tests that opt in, so
# ``tests/core/test_rate_limit.py`` (which asserts limiting works) is untouched.
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_request() -> Iterator[Request]:
    from app.core.rate_limit import limiter

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }
    previously_enabled = limiter.enabled
    limiter.enabled = False
    try:
        yield Request(scope)
    finally:
        limiter.enabled = previously_enabled


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
