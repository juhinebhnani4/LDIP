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
    skip_downstream_dispatch: bool = False,
):
    """Create unified post-OCR processing chain.

    This chain runs after OCR completes (for both small and large documents).
    Docling layout extraction happens synchronously in chunk_document task.

    Args:
        document_id: Document UUID
        matter_id: Matter UUID
        job_id: Processing job UUID
        skip_downstream_dispatch: If True, resolve_aliases won't dispatch
            extract_citations/extract_dates (use when caller handles dispatch)

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
        resolve_aliases,
    )

    logger.info(
        "creating_post_ocr_chain",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
        skip_downstream_dispatch=skip_downstream_dispatch,
    )

    # NOTE: validate_ocr only accepts document_id, not matter_id/job_id
    # The document_id is passed and flows through the chain via prev_result
    return celery_chain(
        validate_ocr.s(document_id=document_id),
        calculate_confidence.s(),
        chunk_document.s(skip_bbox_linking=False),  # Docling runs here (2-4 sec)
        embed_chunks.s(),
        extract_entities.s(),
        resolve_aliases.s(skip_downstream_dispatch=skip_downstream_dispatch),
    )
