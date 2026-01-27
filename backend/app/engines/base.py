"""Base class for AI engines.

Story 4.1: Added ReasoningCaptureMixin for legal defensibility.
"""

from abc import ABC, abstractmethod
from typing import Any

import structlog
from pydantic import BaseModel

from app.models.reasoning_trace import EngineType, ReasoningTraceCreate

logger = structlog.get_logger(__name__)


class EngineInput(BaseModel):
    """Base input model for engine execution."""

    matter_id: str
    query: str | None = None


class EngineOutput(BaseModel):
    """Base output model for engine execution."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    confidence: float | None = None


# =============================================================================
# Story 4.1: Reasoning Capture Mixin
# =============================================================================


class ReasoningCaptureMixin:
    """Mixin for engines to capture reasoning traces for legal defensibility.

    Story 4.1: Provides store_reasoning() method that engines call after LLM responses.

    Usage in engines:
        class MyEngine(ReasoningCaptureMixin, EngineBase):
            async def process(self, matter_id: str, ...):
                response = await self.llm_call(...)
                await self.store_reasoning(
                    matter_id=matter_id,
                    finding_id=finding.id,
                    engine_type=EngineType.CONTRADICTION,
                    model_used="gpt-4",
                    llm_response=response,
                    input_summary="Comparing statements...",
                )
    """

    _reasoning_service = None

    @property
    def reasoning_service(self):
        """Get reasoning trace service, initializing if needed."""
        if self._reasoning_service is None:
            from app.services.reasoning_trace_service import get_reasoning_trace_service
            self._reasoning_service = get_reasoning_trace_service()
        return self._reasoning_service

    async def store_reasoning(
        self,
        matter_id: str,
        engine_type: EngineType,
        model_used: str,
        reasoning_text: str,
        finding_id: str | None = None,
        reasoning_structured: dict[str, Any] | None = None,
        input_summary: str | None = None,
        prompt_version: str | None = None,
        confidence_score: float | None = None,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Store reasoning trace from LLM response.

        Story 4.1: AC 4.1.2 - Graceful failure handling.
        Called by engines after every LLM interaction that produces findings.
        Failure does not block the main operation.

        Args:
            matter_id: Matter UUID.
            engine_type: Source engine type.
            model_used: LLM model identifier (e.g., "gpt-4", "gemini-1.5-flash").
            reasoning_text: Chain-of-thought explanation from LLM.
            finding_id: Optional finding UUID to link.
            reasoning_structured: Optional structured breakdown.
            input_summary: Truncated summary of input context.
            prompt_version: Version of prompt template used.
            confidence_score: Confidence score from LLM (0-1 scale).
            tokens_used: Total tokens consumed.
            cost_usd: Estimated cost in USD.
        """
        if not reasoning_text:
            logger.debug(
                "reasoning_trace_skipped_empty",
                matter_id=matter_id,
                engine_type=engine_type.value,
            )
            return

        trace = ReasoningTraceCreate(
            matter_id=matter_id,
            finding_id=finding_id,
            engine_type=engine_type,
            model_used=model_used,
            reasoning_text=reasoning_text,
            reasoning_structured=reasoning_structured,
            input_summary=input_summary[:1000] if input_summary else None,
            prompt_template_version=prompt_version,
            confidence_score=confidence_score,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        try:
            await self.reasoning_service.store_trace(trace)
        except Exception as e:
            # Story 4.1: AC 4.1.2 - Log but don't fail the main operation
            logger.error(
                "reasoning_trace_storage_failed",
                error=str(e),
                matter_id=matter_id,
                engine_type=engine_type.value,
            )

    async def store_reasoning_from_response(
        self,
        matter_id: str,
        engine_type: EngineType,
        model_used: str,
        llm_response: dict[str, Any],
        finding_id: str | None = None,
        input_summary: str | None = None,
        prompt_version: str | None = None,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Store reasoning trace extracting data from LLM response dict.

        Convenience method that extracts reasoning from common response formats.

        Args:
            matter_id: Matter UUID.
            engine_type: Source engine type.
            model_used: LLM model identifier.
            llm_response: Parsed LLM response dict (expects "reasoning" or "rationale" field).
            finding_id: Optional finding UUID to link.
            input_summary: Truncated summary of input context.
            prompt_version: Version of prompt template used.
            tokens_used: Total tokens consumed.
            cost_usd: Estimated cost in USD.
        """
        # Extract reasoning text from common field names
        reasoning_text = (
            llm_response.get("reasoning")
            or llm_response.get("rationale")
            or llm_response.get("explanation")
            or ""
        )

        # Fallback: construct from available fields if no dedicated reasoning field
        if not reasoning_text and llm_response:
            parts = []
            if "decision" in llm_response:
                parts.append(f"Decision: {llm_response['decision']}")
            if "result" in llm_response:
                parts.append(f"Result: {llm_response['result']}")
            if "confidence" in llm_response:
                parts.append(f"Confidence: {llm_response['confidence']}")
            reasoning_text = ". ".join(parts) if parts else "No reasoning provided"

        # Extract structured reasoning if available
        reasoning_structured = llm_response.get("reasoning_structured")

        # Extract confidence
        confidence_score = llm_response.get("confidence")

        await self.store_reasoning(
            matter_id=matter_id,
            engine_type=engine_type,
            model_used=model_used,
            reasoning_text=reasoning_text,
            finding_id=finding_id,
            reasoning_structured=reasoning_structured,
            input_summary=input_summary,
            prompt_version=prompt_version,
            confidence_score=confidence_score,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )


class EngineBase(ABC):
    """Abstract base class for all AI engines.

    All engines (Citation, Timeline, Contradiction) inherit from this base
    and implement the execute method.

    Attributes:
        name: Engine identifier used for logging and routing.
        logger: Structured logger instance.
    """

    def __init__(self, name: str) -> None:
        """Initialize the engine.

        Args:
            name: Engine name for identification.
        """
        self.name = name
        self.logger = structlog.get_logger(f"engine.{name}")

    @abstractmethod
    async def execute(self, input_data: EngineInput) -> EngineOutput:
        """Execute the engine's main processing logic.

        Args:
            input_data: Input parameters for engine execution.

        Returns:
            Engine execution results.
        """
        ...

    async def validate_input(self, input_data: EngineInput) -> bool:
        """Validate input data before execution.

        Override in subclasses for engine-specific validation.

        Args:
            input_data: Input to validate.

        Returns:
            True if input is valid.
        """
        if not input_data.matter_id:
            self.logger.warning("missing_matter_id")
            return False
        return True

    async def health_check(self) -> dict[str, Any]:
        """Check engine health status.

        Override in subclasses to add engine-specific health checks.

        Returns:
            Health status dictionary.
        """
        return {
            "engine": self.name,
            "status": "healthy",
        }
