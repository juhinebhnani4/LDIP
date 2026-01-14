"""Guardrail service for blocking dangerous queries.

Story 8-1: Regex Pattern Detection Guardrails

Fast-path regex guardrail that blocks dangerous queries BEFORE
they reach the LLM. This is Layer 1 of the Safety Layer.

Query flow with guardrails:
USER QUERY → [GUARDRAIL CHECK] → ORCHESTRATOR → ENGINES → [LANGUAGE POLICING] → RESPONSE
              ^^^^^^^^^^^^^                       ^^^^^^^^^^^^^^^^^^^^^
              Story 8-1 (this)                    Story 8-3

Key Requirements:
- AC #1-3: Pattern matching for dangerous queries
- AC #4: Return GuardrailCheck with is_safe, violation_type, explanation, rewrite
- Performance: Check must complete in < 5ms (regex only, no LLM)

Thread Safety:
- Uses module-level singleton with thread-safe initialization
- Patterns are pre-compiled at module load
"""

from __future__ import annotations

import threading
import time

import structlog

from app.models.safety import GuardrailCheck
from app.services.safety.patterns import CompiledPattern, get_patterns

logger = structlog.get_logger(__name__)


class GuardrailService:
    """Fast-path regex guardrail for dangerous queries.

    Story 8-1: Blocks legal advice/outcome prediction requests
    before they reach LLM (cost + safety optimization).

    Usage:
        service = get_guardrail_service()
        check = service.check_query("Should I file an appeal?")
        if not check.is_safe:
            # Query blocked - return explanation to user
            return check.explanation, check.suggested_rewrite
    """

    def __init__(self) -> None:
        """Initialize guardrail service with pre-compiled patterns.

        Story 8-1: Task 3.1 - Service initialization.
        """
        self._patterns: list[CompiledPattern] = []
        self._load_patterns()
        logger.info("guardrail_service_initialized", pattern_count=len(self._patterns))

    def _load_patterns(self) -> None:
        """Load pre-compiled patterns from registry.

        Story 8-1: Task 3.1 - Pattern loading.
        """
        self._patterns = get_patterns()

    def check_query(self, query: str) -> GuardrailCheck:
        """Check query against all guardrail patterns.

        Story 8-1: AC #1-3 - Pattern matching.

        This is the main entry point for query guardrail checking.
        Returns immediately with is_safe=False if any pattern matches.

        Args:
            query: User query to check.

        Returns:
            GuardrailCheck with result and metadata.
            - is_safe=True: Query can proceed to LLM
            - is_safe=False: Query blocked with explanation and suggested rewrite

        """
        start_time = time.perf_counter()

        # Normalize query for matching (case-insensitive)
        query_lower = query.lower()

        # Check against all patterns (first match wins)
        for pattern in self._patterns:
            if pattern.regex.search(query_lower):
                check_time_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    "query_blocked_by_guardrail",
                    pattern_id=pattern.pattern_id,
                    violation_type=pattern.violation_type,
                    check_time_ms=round(check_time_ms, 3),
                )

                return GuardrailCheck(
                    is_safe=False,
                    violation_type=pattern.violation_type,
                    pattern_matched=pattern.pattern_id,
                    explanation=pattern.get_explanation(query),
                    suggested_rewrite=pattern.get_rewrite(query),
                    check_time_ms=check_time_ms,
                )

        # No pattern matched - query is safe
        check_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "query_passed_guardrail",
            check_time_ms=round(check_time_ms, 3),
        )

        return GuardrailCheck(
            is_safe=True,
            check_time_ms=check_time_ms,
        )

    def get_pattern_count(self) -> int:
        """Get number of loaded patterns.

        Returns:
            Number of patterns in the registry.

        """
        return len(self._patterns)


# =============================================================================
# Story 8-1: Singleton Factory (Task 3.5-3.6)
# =============================================================================

# Singleton instance (thread-safe)
_guardrail_service: GuardrailService | None = None
_service_lock = threading.Lock()


def get_guardrail_service() -> GuardrailService:
    """Get singleton guardrail service instance.

    Story 8-1: Task 3.5 - Factory function with thread-safe initialization.

    Returns:
        GuardrailService singleton instance.

    """
    global _guardrail_service  # noqa: PLW0603

    if _guardrail_service is None:
        with _service_lock:
            # Double-check locking pattern
            if _guardrail_service is None:
                _guardrail_service = GuardrailService()

    return _guardrail_service


def reset_guardrail_service() -> None:
    """Reset singleton for testing.

    Story 8-1: Task 3.5 - Reset function for test isolation.

    Note:
        This creates a fresh instance on next get_guardrail_service() call.

    """
    global _guardrail_service  # noqa: PLW0603

    with _service_lock:
        _guardrail_service = None

    logger.debug("guardrail_service_reset")
