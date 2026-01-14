"""Tests for guardrail pattern matching.

Story 8-1: Regex Pattern Detection Guardrails (AC #1-3)

Test Categories:
- Legal advice requests (AC #1): "Should I file an appeal?"
- Outcome predictions (AC #2): "Will the judge rule in my favor?"
- Probability/chances (AC #3): "What are my chances of winning?"
- Liability conclusions: "Is the defendant guilty?"
- Allowed queries: Factual questions that should pass through
"""

import pytest

from app.services.safety.guardrail import (
    GuardrailService,
    get_guardrail_service,
    reset_guardrail_service,
)


@pytest.fixture
def guardrail_service() -> GuardrailService:
    """Get fresh guardrail service for testing.

    Story 8-1: Task 4.1 - Test fixture.
    """
    reset_guardrail_service()
    return get_guardrail_service()


class TestLegalAdvicePatterns:
    """Test legal advice request detection.

    Story 8-1: AC #1 - Block patterns like "should (i|we|client) (file|appeal|settle)"
    """

    def test_should_i_file_blocked(self, guardrail_service: GuardrailService) -> None:
        """Should block 'Should I file an appeal?'

        Story 8-1: Task 4.2
        """
        check = guardrail_service.check_query("Should I file an appeal?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"
        assert check.pattern_matched is not None
        assert len(check.explanation) > 0

    def test_should_we_settle_blocked(self, guardrail_service: GuardrailService) -> None:
        """Should block 'Should we settle the case?'

        Story 8-1: Task 4.2
        """
        check = guardrail_service.check_query("Should we settle the case?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_should_client_sue_blocked(self, guardrail_service: GuardrailService) -> None:
        """Should block 'Should the client sue?'

        Story 8-1: Task 4.2 - Tests client variant
        """
        check = guardrail_service.check_query("Should the client sue?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_should_my_client_proceed_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Should my client proceed with the claim?'

        Story 8-1: Task 4.2 - Tests my client variant
        """
        check = guardrail_service.check_query("Should my client proceed with the claim?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_do_you_recommend_filing_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Do you recommend filing a motion?'

        Story 8-1: Task 4.2 - Tests recommend pattern
        """
        check = guardrail_service.check_query("Do you recommend filing a motion?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_what_should_i_do_next_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'What should I do next?'

        Story 8-1: Task 4.2 - Tests what should pattern
        """
        check = guardrail_service.check_query("What should I do next?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"


class TestOutcomePredictionPatterns:
    """Test outcome prediction detection.

    Story 8-1: AC #2 - Block patterns like "will (judge|court) (rule|decide|hold)"
    """

    def test_will_judge_rule_blocked(self, guardrail_service: GuardrailService) -> None:
        """Should block 'Will the judge rule in my favor?'

        Story 8-1: Task 4.3
        """
        check = guardrail_service.check_query("Will the judge rule in my favor?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"
        assert check.pattern_matched is not None

    def test_will_court_decide_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Will the court decide against the defendant?'

        Story 8-1: Task 4.3
        """
        check = guardrail_service.check_query(
            "Will the court decide against the defendant?"
        )
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_will_judge_grant_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Will the judge grant the motion?'

        Story 8-1: Task 4.3 - Tests grant variant
        """
        check = guardrail_service.check_query("Will the judge grant the motion?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_will_tribunal_dismiss_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Will the tribunal dismiss this case?'

        Story 8-1: Task 4.3 - Tests tribunal variant
        """
        check = guardrail_service.check_query("Will the tribunal dismiss this case?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_what_will_judge_decide_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'What will the judge decide?'

        Story 8-1: Task 4.3 - Tests what will pattern
        """
        check = guardrail_service.check_query("What will the judge decide?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_is_court_likely_to_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Is the court likely to rule in our favor?'

        Story 8-1: Task 4.3 - Tests likely pattern
        """
        check = guardrail_service.check_query(
            "Is the court likely to rule in our favor?"
        )
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"


class TestChancesPatterns:
    """Test probability/chances detection.

    Story 8-1: AC #3 - Block patterns like "what are (my|our) chances"
    """

    def test_what_are_my_chances_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'What are my chances of winning?'

        Story 8-1: Task 4.4
        """
        check = guardrail_service.check_query("What are my chances of winning?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"  # Chances = outcome prediction

    def test_what_are_our_chances_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'What are our chances in this appeal?'

        Story 8-1: Task 4.4
        """
        check = guardrail_service.check_query("What are our chances in this appeal?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_what_is_the_likelihood_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'What is the likelihood of winning?'

        Story 8-1: Task 4.4 - Tests likelihood pattern
        """
        check = guardrail_service.check_query("What is the likelihood of winning?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_will_we_win_blocked(self, guardrail_service: GuardrailService) -> None:
        """Should block 'Will we win this case?'

        Story 8-1: Task 4.4 - Tests will win pattern
        """
        check = guardrail_service.check_query("Will we win this case?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_can_i_succeed_blocked(self, guardrail_service: GuardrailService) -> None:
        """Should block 'Can I succeed in this lawsuit?'

        Story 8-1: Task 4.4 - Tests can succeed pattern
        """
        check = guardrail_service.check_query("Can I succeed in this lawsuit?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"


class TestLiabilityPatterns:
    """Test liability conclusion detection.

    Story 8-1: Task 4.5 - Block patterns like "is (defendant|plaintiff) (guilty|liable)"
    """

    def test_is_defendant_guilty_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Is the defendant guilty?'

        Story 8-1: Task 4.5
        """
        check = guardrail_service.check_query("Is the defendant guilty?")
        assert check.is_safe is False
        assert check.violation_type == "liability_conclusion"

    def test_is_plaintiff_liable_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Is the plaintiff liable for damages?'

        Story 8-1: Task 4.5
        """
        check = guardrail_service.check_query("Is the plaintiff liable for damages?")
        assert check.is_safe is False
        assert check.violation_type == "liability_conclusion"

    def test_is_accused_responsible_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Is the accused responsible?'

        Story 8-1: Task 4.5 - Tests accused variant
        """
        check = guardrail_service.check_query("Is the accused responsible?")
        assert check.is_safe is False
        assert check.violation_type == "liability_conclusion"

    def test_did_defendant_violate_blocked(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should block 'Did the defendant violate the contract?'

        Story 8-1: Task 4.5 - Tests did violate pattern
        """
        check = guardrail_service.check_query("Did the defendant violate the contract?")
        assert check.is_safe is False
        assert check.violation_type == "liability_conclusion"


class TestAllowedQueries:
    """Test that legitimate queries pass through.

    Story 8-1: Tasks 4.6-4.8 - Ensure conservative blocking doesn't
    impact legitimate factual queries.
    """

    def test_factual_question_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'What does Section 138 say?'

        Story 8-1: Task 4.6
        """
        check = guardrail_service.check_query("What does Section 138 say?")
        assert check.is_safe is True
        assert check.violation_type is None
        assert check.pattern_matched is None

    def test_timeline_question_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'When did the loan default?'

        Story 8-1: Task 4.7
        """
        check = guardrail_service.check_query("When did the loan default?")
        assert check.is_safe is True
        assert check.violation_type is None

    def test_contradiction_question_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'What contradictions exist in witness statements?'

        Story 8-1: Task 4.8
        """
        check = guardrail_service.check_query(
            "What contradictions exist in witness statements?"
        )
        assert check.is_safe is True
        assert check.violation_type is None

    def test_entity_question_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'Who is mentioned in the complaint?'

        Story 8-1: Task 4.6 - Entity queries allowed
        """
        check = guardrail_service.check_query("Who is mentioned in the complaint?")
        assert check.is_safe is True

    def test_citation_question_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'What cases are cited in paragraph 5?'

        Story 8-1: Task 4.6 - Citation queries allowed
        """
        check = guardrail_service.check_query("What cases are cited in paragraph 5?")
        assert check.is_safe is True

    def test_date_question_allowed(self, guardrail_service: GuardrailService) -> None:
        """Should allow 'What dates are mentioned in the loan agreement?'

        Story 8-1: Task 4.7 - Date extraction allowed
        """
        check = guardrail_service.check_query(
            "What dates are mentioned in the loan agreement?"
        )
        assert check.is_safe is True

    def test_summary_question_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'Summarize the main arguments in the judgment'

        Story 8-1: Task 4.6 - Summary queries allowed
        """
        check = guardrail_service.check_query(
            "Summarize the main arguments in the judgment"
        )
        assert check.is_safe is True

    def test_borderline_factors_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'What factors do judges consider in appeals?'

        Story 8-1: Borderline queries allowed (let LLM + Story 8-2 handle)
        """
        check = guardrail_service.check_query(
            "What factors do judges consider in appeals?"
        )
        assert check.is_safe is True

    def test_borderline_standard_allowed(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Should allow 'What is the standard for granting relief?'

        Story 8-1: Borderline queries allowed (let LLM + Story 8-2 handle)
        """
        check = guardrail_service.check_query(
            "What is the standard for granting relief?"
        )
        assert check.is_safe is True


class TestCaseInsensitivity:
    """Test that pattern matching is case-insensitive.

    Story 8-1: Task 5.7 - Case insensitivity requirement
    """

    def test_uppercase_blocked(self, guardrail_service: GuardrailService) -> None:
        """Pattern matching should be case-insensitive (uppercase)."""
        check = guardrail_service.check_query("SHOULD I FILE AN APPEAL?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_mixed_case_blocked(self, guardrail_service: GuardrailService) -> None:
        """Pattern matching should be case-insensitive (mixed case)."""
        check = guardrail_service.check_query("Should I FILE an Appeal?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_lowercase_blocked(self, guardrail_service: GuardrailService) -> None:
        """Pattern matching should be case-insensitive (lowercase)."""
        check = guardrail_service.check_query("should i file an appeal?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"
