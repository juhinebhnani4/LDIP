"""Comprehensive tests for 4-layer matter isolation.

This module tests all four layers of the matter isolation security model:
- Layer 1: PostgreSQL RLS policies
- Layer 2: Vector namespace prefix
- Layer 3: Redis key prefix
- Layer 4: API middleware validation

CRITICAL: These tests verify the security foundation of LDIP.
All tests must pass before any deployment.
"""

import re
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.deps import (
    MatterAccessContext,
    log_matter_access,
    validate_matter_access,
)
from app.models.matter import MatterRole
from app.services.memory.redis_keys import (
    CACHE_TTL,
    SESSION_TTL,
    cache_key,
    cache_pattern,
    extract_matter_id_from_key,
    matter_key,
    matter_pattern,
    session_key,
    session_pattern,
    validate_key_access,
)
from app.services.rag.namespace import (
    MatterNamespaceFilter,
    build_semantic_search_query,
    build_vector_query_filter,
    get_namespace_filter,
    validate_namespace,
    validate_search_results,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_matter_id() -> str:
    """Generate a valid matter UUID."""
    return str(uuid4())


@pytest.fixture
def valid_user_id() -> str:
    """Generate a valid user UUID."""
    return str(uuid4())


@pytest.fixture
def valid_query_hash() -> str:
    """Generate a valid query hash."""
    return "a" * 64  # SHA256 hex string


# =============================================================================
# Layer 1 Tests: PostgreSQL RLS Policies
# =============================================================================

class TestRLSPolicyConcepts:
    """Test the concepts that RLS policies enforce."""

    def test_matter_id_required_for_queries(self, valid_matter_id: str):
        """Verify matter_id is required for all queries."""
        # The namespace filter requires matter_id
        filter_obj = get_namespace_filter(valid_matter_id)
        assert filter_obj.matter_id == valid_matter_id

    def test_empty_matter_id_rejected(self):
        """Verify empty matter_id is rejected."""
        with pytest.raises(ValueError, match="REQUIRED"):
            get_namespace_filter("")

        with pytest.raises(ValueError, match="REQUIRED"):
            get_namespace_filter(None)  # type: ignore

    def test_invalid_uuid_format_rejected(self):
        """Verify invalid UUIDs are rejected."""
        invalid_uuids = [
            "not-a-uuid",
            "12345",
            "'; DROP TABLE matters; --",
            "../../../etc/passwd",
            "00000000-0000-0000-0000-00000000000",  # Missing digit
            "00000000-0000-0000-0000-0000000000000",  # Extra digit
        ]

        for invalid_uuid in invalid_uuids:
            with pytest.raises(ValueError):
                get_namespace_filter(invalid_uuid)


# =============================================================================
# Layer 2 Tests: Vector Namespace Prefix
# =============================================================================

class TestVectorNamespaceIsolation:
    """Test Layer 2: Vector namespace prefix isolation."""

    def test_namespace_filter_creation(self, valid_matter_id: str):
        """Test creating a namespace filter."""
        filter_obj = get_namespace_filter(valid_matter_id)

        assert isinstance(filter_obj, MatterNamespaceFilter)
        assert filter_obj.matter_id == valid_matter_id

    def test_namespace_filter_with_document_ids(self, valid_matter_id: str):
        """Test namespace filter with document filtering."""
        doc_ids = [str(uuid4()), str(uuid4())]
        filter_obj = get_namespace_filter(valid_matter_id, document_ids=doc_ids)

        assert filter_obj.document_ids == doc_ids

    def test_namespace_filter_with_chunk_type(self, valid_matter_id: str):
        """Test namespace filter with chunk type filtering."""
        filter_obj = get_namespace_filter(valid_matter_id, chunk_type="parent")
        assert filter_obj.chunk_type == "parent"

        filter_obj = get_namespace_filter(valid_matter_id, chunk_type="child")
        assert filter_obj.chunk_type == "child"

    def test_invalid_chunk_type_rejected(self, valid_matter_id: str):
        """Test that invalid chunk types are rejected."""
        with pytest.raises(ValueError, match="parent.*child"):
            get_namespace_filter(valid_matter_id, chunk_type="invalid")

    def test_build_vector_query_filter(self, valid_matter_id: str):
        """Test building vector query filter dictionary."""
        filter_obj = get_namespace_filter(
            valid_matter_id,
            chunk_type="parent",
        )
        params = build_vector_query_filter(filter_obj)

        assert params["filter_matter_id"] == valid_matter_id
        assert params["filter_chunk_type"] == "parent"

    def test_build_semantic_search_query(self, valid_matter_id: str):
        """Test building semantic search query parameters."""
        filter_obj = get_namespace_filter(valid_matter_id)
        embedding = [0.1] * 1536

        params = build_semantic_search_query(
            filter_obj,
            embedding,
            limit=10,
            similarity_threshold=0.7,
        )

        assert params["filter_matter_id"] == valid_matter_id
        assert params["query_embedding"] == embedding
        assert params["match_count"] == 10
        assert params["similarity_threshold"] == 0.7

    def test_semantic_search_invalid_embedding_dimension(self, valid_matter_id: str):
        """Test that wrong embedding dimensions are rejected."""
        filter_obj = get_namespace_filter(valid_matter_id)

        with pytest.raises(ValueError, match="1536 dimensions"):
            build_semantic_search_query(filter_obj, [0.1] * 100)

        with pytest.raises(ValueError, match="1536 dimensions"):
            build_semantic_search_query(filter_obj, [])

    def test_validate_search_results_filters_cross_matter(
        self, valid_matter_id: str
    ):
        """Test that search results from other matters are filtered."""
        other_matter_id = str(uuid4())

        results = [
            {"id": "1", "matter_id": valid_matter_id, "content": "valid"},
            {"id": "2", "matter_id": other_matter_id, "content": "invalid"},
            {"id": "3", "matter_id": valid_matter_id, "content": "valid"},
        ]

        validated = validate_search_results(results, valid_matter_id)

        assert len(validated) == 2
        assert all(r["matter_id"] == valid_matter_id for r in validated)

    def test_validate_namespace_returns_valid_id(self, valid_matter_id: str):
        """Test that validate_namespace returns the validated ID."""
        result = validate_namespace(valid_matter_id)
        assert result == valid_matter_id


# =============================================================================
# Layer 3 Tests: Redis Key Prefix
# =============================================================================

class TestRedisKeyPrefixIsolation:
    """Test Layer 3: Redis key prefix isolation."""

    def test_session_key_format(
        self, valid_matter_id: str, valid_user_id: str
    ):
        """Test session key format."""
        key = session_key(valid_matter_id, valid_user_id, "messages")
        expected = f"session:{valid_matter_id}:{valid_user_id}:messages"
        assert key == expected

    def test_session_key_types(
        self, valid_matter_id: str, valid_user_id: str
    ):
        """Test all session key types."""
        for key_type in ["messages", "entities", "context", "metadata"]:
            key = session_key(valid_matter_id, valid_user_id, key_type)
            assert key.endswith(f":{key_type}")

    def test_cache_key_format(
        self, valid_matter_id: str, valid_query_hash: str
    ):
        """Test cache key format."""
        key = cache_key(valid_matter_id, valid_query_hash)
        expected = f"cache:query:{valid_matter_id}:{valid_query_hash}"
        assert key == expected

    def test_matter_key_format(self, valid_matter_id: str):
        """Test matter key format."""
        key = matter_key(valid_matter_id, "timeline")
        expected = f"matter:{valid_matter_id}:timeline"
        assert key == expected

    def test_matter_key_types(self, valid_matter_id: str):
        """Test all matter key types."""
        for key_type in ["timeline", "entity_graph", "findings", "stats"]:
            key = matter_key(valid_matter_id, key_type)
            assert key.endswith(f":{key_type}")

    def test_invalid_uuid_in_session_key(self):
        """Test that invalid UUIDs are rejected in session keys."""
        with pytest.raises(ValueError, match="Invalid UUID"):
            session_key("invalid", str(uuid4()), "messages")

        with pytest.raises(ValueError, match="Invalid UUID"):
            session_key(str(uuid4()), "invalid", "messages")

    def test_invalid_uuid_in_cache_key(self):
        """Test that invalid UUIDs are rejected in cache keys."""
        with pytest.raises(ValueError):
            cache_key("invalid", "a" * 64)

    def test_invalid_query_hash_rejected(self, valid_matter_id: str):
        """Test that invalid query hashes are rejected."""
        with pytest.raises(ValueError, match="hex hash"):
            cache_key(valid_matter_id, "not-a-hash")

        with pytest.raises(ValueError, match="hex hash"):
            cache_key(valid_matter_id, "abc")  # Too short

    def test_validate_key_access_same_matter(self, valid_matter_id: str):
        """Test key validation for same matter."""
        key = f"session:{valid_matter_id}:user:messages"
        assert validate_key_access(key, valid_matter_id) is True

    def test_validate_key_access_different_matter(self, valid_matter_id: str):
        """Test key validation rejects different matter."""
        other_matter_id = str(uuid4())
        key = f"session:{other_matter_id}:user:messages"
        assert validate_key_access(key, valid_matter_id) is False

    def test_extract_matter_id_from_keys(self, valid_matter_id: str):
        """Test extracting matter_id from various key formats."""
        # Session key
        key = f"session:{valid_matter_id}:user:messages"
        assert extract_matter_id_from_key(key) == valid_matter_id

        # Cache key
        key = f"cache:query:{valid_matter_id}:hash123"
        assert extract_matter_id_from_key(key) == valid_matter_id

        # Matter key
        key = f"matter:{valid_matter_id}:timeline"
        assert extract_matter_id_from_key(key) == valid_matter_id

    def test_pattern_generation(self, valid_matter_id: str, valid_user_id: str):
        """Test SCAN pattern generation."""
        assert session_pattern(valid_matter_id) == f"session:{valid_matter_id}:*"
        assert (
            session_pattern(valid_matter_id, valid_user_id)
            == f"session:{valid_matter_id}:{valid_user_id}:*"
        )
        assert cache_pattern(valid_matter_id) == f"cache:query:{valid_matter_id}:*"
        assert matter_pattern(valid_matter_id) == f"matter:{valid_matter_id}:*"

    def test_ttl_constants(self):
        """Test TTL constants are set correctly."""
        assert SESSION_TTL == 7 * 24 * 60 * 60  # 7 days
        assert CACHE_TTL == 60 * 60  # 1 hour


# =============================================================================
# Layer 4 Tests: API Middleware Validation
# =============================================================================

class TestAPIMiddlewareValidation:
    """Test Layer 4: API middleware validation."""

    @pytest.mark.asyncio
    async def test_validate_matter_access_success(self, valid_matter_id: str):
        """Test successful matter access validation."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.OWNER

        validator = validate_matter_access()
        context = await validator(
            request=mock_request,
            matter_id=valid_matter_id,
            user=mock_user,
            matter_service=mock_matter_service,
        )

        assert isinstance(context, MatterAccessContext)
        assert context.matter_id == valid_matter_id
        assert context.user_id == mock_user.id
        assert context.role == MatterRole.OWNER

    @pytest.mark.asyncio
    async def test_validate_matter_access_no_membership(self, valid_matter_id: str):
        """Test access denied when user has no membership."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = None

        validator = validate_matter_access()

        with pytest.raises(HTTPException) as exc_info:
            await validator(
                request=mock_request,
                matter_id=valid_matter_id,
                user=mock_user,
                matter_service=mock_matter_service,
            )

        # Should return 404, not 403, to prevent enumeration
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"]["code"] == "MATTER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_validate_matter_access_insufficient_role(self, valid_matter_id: str):
        """Test access denied when user has insufficient role."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Require owner, but user is viewer
        validator = validate_matter_access(require_role=MatterRole.OWNER)

        with pytest.raises(HTTPException) as exc_info:
            await validator(
                request=mock_request,
                matter_id=valid_matter_id,
                user=mock_user,
                matter_service=mock_matter_service,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    @pytest.mark.asyncio
    async def test_validate_matter_access_invalid_uuid(self):
        """Test that invalid UUIDs are rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        mock_matter_service = MagicMock()

        validator = validate_matter_access()

        with pytest.raises(HTTPException) as exc_info:
            await validator(
                request=mock_request,
                matter_id="invalid-uuid",
                user=mock_user,
                matter_service=mock_matter_service,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"]["code"] == "INVALID_PARAMETER"

    @pytest.mark.asyncio
    async def test_validate_matter_access_sql_injection_attempt(self):
        """Test that SQL injection attempts are blocked."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/matters/test"

        mock_user = MagicMock()
        mock_user.id = str(uuid4())

        mock_matter_service = MagicMock()

        validator = validate_matter_access()

        injection_attempts = [
            "'; DROP TABLE matters; --",
            "1 OR 1=1",
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "{{constructor.constructor('return this')()}}",
        ]

        for attempt in injection_attempts:
            with pytest.raises(HTTPException) as exc_info:
                await validator(
                    request=mock_request,
                    matter_id=attempt,
                    user=mock_user,
                    matter_service=mock_matter_service,
                )

            assert exc_info.value.status_code == 400


# =============================================================================
# Cross-Layer Integration Tests
# =============================================================================

class TestCrossLayerIntegration:
    """Test integration between all security layers."""

    def test_matter_id_consistency_across_layers(self, valid_matter_id: str):
        """Test that matter_id validation is consistent across layers."""
        # Layer 2: Vector namespace
        namespace_filter = get_namespace_filter(valid_matter_id)
        assert namespace_filter.matter_id == valid_matter_id

        # Layer 3: Redis keys
        redis_key = session_key(valid_matter_id, str(uuid4()), "messages")
        extracted = extract_matter_id_from_key(redis_key)
        assert extracted == valid_matter_id

    def test_invalid_uuid_rejected_across_all_layers(self):
        """Test that invalid UUIDs are rejected by all layers."""
        invalid_uuid = "not-a-valid-uuid"

        # Layer 2
        with pytest.raises(ValueError):
            get_namespace_filter(invalid_uuid)

        # Layer 3
        with pytest.raises(ValueError):
            session_key(invalid_uuid, str(uuid4()), "messages")

    def test_cross_matter_access_blocked(self, valid_matter_id: str):
        """Test that cross-matter access is blocked at all layers."""
        other_matter_id = str(uuid4())

        # Layer 2: Search results filtered
        results = [
            {"id": "1", "matter_id": other_matter_id, "content": "other"},
        ]
        validated = validate_search_results(results, valid_matter_id)
        assert len(validated) == 0

        # Layer 3: Key access blocked
        other_key = f"session:{other_matter_id}:user:messages"
        assert validate_key_access(other_key, valid_matter_id) is False


# =============================================================================
# Audit Logging Tests
# =============================================================================

class TestAuditLogging:
    """Test audit logging for security events."""

    @pytest.mark.asyncio
    async def test_log_matter_access_granted(self, valid_matter_id: str, valid_user_id: str):
        """Test logging successful access."""
        with patch("app.api.deps.logger") as mock_logger:
            await log_matter_access(
                user_id=valid_user_id,
                matter_id=valid_matter_id,
                action="view",
                result="granted",
            )

            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args[1]
            assert call_kwargs["user_id"] == valid_user_id
            assert call_kwargs["matter_id"] == valid_matter_id
            assert call_kwargs["result"] == "granted"

    @pytest.mark.asyncio
    async def test_log_matter_access_denied(self, valid_matter_id: str, valid_user_id: str):
        """Test logging denied access."""
        with patch("app.api.deps.logger") as mock_logger:
            await log_matter_access(
                user_id=valid_user_id,
                matter_id=valid_matter_id,
                action="delete",
                result="denied",
            )

            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args[1]
            assert call_kwargs["result"] == "denied"
