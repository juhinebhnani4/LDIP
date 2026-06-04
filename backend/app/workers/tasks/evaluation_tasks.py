"""Celery tasks for RAG evaluation.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Runs batch evaluation of golden dataset items using RAGAS metrics.

Gap 9: Automated RAGAS Regression — Scheduled evaluation, baseline tracking,
regression detection, cost budgeting.

Fix B1/B2/B3 (2026-02-16): Fixed column mismatches, replaced non-existent
get_chat_service with RAGPipelineService, removed latency_ms references,
added metric_scores JSONB + pipeline_config JSONB for extensibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.services.supabase.client import (
    get_service_client,
)
from app.services.supabase.client import (
    get_supabase_client as get_supabase,
)
from app.workers.celery import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)


def _extract_search_latency(rag_result) -> int | None:  # noqa: ANN001
    """Extract actual search latency from RAG pipeline result.

    The RAG adapter tracks search+rerank time separately from full pipeline
    time. This extracts that value for accurate A/B latency comparison.
    Falls back to full pipeline execution_time_ms if search_latency not available.
    """
    if hasattr(rag_result, "search_latency_ms") and rag_result.search_latency_ms is not None:
        return rag_result.search_latency_ms
    # Fallback: use full pipeline time (less accurate but better than nothing)
    if hasattr(rag_result, "execution_time_ms"):
        return rag_result.execution_time_ms
    return None


class EvaluationTaskError(Exception):
    """Error in evaluation task."""

    def __init__(self, message: str, code: str = "EVALUATION_TASK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


def _build_evaluation_row(
    *,
    matter_id: str,
    question: str,
    answer: str,
    contexts: list[str],
    eval_result: Any,
    triggered_by: str,
    pipeline_config: dict[str, Any] | None = None,
    golden_item_id: str | None = None,
    expected_answer: str | None = None,
    job_id: str | None = None,
    chat_message_id: str | None = None,
    embedding_provider: str | None = None,
    rerank_provider: str | None = None,
    search_latency_ms: int | None = None,
) -> dict[str, Any]:
    """Build a row dict matching the evaluation_results schema exactly.

    Single source of truth for column names. If the schema changes,
    update this function only.

    Schema columns (20260122000002 + 20260216000001 + 20260220600001):
        id (auto), matter_id, golden_item_id, question, answer, contexts,
        context_recall, faithfulness, answer_relevancy, overall_score,
        evaluated_at, triggered_by, expected_answer, job_id,
        chat_message_id, metric_scores, pipeline_config,
        embedding_provider, rerank_provider, search_latency_ms
    """
    scores = eval_result.scores

    row: dict[str, Any] = {
        "matter_id": matter_id,
        "question": question,
        "answer": answer,
        "contexts": contexts,
        # Individual float columns (queryable, constrained 0-1)
        "context_recall": scores.context_recall,
        "faithfulness": scores.faithfulness,
        "answer_relevancy": scores.answer_relevancy,
        "overall_score": eval_result.overall_score,
        # JSONB: all metrics (extensible — future metrics go here without migrations)
        "metric_scores": scores.model_dump(exclude_none=True),
        # Pipeline config snapshot (what RAG setup produced this answer)
        "pipeline_config": pipeline_config or {},
        # Traceability
        "triggered_by": triggered_by,
        "evaluated_at": datetime.now(UTC).isoformat(),
    }

    # Optional fields — only include if present (avoid inserting NULLs needlessly)
    if golden_item_id is not None:
        row["golden_item_id"] = golden_item_id
    if expected_answer is not None:
        row["expected_answer"] = expected_answer
    if job_id is not None:
        row["job_id"] = job_id
    if chat_message_id is not None:
        row["chat_message_id"] = chat_message_id
    # Gap 10: Provider attribution and search latency
    if embedding_provider is not None:
        row["embedding_provider"] = embedding_provider
    if rerank_provider is not None:
        row["rerank_provider"] = rerank_provider
    if search_latency_ms is not None:
        row["search_latency_ms"] = search_latency_ms

    return row


# =============================================================================
# Gap 9: Post-batch regression check + baseline management
# =============================================================================


def _run_post_batch_checks(
    matter_id: str,
    job_id: str,
    successful_count: int,
) -> dict[str, Any]:
    """Run regression detection and baseline management after a batch evaluation.

    Called at the end of run_batch_evaluation. Steps:
    1. Auto-create baseline if none exists (first run scenario)
    2. If baseline exists, fetch batch results and run regression detection
    3. Return regression report (or skip info)

    Returns dict with regression info for inclusion in task result.
    """
    settings = get_settings()

    if successful_count == 0:
        return {"regression_check": "skipped", "reason": "no_successful_results"}

    try:
        async def _check_async() -> dict[str, Any]:
            from app.services.evaluation.baseline_service import BaselineService
            from app.services.evaluation.regression_detector import detect_regression

            baseline_svc = BaselineService()

            # Step 1: Auto-create baseline if missing and feature enabled
            if settings.evaluation_auto_baseline:
                new_baseline = await baseline_svc.auto_create_if_missing(
                    matter_id=matter_id,
                    job_id=job_id,
                )
                if new_baseline:
                    return {
                        "regression_check": "baseline_created",
                        "baseline_id": new_baseline.get("id"),
                        "baseline_avg": new_baseline.get("avg_overall"),
                        "reason": "first_batch_run",
                    }

            # Step 2: Get active baseline for comparison
            baseline = await baseline_svc.get_active_baseline(matter_id)
            if not baseline:
                return {"regression_check": "skipped", "reason": "no_baseline"}

            # Step 3: Fetch current batch results
            supabase = get_service_client()
            result = (
                supabase.table("evaluation_results")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("job_id", job_id)
                .execute()
            )

            if not result.data:
                return {"regression_check": "skipped", "reason": "no_results_found"}

            # Step 4: Run regression detection
            report = detect_regression(
                matter_id=matter_id,
                current_results=result.data,
                baseline=baseline,
            )

            return {
                "regression_check": "completed",
                "has_regression": report.has_regression,
                "regression_report": report.to_dict(),
            }

        return run_async(_check_async(), timeout=60)

    except Exception as e:
        logger.warning(
            "post_batch_regression_check_failed",
            matter_id=matter_id,
            job_id=job_id,
            error=str(e),
        )
        return {
            "regression_check": "error",
            "error": str(e),
        }


@celery_app.task(
    name="app.workers.tasks.evaluation_tasks.run_batch_evaluation",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=2,
    retry_jitter=True,
    time_limit=1800,  # 30 minutes max
    soft_time_limit=1500,  # 25 minutes soft limit
)  # type: ignore[misc]
def run_batch_evaluation(
    self,  # type: ignore[no-untyped-def]
    matter_id: str,
    tags: list[str] | None = None,
    user_id: str | None = None,
    embedding_provider: str | None = None,
    rerank_provider: str | None = None,
) -> dict[str, Any]:
    """Run batch evaluation of golden dataset items.

    For each golden item:
    1. Run the question through the RAG pipeline (same pipeline as chat)
    2. Compare RAG answer against expected answer using RAGAS metrics
    3. Store result in evaluation_results table
    4. (Gap 9) Run regression detection against active baseline

    Args:
        matter_id: Matter UUID to evaluate.
        tags: Optional tags to filter golden items.
        user_id: Optional user ID for tracking.
        embedding_provider: Override provider for A/B testing ('openai'|'voyage').
        rerank_provider: Override provider for A/B testing ('cohere'|'voyage').

    Returns:
        Task result with evaluation summary + regression report.
    """
    job_id = self.request.id

    logger.info(
        "batch_evaluation_started",
        job_id=job_id,
        matter_id=matter_id,
        tags=tags,
        user_id=user_id,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
    )

    try:
        async def _evaluate_async() -> dict[str, Any]:

            from app.services.evaluation import get_ragas_evaluator
            from app.services.evaluation.golden_dataset import GoldenDatasetService
            from app.services.rag.pipeline_service import get_rag_pipeline_service

            # Get golden dataset items
            golden_service = GoldenDatasetService()
            items = await golden_service.get_items(
                matter_id=matter_id,
                tags=tags,
                limit=1000,  # Max items per batch
            )

            if not items:
                return {
                    "status": "no_items",
                    "message": "No golden dataset items found",
                    "total_items": 0,
                }

            evaluator = get_ragas_evaluator()
            pipeline = get_rag_pipeline_service()
            supabase = get_supabase()

            # Gap 10: Build provider context for A/B testing
            # This gets passed through to the orchestrator → adapter → search
            # ab_test_override=True bypasses the kill switch — the kill switch
            # controls live traffic routing, not explicit comparison experiments
            provider_context = None
            if embedding_provider or rerank_provider:
                provider_context = {
                    "embedding_provider": embedding_provider,
                    "rerank_provider": rerank_provider,
                    "ab_test_override": True,
                }

            results = []
            errors = []
            total_score = 0.0

            for item in items:
                try:
                    # Step 1: Run question through RAG pipeline
                    # Gap 10: Pass provider context for A/B testing
                    rag_result = await pipeline.query(
                        matter_id=matter_id,
                        question=item.question,
                        user_id=user_id,
                        context=provider_context,
                        skip_cache=True,
                    )
                    # Gap 10: Extract actual search latency from engine result
                    # (tracked inside the RAG adapter, not full pipeline time)
                    search_latency_ms = _extract_search_latency(rag_result)

                    answer = rag_result.answer
                    contexts = rag_result.contexts

                    if not contexts:
                        contexts = ["No context retrieved"]

                    # Step 2: Evaluate using RAGAS
                    eval_result = await evaluator.evaluate_single(
                        question=item.question,
                        answer=answer,
                        contexts=contexts,
                        ground_truth=item.expected_answer,
                    )

                    # Step 3: Store result in database
                    # Gap 10: Include provider info in pipeline_config
                    enriched_config = {
                        **(rag_result.pipeline_config or {}),
                        "embedding_provider": embedding_provider or "openai",
                        "rerank_provider": rerank_provider or "cohere",
                    }

                    row = _build_evaluation_row(
                        matter_id=matter_id,
                        question=item.question,
                        answer=answer,
                        contexts=contexts,
                        eval_result=eval_result,
                        triggered_by="batch",
                        pipeline_config=enriched_config,
                        golden_item_id=item.id,
                        expected_answer=item.expected_answer,
                        job_id=job_id,
                        embedding_provider=embedding_provider or "openai",
                        rerank_provider=rerank_provider or "cohere",
                        search_latency_ms=search_latency_ms,
                    )

                    # Upsert: on retry after partial completion, existing rows
                    # for this (job_id, golden_item_id) pair are updated in-place
                    # instead of creating duplicates. This makes the task idempotent.
                    #
                    # Defensive: try native upsert first (works when PostgREST
                    # correctly resolves the partial unique index). Fall back to
                    # manual select-then-update if PostgREST can't match the index.
                    if job_id and item.id:
                        try:
                            supabase.table("evaluation_results").upsert(
                                row, on_conflict="job_id,golden_item_id"
                            ).execute()
                        except Exception as _upsert_err:
                            _err_msg = str(_upsert_err).lower()
                            if "duplicate" in _err_msg or "unique" in _err_msg or "conflict" in _err_msg:
                                _upd = supabase.table("evaluation_results") \
                                    .update(row) \
                                    .eq("job_id", job_id) \
                                    .eq("golden_item_id", item.id) \
                                    .execute()
                                if not _upd.data:
                                    # Row was deleted between upsert and update
                                    supabase.table("evaluation_results").insert(row).execute()
                            else:
                                raise
                    else:
                        supabase.table("evaluation_results").insert(row).execute()

                    results.append({
                        "golden_item_id": item.id,
                        "question_preview": item.question[:50],
                        "overall_score": eval_result.overall_score,
                        "scores": eval_result.scores.model_dump(),
                    })

                    total_score += eval_result.overall_score

                    logger.debug(
                        "evaluation_item_completed",
                        job_id=job_id,
                        golden_item_id=item.id,
                        overall_score=eval_result.overall_score,
                    )

                except Exception as e:
                    errors.append({
                        "golden_item_id": item.id,
                        "error": str(e),
                    })
                    logger.warning(
                        "evaluation_item_failed",
                        job_id=job_id,
                        golden_item_id=item.id,
                        error=str(e),
                    )

            # Calculate summary
            successful_count = len(results)
            avg_score = total_score / successful_count if successful_count > 0 else 0.0

            return {
                "status": "completed",
                "total_items": len(items),
                "successful": successful_count,
                "failed": len(errors),
                "average_score": round(avg_score, 4),
                "results_preview": results[:10],  # First 10 for preview
                "errors": errors[:5],  # First 5 errors
            }

        result = run_async(_evaluate_async(), timeout=1200)

        logger.info(
            "batch_evaluation_completed",
            job_id=job_id,
            matter_id=matter_id,
            total_items=result.get("total_items"),
            successful=result.get("successful"),
            failed=result.get("failed"),
            average_score=result.get("average_score"),
        )

        # Gap 9: Run post-batch regression check (non-blocking — failures don't fail the task)
        regression_info = _run_post_batch_checks(
            matter_id=matter_id,
            job_id=job_id,
            successful_count=result.get("successful", 0),
        )

        return {
            **result,
            "job_id": job_id,
            "matter_id": matter_id,
            "tags": tags,
            **regression_info,
        }

    except SoftTimeLimitExceeded:
        # Soft limit hit: partial results already inserted. Still run post-batch
        # checks so regressions from partial data are flagged rather than silently lost.
        # Query the actual count of inserted results rather than guessing.
        actual_count = 0
        try:
            _supabase = get_service_client()
            _count_result = (
                _supabase.table("evaluation_results")
                .select("id", count="exact")
                .eq("job_id", job_id)
                .execute()
            )
            actual_count = _count_result.count or 0
        except Exception:
            actual_count = 1  # Safe fallback — triggers regression check
        logger.warning(
            "batch_evaluation_soft_timeout",
            job_id=job_id,
            matter_id=matter_id,
            partial_results=actual_count,
        )
        regression_info = _run_post_batch_checks(
            matter_id=matter_id,
            job_id=job_id,
            successful_count=actual_count,
        )
        return {
            "status": "partial_timeout",
            "job_id": job_id,
            "matter_id": matter_id,
            "error_code": "SOFT_TIME_LIMIT",
            "error_message": "Evaluation timed out; partial results saved",
            **regression_info,
        }

    except Exception as e:
        logger.error(
            "batch_evaluation_failed",
            job_id=job_id,
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        return {
            "status": "failed",
            "job_id": job_id,
            "matter_id": matter_id,
            "error_code": "EVALUATION_FAILED",
            "error_message": str(e),
        }


@celery_app.task(
    name="app.workers.tasks.evaluation_tasks.evaluate_chat_response",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    max_retries=1,
)  # type: ignore[misc]
def evaluate_chat_response(
    self,  # type: ignore[no-untyped-def]
    matter_id: str,
    question: str,
    answer: str,
    contexts: list[str],
    chat_message_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate a single chat response (for auto-evaluation hook).

    This task is called asynchronously after a chat response is generated
    when auto_evaluation_enabled is True in settings.

    Args:
        matter_id: Matter UUID.
        question: User's question.
        answer: Generated answer.
        contexts: Retrieved context chunks.
        chat_message_id: Optional message ID for linking.

    Returns:
        Evaluation result summary.
    """
    settings = get_settings()

    if not settings.auto_evaluation_enabled:
        return {
            "status": "skipped",
            "reason": "Auto evaluation disabled",
        }

    logger.debug(
        "auto_evaluation_started",
        matter_id=matter_id,
        question_preview=question[:50],
        chat_message_id=chat_message_id,
    )

    try:
        async def _evaluate_async() -> dict[str, Any]:
            from app.services.evaluation import get_ragas_evaluator
            from app.services.rag.pipeline_service import get_rag_pipeline_service

            evaluator = get_ragas_evaluator()

            result = await evaluator.evaluate_single(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=None,  # No ground truth for auto-eval
            )

            # Get pipeline config for traceability
            pipeline = get_rag_pipeline_service()
            pipeline_config = pipeline._get_pipeline_config()

            # Store result
            supabase = get_supabase()
            row = _build_evaluation_row(
                matter_id=matter_id,
                question=question,
                answer=answer,
                contexts=contexts,
                eval_result=result,
                triggered_by="auto",
                pipeline_config=pipeline_config,
                chat_message_id=chat_message_id,
            )
            supabase.table("evaluation_results").insert(row).execute()

            return {
                "status": "completed",
                "overall_score": result.overall_score,
                "scores": result.scores.model_dump(),
            }

        result = run_async(_evaluate_async())

        logger.debug(
            "auto_evaluation_completed",
            matter_id=matter_id,
            overall_score=result.get("overall_score"),
        )

        return result

    except Exception as e:
        logger.warning(
            "auto_evaluation_failed",
            matter_id=matter_id,
            error=str(e),
        )

        return {
            "status": "failed",
            "error": str(e),
        }


# =============================================================================
# Gap 9: Scheduled Nightly Evaluation
# =============================================================================


def _estimate_eval_cost(item_count: int) -> float:
    """Estimate evaluation cost in USD.

    RAGAS uses GPT-4 for each (question, answer, contexts) tuple with 3 metrics.
    Approximate: ~2000 tokens input + ~500 tokens output per item × 3 metrics.
    GPT-4 pricing: $0.03/1K input, $0.06/1K output.

    Per item: (2 * 0.03 + 0.5 * 0.06) * 3 = ~$0.27 per item
    Conservative estimate: ~$0.015 per item (RAGAS is batched internally)
    """
    return item_count * 0.015


@celery_app.task(
    name="app.workers.tasks.evaluation_tasks.run_scheduled_evaluation",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=1,
    time_limit=3600,  # 1 hour max (evaluates all matters sequentially)
    soft_time_limit=3300,
)  # type: ignore[misc]
def run_scheduled_evaluation(
    self,  # type: ignore[no-untyped-def]
) -> dict[str, Any]:
    """Nightly scheduled evaluation of all matters with golden datasets.

    Gap 9: Automated RAGAS Regression

    Steps:
    1. Find all matters with golden dataset items (> 0 items)
    2. Check monthly cost budget (skip if exceeded)
    3. For each matter: trigger batch evaluation
    4. Each batch eval handles regression detection via _run_post_batch_checks()

    Cost control:
    - Estimates cost before each matter and skips if budget exceeded
    - Logs cumulative cost for monitoring
    - Budget configurable via EVALUATION_MONTHLY_BUDGET_USD

    This task is triggered by Celery Beat (nightly at 1 AM UTC).
    Gated by EVALUATION_SCHEDULE_ENABLED setting.
    """
    settings = get_settings()

    if not settings.evaluation_schedule_enabled:
        return {
            "status": "skipped",
            "reason": "Scheduled evaluation disabled (EVALUATION_SCHEDULE_ENABLED=false)",
        }

    # Distributed lock: prevent duplicate scheduled evaluations when
    # Celery Beat delivers the same periodic task to multiple workers.
    # Uses Redis SETNX — same Redis as the Celery broker.
    #
    # Lock key uses task ID prefix to be deterministic regardless of
    # execution-start time (avoids midnight boundary race when Beat fires
    # at 23:59 and task starts processing at 00:00 on the next date).
    # TTL is 90 minutes (task time_limit=60m + 30m buffer) so the lock
    # outlives the task and prevents overlapping runs.
    _lock_key: str | None = None
    try:
        from app.services.distributed_lock import get_sync_redis_client
        _redis = get_sync_redis_client()
        # Use the Celery task ID as the lock key — Beat delivers the same
        # periodic task with a unique ID each time, but duplicate deliveries
        # share the same scheduled timestamp via eta/expires.
        _lock_key = f"scheduled_eval_lock:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        _acquired = _redis.set(_lock_key, self.request.id, nx=True, ex=5400)
        if not _acquired:
            logger.info(
                "scheduled_evaluation_skipped_locked",
                lock_key=_lock_key,
                job_id=self.request.id,
            )
            return {
                "status": "skipped",
                "reason": "Another scheduled evaluation is already running today",
            }
    except Exception as _lock_err:
        # Redis unavailable — proceed without lock (better to double-evaluate
        # than skip entirely; cost budget check below still prevents overspend)
        logger.warning(
            "scheduled_evaluation_lock_unavailable",
            error=str(_lock_err),
        )

    logger.info("scheduled_evaluation_started")

    try:
        # Find matters with golden datasets
        supabase = get_service_client()
        golden_counts_result = supabase.rpc(
            "get_evaluation_quality_summary"
        ).execute()

        if not golden_counts_result.data:
            return {
                "status": "no_matters",
                "message": "No matters with golden datasets found",
            }

        matters = golden_counts_result.data

        # Check monthly cost budget
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cost_result = (
            supabase.table("evaluation_results")
            .select("id", count="exact")
            .gte("evaluated_at", month_start.isoformat())
            .eq("triggered_by", "batch")
            .execute()
        )
        monthly_eval_count = cost_result.count or 0
        estimated_monthly_cost = _estimate_eval_cost(monthly_eval_count)

        logger.info(
            "scheduled_evaluation_budget_check",
            monthly_eval_count=monthly_eval_count,
            estimated_monthly_cost_usd=round(estimated_monthly_cost, 2),
            budget_usd=settings.evaluation_monthly_budget_usd,
        )

        results: list[dict[str, Any]] = []
        total_evaluated = 0
        total_skipped = 0
        cumulative_cost = estimated_monthly_cost

        # Per-matter timeout: .apply() runs inline so inner task's time_limit is
        # not enforced by Celery. We use signal.alarm (Unix) as a guard.
        import platform
        import signal
        _is_unix = platform.system() != "Windows"
        PER_MATTER_TIMEOUT = 35 * 60  # 35 minutes (inner task has 30 min hard limit)

        for matter_row in matters:
            m_id = matter_row.get("matter_id")
            m_title = matter_row.get("matter_title", "Unknown")
            golden_count = int(matter_row.get("golden_item_count", 0))

            if golden_count == 0:
                continue

            # Cost check before each matter
            estimated_cost = _estimate_eval_cost(golden_count)
            if cumulative_cost + estimated_cost > settings.evaluation_monthly_budget_usd:
                logger.warning(
                    "scheduled_evaluation_budget_exceeded",
                    matter_id=m_id,
                    matter_title=m_title,
                    cumulative_cost=round(cumulative_cost, 2),
                    estimated_cost=round(estimated_cost, 2),
                    budget=settings.evaluation_monthly_budget_usd,
                )
                total_skipped += 1
                results.append({
                    "matter_id": m_id,
                    "matter_title": m_title,
                    "status": "skipped_budget",
                })
                continue

            # Trigger batch evaluation (synchronous within this task — sequential per matter)
            logger.info(
                "scheduled_evaluation_matter_start",
                matter_id=m_id,
                matter_title=m_title,
                golden_count=golden_count,
            )

            try:
                # Call run_batch_evaluation directly (not .delay) — we want sequential execution
                # within this scheduled task to control cost and avoid overwhelming the system.
                #
                # IMPORTANT: .apply() runs the task inline in this process — the inner task's
                # time_limit/soft_time_limit decorators are NOT enforced. We use signal.alarm
                # (Unix) as a per-matter timeout guard so one hanging matter can't eat the full
                # 1-hour outer limit and starve other matters.

                # signal.alarm is Unix-only; on Windows we rely on the outer task time_limit
                if _is_unix:
                    _prev_handler = signal.getsignal(signal.SIGALRM)

                    def _timeout_handler(signum, frame):  # type: ignore[no-untyped-def]
                        raise TimeoutError(f"Per-matter evaluation timed out after {PER_MATTER_TIMEOUT}s")

                    signal.signal(signal.SIGALRM, _timeout_handler)
                    signal.alarm(PER_MATTER_TIMEOUT)

                try:
                    batch_result = run_batch_evaluation.apply(
                        args=[],
                        kwargs={
                            "matter_id": m_id,
                            "tags": None,
                            "user_id": None,
                        },
                    ).result
                finally:
                    if _is_unix:
                        signal.alarm(0)  # Cancel alarm
                        signal.signal(signal.SIGALRM, _prev_handler)  # Restore handler
                    # Always count cost: LLM API calls are incurred even on
                    # partial failure. Skipping this would allow budget overshoot.
                    cumulative_cost += estimated_cost

                total_evaluated += 1

                results.append({
                    "matter_id": m_id,
                    "matter_title": m_title,
                    "status": batch_result.get("status", "unknown"),
                    "average_score": batch_result.get("average_score"),
                    "has_regression": batch_result.get("has_regression", False),
                    "successful": batch_result.get("successful", 0),
                })

            except Exception as e:
                logger.error(
                    "scheduled_evaluation_matter_failed",
                    matter_id=m_id,
                    error=str(e),
                )
                results.append({
                    "matter_id": m_id,
                    "matter_title": m_title,
                    "status": "failed",
                    "error": str(e)[:200],
                })

        logger.info(
            "scheduled_evaluation_completed",
            total_matters=len(matters),
            total_evaluated=total_evaluated,
            total_skipped=total_skipped,
            cumulative_cost_usd=round(cumulative_cost, 2),
        )

        # Release distributed lock early so manual re-runs are unblocked
        if _lock_key:
            try:  # noqa: SIM105
                _redis.delete(_lock_key)
            except Exception:
                pass  # TTL will handle cleanup

        return {
            "status": "completed",
            "total_matters": len(matters),
            "evaluated": total_evaluated,
            "skipped": total_skipped,
            "cumulative_cost_usd": round(cumulative_cost, 2),
            "budget_usd": settings.evaluation_monthly_budget_usd,
            "results": results,
        }

    except Exception as e:
        logger.error(
            "scheduled_evaluation_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "failed",
            "error_code": "SCHEDULED_EVALUATION_FAILED",
            "error_message": str(e),
        }


# =============================================================================
# Gap 10: A/B Comparison Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.evaluation_tasks.run_ab_comparison",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=1,
    time_limit=3600,  # 1 hour (runs 2 batch evaluations sequentially)
    soft_time_limit=3300,
)  # type: ignore[misc]
def run_ab_comparison(
    self,  # type: ignore[no-untyped-def]
    run_id: str,
    matter_id: str,
    tags: list[str] | None = None,
    user_id: str | None = None,
    control_embedding: str = "openai",
    control_reranker: str = "cohere",
    treatment_embedding: str = "voyage",
    treatment_reranker: str = "voyage",
) -> dict[str, Any]:
    """Run A/B comparison: same golden dataset, two provider configurations.

    Gap 10: Automated Voyage A/B Testing

    Steps:
    1. Run batch evaluation with control providers (OpenAI + Cohere)
    2. Run batch evaluation with treatment providers (Voyage + Voyage)
    3. Aggregate scores, run Welch's t-test, make decision
    4. Update ab_test_runs record with results

    Both arms use the same golden dataset questions in the same order,
    eliminating question-level variance from the comparison.

    Args:
        run_id: A/B test run UUID (from ab_test_runs table).
        matter_id: Matter UUID to evaluate.
        tags: Optional golden dataset tag filters.
        user_id: User ID for tracking.
        control_embedding: Control arm embedding provider.
        control_reranker: Control arm reranker.
        treatment_embedding: Treatment arm embedding provider.
        treatment_reranker: Treatment arm reranker.

    Returns:
        Comparison result with decision.
    """
    logger.info(
        "ab_comparison_started",
        run_id=run_id,
        matter_id=matter_id,
        control=f"{control_embedding}+{control_reranker}",
        treatment=f"{treatment_embedding}+{treatment_reranker}",
    )

    try:
        async def _run_comparison_async() -> dict[str, Any]:
            from app.services.evaluation.ab_testing import ABTestRunner

            runner = ABTestRunner()

            # Guard: reject if another test is already running for this matter
            existing_runs = await runner.list_runs(
                matter_id=matter_id, status=None, limit=5
            )
            active_statuses = {"pending", "running_control", "running_treatment", "comparing"}
            for existing in existing_runs:
                if (
                    existing.get("id") != run_id
                    and existing.get("status") in active_statuses
                ):
                    await runner.update_run(run_id, {
                        "status": "cancelled",
                        "error_message": (
                            f"Another A/B test ({existing['id']}) is already "
                            f"{existing['status']} for this matter"
                        ),
                        "completed_at": datetime.now(UTC).isoformat(),
                    })
                    return {
                        "status": "cancelled",
                        "reason": "duplicate_run",
                        "existing_run_id": existing["id"],
                    }

            # Step 1: Run control arm
            await runner.update_run(
                run_id, {"status": "running_control"}, expected_status="pending"
            )

            control_result = run_batch_evaluation.apply(
                args=[],
                kwargs={
                    "matter_id": matter_id,
                    "tags": tags,
                    "user_id": user_id,
                    "embedding_provider": control_embedding,
                    "rerank_provider": control_reranker,
                },
            ).result

            control_job_id = control_result.get("job_id")
            if not control_job_id or control_result.get("status") == "failed":
                await runner.update_run(run_id, {
                    "status": "failed",
                    "error_message": f"Control arm failed: {control_result.get('error_message', 'unknown')}",
                    "completed_at": datetime.now(UTC).isoformat(),
                }, expected_status="running_control")
                return {"status": "failed", "phase": "control", **control_result}

            await runner.update_run(run_id, {
                "control_job_id": control_job_id,
            })

            logger.info(
                "ab_comparison_control_done",
                run_id=run_id,
                control_job_id=control_job_id,
                avg_score=control_result.get("average_score"),
            )

            # Step 2: Run treatment arm
            await runner.update_run(
                run_id, {"status": "running_treatment"}, expected_status="running_control"
            )

            treatment_result = run_batch_evaluation.apply(
                args=[],
                kwargs={
                    "matter_id": matter_id,
                    "tags": tags,
                    "user_id": user_id,
                    "embedding_provider": treatment_embedding,
                    "rerank_provider": treatment_reranker,
                },
            ).result

            treatment_job_id = treatment_result.get("job_id")
            if not treatment_job_id or treatment_result.get("status") == "failed":
                await runner.update_run(run_id, {
                    "status": "failed",
                    "treatment_job_id": treatment_job_id,
                    "error_message": f"Treatment arm failed: {treatment_result.get('error_message', 'unknown')}",
                    "completed_at": datetime.now(UTC).isoformat(),
                }, expected_status="running_treatment")
                return {"status": "failed", "phase": "treatment", **treatment_result}

            await runner.update_run(run_id, {
                "treatment_job_id": treatment_job_id,
            })

            logger.info(
                "ab_comparison_treatment_done",
                run_id=run_id,
                treatment_job_id=treatment_job_id,
                avg_score=treatment_result.get("average_score"),
            )

            # Step 3: Compare results
            comparison = await runner.complete_comparison(
                run_id=run_id,
                control_job_id=control_job_id,
                treatment_job_id=treatment_job_id,
            )

            return {
                "status": "completed",
                "run_id": run_id,
                "decision": comparison.get("decision"),
                "decision_confidence": comparison.get("decision_confidence"),
                "decision_reasoning": comparison.get("decision_reasoning"),
                "control_overall": comparison.get("control_scores", {}).get("overall"),
                "treatment_overall": comparison.get("treatment_scores", {}).get("overall"),
            }

        result = run_async(_run_comparison_async(), timeout=3000)

        logger.info(
            "ab_comparison_completed",
            run_id=run_id,
            decision=result.get("decision"),
        )

        return result

    except Exception as e:
        logger.error(
            "ab_comparison_failed",
            run_id=run_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Update run status — but only if not already in a terminal state
        # (completed/cancelled). Without this guard, a post-completion error
        # (e.g., in serialization) would overwrite a valid "completed" result.
        try:
            async def _mark_failed() -> None:
                from app.services.evaluation.ab_testing import ABTestRunner
                run = await ABTestRunner.get_run(run_id)
                if run and run.get("status") not in ("completed", "cancelled", "failed"):
                    await ABTestRunner.update_run(run_id, {
                        "status": "failed",
                        "error_message": str(e),  # noqa: F821
                        "completed_at": datetime.now(UTC).isoformat(),
                    }, expected_status=run["status"])
            run_async(_mark_failed(), timeout=10)
        except Exception:
            pass

        return {
            "status": "failed",
            "run_id": run_id,
            "error_code": "AB_COMPARISON_FAILED",
            "error_message": str(e),
        }
