"""Safety services module.

Story 8-1: Regex Pattern Detection Guardrails

Exports:
- GuardrailService: Fast-path regex guardrail service
- get_guardrail_service: Factory function for singleton access
- reset_guardrail_service: Reset singleton for testing
- Pattern registry: get_patterns, COMPILED_PATTERNS
"""

from app.services.safety.guardrail import (
    GuardrailService,
    get_guardrail_service,
    reset_guardrail_service,
)
from app.services.safety.patterns import (
    COMPILED_PATTERNS,
    CompiledPattern,
    get_patterns,
)

__all__ = [
    "COMPILED_PATTERNS",
    "CompiledPattern",
    "GuardrailService",
    "get_guardrail_service",
    "get_patterns",
    "reset_guardrail_service",
]
