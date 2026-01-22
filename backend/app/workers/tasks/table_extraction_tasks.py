"""Celery tasks for table extraction.

Story: RAG Production Gaps - Feature 1
Extracts tables from documents using Docling after OCR completes.
Tables are stored separately and linked to chunks.

This task can run in parallel with chunking for efficiency.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.services.document_service import DocumentService, get_document_service
from app.services.storage_service import StorageService, get_storage_service
from app.services.supabase.client import get_supabase_client as get_supabase

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger(__name__)


class TableExtractionTaskError(Exception):
    """Error in table extraction task."""

    def __init__(self, message: str, code: str = "TABLE_TASK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


@celery_app.task(
    name="app.workers.tasks.table_extraction_tasks.extract_tables",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
)  # type: ignore[misc]
def extract_tables(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    storage_service: StorageService | None = None,
) -> dict[str, str | int | float | None]:
    """Extract tables from a document using Docling.

    This task runs after OCR completes and can run in parallel with chunking.
    Tables are stored in the document_tables table for retrieval.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        storage_service: Optional StorageService instance (for testing).

    Returns:
        Task result with table extraction summary.
    """
    settings = get_settings()

    # Check if table extraction is enabled
    if not settings.table_extraction_enabled:
        logger.debug("table_extraction_disabled_by_config")
        return {
            "status": "table_extraction_skipped",
            "reason": "Table extraction disabled in config",
        }

    # Get document_id from prev_result or parameter
    doc_id = document_id
    job_id: str | None = None
    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("extract_tables_no_document_id")
        return {
            "status": "table_extraction_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Skip if previous task failed
    if prev_result:
        prev_status = prev_result.get("status")
        failed_statuses = ("failed", "error", "ocr_failed")
        if prev_status in failed_statuses:
            logger.info(
                "extract_tables_skipped",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "table_extraction_skipped",
                "document_id": doc_id,
                "job_id": job_id,
                "reason": f"Previous task failed: {prev_status}",
            }

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    store_service = storage_service or get_storage_service()

    logger.info(
        "extract_tables_task_started",
        document_id=doc_id,
        job_id=job_id,
        retry_count=self.request.retries,
    )

    try:
        # Get document info
        storage_path, matter_id = doc_service.get_document_for_processing(doc_id)

        # Download PDF from storage
        logger.info(
            "extract_tables_downloading",
            document_id=doc_id,
            storage_path=storage_path,
        )
        pdf_content = store_service.download_file(storage_path)

        # Save to temp file for Docling (it requires file path)
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)

        try:
            # Import here to avoid loading Docling at startup
            from app.services.table_extraction import get_table_extractor

            extractor = get_table_extractor()

            # Run async extraction in sync context
            async def _extract_async():
                return await extractor.extract_tables(
                    file_path=tmp_path,
                    matter_id=matter_id,
                    document_id=doc_id,
                )

            result = asyncio.run(_extract_async())

            # Store tables in database
            if result.has_tables:
                _store_tables(result, matter_id, doc_id)

            logger.info(
                "extract_tables_task_completed",
                document_id=doc_id,
                job_id=job_id,
                table_count=result.total_tables,
                processing_time_ms=result.processing_time_ms,
                error=result.error,
            )

            return {
                "status": "table_extraction_complete" if result.success else "table_extraction_partial",
                "document_id": doc_id,
                "matter_id": matter_id,
                "job_id": job_id,
                "table_count": result.total_tables,
                "processing_time_ms": result.processing_time_ms,
                "error": result.error,
            }

        finally:
            # Clean up temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass

    except Exception as e:
        logger.error(
            "extract_tables_task_failed",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Don't fail the task - table extraction is non-critical
        return {
            "status": "table_extraction_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": "EXTRACTION_FAILED",
            "error_message": str(e),
        }


def _store_tables(
    result: "TableExtractionResult",  # noqa: F821
    matter_id: str,
    document_id: str,
) -> None:
    """Store extracted tables in database.

    Args:
        result: TableExtractionResult from extractor.
        matter_id: Matter UUID for isolation.
        document_id: Document UUID for linkage.
    """
    from app.services.table_extraction.models import TableExtractionResult

    supabase = get_supabase()

    for table in result.tables:
        try:
            supabase.table("document_tables").insert({
                "document_id": document_id,
                "matter_id": matter_id,
                "table_index": table.table_index,
                "page_number": table.page_number,
                "markdown_content": table.markdown_content,
                "row_count": table.row_count,
                "col_count": table.col_count,
                "confidence": table.confidence,
                "bounding_box": table.bounding_box.model_dump() if table.bounding_box else None,
                "caption": table.caption,
            }).execute()

            logger.debug(
                "table_stored",
                document_id=document_id,
                table_index=table.table_index,
                page_number=table.page_number,
            )

        except Exception as e:
            logger.warning(
                "table_store_failed",
                document_id=document_id,
                table_index=table.table_index,
                error=str(e),
            )
            # Continue storing other tables
