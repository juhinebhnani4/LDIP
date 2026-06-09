"""Self-verification for the INF-014 ② network wall (conftest ``_block_external_network``).

Why this exists (2026-06-09):
    The wall originally patched only httpx. But the app reaches the network
    through four DISTINCT transport families, and three of them (aiohttp, grpc,
    raw sockets) slipped past an httpx-only wall — so the "broken Gemini mock"
    tests reached the REAL Gemini API in CI (async google-genai uses aiohttp,
    not httpx), and Document AI reached real Google over grpc. A wall you can't
    prove is a wall you don't have. These tests run UNDER the autouse wall and
    assert each transport family is blocked, and that loopback (the test
    Redis/Celery broker) is NOT — so a future edit that weakens any layer turns
    this file red instead of letting real network calls leak back in silently.
"""

import socket

import httpx
import pytest


def test_httpx_sync_egress_blocked() -> None:
    with pytest.raises(RuntimeError, match="INF-014 wall"):
        httpx.Client().get("http://example.com")


@pytest.mark.asyncio
async def test_httpx_async_egress_blocked() -> None:
    with pytest.raises(RuntimeError, match="INF-014 wall"):
        async with httpx.AsyncClient() as ac:
            await ac.get("http://example.com")


@pytest.mark.asyncio
async def test_aiohttp_egress_blocked() -> None:
    """google-genai's async path uses aiohttp — the leak that motivated this."""
    aiohttp = pytest.importorskip("aiohttp")
    with pytest.raises(RuntimeError, match="INF-014 wall"):
        async with aiohttp.ClientSession() as session:
            await session.get("http://example.com")


def test_grpc_channel_blocked() -> None:
    """Document AI uses grpc; its C-core I/O can only be stopped at channel creation."""
    grpc = pytest.importorskip("grpc")
    with pytest.raises(RuntimeError, match="INF-014 wall"):
        grpc.insecure_channel("example.com:443")
    with pytest.raises(RuntimeError, match="INF-014 wall"):
        grpc.secure_channel("example.com:443", grpc.ssl_channel_credentials())


def test_socket_nonloopback_egress_blocked() -> None:
    """Backstop for requests/urllib/raw sockets. Literal IP avoids any DNS call."""
    with pytest.raises(RuntimeError, match="INF-014 wall"):
        socket.create_connection(("8.8.8.8", 53), timeout=5)


def test_loopback_is_allowed() -> None:
    """The wall must NOT block loopback — the test Redis/Celery broker lives here.

    Connecting to a closed loopback port should surface a normal OSError
    (connection refused/timeout), proving the guard passed it through to the
    real ``connect`` rather than raising the wall's RuntimeError.
    """
    try:
        conn = socket.create_connection(("127.0.0.1", 9), timeout=2)
        conn.close()  # something happened to be listening — also fine (not blocked)
    except (
        RuntimeError
    ) as exc:  # pragma: no cover - this is the failure we guard against
        pytest.fail(f"loopback wrongly blocked by the wall: {exc}")
    except OSError:
        pass  # connection refused/timeout = guard correctly allowed loopback through
