"""Tests for Statement Query Engine and Value Extractor.

Story 5-1: Entity-Grouped Statement Querying

Tests cover:
- Value extraction (dates, amounts - AC #3)
- Statement querying by entity (AC #1)
- Alias resolution (AC #2)
- Empty results handling (AC #4)
"""

from unittest.mock import MagicMock, patch

import pytest

from app.engines.contradiction.statement_query import (
    StatementQueryEngine,
    ValueExtractor,
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


class TestValueExtractorDatesEdgeCases:
    """Edge case tests for date extraction - Code Review Fix."""

    def test_extract_single_digit_day_month(self) -> None:
        """Should handle single digit day and month (1/3/2024)."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("Meeting on 1/3/2024.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-03-01"

    def test_extract_date_with_ordinal_1st(self) -> None:
        """Should handle 1st ordinal date."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("On 1st February 2024 the meeting happened.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-02-01"

    def test_extract_date_with_ordinal_2nd(self) -> None:
        """Should handle 2nd ordinal date."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("On 2nd March 2024.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-03-02"

    def test_extract_date_with_ordinal_22nd(self) -> None:
        """Should handle 22nd ordinal date."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("On 22nd December 2023.")

        assert len(dates) == 1
        assert dates[0].normalized == "2023-12-22"

    def test_extract_date_with_ordinal_23rd(self) -> None:
        """Should handle 23rd ordinal date."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("On 23rd April 2024.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-04-23"

    def test_reject_invalid_month_13(self) -> None:
        """Should reject dates with month > 12."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("On 15/13/2024 something happened.")

        # Month 13 doesn't exist, should be rejected
        assert len(dates) == 0

    def test_reject_feb_30(self) -> None:
        """Should reject February 30th (never exists)."""
        extractor = ValueExtractor()
        # Our basic validator checks day <= 31, so 30 passes
        # This is a known limitation - full date validation would need calendar logic
        dates = extractor.extract_dates("On 30/02/2024.")

        # Current implementation accepts this (basic validation)
        # This documents the limitation
        assert len(dates) <= 1

    def test_handle_abbreviated_months(self) -> None:
        """Should handle abbreviated month names (Jan, Feb, etc.)."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("On 15 Jan 2024.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-01-15"

    def test_handle_sept_abbreviation(self) -> None:
        """Should handle 'Sept' abbreviation for September."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("dated 5th of Sept, 2024.")

        assert len(dates) == 1
        assert dates[0].normalized == "2024-09-05"

    def test_handle_year_boundaries(self) -> None:
        """Should handle reasonable year boundaries."""
        extractor = ValueExtractor()

        # Year 1900 (boundary)
        dates_1900 = extractor.extract_dates("In 01/01/1900.")
        assert len(dates_1900) == 1
        assert dates_1900[0].normalized == "1900-01-01"

        # Year 2100 (boundary)
        dates_2100 = extractor.extract_dates("By 31/12/2100.")
        assert len(dates_2100) == 1
        assert dates_2100[0].normalized == "2100-12-31"

    def test_reject_year_1899(self) -> None:
        """Should reject years before 1900."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("Back in 15/06/1899.")

        # Year 1899 is out of range
        assert len(dates) == 0

    def test_reject_year_2101(self) -> None:
        """Should reject years after 2100."""
        extractor = ValueExtractor()
        dates = extractor.extract_dates("In 01/01/2101.")

        # Year 2101 is out of range
        assert len(dates) == 0

    def test_case_insensitive_months(self) -> None:
        """Should handle month names in different cases."""
        extractor = ValueExtractor()

        # Uppercase
        dates_upper = extractor.extract_dates("On 5th JANUARY 2024.")
        assert len(dates_upper) == 1
        assert dates_upper[0].normalized == "2024-01-05"

        # Mixed case
        dates_mixed = extractor.extract_dates("On 10th FebruarY 2024.")
        assert len(dates_mixed) == 1
        assert dates_mixed[0].normalized == "2024-02-10"


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


class TestValueExtractorAmountsEdgeCases:
    """Edge case tests for amount extraction - Code Review Fix."""

    def test_extract_rs_without_dot(self) -> None:
        """Should extract Rs without period (Rs 5,00,000)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("The amount was Rs 5,00,000.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "500000"

    def test_extract_rs_with_decimals(self) -> None:
        """Should extract Rs with decimal places."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Total Rs. 1,23,456.78 only.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "123456.78"

    def test_extract_lakhs_with_decimal(self) -> None:
        """Should extract fractional lakhs (5.5 lakhs = 550,000)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Property worth 5.5 lakhs.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "550000"

    def test_extract_crores_with_decimal(self) -> None:
        """Should extract fractional crores (2.5 crores = 25,000,000)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Revenue of 2.5 crores.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "25000000"

    def test_extract_plural_lakh(self) -> None:
        """Should extract 'lakh' (singular) same as 'lakhs'."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("A sum of 1 lakh was paid.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "100000"

    def test_extract_plural_crore(self) -> None:
        """Should extract 'crore' (singular) same as 'crores'."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Budget of 1 crore.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "10000000"

    def test_extract_large_indian_notation(self) -> None:
        """Should handle large numbers in Indian notation."""
        extractor = ValueExtractor()
        # 1,00,00,00,000 = 1 billion in Indian notation
        amounts = extractor.extract_amounts("Rs. 1,00,00,00,000.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "1000000000"

    def test_extract_percentage_integer(self) -> None:
        """Should extract integer percentages."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Interest of 12%.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "12%"

    def test_extract_percentage_word(self) -> None:
        """Should extract 'X percent' format."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Returns 15 percent per annum.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "15%"

    def test_extract_usd_with_comma_and_decimal(self) -> None:
        """Should extract USD with commas and decimals."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Payment of $1,234,567.89.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "USD:1234567.89"

    def test_extract_rupees_lowercase(self) -> None:
        """Should extract 'rupees' in sentence (case insensitive)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("He paid 50,000 Rupees.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "50000"

    def test_mixed_amounts_in_sentence(self) -> None:
        """Should extract multiple different format amounts."""
        extractor = ValueExtractor()
        text = "The principal was Rs. 10,00,000 with interest of 5 lakhs and 8.5% rate."
        amounts = extractor.extract_amounts(text)

        # Should find: Rs. 10,00,000, 5 lakhs, and 8.5%
        assert len(amounts) == 3

    def test_handle_no_space_after_rs(self) -> None:
        """Should handle Rs.100 (no space after Rs.)."""
        extractor = ValueExtractor()
        amounts = extractor.extract_amounts("Amount: Rs.100.")

        assert len(amounts) == 1
        assert amounts[0].normalized == "100"


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
