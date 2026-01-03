"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test basic health check endpoint returns healthy status."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "healthy"
    assert data["data"]["service"] == "ldip-backend"


@pytest.mark.asyncio
async def test_liveness_check(client: AsyncClient) -> None:
    """Test liveness check endpoint returns alive status."""
    response = await client.get("/api/health/live")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_check(client: AsyncClient) -> None:
    """Test readiness check endpoint returns status with checks."""
    response = await client.get("/api/health/ready")

    assert response.status_code == 200
    data = response.json()
    # Without Supabase configured, should show not_ready
    assert "status" in data["data"]
    assert "checks" in data["data"]
    assert "supabase_configured" in data["data"]["checks"]


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Test root endpoint returns welcome message."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "LDIP" in data["message"]
    assert "health" in data
