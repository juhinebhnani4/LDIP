"""Evaluation baseline management service.

Gap 9: Automated RAGAS Regression — Baseline Tracking

Baselines are known-good score snapshots for a matter. They serve as the
reference point for regression detection: each new batch evaluation is
compared against the active baseline to detect quality drops.

Design decisions:
- One active baseline per matter (enforced by partial unique index in DB)
- Creating a new baseline deactivates the previous one (never deleted — history)
- Per-item scores stored in JSONB for granular regression detection
- Auto-promote: first successful batch run becomes the baseline automatically
- Manual promote: admin can promote any batch run to baseline via API
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


class BaselineError(Exception):
    """Error in baseline operations."""

    def __init__(self, message: str, code: str = "BASELINE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class BaselineService:
    """Manages evaluation baselines for regression detection.

    Baselines are immutable snapshots. The only mutation is deactivating
    a baseline when a new one is created (is_active = FALSE).
    """

    @property
    def _supabase(self):  # noqa: ANN202
        """Lazy-load service client (admin access for cross-matter operations)."""
        return get_service_client()

    async def get_active_baseline(self, matter_id: str) -> dict[str, Any] | None:
        """Get the active baseline for a matter.

        Returns None if no baseline exists (matter has never been baselined).
        """
        try:
            result = (
                self._supabase.table("evaluation_baselines")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(
                "baseline_get_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return None

    async def create_baseline_from_job(
        self,
        matter_id: str,
        job_id: str,
        created_by: str = "system",
    ) -> dict[str, Any] | None:
        """Promote a batch evaluation run to active baseline.

        Steps:
        1. Fetch all evaluation_results for this job_id
        2. Calculate aggregate and per-item scores
        3. Deactivate any existing active baseline for this matter
        4. Insert new baseline as active

        Args:
            matter_id: Matter UUID.
            job_id: Celery task ID of the batch run to promote.
            created_by: 'system' for auto-promote, user_id for manual.

        Returns:
            Created baseline record, or None on failure.
        """
        try:
            # BUG-3 fix: Idempotency check — if this job_id was already promoted,
            # return the existing baseline instead of creating a duplicate.
            existing = (
                self._supabase.table("evaluation_baselines")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("promoted_from_job_id", job_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                logger.info(
                    "baseline_already_exists_for_job",
                    matter_id=matter_id,
                    job_id=job_id,
                    baseline_id=existing.data[0].get("id"),
                )
                return existing.data[0]

            # Step 1: Fetch batch results
            result = (
                self._supabase.table("evaluation_results")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("job_id", job_id)
                .execute()
            )

            if not result.data:
                logger.warning(
                    "baseline_no_results",
                    matter_id=matter_id,
                    job_id=job_id,
                )
                return None

            rows = result.data
            successful = [r for r in rows if r.get("overall_score", 0) > 0]

            if not successful:
                logger.warning(
                    "baseline_no_successful_results",
                    matter_id=matter_id,
                    job_id=job_id,
                    total=len(rows),
                )
                return None

            # Step 2: Calculate scores
            avg_overall = sum(r["overall_score"] for r in successful) / len(successful)

            def _safe_avg(key: str) -> float | None:
                vals = [r[key] for r in successful if r.get(key) is not None]
                return sum(vals) / len(vals) if vals else None

            avg_faithfulness = _safe_avg("faithfulness")
            avg_relevancy = _safe_avg("answer_relevancy")
            avg_recall = _safe_avg("context_recall")

            # Per-item scores keyed by golden_item_id
            per_item_scores: dict[str, dict[str, Any]] = {}
            for r in successful:
                gid = r.get("golden_item_id")
                if gid:
                    per_item_scores[gid] = {
                        "overall": r.get("overall_score"),
                        "faithfulness": r.get("faithfulness"),
                        "answer_relevancy": r.get("answer_relevancy"),
                        "context_recall": r.get("context_recall"),
                        "question": (r.get("question") or "")[:100],
                    }

            # Get pipeline_config from first result (all should be same config)
            pipeline_config = successful[0].get("pipeline_config", {})

            # Step 3 & 4: Deactivate old baseline, then insert new one.
            #
            # IMPORTANT: These are two separate Supabase REST calls — NOT a single
            # database transaction. If the insert (Step 4) fails after the deactivate
            # (Step 3) succeeds, the matter will temporarily have no active baseline.
            #
            # Mitigations:
            # - auto_create_if_missing() runs after every batch eval, so the next
            #   nightly run will re-create a baseline from the latest batch results.
            # - The partial unique index (is_active=TRUE per matter_id) prevents
            #   duplicate active baselines even under concurrent writes.
            # - Regression detection gracefully returns "no_baseline" if none exists.
            #
            # If Supabase adds RPC-based transaction support, this should be migrated
            # to a single BEGIN/COMMIT block.

            # Step 3: Deactivate existing active baseline
            self._supabase.table("evaluation_baselines").update(
                {"is_active": False}
            ).eq("matter_id", matter_id).eq("is_active", True).execute()

            # Step 4: Insert new active baseline
            baseline_row = {
                "matter_id": matter_id,
                "avg_overall": round(avg_overall, 4),
                "avg_faithfulness": round(avg_faithfulness, 4)
                if avg_faithfulness is not None
                else None,
                "avg_relevancy": round(avg_relevancy, 4)
                if avg_relevancy is not None
                else None,
                "avg_recall": round(avg_recall, 4) if avg_recall is not None else None,
                "per_item_scores": per_item_scores,
                "total_items": len(rows),
                "successful_items": len(successful),
                "promoted_from_job_id": job_id,
                "pipeline_config": pipeline_config,
                "created_by": created_by,
                "created_at": datetime.now(UTC).isoformat(),
                "is_active": True,
            }

            insert_result = (
                self._supabase.table("evaluation_baselines")
                .insert(baseline_row)
                .execute()
            )

            baseline = insert_result.data[0] if insert_result.data else None

            logger.info(
                "baseline_created",
                matter_id=matter_id,
                job_id=job_id,
                avg_overall=round(avg_overall, 4),
                total_items=len(rows),
                successful=len(successful),
                created_by=created_by,
            )

            return baseline

        except Exception as e:
            logger.error(
                "baseline_create_failed",
                matter_id=matter_id,
                job_id=job_id,
                error=str(e),
            )
            raise BaselineError(f"Failed to create baseline: {e}") from e

    async def auto_create_if_missing(
        self,
        matter_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Auto-create baseline if none exists for this matter.

        Called after every successful batch evaluation. Only creates a baseline
        if the matter has no active baseline (first run scenario).

        Returns:
            Created baseline (if new), or None (if one already exists).
        """
        existing = await self.get_active_baseline(matter_id)
        if existing:
            return None

        logger.info(
            "baseline_auto_creating",
            matter_id=matter_id,
            job_id=job_id,
            reason="no_existing_baseline",
        )

        return await self.create_baseline_from_job(
            matter_id=matter_id,
            job_id=job_id,
            created_by="system",
        )

    async def get_baseline_history(
        self,
        matter_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get baseline history for a matter (most recent first).

        Useful for admin UI to see how baselines evolved over time.
        """
        try:
            result = (
                self._supabase.table("evaluation_baselines")
                .select("*")
                .eq("matter_id", matter_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(
                "baseline_history_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []
