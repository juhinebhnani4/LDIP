"""Library Document Processing Tasks.

Celery tasks for processing library documents (Acts, Statutes, Judgments):
1. chunk_library_document - Create parent-child chunks
2. embed_library_chunks - Generate embeddings for semantic search

These tasks are simpler than document_tasks.py because library documents
don't need: bounding boxes, entity extraction, citation detection, etc.
They just need to be chunked and embedded for RAG search.
"""

import re

import structlog
from celery.exceptions import Retry

from app.models.library import LibraryDocumentStatus
from app.services.chunking.parent_child_chunker import ParentChildChunker
from app.services.library_service import LibraryService, get_library_service
from app.services.rag.embedder import EmbeddingService, get_embedding_service
from app.services.supabase.client import get_service_client
from app.workers.celery import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)

# Batch sizes for processing
EMBEDDING_BATCH_SIZE = 50
EMBEDDING_RATE_LIMIT_DELAY = 0.5  # Seconds between batches

# Regex for detecting legal section titles in Indian statutes.
# Matches patterns like "Section 4.", "Section 137A.", "Article 14",
# "Rule 5", "Order XXI", "Schedule I", "Chapter III".
# Only matches at start of line (after optional whitespace) to avoid
# false positives from mid-sentence references.
_SECTION_TITLE_RE = re.compile(
    r"^\s*("
    r"(?:Section|Sec\.?)\s+\d+[A-Z]?"  # Section 4, Section 137A, Sec. 5
    r"|Article\s+\d+[A-Z]?"  # Article 14, Article 370A
    r"|Rule\s+\d+[A-Z]?"  # Rule 5, Rule 11A
    r"|Order\s+[IVXLCDM]+(?:\s+Rule\s+\d+)?"  # Order XXI, Order XXI Rule 1
    r"|Schedule\s+[IVXLCDM\d]+"  # Schedule I, Schedule 2
    r"|Chapter\s+[IVXLCDM\d]+"  # Chapter III, Chapter 4
    r")",
    re.MULTILINE | re.IGNORECASE,
)


def _extract_section_title(text: str) -> str | None:
    """Extract the first legal section title from chunk text.

    Scans the first ~500 characters for patterns like "Section 4",
    "Article 14", etc. Returns the matched title or None.
    """
    match = _SECTION_TITLE_RE.search(text[:500])
    if match:
        return match.group(1).strip()
    return None


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

        # Fetch document title for chunk context enrichment
        try:
            lib_doc = lib_service.get_document(library_document_id)
            doc_context = lib_doc.title or lib_doc.filename
        except Exception as e:
            logger.warning(
                "chunk_library_document_context_lookup_failed",
                library_document_id=library_document_id,
                error=str(e),
                action="chunking_without_context_header",
            )
            doc_context = None

        # Create chunker and process
        chunker = ParentChildChunker()
        result = chunker.chunk_document(
            library_document_id,
            extracted_text,
            document_context=doc_context,
        )

        # Prepare chunks for insertion
        chunk_records = []

        # Add parent chunks (use ChunkData.id as DB id, matching main pipeline pattern)
        # Build parent_id → section_title map so children inherit their parent's section
        parent_section_map: dict[str, str | None] = {}
        for chunk in result.parent_chunks:
            section = _extract_section_title(chunk.content)
            parent_section_map[str(chunk.id)] = section
            chunk_records.append(
                {
                    "id": str(chunk.id),
                    "library_document_id": library_document_id,
                    "chunk_index": chunk.chunk_index,
                    "parent_chunk_id": None,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "section_title": section,
                    "token_count": chunk.token_count,
                    "chunk_type": "parent",
                }
            )

        # Create parent chunks first to get IDs
        if chunk_records:
            client.table("library_chunks").insert(chunk_records).execute()

            # Add child chunks with parent references
            # ChunkData.parent_id is the parent's ChunkData.id (now also the DB id)
            child_records = []
            for chunk in result.child_chunks:
                parent_id_str = str(chunk.parent_id) if chunk.parent_id else None
                # Child inherits parent's section, or extracts its own if parent had none
                child_section = (
                    parent_section_map.get(parent_id_str) if parent_id_str else None
                ) or _extract_section_title(chunk.content)
                child_records.append(
                    {
                        "id": str(chunk.id),
                        "library_document_id": library_document_id,
                        "chunk_index": chunk.chunk_index,
                        "parent_chunk_id": parent_id_str,
                        "content": chunk.content,
                        "page_number": chunk.page_number,
                        "section_title": child_section,
                        "token_count": chunk.token_count,
                        "chunk_type": "child",
                    }
                )

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
        from app.workers.tasks.pipeline_errors import LibraryPipelineTaskError

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
        except Exception as status_err:
            logger.error(
                "status_update_on_failure_swallowed",
                error=str(status_err),
                library_document_id=library_document_id,
                target_status="failed",
                original_error=str(e),
            )

        # DPP-002: Raise instead of return — Celery stops the chain
        raise LibraryPipelineTaskError(
            str(e),
            error_code="CHUNKING_FAILED",
            library_document_id=library_document_id,
        ) from e


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
        from app.workers.tasks.pipeline_errors import LibraryPipelineTaskError

        logger.error("embed_library_chunks_no_document_id")
        raise LibraryPipelineTaskError(
            "No library_document_id provided",
            error_code="NO_DOCUMENT_ID",
        )

    lib_service = library_service or get_library_service()
    embedder = embedding_service or get_embedding_service()
    client = get_service_client()

    if client is None:
        from app.workers.tasks.pipeline_errors import LibraryPipelineTaskError

        raise LibraryPipelineTaskError(
            "Database client not configured",
            error_code="DATABASE_NOT_CONFIGURED",
            library_document_id=lib_doc_id,
        )

    logger.info(
        "embed_library_chunks_started",
        library_document_id=lib_doc_id,
        retry_count=self.request.retries,
    )

    # RISK-2: prevent concurrent embed of the SAME library doc. A chain-dispatched
    # embed (ocr_and_process_library_document) and a reconciler-dispatched embed
    # (resume_stuck_pipelines) can otherwise run together for one doc → duplicate
    # OpenAI calls + duplicate llm_costs rows (idempotent for correctness, wasteful
    # on the OpenAI text-embedding-3-small bucket). Reuse the main pipeline's
    # PipelineLock (Redis SET NX, 30-min TTL, fail-open) keyed by library_document_id.
    # The embed TASK is the single convergence point both dispatch sources flow
    # through — the lock lives here, not at each dispatch site (avoids the
    # ARCH-003 "release at N call sites" smell; one finally releases it).
    from app.services.distributed_lock import PipelineLock

    _lock = PipelineLock(lib_doc_id)
    if not _lock.acquire():
        logger.info(
            "embed_library_chunks_already_running",
            library_document_id=lib_doc_id,
        )
        return {
            "status": "skipped_locked",
            "library_document_id": lib_doc_id,
            "reason": "Another embed is already running for this document",
        }

    try:
        # Get ALL chunks without embeddings. GAP-21: PostgREST caps a single
        # response at ~1000 rows, so a large Act (e.g. Income Tax Act, 2422
        # chunks) silently fetched only the first 1000, embedded those, and the
        # old guard marked the doc COMPLETED with the rest left NULL. Paginate
        # with .range() (same pattern as library_service.list) so one run
        # actually sees every unembedded chunk.
        chunks: list[dict] = []
        _page_size = 1000
        _offset = 0
        while True:
            _page = (
                client.table("library_chunks")
                .select("id, content")
                .eq("library_document_id", lib_doc_id)
                .is_("embedding", "null")
                .order("page_number", desc=False, nullsfirst=False)
                .order("chunk_index", desc=False)
                .range(_offset, _offset + _page_size - 1)
                .execute()
            )
            _batch = _page.data or []
            chunks.extend(_batch)
            if len(_batch) < _page_size:
                break
            _offset += _page_size

        if not chunks:
            # No unembedded chunks — but is that because all are embedded,
            # or because there are 0 chunks total? (GAP-2 fix)
            total_response = (
                client.table("library_chunks")
                .select("id", count="exact")
                .eq("library_document_id", lib_doc_id)
                .execute()
            )
            total_chunk_count = total_response.count or 0

            if total_chunk_count == 0:
                # 0 chunks total — this doc was never chunked properly.
                # Do NOT set completed; mark as failed so it gets retried.
                logger.error(
                    "embed_library_chunks_zero_chunks",
                    library_document_id=lib_doc_id,
                )
                lib_service.update_status(
                    lib_doc_id,
                    LibraryDocumentStatus.FAILED,
                    quality_flags=["zero_chunks"],
                )
                return {
                    "status": "failed",
                    "library_document_id": lib_doc_id,
                    "embedded_count": 0,
                    "reason": "Document has 0 chunks — chunking may have failed",
                }

            # All chunks genuinely already embedded
            lib_service.update_status(lib_doc_id, LibraryDocumentStatus.COMPLETED)
            logger.info(
                "embed_library_chunks_already_complete",
                library_document_id=lib_doc_id,
                total_chunks=total_chunk_count,
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
        # RISK-3: track whether any zero-result batch was a TRANSIENT throttle
        # (circuit-open / rate-limit) rather than genuine-empty content. embed_batch
        # returns an all-None list for BOTH cases, but we hold the inputs: if a
        # batch had non-empty content yet came back all-None, the all-empty path is
        # impossible, so the cause is necessarily a transient OpenAI throttle. This
        # distinction (made without changing embed_batch's shared contract) lets the
        # completion guard bounded-retry throttles instead of marking FAILED on the
        # first blip — while a genuinely empty/garbage doc still fails fast.
        had_transient_failure = False
        for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[i : i + EMBEDDING_BATCH_SIZE]
            batch_texts = [c["content"] for c in batch]
            batch_ids = [c["id"] for c in batch]

            # Generate embeddings (GAP-11: pass library_document_id for cost attribution)
            async def _embed_batch(batch_texts=batch_texts):
                return await embedder.embed_batch(
                    batch_texts, library_document_id=lib_doc_id
                )

            embeddings = run_async(_embed_batch())

            # embed_batch returns None only on a hard error; on circuit-open /
            # rate-limit it returns a list of all-None. Treat both as a failed
            # batch so the warning actually fires (the bare `is None` check never
            # tripped because the return is a list). embedded_count stays 0 for
            # this batch either way; the completion guard below derives the real
            # outcome from the remaining-NULL count.
            if embeddings is None or all(e is None for e in embeddings):
                # If this batch had real content, an all-None result can only be a
                # transient throttle (the all-empty path can't apply). Flag it.
                batch_has_content = any(t and t.strip() for t in batch_texts)
                if batch_has_content:
                    had_transient_failure = True
                logger.warning(
                    "embed_library_chunks_batch_failed",
                    library_document_id=lib_doc_id,
                    batch_index=i // EMBEDDING_BATCH_SIZE,
                    batch_size=len(batch),
                    transient_throttle=batch_has_content,
                )
                continue

            # Update chunks with embeddings
            for chunk_id, embedding in zip(batch_ids, embeddings, strict=False):
                if embedding is not None:
                    client.table("library_chunks").update({"embedding": embedding}).eq(
                        "id", chunk_id
                    ).execute()
                    embedded_count += 1

            # Rate limit delay between batches
            if i + EMBEDDING_BATCH_SIZE < len(chunks):
                import time

                time.sleep(EMBEDDING_RATE_LIMIT_DELAY)

        # GAP-4: Generate Voyage embeddings (best-effort, non-blocking)
        voyage_count = 0
        try:
            from app.core.config import get_settings

            settings = get_settings()
            if settings.voyage_api_key:
                from app.services.rag.voyage_embedder import (
                    get_voyage_embedding_service,
                )

                voyage_embedder = get_voyage_embedding_service()

                for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
                    batch = chunks[i : i + EMBEDDING_BATCH_SIZE]
                    batch_texts = [c["content"] for c in batch]
                    batch_ids = [c["id"] for c in batch]

                    async def _embed_voyage_batch(batch_texts=batch_texts):
                        return await voyage_embedder.embed_batch(
                            batch_texts,
                            matter_id=None,
                            input_type="document",
                        )

                    voyage_embeddings = run_async(_embed_voyage_batch())
                    if voyage_embeddings:
                        for chunk_id, v_emb in zip(
                            batch_ids, voyage_embeddings, strict=False
                        ):
                            if v_emb is not None:
                                client.table("library_chunks").update(
                                    {"embedding_voyage": v_emb}
                                ).eq("id", chunk_id).execute()
                                voyage_count += 1

                    if i + EMBEDDING_BATCH_SIZE < len(chunks):
                        import time

                        time.sleep(EMBEDDING_RATE_LIMIT_DELAY)

                logger.info(
                    "embed_library_chunks_voyage_complete",
                    library_document_id=lib_doc_id,
                    voyage_count=voyage_count,
                )
        except Exception as e:
            logger.warning(
                "embed_library_chunks_voyage_failed",
                library_document_id=lib_doc_id,
                error=str(e),
                voyage_count=voyage_count,
            )

        # GAP-21: Derive completion from OBSERVED reality, not this run's counter.
        # The old guard marked COMPLETED whenever embedded_count > 0, so any
        # partial embed (some batches failed, OR the fetch was truncated at 1000)
        # left NULL-embedding chunks behind on a "completed" doc — silently absent
        # from semantic search and invisible to status-keyed recovery. Re-query the
        # true remaining-NULL count (count="exact" is accurate beyond 1000 rows)
        # and only mark COMPLETED when zero remain.
        remaining_null = (
            client.table("library_chunks")
            .select("id", count="exact")
            .eq("library_document_id", lib_doc_id)
            .is_("embedding", "null")
            .execute()
        ).count or 0

        if remaining_null == 0:
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

        if embedded_count == 0:
            # No progress this run. RISK-3: distinguish a TRANSIENT throttle (a
            # retry seconds later would succeed) from a GENUINE failure (empty /
            # garbage content — retrying is useless). The old guard marked FAILED
            # on either, so one transient OpenAI blip on the first batch stranded
            # the doc (FAILED is excluded from the reconciler → manual reset).
            if had_transient_failure:
                # Bounded-retry via Celery's NATIVE retry counter — the worker is
                # freed between attempts (not an in-task sleep loop), and the
                # maintenance reconciler remains the outer safety net. Keep the doc
                # PROCESSING (non-terminal) across retries so state reflects
                # in-flight, not failed.
                if self.request.retries < self.max_retries:
                    logger.warning(
                        "embed_library_chunks_transient_throttle_retry",
                        library_document_id=lib_doc_id,
                        attempted_chunks=len(chunks),
                        remaining_null=remaining_null,
                        retry=self.request.retries + 1,
                        max_retries=self.max_retries,
                    )
                    try:
                        lib_service.update_status(
                            lib_doc_id,
                            LibraryDocumentStatus.PROCESSING,
                            quality_flags=["embedding_throttled"],
                        )
                    except Exception as status_err:
                        logger.warning(
                            "embed_throttle_status_update_swallowed",
                            error=str(status_err),
                            library_document_id=lib_doc_id,
                        )
                    # exponential-ish countdown bounded at 120s; self.retry raises
                    # celery Retry (re-raised past the generic handler below).
                    raise self.retry(
                        countdown=min(120, 15 * (2**self.request.retries)),
                    )
                # Bounded retries exhausted — terminal, but LABELED as a throttle so
                # ops can tell "OpenAI quota problem" from "bad document". FAILED
                # stays reachable (E2E-007: no infinite recovery loop).
                logger.error(
                    "embed_library_chunks_throttle_exhausted",
                    library_document_id=lib_doc_id,
                    attempted_chunks=len(chunks),
                    remaining_null=remaining_null,
                    retries=self.request.retries,
                )
                lib_service.update_status(
                    lib_doc_id,
                    LibraryDocumentStatus.FAILED,
                    quality_flags=["embedding_throttle_exhausted"],
                )
                return {
                    "status": "failed",
                    "library_document_id": lib_doc_id,
                    "embedded_count": 0,
                    "total_chunks": len(chunks),
                    "remaining_null": remaining_null,
                    "reason": "Embedding throttled; bounded retries exhausted",
                }

            # Genuine zero-progress: every attempted batch was empty/garbage content
            # (no transient throttle seen). Retrying is useless — mark FAILED so it
            # surfaces and stops being re-dispatched (convergence: terminal state,
            # never an infinite recovery loop). This is also the anti-thrash backstop.
            logger.error(
                "embed_library_chunks_all_batches_failed",
                library_document_id=lib_doc_id,
                attempted_chunks=len(chunks),
                remaining_null=remaining_null,
            )
            lib_service.update_status(
                lib_doc_id,
                LibraryDocumentStatus.FAILED,
                quality_flags=["embedding_failed"],
            )
            return {
                "status": "failed",
                "library_document_id": lib_doc_id,
                "embedded_count": 0,
                "total_chunks": len(chunks),
                "remaining_null": remaining_null,
                "reason": "All embedding batches failed",
            }

        # Partial progress: embedded some this run, but NULL chunks remain. Leave
        # NON-terminal (processing) — do NOT mark COMPLETED. The library recovery
        # reconciler re-dispatches embed-only for the still-NULL chunks until they
        # converge to COMPLETED (or the all-failed branch above marks FAILED).
        logger.warning(
            "embed_library_chunks_partial",
            library_document_id=lib_doc_id,
            embedded_count=embedded_count,
            remaining_null=remaining_null,
            total_chunks=len(chunks),
        )
        lib_service.update_status(
            lib_doc_id,
            LibraryDocumentStatus.PROCESSING,
            quality_flags=["embedding_partial"],
        )
        return {
            "status": "embedding_partial",
            "library_document_id": lib_doc_id,
            "embedded_count": embedded_count,
            "remaining_null": remaining_null,
            "total_chunks": len(chunks),
        }

    except Retry:
        # RISK-3: self.retry() (transient-throttle bounded retry) raises celery's
        # Retry. It MUST propagate so Celery re-queues the task — the generic
        # handler below would otherwise swallow it into a FAILED status.
        raise

    except Exception as e:
        from app.workers.tasks.pipeline_errors import LibraryPipelineTaskError

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
        except Exception as status_err:
            logger.error(
                "status_update_on_failure_swallowed",
                error=str(status_err),
                library_document_id=lib_doc_id,
                target_status="failed",
                original_error=str(e),
            )

        # DPP-002: Raise instead of return — Celery stops the chain
        raise LibraryPipelineTaskError(
            str(e),
            error_code="EMBEDDING_FAILED",
            library_document_id=lib_doc_id,
        ) from e

    finally:
        # RISK-2: single release point for the embed lock — runs on success,
        # FAILED, and retry (released here, re-acquired on the next run).
        _lock.release()


# =============================================================================
# Callback Dispatcher (fires after embed completes)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.fire_library_callbacks",
)  # type: ignore[misc]
def fire_library_callbacks(
    prev_result: dict[str, str | int | None] | None = None,
    library_document_id: str | None = None,
    callbacks: list[dict] | None = None,
) -> dict[str, str | int | None]:
    """Fire callback tasks after library processing completes.

    Chained after embed_library_chunks to ensure chunks and embeddings
    exist before downstream tasks (like verification) run.

    Args:
        prev_result: Result from embed_library_chunks.
        library_document_id: Library document UUID.
        callbacks: List of dicts with "task_name" and "kwargs".

    Returns:
        Summary of dispatched callbacks.
    """
    if not callbacks:
        return {"status": "no_callbacks", "library_document_id": library_document_id}

    # Only fire callbacks (e.g. citation verification) when the embed step
    # GENUINELY completed. This gate previously fired on anything NOT containing
    # "failed", which let verification run on:
    #   - "embedding_partial" → verification against partial embeddings produces
    #     false section-not-found (RISK-1(b)); and
    #   - "skipped_locked" → after the RISK-2 lock, this task embedded nothing
    #     (another run owns the doc), so its result says nothing about completeness.
    # Deferring verification is strictly safer than verifying on incomplete data:
    # the RISK-1 derived-state reconciler will fire verification exactly once the
    # doc is truly fully embedded. (RISK-1 will replace this gate with that
    # reconciler; until then, "only on embedding_complete" is the safe interim.)
    if prev_result is not None:
        prev_status = str(prev_result.get("status", ""))
        if prev_status != "embedding_complete":
            logger.info(
                "fire_library_callbacks_skipped_not_complete",
                library_document_id=library_document_id,
                prev_status=prev_status,
            )
            return {
                "status": "skipped",
                "library_document_id": library_document_id,
                "reason": f"Embed not complete: {prev_status}",
            }

    dispatched = 0
    for cb in callbacks:
        task_name = cb.get("task_name")
        kwargs = dict(cb.get("kwargs", {}))
        queue = cb.get("queue", "default")

        # Auto-inject library_document_id as act_document_id if not set
        # This solves the chicken-and-egg: callbacks are registered before
        # the library_document_id is known, so we inject it at dispatch time.
        if "act_document_id" not in kwargs and library_document_id:
            kwargs["act_document_id"] = library_document_id

        try:
            celery_app.send_task(task_name, kwargs=kwargs, queue=queue)
            dispatched += 1
            logger.info(
                "library_callback_dispatched",
                task_name=task_name,
                library_document_id=library_document_id,
            )
        except Exception as e:
            logger.warning(
                "library_callback_dispatch_failed",
                task_name=task_name,
                error=str(e),
            )

    return {
        "status": "callbacks_dispatched",
        "library_document_id": library_document_id,
        "dispatched": dispatched,
    }


# =============================================================================
# Library Document OCR + Processing (for auto-fetched acts)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.ocr_and_process_library_document",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)  # type: ignore[misc]
def ocr_and_process_library_document(
    self,  # type: ignore[no-untyped-def]
    library_document_id: str,
    storage_path: str,
    on_complete_callbacks: list[dict] | None = None,
) -> dict[str, str | int | None]:
    """Download a library document PDF, run OCR, then process (chunk + embed).

    Used for auto-fetched Act PDFs that are stored in Supabase but never OCR'd.

    Args:
        library_document_id: Library document UUID.
        storage_path: Supabase storage path to the PDF.
        on_complete_callbacks: Optional list of task signatures to fire after
            embed completes. Each dict has "task_name" and "kwargs".
            Used to defer verification until chunks/embeddings exist.

    Returns:
        Task result with OCR + processing summary.
    """
    logger.info(
        "ocr_library_document_started",
        library_document_id=library_document_id,
        storage_path=storage_path,
        retry_count=self.request.retries,
    )

    lib_service = get_library_service()
    client = get_service_client()

    if client is None:
        return {
            "status": "failed",
            "library_document_id": library_document_id,
            "reason": "database_not_configured",
        }

    try:
        # 0. Idempotency: if chunks already exist, skip OCR entirely
        existing_chunks = (
            client.table("library_chunks")
            .select("id", count="exact")
            .eq("library_document_id", library_document_id)
            .execute()
        )
        if (existing_chunks.count or 0) > 0:
            logger.info(
                "ocr_library_document_skipped_chunks_exist",
                library_document_id=library_document_id,
                chunk_count=existing_chunks.count,
            )
            # Dispatch embedding only (chunks exist, may need embeddings)
            embed_library_chunks.apply_async(
                kwargs={"library_document_id": library_document_id},
                queue="default",
            )
            return {
                "status": "skipped",
                "library_document_id": library_document_id,
                "reason": f"chunks_exist ({existing_chunks.count})",
            }

        # 1. Update status to processing
        lib_service.update_status(library_document_id, LibraryDocumentStatus.PROCESSING)

        # 2. Download PDF from Supabase storage
        # BUG-016: Pre-flight check — verify file exists before download.
        # Missing files are permanent failures (retrying won't help), so fail
        # immediately with a clear flag instead of exhausting retries → DLQ.
        try:
            pdf_bytes = client.storage.from_("documents").download(storage_path)
        except Exception as storage_err:
            err_msg = str(storage_err).lower()
            if (
                "not found" in err_msg
                or "404" in err_msg
                or "object not found" in err_msg
            ):
                logger.error(
                    "ocr_library_document_storage_missing",
                    library_document_id=library_document_id,
                    storage_path=storage_path,
                    error=str(storage_err),
                )
                lib_service.update_status(
                    library_document_id,
                    LibraryDocumentStatus.FAILED,
                    quality_flags=["storage_missing"],
                )
                return {
                    "status": "failed",
                    "library_document_id": library_document_id,
                    "reason": f"storage_missing: {storage_path}",
                }
            # Re-raise transient errors (network, timeout) for retry
            raise

        # 3. Extract text — try pypdf first (free, fast), fall back to Document AI OCR
        extracted_text = ""
        page_count = 0
        extraction_method = "unknown"

        try:
            from io import BytesIO

            import pypdf

            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            page_texts = []
            for page in reader.pages:
                page_texts.append(page.extract_text() or "")
            extracted_text = "\n".join(page_texts)
            extraction_method = "pypdf"
            logger.info(
                "library_text_extraction_pypdf",
                library_document_id=library_document_id,
                page_count=page_count,
                text_length=len(extracted_text),
                avg_chars_per_page=len(extracted_text) // max(page_count, 1),
            )
        except Exception as e:
            logger.warning(
                "library_pypdf_extraction_failed",
                library_document_id=library_document_id,
                error=str(e),
            )

        # If pypdf got too little text (<100 chars/page avg), the PDF is likely
        # a scan — fall back to Document AI OCR
        avg_chars = len(extracted_text.strip()) // max(page_count, 1)
        if avg_chars < 100:
            logger.info(
                "library_falling_back_to_ocr",
                library_document_id=library_document_id,
                pypdf_chars=len(extracted_text),
                avg_chars_per_page=avg_chars,
                reason="insufficient text from pypdf",
            )
            from app.services.ocr.processor import OCRProcessor

            processor = OCRProcessor()
            ocr_result = processor.process_document(
                pdf_bytes, library_document_id=library_document_id
            )
            extracted_text = ocr_result.full_text
            page_count = ocr_result.page_count
            extraction_method = "document_ai"

        if not extracted_text or len(extracted_text.strip()) < 50:
            lib_service.update_status(
                library_document_id,
                LibraryDocumentStatus.FAILED,
                quality_flags=["ocr_empty_text"],
            )
            return {
                "status": "failed",
                "library_document_id": library_document_id,
                "reason": "empty_text",
            }

        # 4. Update page_count on the library document
        client.table("library_documents").update(
            {
                "page_count": page_count,
            }
        ).eq("id", library_document_id).execute()

        # 5. Chunk inline (text is already in memory — no need to serialize
        #    through Redis, which hits the 100MB Upstash record limit for
        #    large Acts like Income Tax Act at 3MB+).
        chunk_result = chunk_library_document(
            library_document_id,
            extracted_text,
        )
        logger.info(
            "library_chunking_inline_complete",
            library_document_id=library_document_id,
            chunk_count=chunk_result.get("chunk_count", 0),
        )

        # 6. Dispatch embedding as a separate task (small message — just the ID)
        from celery import chain

        steps = [embed_library_chunks.s(library_document_id=library_document_id)]

        if on_complete_callbacks:
            steps.append(
                fire_library_callbacks.s(
                    library_document_id=library_document_id,
                    callbacks=on_complete_callbacks,
                )
            )

        if len(steps) == 1:
            steps[0].apply_async(queue="default")
        else:
            pipeline = chain(*steps)
            pipeline.link_error(
                on_library_chain_error.s(
                    library_document_id=library_document_id,
                )
            )
            pipeline.apply_async(queue="default")

        logger.info(
            "ocr_library_document_complete",
            library_document_id=library_document_id,
            text_length=len(extracted_text),
            page_count=page_count,
            extraction_method=extraction_method,
            has_callbacks=bool(on_complete_callbacks),
        )

        return {
            "status": "ocr_complete",
            "library_document_id": library_document_id,
            "text_length": len(extracted_text),
            "page_count": page_count,
            "extraction_method": extraction_method,
        }

    except Exception as e:
        logger.error(
            "ocr_library_document_failed",
            library_document_id=library_document_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=self.request.retries,
            max_retries=self.max_retries,
        )

        # Retry on transient errors before marking as failed
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            try:
                lib_service.update_status(
                    library_document_id,
                    LibraryDocumentStatus.FAILED,
                    quality_flags=["ocr_failed"],
                )
            except Exception as status_err:
                logger.error(
                    "status_update_on_failure_swallowed",
                    error=str(status_err),
                    library_document_id=library_document_id,
                    target_status="failed",
                    original_error=str(e),
                )
            return {
                "status": "failed",
                "library_document_id": library_document_id,
                "reason": str(e),
            }


# =============================================================================
# Library Chain Error Callback (DPP-002 — P7/P8 wall)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.on_library_chain_error",
    bind=True,
    ignore_result=True,
    queue="default",
)
def on_library_chain_error(
    self,  # type: ignore[no-untyped-def]
    failed_task_id: str,
    *,
    library_document_id: str | None = None,
) -> None:
    """Safety-net error callback for the library processing chain.

    Fired by Celery's link_error when any task in the library chain raises.
    Updates library document status to FAILED idempotently.
    """
    logger.error(
        "library_pipeline_chain_error",
        failed_task_id=failed_task_id,
        library_document_id=library_document_id,
    )
    if library_document_id:
        try:
            lib_service = get_library_service()
            lib_service.update_status(
                library_document_id,
                LibraryDocumentStatus.FAILED,
                quality_flags=["chain_error"],
            )
        except Exception as e:
            logger.warning(
                "library_chain_error_cleanup_failed",
                library_document_id=library_document_id,
                error=str(e),
            )


# NOTE: process_library_document was removed — it was a parallel path to
# ocr_and_process_library_document that passed extracted_text through Redis
# (hitting the 100MB Upstash limit). All callers now use
# ocr_and_process_library_document which extracts text inline via pypdf.


# =============================================================================
# Promote Chunks from Documents → Library
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.library_tasks.promote_chunks_to_library",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)  # type: ignore[misc]
def promote_chunks_to_library(
    self,  # type: ignore[no-untyped-def]
    library_document_id: str,
    source_document_id: str,
    storage_path: str,
) -> dict[str, str | int | None]:
    """Copy chunks from documents table to library_chunks, or OCR if none exist.

    Used when a document is promoted from the matter-specific documents table
    to the shared library. Copies existing chunks to avoid re-processing.

    Args:
        library_document_id: Target library document UUID.
        source_document_id: Source document UUID (from documents table).
        storage_path: Supabase storage path to PDF (fallback for OCR).

    Returns:
        Task result dict.
    """
    logger.info(
        "promote_chunks_started",
        library_document_id=library_document_id,
        source_document_id=source_document_id,
    )

    client = get_service_client()
    if client is None:
        return {
            "status": "failed",
            "library_document_id": library_document_id,
            "reason": "database_not_configured",
        }

    try:
        # Idempotency: skip if library_chunks already exist
        existing = (
            client.table("library_chunks")
            .select("id", count="exact")
            .eq("library_document_id", library_document_id)
            .execute()
        )

        if existing.count and existing.count > 0:
            logger.info(
                "promote_chunks_already_exist",
                library_document_id=library_document_id,
                count=existing.count,
            )
            # Ensure status is completed
            client.table("library_documents").update(
                {
                    "status": "completed",
                }
            ).eq("id", library_document_id).execute()
            return {
                "status": "already_exists",
                "library_document_id": library_document_id,
                "chunk_count": existing.count,
            }

        # Check if source document has chunks
        source_chunks = (
            client.table("chunks")
            .select(
                "content, embedding, page_number, chunk_index, token_count, chunk_type"
            )
            .eq("document_id", source_document_id)
            .is_("parent_chunk_id", "null")
            .order("chunk_index")
            .execute()
        )

        if source_chunks.data and len(source_chunks.data) > 0:
            # Copy chunks to library_chunks
            library_chunks = []
            for i, chunk in enumerate(source_chunks.data):
                library_chunks.append(
                    {
                        "library_document_id": library_document_id,
                        "chunk_index": chunk.get("chunk_index", i),
                        "content": chunk["content"],
                        "page_number": chunk.get("page_number"),
                        "token_count": chunk.get("token_count"),
                        "chunk_type": chunk.get("chunk_type", "parent"),
                        "embedding": chunk.get("embedding"),
                    }
                )

            # Insert in batches to avoid payload limits
            batch_size = 100
            total_inserted = 0
            for start in range(0, len(library_chunks), batch_size):
                batch = library_chunks[start : start + batch_size]
                client.table("library_chunks").insert(batch).execute()
                total_inserted += len(batch)

            # Update library document status to completed
            client.table("library_documents").update(
                {
                    "status": "completed",
                    "page_count": max(
                        (c.get("page_number") or 0 for c in source_chunks.data),
                        default=None,
                    ),
                }
            ).eq("id", library_document_id).execute()

            logger.info(
                "promote_chunks_copied",
                library_document_id=library_document_id,
                source_document_id=source_document_id,
                chunk_count=total_inserted,
            )

            return {
                "status": "chunks_copied",
                "library_document_id": library_document_id,
                "chunk_count": total_inserted,
            }

        else:
            # No chunks in source — fall back to OCR + processing
            logger.info(
                "promote_chunks_no_source_chunks_fallback_to_ocr",
                library_document_id=library_document_id,
                source_document_id=source_document_id,
            )
            ocr_and_process_library_document.apply_async(
                kwargs={
                    "library_document_id": library_document_id,
                    "storage_path": storage_path,
                },
                queue="default",
            )
            return {
                "status": "ocr_fallback_triggered",
                "library_document_id": library_document_id,
            }

    except Exception as e:
        logger.error(
            "promote_chunks_failed",
            library_document_id=library_document_id,
            source_document_id=source_document_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # Fall back to OCR as last resort
            try:
                ocr_and_process_library_document.apply_async(
                    kwargs={
                        "library_document_id": library_document_id,
                        "storage_path": storage_path,
                    },
                    queue="default",
                )
            except Exception as dispatch_err:
                logger.error(
                    "ocr_fallback_dispatch_swallowed",
                    error=str(dispatch_err),
                    library_document_id=library_document_id,
                    storage_path=storage_path,
                )
            return {
                "status": "failed",
                "library_document_id": library_document_id,
                "reason": str(e),
            }
