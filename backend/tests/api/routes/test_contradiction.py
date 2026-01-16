"""Tests for Contradiction API routes.

Story 5-1: API endpoint tests for entity statement querying.
Story 5-2: API endpoint tests for statement pair comparison.

Uses FastAPI dependency_overrides for proper test isolation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.contradiction import (
    DocumentStatements,
    EntityComparisonsResponse,
    EntityStatements,
    EntityStatementsResponse,
    PaginationMeta,
    Statement,
    StatementValue,
    StatementValueType,
)
from app.models.matter import MatterRole
from app.services.contradiction.statement_query import EntityNotFoundError

# Test JWT secret
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.is_configured = True
    settings.debug = True
    return settings


def create_test_token(
    user_id: str = "test-user-id",
    email: str = "test@example.com",
) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def sync_client() -> TestClient:
    """Create synchronous test client for auth tests."""
    return TestClient(app)


class TestGetEntityStatementsAuth:
    """Tests for authentication requirements."""

    def test_get_entity_statements_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.get(
            "/api/matters/matter-123/contradictions/entities/entity-123/statements"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetEntityStatements:
    """Tests for GET /api/matters/{matter_id}/contradictions/entities/{entity_id}/statements."""

    @pytest.fixture
    def mock_service_response(self) -> EntityStatementsResponse:
        """Create mock service response."""
        return EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Nirav Jobalia",
                total_statements=2,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name="Contract.pdf",
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id="chunk-1",
                                document_id="doc-1",
                                content="On 15/01/2024, payment of Rs. 5,00,000 was made.",
                                dates=[
                                    StatementValue(
                                        type=StatementValueType.DATE,
                                        raw_text="15/01/2024",
                                        normalized="2024-01-15",
                                        confidence=0.9,
                                    )
                                ],
                                amounts=[
                                    StatementValue(
                                        type=StatementValueType.AMOUNT,
                                        raw_text="Rs. 5,00,000",
                                        normalized="500000",
                                        confidence=0.9,
                                    )
                                ],
                                page_number=1,
                                confidence=1.0,
                            )
                        ],
                        statement_count=1,
                    )
                ],
                aliases_included=["N.D. Jobalia"],
            ),
            meta=PaginationMeta(
                total=2,
                page=1,
                per_page=50,
                total_pages=1,
            ),
        )

    @pytest.mark.anyio
    async def test_get_entity_statements_success(
        self,
        mock_service_response: EntityStatementsResponse,
    ) -> None:
        """Should return 200 with entity statements on success."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        # Mock matter service for auth
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        # Mock statement query service
        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=mock_service_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        assert data["data"]["entityId"] == "entity-123"
        assert data["data"]["entityName"] == "Nirav Jobalia"
        assert data["data"]["totalStatements"] == 2
        assert len(data["data"]["documents"]) == 1

    @pytest.mark.anyio
    async def test_get_entity_statements_not_found(self) -> None:
        """Should return 404 when entity not found."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(side_effect=EntityNotFoundError(
            "entity-123", "matter-123"
        ))

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.anyio
    async def test_get_entity_statements_with_query_params(
        self,
        mock_service_response: EntityStatementsResponse,
    ) -> None:
        """Should pass query parameters to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=mock_service_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                params={
                    "includeAliases": "false",
                    "page": 2,
                    "perPage": 25,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        # Verify service was called with correct params
        call_args = mock_stmt_service.get_entity_statements.call_args
        assert call_args.kwargs["include_aliases"] is False
        assert call_args.kwargs["page"] == 2
        assert call_args.kwargs["per_page"] == 25

    @pytest.mark.anyio
    async def test_get_entity_statements_empty_result(self) -> None:
        """Should return 200 with empty statements (AC #4)."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        empty_response = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test Entity",
                total_statements=0,
                documents=[],
                aliases_included=[],
            ),
            meta=PaginationMeta(
                total=0,
                page=1,
                per_page=50,
                total_pages=0,
            ),
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=empty_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        # Should return 200, not 404 (AC #4)
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["totalStatements"] == 0
        assert len(data["data"]["documents"]) == 0


class TestGetEntityStatementsValueExtraction:
    """Tests for value extraction in API responses (AC #3)."""

    @pytest.mark.anyio
    async def test_response_includes_extracted_dates(self) -> None:
        """Should include extracted dates in statements."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        response_with_dates = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test",
                total_statements=1,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name=None,
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id="chunk-1",
                                document_id="doc-1",
                                content="On 15/01/2024.",
                                dates=[
                                    StatementValue(
                                        type=StatementValueType.DATE,
                                        raw_text="15/01/2024",
                                        normalized="2024-01-15",
                                        confidence=0.9,
                                    )
                                ],
                                amounts=[],
                                page_number=1,
                                confidence=1.0,
                            )
                        ],
                        statement_count=1,
                    )
                ],
                aliases_included=[],
            ),
            meta=PaginationMeta(total=1, page=1, per_page=50, total_pages=1),
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=response_with_dates)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        statement = data["data"]["documents"][0]["statements"][0]
        assert len(statement["dates"]) == 1
        assert statement["dates"][0]["type"] == "DATE"
        assert statement["dates"][0]["normalized"] == "2024-01-15"

    @pytest.mark.anyio
    async def test_response_includes_extracted_amounts(self) -> None:
        """Should include extracted amounts in statements."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        response_with_amounts = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test",
                total_statements=1,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name=None,
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id="chunk-1",
                                document_id="doc-1",
                                content="Payment of 5 lakhs.",
                                dates=[],
                                amounts=[
                                    StatementValue(
                                        type=StatementValueType.AMOUNT,
                                        raw_text="5 lakhs",
                                        normalized="500000",
                                        confidence=0.9,
                                    )
                                ],
                                page_number=1,
                                confidence=1.0,
                            )
                        ],
                        statement_count=1,
                    )
                ],
                aliases_included=[],
            ),
            meta=PaginationMeta(total=1, page=1, per_page=50, total_pages=1),
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=response_with_amounts)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        statement = data["data"]["documents"][0]["statements"][0]
        assert len(statement["amounts"]) == 1
        assert statement["amounts"][0]["type"] == "AMOUNT"
        assert statement["amounts"][0]["normalized"] == "500000"


class TestGetEntityStatementsAliasResolution:
    """Tests for alias resolution in API responses (AC #2)."""

    @pytest.mark.anyio
    async def test_response_includes_aliases_searched(self) -> None:
        """Should include aliasesIncluded in response."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_statement_service
        from app.core.config import get_settings

        response_with_aliases = EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Nirav Jobalia",
                total_statements=3,
                documents=[],
                aliases_included=["N.D. Jobalia", "Nirav D. Jobalia"],
            ),
            meta=PaginationMeta(total=3, page=1, per_page=50, total_pages=1),
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_stmt_service = MagicMock()
        mock_stmt_service.get_entity_statements = AsyncMock(return_value=response_with_aliases)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_statement_service] = lambda: mock_stmt_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                "/api/matters/matter-123/contradictions/entities/entity-123/statements",
                params={"includeAliases": "true"},
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        assert "N.D. Jobalia" in data["data"]["aliasesIncluded"]
        assert "Nirav D. Jobalia" in data["data"]["aliasesIncluded"]


# =============================================================================
# Story 5-2: Statement Comparison API Tests
# =============================================================================


class TestCompareEntityStatementsAuth:
    """Tests for comparison endpoint authentication."""

    def test_compare_entity_statements_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.post(
            "/api/matters/matter-123/contradictions/entities/entity-123/compare"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCompareEntityStatements:
    """Tests for POST /api/matters/{matter_id}/contradictions/entities/{entity_id}/compare."""

    @pytest.fixture
    def mock_comparison_response(self) -> "EntityComparisonsResponse":
        """Create mock comparison response."""
        from app.models.contradiction import (
            ComparisonMeta,
            ComparisonResult,
            ContradictionEvidence,
            EntityComparisons,
            EntityComparisonsResponse,
            EvidenceType,
            StatementPairComparison,
        )

        return EntityComparisonsResponse(
            data=EntityComparisons(
                entity_id="entity-123",
                entity_name="Nirav Jobalia",
                comparisons=[
                    StatementPairComparison(
                        statement_a_id="chunk-1",
                        statement_b_id="chunk-2",
                        statement_a_content="The loan was Rs. 5 lakhs.",
                        statement_b_content="The loan was Rs. 8 lakhs.",
                        result=ComparisonResult.CONTRADICTION,
                        reasoning="Statement A claims loan was Rs. 5 lakhs. Statement B claims Rs. 8 lakhs. These amounts conflict.",
                        confidence=0.95,
                        evidence=ContradictionEvidence(
                            type=EvidenceType.AMOUNT_MISMATCH,
                            value_a="500000",
                            value_b="800000",
                            page_refs={"statement_a": 5, "statement_b": 12},
                        ),
                        document_a_id="doc-1",
                        document_b_id="doc-2",
                        page_a=5,
                        page_b=12,
                    ),
                ],
                contradictions_found=1,
                total_pairs_compared=10,
            ),
            meta=ComparisonMeta(
                pairs_compared=10,
                contradictions_found=1,
                total_cost_usd=0.35,
                processing_time_ms=5000,
            ),
        )

    @pytest.mark.anyio
    async def test_compare_entity_statements_success(
        self,
        mock_comparison_response: "EntityComparisonsResponse",
    ) -> None:
        """Should return 200 with comparison results on success."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_comparison_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_comp_service = MagicMock()
        mock_comp_service.compare_entity_statements = AsyncMock(return_value=mock_comparison_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_comparison_service] = lambda: mock_comp_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.post(
                "/api/matters/matter-123/contradictions/entities/entity-123/compare",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        assert data["data"]["entityId"] == "entity-123"
        assert data["data"]["contradictionsFound"] == 1
        assert data["meta"]["pairsCompared"] == 10
        assert data["meta"]["totalCostUsd"] == 0.35

    @pytest.mark.anyio
    async def test_compare_entity_statements_not_found(self) -> None:
        """Should return 404 when entity not found."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_comparison_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_comp_service = MagicMock()
        mock_comp_service.compare_entity_statements = AsyncMock(
            side_effect=EntityNotFoundError("entity-123", "matter-123")
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_comparison_service] = lambda: mock_comp_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.post(
                "/api/matters/matter-123/contradictions/entities/entity-123/compare",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.anyio
    async def test_compare_entity_statements_too_many(self) -> None:
        """Should return 422 when too many statements."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_comparison_service
        from app.core.config import get_settings
        from app.services.contradiction.comparator import TooManyStatementsError

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_comp_service = MagicMock()
        mock_comp_service.compare_entity_statements = AsyncMock(
            side_effect=TooManyStatementsError(150, 100)
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_comparison_service] = lambda: mock_comp_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.post(
                "/api/matters/matter-123/contradictions/entities/entity-123/compare",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"]["code"] == "TOO_MANY_STATEMENTS"
        assert data["detail"]["error"]["details"]["statementCount"] == 150

    @pytest.mark.anyio
    async def test_compare_entity_statements_with_params(
        self,
        mock_comparison_response: "EntityComparisonsResponse",
    ) -> None:
        """Should pass query parameters to service."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_comparison_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_comp_service = MagicMock()
        mock_comp_service.compare_entity_statements = AsyncMock(return_value=mock_comparison_response)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_comparison_service] = lambda: mock_comp_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.post(
                "/api/matters/matter-123/contradictions/entities/entity-123/compare",
                params={
                    "maxPairs": "25",
                    "confidenceThreshold": "0.8",
                    "includeAliases": "false",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        # Verify service was called with correct params
        call_args = mock_comp_service.compare_entity_statements.call_args
        assert call_args.kwargs["max_pairs"] == 25
        assert call_args.kwargs["confidence_threshold"] == 0.8
        assert call_args.kwargs["include_aliases"] is False


class TestCompareEntityStatementsChainOfThought:
    """Tests for chain-of-thought reasoning in comparison results (AC #4)."""

    @pytest.mark.anyio
    async def test_response_includes_reasoning(self) -> None:
        """Should include chain-of-thought reasoning in response."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_comparison_service
        from app.core.config import get_settings
        from app.models.contradiction import (
            ComparisonMeta,
            ComparisonResult,
            ContradictionEvidence,
            EntityComparisons,
            EntityComparisonsResponse,
            EvidenceType,
            StatementPairComparison,
        )

        response_with_reasoning = EntityComparisonsResponse(
            data=EntityComparisons(
                entity_id="entity-123",
                entity_name="Test",
                comparisons=[
                    StatementPairComparison(
                        statement_a_id="chunk-1",
                        statement_b_id="chunk-2",
                        statement_a_content="The contract was signed on 15/01/2024.",
                        statement_b_content="The contract was signed on 15/06/2024.",
                        result=ComparisonResult.CONTRADICTION,
                        reasoning="Step 1: Statement A claims signing date was 15/01/2024. Step 2: Statement B claims 15/06/2024. Step 3: These dates conflict - same event with different dates.",
                        confidence=0.92,
                        evidence=ContradictionEvidence(
                            type=EvidenceType.DATE_MISMATCH,
                            value_a="2024-01-15",
                            value_b="2024-06-15",
                        ),
                        document_a_id="doc-1",
                        document_b_id="doc-2",
                    ),
                ],
                contradictions_found=1,
                total_pairs_compared=1,
            ),
            meta=ComparisonMeta(
                pairs_compared=1,
                contradictions_found=1,
                total_cost_usd=0.04,
                processing_time_ms=1500,
            ),
        )

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_comp_service = MagicMock()
        mock_comp_service.compare_entity_statements = AsyncMock(return_value=response_with_reasoning)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_comparison_service] = lambda: mock_comp_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.post(
                "/api/matters/matter-123/contradictions/entities/entity-123/compare",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        data = response.json()
        comparison = data["data"]["comparisons"][0]

        # Verify reasoning is present (AC #4)
        assert "reasoning" in comparison
        assert "Step 1" in comparison["reasoning"]
        assert "dates conflict" in comparison["reasoning"]

        # Verify evidence values
        assert comparison["evidence"]["type"] == "date_mismatch"
        assert comparison["evidence"]["valueA"] == "2024-01-15"
        assert comparison["evidence"]["valueB"] == "2024-06-15"


class TestCompareEntityStatementsMatterIsolation:
    """Tests for matter isolation (CRITICAL security test)."""

    @pytest.mark.anyio
    async def test_matter_id_validated(self) -> None:
        """Should validate matter_id for every request."""
        from app.api.deps import get_matter_service
        from app.api.routes.contradiction import _get_comparison_service
        from app.core.config import get_settings

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.EDITOR

        mock_comp_service = MagicMock()
        # Simulate entity being validated against matter
        mock_comp_service.compare_entity_statements = AsyncMock(
            side_effect=EntityNotFoundError("entity-123", "other-matter")
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[_get_comparison_service] = lambda: mock_comp_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.post(
                "/api/matters/other-matter/contradictions/entities/entity-123/compare",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        # Should return 404, not expose that entity exists in other matter
        assert response.status_code == 404
