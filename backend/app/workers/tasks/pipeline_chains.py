"""Unified task chains for document processing.

This module provides factory functions that create consistent task chains
for both small and large documents, ensuring feature parity.

The key insight: OCR must split for large documents (Document AI's 15-page limit),
but all post-OCR processing should be identical regardless of document size.

DPP-002: Chains now use link_error callbacks for centralized cleanup.
When any task raises PipelineTaskError, the chain stops immediately and
on_chain_error handles _mark_job_failed + _release_pipeline_lock_safe
as a safety net (tasks also do their own cleanup before raising).
"""

import structlog
from celery import chain as celery_chain

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Safety-net error callback (DPP-002 — P7/P8 wall)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="app.workers.tasks.pipeline_chains.on_chain_error",
    bind=True,
    ignore_result=True,
    queue="default",
)
def on_chain_error(
    self,  # type: ignore[no-untyped-def]
    failed_task_id: str,
    *,
    document_id: str | None = None,
    job_id: str | None = None,
    matter_id: str | None = None,
) -> None:
    """Safety-net error callback for the post-OCR chain.

    Fired by Celery's link_error when ANY task in the chain raises.
    Calls cleanup functions idempotently — if the task already did its
    own cleanup before raising, these are no-ops.

    This is the P8 wall: centralized cleanup instead of relying on
    every sibling task to independently remember the same cleanup steps.
    """
    from app.workers.tasks.document_tasks import (
        _mark_job_failed,
        _release_pipeline_lock_safe,
    )

    logger.error(
        "pipeline_chain_error",
        failed_task_id=failed_task_id,
        document_id=document_id,
        job_id=job_id,
        matter_id=matter_id,
    )

    # Both functions are idempotent and safe to call even if already called
    _mark_job_failed(
        job_id,
        f"Pipeline chain failed (task {failed_task_id})",
        "CHAIN_ERROR",
        matter_id,
    )
    _release_pipeline_lock_safe(document_id)


def create_post_ocr_chain(
    document_id: str,
    matter_id: str,
    job_id: str,
):
    """Create unified post-OCR processing chain.

    This chain runs after OCR completes (for both small and large documents).
    Docling layout extraction happens synchronously in chunk_document task.

    After extract_entities completes, it fans out citations, dates, and
    alias resolution in parallel via _dispatch_post_entity_tasks().

    The chain has a link_error callback (on_chain_error) that fires if ANY
    task raises an exception. This ensures cleanup (job failure marking,
    lock release) happens even if a task crashes before its own cleanup.

    Args:
        document_id: Document UUID
        matter_id: Matter UUID
        job_id: Processing job UUID

    Returns:
        Celery chain ready for apply_async()

    Example:
        # After OCR completes for a large document:
        chain = create_post_ocr_chain(doc_id, matter_id, job_id)
        chain.apply_async()
    """
    # Import here to avoid circular imports
    from app.workers.tasks.document_tasks import (
        calculate_confidence,
        chunk_document,
        embed_chunks,
        extract_entities,
        validate_ocr,
    )

    try:
        from app.workers.tasks.table_extraction_tasks import extract_tables

        _has_extract_tables = True
    except ImportError:
        _has_extract_tables = False
        logger.warning("extract_tables_import_failed", reason="docling not available")

    logger.info(
        "creating_post_ocr_chain",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
        has_extract_tables=_has_extract_tables,
    )

    # NOTE: validate_ocr only accepts document_id, not matter_id/job_id
    # The document_id is passed and flows through the chain via prev_result
    # extract_tables runs after chunking to create table chunks (Gap 5)
    # embed_chunks embeds ALL chunks (text + table) — queries by embedding IS NULL
    # extract_entities dispatches citations, dates, and aliases via _dispatch_post_entity_tasks()
    steps = [
        validate_ocr.s(document_id=document_id),
        calculate_confidence.s(),
        chunk_document.s(skip_bbox_linking=False),  # Docling layout runs here (2-4 sec)
    ]
    if _has_extract_tables:
        steps.append(extract_tables.s())  # Gap 5: extract tables + create table chunks
    steps.extend(
        [
            embed_chunks.s(),
            extract_entities.s(),
        ]
    )

    # DPP-002: Attach error callback so chain failures trigger centralized cleanup.
    # on_chain_error receives the failed task's ID plus the pipeline context.
    error_callback = on_chain_error.s(
        document_id=document_id,
        job_id=job_id,
        matter_id=matter_id,
    )
    c = celery_chain(*steps)
    c.link_error(error_callback)
    return c
