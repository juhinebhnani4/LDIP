"""Celery tasks related to document processing.

These are intentionally minimal placeholders for the foundation story.
Future stories (Epic 2) will implement OCR, chunking, and embedding here.
"""

import structlog

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)

@celery_app.task(name="app.workers.tasks.document_tasks.process_document")  # type: ignore[untyped-decorator]
def process_document(document_id: str) -> dict[str, str]:
    """Placeholder task for processing a document.

    Args:
        document_id: Document identifier.

    Returns:
        Task result payload.
    """
    logger.info("document_task_placeholder", task="process_document", document_id=document_id)
    return {"status": "not_implemented", "document_id": document_id}


