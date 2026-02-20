"""Unified task chains for document processing.

This module provides factory functions that create consistent task chains
for both small and large documents, ensuring feature parity.

The key insight: OCR must split for large documents (Document AI's 15-page limit),
but all post-OCR processing should be identical regardless of document size.
"""

from celery import chain as celery_chain

import structlog

logger = structlog.get_logger(__name__)


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
        validate_ocr,
        calculate_confidence,
        chunk_document,
        embed_chunks,
        extract_entities,
    )
    from app.workers.tasks.table_extraction_tasks import extract_tables

    logger.info(
        "creating_post_ocr_chain",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
    )

    # NOTE: validate_ocr only accepts document_id, not matter_id/job_id
    # The document_id is passed and flows through the chain via prev_result
    # extract_tables runs after chunking to create table chunks (Gap 5)
    # embed_chunks embeds ALL chunks (text + table) — queries by embedding IS NULL
    # extract_entities dispatches citations, dates, and aliases via _dispatch_post_entity_tasks()
    return celery_chain(
        validate_ocr.s(document_id=document_id),
        calculate_confidence.s(),
        chunk_document.s(skip_bbox_linking=False),  # Docling layout runs here (2-4 sec)
        extract_tables.s(),  # Gap 5: extract tables + create table chunks
        embed_chunks.s(),
        extract_entities.s(),
    )
