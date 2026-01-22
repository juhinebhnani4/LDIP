"""RAGAS evaluation service for RAG quality metrics.

Story: RAG Production Gaps - Feature 2: Evaluation Framework

Measures:
- Context Recall: How much relevant context was retrieved
- Faithfulness: How grounded is the answer in the context
- Answer Relevancy: How relevant is the answer to the question

CRITICAL: Uses GPT-4 for evaluation per LLM routing rules (ADR-002).
Evaluation is a high-stakes task requiring accurate assessment.
"""

from __future__ import annotations

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
        self._metrics: list = []
        settings = get_settings()
        self._llm_model = settings.openai_evaluation_model

    def _ensure_initialized(self) -> None:
        """Lazy initialization of RAGAS components."""
        if self._initialized:
            return

        try:
            from ragas.metrics import (
                answer_relevancy,
                context_recall,
                faithfulness,
            )

            self._metrics = [context_recall, faithfulness, answer_relevancy]
            self._initialized = True
            logger.info("ragas_evaluator_initialized", model=self._llm_model)

        except ImportError as e:
            logger.error("ragas_import_failed", error=str(e))
            raise RAGASNotConfiguredError(
                "RAGAS not installed. Run: pip install ragas"
            ) from e

    async def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> EvaluationResult:
        """Evaluate a single QA pair.

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
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import answer_relevancy, context_recall, faithfulness

            # Prepare dataset for RAGAS
            data = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            }
            if ground_truth:
                data["ground_truth"] = [ground_truth]

            dataset = Dataset.from_dict(data)

            # Select metrics based on available data
            # context_recall requires ground_truth
            metrics = (
                [context_recall, faithfulness, answer_relevancy]
                if ground_truth
                else [faithfulness, answer_relevancy]
            )

            # Run evaluation
            result = evaluate(
                dataset,
                metrics=metrics,
            )

            # Extract scores
            scores = MetricScores(
                context_recall=result.get("context_recall"),
                faithfulness=result.get("faithfulness"),
                answer_relevancy=result.get("answer_relevancy"),
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
