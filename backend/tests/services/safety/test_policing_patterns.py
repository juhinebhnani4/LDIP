"""Tests for language policing patterns.

Story 8-3: Language Policing (AC #1-4)

Test Categories:
- Legal conclusions (AC #1): "violated Section X" → "affected by Section X"
- Guilt patterns (AC #2): "defendant is guilty" → "defendant's liability regarding"
- Prediction patterns (AC #3): "the court will rule" → "the court may consider"
- Proof patterns (AC #4): "proves that" → "suggests that"
- Quote preservation (AC #6): Direct quotes should NOT be modified
"""

import pytest

from app.services.safety.language_policing import (
    LanguagePolicingService,
    get_language_policing_service,
    reset_language_policing_service,
)


@pytest.fixture
def policing_service() -> LanguagePolicingService:
    """Get fresh language policing service for testing.

    Story 8-3: Task 9.1 - Test fixture.
    """
    reset_language_policing_service()
    return get_language_policing_service()


class TestLegalConclusionPatterns:
    """Test legal conclusion replacement patterns.

    Story 8-3: AC #1 - Replace "violated Section X" with "affected by Section X"
    """

    def test_violated_section_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'violated Section 138' with 'affected by Section 138'.

        Story 8-3: Task 2.2
        """
        result = policing_service.sanitize_text(
            "The defendant violated Section 138 of the NI Act."
        )
        assert "affected by Section 138" in result.sanitized_text
        assert "violated Section 138" not in result.sanitized_text
        assert len(result.replacements_made) > 0

    def test_violated_act_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'violated Act 245' with 'affected by Act 245'.

        Story 8-3: Task 2.2 - Tests Act variant
        """
        result = policing_service.sanitize_text("The company violated Act 245.")
        assert "affected by Act 245" in result.sanitized_text
        assert "violated Act 245" not in result.sanitized_text

    def test_breached_contract_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'breached the contract' with 'regarding the contract terms'.

        Story 8-3: Task 2.2
        """
        result = policing_service.sanitize_text("The party breached the contract.")
        assert "regarding the contract terms" in result.sanitized_text
        assert "breached the contract" not in result.sanitized_text

    def test_violated_agreement_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'violated the agreement' with 'regarding the agreement terms'.

        Story 8-3: Task 2.2
        """
        result = policing_service.sanitize_text("The defendant violated the agreement.")
        assert "regarding the agreement terms" in result.sanitized_text
        assert "violated the agreement" not in result.sanitized_text


class TestGuiltPatterns:
    """Test guilt/liability pattern replacements.

    Story 8-3: AC #2 - Replace "defendant is guilty" with "defendant's liability regarding"
    """

    def test_defendant_guilty_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'defendant is guilty' with 'defendant's liability regarding'.

        Story 8-3: Task 2.3
        """
        result = policing_service.sanitize_text("The defendant is guilty of fraud.")
        assert "defendant's liability regarding" in result.sanitized_text
        assert "defendant is guilty" not in result.sanitized_text

    def test_accused_guilty_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'accused is guilty' with 'accused's liability regarding'.

        Story 8-3: Task 2.3 - Tests accused variant
        """
        result = policing_service.sanitize_text("The accused is guilty of the offense.")
        assert "accused's liability regarding" in result.sanitized_text
        assert "accused is guilty" not in result.sanitized_text

    def test_plaintiff_entitled_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'plaintiff is entitled' with 'plaintiff's potential entitlement'.

        Story 8-3: Task 2.3
        """
        result = policing_service.sanitize_text(
            "The plaintiff is entitled to damages."
        )
        assert "plaintiff's potential entitlement" in result.sanitized_text
        assert "plaintiff is entitled" not in result.sanitized_text

    def test_party_at_fault_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'defendant is at fault' with 'defendant's potential responsibility'.

        Story 8-3: Task 2.3
        """
        result = policing_service.sanitize_text("The defendant is at fault.")
        assert "defendant's potential responsibility" in result.sanitized_text
        assert "defendant is at fault" not in result.sanitized_text


class TestPredictionPatterns:
    """Test prediction pattern replacements.

    Story 8-3: AC #3 - Replace "the court will rule" with "the court may consider"
    """

    def test_court_will_rule_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'court will rule' with 'court may consider'.

        Story 8-3: Task 2.4
        """
        result = policing_service.sanitize_text(
            "The court will rule against the defendant."
        )
        assert "court may consider" in result.sanitized_text
        assert "court will rule" not in result.sanitized_text

    def test_judge_will_decide_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'judge will decide' with 'judge may'.

        Story 8-3: Task 2.4
        """
        result = policing_service.sanitize_text("The judge will decide the case.")
        assert "judge may" in result.sanitized_text
        assert "judge will decide" not in result.sanitized_text

    def test_tribunal_will_grant_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'tribunal will grant' with 'tribunal may consider'.

        Story 8-3: Task 2.4
        """
        result = policing_service.sanitize_text("The tribunal will grant the relief.")
        assert "tribunal may consider" in result.sanitized_text
        assert "tribunal will grant" not in result.sanitized_text


class TestProofPatterns:
    """Test proof/evidence pattern replacements.

    Story 8-3: AC #4 - Replace "proves that" with "suggests that"
    """

    def test_proves_that_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'proves that' with 'suggests that'.

        Story 8-3: Task 2.5
        """
        result = policing_service.sanitize_text(
            "The evidence proves that defendant is liable."
        )
        assert "suggests that" in result.sanitized_text
        assert "proves that" not in result.sanitized_text

    def test_establishes_that_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'establishes that' with 'indicates that'.

        Story 8-3: Task 2.5
        """
        result = policing_service.sanitize_text(
            "The document establishes that fraud occurred."
        )
        assert "indicates that" in result.sanitized_text
        assert "establishes that" not in result.sanitized_text

    def test_demonstrates_that_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'demonstrates that' with 'may indicate that'.

        Story 8-3: Task 2.5
        """
        result = policing_service.sanitize_text(
            "The timeline demonstrates that breach occurred."
        )
        assert "may indicate that" in result.sanitized_text
        assert "demonstrates that" not in result.sanitized_text

    def test_clearly_shows_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'clearly shows' with 'appears to show'.

        Story 8-3: Task 2.5
        """
        result = policing_service.sanitize_text("The evidence clearly shows the fraud.")
        assert "appears to show" in result.sanitized_text
        assert "clearly shows" not in result.sanitized_text

    def test_conclusively_proves_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'conclusively proves' with 'may suggest'.

        Story 8-3: Task 2.5
        """
        result = policing_service.sanitize_text("This conclusively proves the breach.")
        assert "may suggest" in result.sanitized_text
        assert "conclusively proves" not in result.sanitized_text


class TestDefinitivePatterns:
    """Test definitive statement pattern replacements.

    Story 8-3: Task 2.6 - Replace definitive language with tentative language
    """

    def test_is_liable_for_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'is liable for' with 'regarding potential liability for'.

        Story 8-3: Task 2.6
        """
        result = policing_service.sanitize_text("The defendant is liable for damages.")
        assert "regarding potential liability for" in result.sanitized_text
        assert "is liable for" not in result.sanitized_text

    def test_is_responsible_for_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'is responsible for' with 'regarding responsibility for'.

        Story 8-3: Task 2.6
        """
        result = policing_service.sanitize_text("The party is responsible for the loss.")
        assert "regarding responsibility for" in result.sanitized_text
        assert "is responsible for" not in result.sanitized_text

    def test_must_pay_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'must pay' with 'may be required to pay'.

        Story 8-3: Task 2.6
        """
        result = policing_service.sanitize_text("The defendant must pay compensation.")
        assert "may be required to pay" in result.sanitized_text
        assert "must pay" not in result.sanitized_text


class TestLiabilityPatterns:
    """Test liability-specific pattern replacements.

    Story 8-3: Task 2.7 - Replace liability conclusions with observations
    """

    def test_owes_damages_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'owes damages' with 'regarding potential damages'.

        Story 8-3: Task 2.7
        """
        result = policing_service.sanitize_text("The defendant owes damages.")
        assert "regarding potential damages" in result.sanitized_text
        assert "owes damages" not in result.sanitized_text

    def test_is_negligent_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'is negligent' with 'regarding potential negligence'.

        Story 8-3: Task 2.7
        """
        result = policing_service.sanitize_text("The doctor is negligent.")
        assert "regarding potential negligence" in result.sanitized_text
        assert "is negligent" not in result.sanitized_text

    def test_committed_fraud_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'committed fraud' with 'regarding potential fraud'.

        Story 8-3: Task 2.7
        """
        result = policing_service.sanitize_text("The company committed fraud.")
        assert "regarding potential fraud" in result.sanitized_text
        assert "committed fraud" not in result.sanitized_text

    def test_in_breach_of_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Should replace 'in breach of' with 'regarding compliance with'.

        Story 8-3: Task 2.7
        """
        result = policing_service.sanitize_text("The party was in breach of contract.")
        assert "regarding compliance with" in result.sanitized_text
        assert "in breach of" not in result.sanitized_text


class TestSafeTextPassThrough:
    """Test that safe text passes through unchanged.

    Story 8-3: Ensure factual text is not modified unnecessarily.
    """

    def test_factual_statement_unchanged(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Factual statements without legal conclusions should pass through."""
        original = "The loan was disbursed on January 15, 2023."
        result = policing_service.sanitize_text(original)
        assert result.sanitized_text == original
        assert len(result.replacements_made) == 0

    def test_citation_reference_unchanged(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Citation references should pass through unchanged."""
        original = "Section 138 of the NI Act prescribes penalties for bounced cheques."
        result = policing_service.sanitize_text(original)
        assert result.sanitized_text == original
        assert len(result.replacements_made) == 0

    def test_entity_mention_unchanged(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Entity mentions should pass through unchanged."""
        original = "The witness John Smith testified on March 5, 2024."
        result = policing_service.sanitize_text(original)
        assert result.sanitized_text == original
        assert len(result.replacements_made) == 0


class TestCaseInsensitivity:
    """Test that pattern matching is case-insensitive.

    Story 8-3: Patterns should match regardless of case.
    """

    def test_uppercase_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Pattern matching should be case-insensitive (uppercase)."""
        result = policing_service.sanitize_text(
            "The evidence PROVES THAT the defendant breached the contract."
        )
        assert "suggests that" in result.sanitized_text.lower()
        assert "proves that" not in result.sanitized_text.lower()

    def test_mixed_case_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Pattern matching should be case-insensitive (mixed case)."""
        result = policing_service.sanitize_text("The defendant Is Guilty of fraud.")
        assert "liability regarding" in result.sanitized_text.lower()
        assert "is guilty" not in result.sanitized_text.lower()


class TestMultipleReplacements:
    """Test text with multiple patterns that need replacement."""

    def test_multiple_patterns_replaced(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Multiple patterns in same text should all be replaced."""
        text = (
            "The evidence proves that defendant violated Section 138. "
            "The court will rule against him and he must pay damages."
        )
        result = policing_service.sanitize_text(text)

        assert "suggests that" in result.sanitized_text
        assert "affected by Section 138" in result.sanitized_text
        assert "may consider" in result.sanitized_text
        assert "may be required to pay" in result.sanitized_text
        assert len(result.replacements_made) >= 4


class TestReplacementMetadata:
    """Test that replacement records are properly created."""

    def test_replacement_record_fields(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Replacement records should have all required fields."""
        result = policing_service.sanitize_text(
            "The evidence proves that fraud occurred."
        )

        assert len(result.replacements_made) > 0
        record = result.replacements_made[0]

        assert record.original_phrase
        assert record.replacement_phrase
        assert record.position_start >= 0
        assert record.position_end > record.position_start
        assert record.rule_id

    def test_timing_metadata(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Result should include timing metadata."""
        result = policing_service.sanitize_text(
            "The defendant violated Section 138."
        )

        assert result.sanitization_time_ms >= 0
        assert result.llm_policing_applied is False  # Regex only

    def test_regex_policing_under_5ms(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """L4 fix: Regex policing should complete in < 5ms per story requirements.

        Story 8-3: Performance target < 5ms for regex policing (excluding LLM).
        """
        # Run multiple times to warm up and get stable measurement
        for _ in range(3):
            result = policing_service.sanitize_text(
                "The evidence proves that defendant violated Section 138. "
                "The court will rule against him and he must pay damages."
            )

        # Final measurement
        result = policing_service.sanitize_text(
            "The evidence proves that defendant violated Section 138. "
            "The court will rule against him and he must pay damages."
        )

        assert result.sanitization_time_ms < 5.0, (
            f"Regex policing took {result.sanitization_time_ms:.2f}ms, "
            f"expected < 5ms per Story 8-3 requirements"
        )


class TestEmptyAndEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Empty string should return empty result."""
        result = policing_service.sanitize_text("")
        assert result.sanitized_text == ""
        assert len(result.replacements_made) == 0

    def test_whitespace_only(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Whitespace-only string should return same string."""
        result = policing_service.sanitize_text("   ")
        assert result.sanitized_text == "   "
        assert len(result.replacements_made) == 0

    def test_very_long_text(
        self, policing_service: LanguagePolicingService
    ) -> None:
        """Long text should be processed successfully."""
        text = "The defendant violated Section 138. " * 100
        result = policing_service.sanitize_text(text)

        assert "affected by Section 138" in result.sanitized_text
        assert len(result.replacements_made) == 100
