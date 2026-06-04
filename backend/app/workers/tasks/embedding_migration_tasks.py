"""Celery tasks for embedding model migration.

Story 1.4: Implement Embedding Migration Path

Provides background tasks for migrating embeddings when upgrading
embedding models. Runs asynchronously with progress tracking.
"""

import structlog

from app.services.rag.embedding_migration import (
    MigrationConfig,
    get_current_embedding_model_version,
    get_embedding_migration_service,
)
from app.workers.celery_app import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)


# =============================================================================
# Validation Constants
# =============================================================================

MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 500
DEFAULT_BATCH_SIZE = 50


# =============================================================================
# Helper function for async task execution
# =============================================================================


def _run_async(coro):
    """Run async coroutine in sync context for Celery tasks."""
    return run_async(coro)


def _validate_migration_params(
    source_model_version: str,
    target_model_version: str | None,
    batch_size: int,
) -> dict | None:
    """Validate migration task parameters.

    Args:
        source_model_version: Source embedding model version to migrate from.
        target_model_version: Target model version (can be None).
        batch_size: Number of chunks to process per batch.

    Returns:
        None if valid, or dict with error details if invalid.
    """
    # Validate source_model_version is non-empty string
    if not source_model_version or not isinstance(source_model_version, str):
        return {
            "status": "validation_error",
            "error": "source_model_version must be a non-empty string",
            "field": "source_model_version",
        }

    if source_model_version.strip() != source_model_version:
        return {
            "status": "validation_error",
            "error": "source_model_version cannot have leading/trailing whitespace",
            "field": "source_model_version",
        }

    # Validate target_model_version if provided
    if target_model_version is not None:  # noqa: SIM102
        if not isinstance(target_model_version, str) or not target_model_version:
            return {
                "status": "validation_error",
                "error": "target_model_version must be a non-empty string if provided",
                "field": "target_model_version",
            }

    # Validate batch_size is within acceptable range
    if not isinstance(batch_size, int) or batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
        return {
            "status": "validation_error",
            "error": f"batch_size must be an integer between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}",
            "field": "batch_size",
            "value": batch_size,
        }

    # Source and target should be different
    effective_target = target_model_version or get_current_embedding_model_version()
    if source_model_version == effective_target:
        return {
            "status": "validation_error",
            "error": "source_model_version and target_model_version cannot be the same",
            "source": source_model_version,
            "target": effective_target,
        }

    return None


# =============================================================================
# Migration Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.embedding_migration_tasks.migrate_embeddings",
    bind=True,
    max_retries=0,  # Don't retry migrations - they're resumable
    soft_time_limit=7200,  # 2 hour soft limit
    time_limit=7500,  # 2.5 hour hard limit
)
def migrate_embeddings(
    self,
    source_model_version: str,
    target_model_version: str | None = None,
    matter_id: str | None = None,
    batch_size: int = 50,
    resume_from_chunk_id: str | None = None,
) -> dict:
    """Migrate embeddings from one model version to another.

    Story 1.4: Implement Embedding Migration Path

    This task runs in the background to re-embed document chunks
    when upgrading embedding models.

    Args:
        source_model_version: Current embedding model version to migrate from.
        target_model_version: Target model version (defaults to current).
        matter_id: Optional matter ID to limit migration scope.
        batch_size: Number of chunks to process per batch.
        resume_from_chunk_id: Resume migration from this chunk ID.

    Returns:
        Dict with migration results.

    Example:
        >>> from app.workers.tasks.embedding_migration_tasks import migrate_embeddings
        >>> result = migrate_embeddings.delay(
        ...     source_model_version="text-embedding-ada-002",
        ...     target_model_version="text-embedding-3-small",
        ... )
        >>> result.get()  # Wait for completion
        {'status': 'completed', 'processed': 1000, ...}
    """
    # Validate input parameters before starting
    validation_error = _validate_migration_params(
        source_model_version=source_model_version,
        target_model_version=target_model_version,
        batch_size=batch_size,
    )
    if validation_error:
        logger.warning(
            "embedding_migration_validation_failed",
            **validation_error,
        )
        return validation_error

    logger.info(
        "embedding_migration_task_started",
        source_version=source_model_version,
        target_version=target_model_version,
        matter_id=matter_id,
        batch_size=batch_size,
        resume_from=resume_from_chunk_id,
    )

    try:
        service = get_embedding_migration_service()

        config = MigrationConfig(
            source_model_version=source_model_version,
            target_model_version=target_model_version or get_current_embedding_model_version(),
            matter_id=matter_id,
            batch_size=batch_size,
            resume_from_chunk_id=resume_from_chunk_id,
        )

        progress = _run_async(service.start_migration(config))

        result = {
            "status": "completed" if progress.is_complete else "partial",
            "processed_chunks": progress.processed_chunks,
            "failed_chunks": progress.failed_chunks,
            "skipped_chunks": progress.skipped_chunks,
            "total_chunks": progress.total_chunks,
            "progress_percent": progress.progress_percent,
            "last_chunk_id": progress.last_chunk_id,
            "error_message": progress.error_message,
        }

        logger.info(
            "embedding_migration_task_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "embedding_migration_task_failed",
            error=str(e),
            source_version=source_model_version,
            target_version=target_model_version,
        )
        return {
            "status": "failed",
            "error": str(e),
        }


@celery_app.task(
    name="app.workers.tasks.embedding_migration_tasks.check_migration_status",
)
def check_migration_status(
    matter_id: str | None = None,
) -> dict:
    """Check embedding migration status and version distribution.

    Args:
        matter_id: Optional matter ID to filter.

    Returns:
        Dict with version distribution and migration status.
    """
    try:
        service = get_embedding_migration_service()
        status = _run_async(service.get_migration_status(matter_id))

        logger.info(
            "embedding_migration_status_checked",
            matter_id=matter_id,
            **status,
        )

        return status

    except Exception as e:
        logger.error(
            "embedding_migration_status_check_failed",
            error=str(e),
        )
        return {
            "status": "error",
            "error": str(e),
        }
