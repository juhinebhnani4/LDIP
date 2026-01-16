"""Structured logging configuration using structlog.

Provides structured JSON logging with optional Axiom integration for
production observability (Story 13.1).

Key Features:
- Development: Pretty console output with colors
- Production: JSON output for log aggregation
- Axiom Integration: When AXIOM_TOKEN is configured, sends logs to Axiom
- Graceful Fallback: If Axiom is unavailable, logs continue to stdout
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, cast

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    import axiom_py

# Axiom client singleton - initialized lazily on first log in production
_axiom_client: axiom_py.Client | None = None


def _get_axiom_processor() -> structlog.types.Processor | None:
    """Get Axiom processor if configured, with graceful error handling.

    Returns:
        AxiomProcessor instance if configured, None otherwise.
    """
    global _axiom_client

    settings = get_settings()

    if not settings.axiom_token:
        return None

    try:
        from axiom_py import Client
        from axiom_py.structlog import AxiomProcessor

        if _axiom_client is None:
            _axiom_client = Client(settings.axiom_token)

        return AxiomProcessor(_axiom_client, settings.axiom_dataset)
    except ImportError:
        # axiom-py not installed - log warning and continue
        logging.getLogger(__name__).warning(
            "axiom-py not installed but AXIOM_TOKEN is set. "
            "Install axiom-py for Axiom logging support."
        )
        return None
    except Exception as e:
        # Axiom client initialization failed - log warning and continue
        logging.getLogger(__name__).warning(
            f"Failed to initialize Axiom client: {e}. "
            "Logs will not be sent to Axiom."
        )
        return None


def configure_logging() -> None:
    """Configure structured logging for the application.

    In development (DEBUG=true):
        - Pretty console output with colors
        - No Axiom integration

    In production (DEBUG=false):
        - JSON output for log aggregation
        - Axiom integration if AXIOM_TOKEN is configured
        - Graceful fallback if Axiom is unavailable
    """
    settings = get_settings()

    # Determine log level based on debug setting
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Shared processors for both dev and prod
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.debug:
        # Development: pretty console output
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output for log aggregation (Axiom)
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
        ]

        # Add Axiom processor if configured (before JSONRenderer)
        axiom_processor = _get_axiom_processor()
        if axiom_processor is not None:
            processors.append(axiom_processor)
            logging.getLogger(__name__).info(
                f"Axiom logging enabled for dataset: {settings.axiom_dataset}"
            )

        # JSONRenderer must be last
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name. If None, uses the calling module's name.

    Returns:
        A structured logger instance.
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
