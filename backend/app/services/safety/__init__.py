"""Safety services module.

Story 8-1: Regex Pattern Detection Guardrails
Story 8-2: GPT-4o-mini Subtle Violation Detection
Story 8-3: Language Policing Output Sanitization

Exports:
- GuardrailService: Fast-path regex guardrail service (Story 8-1)
- SubtleViolationDetector: LLM-based subtle detection (Story 8-2)
- SafetyGuard: Combined regex + LLM safety guard (Story 8-2)
- LanguagePolicingService: Regex-based output sanitization (Story 8-3)
- LanguagePolice: Combined regex + LLM output sanitization (Story 8-3)
- QuoteDetector: Quote detection for preservation (Story 8-3)
- Factory functions and pattern registry
"""

from app.services.safety.guardrail import (
    GuardrailService,
    get_guardrail_service,
    reset_guardrail_service,
)
from app.services.safety.language_police import (
    LanguagePolice,
    get_language_police,
    reset_language_police,
)
from app.services.safety.language_policing import (
    LanguagePolicingService,
    get_language_policing_service,
    reset_language_policing_service,
)
from app.services.safety.patterns import (
    COMPILED_PATTERNS,
    CompiledPattern,
    get_patterns,
)
from app.services.safety.policing_patterns import (
    COMPILED_POLICING_PATTERNS,
    CompiledPolicingPattern,
    get_policing_patterns,
)
from app.services.safety.quote_detector import (
    QuoteDetector,
    detect_quotes,
)
from app.services.safety.safety_guard import (
    SafetyGuard,
    get_safety_guard,
    reset_safety_guard,
)
from app.services.safety.subtle_detector import (
    SubtleViolationDetector,
    get_subtle_violation_detector,
    reset_subtle_violation_detector,
)

__all__ = [
    # Story 8-1: Regex guardrail
    "COMPILED_PATTERNS",
    "CompiledPattern",
    "GuardrailService",
    "get_guardrail_service",
    "get_patterns",
    "reset_guardrail_service",
    # Story 8-2: LLM-based subtle detection
    "SubtleViolationDetector",
    "get_subtle_violation_detector",
    "reset_subtle_violation_detector",
    # Story 8-2: Combined safety guard
    "SafetyGuard",
    "get_safety_guard",
    "reset_safety_guard",
    # Story 8-3: Language policing
    "COMPILED_POLICING_PATTERNS",
    "CompiledPolicingPattern",
    "LanguagePolice",
    "LanguagePolicingService",
    "QuoteDetector",
    "detect_quotes",
    "get_language_police",
    "get_language_policing_service",
    "get_policing_patterns",
    "reset_language_police",
    "reset_language_policing_service",
]
