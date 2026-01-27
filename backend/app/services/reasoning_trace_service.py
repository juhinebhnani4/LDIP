"""Service for storing and retrieving reasoning traces (Story 4.1).

Epic 4: Legal Defensibility (Gap Remediation)

This service manages reasoning trace storage and retrieval for legal defensibility:
- Store traces after LLM responses
- Retrieve traces for findings
- Get trace statistics
- Hydrate archived traces from cold storage

Implements:
- AC 4.1.1: Store structured summary with input context, evidence, confidence, rationale
- AC 4.1.2: Graceful failure handling - don't fail main operation on trace storage failure
- AC 4.1.3: Capture reasoning from all engines
- AC 4.1.4: API retrieval of full chain-of-thought
"""

from datetime import datetime

import structlog
from supabase import Client

from app.models.reasoning_trace import (
    EngineType,
    ReasoningTrace,
    ReasoningTraceCreate,
    ReasoningTraceStats,
    ReasoningTraceSummary,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


class ReasoningTraceService:
    """Manages reasoning trace storage and retrieval.

    Story 4.1: Core service for legal defensibility reasoning traces.

    SECURITY: Uses service role client as traces are written by background
    engines without user JWT context. Matter isolation enforced via RLS
    for reads and explicit matter_id validation for writes.
    """

    def __init__(self, client: Client | None = None) -> None:
        """Initialize reasoning trace service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self._client = client

    @property
    def client(self) -> Client:
        """Get Supabase client, initializing if needed."""
        if self._client is None:
            self._client = get_service_client()
        if self._client is None:
            raise RuntimeError("Supabase client not configured")
        return self._client

    async def store_trace(self, trace: ReasoningTraceCreate) -> ReasoningTrace:
        """Store a new reasoning trace.

        Story 4.1: AC 4.1.1 - Store structured summary after LLM response.

        Called by engines after LLM responses to capture reasoning.
        Uses service role to bypass RLS as engines run without user context.

        Args:
            trace: Reasoning trace data to store.

        Returns:
            Created reasoning trace record.

        Raises:
            Exception: If storage fails (caller should catch and continue).
        """
        # Convert to dict with snake_case for database
        data = {
            "matter_id": trace.matter_id,
            "finding_id": trace.finding_id,
            "engine_type": trace.engine_type.value,
            "model_used": trace.model_used,
            "reasoning_text": trace.reasoning_text,
            "reasoning_structured": trace.reasoning_structured,
            "input_summary": trace.input_summary[:1000] if trace.input_summary else None,
            "prompt_template_version": trace.prompt_template_version,
            "confidence_score": trace.confidence_score,
            "tokens_used": trace.tokens_used,
            "cost_usd": float(trace.cost_usd) if trace.cost_usd else None,
        }

        result = self.client.table("reasoning_traces").insert(data).execute()

        if not result.data:
            logger.error(
                "reasoning_trace_storage_failed",
                matter_id=trace.matter_id,
                engine_type=trace.engine_type.value,
            )
            raise RuntimeError("Failed to store reasoning trace")

        logger.info(
            "reasoning_trace_stored",
            trace_id=result.data[0]["id"],
            matter_id=trace.matter_id,
            engine_type=trace.engine_type.value,
            model_used=trace.model_used,
        )

        return self._row_to_trace(result.data[0])

    async def get_trace(self, trace_id: str, matter_id: str) -> ReasoningTrace | None:
        """Get a specific reasoning trace.

        Story 4.1: AC 4.1.4 - Retrieve full chain-of-thought.

        Args:
            trace_id: Trace UUID to retrieve.
            matter_id: Matter UUID for access validation.

        Returns:
            Reasoning trace or None if not found.
        """
        result = (
            self.client.table("reasoning_traces")
            .select("*")
            .eq("id", trace_id)
            .eq("matter_id", matter_id)
            .maybe_single()
            .execute()
        )

        # maybe_single() returns None when no row found
        if result is None or not result.data:
            return None

        trace = self._row_to_trace(result.data)

        # If archived, hydrate from cold storage
        if trace.archived_at and trace.archive_path:
            trace = await self._hydrate_from_archive(trace)

        return trace

    async def get_traces_for_finding(
        self,
        finding_id: str,
        matter_id: str,
    ) -> list[ReasoningTrace]:
        """Get all reasoning traces for a specific finding.

        Story 4.1: AC 4.1.4 - Retrieve reasoning for finding detail view.

        Args:
            finding_id: Finding UUID to get traces for.
            matter_id: Matter UUID for access validation.

        Returns:
            List of reasoning traces for the finding.
        """
        result = (
            self.client.table("reasoning_traces")
            .select("*")
            .eq("finding_id", finding_id)
            .eq("matter_id", matter_id)
            .order("created_at", desc=True)
            .execute()
        )

        return [self._row_to_trace(row) for row in result.data]

    async def get_traces_for_matter(
        self,
        matter_id: str,
        engine_type: EngineType | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ReasoningTraceSummary]:
        """Get reasoning trace summaries for a matter.

        Story 4.1: List view for reasoning traces.

        Args:
            matter_id: Matter UUID.
            engine_type: Optional filter by engine type.
            include_archived: Whether to include archived traces.
            limit: Maximum number of traces to return.
            offset: Number of traces to skip.

        Returns:
            List of reasoning trace summaries.
        """
        query = (
            self.client.table("reasoning_traces")
            .select("id, engine_type, model_used, reasoning_text, confidence_score, created_at, archived_at")
            .eq("matter_id", matter_id)
        )

        if engine_type:
            query = query.eq("engine_type", engine_type.value)

        if not include_archived:
            query = query.is_("archived_at", "null")

        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        return [
            ReasoningTraceSummary(
                id=row["id"],
                engine_type=EngineType(row["engine_type"]),
                model_used=row["model_used"],
                reasoning_preview=(
                    row["reasoning_text"][:200] + "..."
                    if len(row["reasoning_text"]) > 200
                    else row["reasoning_text"]
                ),
                confidence_score=row["confidence_score"],
                created_at=row["created_at"],
                is_archived=row["archived_at"] is not None,
            )
            for row in result.data
        ]

    async def get_stats(self, matter_id: str) -> ReasoningTraceStats:
        """Get reasoning trace statistics for a matter.

        Story 4.1/4.2: Dashboard statistics for reasoning traces.

        Args:
            matter_id: Matter UUID.

        Returns:
            Statistics for the matter's reasoning traces.
        """
        result = (
            self.client.table("reasoning_traces")
            .select("engine_type, archived_at, tokens_used, cost_usd, created_at")
            .eq("matter_id", matter_id)
            .execute()
        )

        traces = result.data
        if not traces:
            return ReasoningTraceStats(
                total_traces=0,
                traces_by_engine={},
                hot_storage_count=0,
                cold_storage_count=0,
                total_tokens_used=0,
                total_cost_usd=0.0,
                oldest_hot_trace=None,
                newest_trace=None,
            )

        traces_by_engine: dict[str, int] = {}
        hot_count = 0
        cold_count = 0
        total_tokens = 0
        total_cost = 0.0
        hot_traces_dates: list[str] = []
        all_dates: list[str] = []

        for t in traces:
            engine = t["engine_type"]
            traces_by_engine[engine] = traces_by_engine.get(engine, 0) + 1

            if t["archived_at"]:
                cold_count += 1
            else:
                hot_count += 1
                hot_traces_dates.append(t["created_at"])

            total_tokens += t["tokens_used"] or 0
            total_cost += float(t["cost_usd"] or 0)
            all_dates.append(t["created_at"])

        return ReasoningTraceStats(
            total_traces=len(traces),
            traces_by_engine=traces_by_engine,
            hot_storage_count=hot_count,
            cold_storage_count=cold_count,
            total_tokens_used=total_tokens,
            total_cost_usd=total_cost,
            oldest_hot_trace=min(hot_traces_dates) if hot_traces_dates else None,
            newest_trace=max(all_dates) if all_dates else None,
        )

    async def _hydrate_from_archive(self, trace: ReasoningTrace) -> ReasoningTrace:
        """Fetch full reasoning text from cold storage.

        Story 4.2: AC 4.2.2 - Hydrate archived traces on request.

        Args:
            trace: Trace with archive_path set.

        Returns:
            Trace with full reasoning text restored.
        """
        if not trace.archive_path:
            return trace

        try:
            import gzip
            import json

            # Download from Supabase Storage
            response = self.client.storage.from_("reasoning-archive").download(trace.archive_path)
            archived_data = json.loads(gzip.decompress(response))

            # Create new trace with hydrated data
            return ReasoningTrace(
                id=trace.id,
                matter_id=trace.matter_id,
                finding_id=trace.finding_id,
                engine_type=trace.engine_type,
                model_used=trace.model_used,
                reasoning_text=archived_data.get("reasoning_text", trace.reasoning_text),
                reasoning_structured=archived_data.get("reasoning_structured"),
                input_summary=archived_data.get("input_summary"),
                prompt_template_version=trace.prompt_template_version,
                confidence_score=trace.confidence_score,
                tokens_used=trace.tokens_used,
                cost_usd=trace.cost_usd,
                created_at=trace.created_at,
                archived_at=trace.archived_at,
                archive_path=trace.archive_path,
            )
        except Exception as e:
            logger.error(
                "reasoning_trace_hydration_failed",
                trace_id=trace.id,
                archive_path=trace.archive_path,
                error=str(e),
            )
            # Return original trace if hydration fails
            return trace

    def _row_to_trace(self, row: dict) -> ReasoningTrace:
        """Convert database row to ReasoningTrace model.

        Args:
            row: Database row dict.

        Returns:
            ReasoningTrace model instance.
        """
        return ReasoningTrace(
            id=row["id"],
            matter_id=row["matter_id"],
            finding_id=row.get("finding_id"),
            engine_type=EngineType(row["engine_type"]),
            model_used=row["model_used"],
            reasoning_text=row["reasoning_text"],
            reasoning_structured=row.get("reasoning_structured"),
            input_summary=row.get("input_summary"),
            prompt_template_version=row.get("prompt_template_version"),
            confidence_score=row.get("confidence_score"),
            tokens_used=row.get("tokens_used"),
            cost_usd=float(row["cost_usd"]) if row.get("cost_usd") else None,
            created_at=row["created_at"],
            archived_at=row.get("archived_at"),
            archive_path=row.get("archive_path"),
        )


# =============================================================================
# Story 4.1: Singleton Factory
# =============================================================================

_reasoning_trace_service: ReasoningTraceService | None = None


def get_reasoning_trace_service() -> ReasoningTraceService:
    """Get singleton ReasoningTraceService instance.

    Returns:
        ReasoningTraceService singleton instance.
    """
    global _reasoning_trace_service  # noqa: PLW0603

    if _reasoning_trace_service is None:
        _reasoning_trace_service = ReasoningTraceService()

    return _reasoning_trace_service


def reset_reasoning_trace_service() -> None:
    """Reset singleton for testing."""
    global _reasoning_trace_service  # noqa: PLW0603
    _reasoning_trace_service = None
    logger.debug("reasoning_trace_service_reset")
