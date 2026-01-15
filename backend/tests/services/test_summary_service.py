"""Tests for Summary Service.

Story 14.1: Summary API Endpoint

Test Categories:
- Stats computation
- Attention items
- GPT-4 generation
- Redis caching
- Language policing
"""

import pytest
import json
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.summary import (
    AttentionItemType,
    KeyIssueVerificationStatus,
    MatterStats,
    PartyRole,
)
from app.services.summary_service import SummaryService, SummaryServiceError


@pytest.fixture
def mock_supabase_client():
    """Create mock Supabase client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    client = MagicMock()
    return client


# =============================================================================
# Stats Computation Tests
# =============================================================================


class TestGetStats:
    """Test stats computation."""

    @pytest.mark.asyncio
    async def test_computes_total_pages(self, mock_supabase_client) -> None:
        """Should compute total pages from documents."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        # Mock document query
        mock_result = MagicMock()
        mock_result.data = [
            {"page_count": 50},
            {"page_count": 100},
            {"page_count": 25},
        ]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = await service._get_total_pages("matter-123")

        assert result == 175

    @pytest.mark.asyncio
    async def test_handles_null_page_counts(self, mock_supabase_client) -> None:
        """Should handle null page counts gracefully."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        mock_result = MagicMock()
        mock_result.data = [
            {"page_count": 50},
            {"page_count": None},
            {"page_count": 25},
        ]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = await service._get_total_pages("matter-123")

        assert result == 75

    @pytest.mark.asyncio
    async def test_handles_database_error(self, mock_supabase_client) -> None:
        """Should return 0 on database error."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            "DB Error"
        )

        result = await service._get_total_pages("matter-123")

        assert result == 0


# =============================================================================
# Attention Items Tests
# =============================================================================


class TestGetAttentionItems:
    """Test attention items computation."""

    @pytest.mark.asyncio
    async def test_returns_contradictions(self, mock_supabase_client) -> None:
        """Should return contradiction count."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        # Mock contradiction count
        mock_contradictions = MagicMock()
        mock_contradictions.count = 5

        # Mock citations (none)
        mock_citations = MagicMock()
        mock_citations.count = 0

        # Mock anomalies (none)
        mock_anomalies = MagicMock()
        mock_anomalies.count = 0

        def mock_execute():
            call_args = mock_supabase_client.table.call_args[0][0]
            if call_args == "statement_comparisons":
                return mock_contradictions
            elif call_args == "citations":
                return mock_citations
            else:
                return mock_anomalies

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = mock_execute
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_citations
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_anomalies

        result = await service.get_attention_items("matter-123")

        # Should have at least one attention item for contradictions
        assert any(
            item.type == AttentionItemType.CONTRADICTION
            for item in result
        )

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_issues(self, mock_supabase_client) -> None:
        """Should return empty list when no issues found."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        # All counts return 0
        mock_result = MagicMock()
        mock_result.count = 0

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_result
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = await service.get_attention_items("matter-123")

        assert result == []


# =============================================================================
# Redis Caching Tests
# =============================================================================


class TestSummaryCache:
    """Test Redis caching."""

    @pytest.mark.asyncio
    async def test_returns_cached_summary(self, mock_redis_client) -> None:
        """Should return cached summary if available."""
        service = SummaryService()
        # Use valid UUID format
        matter_id = "12345678-1234-1234-1234-123456789abc"

        cached_data = {
            "matterId": matter_id,
            "attentionItems": [],
            "parties": [],
            "subjectMatter": {
                "description": "Cached description",
                "sources": [],
                "isVerified": False,
            },
            "currentStatus": {
                "lastOrderDate": "2026-01-15T00:00:00Z",
                "description": "Cached status",
                "sourceDocument": "doc.pdf",
                "sourcePage": 1,
                "isVerified": False,
            },
            "keyIssues": [],
            "stats": {
                "totalPages": 100,
                "entitiesFound": 20,
                "eventsExtracted": 10,
                "citationsFound": 30,
                "verificationPercent": 50.0,
            },
            "generatedAt": "2026-01-15T00:00:00Z",
        }
        mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        # get_redis_client is async, so return an async mock
        async def mock_get_redis():
            return mock_redis_client

        with patch(
            "app.services.summary_service.get_redis_client",
            side_effect=mock_get_redis,
        ):
            result = await service._get_cached_summary(matter_id)

        assert result is not None
        assert result.matter_id == matter_id

    @pytest.mark.asyncio
    async def test_returns_none_on_cache_miss(self, mock_redis_client) -> None:
        """Should return None when cache is empty."""
        service = SummaryService()
        matter_id = "12345678-1234-1234-1234-123456789abc"
        mock_redis_client.get = AsyncMock(return_value=None)

        async def mock_get_redis():
            return mock_redis_client

        with patch(
            "app.services.summary_service.get_redis_client",
            side_effect=mock_get_redis,
        ):
            result = await service._get_cached_summary(matter_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_cache_errors(self, mock_redis_client) -> None:
        """Should return None on cache errors."""
        service = SummaryService()
        matter_id = "12345678-1234-1234-1234-123456789abc"
        mock_redis_client.get = AsyncMock(side_effect=Exception("Redis error"))

        async def mock_get_redis():
            return mock_redis_client

        with patch(
            "app.services.summary_service.get_redis_client",
            side_effect=mock_get_redis,
        ):
            result = await service._get_cached_summary(matter_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_caches_summary_with_ttl(self, mock_redis_client) -> None:
        """Should cache summary with TTL."""
        from app.models.summary import (
            MatterSummary,
            SubjectMatter,
            CurrentStatus,
            MatterStats,
        )

        service = SummaryService()
        matter_id = "12345678-1234-1234-1234-123456789abc"

        summary = MatterSummary(
            matter_id=matter_id,
            attention_items=[],
            parties=[],
            subject_matter=SubjectMatter(
                description="Test",
                sources=[],
                is_verified=False,
            ),
            current_status=CurrentStatus(
                last_order_date="2026-01-15T00:00:00Z",
                description="Test",
                source_document="doc.pdf",
                source_page=1,
                is_verified=False,
            ),
            key_issues=[],
            stats=MatterStats(),
            generated_at="2026-01-15T00:00:00Z",
        )

        async def mock_get_redis():
            return mock_redis_client

        with patch(
            "app.services.summary_service.get_redis_client",
            side_effect=mock_get_redis,
        ):
            await service._cache_summary(matter_id, summary)

        mock_redis_client.setex.assert_called_once()
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][0] == f"summary:{matter_id}"
        assert call_args[0][1] == 3600  # 1 hour TTL


# =============================================================================
# GPT-4 Generation Tests
# =============================================================================


class TestGenerateSubjectMatter:
    """Test subject matter generation."""

    @pytest.mark.asyncio
    async def test_returns_default_on_empty_chunks(self) -> None:
        """Should return default when no chunks provided."""
        service = SummaryService()

        result = await service.generate_subject_matter("matter-123", [])

        assert result.description == "No documents available to generate summary."
        assert result.sources == []

    @pytest.mark.asyncio
    async def test_calls_openai_with_correct_prompt(
        self, mock_openai_client
    ) -> None:
        """Should call OpenAI with formatted prompt."""
        service = SummaryService()
        service._openai_client = mock_openai_client

        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "description": "Test description",
                        "sources": [{"documentName": "doc.pdf", "pageRange": "1-5"}],
                    })
                )
            )
        ]
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        chunks = [
            {"content": "Test content", "document_name": "doc.pdf", "page_number": 1}
        ]

        with patch(
            "app.services.summary_service.get_language_policing_service"
        ) as mock_policing:
            mock_policing.return_value.sanitize_text.return_value.sanitized_text = (
                "Test description"
            )

            result = await service.generate_subject_matter("matter-123", chunks)

        assert result.description == "Test description"
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_openai_error(self, mock_openai_client) -> None:
        """Should return default on OpenAI error."""
        service = SummaryService()
        service._openai_client = mock_openai_client
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        chunks = [{"content": "Test", "document_name": "doc.pdf", "page_number": 1}]

        result = await service.generate_subject_matter("matter-123", chunks)

        assert result.description == "Unable to generate summary at this time."


class TestGetKeyIssues:
    """Test key issues extraction."""

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_chunks(self) -> None:
        """Should return empty list when no chunks provided."""
        service = SummaryService()

        result = await service.get_key_issues("matter-123", [])

        assert result == []

    @pytest.mark.asyncio
    async def test_limits_to_5_issues(self, mock_openai_client) -> None:
        """Should limit issues to 5."""
        service = SummaryService()
        service._openai_client = mock_openai_client

        # Mock response with more than 5 issues
        issues = [
            {"id": f"issue-{i}", "number": i, "title": f"Issue {i}"}
            for i in range(1, 10)
        ]
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content=json.dumps({"issues": issues}))
            )
        ]
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        chunks = [{"content": "Test", "document_name": "doc.pdf", "page_number": 1}]

        with patch(
            "app.services.summary_service.get_language_policing_service"
        ) as mock_policing:
            mock_policing.return_value.sanitize_text.return_value.sanitized_text = "Issue"

            result = await service.get_key_issues("matter-123", chunks)

        assert len(result) <= 5


# =============================================================================
# Parties Tests
# =============================================================================


class TestGetParties:
    """Test parties retrieval."""

    @pytest.mark.asyncio
    async def test_returns_sorted_parties(self, mock_supabase_client) -> None:
        """Should return parties sorted by role."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "mention-1",
                "entity_id": "entity-1",
                "page_number": 1,
                "identity_nodes": {
                    "id": "entity-1",
                    "canonical_name": "Respondent Inc",
                    "entity_type": "organization",
                    "metadata": {"roles": ["respondent"]},
                },
                "documents": {"name": "doc.pdf"},
            },
            {
                "id": "mention-2",
                "entity_id": "entity-2",
                "page_number": 2,
                "identity_nodes": {
                    "id": "entity-2",
                    "canonical_name": "John Petitioner",
                    "entity_type": "person",
                    "metadata": {"roles": ["petitioner"]},
                },
                "documents": {"name": "petition.pdf"},
            },
        ]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

        result = await service.get_parties("matter-123")

        # Petitioner should come first
        assert result[0].role == PartyRole.PETITIONER
        assert result[1].role == PartyRole.RESPONDENT

    @pytest.mark.asyncio
    async def test_limits_to_4_parties(self, mock_supabase_client) -> None:
        """Should limit parties to 4."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": f"mention-{i}",
                "entity_id": f"entity-{i}",
                "page_number": i,
                "identity_nodes": {
                    "id": f"entity-{i}",
                    "canonical_name": f"Party {i}",
                    "entity_type": "person",
                    "metadata": {},
                },
                "documents": {"name": "doc.pdf"},
            }
            for i in range(1, 10)
        ]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

        result = await service.get_parties("matter-123")

        assert len(result) <= 4


# =============================================================================
# Verification Stats Tests
# =============================================================================


class TestVerificationStats:
    """Test verification percentage computation."""

    @pytest.mark.asyncio
    async def test_computes_percentage(self, mock_supabase_client) -> None:
        """Should compute correct verification percentage."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        # Mock total count
        mock_total = MagicMock()
        mock_total.count = 10

        # Mock approved count
        mock_approved = MagicMock()
        mock_approved.count = 7

        call_count = [0]

        def mock_execute():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_total
            return mock_approved

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute = mock_execute
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_approved

        result = await service._get_verification_stats("matter-123")

        assert result == 70.0

    @pytest.mark.asyncio
    async def test_returns_zero_on_no_verifications(
        self, mock_supabase_client
    ) -> None:
        """Should return 0 when no verifications exist."""
        service = SummaryService()
        service._supabase_client = mock_supabase_client

        mock_result = MagicMock()
        mock_result.count = 0
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = await service._get_verification_stats("matter-123")

        assert result == 0.0
