"""Evaluation API Pydantic models.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
API request/response models for evaluation endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================


class EvaluateRequest(BaseModel):
    """Request to evaluate a single QA pair."""

    question: str = Field(..., min_length=1, description="User's question")
    answer: str = Field(..., min_length=1, description="Generated answer")
    contexts: list[str] = Field(..., min_length=1, description="Retrieved context chunks")
    ground_truth: str | None = Field(
        None, description="Expected answer (optional, enables context_recall)"
    )
    save_result: bool = Field(
        False, description="Whether to save result to evaluation_results table"
    )


class BatchEvaluateRequest(BaseModel):
    """Request to trigger batch evaluation of golden dataset."""

    tags: list[str] | None = Field(
        None, description="Tags to filter golden items (evaluate only matching)"
    )


class AddGoldenItemRequest(BaseModel):
    """Request to add a golden dataset item."""

    question: str = Field(..., min_length=1, description="Test question")
    expected_answer: str = Field(..., min_length=1, description="Ground truth answer")
    relevant_chunk_ids: list[str] | None = Field(
        None, description="UUIDs of relevant chunks"
    )
    tags: list[str] | None = Field(
        None, description="Tags for filtering (citation, timeline, etc.)"
    )


class UpdateGoldenItemRequest(BaseModel):
    """Request to update a golden dataset item."""

    question: str | None = Field(None, min_length=1, description="Updated question")
    expected_answer: str | None = Field(None, min_length=1, description="Updated answer")
    relevant_chunk_ids: list[str] | None = Field(None, description="Updated chunk IDs")
    tags: list[str] | None = Field(None, description="Updated tags")


# =============================================================================
# Response Models
# =============================================================================


class MetricScoresData(BaseModel):
    """RAGAS metric scores for API response."""

    context_recall: float | None = Field(None, description="Context recall (0-1)")
    faithfulness: float | None = Field(None, description="Faithfulness (0-1)")
    answer_relevancy: float | None = Field(None, description="Answer relevancy (0-1)")
    overall: float = Field(..., description="Overall score (average)")


class EvaluationResultData(BaseModel):
    """Single evaluation result for API response."""

    question: str
    scores: MetricScoresData
    overall_score: float
    evaluated_at: datetime


class EvaluateResponse(BaseModel):
    """Response for single evaluation."""

    data: Any = Field(..., description="Evaluation result")


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int = Field(..., description="Total items")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total pages")


class EvaluationResultsResponse(BaseModel):
    """Response for evaluation results list."""

    data: list[dict[str, Any]] = Field(..., description="Evaluation results")
    meta: PaginationMeta = Field(..., description="Pagination info")


class GoldenDatasetResponse(BaseModel):
    """Response for golden dataset list."""

    data: list[dict[str, Any]] = Field(..., description="Golden dataset items")
    meta: PaginationMeta = Field(..., description="Pagination info")


class GoldenItemResponse(BaseModel):
    """Response for single golden dataset item."""

    data: dict[str, Any] = Field(..., description="Golden item data")
