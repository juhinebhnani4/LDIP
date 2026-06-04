"""RAGAS evaluation service for RAG quality metrics.

Story: RAG Production Gaps - Feature 2: Evaluation Framework

Measures:
- Context Recall: How much relevant context was retrieved
- Faithfulness: How grounded is the answer in the context
- Answer Relevancy: How relevant is the answer to the question

CRITICAL: Uses GPT-4 for evaluation per LLM routing rules (ADR-002).
Evaluation is a high-stakes task requiring accurate assessment.

Implementation note: Uses RAGAS 0.4.x collections API with direct
``await metric.ascore()`` calls instead of the legacy ``evaluate()``
function. The legacy ``evaluate()`` calls ``asyncio.run()`` internally
which creates a nested event loop — this conflicts with both FastAPI's
uvloop (BUG-7) and Celery gevent workers where gevent monkey-patches
socket/ssl modules, breaking I/O in spawned threads (BUG-10b).
The collections API is purely async and avoids all of these issues.
"""

from __future__ import annotations

import math
import time
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.services.evaluation.models import (
    EvaluationRequest,
    EvaluationResult,
    MetricScores,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class EvaluationError(Exception):
    """Base exception for evaluation operations."""

    def __init__(
        self,
        message: str,
        code: str = "EVALUATION_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class RAGASNotConfiguredError(EvaluationError):
    """Raised when RAGAS dependencies are not available."""

    def __init__(self, message: str):
        super().__init__(message, code="RAGAS_NOT_CONFIGURED", is_retryable=False)


def _safe_score(val) -> float | None:  # noqa: ANN001
    """Convert a metric score to float, treating NaN as None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


# Faithfulness breaks the answer into atomic statements via an LLM call,
# then verifies each statement against contexts (second LLM call).
# Long answers (>2500 chars) produce too many statements, causing the
# statement-extraction LLM call to return malformed JSON that fails
# parsing after 3 retries.  Truncating to ~2500 chars keeps the
# statement count manageable while still evaluating the core answer.
_MAX_ANSWER_CHARS_FOR_FAITHFULNESS = 2500


class RAGASEvaluator:
    """Evaluate RAG quality using RAGAS metrics.

    This service provides quality assessment of RAG pipelines by measuring:
    - Context Recall: Did we retrieve all relevant information?
    - Faithfulness: Is the answer grounded in the retrieved context?
    - Answer Relevancy: Is the answer relevant to the question?

    Example:
        >>> evaluator = get_ragas_evaluator()
        >>> result = await evaluator.evaluate_single(
        ...     question="What is the penalty for Section 138?",
        ...     answer="The penalty includes imprisonment up to 2 years.",
        ...     contexts=["Section 138 of NI Act provides for..."],
        ...     ground_truth="Imprisonment up to 2 years or fine twice the cheque amount.",
        ... )
        >>> print(f"Faithfulness: {result.scores.faithfulness}")
    """

    def __init__(self) -> None:
        """Initialize RAGAS evaluator."""
        self._initialized = False
        settings = get_settings()
        self._llm_model = settings.openai_evaluation_model

    def _ensure_initialized(self) -> None:
        """Lazy initialization — verify RAGAS collections API is available."""
        if self._initialized:
            return

        try:
            from ragas.metrics.collections import (  # noqa: F401
                AnswerRelevancy,
                ContextRecall,
                Faithfulness,
            )

            self._initialized = True
            logger.info("ragas_evaluator_initialized", model=self._llm_model)

        except ImportError as e:
            logger.error("ragas_import_failed", error=str(e))
            raise RAGASNotConfiguredError(
                "RAGAS collections API not available. Requires ragas>=0.4.0"
            ) from e

    async def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> EvaluationResult:
        """Evaluate a single QA pair using RAGAS collections API.

        Uses ``await metric.ascore()`` directly instead of the legacy
        ``evaluate()`` wrapper. This is purely async and works correctly
        in both FastAPI (uvloop) and Celery gevent workers.

        Args:
            question: User's question.
            answer: Generated answer.
            contexts: Retrieved context chunks.
            ground_truth: Expected answer (optional, for context_recall).

        Returns:
            EvaluationResult with metric scores.

        Raises:
            EvaluationError: If evaluation fails.
        """
        self._ensure_initialized()

        start_time = time.time()

        logger.info(
            "evaluation_start",
            question_length=len(question),
            answer_length=len(answer),
            context_count=len(contexts),
            has_ground_truth=ground_truth is not None,
        )

        try:
            from openai import AsyncOpenAI
            from ragas.embeddings.base import embedding_factory
            from ragas.llms import llm_factory
            from ragas.metrics.collections import (
                AnswerRelevancy,
                ContextRecall,
                Faithfulness,
            )

            # Create RAGAS-native LLM and embeddings (not LangChain wrappers).
            # The collections API requires InstructorBaseRagasLLM, not
            # LangchainLLMWrapper.
            client = AsyncOpenAI()
            # max_tokens=4096: RAGAS defaults to 1024 which is too low
            # for Faithfulness NLI verdicts on long answers (each verdict
            # is ~200 tokens; 15+ statements → 3000+ output tokens).
            llm = llm_factory(self._llm_model, client=client, max_tokens=4096)
            embeddings = embedding_factory(
                "openai",
                model="text-embedding-3-small",
                client=client,
            )

            # Score each metric individually with await — no evaluate(),
            # no asyncio.run(), no thread hacks.
            faithfulness_score = None
            answer_relevancy_score = None
            context_recall_score = None

            # --- Faithfulness ---
            # Truncate long answers to prevent statement-extraction JSON
            # parse failures (see _MAX_ANSWER_CHARS_FOR_FAITHFULNESS).
            faith_answer = answer
            if len(answer) > _MAX_ANSWER_CHARS_FOR_FAITHFULNESS:
                faith_answer = answer[:_MAX_ANSWER_CHARS_FOR_FAITHFULNESS]
                logger.info(
                    "faithfulness_answer_truncated",
                    original_len=len(answer),
                    truncated_len=len(faith_answer),
                )
            try:
                faith_metric = Faithfulness(llm=llm)
                faith_result = await faith_metric.ascore(
                    user_input=question,
                    response=faith_answer,
                    retrieved_contexts=contexts,
                )
                faithfulness_score = _safe_score(faith_result.value)
            except Exception as e:
                logger.warning(
                    "metric_faithfulness_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    answer_length=len(faith_answer),
                )

            # --- Answer Relevancy ---
            try:
                relevancy_metric = AnswerRelevancy(
                    llm=llm,
                    embeddings=embeddings,
                )
                relevancy_result = await relevancy_metric.ascore(
                    user_input=question,
                    response=answer,
                )
                answer_relevancy_score = _safe_score(relevancy_result.value)
            except Exception as e:
                logger.warning(
                    "metric_answer_relevancy_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # --- Context Recall (requires ground_truth) ---
            if ground_truth:
                try:
                    recall_metric = ContextRecall(llm=llm)
                    recall_result = await recall_metric.ascore(
                        user_input=question,
                        retrieved_contexts=contexts,
                        reference=ground_truth,
                    )
                    context_recall_score = _safe_score(recall_result.value)
                except Exception as e:
                    logger.warning(
                        "metric_context_recall_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

            scores = MetricScores(
                context_recall=context_recall_score,
                faithfulness=faithfulness_score,
                answer_relevancy=answer_relevancy_score,
            )

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "evaluation_complete",
                faithfulness=scores.faithfulness,
                answer_relevancy=scores.answer_relevancy,
                context_recall=scores.context_recall,
                overall_score=scores.overall,
                processing_time_ms=processing_time,
            )

            return EvaluationResult(
                question=question,
                scores=scores,
                overall_score=scores.overall,
                evaluated_at=datetime.utcnow(),
            )

        except RAGASNotConfiguredError:
            raise

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)

            logger.error(
                "evaluation_failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time,
            )

            raise EvaluationError(
                f"Evaluation failed: {e}",
                code="EVALUATION_FAILED",
            ) from e

    async def evaluate_batch(
        self,
        items: list[EvaluationRequest],
    ) -> list[EvaluationResult]:
        """Evaluate multiple QA pairs.

        Useful for evaluating a golden dataset.

        Args:
            items: List of EvaluationRequest objects.

        Returns:
            List of EvaluationResult objects.
        """
        results: list[EvaluationResult] = []

        for idx, item in enumerate(items):
            try:
                result = await self.evaluate_single(
                    question=item.question,
                    answer=item.answer,
                    contexts=item.contexts,
                    ground_truth=item.ground_truth,
                )
                results.append(result)

                logger.debug(
                    "batch_evaluation_item_complete",
                    item_index=idx,
                    overall_score=result.overall_score,
                )

            except Exception as e:
                logger.warning(
                    "batch_evaluation_item_failed",
                    item_index=idx,
                    error=str(e),
                )
                # Add a failed result with zero scores
                results.append(
                    EvaluationResult(
                        question=item.question,
                        scores=MetricScores(),
                        overall_score=0.0,
                        evaluated_at=datetime.utcnow(),
                    )
                )

        return results


@lru_cache(maxsize=1)
def get_ragas_evaluator() -> RAGASEvaluator:
    """Get singleton RAGAS evaluator instance.

    Returns:
        RAGASEvaluator instance.
    """
    return RAGASEvaluator()
