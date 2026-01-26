"""Library Document Processing Tasks.

Celery tasks for processing library documents (Acts, Statutes, Judgments):
1. chunk_library_document - Create parent-child chunks
2. embed_library_chunks - Generate embeddings for semantic search

These tasks are simpler than document_tasks.py because library documents
don't need: bounding boxes, entity extraction, citation detection, etc.
They just need to be chunked and embedded for RAG search.
"""

import asyncio

import structlog

from app.models.library import LibraryDocumentStatus
from app.services.chunking.parent_child_chunker import ParentChildChunker
from app.services.library_service import get_library_service, LibraryService
from app.services.rag.embedder import EmbeddingService, get_embedding_service
from app.services.supabase.client import get_service_client
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)

# Batch sizes for processing
EMBEDDING_BATCH_SIZE = 50
EMBEDDING_RATE_LIMIT_DELAY = 0.5  # Seconds between batches


# =============================================================================
# Library Document Chunking Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.chunk_library_document",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
)  # type: ignore[misc]
def chunk_library_document(
    self,  # type: ignore[no-untyped-def]
    library_document_id: str,
    extracted_text: str,
    library_service: LibraryService | None = None,
) -> dict[str, str | int | None]:
    """Chunk a library document into parent-child hierarchy for RAG.

    Creates document chunks stored in library_chunks table.
    No bounding box linking since library documents don't need highlighting.

    Args:
        library_document_id: Library document UUID.
        extracted_text: OCR/extracted text content.
        library_service: Optional LibraryService instance (for testing).

    Returns:
        Task result with chunking summary.
    """
    logger.info(
        "chunk_library_document_started",
        library_document_id=library_document_id,
        text_length=len(extracted_text),
        retry_count=self.request.retries,
    )

    lib_service = library_service or get_library_service()
    client = get_service_client()

    if client is None:
        logger.error(
            "chunk_library_document_no_client",
            library_document_id=library_document_id,
        )
        return {
            "status": "chunking_failed",
            "library_document_id": library_document_id,
            "error_code": "DATABASE_NOT_CONFIGURED",
            "error_message": "Database client not configured",
        }

    try:
        # Update status to processing
        lib_service.update_status(library_document_id, LibraryDocumentStatus.PROCESSING)

        # IDEMPOTENCY CHECK: Skip if chunks already exist
        existing = (
            client.table("library_chunks")
            .select("id", count="exact")
            .eq("library_document_id", library_document_id)
            .execute()
        )
        existing_count = existing.count or 0

        if existing_count > 0:
            logger.info(
                "chunk_library_document_already_complete",
                library_document_id=library_document_id,
                existing_chunks=existing_count,
                action="skipping_rechunk",
            )
            return {
                "status": "chunking_complete",
                "library_document_id": library_document_id,
                "chunk_count": existing_count,
                "note": "Chunks already exist (idempotent skip)",
            }

        # Create chunker and process
        chunker = ParentChildChunker()
        result = chunker.chunk_document(library_document_id, extracted_text)

        # Prepare chunks for insertion
        chunk_records = []

        # Add parent chunks
        for chunk in result.parent_chunks:
            chunk_records.append({
                "library_document_id": library_document_id,
                "chunk_index": chunk.chunk_index,
                "parent_chunk_id": None,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "section_title": None,  # Could be enhanced to detect section titles
                "token_count": chunk.token_count,
                "chunk_type": "parent",
            })

        # Create parent chunks first to get IDs
        if chunk_records:
            parent_result = (
                client.table("library_chunks")
                .insert(chunk_records)
                .execute()
            )

            # Build parent ID mapping
            parent_id_map = {}
            for record in parent_result.data or []:
                parent_id_map[record["chunk_index"]] = record["id"]

            # Add child chunks with parent references
            child_records = []
            for chunk in result.child_chunks:
                parent_idx = chunk.parent_chunk_index
                parent_id = parent_id_map.get(parent_idx)

                child_records.append({
                    "library_document_id": library_document_id,
                    "chunk_index": chunk.chunk_index,
                    "parent_chunk_id": parent_id,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "section_title": None,
                    "token_count": chunk.token_count,
                    "chunk_type": "child",
                })

            if child_records:
                client.table("library_chunks").insert(child_records).execute()

        total_chunks = len(result.parent_chunks) + len(result.child_chunks)

        logger.info(
            "chunk_library_document_completed",
            library_document_id=library_document_id,
            parent_chunks=len(result.parent_chunks),
            child_chunks=len(result.child_chunks),
            total_tokens=result.total_tokens,
        )

        return {
            "status": "chunking_complete",
            "library_document_id": library_document_id,
            "parent_chunks": len(result.parent_chunks),
            "child_chunks": len(result.child_chunks),
            "total_tokens": result.total_tokens,
            "chunk_count": total_chunks,
        }

    except Exception as e:
        logger.error(
            "chunk_library_document_failed",
            library_document_id=library_document_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Update status to failed
        try:
            lib_service.update_status(
                library_document_id,
                LibraryDocumentStatus.FAILED,
                quality_flags=["chunking_failed"],
            )
        except Exception:
            pass

        return {
            "status": "chunking_failed",
            "library_document_id": library_document_id,
            "error_code": "CHUNKING_FAILED",
            "error_message": str(e),
        }


# =============================================================================
# Library Chunk Embedding Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.embed_library_chunks",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)  # type: ignore[misc]
def embed_library_chunks(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | None] | None = None,
    library_document_id: str | None = None,
    library_service: LibraryService | None = None,
    embedding_service: EmbeddingService | None = None,
) -> dict[str, str | int | None]:
    """Generate embeddings for library document chunks.

    Processes chunks in batches to respect OpenAI rate limits.

    Args:
        prev_result: Result from previous task (contains library_document_id).
        library_document_id: Library document UUID.
        library_service: Optional LibraryService instance (for testing).
        embedding_service: Optional EmbeddingService instance (for testing).

    Returns:
        Task result with embedding summary.
    """
    # Get library_document_id from prev_result or parameter
    lib_doc_id = library_document_id
    if lib_doc_id is None and prev_result:
        lib_doc_id = prev_result.get("library_document_id")  # type: ignore[assignment]

    if not lib_doc_id:
        logger.error("embed_library_chunks_no_document_id")
        return {
            "status": "embedding_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No library_document_id provided",
        }

    # Skip if previous task failed
    if prev_result:
        prev_status = prev_result.get("status")
        if prev_status and "failed" in prev_status:
            logger.info(
                "embed_library_chunks_skipped",
                library_document_id=lib_doc_id,
                prev_status=prev_status,
                reason="Previous task failed",
            )
            return {
                "status": "embedding_skipped",
                "library_document_id": lib_doc_id,
                "reason": f"Previous task failed: {prev_status}",
            }

    lib_service = library_service or get_library_service()
    embedder = embedding_service or get_embedding_service()
    client = get_service_client()

    if client is None:
        return {
            "status": "embedding_failed",
            "library_document_id": lib_doc_id,
            "error_code": "DATABASE_NOT_CONFIGURED",
            "error_message": "Database client not configured",
        }

    logger.info(
        "embed_library_chunks_started",
        library_document_id=lib_doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get chunks without embeddings
        response = (
            client.table("library_chunks")
            .select("id, content")
            .eq("library_document_id", lib_doc_id)
            .is_("embedding", "null")
            .order("page_number", desc=False, nullsfirst=False)
            .order("chunk_index", desc=False)
            .execute()
        )

        chunks = response.data or []

        if not chunks:
            # All chunks already embedded
            lib_service.update_status(lib_doc_id, LibraryDocumentStatus.COMPLETED)
            logger.info(
                "embed_library_chunks_already_complete",
                library_document_id=lib_doc_id,
            )
            return {
                "status": "embedding_complete",
                "library_document_id": lib_doc_id,
                "embedded_count": 0,
                "reason": "All chunks already embedded",
            }

        logger.info(
            "embed_library_chunks_processing",
            library_document_id=lib_doc_id,
            chunk_count=len(chunks),
            batch_size=EMBEDDING_BATCH_SIZE,
        )

        # Process in batches
        embedded_count = 0
        for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[i:i + EMBEDDING_BATCH_SIZE]
            batch_texts = [c["content"] for c in batch]
            batch_ids = [c["id"] for c in batch]

            # Generate embeddings
            async def _embed_batch():
                return await embedder.embed_batch(batch_texts)

            embeddings = asyncio.run(_embed_batch())

            if embeddings is None:
                logger.warning(
                    "embed_library_chunks_batch_failed",
                    library_document_id=lib_doc_id,
                    batch_index=i // EMBEDDING_BATCH_SIZE,
                    batch_size=len(batch),
                )
                continue

            # Update chunks with embeddings
            for chunk_id, embedding in zip(batch_ids, embeddings):
                if embedding is not None:
                    client.table("library_chunks").update(
                        {"embedding": embedding}
                    ).eq("id", chunk_id).execute()
                    embedded_count += 1

            # Rate limit delay between batches
            if i + EMBEDDING_BATCH_SIZE < len(chunks):
                import time
                time.sleep(EMBEDDING_RATE_LIMIT_DELAY)

        # Update document status
        lib_service.update_status(lib_doc_id, LibraryDocumentStatus.COMPLETED)

        logger.info(
            "embed_library_chunks_completed",
            library_document_id=lib_doc_id,
            embedded_count=embedded_count,
            total_chunks=len(chunks),
        )

        return {
            "status": "embedding_complete",
            "library_document_id": lib_doc_id,
            "embedded_count": embedded_count,
            "total_chunks": len(chunks),
        }

    except Exception as e:
        logger.error(
            "embed_library_chunks_failed",
            library_document_id=lib_doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Update status to failed
        try:
            lib_service.update_status(
                lib_doc_id,
                LibraryDocumentStatus.FAILED,
                quality_flags=["embedding_failed"],
            )
        except Exception:
            pass

        return {
            "status": "embedding_failed",
            "library_document_id": lib_doc_id,
            "error_code": "EMBEDDING_FAILED",
            "error_message": str(e),
        }


# =============================================================================
# Library Document Processing Pipeline
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.process_library_document",
)  # type: ignore[misc]
def process_library_document(
    library_document_id: str,
    extracted_text: str,
) -> dict[str, str | int | None]:
    """Process a library document through the full pipeline.

    Chains: chunk_library_document -> embed_library_chunks

    Args:
        library_document_id: Library document UUID.
        extracted_text: OCR/extracted text content.

    Returns:
        Task chain signature.
    """
    from celery import chain

    logger.info(
        "process_library_document_started",
        library_document_id=library_document_id,
        text_length=len(extracted_text),
    )

    # Create processing chain
    pipeline = chain(
        chunk_library_document.s(library_document_id, extracted_text),
        embed_library_chunks.s(),
    )

    # Execute chain
    result = pipeline.apply_async()

    return {
        "status": "processing_started",
        "library_document_id": library_document_id,
        "task_id": result.id,
    }
