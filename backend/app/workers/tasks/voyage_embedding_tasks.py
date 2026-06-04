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
DEFAULT_BATCH_SIZE = 5  # Small default to respect free-tier rate limits (3 RPM, 10K TPM)
RATE_LIMIT_DELAY = 25  # 25 seconds between batches (free tier = 3 RPM)
RATE_LIMIT_RETRY_DELAY = 60  # Wait 60s on rate limit error before retrying
MAX_RATE_LIMIT_RETRIES = 3  # Max retries per batch on rate limit


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
    calls Voyage API directly with rate-limit retry logic,
    and updates the `embedding_voyage` column.

    Args:
        matter_id: Optional matter ID to limit scope.
        batch_size: Chunks per batch (default 5 for free-tier safety).
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
    """Async migration logic with rate-limit retry."""
    from app.services.supabase.client import get_service_client

    supabase = get_service_client()
    if supabase is None:
        return {"status": "failed", "error": "Service client not available"}

    # Import voyageai directly to bypass circuit breaker for batch migration
    import voyageai

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.voyage_api_key:
        return {"status": "failed", "error": "VOYAGE_API_KEY not configured"}

    client = voyageai.Client(api_key=settings.voyage_api_key)

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

        # Call Voyage API with rate-limit retry
        embeddings = None
        for retry in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                result = client.embed(
                    texts=texts,
                    model="voyage-law-2",
                    input_type="document",
                )
                embeddings = result.embeddings
                break
            except Exception as e:
                error_str = str(e)
                if "rate" in error_str.lower() or "RateLimitError" in type(e).__name__:
                    logger.warning(
                        "voyage_batch_rate_limited",
                        retry=retry + 1,
                        max_retries=MAX_RATE_LIMIT_RETRIES,
                        delay=RATE_LIMIT_RETRY_DELAY,
                    )
                    if retry < MAX_RATE_LIMIT_RETRIES:
                        await asyncio.sleep(RATE_LIMIT_RETRY_DELAY)
                        continue
                logger.error(
                    "voyage_batch_embed_api_error",
                    error=error_str,
                    error_type=type(e).__name__,
                    batch_size=len(texts),
                )
                break

        if embeddings is None:
            # All retries failed, mark all chunks as failed
            failed += len(chunks)
            last_chunk_id = chunks[-1]["id"]
            await asyncio.sleep(RATE_LIMIT_RETRY_DELAY)
            continue

        # Update each chunk with its Voyage embedding
        for chunk, embedding in zip(chunks, embeddings, strict=False):
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
        logger.info(
            "voyage_batch_progress",
            processed=processed,
            failed=failed,
            last_chunk_id=last_chunk_id,
        )

        # Rate limit between batches (respect free tier 3 RPM)
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
