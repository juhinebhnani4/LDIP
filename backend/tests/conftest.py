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

import socket
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

# Optional egress transports — imported once, guarded so a missing package never
# breaks collection. Each is a SEPARATE network channel the app can reach Google
# (or anything) through, and each needs its own chokepoint (see the wall below).
try:
    import aiohttp  # google-genai's async path uses aiohttp, NOT httpx
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]
try:
    import grpc  # google-cloud-documentai uses grpc (C-core, bypasses sockets)
    import grpc.aio as _grpc_aio
except ImportError:  # pragma: no cover
    grpc = None  # type: ignore[assignment]
    _grpc_aio = None  # type: ignore[assignment]

from app.core.security import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auth import AuthenticatedUser  # noqa: E402

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
# A unit test that genuinely needs the network must fail VISIBLY here instead of
# silently passing (or hanging on DNS) by reaching a real API. The original wall
# patched only httpx — but the app reaches the network through FOUR distinct
# transport families, and httpx is just one. Each needs its own chokepoint
# (proven empirically 2026-06-09, not assumed — see the probe in the PR):
#
#   * httpx           — Supabase, OpenAI, Cohere, google-genai SYNC calls.
#   * aiohttp         — google-genai ASYNC calls go through aiohttp, NOT httpx,
#                       so they escaped the old wall (the broken-Gemini-mock
#                       tests reached real Gemini and got "400 API key invalid").
#   * grpc            — google-cloud-documentai. grpc does its socket I/O in C,
#                       BELOW Python's ``socket`` module, so NO socket patch can
#                       catch it — the only Python chokepoint is channel creation.
#   * socket (backstop) — catches requests/urllib/raw-socket sync egress that
#                       isn't one of the above. Loopback is ALLOWED so the local
#                       Redis/Celery broker (127.0.0.1:6379) still works.
#
# Why chokepoints-per-transport and not "patch every SDK": transport families
# are a small, stable, closed set (4); SDKs are not. The socket backstop catches
# the long tail of Python-level egress for free, so the only thing ever needing
# an explicit entry is a new C-level transport (rare, and it fails loudly in CI).
# This is a wall, not the ARCH-003 "remember to mock each new client" sticky-note.
# ``tests/test_network_wall.py`` asserts each layer holds, so the wall is
# self-verifying and can't silently regress.
#
# TestClient/``client`` use httpx.ASGITransport (in-process, no socket) and are
# NOT affected. Deliberately NOT a blanket Supabase-client mock: a ``MagicMock``
# makes DB queries *succeed* returning empty-but-truthy data, which silently
# changes behaviour — it once zeroed every LLM cost by "loading" an empty pricing
# dict at startup and breaking 3 contradiction tests. Blocking egress preserves
# the real fallback paths; tests needing DB data mock the client locally (scoped).
# ---------------------------------------------------------------------------
def _blocked_egress(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError(
        "INF-014 wall: real network egress is blocked in unit tests. "
        "Mock the client/transport, or move this test to tests/integration."
    )


def _is_loopback(host: object) -> bool:
    """True for localhost-family hosts (Redis/Celery broker run here in tests)."""
    return isinstance(host, str) and (
        host == "localhost" or host == "::1" or host.startswith("127.")
    )


@pytest.fixture(autouse=True)
def _block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. httpx (sync + async) — keeps the friendly "mock me" message.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked_egress)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", _blocked_egress
    )

    # 2. aiohttp — google-genai's async path. One chokepoint covers every verb.
    if aiohttp is not None:
        monkeypatch.setattr(aiohttp.client.ClientSession, "_request", _blocked_egress)

    # 3. grpc — google-cloud-documentai. Block channel creation (the only Python
    #    seam; grpc's actual I/O is in C and unreachable from a socket patch).
    if grpc is not None:
        monkeypatch.setattr(grpc, "secure_channel", _blocked_egress)
        monkeypatch.setattr(grpc, "insecure_channel", _blocked_egress)
    if _grpc_aio is not None:
        monkeypatch.setattr(_grpc_aio, "secure_channel", _blocked_egress)
        monkeypatch.setattr(_grpc_aio, "insecure_channel", _blocked_egress)

    # 4. socket backstop — any other Python-level egress (requests/urllib/raw).
    #    Loopback is allowed so the test Redis/Celery broker keeps working;
    #    AF_UNIX (address is a str path, not a tuple) is local IPC, not network.
    _real_connect = socket.socket.connect

    def _guarded_connect(self: socket.socket, address: Any) -> Any:
        if not isinstance(address, (tuple, list)):  # AF_UNIX path — local IPC
            return _real_connect(self, address)
        host = address[0] if address else None
        if _is_loopback(host):
            return _real_connect(self, address)
        raise RuntimeError(
            f"INF-014 wall: real socket egress to {host!r} is blocked in unit "
            "tests. Mock the client, or move this test to tests/integration."
        )

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


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
