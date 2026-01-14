"""Tests for quote preservation during language policing.

Story 8-3: Language Policing (AC #6)

Test Categories:
- Double-quoted text preservation
- Single-quoted text preservation
- Citation reference preservation
- Block quote preservation
- Mixed content (quotes + unprotected text)
"""

import pytest

from app.services.safety.quote_detector import QuoteDetector, detect_quotes
from app.services.safety.language_policing import (
    LanguagePolicingService,
    get_language_policing_service,
    reset_language_policing_service,
)


@pytest.fixture
def quote_detector() -> QuoteDetector:
    """Get fresh quote detector for testing.

    Story 8-3: Task 10.1 - Test fixture.
    """
    return QuoteDetector()


@pytest.fixture
def policing_service() -> LanguagePolicingService:
    """Get fresh language policing service for testing.

    Story 8-3: Task 10.1 - Test fixture.
    """
    reset_language_policing_service()
    return get_language_policing_service()


class TestQuoteDetection:
    """Test quote detection functionality.

    Story 8-3: AC #6 - Detect direct quotes from documents.
    """

    def test_double_quotes_detected(self, quote_detector: QuoteDetector) -> None:
        """Should detect text in double quotes."""
        text = 'The witness stated "the defendant violated the agreement" in court.'
        regions = quote_detector.detect_protected_regions(text)

        assert len(regions) == 1
        assert '"the defendant violated the agreement"' in regions[0].text

    def test_single_quotes_detected(self, quote_detector: QuoteDetector) -> None:
        """Should detect text in single quotes (if long enough)."""
        text = "The document says 'the contract was breached on January 15' clearly."
        regions = quote_detector.detect_protected_regions(text)

        # Single quotes need to be at least 10 chars to avoid contractions
        assert len(regions) == 1
        assert "'the contract was breached on January 15'" in regions[0].text

    def test_short_single_quotes_ignored(self, quote_detector: QuoteDetector) -> None:
        """Short single-quoted text should be ignored (likely contractions)."""
        text = "I don't think the defendant's argument is valid."
        regions = quote_detector.detect_protected_regions(text)

        # Short quotes like "don't" should not be detected
        assert len(regions) == 0

    def test_multiple_quotes_detected(self, quote_detector: QuoteDetector) -> None:
        """Should detect multiple quotes in same text."""
        text = (
            'First witness said "guilty" and second said "not guilty". '
            'Third said "the defendant violated the contract".'
        )
        regions = quote_detector.detect_protected_regions(text)

        assert len(regions) == 3

    def test_citation_pattern_detected(self, quote_detector: QuoteDetector) -> None:
        """Should detect citation reference patterns."""
        text = "As stated in [Exhibit A, p. 5], the defendant was liable."
        regions = quote_detector.detect_protected_regions(text)

        assert len(regions) == 1
        assert regions[0].source == "Exhibit A"
        assert regions[0].page == 5

    def test_citation_with_parens_detected(self, quote_detector: QuoteDetector) -> None:
        """Should detect citation in parentheses."""
        text = "According to (Contract Agreement, page 12), the terms were clear."
        regions = quote_detector.detect_protected_regions(text)

        assert len(regions) == 1
        assert regions[0].source == "Contract Agreement"
        assert regions[0].page == 12

    def test_block_quote_detected(self, quote_detector: QuoteDetector) -> None:
        """Should detect markdown-style block quotes."""
        text = "The document states:\n> The defendant violated the agreement\n\nEnd of quote."
        regions = quote_detector.detect_protected_regions(text)

        assert len(regions) == 1
        assert "The defendant violated the agreement" in regions[0].text

    def test_no_quotes_empty_result(self, quote_detector: QuoteDetector) -> None:
        """Text without quotes should return empty regions."""
        text = "This is a plain statement without any quotes."
        regions = quote_detector.detect_protected_regions(text)

        assert len(regions) == 0


class TestQuotePreservation:
    """Test that quotes are preserved during sanitization.

    Story 8-3: AC #6 - Direct quotes must not be modified.
    """

    def test_quoted_violation_preserved(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Legal conclusion inside quotes should NOT be replaced."""
        text = 'The witness testified "the defendant violated Section 138" in court.'
        result = policing_service.sanitize_text(text)

        # The quoted text should remain unchanged
        assert '"the defendant violated Section 138"' in result.sanitized_text
        assert len(result.quotes_preserved) == 1

    def test_quoted_guilty_preserved(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """'is guilty' inside quotes should NOT be replaced."""
        text = 'The judge stated "defendant is guilty of fraud" in the ruling.'
        result = policing_service.sanitize_text(text)

        # The quoted text should remain unchanged
        assert '"defendant is guilty of fraud"' in result.sanitized_text

    def test_unquoted_violation_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Legal conclusions outside quotes should be replaced."""
        text = (
            'The witness said "defendant was present" and '
            'the defendant violated Section 138.'
        )
        result = policing_service.sanitize_text(text)

        # Quote preserved, but unquoted violation replaced
        assert '"defendant was present"' in result.sanitized_text
        assert "affected by Section 138" in result.sanitized_text
        assert 'defendant violated Section 138' not in result.sanitized_text

    def test_mixed_quotes_and_violations(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Mixed content should preserve quotes, replace others."""
        text = (
            'Document states "defendant breached contract" but also '
            'the evidence proves that more violations occurred.'
        )
        result = policing_service.sanitize_text(text)

        # Quote preserved
        assert '"defendant breached contract"' in result.sanitized_text
        # Unquoted violation replaced
        assert "suggests that" in result.sanitized_text
        assert "proves that" not in result.sanitized_text.replace(
            '"defendant breached contract"', ""
        )

    def test_citation_reference_preserved(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Citation references should be preserved."""
        text = (
            "As stated in [Exhibit A, p. 5], the defendant violated the contract. "
            "The court will rule on this matter."
        )
        result = policing_service.sanitize_text(text)

        # Citation preserved
        assert "As stated in [Exhibit A, p. 5]" in result.sanitized_text
        # But "court will rule" replaced
        assert "court may consider" in result.sanitized_text


class TestQuotePreservationMetadata:
    """Test that quote preservation metadata is properly recorded."""

    def test_quotes_preserved_list(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Preserved quotes should be recorded in result."""
        text = 'The witness said "defendant violated the agreement" in testimony.'
        result = policing_service.sanitize_text(text)

        assert len(result.quotes_preserved) == 1
        preserved = result.quotes_preserved[0]

        assert '"defendant violated the agreement"' in preserved.quoted_text
        assert preserved.start_pos >= 0
        assert preserved.end_pos > preserved.start_pos

    def test_citation_source_extracted(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Citation source info should be extracted."""
        text = "Per [Contract Agreement, page 12], the terms were violated."
        result = policing_service.sanitize_text(text)

        # Find citation-related preserved region
        citations = [q for q in result.quotes_preserved if q.source_document]

        assert len(citations) == 1
        assert citations[0].source_document == "Contract Agreement"
        assert citations[0].page_number == 12

    def test_attribution_note_for_citation(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """H1 fix: AC #6 - Citations should have attribution note with document and page.

        Story 8-3: AC #6 - "a note indicates 'Direct quote from [document name, page X]'"
        """
        text = "Per [Contract Agreement, page 12], the terms were violated."
        result = policing_service.sanitize_text(text)

        citations = [q for q in result.quotes_preserved if q.source_document]
        assert len(citations) == 1

        # AC #6: Verify attribution note format
        assert citations[0].attribution_note == "Direct quote from [Contract Agreement, p. 12]"

    def test_attribution_note_for_plain_quote(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """H1 fix: AC #6 - Plain quotes should have default attribution note.

        Story 8-3: AC #6 - Quotes without source should still indicate preservation.
        """
        text = 'The witness said "defendant violated the agreement" in court.'
        result = policing_service.sanitize_text(text)

        assert len(result.quotes_preserved) == 1
        # Plain quote has default attribution
        assert result.quotes_preserved[0].attribution_note == "Direct quote preserved verbatim"


class TestEdgeCases:
    """Test edge cases for quote preservation."""

    def test_nested_quotes_handled(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Nested quotes should be handled gracefully."""
        # This is a complex case - outer quote contains inner
        text = 'He said "The witness stated that defendant violated the law".'
        result = policing_service.sanitize_text(text)

        # Should preserve the outer quote
        assert "defendant violated the law" in result.sanitized_text

    def test_empty_quotes_ignored(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Empty quotes should be ignored."""
        text = 'The statement was "" and the defendant violated Section 138.'
        result = policing_service.sanitize_text(text)

        # Empty quote preserved, violation replaced
        assert '""' in result.sanitized_text
        assert "affected by Section 138" in result.sanitized_text

    def test_quote_at_start(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Quote at start of text should be preserved."""
        text = '"Defendant violated the contract" was the finding.'
        result = policing_service.sanitize_text(text)

        assert '"Defendant violated the contract"' in result.sanitized_text

    def test_quote_at_end(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Quote at end of text should be preserved."""
        text = 'The judge said "defendant is guilty"'
        result = policing_service.sanitize_text(text)

        assert '"defendant is guilty"' in result.sanitized_text

    def test_long_quoted_text(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Long quoted text should be fully preserved."""
        quote_content = "the defendant violated Section 138 and is guilty of breach and must pay damages"
        text = f'The ruling states "{quote_content}" according to the documents.'
        result = policing_service.sanitize_text(text)

        assert f'"{quote_content}"' in result.sanitized_text


class TestDetectQuotesModule:
    """Test the module-level detect_quotes function."""

    def test_detect_quotes_function(self) -> None:
        """Module function should work the same as detector instance."""
        text = 'The witness said "defendant violated the agreement" in court.'
        regions = detect_quotes(text)

        assert len(regions) == 1
        assert '"defendant violated the agreement"' in regions[0].text
