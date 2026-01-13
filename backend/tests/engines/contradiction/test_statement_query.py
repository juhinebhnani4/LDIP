"""Tests for Statement Query Engine and Value Extractor.

Story 5-1: Entity-Grouped Statement Querying

Tests cover:
- Value extraction (dates, amounts - AC #3)
- Statement querying by entity (AC #1)
- Alias resolution (AC #2)
- Empty results handling (AC #4)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.contradiction.statement_query import (
    StatementQueryEngine,
    ValueExtractor,
    get_statement_query_engine,
    get_value_extractor,
)
from app.models.contradiction import StatementValueType


# =============================================================================
# Value Extractor Tests (AC #3)
# =============================================================================


class TestValueExtractorDates:
    """Tests for date extraction from statements."""

    def test_extract_dd_mm_yyyy_slash(self) -> None:
        """Should extract DD/MM/YYYY format."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("The document was signed on 15/01/2024.")

        assert len(dates) == 1
        assert dates[0].type == StatementValueType.DATE
        assert dates[0].raw_text == "15/01/2024"
        assert dates[0].normalized == "2024-01-15"

    def test_extract_dd_mm_yyyy_dash(self) -> None:
        """Should extract DD-MM-YYYY format."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("Filed on 25-12-2023.")

        assert len(dates) == 1
        assert dates[0].normalized == "2023-12-25"

    def test_extract_dd_mm_yyyy_dot(self) -> None:
        """Should extract DD.MM.YYYY format."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("Meeting on 05.03.2024")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-03-05"

    def test_extract_legal_dated_format(self) -> None:
        """Should extract 'dated 15th of January, 2024' format."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("The contract dated 15th of January, 2024 is hereby void.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-01-15"

    def test_extract_written_date_format(self) -> None:
        """Should extract '15th January 2024' format."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("The hearing was held on 3rd March 2024.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-03-03"

    def test_extract_iso_date_format(self) -> None:
        """Should extract YYYY-MM-DD ISO format."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("Reference: Case filed 2024-06-15.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-06-15"

    def test_extract_multiple_dates(self) -> None:
        """Should extract multiple dates from text."""
        extractor = ValueExtractor()
        text = "The contract from 01/05/2023 was amended on 15/08/2023."
        dates = extractor.extract_dates(text)

        assert len(dates) == 2
        assert dates[0].normalized == "2023-05-01"
        assert dates[1].normalized == "2023-08-15"

    def test_extract_no_dates(self) -> None:
        """Should return empty list when no dates found."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("No dates in this text.")

        assert len(dates) == 0

    def test_extract_empty_text(self) -> None:
        """Should handle empty text gracefully."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("")

        assert len(dates) == 0

    def test_extract_invalid_date_rejected(self) -> None:
        """Should reject invalid dates (month > 12, day > 31)."""
        extractor = ValueExtractor()
        # 32nd day doesn't exist
        dates = extractor.extract_dates("On 32/01/2024 something happened.")

        # Should be empty because 32 is not a valid day
        assert len(dates) == 0

    def test_deduplicate_dates(self) -> None:
        """Should not duplicate same date found multiple times."""
        extractor = ValueExtractor()
        text = "The date 15/01/2024 appears twice: 15/01/2024."
        dates = extractor.extract_dates(text)

        # Should have only one entry for the same date text
        assert len(dates) == 1


class TestValueExtractorAmounts:
    """Tests for amount extraction from statements."""

    def test_extract_rs_format(self) -> None:
        """Should extract Rs. X,XX,XXX format."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("The amount was Rs. 5,00,000.")

        assert len(amounts) == 1
        assert amounts[0].type == StatementValueType.AMOUNT
        assert amounts[0].normalized == "500000"

    def test_extract_rupees_word(self) -> None:
        """Should extract 'X rupees' format."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("He paid 50000 rupees.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "50000"

    def test_extract_lakhs(self) -> None:
        """Should extract 'X lakhs' format (1 lakh = 100,000)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("The property cost 50 lakhs.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "5000000"  # 50 * 100,000

    def test_extract_crores(self) -> None:
        """Should extract 'X crores' format (1 crore = 10,000,000)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Revenue of 2 crores.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "20000000"  # 2 * 10,000,000

    def test_extract_usd(self) -> None:
        """Should extract USD format."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Payment of $10,000 received.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "USD:10000"

    def test_extract_percentage(self) -> None:
        """Should extract percentage as QUANTITY type."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Interest rate of 8.5%.")

        assert len(amounts) == 1
        assert amounts[0].type == StatementValueType.QUANTITY
        assert amounts[0].normalized == "8.5%"

    def test_extract_multiple_amounts(self) -> None:
        """Should extract multiple amounts from text."""
        extractor = ValueExtractor()
        text = "Principal of Rs. 10,00,000 with interest of 5 lakhs."
        amounts = extractor.extract_amounts(text)

        assert len(amounts) == 2

    def test_extract_no_amounts(self) -> None:
        """Should return empty list when no amounts found."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("No amounts here.")

        assert len(amounts) == 0

    def test_extract_empty_text(self) -> None:
        """Should handle empty text gracefully."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("")

        assert len(amounts) == 0


class TestValueExtractorCombined:
    """Tests for combined date and amount extraction."""

    def test_extract_all_values(self) -> None:
        """Should extract both dates and amounts."""
        extractor = ValueExtractor()
        text = "On 15/01/2024, he paid Rs. 5,00,000."

        dates, amounts = extractor.extract_all_values(text)

        assert len(dates) == 1
        assert len(amounts) == 1
        assert dates[0].normalized == "2024-01-15"
        assert amounts[0].normalized == "500000"

    def test_extract_all_values_empty(self) -> None:
        """Should return empty lists for text without values."""
        extractor = ValueExtractor()
        dates, amounts = extractor.extract_all_values("Just plain text.")

        assert len(dates) == 0
        assert len(amounts) == 0


class TestValueExtractorFactory:
    """Tests for ValueExtractor factory function."""

    def test_singleton_factory(self) -> None:
        """Should return singleton instance."""
        get_value_extractor.cache_clear()

        extractor1 = get_value_extractor()
        extractor2 = get_value_extractor()

        assert extractor1 is extractor2

        get_value_extractor.cache_clear()


# =============================================================================
# Statement Query Engine Tests (AC #1, #2, #4)
# =============================================================================


class TestStatementQueryEngine:
    """Tests for StatementQueryEngine."""

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.fixture
    def engine(self, mock_supabase_client: MagicMock) -> StatementQueryEngine:
        """Create engine with mock client."""
        return StatementQueryEngine(mock_supabase_client)

    def test_init_creates_instance(self, mock_supabase_client: MagicMock) -> None:
        """Should create engine instance."""
        engine = StatementQueryEngine(mock_supabase_client)
        assert engine is not None
        assert engine._client is mock_supabase_client

    @pytest.mark.asyncio
    async def test_get_statements_for_entity_empty_result(
        self,
        engine: StatementQueryEngine,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Should return empty EntityStatements when no chunks found (AC #4)."""
        # Mock empty response
        mock_response = MagicMock()
        mock_response.data = []

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.contains.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_supabase_client.table.return_value = MagicMock(select=MagicMock(return_value=mock_query))

        # Mock entity name lookup
        mock_name_response = MagicMock()
        mock_name_response.data = [{"canonical_name": "Test Entity"}]

        mock_name_query = MagicMock()
        mock_name_query.eq.return_value = mock_name_query
        mock_name_query.limit.return_value = mock_name_query
        mock_name_query.execute.return_value = mock_name_response

        def table_side_effect(table_name: str):
            if table_name == "identity_nodes":
                return MagicMock(select=MagicMock(return_value=mock_name_query))
            return MagicMock(select=MagicMock(return_value=mock_query))

        mock_supabase_client.table.side_effect = table_side_effect

        result = await engine.get_statements_for_entity(
            entity_id="entity-123",
            matter_id="matter-456",
        )

        assert result.total_statements == 0
        assert len(result.documents) == 0
        # No error - AC #4 satisfied

    @pytest.mark.asyncio
    async def test_get_statements_for_entity_with_results(
        self,
        engine: StatementQueryEngine,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Should return grouped statements when chunks found (AC #1)."""
        # Mock chunk response
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "content": "On 15/01/2024, the payment was Rs. 5,00,000.",
                "page_number": 1,
                "entity_ids": ["entity-123"],
            },
            {
                "id": "chunk-2",
                "document_id": "doc-1",
                "content": "Another statement about the entity.",
                "page_number": 2,
                "entity_ids": ["entity-123"],
            },
        ]

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.contains.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_response

        # Mock entity name lookup
        mock_name_response = MagicMock()
        mock_name_response.data = [{"canonical_name": "Test Entity"}]

        mock_name_query = MagicMock()
        mock_name_query.eq.return_value = mock_name_query
        mock_name_query.limit.return_value = mock_name_query
        mock_name_query.execute.return_value = mock_name_response

        def table_side_effect(table_name: str):
            if table_name == "identity_nodes":
                return MagicMock(select=MagicMock(return_value=mock_name_query))
            return MagicMock(select=MagicMock(return_value=mock_query))

        mock_supabase_client.table.side_effect = table_side_effect

        result = await engine.get_statements_for_entity(
            entity_id="entity-123",
            matter_id="matter-456",
        )

        assert result.total_statements == 2
        assert len(result.documents) == 1  # Both from same doc
        assert result.documents[0].statement_count == 2

        # Check value extraction happened (AC #3)
        first_statement = result.documents[0].statements[0]
        assert len(first_statement.dates) == 1
        assert len(first_statement.amounts) == 1

    @pytest.mark.asyncio
    async def test_get_statements_includes_matter_filter(
        self,
        engine: StatementQueryEngine,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Should always include matter_id filter (Layer 4 isolation)."""
        mock_response = MagicMock()
        mock_response.data = []

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.contains.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_response

        # Track calls to verify matter_id filter
        eq_calls = []
        def track_eq(field, value):
            eq_calls.append((field, value))
            return mock_query

        mock_query.eq.side_effect = track_eq

        mock_name_response = MagicMock()
        mock_name_response.data = [{"canonical_name": "Test"}]

        mock_name_query = MagicMock()
        mock_name_query.eq.return_value = mock_name_query
        mock_name_query.limit.return_value = mock_name_query
        mock_name_query.execute.return_value = mock_name_response

        def table_side_effect(table_name: str):
            if table_name == "identity_nodes":
                return MagicMock(select=MagicMock(return_value=mock_name_query))
            return MagicMock(select=MagicMock(return_value=mock_query))

        mock_supabase_client.table.side_effect = table_side_effect

        await engine.get_statements_for_entity(
            entity_id="entity-123",
            matter_id="matter-456",
        )

        # Verify matter_id was used in filter
        assert ("matter_id", "matter-456") in eq_calls


class TestStatementQueryEngineWithAliases:
    """Tests for alias resolution in statement querying (AC #2)."""

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.fixture
    def engine(self, mock_supabase_client: MagicMock) -> StatementQueryEngine:
        """Create engine with mock client."""
        return StatementQueryEngine(mock_supabase_client)

    @pytest.mark.asyncio
    async def test_get_statements_with_aliases(
        self,
        engine: StatementQueryEngine,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Should include aliases in query when include_aliases=True (AC #2)."""
        with patch.object(engine, "_get_alias_entities") as mock_get_aliases:
            # Mock alias entities
            mock_get_aliases.return_value = [
                {"id": "alias-entity-1", "canonical_name": "N.D. Jobalia"},
            ]

            mock_response = MagicMock()
            mock_response.data = []

            mock_query = MagicMock()
            mock_query.eq.return_value = mock_query
            mock_query.overlaps.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            mock_query.execute.return_value = mock_response

            mock_name_response = MagicMock()
            mock_name_response.data = [{"canonical_name": "Nirav Jobalia"}]

            mock_name_query = MagicMock()
            mock_name_query.eq.return_value = mock_name_query
            mock_name_query.limit.return_value = mock_name_query
            mock_name_query.execute.return_value = mock_name_response

            def table_side_effect(table_name: str):
                if table_name == "identity_nodes":
                    return MagicMock(select=MagicMock(return_value=mock_name_query))
                return MagicMock(select=MagicMock(return_value=mock_query))

            mock_supabase_client.table.side_effect = table_side_effect

            result = await engine.get_statements_for_canonical_entity(
                entity_id="entity-123",
                matter_id="matter-456",
                include_aliases=True,
            )

            # Verify aliases were fetched
            mock_get_aliases.assert_called_once_with("entity-123", "matter-456")

            # Verify aliases are included in response
            assert "N.D. Jobalia" in result.aliases_included
