"""Celery tasks for RAG evaluation.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Runs batch evaluation of golden dataset items using RAGAS metrics.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.services.supabase.client import get_supabase_client as get_supabase

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class EvaluationTaskError(Exception):
    """Error in evaluation task."""

    def __init__(self, message: str, code: str = "EVALUATION_TASK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


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

    Evaluates all golden dataset items (optionally filtered by tags) using
    the RAG pipeline and RAGAS metrics.

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
        # Run async evaluation in sync context
        async def _evaluate_async() -> dict[str, Any]:
            from app.services.evaluation import get_ragas_evaluator
            from app.services.evaluation.golden_dataset import GoldenDatasetService
            from app.services.rag.chat_service import get_chat_service

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
            chat_service = get_chat_service()
            supabase = get_supabase()

            results = []
            errors = []
            total_score = 0.0

            for item in items:
                try:
                    # Get RAG response for the question
                    rag_response = await chat_service.get_rag_response(
                        matter_id=matter_id,
                        question=item.question,
                        user_id=user_id,
                    )

                    # Extract answer and contexts
                    answer = rag_response.get("answer", "")
                    contexts = [
                        chunk.get("content", "")
                        for chunk in rag_response.get("chunks", [])
                    ]

                    if not contexts:
                        contexts = ["No context retrieved"]

                    # Evaluate using RAGAS
                    eval_result = await evaluator.evaluate_single(
                        question=item.question,
                        answer=answer,
                        contexts=contexts,
                        ground_truth=item.expected_answer,
                    )

                    # Store result in database
                    result_data = {
                        "matter_id": matter_id,
                        "golden_item_id": item.id,
                        "question": item.question,
                        "generated_answer": answer,
                        "expected_answer": item.expected_answer,
                        "contexts": contexts,
                        "scores": eval_result.scores.model_dump(),
                        "overall_score": eval_result.overall_score,
                        "latency_ms": eval_result.latency_ms,
                        "evaluated_at": datetime.now(UTC).isoformat(),
                        "job_id": job_id,
                    }

                    supabase.table("evaluation_results").insert(result_data).execute()

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

        result = asyncio.run(_evaluate_async())

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

            evaluator = get_ragas_evaluator()

            result = await evaluator.evaluate_single(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=None,  # No ground truth for auto-eval
            )

            # Store result
            supabase = get_supabase()
            supabase.table("evaluation_results").insert({
                "matter_id": matter_id,
                "question": question,
                "generated_answer": answer,
                "contexts": contexts,
                "scores": result.scores.model_dump(),
                "overall_score": result.overall_score,
                "latency_ms": result.latency_ms,
                "evaluated_at": datetime.now(UTC).isoformat(),
                "chat_message_id": chat_message_id,
                "is_auto_evaluation": True,
            }).execute()

            return {
                "status": "completed",
                "overall_score": result.overall_score,
                "scores": result.scores.model_dump(),
            }

        result = asyncio.run(_evaluate_async())

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
