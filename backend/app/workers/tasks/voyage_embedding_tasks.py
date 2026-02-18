"""Celery tasks for batch Voyage AI embedding migration.

Generates Voyage law-2 embeddings (1024 dims) for existing chunks that
already have OpenAI embeddings but lack Voyage embeddings. Stores results
in the new `embedding_voyage` column alongside the existing OpenAI column.
"""

import asyncio
import time

import structlog

from app.workers.celery import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 200
DEFAULT_BATCH_SIZE = 50
RATE_LIMIT_DELAY = 0.5  # seconds between batches


# =============================================================================
# Batch Migration Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.voyage_embedding_tasks.batch_embed_voyage",
    bind=True,
    max_retries=0,
    soft_time_limit=7200,  # 2 hour soft limit
    time_limit=7500,  # 2.5 hour hard limit
)
def batch_embed_voyage(
    self,
    matter_id: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume_from_chunk_id: str | None = None,
) -> dict:
    """Batch-generate Voyage embeddings for chunks missing them.

    Fetches chunks with `embedding IS NOT NULL` but `embedding_voyage IS NULL`,
    calls VoyageEmbeddingService.embed_batch() with input_type="document",
    and updates the `embedding_voyage` column.

    Args:
        matter_id: Optional matter ID to limit scope.
        batch_size: Chunks per batch (default 50).
        resume_from_chunk_id: Resume from this chunk ID.

    Returns:
        Dict with migration results.
    """
    if not isinstance(batch_size, int) or batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
        return {
            "status": "validation_error",
            "error": f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}",
        }

    logger.info(
        "voyage_batch_embed_started",
        matter_id=matter_id,
        batch_size=batch_size,
        resume_from=resume_from_chunk_id,
    )

    try:
        result = run_async(_run_migration(matter_id, batch_size, resume_from_chunk_id))
        logger.info("voyage_batch_embed_completed", **result)
        return result
    except Exception as e:
        logger.error("voyage_batch_embed_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


async def _run_migration(
    matter_id: str | None,
    batch_size: int,
    resume_from_chunk_id: str | None,
) -> dict:
    """Async migration logic."""
    from app.core.supabase import get_service_client
    from app.services.rag.voyage_embedder import get_voyage_embedding_service

    supabase = get_service_client()
    if supabase is None:
        return {"status": "failed", "error": "Service client not available"}

    embedder = get_voyage_embedding_service()

    processed = 0
    failed = 0
    last_chunk_id = resume_from_chunk_id
    start_time = time.time()

    while True:
        # Fetch batch of chunks needing Voyage embeddings
        query = supabase.table("chunks").select(
            "id, content"
        ).is_("embedding_voyage", "null").not_.is_("embedding", "null")

        if matter_id:
            query = query.eq("matter_id", matter_id)
        if last_chunk_id:
            query = query.gt("id", last_chunk_id)

        query = query.order("id").limit(batch_size)
        response = query.execute()

        if not response.data:
            break  # No more chunks to process

        chunks = response.data
        texts = [c["content"] for c in chunks]

        # Generate Voyage embeddings
        embeddings = await embedder.embed_batch(
            texts, skip_empty=True, input_type="document",
        )

        # Update each chunk with its Voyage embedding
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is None:
                failed += 1
                continue

            try:
                supabase.table("chunks").update(
                    {"embedding_voyage": embedding}
                ).eq("id", chunk["id"]).execute()
                processed += 1
            except Exception as e:
                logger.warning(
                    "voyage_embed_chunk_update_failed",
                    chunk_id=chunk["id"],
                    error=str(e),
                )
                failed += 1

        last_chunk_id = chunks[-1]["id"]

        # Rate limit between batches
        await asyncio.sleep(RATE_LIMIT_DELAY)

    elapsed = time.time() - start_time

    return {
        "status": "completed",
        "processed_chunks": processed,
        "failed_chunks": failed,
        "last_chunk_id": last_chunk_id,
        "elapsed_seconds": round(elapsed, 1),
        "matter_id": matter_id,
    }
