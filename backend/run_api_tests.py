#!/usr/bin/env python3
"""
Quick API Endpoint Tester with Real Supabase Authentication.

Run this script to test all API endpoints against your running backend.

Usage:
    # Set test credentials
    set TEST_USER_EMAIL=your-test@email.com
    set TEST_USER_PASSWORD=your-password

    # Run tests
    python run_api_tests.py

    # Or with credentials inline
    python run_api_tests.py --email test@email.com --password yourpass
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ANSI colors for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

# Use simple ASCII for Windows compatibility
CHECK = "[OK]"
CROSS = "[FAIL]"


@dataclass
class TestResult:
    endpoint: str
    method: str
    status_code: int
    success: bool
    response_time_ms: float
    error: str | None = None
    category: str = "unknown"


@dataclass
class TestReport:
    results: list[TestResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    def add(self, result: TestResult):
        self.results.append(result)

    def print_summary(self):
        duration = time.time() - self.start_time
        print(f"\n{'='*70}")
        print(f"{Colors.BOLD}API ENDPOINT TEST RESULTS{Colors.RESET}")
        print(f"{'='*70}")
        print(f"\nDuration: {duration:.2f}s")
        print(f"Total:    {self.total}")
        print(f"Passed:   {Colors.GREEN}{self.passed}{Colors.RESET}")
        print(f"Failed:   {Colors.RED}{self.failed}{Colors.RESET}")
        print(f"\nPass Rate: {(self.passed/self.total*100):.1f}%" if self.total > 0 else "")

        if self.failed > 0:
            print(f"\n{Colors.RED}FAILED ENDPOINTS:{Colors.RESET}")
            print("-" * 50)
            for r in self.results:
                if not r.success:
                    print(f"  {r.method:6} {r.endpoint}")
                    print(f"         Status: {r.status_code} | Error: {r.error or 'N/A'}")


class APITester:
    def __init__(self, base_url: str, supabase_url: str, supabase_key: str):
        self.base_url = base_url
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.access_token: str | None = None
        self.user_id: str | None = None
        self.test_matter_id: str | None = None
        self.report = TestReport()
        self.client = httpx.Client(timeout=30.0)

    def authenticate(self, email: str, password: str) -> bool:
        """Authenticate with Supabase and get access token."""
        print(f"\n{Colors.CYAN}Authenticating with Supabase...{Colors.RESET}")

        try:
            response = self.client.post(
                f"{self.supabase_url}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": self.supabase_key,
                    "Content-Type": "application/json"
                },
                json={"email": email, "password": password}
            )

            if response.status_code != 200:
                print(f"{Colors.RED}Authentication failed: {response.status_code}{Colors.RESET}")
                print(f"Response: {response.text[:200]}")
                return False

            data = response.json()
            self.access_token = data["access_token"]
            self.user_id = data["user"]["id"]
            print(f"{Colors.GREEN}{CHECK} Authenticated as: {email}{Colors.RESET}")
            print(f"  User ID: {self.user_id}")
            return True

        except Exception as e:
            print(f"{Colors.RED}Authentication error: {e}{Colors.RESET}")
            return False

    def _headers(self, authenticated: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def test(self, method: str, path: str, category: str,
             authenticated: bool = True, json_data: dict | None = None,
             params: dict | None = None, expected_codes: list[int] | None = None) -> TestResult:
        """Execute a single endpoint test."""
        url = f"{self.base_url}{path}"
        expected = expected_codes or [200, 201]

        start = time.time()
        try:
            response = self.client.request(
                method,
                url,
                headers=self._headers(authenticated),
                json=json_data,
                params=params
            )
            elapsed_ms = (time.time() - start) * 1000

            success = response.status_code in expected
            error = None if success else f"Expected {expected}, got {response.status_code}"

            result = TestResult(
                endpoint=path,
                method=method,
                status_code=response.status_code,
                success=success,
                response_time_ms=elapsed_ms,
                error=error,
                category=category
            )

        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            result = TestResult(
                endpoint=path,
                method=method,
                status_code=0,
                success=False,
                response_time_ms=elapsed_ms,
                error=str(e),
                category=category
            )

        # Print result
        status = f"{Colors.GREEN}{CHECK}{Colors.RESET}" if result.success else f"{Colors.RED}{CROSS}{Colors.RESET}"
        print(f"  {status} {method:6} {path:50} [{result.status_code}] {result.response_time_ms:.0f}ms")

        self.report.add(result)
        return result

    def create_test_matter(self) -> bool:
        """Create a test matter for testing matter-scoped endpoints."""
        print(f"\n{Colors.CYAN}Creating test matter...{Colors.RESET}")

        try:
            response = self.client.post(
                f"{self.base_url}/api/matters",
                headers=self._headers(),
                json={
                    "title": f"API Test Matter - {datetime.now().isoformat()}",
                    "description": "Automated API testing"
                }
            )

            if response.status_code in [200, 201]:
                data = response.json()
                self.test_matter_id = data.get("data", {}).get("id")
                print(f"{Colors.GREEN}{CHECK} Created test matter: {self.test_matter_id}{Colors.RESET}")
                return True
            else:
                print(f"{Colors.RED}Failed to create test matter: {response.status_code}{Colors.RESET}")
                return False

        except Exception as e:
            print(f"{Colors.RED}Error creating test matter: {e}{Colors.RESET}")
            return False

    def cleanup_test_matter(self):
        """Delete the test matter."""
        if self.test_matter_id:
            print(f"\n{Colors.CYAN}Cleaning up test matter...{Colors.RESET}")
            try:
                self.client.delete(
                    f"{self.base_url}/api/matters/{self.test_matter_id}",
                    headers=self._headers()
                )
                print(f"{Colors.GREEN}{CHECK} Deleted test matter{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.YELLOW}Warning: Could not delete test matter: {e}{Colors.RESET}")

    def run_all_tests(self):
        """Run all endpoint tests."""
        m = self.test_matter_id  # shorthand

        # ====================================================================
        # HEALTH ENDPOINTS (No Auth)
        # ====================================================================
        print(f"\n{Colors.BOLD}[HEALTH ENDPOINTS]{Colors.RESET}")
        self.test("GET", "/", "health", authenticated=False)
        self.test("GET", "/api/health", "health", authenticated=False)
        self.test("GET", "/api/health/ready", "health", authenticated=False)
        self.test("GET", "/api/health/live", "health", authenticated=False)
        self.test("GET", "/api/health/circuits", "health", authenticated=False)

        # Health (Authenticated)
        print(f"\n{Colors.BOLD}[HEALTH ENDPOINTS - AUTHENTICATED]{Colors.RESET}")
        self.test("GET", "/api/health/me", "health")
        self.test("GET", "/api/health/rate-limits", "health")

        # ====================================================================
        # MATTERS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[MATTERS ENDPOINTS]{Colors.RESET}")
        self.test("GET", "/api/matters", "matters")
        self.test("GET", f"/api/matters/{m}", "matters")
        self.test("GET", f"/api/matters/{m}/tab-stats", "matters")
        self.test("GET", f"/api/matters/{m}/members", "matters")
        self.test("PATCH", f"/api/matters/{m}", "matters",
                  json_data={"description": f"Updated {datetime.now().isoformat()}"})

        # ====================================================================
        # DOCUMENTS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[DOCUMENTS ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/documents", "documents")
        self.test("GET", f"/api/matters/{m}/documents", "documents",
                  params={"page": 1, "per_page": 10})

        # ====================================================================
        # SEARCH ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[SEARCH ENDPOINTS]{Colors.RESET}")
        search_body = {"query": "test", "limit": 5}
        self.test("POST", f"/api/matters/{m}/search", "search",
                  json_data=search_body, expected_codes=[200, 404])
        self.test("POST", f"/api/matters/{m}/search/bm25", "search",
                  json_data=search_body, expected_codes=[200, 404])
        self.test("POST", f"/api/matters/{m}/search/semantic", "search",
                  json_data=search_body, expected_codes=[200, 404])
        self.test("POST", f"/api/matters/{m}/search/rerank", "search",
                  json_data=search_body, expected_codes=[200, 404])

        # ORPHANED: alias-expanded search
        self.test("POST", f"/api/matters/{m}/search/alias-expanded", "search-orphaned",
                  json_data=search_body, expected_codes=[200, 404, 500])

        # ====================================================================
        # ENTITIES ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[ENTITIES ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/entities", "entities")
        self.test("GET", f"/api/matters/{m}/entities", "entities",
                  params={"page": 1, "per_page": 20})

        # ====================================================================
        # CITATIONS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[CITATIONS ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/citations", "citations")
        self.test("GET", f"/api/matters/{m}/citations/stats", "citations")
        self.test("GET", f"/api/matters/{m}/citations/summary/by-act", "citations")
        self.test("GET", f"/api/matters/{m}/citations/acts/discovery", "citations")

        # ====================================================================
        # TIMELINE ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[TIMELINE ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/timeline", "timeline")
        self.test("GET", f"/api/matters/{m}/timeline/stats", "timeline")
        self.test("GET", f"/api/matters/{m}/timeline/full", "timeline")
        self.test("GET", f"/api/matters/{m}/timeline/raw-dates", "timeline")
        self.test("GET", f"/api/matters/{m}/timeline/events", "timeline")
        self.test("GET", f"/api/matters/{m}/timeline/unclassified", "timeline")
        self.test("GET", f"/api/matters/{m}/timeline/entities", "timeline")

        # ====================================================================
        # SUMMARY ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[SUMMARY ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/summary", "summary", expected_codes=[200, 404])
        self.test("GET", f"/api/matters/{m}/summary/verifications", "summary", expected_codes=[200, 404])

        # ====================================================================
        # VERIFICATIONS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[VERIFICATIONS ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/verifications/stats", "verifications")
        self.test("GET", f"/api/matters/{m}/verifications/pending", "verifications")
        self.test("GET", f"/api/matters/{m}/verifications", "verifications")
        self.test("GET", f"/api/matters/{m}/verifications/export-eligibility", "verifications")

        # ====================================================================
        # JOBS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[JOBS ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/jobs/matters/{m}", "jobs")
        self.test("GET", f"/api/jobs/matters/{m}/stats", "jobs", expected_codes=[200, 404])

        # ====================================================================
        # ACTIVITY & DASHBOARD ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[ACTIVITY & DASHBOARD ENDPOINTS]{Colors.RESET}")
        self.test("GET", "/api/activity-feed", "activity")
        self.test("GET", "/api/dashboard/stats", "dashboard")

        # ====================================================================
        # NOTIFICATIONS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[NOTIFICATIONS ENDPOINTS]{Colors.RESET}")
        self.test("GET", "/api/notifications", "notifications")

        # ====================================================================
        # EXPORTS ENDPOINTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[EXPORTS ENDPOINTS]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/exports", "exports")

        # ====================================================================
        # CONTRADICTIONS ENDPOINTS (ORPHANED)
        # ====================================================================
        print(f"\n{Colors.BOLD}[CONTRADICTIONS ENDPOINTS - ORPHANED]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/contradictions", "contradictions-orphaned",
                  expected_codes=[200, 404, 500])

        # ====================================================================
        # ANOMALIES ENDPOINTS (ORPHANED)
        # ====================================================================
        print(f"\n{Colors.BOLD}[ANOMALIES ENDPOINTS - ORPHANED]{Colors.RESET}")
        self.test("GET", f"/api/matters/{m}/anomalies", "anomalies-orphaned",
                  expected_codes=[200, 404, 500])
        self.test("GET", f"/api/matters/{m}/anomalies/summary", "anomalies-orphaned",
                  expected_codes=[200, 404, 500])

        # ====================================================================
        # AUTHORIZATION TESTS
        # ====================================================================
        print(f"\n{Colors.BOLD}[AUTHORIZATION TESTS]{Colors.RESET}")

        # Test without auth
        old_token = self.access_token
        self.access_token = None
        self.test("GET", "/api/matters", "auth-test", expected_codes=[401])
        self.access_token = old_token

        # Test with invalid token
        self.access_token = "invalid-token"
        self.test("GET", "/api/matters", "auth-test", expected_codes=[401])
        self.access_token = old_token

    def save_report(self, filename: str = "api_test_report.json"):
        """Save detailed report to JSON file."""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": self.report.total,
                "passed": self.report.passed,
                "failed": self.report.failed,
                "pass_rate": f"{(self.report.passed/self.report.total*100):.1f}%" if self.report.total > 0 else "0%"
            },
            "by_category": {},
            "results": []
        }

        # Group by category
        for r in self.report.results:
            if r.category not in report_data["by_category"]:
                report_data["by_category"][r.category] = {"passed": 0, "failed": 0}
            if r.success:
                report_data["by_category"][r.category]["passed"] += 1
            else:
                report_data["by_category"][r.category]["failed"] += 1

            report_data["results"].append({
                "endpoint": r.endpoint,
                "method": r.method,
                "category": r.category,
                "status_code": r.status_code,
                "success": r.success,
                "response_time_ms": round(r.response_time_ms, 2),
                "error": r.error
            })

        with open(filename, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n{Colors.CYAN}Detailed report saved to: {filename}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(description="Test all API endpoints with real authentication")
    parser.add_argument("--email", help="Test user email", default=os.getenv("TEST_USER_EMAIL"))
    parser.add_argument("--password", help="Test user password", default=os.getenv("TEST_USER_PASSWORD"))
    parser.add_argument("--base-url", help="API base URL", default=os.getenv("API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--no-cleanup", action="store_true", help="Don't delete test matter after tests")
    args = parser.parse_args()

    # Get Supabase config
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([supabase_url, supabase_key]):
        print(f"{Colors.RED}Error: Missing SUPABASE_URL or SUPABASE_KEY in environment{Colors.RESET}")
        sys.exit(1)

    if not all([args.email, args.password]):
        print(f"{Colors.RED}Error: Missing test user credentials{Colors.RESET}")
        print("Set TEST_USER_EMAIL and TEST_USER_PASSWORD or use --email and --password flags")
        sys.exit(1)

    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}LDIP API ENDPOINT TESTER{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"Base URL: {args.base_url}")
    print(f"User: {args.email}")

    # Create tester
    tester = APITester(args.base_url, supabase_url, supabase_key)

    # Authenticate
    if not tester.authenticate(args.email, args.password):
        sys.exit(1)

    # Create test matter
    if not tester.create_test_matter():
        print(f"{Colors.YELLOW}Warning: Could not create test matter. Some tests will fail.{Colors.RESET}")

    try:
        # Run all tests
        tester.run_all_tests()

        # Print summary
        tester.report.print_summary()

        # Save report
        tester.save_report()

    finally:
        # Cleanup
        if not args.no_cleanup:
            tester.cleanup_test_matter()

    # Exit with appropriate code
    sys.exit(0 if tester.report.failed == 0 else 1)


if __name__ == "__main__":
    main()
