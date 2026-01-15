"""Tests for Summary API routes.

Story 14.1: Summary API Endpoint

Test Categories:
- Authentication requirements
- Endpoint existence and routing
- Role-based access control
- Response format validation
- Error handling
- Cache behavior
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import MatterAccessContext, MatterRole
from app.models.summary import (
    AttentionItem,
    AttentionItemType,
    CurrentStatus,
    KeyIssue,
    KeyIssueVerificationStatus,
    MatterStats,
    MatterSummary,
    PartyInfo,
    PartyRole,
    SubjectMatter,
    SubjectMatterSource,
)


@pytest.fixture
def sync_client() -> TestClient:
    """Create synchronous test client for auth tests."""
    return TestClient(app)


@pytest.fixture
def mock_matter_access() -> MatterAccessContext:
    """Create mock matter access context for testing."""
    return MatterAccessContext(
        matter_id="matter-123",
        user_id="user-123",
        role=MatterRole.OWNER,
        access_level="viewer",
    )


@pytest.fixture
def mock_viewer_access() -> MatterAccessContext:
    """Create mock viewer access context for testing."""
    return MatterAccessContext(
        matter_id="matter-123",
        user_id="user-456",
        role=MatterRole.VIEWER,
        access_level="viewer",
    )


@pytest.fixture
def mock_summary() -> MatterSummary:
    """Create mock summary for testing."""
    return MatterSummary(
        matter_id="matter-123",
        attention_items=[
            AttentionItem(
                type=AttentionItemType.CONTRADICTION,
                count=3,
                label="contradictions detected",
                target_tab="verification",
            ),
            AttentionItem(
                type=AttentionItemType.CITATION_ISSUE,
                count=2,
                label="citations need verification",
                target_tab="citations",
            ),
        ],
        parties=[
            PartyInfo(
                entity_id="entity-1",
                entity_name="John Doe",
                role=PartyRole.PETITIONER,
                source_document="Petition.pdf",
                source_page=1,
                is_verified=False,
            ),
        ],
        subject_matter=SubjectMatter(
            description="Test matter description",
            sources=[
                SubjectMatterSource(
                    document_name="Document.pdf",
                    page_range="1-5",
                ),
            ],
            is_verified=False,
        ),
        current_status=CurrentStatus(
            last_order_date=datetime(2026, 1, 15, tzinfo=UTC).isoformat(),
            description="Matter adjourned",
            source_document="Order.pdf",
            source_page=1,
            is_verified=False,
        ),
        key_issues=[
            KeyIssue(
                id="issue-1",
                number=1,
                title="Whether the claim is valid?",
                verification_status=KeyIssueVerificationStatus.PENDING,
            ),
        ],
        stats=MatterStats(
            total_pages=100,
            entities_found=20,
            events_extracted=15,
            citations_found=30,
            verification_percent=60.0,
        ),
        generated_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
    )


# =============================================================================
# Authentication Tests
# =============================================================================


class TestSummaryAuth:
    """Test authentication for summary endpoint."""

    def test_requires_auth(self, sync_client) -> None:
        """Summary endpoint should require authentication."""
        response = sync_client.get("/api/matters/matter-123/summary")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_rejected(self, sync_client) -> None:
        """Invalid token should be rejected."""
        response = sync_client.get(
            "/api/matters/matter-123/summary",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Authenticated Endpoint Tests
# =============================================================================


class TestGetSummaryAuthenticated:
    """Test get summary with authenticated user."""

    @pytest.mark.asyncio
    async def test_returns_summary(
        self, mock_matter_access, mock_summary
    ) -> None:
        """Should return summary data."""
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(return_value=mock_summary)

        response = await get_matter_summary(
            access=mock_matter_access,
            force_refresh=False,
            summary_service=mock_service,
        )

        assert response.data.matter_id == "matter-123"
        assert len(response.data.attention_items) == 2
        assert len(response.data.parties) == 1
        assert response.data.stats.total_pages == 100

    @pytest.mark.asyncio
    async def test_viewer_can_access_summary(
        self, mock_viewer_access, mock_summary
    ) -> None:
        """Viewer role should be able to access summary."""
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(return_value=mock_summary)

        response = await get_matter_summary(
            access=mock_viewer_access,
            force_refresh=False,
            summary_service=mock_service,
        )

        assert response.data.matter_id == "matter-123"

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self, mock_matter_access, mock_summary
    ) -> None:
        """Force refresh should call service with force_refresh=True."""
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(return_value=mock_summary)

        await get_matter_summary(
            access=mock_matter_access,
            force_refresh=True,
            summary_service=mock_service,
        )

        mock_service.get_summary.assert_called_once_with(
            matter_id="matter-123",
            force_refresh=True,
        )


# =============================================================================
# Response Format Tests
# =============================================================================


class TestSummaryResponseFormat:
    """Test response format validation."""

    @pytest.mark.asyncio
    async def test_response_includes_all_fields(
        self, mock_matter_access, mock_summary
    ) -> None:
        """Response should include all required fields."""
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(return_value=mock_summary)

        response = await get_matter_summary(
            access=mock_matter_access,
            force_refresh=False,
            summary_service=mock_service,
        )

        # Check all required fields
        data = response.data
        assert hasattr(data, "matter_id")
        assert hasattr(data, "attention_items")
        assert hasattr(data, "parties")
        assert hasattr(data, "subject_matter")
        assert hasattr(data, "current_status")
        assert hasattr(data, "key_issues")
        assert hasattr(data, "stats")
        assert hasattr(data, "generated_at")

    @pytest.mark.asyncio
    async def test_attention_items_structure(
        self, mock_matter_access, mock_summary
    ) -> None:
        """Attention items should have correct structure."""
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(return_value=mock_summary)

        response = await get_matter_summary(
            access=mock_matter_access,
            force_refresh=False,
            summary_service=mock_service,
        )

        item = response.data.attention_items[0]
        assert item.type == AttentionItemType.CONTRADICTION
        assert item.count == 3
        assert item.label == "contradictions detected"
        assert item.target_tab == "verification"

    @pytest.mark.asyncio
    async def test_stats_structure(
        self, mock_matter_access, mock_summary
    ) -> None:
        """Stats should have correct structure."""
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(return_value=mock_summary)

        response = await get_matter_summary(
            access=mock_matter_access,
            force_refresh=False,
            summary_service=mock_service,
        )

        stats = response.data.stats
        assert stats.total_pages == 100
        assert stats.entities_found == 20
        assert stats.events_extracted == 15
        assert stats.citations_found == 30
        assert stats.verification_percent == 60.0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestSummaryErrorHandling:
    """Test error handling for summary endpoint."""

    @pytest.mark.asyncio
    async def test_service_error_returns_500(self, mock_matter_access) -> None:
        """Service error should return 500."""
        from fastapi import HTTPException
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import (
            SummaryService,
            SummaryServiceError,
        )

        mock_service = MagicMock(spec=SummaryService)
        error = SummaryServiceError("Generation failed", code="GENERATION_FAILED")
        mock_service.get_summary = AsyncMock(side_effect=error)

        with pytest.raises(HTTPException) as exc_info:
            await get_matter_summary(
                access=mock_matter_access,
                force_refresh=False,
                summary_service=mock_service,
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.detail["error"]["code"] == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_openai_not_configured_returns_503(
        self, mock_matter_access
    ) -> None:
        """OpenAI not configured should return 503."""
        from fastapi import HTTPException
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import (
            SummaryService,
            OpenAIConfigurationError,
        )

        mock_service = MagicMock(spec=SummaryService)
        error = OpenAIConfigurationError("OpenAI API key not configured")
        mock_service.get_summary = AsyncMock(side_effect=error)

        with pytest.raises(HTTPException) as exc_info:
            await get_matter_summary(
                access=mock_matter_access,
                force_refresh=False,
                summary_service=mock_service,
            )

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_500(self, mock_matter_access) -> None:
        """Unexpected error should return 500 with generic message."""
        from fastapi import HTTPException
        from app.api.routes.summary import get_matter_summary
        from app.services.summary_service import SummaryService

        mock_service = MagicMock(spec=SummaryService)
        mock_service.get_summary = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_matter_summary(
                access=mock_matter_access,
                force_refresh=False,
                summary_service=mock_service,
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.detail["error"]["code"] == "INTERNAL_ERROR"


# =============================================================================
# Model Validation Tests
# =============================================================================


class TestSummaryModelValidation:
    """Test model validation."""

    def test_matter_summary_serialization(self, mock_summary) -> None:
        """MatterSummary should serialize to JSON correctly."""
        json_data = mock_summary.model_dump(by_alias=True)

        # Check camelCase keys
        assert "matterId" in json_data
        assert "attentionItems" in json_data
        assert "subjectMatter" in json_data
        assert "currentStatus" in json_data
        assert "keyIssues" in json_data
        assert "generatedAt" in json_data

    def test_attention_item_serialization(self) -> None:
        """AttentionItem should serialize with camelCase."""
        item = AttentionItem(
            type=AttentionItemType.CONTRADICTION,
            count=5,
            label="test",
            target_tab="tab",
        )
        json_data = item.model_dump(by_alias=True)

        assert "targetTab" in json_data
        assert json_data["targetTab"] == "tab"

    def test_party_info_serialization(self) -> None:
        """PartyInfo should serialize with camelCase."""
        party = PartyInfo(
            entity_id="id-1",
            entity_name="Test",
            role=PartyRole.PETITIONER,
            source_document="doc.pdf",
            source_page=1,
            is_verified=True,
        )
        json_data = party.model_dump(by_alias=True)

        assert "entityId" in json_data
        assert "entityName" in json_data
        assert "sourceDocument" in json_data
        assert "sourcePage" in json_data
        assert "isVerified" in json_data

    def test_key_issue_serialization(self) -> None:
        """KeyIssue should serialize with camelCase."""
        issue = KeyIssue(
            id="issue-1",
            number=1,
            title="Test issue",
            verification_status=KeyIssueVerificationStatus.VERIFIED,
        )
        json_data = issue.model_dump(by_alias=True)

        assert "verificationStatus" in json_data
        assert json_data["verificationStatus"] == "verified"

    def test_matter_stats_serialization(self) -> None:
        """MatterStats should serialize with camelCase."""
        stats = MatterStats(
            total_pages=100,
            entities_found=50,
            events_extracted=25,
            citations_found=75,
            verification_percent=80.0,
        )
        json_data = stats.model_dump(by_alias=True)

        assert "totalPages" in json_data
        assert "entitiesFound" in json_data
        assert "eventsExtracted" in json_data
        assert "citationsFound" in json_data
        assert "verificationPercent" in json_data
