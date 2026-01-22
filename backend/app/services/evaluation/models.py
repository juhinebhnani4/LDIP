"""Evaluation data models.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Pydantic models for RAGAS evaluation.
"""

from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class MetricScores(BaseModel):
    """RAGAS metric scores."""

    context_recall: float | None = Field(
        None, ge=0.0, le=1.0, description="How much relevant context was retrieved"
    )
    faithfulness: float | None = Field(
        None, ge=0.0, le=1.0, description="How grounded is the answer in context"
    )
    answer_relevancy: float | None = Field(
        None, ge=0.0, le=1.0, description="How relevant is answer to question"
    )

    @computed_field
    @property
    def overall(self) -> float:
        """Calculate overall score (average of available metrics)."""
        scores = [
            s
            for s in [self.faithfulness, self.answer_relevancy, self.context_recall]
            if s is not None
        ]
        return sum(scores) / len(scores) if scores else 0.0

    @computed_field
    @property
    def metrics_count(self) -> int:
        """Count of available metrics."""
        return sum(
            1
            for s in [self.faithfulness, self.answer_relevancy, self.context_recall]
            if s is not None
        )


class EvaluationRequest(BaseModel):
    """Request to evaluate a QA pair."""

    question: str = Field(..., description="User's question")
    answer: str = Field(..., description="Generated answer")
    contexts: list[str] = Field(..., description="Retrieved context chunks")
    ground_truth: str | None = Field(
        None, description="Expected answer (optional, required for context_recall)"
    )


class EvaluationResult(BaseModel):
    """Result of evaluation."""

    question: str = Field(..., description="Evaluated question")
    scores: MetricScores = Field(..., description="RAGAS metric scores")
    overall_score: float = Field(..., description="Overall quality score")
    evaluated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Evaluation timestamp"
    )


class GoldenDatasetItem(BaseModel):
    """A single item in the golden dataset for evaluation."""

    id: str | None = Field(None, description="Item UUID (set after creation)")
    matter_id: str = Field(..., description="Matter UUID for isolation")
    question: str = Field(..., description="Test question")
    expected_answer: str = Field(..., description="Ground truth answer")
    relevant_chunk_ids: list[str] = Field(
        default_factory=list, description="UUIDs of relevant chunks"
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags for filtering (e.g., 'citation', 'timeline')"
    )
    created_by: str | None = Field(None, description="User who created this item")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")


class BatchEvaluationResult(BaseModel):
    """Result of batch evaluation."""

    matter_id: str = Field(..., description="Matter that was evaluated")
    total_items: int = Field(..., description="Total golden items evaluated")
    successful: int = Field(..., description="Successfully evaluated count")
    failed: int = Field(..., description="Failed evaluation count")
    avg_overall_score: float = Field(..., description="Average overall score")
    avg_faithfulness: float | None = Field(None, description="Average faithfulness")
    avg_relevancy: float | None = Field(None, description="Average answer relevancy")
    avg_recall: float | None = Field(None, description="Average context recall")
    triggered_by: str = Field(..., description="Who/what triggered evaluation")
    evaluated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Evaluation timestamp"
    )
