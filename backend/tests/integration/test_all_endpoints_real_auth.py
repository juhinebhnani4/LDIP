"""
Comprehensive API Endpoint Testing with Real Supabase Authentication.

This script tests ALL API endpoints with actual authentication tokens
from Supabase, not mocked data.

Usage:
    # Set test user credentials in environment or .env.test
    export TEST_USER_EMAIL="your-test@email.com"
    export TEST_USER_PASSWORD="your-password"

    # Run all tests
    pytest tests/integration/test_all_endpoints_real_auth.py -v

    # Run specific test class
    pytest tests/integration/test_all_endpoints_real_auth.py::TestHealthEndpoints -v

    # Run with report
    pytest tests/integration/test_all_endpoints_real_auth.py -v --tb=short --json-report
"""

import os
import json
import time
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field

import pytest
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD")


@dataclass
class TestResult:
    """Result of a single endpoint test."""
    endpoint: str
    method: str
    status_code: int
    success: bool
    response_time_ms: float
    error: str | None = None
    response_data: dict | None = None


@dataclass
class TestReport:
    """Aggregated test report."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[TestResult] = field(default_factory=list)

    def add_result(self, result: TestResult):
        self.results.append(result)
        self.total += 1
        if result.success:
            self.passed += 1
        else:
            self.failed += 1

    def summary(self) -> str:
        return f"Total: {self.total} | Passed: {self.passed} | Failed: {self.failed} | Skipped: {self.skipped}"


class SupabaseAuthClient:
    """Handle real Supabase authentication."""

    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self._access_token: str | None = None
        self._user_id: str | None = None

    def sign_in(self, email: str, password: str) -> str:
        """Sign in with email/password and return access token."""
        response = httpx.post(
            f"{self.url}/auth/v1/token?grant_type=password",
            headers={
                "apikey": self.key,
                "Content-Type": "application/json"
            },
            json={
                "email": email,
                "password": password
            }
        )

        if response.status_code != 200:
            raise Exception(f"Auth failed: {response.status_code} - {response.text}")

        data = response.json()
        self._access_token = data["access_token"]
        self._user_id = data["user"]["id"]
        return self._access_token

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def user_id(self) -> str | None:
        return self._user_id


class APITestClient:
    """HTTP client for testing API endpoints with real auth."""

    def __init__(self, base_url: str, auth_token: str | None = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self._client = httpx.Client(timeout=30.0)

    def _headers(self, authenticated: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if authenticated and self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def get(self, path: str, authenticated: bool = True, **kwargs) -> TestResult:
        return self._request("GET", path, authenticated, **kwargs)

    def post(self, path: str, authenticated: bool = True, **kwargs) -> TestResult:
        return self._request("POST", path, authenticated, **kwargs)

    def patch(self, path: str, authenticated: bool = True, **kwargs) -> TestResult:
        return self._request("PATCH", path, authenticated, **kwargs)

    def put(self, path: str, authenticated: bool = True, **kwargs) -> TestResult:
        return self._request("PUT", path, authenticated, **kwargs)

    def delete(self, path: str, authenticated: bool = True, **kwargs) -> TestResult:
        return self._request("DELETE", path, authenticated, **kwargs)

    def _request(self, method: str, path: str, authenticated: bool = True, **kwargs) -> TestResult:
        url = f"{self.base_url}{path}"
        headers = self._headers(authenticated)

        start_time = time.time()
        try:
            response = self._client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            elapsed_ms = (time.time() - start_time) * 1000

            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text[:500]}

            # Success if 2xx or expected 4xx for validation tests
            success = 200 <= response.status_code < 300

            return TestResult(
                endpoint=path,
                method=method,
                status_code=response.status_code,
                success=success,
                response_time_ms=elapsed_ms,
                response_data=response_data
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return TestResult(
                endpoint=path,
                method=method,
                status_code=0,
                success=False,
                response_time_ms=elapsed_ms,
                error=str(e)
            )


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def supabase_auth():
    """Create and authenticate Supabase client."""
    if not all([SUPABASE_URL, SUPABASE_KEY, TEST_USER_EMAIL, TEST_USER_PASSWORD]):
        pytest.skip("Missing Supabase credentials. Set TEST_USER_EMAIL and TEST_USER_PASSWORD.")

    auth = SupabaseAuthClient(SUPABASE_URL, SUPABASE_KEY)
    auth.sign_in(TEST_USER_EMAIL, TEST_USER_PASSWORD)
    return auth


@pytest.fixture(scope="session")
def api_client(supabase_auth) -> APITestClient:
    """Create authenticated API test client."""
    return APITestClient(API_BASE_URL, supabase_auth.access_token)


@pytest.fixture(scope="session")
def user_id(supabase_auth) -> str:
    """Get the authenticated user's ID."""
    return supabase_auth.user_id


@pytest.fixture(scope="session")
def test_report() -> TestReport:
    """Shared test report for aggregating results."""
    return TestReport()


@pytest.fixture(scope="session")
def test_matter_id(api_client) -> str:
    """Create a test matter and return its ID. Cleanup after session."""
    # Create a test matter
    result = api_client.post(
        "/api/matters",
        json={
            "title": f"API Test Matter - {datetime.now().isoformat()}",
            "description": "Created by automated API tests"
        }
    )

    if not result.success:
        pytest.skip(f"Could not create test matter: {result.error or result.response_data}")

    matter_id = result.response_data["data"]["id"]
    yield matter_id

    # Cleanup: delete the test matter
    api_client.delete(f"/api/matters/{matter_id}")


# ============================================================================
# HEALTH ENDPOINTS (No Auth Required)
# ============================================================================

class TestHealthEndpoints:
    """Test health check endpoints - no authentication required."""

    def test_root_endpoint(self, api_client: APITestClient, test_report: TestReport):
        """GET / - Root welcome endpoint."""
        result = api_client.get("/", authenticated=False)
        test_report.add_result(result)
        assert result.success, f"Root endpoint failed: {result.error or result.response_data}"

    def test_health_check(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/health - Basic health check."""
        result = api_client.get("/api/health", authenticated=False)
        test_report.add_result(result)
        assert result.success, f"Health check failed: {result.error or result.response_data}"
        assert result.response_data["data"]["status"] == "healthy"

    def test_readiness_check(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/health/ready - Readiness probe with dependencies."""
        result = api_client.get("/api/health/ready", authenticated=False)
        test_report.add_result(result)
        assert result.success, f"Readiness check failed: {result.error or result.response_data}"

    def test_liveness_check(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/health/live - Liveness probe."""
        result = api_client.get("/api/health/live", authenticated=False)
        test_report.add_result(result)
        assert result.success, f"Liveness check failed: {result.error or result.response_data}"

    def test_circuits_status(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/health/circuits - Circuit breaker status."""
        result = api_client.get("/api/health/circuits", authenticated=False)
        test_report.add_result(result)
        assert result.success, f"Circuits status failed: {result.error or result.response_data}"


class TestAuthenticatedHealthEndpoints:
    """Test auth-protected health endpoints."""

    def test_authenticated_user_info(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/health/me - Get authenticated user info."""
        result = api_client.get("/api/health/me")
        test_report.add_result(result)
        assert result.success, f"Auth user info failed: {result.error or result.response_data}"
        assert "user_id" in result.response_data.get("data", {})

    def test_rate_limits_status(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/health/rate-limits - Get rate limit configuration."""
        result = api_client.get("/api/health/rate-limits")
        test_report.add_result(result)
        assert result.success, f"Rate limits status failed: {result.error or result.response_data}"


# ============================================================================
# MATTERS ENDPOINTS
# ============================================================================

class TestMattersEndpoints:
    """Test matter CRUD and member management endpoints."""

    def test_list_matters(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/matters - List all accessible matters."""
        result = api_client.get("/api/matters")
        test_report.add_result(result)
        assert result.success, f"List matters failed: {result.error or result.response_data}"
        assert "data" in result.response_data

    def test_create_matter(self, api_client: APITestClient, test_report: TestReport):
        """POST /api/matters - Create a new matter."""
        result = api_client.post(
            "/api/matters",
            json={
                "title": f"Test Matter {datetime.now().isoformat()}",
                "description": "Test matter for API validation"
            }
        )
        test_report.add_result(result)
        assert result.success, f"Create matter failed: {result.error or result.response_data}"

        # Cleanup
        if result.success and result.response_data:
            matter_id = result.response_data.get("data", {}).get("id")
            if matter_id:
                api_client.delete(f"/api/matters/{matter_id}")

    def test_get_matter(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id} - Get matter details."""
        result = api_client.get(f"/api/matters/{test_matter_id}")
        test_report.add_result(result)
        assert result.success, f"Get matter failed: {result.error or result.response_data}"

    def test_update_matter(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """PATCH /api/matters/{id} - Update matter details."""
        result = api_client.patch(
            f"/api/matters/{test_matter_id}",
            json={"description": f"Updated at {datetime.now().isoformat()}"}
        )
        test_report.add_result(result)
        assert result.success, f"Update matter failed: {result.error or result.response_data}"

    def test_get_tab_stats(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/tab-stats - Get workspace tab statistics."""
        result = api_client.get(f"/api/matters/{test_matter_id}/tab-stats")
        test_report.add_result(result)
        assert result.success, f"Tab stats failed: {result.error or result.response_data}"

    def test_list_members(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/members - List matter members."""
        result = api_client.get(f"/api/matters/{test_matter_id}/members")
        test_report.add_result(result)
        assert result.success, f"List members failed: {result.error or result.response_data}"


# ============================================================================
# DOCUMENTS ENDPOINTS
# ============================================================================

class TestDocumentsEndpoints:
    """Test document upload and management endpoints."""

    def test_list_documents(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/documents - List documents in matter."""
        result = api_client.get(f"/api/matters/{test_matter_id}/documents")
        test_report.add_result(result)
        assert result.success, f"List documents failed: {result.error or result.response_data}"

    def test_list_documents_with_filters(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/documents - List with pagination and filters."""
        result = api_client.get(
            f"/api/matters/{test_matter_id}/documents",
            params={"page": 1, "per_page": 10, "status": "completed"}
        )
        test_report.add_result(result)
        assert result.success, f"List documents with filters failed: {result.error or result.response_data}"


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

class TestSearchEndpoints:
    """Test search functionality endpoints."""

    def test_hybrid_search(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """POST /api/matters/{id}/search - Hybrid BM25 + semantic search."""
        result = api_client.post(
            f"/api/matters/{test_matter_id}/search",
            json={"query": "test search query", "limit": 10}
        )
        test_report.add_result(result)
        # May return empty results, but should not error
        assert result.status_code in [200, 404], f"Hybrid search failed: {result.error or result.response_data}"

    def test_bm25_search(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """POST /api/matters/{id}/search/bm25 - BM25-only keyword search."""
        result = api_client.post(
            f"/api/matters/{test_matter_id}/search/bm25",
            json={"query": "test", "limit": 10}
        )
        test_report.add_result(result)
        assert result.status_code in [200, 404], f"BM25 search failed: {result.error or result.response_data}"

    def test_semantic_search(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """POST /api/matters/{id}/search/semantic - Semantic vector search."""
        result = api_client.post(
            f"/api/matters/{test_matter_id}/search/semantic",
            json={"query": "test semantic query", "limit": 10}
        )
        test_report.add_result(result)
        assert result.status_code in [200, 404], f"Semantic search failed: {result.error or result.response_data}"

    def test_rerank_search(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """POST /api/matters/{id}/search/rerank - Hybrid search with Cohere rerank."""
        result = api_client.post(
            f"/api/matters/{test_matter_id}/search/rerank",
            json={"query": "test rerank query", "limit": 10}
        )
        test_report.add_result(result)
        assert result.status_code in [200, 404], f"Rerank search failed: {result.error or result.response_data}"


# ============================================================================
# ENTITIES (MIG) ENDPOINTS
# ============================================================================

class TestEntitiesEndpoints:
    """Test entity management endpoints."""

    def test_list_entities(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/entities - List entities with mention counts."""
        result = api_client.get(f"/api/matters/{test_matter_id}/entities")
        test_report.add_result(result)
        assert result.success, f"List entities failed: {result.error or result.response_data}"

    def test_list_entities_paginated(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/entities - List with pagination."""
        result = api_client.get(
            f"/api/matters/{test_matter_id}/entities",
            params={"page": 1, "per_page": 20}
        )
        test_report.add_result(result)
        assert result.success, f"List entities paginated failed: {result.error or result.response_data}"


# ============================================================================
# CITATIONS ENDPOINTS
# ============================================================================

class TestCitationsEndpoints:
    """Test citation management endpoints."""

    def test_list_citations(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/citations - List citations."""
        result = api_client.get(f"/api/matters/{test_matter_id}/citations")
        test_report.add_result(result)
        assert result.success, f"List citations failed: {result.error or result.response_data}"

    def test_citation_stats(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/citations/stats - Get citation statistics."""
        result = api_client.get(f"/api/matters/{test_matter_id}/citations/stats")
        test_report.add_result(result)
        assert result.success, f"Citation stats failed: {result.error or result.response_data}"

    def test_citation_summary_by_act(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/citations/summary/by-act - Citations grouped by Act."""
        result = api_client.get(f"/api/matters/{test_matter_id}/citations/summary/by-act")
        test_report.add_result(result)
        assert result.success, f"Citation summary failed: {result.error or result.response_data}"

    def test_act_discovery_report(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/citations/acts/discovery - Act Discovery Report."""
        result = api_client.get(f"/api/matters/{test_matter_id}/citations/acts/discovery")
        test_report.add_result(result)
        assert result.success, f"Act discovery failed: {result.error or result.response_data}"


# ============================================================================
# TIMELINE ENDPOINTS
# ============================================================================

class TestTimelineEndpoints:
    """Test timeline and event management endpoints."""

    def test_list_timeline_events(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/timeline - List timeline events."""
        result = api_client.get(f"/api/matters/{test_matter_id}/timeline")
        test_report.add_result(result)
        assert result.success, f"List timeline failed: {result.error or result.response_data}"

    def test_timeline_stats(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/timeline/stats - Get timeline statistics."""
        result = api_client.get(f"/api/matters/{test_matter_id}/timeline/stats")
        test_report.add_result(result)
        assert result.success, f"Timeline stats failed: {result.error or result.response_data}"

    def test_full_timeline_with_entities(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/timeline/full - Timeline with entity info."""
        result = api_client.get(f"/api/matters/{test_matter_id}/timeline/full")
        test_report.add_result(result)
        assert result.success, f"Full timeline failed: {result.error or result.response_data}"

    def test_raw_dates(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/timeline/raw-dates - List extracted dates."""
        result = api_client.get(f"/api/matters/{test_matter_id}/timeline/raw-dates")
        test_report.add_result(result)
        assert result.success, f"Raw dates failed: {result.error or result.response_data}"

    def test_classified_events(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/timeline/events - List classified events."""
        result = api_client.get(f"/api/matters/{test_matter_id}/timeline/events")
        test_report.add_result(result)
        assert result.success, f"Classified events failed: {result.error or result.response_data}"

    def test_unclassified_events(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/timeline/unclassified - Events needing classification."""
        result = api_client.get(f"/api/matters/{test_matter_id}/timeline/unclassified")
        test_report.add_result(result)
        assert result.success, f"Unclassified events failed: {result.error or result.response_data}"


# ============================================================================
# SUMMARY ENDPOINTS
# ============================================================================

class TestSummaryEndpoints:
    """Test AI-generated summary endpoints."""

    def test_get_summary(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/summary - Get executive summary."""
        result = api_client.get(f"/api/matters/{test_matter_id}/summary")
        test_report.add_result(result)
        # May return 404 if no summary generated yet
        assert result.status_code in [200, 404], f"Get summary failed: {result.error or result.response_data}"

    def test_get_summary_verifications(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/summary/verifications - List verification decisions."""
        result = api_client.get(f"/api/matters/{test_matter_id}/summary/verifications")
        test_report.add_result(result)
        assert result.status_code in [200, 404], f"Summary verifications failed: {result.error or result.response_data}"


# ============================================================================
# VERIFICATIONS ENDPOINTS
# ============================================================================

class TestVerificationsEndpoints:
    """Test verification workflow endpoints."""

    def test_verification_stats(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/verifications/stats - Verification statistics."""
        result = api_client.get(f"/api/matters/{test_matter_id}/verifications/stats")
        test_report.add_result(result)
        assert result.success, f"Verification stats failed: {result.error or result.response_data}"

    def test_pending_verifications(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/verifications/pending - Pending verification queue."""
        result = api_client.get(f"/api/matters/{test_matter_id}/verifications/pending")
        test_report.add_result(result)
        assert result.success, f"Pending verifications failed: {result.error or result.response_data}"

    def test_list_verifications(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/verifications - List all verifications."""
        result = api_client.get(f"/api/matters/{test_matter_id}/verifications")
        test_report.add_result(result)
        assert result.success, f"List verifications failed: {result.error or result.response_data}"

    def test_export_eligibility(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/verifications/export-eligibility - Check export eligibility."""
        result = api_client.get(f"/api/matters/{test_matter_id}/verifications/export-eligibility")
        test_report.add_result(result)
        assert result.success, f"Export eligibility failed: {result.error or result.response_data}"


# ============================================================================
# JOBS ENDPOINTS
# ============================================================================

class TestJobsEndpoints:
    """Test job tracking endpoints."""

    def test_list_matter_jobs(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/jobs/matters/{id} - List jobs for matter."""
        result = api_client.get(f"/api/jobs/matters/{test_matter_id}")
        test_report.add_result(result)
        assert result.success, f"List matter jobs failed: {result.error or result.response_data}"

    def test_job_queue_stats(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/jobs/matters/{id}/stats - Job queue statistics."""
        result = api_client.get(f"/api/matters/{test_matter_id}/jobs/stats")
        test_report.add_result(result)
        # Endpoint might be at different path
        if result.status_code == 404:
            result = api_client.get(f"/api/jobs/matters/{test_matter_id}/stats")
            test_report.add_result(result)
        assert result.status_code in [200, 404], f"Job stats failed: {result.error or result.response_data}"


# ============================================================================
# ACTIVITY & DASHBOARD ENDPOINTS
# ============================================================================

class TestActivityEndpoints:
    """Test activity feed and dashboard endpoints."""

    def test_activity_feed(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/activity-feed - Get activity feed."""
        result = api_client.get("/api/activity-feed")
        test_report.add_result(result)
        assert result.success, f"Activity feed failed: {result.error or result.response_data}"

    def test_dashboard_stats(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/dashboard/stats - Get dashboard statistics."""
        result = api_client.get("/api/dashboard/stats")
        test_report.add_result(result)
        assert result.success, f"Dashboard stats failed: {result.error or result.response_data}"


# ============================================================================
# NOTIFICATIONS ENDPOINTS
# ============================================================================

class TestNotificationsEndpoints:
    """Test notification endpoints."""

    def test_list_notifications(self, api_client: APITestClient, test_report: TestReport):
        """GET /api/notifications - Get notifications."""
        result = api_client.get("/api/notifications")
        test_report.add_result(result)
        assert result.success, f"List notifications failed: {result.error or result.response_data}"


# ============================================================================
# EXPORTS ENDPOINTS
# ============================================================================

class TestExportsEndpoints:
    """Test export generation endpoints."""

    def test_list_exports(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/exports - List export history."""
        result = api_client.get(f"/api/matters/{test_matter_id}/exports")
        test_report.add_result(result)
        assert result.success, f"List exports failed: {result.error or result.response_data}"


# ============================================================================
# CHUNKS ENDPOINTS
# ============================================================================

class TestChunksEndpoints:
    """Test chunk retrieval endpoints."""

    # Note: These require a document_id which we don't have in a fresh test matter
    # Skipping individual chunk tests - would need to upload a document first
    pass


# ============================================================================
# ORPHANED ENDPOINTS TESTS
# ============================================================================

class TestOrphanedEndpoints:
    """Test endpoints identified as orphaned (not used by frontend)."""

    def test_alias_expanded_search(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """POST /api/matters/{id}/search/alias-expanded - ORPHANED: Alias-expanded search."""
        result = api_client.post(
            f"/api/matters/{test_matter_id}/search/alias-expanded",
            json={"query": "test", "limit": 10}
        )
        test_report.add_result(result)
        # Document that this endpoint exists but may not be fully implemented
        print(f"ORPHANED ENDPOINT: alias-expanded search returned {result.status_code}")

    def test_contradictions_list(self, api_client: APITestClient, test_matter_id: str, test_report: TestReport):
        """GET /api/matters/{id}/contradictions - ORPHANED: List contradictions."""
        result = api_client.get(f"/api/matters/{test_matter_id}/contradictions")
        test_report.add_result(result)
        print(f"ORPHANED ENDPOINT: contradictions list returned {result.status_code}")


# ============================================================================
# AUTHORIZATION TESTS
# ============================================================================

class TestAuthorizationFlow:
    """Test authorization scenarios."""

    def test_unauthenticated_request(self, test_report: TestReport):
        """Test that protected endpoints reject unauthenticated requests."""
        client = APITestClient(API_BASE_URL, auth_token=None)
        result = client.get("/api/matters", authenticated=True)
        test_report.add_result(result)
        assert result.status_code == 401, f"Expected 401, got {result.status_code}"

    def test_invalid_token(self, test_report: TestReport):
        """Test that invalid tokens are rejected."""
        client = APITestClient(API_BASE_URL, auth_token="invalid-token-here")
        result = client.get("/api/matters")
        test_report.add_result(result)
        assert result.status_code == 401, f"Expected 401, got {result.status_code}"


# ============================================================================
# FINAL REPORT
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def print_final_report(test_report: TestReport):
    """Print final test report after all tests complete."""
    yield

    print("\n" + "=" * 70)
    print("API ENDPOINT TEST REPORT")
    print("=" * 70)
    print(f"\n{test_report.summary()}\n")

    if test_report.failed > 0:
        print("\nFAILED ENDPOINTS:")
        print("-" * 50)
        for result in test_report.results:
            if not result.success:
                print(f"  {result.method} {result.endpoint}")
                print(f"    Status: {result.status_code}")
                if result.error:
                    print(f"    Error: {result.error}")
                print()

    # Save report to JSON
    report_data = {
        "summary": {
            "total": test_report.total,
            "passed": test_report.passed,
            "failed": test_report.failed,
            "skipped": test_report.skipped
        },
        "results": [
            {
                "endpoint": r.endpoint,
                "method": r.method,
                "status_code": r.status_code,
                "success": r.success,
                "response_time_ms": r.response_time_ms,
                "error": r.error
            }
            for r in test_report.results
        ]
    }

    report_path = "api_test_report.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\nDetailed report saved to: {report_path}")
