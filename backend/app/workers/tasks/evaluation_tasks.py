"""Celery tasks for RAG evaluation.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Runs batch evaluation of golden dataset items using RAGAS metrics.

Fix B1/B2/B3 (2026-02-16): Fixed column mismatches, replaced non-existent
get_chat_service with RAGPipelineService, removed latency_ms references,
added metric_scores JSONB + pipeline_config JSONB for extensibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.workers.celery import celery_app
from app.core.config import get_settings
from app.services.supabase.client import get_supabase_client as get_supabase
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)


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
) -> dict[str, Any]:
    """Build a row dict matching the evaluation_results schema exactly.

    Single source of truth for column names. If the schema changes,
    update this function only.

    Schema columns (20260122000002 + 20260216000001):
        id (auto), matter_id, golden_item_id, question, answer, contexts,
        context_recall, faithfulness, answer_relevancy, overall_score,
        evaluated_at, triggered_by, expected_answer, job_id,
        chat_message_id, metric_scores, pipeline_config
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

    return row


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
) -> dict[str, Any]:
    """Run batch evaluation of golden dataset items.

    For each golden item:
    1. Run the question through the RAG pipeline (same pipeline as chat)
    2. Compare RAG answer against expected answer using RAGAS metrics
    3. Store result in evaluation_results table

    Args:
        matter_id: Matter UUID to evaluate.
        tags: Optional tags to filter golden items.
        user_id: Optional user ID for tracking.

    Returns:
        Task result with evaluation summary.
    """
    settings = get_settings()
    job_id = self.request.id

    logger.info(
        "batch_evaluation_started",
        job_id=job_id,
        matter_id=matter_id,
        tags=tags,
        user_id=user_id,
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

            results = []
            errors = []
            total_score = 0.0

            for item in items:
                try:
                    # Step 1: Run question through RAG pipeline
                    rag_result = await pipeline.query(
                        matter_id=matter_id,
                        question=item.question,
                        user_id=user_id,
                        skip_cache=True,
                    )

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
                    row = _build_evaluation_row(
                        matter_id=matter_id,
                        question=item.question,
                        answer=answer,
                        contexts=contexts,
                        eval_result=eval_result,
                        triggered_by="batch",
                        pipeline_config=rag_result.pipeline_config,
                        golden_item_id=item.id,
                        expected_answer=item.expected_answer,
                        job_id=job_id,
                    )
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

        return {
            **result,
            "job_id": job_id,
            "matter_id": matter_id,
            "tags": tags,
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
