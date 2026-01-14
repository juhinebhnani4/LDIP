"""Combined safety guard with regex + LLM detection.

Story 8-1 + 8-2: Two-Phase Safety Guard

This service combines the fast-path regex guardrail (Story 8-1) with
the LLM-based subtle detection (Story 8-2) into a unified safety pipeline.

Pipeline:
1. Regex check (< 5ms) - blocks obvious violations
2. If regex passes, LLM check (~500-2000ms) - catches subtle violations

CRITICAL: LLM failures should NOT block queries - fail open to prevent DoS.
"""

from __future__ import annotations

from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.models.safety import SafetyCheckResult
from app.services.safety.guardrail import GuardrailService, get_guardrail_service
from app.services.safety.subtle_detector import (
    SubtleViolationDetector,
    get_subtle_violation_detector,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 8-2: SafetyGuard Service (Task 5)
# =============================================================================


class SafetyGuard:
    """Combined safety guard with regex + LLM detection.

    Story 8-1 + 8-2: Two-phase safety checking.

    Pipeline:
    1. Fast regex check (< 5ms) - blocks obvious violations (Story 8-1)
    2. If regex passes, LLM check (~500-2000ms) - catches subtle violations (Story 8-2)

    Example:
        >>> guard = get_safety_guard()
        >>> result = await guard.check_query("Should I file an appeal?")
        >>> result.is_safe
        False
        >>> result.blocked_by
        'regex'

        >>> result = await guard.check_query(
        ...     "Based on this evidence, is it clear that..."
        ... )
        >>> result.blocked_by
        'llm'
    """

    def __init__(
        self,
        guardrail_service: GuardrailService | None = None,
        subtle_detector: SubtleViolationDetector | None = None,
    ) -> None:
        """Initialize safety guard.

        Story 8-2: Task 5.2 - Service initialization.

        Args:
            guardrail_service: Regex-based guardrail (Story 8-1).
            subtle_detector: LLM-based detector (Story 8-2).
        """
        self._guardrail = guardrail_service or get_guardrail_service()
        self._subtle_detector = subtle_detector or get_subtle_violation_detector()
        self._llm_enabled = get_settings().safety_llm_enabled

        logger.info(
            "safety_guard_initialized",
            llm_enabled=self._llm_enabled,
        )

    async def check_query(self, query: str) -> SafetyCheckResult:
        """Check query against both regex and LLM guardrails.

        Story 8-1 + 8-2: Combined safety pipeline.

        Args:
            query: User query to check.

        Returns:
            SafetyCheckResult with combined results.
        """
        # Phase 1: Fast regex check (Story 8-1)
        regex_check = self._guardrail.check_query(query)

        if not regex_check.is_safe:
            logger.info(
                "query_blocked_by_regex",
                pattern_matched=regex_check.pattern_matched,
                violation_type=regex_check.violation_type,
                check_time_ms=round(regex_check.check_time_ms, 3),
            )

            return SafetyCheckResult(
                is_safe=False,
                blocked_by="regex",
                violation_type=regex_check.violation_type,
                explanation=regex_check.explanation,
                suggested_rewrite=regex_check.suggested_rewrite,
                regex_check_ms=regex_check.check_time_ms,
            )

        # Phase 2: LLM check if enabled (Story 8-2)
        if not self._llm_enabled:
            logger.debug(
                "llm_check_disabled",
                regex_check_ms=round(regex_check.check_time_ms, 3),
            )
            return SafetyCheckResult(
                is_safe=True,
                blocked_by=None,
                regex_check_ms=regex_check.check_time_ms,
            )

        try:
            llm_check = await self._subtle_detector.detect_violation(query)

            if not llm_check.is_safe:
                logger.info(
                    "query_blocked_by_llm",
                    violation_type=llm_check.violation_type,
                    confidence=llm_check.confidence,
                    regex_check_ms=round(regex_check.check_time_ms, 3),
                    llm_check_ms=round(llm_check.check_time_ms, 2),
                )

                return SafetyCheckResult(
                    is_safe=False,
                    blocked_by="llm",
                    violation_type=llm_check.violation_type,
                    explanation=llm_check.explanation,
                    suggested_rewrite=llm_check.suggested_rewrite,
                    regex_check_ms=regex_check.check_time_ms,
                    llm_check_ms=llm_check.check_time_ms,
                    llm_cost_usd=llm_check.llm_cost_usd,
                )

            # Query passed both checks
            logger.debug(
                "query_passed_safety",
                regex_check_ms=round(regex_check.check_time_ms, 3),
                llm_check_ms=round(llm_check.check_time_ms, 2),
            )

            return SafetyCheckResult(
                is_safe=True,
                blocked_by=None,
                regex_check_ms=regex_check.check_time_ms,
                llm_check_ms=llm_check.check_time_ms,
                llm_cost_usd=llm_check.llm_cost_usd,
            )

        except Exception as e:
            # LLM failures should NOT block queries - fail open
            logger.warning(
                "safety_llm_check_failed",
                error=str(e),
                error_type=type(e).__name__,
                fallback="allowing_query",
            )

            return SafetyCheckResult(
                is_safe=True,
                blocked_by=None,
                regex_check_ms=regex_check.check_time_ms,
                llm_check_failed=True,
            )

    @property
    def guardrail(self) -> GuardrailService:
        """Get the guardrail service instance."""
        return self._guardrail

    @property
    def subtle_detector(self) -> SubtleViolationDetector:
        """Get the subtle detector instance."""
        return self._subtle_detector

    @property
    def llm_enabled(self) -> bool:
        """Check if LLM detection is enabled."""
        return self._llm_enabled


# =============================================================================
# Story 8-2: Singleton Factory (Task 5.5)
# =============================================================================


@lru_cache(maxsize=1)
def get_safety_guard() -> SafetyGuard:
    """Get singleton safety guard instance.

    Story 8-2: Task 5.5 - Factory function.

    Returns:
        SafetyGuard singleton instance.
    """
    return SafetyGuard()


def reset_safety_guard() -> None:
    """Reset singleton for testing.

    Story 8-2: Reset function for test isolation.

    Note:
        This clears the LRU cache, creating a fresh instance on next call.
    """
    get_safety_guard.cache_clear()
    logger.debug("safety_guard_reset")
