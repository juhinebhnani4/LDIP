"""Base class for AI engines."""

from abc import ABC, abstractmethod
from typing import Any

import structlog
from pydantic import BaseModel


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
