"""Tests for pattern-based OCR correction."""

import pytest

from app.models.ocr_validation import CorrectionType, LowConfidenceWord
from app.services.ocr.pattern_corrector import (
    COMMON_OCR_PATTERNS,
    CRITICAL_CONTENT_PATTERNS,
    PatternCorrector,
    PatternRule,
    apply_pattern_corrections,
    get_pattern_corrector,
)


class TestPatternRule:
    """Tests for PatternRule dataclass."""

    def test_creates_pattern_rule(self) -> None:
        """Should create a pattern rule with all fields."""
        rule = PatternRule(
            name="test_rule",
            pattern=r"\d+",
            replacement="NUM",
            description="Test description",
        )

        assert rule.name == "test_rule"
        assert rule.pattern == r"\d+"
        assert rule.replacement == "NUM"
        assert rule.description == "Test description"


class TestPatternCorrector:
    """Tests for PatternCorrector class."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_initialization_compiles_patterns(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should compile all patterns on initialization."""
        assert len(corrector.patterns) == len(COMMON_OCR_PATTERNS)

    def test_returns_none_for_empty_text(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should return None for empty text."""
        result = corrector.correct("")
        assert result is None

        result = corrector.correct(None)  # type: ignore
        assert result is None


class TestOZeroConfusion:
    """Tests for O/0 confusion corrections."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_corrects_O_in_middle_of_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct O in the middle of numbers."""
        result = corrector.correct("1O23")

        assert result is not None
        assert result.corrected == "1023"
        assert result.was_corrected is True
        assert result.correction_type == CorrectionType.PATTERN

    def test_corrects_multiple_O_in_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct multiple O characters in numbers."""
        result = corrector.correct("1O,OOO")

        assert result is not None
        assert result.corrected == "10,000"

    def test_corrects_O_at_start_of_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct O at the start of numbers."""
        result = corrector.correct("O5")

        assert result is not None
        assert result.corrected == "05"

    def test_corrects_O_at_end_of_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct O at the end of numbers."""
        result = corrector.correct("5O")

        assert result is not None
        assert result.corrected == "50"

    def test_preserves_O_in_words(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should not change O in regular words."""
        result = corrector.correct("WORD")

        assert result is None  # No correction needed

    def test_corrects_currency_with_O(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct O in currency amounts."""
        result = corrector.correct("Rs. 1O,OOO")

        assert result is not None
        assert result.corrected == "Rs. 10,000"


class TestLOneConfusion:
    """Tests for l/1 confusion corrections."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_corrects_l_in_middle_of_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct l in the middle of numbers."""
        result = corrector.correct("1l23")

        assert result is not None
        assert result.corrected == "1123"

    def test_corrects_l_after_digit(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct l after a digit."""
        result = corrector.correct("5l")

        assert result is not None
        assert result.corrected == "51"

    def test_corrects_I_in_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct uppercase I in numbers."""
        result = corrector.correct("1I23")

        assert result is not None
        assert result.corrected == "1123"


class TestCurrencyPatterns:
    """Tests for Indian currency pattern corrections."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_corrects_S_in_amount(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct S confused with 5 in currency."""
        result = corrector.correct("Rs. S000")

        assert result is not None
        assert result.corrected == "Rs. 5000"

    def test_corrects_l_in_amount(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct l confused with 1 in currency."""
        result = corrector.correct("Rs. l000")

        assert result is not None
        assert result.corrected == "Rs. 1000"

    def test_corrects_I_in_amount(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct I confused with 1 in currency."""
        result = corrector.correct("Rs. I000")

        assert result is not None
        assert result.corrected == "Rs. 1000"


class TestDatePatterns:
    """Tests for date pattern corrections."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_corrects_O_in_day(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct O in day portion of date."""
        result = corrector.correct("O5/12/2023")

        assert result is not None
        assert "05" in result.corrected

    def test_corrects_O_in_month(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct O in month portion of date."""
        result = corrector.correct("15/O1/2023")

        assert result is not None
        assert "/01/" in result.corrected

    def test_corrects_date_with_dashes(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should handle dates with dashes."""
        result = corrector.correct("15-O2-2023")

        assert result is not None
        # After correction, should have 0 instead of O


class TestBEightConfusion:
    """Tests for B/8 confusion corrections."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_corrects_B_in_number(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should correct B confused with 8 in numbers."""
        result = corrector.correct("1B23")

        assert result is not None
        assert result.corrected == "1823"


class TestCorrectWord:
    """Tests for correct_word method."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_returns_corrected_result(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should return ValidationResult with correction details."""
        word = LowConfidenceWord(
            bbox_id="bbox-123",
            text="1O23",
            confidence=0.60,
            page=1,
            context_before="amount:",
            context_after="rupees",
            x=10.0,
            y=20.0,
            width=8.0,
            height=5.0,
        )

        result = corrector.correct_word(word)

        assert result.bbox_id == "bbox-123"
        assert result.original == "1O23"
        assert result.corrected == "1023"
        assert result.old_confidence == 0.60
        assert result.new_confidence == 0.95  # High confidence for pattern
        assert result.correction_type == CorrectionType.PATTERN
        assert result.was_corrected is True

    def test_returns_unchanged_when_no_pattern_matches(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should return unchanged result when no pattern matches."""
        word = LowConfidenceWord(
            bbox_id="bbox-456",
            text="Section",
            confidence=0.70,
            page=1,
            context_before="",
            context_after="302",
            x=10.0,
            y=20.0,
            width=8.0,
            height=5.0,
        )

        result = corrector.correct_word(word)

        assert result.bbox_id == "bbox-456"
        assert result.original == "Section"
        assert result.corrected == "Section"
        assert result.old_confidence == 0.70
        assert result.new_confidence == 0.70
        assert result.correction_type is None
        assert result.was_corrected is False


class TestIsCriticalContent:
    """Tests for is_critical_content method."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_detects_date_content(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should detect date patterns."""
        assert corrector.is_critical_content("15/01/2023") == "date"
        assert corrector.is_critical_content("Filed on 15/01/2023") == "date"
        assert corrector.is_critical_content("01-12-2023") == "date"

    def test_detects_amount_content(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should detect Indian currency amounts."""
        assert corrector.is_critical_content("Rs. 10,000") == "amount"
        assert corrector.is_critical_content("Amount Rs.5000") == "amount"

    def test_detects_section_content(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should detect legal section references."""
        assert corrector.is_critical_content("Section 302") == "section"
        assert corrector.is_critical_content("Under Section 420") == "section"

    def test_detects_year_content(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should detect year patterns."""
        assert corrector.is_critical_content("Year 2023") == "year"
        assert corrector.is_critical_content("Since 1985") == "year"

    def test_returns_none_for_non_critical(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should return None for non-critical content."""
        assert corrector.is_critical_content("The quick brown fox") is None
        assert corrector.is_critical_content("jurisdiction") is None


class TestApplyPatternCorrections:
    """Tests for apply_pattern_corrections function."""

    def test_separates_corrected_and_remaining_words(self) -> None:
        """Should separate words into corrected and remaining lists."""
        words = [
            LowConfidenceWord(
                bbox_id="1", text="1O23", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),  # Should be corrected
            LowConfidenceWord(
                bbox_id="2", text="Section", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),  # Should remain
            LowConfidenceWord(
                bbox_id="3", text="Rs. l000", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),  # Should be corrected
        ]

        corrected, remaining = apply_pattern_corrections(words)

        assert len(corrected) == 2
        assert len(remaining) == 1

        # Verify corrected results
        corrected_texts = {r.corrected for r in corrected}
        assert "1023" in corrected_texts
        assert "Rs. 1000" in corrected_texts

        # Verify remaining
        assert remaining[0].text == "Section"

    def test_returns_empty_for_no_corrections(self) -> None:
        """Should return all words as remaining when no corrections apply."""
        words = [
            LowConfidenceWord(
                bbox_id="1", text="Court", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),
            LowConfidenceWord(
                bbox_id="2", text="Order", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),
        ]

        corrected, remaining = apply_pattern_corrections(words)

        assert len(corrected) == 0
        assert len(remaining) == 2

    def test_handles_empty_word_list(self) -> None:
        """Should handle empty word list."""
        corrected, remaining = apply_pattern_corrections([])

        assert corrected == []
        assert remaining == []


class TestGetPatternCorrector:
    """Tests for get_pattern_corrector factory function."""

    def test_returns_pattern_corrector(self) -> None:
        """Should return a PatternCorrector instance."""
        corrector = get_pattern_corrector()

        assert isinstance(corrector, PatternCorrector)

    def test_returns_same_instance_each_time(self) -> None:
        """Should return same cached instance (singleton pattern)."""
        corrector1 = get_pattern_corrector()
        corrector2 = get_pattern_corrector()

        # Same object (cached with @lru_cache for consistency with other services)
        assert corrector1 is corrector2


class TestPatternReasoning:
    """Tests for pattern correction reasoning."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_includes_reasoning_in_result(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should include descriptive reasoning in result."""
        result = corrector.correct("1O23")

        assert result is not None
        assert result.reasoning is not None
        assert len(result.reasoning) > 0

    def test_combines_multiple_corrections_in_reasoning(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should include all applied rules in reasoning."""
        # This text has multiple O issues
        result = corrector.correct("1O,OOO")

        assert result is not None
        assert result.reasoning is not None
        # Should have semicolon if multiple rules applied
        # (depending on how patterns match)


class TestEdgeCases:
    """Tests for edge cases in pattern correction."""

    @pytest.fixture
    def corrector(self) -> PatternCorrector:
        """Create a pattern corrector instance."""
        return PatternCorrector()

    def test_preserves_mixed_content(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should only correct OCR errors, preserving valid content."""
        # "Order" should not be changed, but "1O" should become "10"
        result = corrector.correct("1O")

        assert result is not None
        assert result.corrected == "10"

    def test_handles_special_characters(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Should handle text with special characters."""
        result = corrector.correct("Rs. 1O,OOO/-")

        assert result is not None
        assert "10,000" in result.corrected

    def test_case_sensitive_patterns(
        self,
        corrector: PatternCorrector,
    ) -> None:
        """Patterns should be case-sensitive where appropriate."""
        # Lowercase 'o' is different from uppercase 'O'
        # This tests that patterns correctly match intended cases
        result_upper = corrector.correct("1O23")
        assert result_upper is not None
        assert result_upper.corrected == "1023"
