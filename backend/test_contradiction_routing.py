#!/usr/bin/env python3
"""Test the two-tier contradiction model routing implementation.

This script validates that:
1. Gemini Flash is used for initial screening
2. Consistent/unrelated results with high confidence skip GPT-4
3. Uncertain/contradiction results escalate to GPT-4
4. Cost savings are achieved through routing
"""

import asyncio
import sys
sys.path.insert(0, ".")

from dataclasses import dataclass
from app.models.contradiction import Statement
from app.engines.contradiction.comparator import (
    StatementComparator,
    get_statement_comparator,
)
from app.core.config import get_settings


@dataclass
class TestCase:
    name: str
    statement_a: str
    statement_b: str
    entity_name: str
    expected_screening: str  # "consistent", "unrelated", "needs_review"
    expected_escalation: bool


# Test cases for different scenarios
TEST_CASES = [
    TestCase(
        name="Clearly Consistent",
        statement_a="The loan was disbursed on January 15, 2024 to Mr. Sharma.",
        statement_b="Mr. Sharma received the loan disbursement in January 2024.",
        entity_name="Mr. Sharma",
        expected_screening="consistent",
        expected_escalation=False,
    ),
    TestCase(
        name="Clearly Unrelated",
        statement_a="Mr. Sharma works as a software engineer in Bangalore.",
        statement_b="The property is located at 123 Main Street, Mumbai.",
        entity_name="Mr. Sharma",
        expected_screening="unrelated",
        expected_escalation=False,
    ),
    TestCase(
        name="Potential Date Contradiction",
        statement_a="The loan was disbursed on January 15, 2024.",
        statement_b="The loan was disbursed on June 15, 2024.",
        entity_name="Loan Disbursement",
        expected_screening="needs_review",
        expected_escalation=True,
    ),
    TestCase(
        name="Potential Amount Contradiction",
        statement_a="The property was valued at Rs. 50 lakhs.",
        statement_b="The property value is Rs. 80 lakhs.",
        entity_name="Property",
        expected_screening="needs_review",
        expected_escalation=True,
    ),
]


async def test_single_comparison(comparator: StatementComparator, test_case: TestCase):
    """Run a single comparison test."""
    print(f"\n{'='*60}")
    print(f"Test: {test_case.name}")
    print(f"{'='*60}")
    print(f"Statement A: {test_case.statement_a[:80]}...")
    print(f"Statement B: {test_case.statement_b[:80]}...")
    print(f"Entity: {test_case.entity_name}")
    print(f"Expected screening: {test_case.expected_screening}")
    print(f"Expected escalation: {test_case.expected_escalation}")
    print("-" * 60)

    # Create mock statements
    stmt_a = Statement(
        entity_id="test-entity-001",
        chunk_id="test-chunk-a",
        document_id="test-doc-a",
        content=test_case.statement_a,
        page_number=1,
    )
    stmt_b = Statement(
        entity_id="test-entity-001",
        chunk_id="test-chunk-b",
        document_id="test-doc-b",
        content=test_case.statement_b,
        page_number=1,
    )

    try:
        comparison, cost_tracker = await comparator.compare_statement_pair(
            statement_a=stmt_a,
            statement_b=stmt_b,
            entity_name=test_case.entity_name,
            doc_a_name="Document A",
            doc_b_name="Document B",
        )

        print(f"Result: {comparison.result.value}")
        print(f"Confidence: {comparison.confidence}")
        print(f"Reasoning: {comparison.reasoning[:100]}...")
        print(f"\nCost Tracking:")
        print(f"  Screening model: {cost_tracker.screening_model or 'N/A'}")
        print(f"  Screening tokens: {cost_tracker.screening_input_tokens} in / {cost_tracker.screening_output_tokens} out")
        print(f"  GPT-4 tokens: {cost_tracker.input_tokens} in / {cost_tracker.output_tokens} out")
        print(f"  Was escalated: {cost_tracker.was_escalated}")
        print(f"  Total cost: ${cost_tracker.cost_usd:.6f}")

        # Validate expectations
        if cost_tracker.was_escalated != test_case.expected_escalation:
            print(f"\n[WARNING] Escalation mismatch! Expected: {test_case.expected_escalation}, Got: {cost_tracker.was_escalated}")
        else:
            print(f"\n[OK] Escalation matched expectations")

        return {
            "name": test_case.name,
            "result": comparison.result.value,
            "confidence": comparison.confidence,
            "escalated": cost_tracker.was_escalated,
            "cost_usd": cost_tracker.cost_usd,
            "success": cost_tracker.was_escalated == test_case.expected_escalation,
        }

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        return {
            "name": test_case.name,
            "error": str(e),
            "success": False,
        }


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Contradiction Model Routing Test")
    print("=" * 60)

    settings = get_settings()
    print(f"\nConfiguration:")
    print(f"  Routing enabled: {settings.contradiction_model_routing_enabled}")
    print(f"  Screening model: {settings.contradiction_screening_model}")
    print(f"  Confidence threshold: {settings.contradiction_screening_confidence_threshold}")
    print(f"  Escalate results: {settings.contradiction_escalate_results}")
    print(f"  GPT-4 model: {settings.openai_comparison_model}")

    if not settings.gemini_api_key:
        print("\n[WARNING] Gemini API key not configured - routing will fall back to GPT-4 only")

    if not settings.openai_api_key:
        print("\n[ERROR] OpenAI API key not configured - cannot run tests")
        return

    comparator = get_statement_comparator()

    results = []
    total_cost = 0.0

    for test_case in TEST_CASES:
        result = await test_single_comparison(comparator, test_case)
        results.append(result)
        if "cost_usd" in result:
            total_cost += result["cost_usd"]

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.get("success"))
    failed = len(results) - passed

    for r in results:
        status = "[PASS]" if r.get("success") else "[FAIL]"
        cost = f"${r.get('cost_usd', 0):.6f}" if "cost_usd" in r else "N/A"
        escalated = "escalated" if r.get("escalated") else "screened"
        print(f"  {status} {r['name']}: {r.get('result', 'ERROR')} ({escalated}) - {cost}")

    print(f"\nTotal: {passed}/{len(results)} passed")
    print(f"Total cost: ${total_cost:.6f}")

    # Cost analysis
    if passed > 0:
        screened_count = sum(1 for r in results if not r.get("escalated", True) and r.get("success"))
        if screened_count > 0:
            savings_pct = (screened_count / len(results)) * 100
            print(f"\nCost savings: ~{savings_pct:.0f}% of comparisons skipped GPT-4")


if __name__ == "__main__":
    asyncio.run(main())
