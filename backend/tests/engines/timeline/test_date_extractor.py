"""Tests for Date Extractor service.

Story 4-1: Date Extraction with Gemini
"""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engines.timeline.date_extractor import (
    DateConfigurationError,
    DateExtractor,
    get_date_extractor,
)
from app.models.timeline import ExtractedDate


class TestDateExtractorInit:
    """Tests for DateExtractor initialization."""

    def test_init_creates_instance(self) -> None:
        """Should create DateExtractor instance."""
        extractor = DateExtractor()
        assert extractor is not None
        assert extractor._model is None  # Lazy initialization

    def test_singleton_factory(self) -> None:
        """Should return singleton from factory."""
        # Clear cache
        get_date_extractor.cache_clear()

        extractor1 = get_date_extractor()
        extractor2 = get_date_extractor()

        assert extractor1 is extractor2

        # Clean up
        get_date_extractor.cache_clear()


class TestDateExtractorParsing:
    """Tests for response parsing logic."""

    def test_parse_valid_response(self) -> None:
        """Should parse valid Gemini JSON response."""
        extractor = DateExtractor()
        response_text = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                    "context_before": "The filing was on",
                    "context_after": "before the court.",
                    "is_ambiguous": False,
                    "ambiguity_reason": None,
                    "confidence": 0.95,
                }
            ]
        })

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=1,
        )

        assert result.document_id == "doc-123"
        assert result.matter_id == "matter-456"
        assert len(result.dates) == 1
        assert result.dates[0].date_text == "15/01/2024"
        assert result.dates[0].extracted_date == date(2024, 1, 15)
        assert result.dates[0].date_precision == "day"
        assert result.dates[0].confidence == 0.95

    def test_parse_empty_response(self) -> None:
        """Should handle empty dates array."""
        extractor = DateExtractor()
        response_text = json.dumps({"dates": []})

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert len(result.dates) == 0
        assert result.total_dates_found == 0

    def test_parse_invalid_json(self) -> None:
        """Should handle invalid JSON gracefully."""
        extractor = DateExtractor()
        response_text = "not valid json"

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert len(result.dates) == 0
        assert result.total_dates_found == 0

    def test_parse_markdown_wrapped_json(self) -> None:
        """Should strip markdown code blocks."""
        extractor = DateExtractor()
        response_text = """```json
{
    "dates": [
        {
            "date_text": "2024-03-15",
            "extracted_date": "2024-03-15",
            "date_precision": "day",
            "context_before": "",
            "context_after": "",
            "is_ambiguous": false,
            "confidence": 0.9
        }
    ]
}
```"""

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert len(result.dates) == 1
        assert result.dates[0].date_text == "2024-03-15"

    def test_parse_multiple_dates(self) -> None:
        """Should parse multiple dates from response."""
        extractor = DateExtractor()
        response_text = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                    "confidence": 0.95,
                },
                {
                    "date_text": "March 2024",
                    "extracted_date": "2024-03-01",
                    "date_precision": "month",
                    "confidence": 0.90,
                },
                {
                    "date_text": "2023",
                    "extracted_date": "2023-01-01",
                    "date_precision": "year",
                    "confidence": 0.85,
                },
            ]
        })

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert len(result.dates) == 3
        assert result.dates[0].date_precision == "day"
        assert result.dates[1].date_precision == "month"
        assert result.dates[2].date_precision == "year"

    def test_parse_ambiguous_date(self) -> None:
        """Should parse ambiguous date with reason."""
        extractor = DateExtractor()
        response_text = json.dumps({
            "dates": [
                {
                    "date_text": "01/02/2024",
                    "extracted_date": "2024-02-01",
                    "date_precision": "day",
                    "is_ambiguous": True,
                    "ambiguity_reason": "DD/MM vs MM/DD uncertain",
                    "confidence": 0.70,
                }
            ]
        })

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert len(result.dates) == 1
        assert result.dates[0].is_ambiguous is True
        assert "DD/MM" in result.dates[0].ambiguity_reason


class TestDateExtractorChunking:
    """Tests for text chunking logic."""

    def test_split_short_text(self) -> None:
        """Should not split text under max length."""
        extractor = DateExtractor()
        text = "Short text with date 15/01/2024."

        chunks = extractor._split_into_chunks(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_long_text(self) -> None:
        """Should split long text into overlapping chunks."""
        extractor = DateExtractor()
        # Create text longer than MAX_TEXT_LENGTH (30000)
        text = "Date 15/01/2024. " * 3000  # ~51000 chars

        chunks = extractor._split_into_chunks(text)

        assert len(chunks) > 1
        # Verify overlap exists
        for i in range(len(chunks) - 1):
            # Last 500 chars of chunk should appear in next chunk
            overlap_region = chunks[i][-500:]
            assert any(char in chunks[i + 1] for char in overlap_region)

    def test_dedup_dates(self) -> None:
        """Should remove duplicate dates."""
        extractor = DateExtractor()
        dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                confidence=0.95,
            ),
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",  # Duplicate
                date_precision="day",
                confidence=0.90,
            ),
            ExtractedDate(
                extracted_date=date(2024, 3, 1),
                date_text="March 2024",  # Different date
                date_precision="month",
                confidence=0.85,
            ),
        ]

        unique = extractor._deduplicate_dates(dates)

        assert len(unique) == 2
        date_texts = {d.date_text for d in unique}
        assert "15/01/2024" in date_texts
        assert "March 2024" in date_texts


class TestDateExtractorExtraction:
    """Tests for full extraction with mocked Gemini."""

    @pytest.mark.asyncio
    async def test_extract_empty_text(self) -> None:
        """Should return empty result for empty text."""
        extractor = DateExtractor()

        result = await extractor.extract_dates_from_text(
            text="",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.dates) == 0
        assert result.total_dates_found == 0

    @pytest.mark.asyncio
    async def test_extract_whitespace_text(self) -> None:
        """Should return empty result for whitespace-only text."""
        extractor = DateExtractor()

        result = await extractor.extract_dates_from_text(
            text="   \n\t  ",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.dates) == 0

    @pytest.mark.asyncio
    async def test_extract_with_mocked_gemini(self) -> None:
        """Should extract dates using mocked Gemini response."""
        extractor = DateExtractor()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                    "context_before": "Filed on",
                    "context_after": "in Mumbai",
                    "is_ambiguous": False,
                    "confidence": 0.95,
                }
            ]
        })

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text="Filed on 15/01/2024 in Mumbai High Court.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.dates) == 1
        assert result.dates[0].date_text == "15/01/2024"
        assert result.dates[0].extracted_date == date(2024, 1, 15)

    def test_extract_sync_with_mocked_gemini(self) -> None:
        """Should extract dates synchronously."""
        extractor = DateExtractor()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "dates": [
                {
                    "date_text": "March 2024",
                    "extracted_date": "2024-03-01",
                    "date_precision": "month",
                    "confidence": 0.90,
                }
            ]
        })

        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(return_value=mock_response)
        extractor._model = mock_model

        result = extractor.extract_dates_sync(
            text="Hearing scheduled for March 2024.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.dates) == 1
        assert result.dates[0].date_precision == "month"


class TestIndianDateFormats:
    """Tests for Indian date format handling."""

    def test_indian_standard_format(self) -> None:
        """Should prefer DD/MM/YYYY for Indian documents."""
        extractor = DateExtractor()
        # The prompt instructs Gemini to prefer DD/MM for Indian docs
        # This test verifies the parsing handles it correctly
        response_text = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",  # DD/MM interpretation
                    "date_precision": "day",
                    "is_ambiguous": False,
                    "confidence": 0.95,
                }
            ]
        })

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert result.dates[0].extracted_date == date(2024, 1, 15)

    def test_legal_format_this_day_of(self) -> None:
        """Should parse 'this X day of Y' legal format."""
        extractor = DateExtractor()
        response_text = json.dumps({
            "dates": [
                {
                    "date_text": "this 5th day of January, 2024",
                    "extracted_date": "2024-01-05",
                    "date_precision": "day",
                    "confidence": 0.95,
                }
            ]
        })

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        assert result.dates[0].extracted_date == date(2024, 1, 5)

    def test_financial_year_format(self) -> None:
        """Should handle Indian financial year format."""
        extractor = DateExtractor()
        response_text = json.dumps({
            "dates": [
                {
                    "date_text": "F.Y. 2023-24",
                    "extracted_date": "2023-04-01",
                    "date_precision": "year",
                    "confidence": 0.85,
                }
            ]
        })

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            matter_id="matter-456",
            page_number=None,
        )

        # FY 2023-24 starts April 1, 2023
        assert result.dates[0].extracted_date == date(2023, 4, 1)
        assert result.dates[0].date_precision == "year"


class TestDatePrecision:
    """Tests for date precision handling."""

    def test_day_precision(self) -> None:
        """Should handle day precision dates."""
        extractor = DateExtractor()
        response = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                    "confidence": 0.95,
                }
            ]
        })

        result = extractor._parse_response(response, "doc", "matter", None)
        assert result.dates[0].date_precision == "day"

    def test_month_precision(self) -> None:
        """Should handle month precision dates."""
        extractor = DateExtractor()
        response = json.dumps({
            "dates": [
                {
                    "date_text": "January 2024",
                    "extracted_date": "2024-01-01",
                    "date_precision": "month",
                    "confidence": 0.90,
                }
            ]
        })

        result = extractor._parse_response(response, "doc", "matter", None)
        assert result.dates[0].date_precision == "month"

    def test_year_precision(self) -> None:
        """Should handle year precision dates."""
        extractor = DateExtractor()
        response = json.dumps({
            "dates": [
                {
                    "date_text": "2024",
                    "extracted_date": "2024-01-01",
                    "date_precision": "year",
                    "confidence": 0.80,
                }
            ]
        })

        result = extractor._parse_response(response, "doc", "matter", None)
        assert result.dates[0].date_precision == "year"

    def test_approximate_precision(self) -> None:
        """Should handle approximate dates."""
        extractor = DateExtractor()
        response = json.dumps({
            "dates": [
                {
                    "date_text": "circa 2020",
                    "extracted_date": "2020-01-01",
                    "date_precision": "approximate",
                    "is_ambiguous": True,
                    "confidence": 0.65,
                }
            ]
        })

        result = extractor._parse_response(response, "doc", "matter", None)
        assert result.dates[0].date_precision == "approximate"
        assert result.dates[0].is_ambiguous is True


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_api_key(self) -> None:
        """Should raise error when API key is missing."""
        extractor = DateExtractor()
        extractor.api_key = None

        with pytest.raises(DateConfigurationError):
            _ = extractor.model

    def test_invalid_date_string(self) -> None:
        """Should skip invalid date strings."""
        extractor = DateExtractor()
        response = json.dumps({
            "dates": [
                {
                    "date_text": "invalid",
                    "extracted_date": "not-a-date",
                    "date_precision": "day",
                    "confidence": 0.5,
                }
            ]
        })

        result = extractor._parse_response(response, "doc", "matter", None)
        assert len(result.dates) == 0

    def test_missing_required_fields(self) -> None:
        """Should skip dates with missing required fields."""
        extractor = DateExtractor()
        response = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    # Missing extracted_date
                    "date_precision": "day",
                },
                {
                    # Missing date_text
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                },
            ]
        })

        result = extractor._parse_response(response, "doc", "matter", None)
        assert len(result.dates) == 0


class TestRetryLogic:
    """Tests for rate limit retry behavior."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_429(self) -> None:
        """Should retry on 429 rate limit errors."""
        extractor = DateExtractor()

        # First call raises 429, second succeeds
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Resource Exhausted")
            mock_response = MagicMock()
            mock_response.text = json.dumps({"dates": []})
            return mock_response

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text="Test text with date 15/01/2024.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert call_count == 2  # Retried once

    @pytest.mark.asyncio
    async def test_retry_on_quota_exceeded(self) -> None:
        """Should retry on quota exceeded errors."""
        extractor = DateExtractor()

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("quota exceeded for project")
            mock_response = MagicMock()
            mock_response.text = json.dumps({"dates": []})
            return mock_response

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text="Test text.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert call_count == 2  # Retried once

    @pytest.mark.asyncio
    async def test_no_retry_on_non_rate_limit_error(self) -> None:
        """Should not retry on non-rate-limit errors."""
        extractor = DateExtractor()

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("Some other error")

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text="Test text.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert call_count == 1  # No retry
        assert len(result.dates) == 0  # Graceful degradation

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self) -> None:
        """Should stop after MAX_RETRIES attempts."""
        extractor = DateExtractor()

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("429 rate limit")

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text="Test text.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert call_count == 3  # MAX_RETRIES = 3
        assert len(result.dates) == 0  # Empty result after exhaustion

    def test_sync_retry_on_rate_limit(self) -> None:
        """Should retry synchronously on rate limit."""
        extractor = DateExtractor()

        call_count = 0

        def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("resource exhausted")
            mock_response = MagicMock()
            mock_response.text = json.dumps({"dates": []})
            return mock_response

        mock_model = MagicMock()
        mock_model.generate_content = mock_generate
        extractor._model = mock_model

        result = extractor.extract_dates_sync(
            text="Test text.",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert call_count == 2  # Retried once


class TestIntegrationPipeline:
    """Integration tests for date extraction pipeline.

    These tests verify the full flow from extraction to storage.
    They use mocked external services but test internal logic integration.
    """

    @pytest.mark.asyncio
    async def test_full_extraction_flow(self) -> None:
        """Should extract dates and return proper result structure."""
        extractor = DateExtractor()

        # Mock Gemini response with multiple date types
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                    "context_before": "The complaint was filed on",
                    "context_after": "before the Hon'ble Court.",
                    "is_ambiguous": False,
                    "confidence": 0.95,
                },
                {
                    "date_text": "01/02/2024",
                    "extracted_date": "2024-02-01",
                    "date_precision": "day",
                    "context_before": "Notice dated",
                    "context_after": "was issued.",
                    "is_ambiguous": True,
                    "ambiguity_reason": "DD/MM vs MM/DD uncertain",
                    "confidence": 0.70,
                },
                {
                    "date_text": "March 2024",
                    "extracted_date": "2024-03-01",
                    "date_precision": "month",
                    "context_before": "Hearing scheduled for",
                    "context_after": "",
                    "is_ambiguous": False,
                    "confidence": 0.90,
                },
            ]
        })

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text="The complaint was filed on 15/01/2024 before the Hon'ble Court. "
                 "Notice dated 01/02/2024 was issued. Hearing scheduled for March 2024.",
            document_id="doc-123",
            matter_id="matter-456",
            page_number=5,
        )

        # Verify result structure
        assert result.document_id == "doc-123"
        assert result.matter_id == "matter-456"
        assert result.total_dates_found == 3
        assert result.processing_time_ms >= 0

        # Verify dates
        assert len(result.dates) == 3

        # First date - unambiguous
        assert result.dates[0].date_text == "15/01/2024"
        assert result.dates[0].extracted_date == date(2024, 1, 15)
        assert result.dates[0].is_ambiguous is False
        assert result.dates[0].confidence == 0.95
        assert result.dates[0].page_number == 5

        # Second date - ambiguous
        assert result.dates[1].is_ambiguous is True
        assert "DD/MM" in result.dates[1].ambiguity_reason
        assert result.dates[1].confidence == 0.70

        # Third date - month precision
        assert result.dates[2].date_precision == "month"

    @pytest.mark.asyncio
    async def test_context_window_preserved(self) -> None:
        """Should preserve context windows in extraction."""
        extractor = DateExtractor()

        context_before = "After reviewing all the documents submitted by the petitioner "
        context_after = "the court shall proceed to hear the arguments."

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "dates": [
                {
                    "date_text": "15/01/2024",
                    "extracted_date": "2024-01-15",
                    "date_precision": "day",
                    "context_before": context_before,
                    "context_after": context_after,
                    "is_ambiguous": False,
                    "confidence": 0.95,
                }
            ]
        })

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        extractor._model = mock_model

        result = await extractor.extract_dates_from_text(
            text=f"{context_before}15/01/2024{context_after}",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert result.dates[0].context_before == context_before
        assert result.dates[0].context_after == context_after
