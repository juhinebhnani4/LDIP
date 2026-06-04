"""Evaluation framework using RAGAS.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Provides metrics for measuring RAG quality including:
- Context Recall
- Faithfulness
- Answer Relevancy
"""

from app.services.evaluation.baseline_service import BaselineService
from app.services.evaluation.golden_dataset import GoldenDatasetService
from app.services.evaluation.models import (
    EvaluationRequest,
    EvaluationResult,
    GoldenDatasetItem,
    MetricScores,
)
from app.services.evaluation.ragas_evaluator import (
    RAGASEvaluator,
    get_ragas_evaluator,
)
from app.services.evaluation.regression_detector import (
    RegressionReport,
    detect_regression,
)

__all__ = [
    "RAGASEvaluator",
    "get_ragas_evaluator",
    "EvaluationRequest",
    "EvaluationResult",
    "MetricScores",
    "GoldenDatasetItem",
    "GoldenDatasetService",
    "BaselineService",
    "detect_regression",
    "RegressionReport",
]
