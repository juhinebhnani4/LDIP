"""Service for archiving reasoning traces to cold storage (Story 4.2).

Epic 4: Legal Defensibility (Gap Remediation)

This service manages archival of reasoning traces to Supabase Storage:
- Archive traces older than retention period to cold storage
- Store as gzipped JSON for space efficiency
- Restore traces from cold storage when needed

Implements:
- AC 4.2.1: Archive traces older than 30 days to Supabase Storage (gzipped JSONL)
- AC 4.2.2: Hydrate traces from cold storage within 5 seconds
- AC 4.2.3: Graceful failure handling - trace remains in hot storage on failure
- AC 4.2.4: Track hot and cold storage counts
"""

import gzip
import json
from datetime import UTC, datetime, timedelta

import structlog
from supabase import Client

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Configuration
HOT_RETENTION_DAYS = 30
ARCHIVE_BATCH_SIZE = 100


class ReasoningArchiveService:
    """Manages archival of reasoning traces to Supabase Storage.

    Story 4.2: Tiered reasoning storage for cost optimization.

    SECURITY: Uses service role client for storage operations.
    Archival runs as background task without user context.
    """

    def __init__(self, client: Client | None = None) -> None:
        """Initialize reasoning archive service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self._client = client
        self.bucket = "reasoning-archive"

    @property
    def client(self) -> Client:
        """Get Supabase client, initializing if needed."""
        if self._client is None:
            self._client = get_service_client()
        if self._client is None:
            raise RuntimeError("Supabase client not configured")
        return self._client

    async def archive_old_traces(self) -> dict[str, int]:
        """Archive traces older than HOT_RETENTION_DAYS to cold storage.

        Story 4.2: AC 4.2.1 - Move old traces to Supabase Storage.

        Returns:
            Dict with 'archived' and 'failed' counts.
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=HOT_RETENTION_DAYS)

        # Find traces to archive
        result = (
            self.client.table("reasoning_traces")
            .select("id, matter_id, reasoning_text, reasoning_structured, input_summary, created_at")
            .lt("created_at", cutoff_date.isoformat())
            .is_("archived_at", "null")
            .limit(ARCHIVE_BATCH_SIZE)
            .execute()
        )

        traces = result.data
        if not traces:
            logger.info("reasoning_archival_no_traces", cutoff_date=cutoff_date.isoformat())
            return {"archived": 0, "failed": 0}

        archived = 0
        failed = 0

        for trace in traces:
            try:
                await self._archive_single_trace(trace)
                archived += 1
            except Exception as e:
                logger.error(
                    "reasoning_trace_archive_failed",
                    trace_id=trace["id"],
                    error=str(e),
                )
                failed += 1

        logger.info(
            "reasoning_archival_batch_complete",
            archived=archived,
            failed=failed,
            cutoff_date=cutoff_date.isoformat(),
        )

        return {"archived": archived, "failed": failed}

    async def _archive_single_trace(self, trace: dict) -> None:
        """Archive a single trace to Supabase Storage.

        Story 4.2: AC 4.2.1 - Store as gzipped JSON.

        Args:
            trace: Trace record from database.

        Raises:
            Exception: If archival fails.
        """
        trace_id = trace["id"]
        matter_id = trace["matter_id"]

        # Prepare archive data
        archive_data = {
            "reasoning_text": trace["reasoning_text"],
            "reasoning_structured": trace["reasoning_structured"],
            "input_summary": trace["input_summary"],
            "archived_at": datetime.now(UTC).isoformat(),
        }

        # Compress
        compressed = gzip.compress(json.dumps(archive_data).encode("utf-8"))

        # Upload to storage
        archive_path = f"{matter_id}/{trace_id}.json.gz"

        self.client.storage.from_(self.bucket).upload(
            archive_path,
            compressed,
            {"content-type": "application/gzip"},
        )

        # Update trace record (clear large text, set archive path)
        # Story 4.2: Keep a placeholder text so trace row is still meaningful
        self.client.table("reasoning_traces").update({
            "reasoning_text": f"[Archived to cold storage: {archive_path}]",
            "reasoning_structured": None,
            "input_summary": None,
            "archived_at": datetime.now(UTC).isoformat(),
            "archive_path": archive_path,
        }).eq("id", trace_id).execute()

        logger.debug(
            "reasoning_trace_archived",
            trace_id=trace_id,
            matter_id=matter_id,
            archive_path=archive_path,
            compressed_size=len(compressed),
        )

    async def restore_trace(self, trace_id: str, matter_id: str) -> bool:
        """Restore a trace from cold storage to hot storage.

        Story 4.2: Used when archived trace needs frequent access.

        Args:
            trace_id: Trace UUID to restore.
            matter_id: Matter UUID for validation.

        Returns:
            True if restoration was successful.
        """
        # Get trace record
        result = (
            self.client.table("reasoning_traces")
            .select("*")
            .eq("id", trace_id)
            .eq("matter_id", matter_id)
            .maybe_single()
            .execute()
        )

        if not result.data or not result.data.get("archive_path"):
            logger.warning(
                "reasoning_trace_restore_not_found",
                trace_id=trace_id,
                matter_id=matter_id,
            )
            return False

        archive_path = result.data["archive_path"]

        try:
            # Download from storage
            response = self.client.storage.from_(self.bucket).download(archive_path)
            archived_data = json.loads(gzip.decompress(response))

            # Restore to database
            self.client.table("reasoning_traces").update({
                "reasoning_text": archived_data["reasoning_text"],
                "reasoning_structured": archived_data.get("reasoning_structured"),
                "input_summary": archived_data.get("input_summary"),
                "archived_at": None,
                "archive_path": None,
            }).eq("id", trace_id).execute()

            # Delete from storage
            self.client.storage.from_(self.bucket).remove([archive_path])

            logger.info(
                "reasoning_trace_restored",
                trace_id=trace_id,
                matter_id=matter_id,
            )
            return True

        except Exception as e:
            logger.error(
                "reasoning_trace_restore_failed",
                trace_id=trace_id,
                archive_path=archive_path,
                error=str(e),
            )
            return False

    async def get_archive_stats(self) -> dict[str, int]:
        """Get archival statistics.

        Story 4.2: AC 4.2.4 - Track storage counts.

        Returns:
            Dict with hot and cold storage counts.
        """
        # Get hot storage count
        hot_result = (
            self.client.table("reasoning_traces")
            .select("id", count="exact")
            .is_("archived_at", "null")
            .execute()
        )

        # Get cold storage count
        cold_result = (
            self.client.table("reasoning_traces")
            .select("id", count="exact")
            .not_.is_("archived_at", "null")
            .execute()
        )

        return {
            "hot_storage_count": hot_result.count or 0,
            "cold_storage_count": cold_result.count or 0,
            "total_count": (hot_result.count or 0) + (cold_result.count or 0),
        }


# =============================================================================
# Story 4.2: Singleton Factory
# =============================================================================

_reasoning_archive_service: ReasoningArchiveService | None = None


def get_reasoning_archive_service() -> ReasoningArchiveService:
    """Get singleton ReasoningArchiveService instance.

    Returns:
        ReasoningArchiveService singleton instance.
    """
    global _reasoning_archive_service  # noqa: PLW0603

    if _reasoning_archive_service is None:
        _reasoning_archive_service = ReasoningArchiveService()

    return _reasoning_archive_service


def reset_reasoning_archive_service() -> None:
    """Reset singleton for testing."""
    global _reasoning_archive_service  # noqa: PLW0603
    _reasoning_archive_service = None
    logger.debug("reasoning_archive_service_reset")
