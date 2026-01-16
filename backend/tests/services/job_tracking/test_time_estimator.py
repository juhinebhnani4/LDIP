"""Unit tests for the Time Estimator Service.

Story 2c-3: Background Job Status Tracking and Retry
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.services.job_tracking.time_estimator import (
    DEFAULT_ALIAS_MS_FIXED,
    DEFAULT_CHUNK_MS_PER_1K_CHARS,
    DEFAULT_CONFIDENCE_MS_FIXED,
    DEFAULT_EMBED_MS_PER_CHUNK,
    DEFAULT_ENTITY_MS_PER_CHUNK,
    DEFAULT_OCR_MS_PER_PAGE,
    DEFAULT_QUEUE_WAIT_MS_PER_JOB,
    DEFAULT_VALIDATION_MS_PER_PAGE,
    TimeEstimator,
    TimeEstimatorConfig,
    get_estimator_config,
    get_time_estimator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def estimator():
    """Create a TimeEstimator with default configuration."""
    # Clear cache to get fresh config
    get_estimator_config.cache_clear()
    return TimeEstimator()


@pytest.fixture
def custom_config():
    """Create a custom TimeEstimatorConfig."""
    config = TimeEstimatorConfig()
    config.ocr_ms_per_page = 2000  # Faster than default
    config.embed_ms_per_chunk = 100
    config.entity_ms_per_chunk = 300
    return config


# =============================================================================
# Test Configuration
# =============================================================================


class TestTimeEstimatorConfig:
    """Tests for TimeEstimatorConfig."""

    def test_uses_default_values(self) -> None:
        """Should use default values when env vars not set."""
        # Clear cache
        get_estimator_config.cache_clear()

        config = TimeEstimatorConfig()

        assert config.ocr_ms_per_page == DEFAULT_OCR_MS_PER_PAGE
        assert config.validation_ms_per_page == DEFAULT_VALIDATION_MS_PER_PAGE
        assert config.confidence_ms_fixed == DEFAULT_CONFIDENCE_MS_FIXED
        assert config.chunk_ms_per_1k_chars == DEFAULT_CHUNK_MS_PER_1K_CHARS
        assert config.embed_ms_per_chunk == DEFAULT_EMBED_MS_PER_CHUNK
        assert config.entity_ms_per_chunk == DEFAULT_ENTITY_MS_PER_CHUNK
        assert config.alias_ms_fixed == DEFAULT_ALIAS_MS_FIXED
        assert config.queue_wait_ms_per_job == DEFAULT_QUEUE_WAIT_MS_PER_JOB

    def test_reads_from_environment(self) -> None:
        """Should read values from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "JOB_ESTIMATE_OCR_MS_PER_PAGE": "5000",
                "JOB_ESTIMATE_EMBED_MS_PER_CHUNK": "500",
            },
        ):
            config = TimeEstimatorConfig()

            assert config.ocr_ms_per_page == 5000
            assert config.embed_ms_per_chunk == 500
            # Others should still be defaults
            assert config.validation_ms_per_page == DEFAULT_VALIDATION_MS_PER_PAGE


# =============================================================================
# Test Individual Stage Estimates
# =============================================================================


class TestOCRTimeEstimate:
    """Tests for OCR time estimation."""

    def test_estimates_ocr_time_for_pages(self, estimator: TimeEstimator) -> None:
        """Should estimate OCR time based on page count."""
        result = estimator.estimate_ocr_time(page_count=10)

        expected_ms = 10 * DEFAULT_OCR_MS_PER_PAGE
        assert result == timedelta(milliseconds=expected_ms)

    def test_returns_zero_for_zero_pages(self, estimator: TimeEstimator) -> None:
        """Should return zero for zero pages."""
        result = estimator.estimate_ocr_time(page_count=0)
        assert result == timedelta(0)

    def test_returns_zero_for_negative_pages(self, estimator: TimeEstimator) -> None:
        """Should return zero for negative pages."""
        result = estimator.estimate_ocr_time(page_count=-5)
        assert result == timedelta(0)


class TestValidationTimeEstimate:
    """Tests for validation time estimation."""

    def test_estimates_validation_time(self, estimator: TimeEstimator) -> None:
        """Should estimate validation time based on page count."""
        result = estimator.estimate_validation_time(page_count=20)

        expected_ms = 20 * DEFAULT_VALIDATION_MS_PER_PAGE
        assert result == timedelta(milliseconds=expected_ms)

    def test_returns_zero_for_zero_pages(self, estimator: TimeEstimator) -> None:
        """Should return zero for zero pages."""
        result = estimator.estimate_validation_time(page_count=0)
        assert result == timedelta(0)


class TestConfidenceTimeEstimate:
    """Tests for confidence calculation time estimation."""

    def test_returns_fixed_time(self, estimator: TimeEstimator) -> None:
        """Should return fixed time for confidence calculation."""
        result = estimator.estimate_confidence_time()
        assert result == timedelta(milliseconds=DEFAULT_CONFIDENCE_MS_FIXED)


class TestChunkingTimeEstimate:
    """Tests for chunking time estimation."""

    def test_estimates_chunking_time(self, estimator: TimeEstimator) -> None:
        """Should estimate chunking time based on text length."""
        result = estimator.estimate_chunking_time(text_length=10000)

        # 10K chars = 10 units of 1K chars
        expected_ms = 10 * DEFAULT_CHUNK_MS_PER_1K_CHARS
        assert result == timedelta(milliseconds=expected_ms)

    def test_returns_zero_for_zero_length(self, estimator: TimeEstimator) -> None:
        """Should return zero for zero text length."""
        result = estimator.estimate_chunking_time(text_length=0)
        assert result == timedelta(0)


class TestEmbeddingTimeEstimate:
    """Tests for embedding time estimation."""

    def test_estimates_embedding_time(self, estimator: TimeEstimator) -> None:
        """Should estimate embedding time based on chunk count."""
        result = estimator.estimate_embedding_time(chunk_count=50)

        expected_ms = 50 * DEFAULT_EMBED_MS_PER_CHUNK
        assert result == timedelta(milliseconds=expected_ms)

    def test_returns_zero_for_zero_chunks(self, estimator: TimeEstimator) -> None:
        """Should return zero for zero chunks."""
        result = estimator.estimate_embedding_time(chunk_count=0)
        assert result == timedelta(0)


class TestEntityExtractionTimeEstimate:
    """Tests for entity extraction time estimation."""

    def test_estimates_entity_time(self, estimator: TimeEstimator) -> None:
        """Should estimate entity extraction time based on chunk count."""
        result = estimator.estimate_entity_extraction_time(chunk_count=30)

        expected_ms = 30 * DEFAULT_ENTITY_MS_PER_CHUNK
        assert result == timedelta(milliseconds=expected_ms)

    def test_returns_zero_for_zero_chunks(self, estimator: TimeEstimator) -> None:
        """Should return zero for zero chunks."""
        result = estimator.estimate_entity_extraction_time(chunk_count=0)
        assert result == timedelta(0)


class TestAliasResolutionTimeEstimate:
    """Tests for alias resolution time estimation."""

    def test_returns_fixed_time(self, estimator: TimeEstimator) -> None:
        """Should return fixed time for alias resolution."""
        result = estimator.estimate_alias_resolution_time()
        assert result == timedelta(milliseconds=DEFAULT_ALIAS_MS_FIXED)


# =============================================================================
# Test Combined Estimates
# =============================================================================


class TestTotalDocumentTimeEstimate:
    """Tests for total document time estimation."""

    def test_estimates_total_time_with_all_params(
        self, estimator: TimeEstimator
    ) -> None:
        """Should calculate total time with all parameters provided."""
        result = estimator.estimate_total_document_time(
            page_count=10,
            text_length=20000,
            chunk_count=40,
        )

        # Calculate expected total
        expected = timedelta(0)
        expected += timedelta(milliseconds=10 * DEFAULT_OCR_MS_PER_PAGE)  # OCR
        expected += timedelta(milliseconds=10 * DEFAULT_VALIDATION_MS_PER_PAGE)  # Validation
        expected += timedelta(milliseconds=DEFAULT_CONFIDENCE_MS_FIXED)  # Confidence
        expected += timedelta(milliseconds=20 * DEFAULT_CHUNK_MS_PER_1K_CHARS)  # Chunking
        expected += timedelta(milliseconds=40 * DEFAULT_EMBED_MS_PER_CHUNK)  # Embedding
        expected += timedelta(milliseconds=40 * DEFAULT_ENTITY_MS_PER_CHUNK)  # Entity
        expected += timedelta(milliseconds=DEFAULT_ALIAS_MS_FIXED)  # Alias

        assert result == expected

    def test_estimates_text_and_chunks_from_pages(
        self, estimator: TimeEstimator
    ) -> None:
        """Should estimate text length and chunk count from page count."""
        result = estimator.estimate_total_document_time(page_count=5)

        # Should use defaults: 2000 chars/page, 4 chunks/page
        # So 5 pages = 10000 chars, 20 chunks
        expected = timedelta(0)
        expected += timedelta(milliseconds=5 * DEFAULT_OCR_MS_PER_PAGE)
        expected += timedelta(milliseconds=5 * DEFAULT_VALIDATION_MS_PER_PAGE)
        expected += timedelta(milliseconds=DEFAULT_CONFIDENCE_MS_FIXED)
        expected += timedelta(milliseconds=10 * DEFAULT_CHUNK_MS_PER_1K_CHARS)  # 10K chars
        expected += timedelta(milliseconds=20 * DEFAULT_EMBED_MS_PER_CHUNK)  # 20 chunks
        expected += timedelta(milliseconds=20 * DEFAULT_ENTITY_MS_PER_CHUNK)  # 20 chunks
        expected += timedelta(milliseconds=DEFAULT_ALIAS_MS_FIXED)

        assert result == expected

    def test_returns_zero_for_zero_pages(self, estimator: TimeEstimator) -> None:
        """Should return zero for zero pages."""
        result = estimator.estimate_total_document_time(page_count=0)
        assert result == timedelta(0)


class TestRemainingTimeEstimate:
    """Tests for remaining time estimation."""

    def test_estimates_remaining_from_early_stage(
        self, estimator: TimeEstimator
    ) -> None:
        """Should estimate remaining time from an early stage."""
        result = estimator.estimate_remaining_time(
            current_stage="ocr",
            page_count=10,
            text_length=20000,
            chunk_count=40,
        )

        # Should include all stages after OCR
        expected = timedelta(0)
        expected += timedelta(milliseconds=10 * DEFAULT_VALIDATION_MS_PER_PAGE)
        expected += timedelta(milliseconds=DEFAULT_CONFIDENCE_MS_FIXED)
        expected += timedelta(milliseconds=20 * DEFAULT_CHUNK_MS_PER_1K_CHARS)
        expected += timedelta(milliseconds=40 * DEFAULT_EMBED_MS_PER_CHUNK)
        expected += timedelta(milliseconds=40 * DEFAULT_ENTITY_MS_PER_CHUNK)
        expected += timedelta(milliseconds=DEFAULT_ALIAS_MS_FIXED)

        assert result == expected

    def test_estimates_remaining_from_late_stage(
        self, estimator: TimeEstimator
    ) -> None:
        """Should estimate remaining time from a late stage."""
        result = estimator.estimate_remaining_time(
            current_stage="entity_extraction",
            page_count=10,
            text_length=20000,
            chunk_count=40,
        )

        # Should only include alias resolution
        expected = timedelta(milliseconds=DEFAULT_ALIAS_MS_FIXED)
        assert result == expected

    def test_returns_full_estimate_for_unknown_stage(
        self, estimator: TimeEstimator
    ) -> None:
        """Should return full estimate for unknown stage."""
        result = estimator.estimate_remaining_time(
            current_stage="unknown_stage",
            page_count=10,
        )

        # Should return full estimate
        full_estimate = estimator.estimate_total_document_time(page_count=10)
        assert result == full_estimate


# =============================================================================
# Test Queue Wait Time
# =============================================================================


class TestQueueWaitTimeEstimate:
    """Tests for queue wait time estimation."""

    def test_estimates_wait_time(self, estimator: TimeEstimator) -> None:
        """Should estimate wait time based on queue position."""
        result = estimator.estimate_queue_wait_time(queue_position=5)

        expected_ms = 5 * DEFAULT_QUEUE_WAIT_MS_PER_JOB
        assert result == timedelta(milliseconds=expected_ms)

    def test_returns_zero_for_front_of_queue(self, estimator: TimeEstimator) -> None:
        """Should return zero for position 0."""
        result = estimator.estimate_queue_wait_time(queue_position=0)
        assert result == timedelta(0)

    def test_returns_zero_for_negative_position(
        self, estimator: TimeEstimator
    ) -> None:
        """Should return zero for negative position."""
        result = estimator.estimate_queue_wait_time(queue_position=-1)
        assert result == timedelta(0)


# =============================================================================
# Test Completion Time Estimation
# =============================================================================


class TestCompletionTimeEstimate:
    """Tests for completion time estimation."""

    def test_estimates_completion_with_queue_wait(
        self, estimator: TimeEstimator
    ) -> None:
        """Should include queue wait in completion estimate."""
        before = datetime.now(UTC)
        result = estimator.estimate_completion_time(
            page_count=10,
            queue_position=3,
        )
        after = datetime.now(UTC)

        # Should be in the future
        assert result >= before

        # Calculate expected minimum time
        queue_wait = timedelta(milliseconds=3 * DEFAULT_QUEUE_WAIT_MS_PER_JOB)
        process_time = estimator.estimate_total_document_time(page_count=10)

        expected_min = before + queue_wait + process_time
        expected_max = after + queue_wait + process_time

        assert expected_min <= result <= expected_max

    def test_uses_remaining_time_when_stage_provided(
        self, estimator: TimeEstimator
    ) -> None:
        """Should use remaining time when current stage is provided."""
        before = datetime.now(UTC)
        result = estimator.estimate_completion_time(
            page_count=10,
            queue_position=0,
            current_stage="chunking",
        )

        remaining_time = estimator.estimate_remaining_time(
            current_stage="chunking",
            page_count=10,
        )

        # Result should be approximately now + remaining time
        assert result >= before + remaining_time


# =============================================================================
# Test Stage Progress Estimation
# =============================================================================


class TestStageProgressEstimate:
    """Tests for stage progress estimation."""

    def test_calculates_progress_for_ocr(self, estimator: TimeEstimator) -> None:
        """Should calculate progress percentage for OCR stage."""
        # OCR is the first stage with 40% weight
        result = estimator.estimate_stage_progress(
            current_stage="ocr",
            stage_progress=0.5,  # 50% through OCR
        )

        # 0 completed stages + 50% of 40% = 20%
        assert result == 20

    def test_calculates_progress_for_middle_stage(
        self, estimator: TimeEstimator
    ) -> None:
        """Should calculate progress for middle stage."""
        # Chunking is after OCR (40%) + validation (10%) + confidence (2%)
        result = estimator.estimate_stage_progress(
            current_stage="chunking",
            stage_progress=0.0,  # Just started chunking
        )

        # 52% completed (40 + 10 + 2)
        assert result == 52

    def test_calculates_progress_for_last_stage(
        self, estimator: TimeEstimator
    ) -> None:
        """Should calculate progress near end."""
        # Alias resolution is last, after 95% complete
        result = estimator.estimate_stage_progress(
            current_stage="alias_resolution",
            stage_progress=0.5,  # 50% through alias
        )

        # 95% + 50% of 5% = 97.5% -> 97
        assert result == 97

    def test_returns_zero_for_unknown_stage(self, estimator: TimeEstimator) -> None:
        """Should return 0 for unknown stage."""
        result = estimator.estimate_stage_progress(
            current_stage="unknown_stage",
            stage_progress=0.5,
        )
        assert result == 0

    def test_normalizes_stage_names(self, estimator: TimeEstimator) -> None:
        """Should handle different stage name formats."""
        # Test with spaces
        result1 = estimator.estimate_stage_progress("entity extraction", 0.0)
        # Test with dashes
        result2 = estimator.estimate_stage_progress("entity-extraction", 0.0)
        # Test with underscores (canonical)
        result3 = estimator.estimate_stage_progress("entity_extraction", 0.0)

        assert result1 == result2 == result3


# =============================================================================
# Test Custom Configuration
# =============================================================================


class TestCustomConfiguration:
    """Tests with custom configuration."""

    def test_uses_custom_config(self, custom_config: TimeEstimatorConfig) -> None:
        """Should use custom configuration values."""
        estimator = TimeEstimator(config=custom_config)

        # OCR should be faster with custom config
        result = estimator.estimate_ocr_time(page_count=10)

        expected_ms = 10 * custom_config.ocr_ms_per_page
        assert result == timedelta(milliseconds=expected_ms)
        assert result < timedelta(milliseconds=10 * DEFAULT_OCR_MS_PER_PAGE)


# =============================================================================
# Test Singleton Pattern
# =============================================================================


class TestTimeEstimatorFactory:
    """Tests for time estimator factory function."""

    def test_returns_singleton_instance(self) -> None:
        """Should return the same instance on multiple calls."""
        # Clear the cache first
        get_time_estimator.cache_clear()

        estimator1 = get_time_estimator()
        estimator2 = get_time_estimator()

        assert estimator1 is estimator2

        # Clear cache after test
        get_time_estimator.cache_clear()
