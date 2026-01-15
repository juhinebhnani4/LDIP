"""Time Estimator Service for processing job duration estimation.

Provides time estimates for document processing stages:
- OCR processing (based on page count)
- Chunking (based on text length)
- Embedding (based on chunk count)
- Entity extraction (based on chunk count)
- Alias resolution (fixed estimate)

Estimates can be tuned via environment variables.
"""

import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Configuration (tunable via environment variables)
# =============================================================================

# Default estimates per stage (milliseconds)
DEFAULT_OCR_MS_PER_PAGE = 3000  # 3 seconds per page
DEFAULT_VALIDATION_MS_PER_PAGE = 500  # 0.5 seconds per page
DEFAULT_CONFIDENCE_MS_FIXED = 1000  # 1 second fixed
DEFAULT_CHUNK_MS_PER_1K_CHARS = 100  # 0.1 seconds per 1K chars
DEFAULT_EMBED_MS_PER_CHUNK = 200  # 0.2 seconds per chunk
DEFAULT_ENTITY_MS_PER_CHUNK = 500  # 0.5 seconds per chunk
DEFAULT_ALIAS_MS_FIXED = 5000  # 5 seconds fixed

# Queue wait time estimate per job
DEFAULT_QUEUE_WAIT_MS_PER_JOB = 30000  # 30 seconds per job ahead in queue


def _get_env_int(key: str, default: int) -> int:
    """Get integer from environment variable with default."""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


class TimeEstimatorConfig:
    """Configuration for time estimation."""

    def __init__(self) -> None:
        """Initialize with environment variables or defaults."""
        self.ocr_ms_per_page = _get_env_int(
            "JOB_ESTIMATE_OCR_MS_PER_PAGE",
            DEFAULT_OCR_MS_PER_PAGE,
        )
        self.validation_ms_per_page = _get_env_int(
            "JOB_ESTIMATE_VALIDATION_MS_PER_PAGE",
            DEFAULT_VALIDATION_MS_PER_PAGE,
        )
        self.confidence_ms_fixed = _get_env_int(
            "JOB_ESTIMATE_CONFIDENCE_MS_FIXED",
            DEFAULT_CONFIDENCE_MS_FIXED,
        )
        self.chunk_ms_per_1k_chars = _get_env_int(
            "JOB_ESTIMATE_CHUNK_MS_PER_1K_CHARS",
            DEFAULT_CHUNK_MS_PER_1K_CHARS,
        )
        self.embed_ms_per_chunk = _get_env_int(
            "JOB_ESTIMATE_EMBED_MS_PER_CHUNK",
            DEFAULT_EMBED_MS_PER_CHUNK,
        )
        self.entity_ms_per_chunk = _get_env_int(
            "JOB_ESTIMATE_ENTITY_MS_PER_CHUNK",
            DEFAULT_ENTITY_MS_PER_CHUNK,
        )
        self.alias_ms_fixed = _get_env_int(
            "JOB_ESTIMATE_ALIAS_MS_FIXED",
            DEFAULT_ALIAS_MS_FIXED,
        )
        self.queue_wait_ms_per_job = _get_env_int(
            "JOB_ESTIMATE_QUEUE_WAIT_MS_PER_JOB",
            DEFAULT_QUEUE_WAIT_MS_PER_JOB,
        )


@lru_cache(maxsize=1)
def get_estimator_config() -> TimeEstimatorConfig:
    """Get cached estimator configuration."""
    return TimeEstimatorConfig()


# =============================================================================
# Estimator Service
# =============================================================================


class TimeEstimator:
    """Service for estimating document processing time.

    Provides estimates for individual stages and total processing time.
    Accounts for queue position and document characteristics.

    Example:
        >>> estimator = TimeEstimator()
        >>> ocr_time = estimator.estimate_ocr_time(page_count=50)
        >>> ocr_time
        timedelta(seconds=150)
    """

    def __init__(self, config: TimeEstimatorConfig | None = None) -> None:
        """Initialize with optional custom configuration.

        Args:
            config: Optional custom configuration. Uses defaults if not provided.
        """
        self.config = config or get_estimator_config()

    # =========================================================================
    # Individual Stage Estimates
    # =========================================================================

    def estimate_ocr_time(self, page_count: int) -> timedelta:
        """Estimate OCR processing time.

        Args:
            page_count: Number of pages in document.

        Returns:
            Estimated duration.
        """
        if page_count <= 0:
            return timedelta(0)

        ms = page_count * self.config.ocr_ms_per_page
        return timedelta(milliseconds=ms)

    def estimate_validation_time(self, page_count: int) -> timedelta:
        """Estimate OCR validation time.

        Args:
            page_count: Number of pages to validate.

        Returns:
            Estimated duration.
        """
        if page_count <= 0:
            return timedelta(0)

        ms = page_count * self.config.validation_ms_per_page
        return timedelta(milliseconds=ms)

    def estimate_confidence_time(self) -> timedelta:
        """Estimate confidence calculation time.

        Returns:
            Estimated duration (fixed).
        """
        return timedelta(milliseconds=self.config.confidence_ms_fixed)

    def estimate_chunking_time(self, text_length: int) -> timedelta:
        """Estimate chunking time based on text length.

        Args:
            text_length: Total text length in characters.

        Returns:
            Estimated duration.
        """
        if text_length <= 0:
            return timedelta(0)

        # Convert to 1K char units
        k_chars = text_length / 1000
        ms = k_chars * self.config.chunk_ms_per_1k_chars
        return timedelta(milliseconds=ms)

    def estimate_embedding_time(self, chunk_count: int) -> timedelta:
        """Estimate embedding generation time.

        Args:
            chunk_count: Number of chunks to embed.

        Returns:
            Estimated duration.
        """
        if chunk_count <= 0:
            return timedelta(0)

        ms = chunk_count * self.config.embed_ms_per_chunk
        return timedelta(milliseconds=ms)

    def estimate_entity_extraction_time(self, chunk_count: int) -> timedelta:
        """Estimate entity extraction time.

        Args:
            chunk_count: Number of chunks to process.

        Returns:
            Estimated duration.
        """
        if chunk_count <= 0:
            return timedelta(0)

        ms = chunk_count * self.config.entity_ms_per_chunk
        return timedelta(milliseconds=ms)

    def estimate_alias_resolution_time(self) -> timedelta:
        """Estimate alias resolution time.

        Returns:
            Estimated duration (fixed).
        """
        return timedelta(milliseconds=self.config.alias_ms_fixed)

    # =========================================================================
    # Combined Estimates
    # =========================================================================

    def estimate_total_document_time(
        self,
        page_count: int,
        text_length: int | None = None,
        chunk_count: int | None = None,
    ) -> timedelta:
        """Estimate total document processing time.

        If text_length or chunk_count are not provided, they are estimated
        from page_count using reasonable defaults:
        - ~2000 chars per page
        - ~4 chunks per page (parent + children)

        Args:
            page_count: Number of pages in document.
            text_length: Optional total text length. Estimated if not provided.
            chunk_count: Optional chunk count. Estimated if not provided.

        Returns:
            Total estimated duration for all stages.
        """
        if page_count <= 0:
            return timedelta(0)

        # Estimate text length if not provided (avg ~2000 chars per page)
        if text_length is None:
            text_length = page_count * 2000

        # Estimate chunk count if not provided (avg ~4 chunks per page)
        if chunk_count is None:
            chunk_count = page_count * 4

        total = timedelta(0)

        # Stage 1: OCR
        total += self.estimate_ocr_time(page_count)

        # Stage 2: Validation
        total += self.estimate_validation_time(page_count)

        # Stage 3: Confidence calculation
        total += self.estimate_confidence_time()

        # Stage 4: Chunking
        total += self.estimate_chunking_time(text_length)

        # Stage 5: Embedding
        total += self.estimate_embedding_time(chunk_count)

        # Stage 6: Entity extraction
        total += self.estimate_entity_extraction_time(chunk_count)

        # Stage 7: Alias resolution
        total += self.estimate_alias_resolution_time()

        return total

    def estimate_remaining_time(
        self,
        current_stage: str,
        page_count: int,
        text_length: int | None = None,
        chunk_count: int | None = None,
    ) -> timedelta:
        """Estimate remaining time from current stage.

        Args:
            current_stage: Current processing stage name.
            page_count: Number of pages in document.
            text_length: Optional total text length.
            chunk_count: Optional chunk count.

        Returns:
            Estimated remaining duration.
        """
        if page_count <= 0:
            return timedelta(0)

        # Estimate text length if not provided
        if text_length is None:
            text_length = page_count * 2000

        # Estimate chunk count if not provided
        if chunk_count is None:
            chunk_count = page_count * 4

        # Stage order
        stages = [
            "ocr",
            "validation",
            "confidence",
            "chunking",
            "embedding",
            "entity_extraction",
            "alias_resolution",
        ]

        # Normalize stage name
        normalized = current_stage.lower().replace(" ", "_").replace("-", "_")

        # Find current stage index
        try:
            current_idx = stages.index(normalized)
        except ValueError:
            # Unknown stage, return full estimate
            logger.warning("unknown_stage_for_estimate", stage=current_stage)
            return self.estimate_total_document_time(page_count, text_length, chunk_count)

        # Calculate remaining stages
        remaining = timedelta(0)

        for idx in range(current_idx + 1, len(stages)):
            stage = stages[idx]
            match stage:
                case "ocr":
                    remaining += self.estimate_ocr_time(page_count)
                case "validation":
                    remaining += self.estimate_validation_time(page_count)
                case "confidence":
                    remaining += self.estimate_confidence_time()
                case "chunking":
                    remaining += self.estimate_chunking_time(text_length)
                case "embedding":
                    remaining += self.estimate_embedding_time(chunk_count)
                case "entity_extraction":
                    remaining += self.estimate_entity_extraction_time(chunk_count)
                case "alias_resolution":
                    remaining += self.estimate_alias_resolution_time()

        return remaining

    def estimate_queue_wait_time(self, queue_position: int) -> timedelta:
        """Estimate wait time based on queue position.

        Args:
            queue_position: Position in queue (0 = next up).

        Returns:
            Estimated wait duration.
        """
        if queue_position <= 0:
            return timedelta(0)

        ms = queue_position * self.config.queue_wait_ms_per_job
        return timedelta(milliseconds=ms)

    def estimate_completion_time(
        self,
        page_count: int,
        queue_position: int = 0,
        current_stage: str | None = None,
        text_length: int | None = None,
        chunk_count: int | None = None,
    ) -> datetime:
        """Estimate job completion timestamp.

        Args:
            page_count: Number of pages in document.
            queue_position: Position in queue (0 = processing).
            current_stage: Current stage if already processing.
            text_length: Optional total text length.
            chunk_count: Optional chunk count.

        Returns:
            Estimated completion datetime.
        """
        now = datetime.now(UTC)

        # Queue wait time
        wait_time = self.estimate_queue_wait_time(queue_position)

        # Processing time
        if current_stage:
            process_time = self.estimate_remaining_time(
                current_stage, page_count, text_length, chunk_count
            )
        else:
            process_time = self.estimate_total_document_time(
                page_count, text_length, chunk_count
            )

        return now + wait_time + process_time

    # =========================================================================
    # Stage Progress Estimation
    # =========================================================================

    def estimate_stage_progress(
        self,
        current_stage: str,
        stage_progress: float = 0.0,
    ) -> int:
        """Calculate overall progress percentage based on stage.

        Each stage has a weight based on typical duration.
        Progress is calculated as: completed stages + partial current stage.

        Args:
            current_stage: Current processing stage name.
            stage_progress: Progress within current stage (0.0 - 1.0).

        Returns:
            Overall progress percentage (0-100).
        """
        # Stage weights (approximate percentage of total time)
        stage_weights = {
            "ocr": 40,  # OCR typically takes longest
            "validation": 10,
            "confidence": 2,
            "chunking": 8,
            "embedding": 15,
            "entity_extraction": 20,
            "alias_resolution": 5,
        }

        # Stage order
        stages = list(stage_weights.keys())

        # Normalize stage name
        normalized = current_stage.lower().replace(" ", "_").replace("-", "_")

        # Find current stage index
        try:
            current_idx = stages.index(normalized)
        except ValueError:
            logger.warning("unknown_stage_for_progress", stage=current_stage)
            return 0

        # Sum completed stage weights
        completed_weight = sum(stage_weights[s] for s in stages[:current_idx])

        # Add partial current stage
        current_weight = stage_weights.get(normalized, 0) * stage_progress

        total_progress = completed_weight + current_weight

        # Ensure bounds
        return max(0, min(100, int(total_progress)))


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_time_estimator() -> TimeEstimator:
    """Get singleton time estimator instance.

    Returns:
        TimeEstimator instance.
    """
    return TimeEstimator()
