"""Celery tasks for table extraction.

Story: RAG Production Gaps - Feature 1 + Gap 5 (Table-Aware Embedding)
Extracts tables from documents using Docling after OCR completes.
Tables are stored in document_tables AND as searchable chunks in the
chunks table (chunk_type='table'), enabling hybrid search (BM25 + semantic).

This task runs after chunk_document in the pipeline chain, before embed_chunks.
Table chunks are embedded and FTS-indexed automatically by downstream tasks.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from app.core.config import get_settings
from app.services.document_service import DocumentService, get_document_service
from app.services.storage_service import StorageService, get_storage_service
from app.services.supabase.client import get_service_client
from app.workers.celery import celery_app
from app.workers.utils import run_async

if TYPE_CHECKING:
    from pathlib import Path

    from app.services.table_extraction.models import (
        ExtractedTable,
        TableExtractionResult,
    )

logger = structlog.get_logger(__name__)

# Max tokens per table chunk — matches parent chunk size for consistency
TABLE_CHUNK_MAX_TOKENS = 2000
# Minimum confidence to create a searchable chunk from a table
TABLE_CHUNK_MIN_CONFIDENCE = 0.5


class TableExtractionTaskError(Exception):
    """Error in table extraction task."""

    def __init__(self, message: str, code: str = "TABLE_TASK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


@celery_app.task(
    name="app.workers.tasks.table_extraction_tasks.extract_tables",
    bind=True,
    max_retries=2,
    soft_time_limit=600,  # 10 minutes soft limit for Docling ML extraction
    time_limit=660,  # 11 minutes hard limit
)  # type: ignore[misc]
def extract_tables(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    storage_service: StorageService | None = None,
) -> dict[str, str | int | float | None]:
    """Extract tables from a document using Docling and create searchable chunks.

    This task runs after chunk_document in the pipeline chain. It:
    1. Extracts tables from the PDF using Docling ML
    2. Stores structured table data in document_tables
    3. Creates table chunks in the chunks table (chunk_type='table')

    Table chunks are then embedded by embed_chunks and FTS-indexed automatically.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        storage_service: Optional StorageService instance (for testing).

    Returns:
        Task result with table extraction summary (always returns, never raises).
    """
    settings = get_settings()

    # Check if table extraction is enabled
    if not settings.table_extraction_enabled:
        logger.debug("table_extraction_disabled_by_config")
        # Pass through document_id for downstream tasks
        result: dict[str, str | int | float | None] = {
            "status": "table_extraction_skipped",
            "reason": "Table extraction disabled in config",
        }
        if prev_result and prev_result.get("document_id"):
            result["document_id"] = prev_result["document_id"]
            result["job_id"] = prev_result.get("job_id")
        return result

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
        failed_statuses = (
            "failed",
            "error",
            "ocr_failed",
            "chunking_failed",
            "chunking_skipped",
        )
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

        # Save to temp file for Docling (it requires file path).
        # Track tmp_path at outer scope so cleanup runs even if write() throws.
        import tempfile
        from pathlib import Path

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(pdf_content)

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

            result = run_async(_extract_async())

            # Store tables in document_tables and create searchable chunks
            table_chunk_count = 0
            if result.has_tables:
                _store_tables(result, matter_id, doc_id)
                table_chunk_count = _create_table_chunks(
                    result,
                    matter_id,
                    doc_id,
                )

            logger.info(
                "extract_tables_task_completed",
                document_id=doc_id,
                job_id=job_id,
                table_count=result.total_tables,
                table_chunk_count=table_chunk_count,
                processing_time_ms=result.processing_time_ms,
                error=result.error,
            )

            return {
                "status": "table_extraction_complete"
                if result.success
                else "table_extraction_partial",
                "document_id": doc_id,
                "matter_id": matter_id,
                "job_id": job_id,
                "table_count": result.total_tables,
                "table_chunk_count": table_chunk_count,
                "processing_time_ms": result.processing_time_ms,
                "error": result.error,
            }
        finally:
            # Clean up temp file — runs regardless of where the exception occurred
            if tmp_path is not None:
                with contextlib.suppress(Exception):
                    tmp_path.unlink()

    except ConnectionError as e:
        # Manual retry for transient network errors. We handle this inside
        # the except block (not via autoretry_for) to preserve the "never raises"
        # contract. autoretry_for intercepts exceptions BEFORE this handler,
        # and when retries exhaust, MaxRetriesExceededError breaks the Celery chain.
        #
        # With manual retry: if retries remain, self.retry() raises Retry (Celery
        # re-queues the task). If retries are exhausted, we return gracefully
        # so the chain continues to embed_chunks.
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.warning(
                "extract_tables_connection_error_retrying",
                document_id=doc_id,
                job_id=job_id,
                retry=retry_count + 1,
                max_retries=self.max_retries,
                error=str(e),
            )
            # self.retry() raises Retry exception — Celery re-queues the task
            raise self.retry(exc=e, countdown=min(30 * (2**retry_count), 60)) from e

        # Retries exhausted — return gracefully so the chain continues
        logger.error(
            "extract_tables_connection_error_exhausted",
            document_id=doc_id,
            job_id=job_id,
            retries_attempted=retry_count,
            error=str(e),
        )
        return {
            "status": "table_extraction_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": "CONNECTION_ERROR",
            "error_message": f"Network error after {retry_count} retries: {e}",
        }

    except Exception as e:
        logger.error(
            "extract_tables_task_failed",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Don't fail the task - table extraction is non-critical
        # Pass through document_id so embed_chunks can still run
        return {
            "status": "table_extraction_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": "EXTRACTION_FAILED",
            "error_message": str(e),
        }


def _store_tables(
    result: TableExtractionResult,
    matter_id: str,
    document_id: str,
) -> None:
    """Store extracted tables in document_tables.

    Handles idempotency by deleting existing tables for this document first.

    Args:
        result: TableExtractionResult from extractor.
        matter_id: Matter UUID for isolation.
        document_id: Document UUID for linkage.
    """
    # Use service client (not anon client) for write operations in background tasks.
    # Background workers have no user context, so RLS with anon client may silently fail.
    supabase = get_service_client()
    if supabase is None:
        logger.warning("table_store_skipped_no_client", document_id=document_id)
        return

    # Idempotency: delete existing tables for this document before re-inserting
    try:
        supabase.table("document_tables").delete().eq(
            "document_id", document_id
        ).execute()
    except Exception as e:
        logger.warning(
            "table_cleanup_failed",
            document_id=document_id,
            error=str(e),
        )

    for table in result.tables:
        try:
            supabase.table("document_tables").insert(
                {
                    "document_id": document_id,
                    "matter_id": matter_id,
                    "table_index": table.table_index,
                    "page_number": table.page_number,
                    "markdown_content": table.markdown_content,
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                    "confidence": table.confidence,
                    "bounding_box": table.bounding_box.model_dump()
                    if table.bounding_box
                    else None,
                    "caption": table.caption,
                }
            ).execute()

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


def _create_table_chunks(
    result: TableExtractionResult,
    matter_id: str,
    document_id: str,
) -> int:
    """Create searchable chunks from extracted tables.

    Gap 5: Table-Aware Embedding.
    Inserts table content as chunks with chunk_type='table' into the chunks
    table, enabling hybrid search (BM25 + semantic). Large tables are split
    by rows to stay within token limits.

    Table chunks are self-contained (parent_chunk_id=NULL) and skip parent
    context expansion in the RAG adapter.

    Args:
        result: TableExtractionResult from extractor.
        matter_id: Matter UUID for isolation.
        document_id: Document UUID for linkage.

    Returns:
        Number of table chunks created.
    """
    from app.services.chunking.token_counter import count_tokens

    client = get_service_client()
    if client is None:
        logger.warning(
            "table_chunks_skipped_no_client",
            document_id=document_id,
        )
        return 0

    # Idempotency: delete existing table chunks for this document
    try:
        client.table("chunks").delete().eq("document_id", document_id).eq(
            "chunk_type", "table"
        ).execute()
    except Exception as e:
        logger.warning(
            "table_chunks_cleanup_failed",
            document_id=document_id,
            error=str(e),
        )

    # Get the next chunk_index to avoid collisions with text chunks.
    # Query max chunk_index among non-table chunks (parent+child) since we just
    # deleted table chunks above. If the query fails, we cannot safely determine
    # the next index — skip table chunk creation rather than risk collisions.
    try:
        max_index_resp = (
            client.table("chunks")
            .select("chunk_index")
            .eq("document_id", document_id)
            .order("chunk_index", desc=True)
            .limit(1)
            .execute()
        )
        next_index = (
            (max_index_resp.data[0]["chunk_index"] + 1) if max_index_resp.data else 0
        )
    except Exception as e:
        logger.error(
            "table_chunks_max_index_query_failed",
            document_id=document_id,
            error=str(e),
        )
        return 0  # Skip table chunks rather than risk index collisions

    chunk_records: list[dict] = []

    for table in result.tables:
        # Skip low-confidence tables — not reliable enough for search
        if table.confidence < TABLE_CHUNK_MIN_CONFIDENCE:
            logger.debug(
                "table_chunk_skipped_low_confidence",
                document_id=document_id,
                table_index=table.table_index,
                confidence=table.confidence,
            )
            continue

        # Skip empty/trivial tables
        if table.row_count < 2 or not table.markdown_content.strip():
            continue

        # Build contextual prefix
        caption_part = f": {table.caption}" if table.caption else ""
        page_part = f", p. {table.page_number}" if table.page_number else ""

        # Check if table fits in a single chunk
        full_content = f"Table {table.table_index + 1}{caption_part}{page_part}\n{table.markdown_content}"
        token_count = count_tokens(full_content)

        if token_count <= TABLE_CHUNK_MAX_TOKENS:
            # Single chunk for the whole table
            chunk_records.append(
                {
                    "id": str(uuid4()),
                    "matter_id": matter_id,
                    "document_id": document_id,
                    "chunk_index": next_index,
                    "parent_chunk_id": None,
                    "content": full_content,
                    "page_number": table.page_number,
                    "bbox_ids": None,
                    "token_count": token_count,
                    "chunk_type": "table",
                    "layout_derived": True,
                }
            )
            next_index += 1
        else:
            # Split large table by rows
            split_chunks = _split_table_by_rows(
                table,
                matter_id,
                document_id,
                next_index,
            )
            chunk_records.extend(split_chunks)
            next_index += len(split_chunks)

    if not chunk_records:
        logger.info(
            "table_chunks_none_created",
            document_id=document_id,
            table_count=result.total_tables,
            reason="All tables filtered (low confidence, empty, or no tables)",
        )
        return 0

    # Batch insert table chunks
    created_count = 0
    batch_size = 50
    for i in range(0, len(chunk_records), batch_size):
        batch = chunk_records[i : i + batch_size]
        try:
            resp = client.table("chunks").insert(batch).execute()
            created_count += len(resp.data) if resp.data else 0
        except Exception as e:
            logger.warning(
                "table_chunks_batch_insert_failed",
                document_id=document_id,
                batch_offset=i,
                batch_size=len(batch),
                error=str(e),
            )

    logger.info(
        "table_chunks_created",
        document_id=document_id,
        matter_id=matter_id,
        chunk_count=created_count,
        table_count=result.total_tables,
    )

    return created_count


def _split_table_by_rows(
    table: ExtractedTable,
    matter_id: str,
    document_id: str,
    start_index: int,
) -> list[dict]:
    """Split a large table into multiple chunks by rows.

    Repeats the header row and separator in each chunk for context.
    Each chunk stays under TABLE_CHUNK_MAX_TOKENS.

    Args:
        table: The extracted table to split.
        matter_id: Matter UUID.
        document_id: Document UUID.
        start_index: Starting chunk_index for these chunks.

    Returns:
        List of chunk record dicts ready for DB insertion.
    """
    from app.services.chunking.token_counter import count_tokens

    lines = table.markdown_content.strip().split("\n")

    # Extract header (first 2 lines: header row + separator)
    if len(lines) < 3:
        # Table too small to split, shouldn't happen but handle gracefully
        page_part = f", p. {table.page_number}" if table.page_number else ""
        content = f"Table {table.table_index + 1}{page_part}\n{table.markdown_content}"
        return [
            {
                "id": str(uuid4()),
                "matter_id": matter_id,
                "document_id": document_id,
                "chunk_index": start_index,
                "parent_chunk_id": None,
                "content": content,
                "page_number": table.page_number,
                "bbox_ids": None,
                "token_count": count_tokens(content),
                "chunk_type": "table",
                "layout_derived": True,
            }
        ]

    header_line = lines[0]
    separator_line = lines[1]
    data_rows = lines[2:]

    caption_part = f": {table.caption}" if table.caption else ""
    page_part = f", p. {table.page_number}" if table.page_number else ""

    header_block = f"{header_line}\n{separator_line}"
    header_tokens = count_tokens(header_block)

    # Budget for data rows per chunk. If the header is extremely wide (many columns),
    # ensure a minimum budget of 200 tokens per chunk to avoid 1-row-per-chunk explosion.
    row_budget = max(
        TABLE_CHUNK_MAX_TOKENS - header_tokens - 30, 200
    )  # 30 tokens for prefix

    chunks: list[dict] = []
    current_rows: list[str] = []
    current_tokens = 0
    part_num = 1

    for row in data_rows:
        row_tokens = count_tokens(row)

        # Guard: if a single row exceeds the budget, truncate it to avoid
        # creating an oversized chunk. Legal tables with many columns can
        # easily have rows exceeding 2000 tokens.
        # Truncation preserves markdown table structure by cutting at cell
        # boundaries (| delimiters) and appending a closing pipe.
        if row_tokens > row_budget:
            cells = row.split("|")
            truncated: list[str] = []
            accumulated = 0
            for cell in cells:
                cell_tokens = count_tokens(cell)
                if accumulated + cell_tokens > row_budget and truncated:
                    break
                truncated.append(cell)
                accumulated += cell_tokens
            row = "|".join(truncated) + "| ..."
            row_tokens = count_tokens(row)

        if current_tokens + row_tokens > row_budget and current_rows:
            # Flush current chunk
            prefix = f"Table {table.table_index + 1}{caption_part}, part {part_num}{page_part}"
            content = f"{prefix}\n{header_block}\n" + "\n".join(current_rows)
            chunks.append(
                {
                    "id": str(uuid4()),
                    "matter_id": matter_id,
                    "document_id": document_id,
                    "chunk_index": start_index + len(chunks),
                    "parent_chunk_id": None,
                    "content": content,
                    "page_number": table.page_number,
                    "bbox_ids": None,
                    "token_count": count_tokens(content),
                    "chunk_type": "table",
                    "layout_derived": True,
                }
            )
            current_rows = []
            current_tokens = 0
            part_num += 1

        current_rows.append(row)
        current_tokens += row_tokens

    # Flush remaining rows
    if current_rows:
        prefix = f"Table {table.table_index + 1}{caption_part}"
        if part_num > 1:
            prefix += f", part {part_num}"
        prefix += page_part
        content = f"{prefix}\n{header_block}\n" + "\n".join(current_rows)
        chunks.append(
            {
                "id": str(uuid4()),
                "matter_id": matter_id,
                "document_id": document_id,
                "chunk_index": start_index + len(chunks),
                "parent_chunk_id": None,
                "content": content,
                "page_number": table.page_number,
                "bbox_ids": None,
                "token_count": count_tokens(content),
                "chunk_type": "table",
                "layout_derived": True,
            }
        )

    return chunks
