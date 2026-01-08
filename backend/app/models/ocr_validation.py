"""OCR validation models for post-processing and correction.

Models for Gemini-based OCR validation including low-confidence word extraction,
validation results, and human review queue management.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """OCR validation status for documents.

    States:
    - pending_validation: Awaiting validation processing
    - validated: Validation completed successfully
    - requires_human_review: Contains words requiring human review
    """

    PENDING = "pending"
    VALIDATED = "validated"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class CorrectionType(str, Enum):
    """Type of correction applied to OCR text.

    Types:
    - pattern: Deterministic regex pattern correction
    - gemini: LLM-based correction via Gemini
    - human: Human-reviewed and corrected
    """

    PATTERN = "pattern"
    GEMINI = "gemini"
    HUMAN = "human"


class HumanReviewStatus(str, Enum):
    """Status of human review items.

    States:
    - pending: Awaiting human review
    - completed: Review completed with correction
    - skipped: Reviewer chose to skip/accept original
    """

    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class LowConfidenceWord(BaseModel):
    """A word with low OCR confidence requiring validation.

    Contains the word text, confidence score, location information,
    and surrounding context for validation.
    """

    bbox_id: str = Field(..., description="UUID of the bounding box")
    text: str = Field(..., description="OCR-extracted text content")
    confidence: float = Field(..., ge=0, le=1, description="OCR confidence score (0-1)")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    context_before: str = Field(
        default="", description="Text before this word (up to 50 chars)"
    )
    context_after: str = Field(
        default="", description="Text after this word (up to 50 chars)"
    )
    x: float = Field(..., ge=0, le=100, description="X coordinate (percentage)")
    y: float = Field(..., ge=0, le=100, description="Y coordinate (percentage)")
    width: float = Field(..., ge=0, le=100, description="Width (percentage)")
    height: float = Field(..., ge=0, le=100, description="Height (percentage)")


class ValidationResult(BaseModel):
    """Result of validating a single word.

    Contains original and corrected text, confidence scores,
    and the type of correction applied.
    """

    bbox_id: str = Field(..., description="UUID of the bounding box")
    original: str = Field(..., description="Original OCR text")
    corrected: str = Field(..., description="Corrected text (may be same as original)")
    old_confidence: float = Field(..., ge=0, le=1, description="Original confidence")
    new_confidence: float = Field(..., ge=0, le=1, description="New confidence after validation")
    correction_type: CorrectionType | None = Field(
        None, description="Type of correction applied (None if no change)"
    )
    reasoning: str | None = Field(
        None, description="Explanation for the correction"
    )
    was_corrected: bool = Field(
        default=False, description="Whether the text was actually changed"
    )


class ValidationLogEntry(BaseModel):
    """Log entry for a validation correction.

    Used for audit trail and tracking all corrections made.
    """

    id: str | None = Field(None, description="UUID of the log entry")
    document_id: str = Field(..., description="UUID of the document")
    bbox_id: str | None = Field(None, description="UUID of the bounding box")
    original_text: str = Field(..., description="Original OCR text")
    corrected_text: str = Field(..., description="Corrected text")
    old_confidence: float | None = Field(None, ge=0, le=1, description="Original confidence")
    new_confidence: float | None = Field(None, ge=0, le=1, description="New confidence")
    validation_type: CorrectionType = Field(..., description="Type of validation")
    reasoning: str | None = Field(None, description="Explanation for correction")
    created_at: datetime | None = Field(None, description="When the correction was made")


class HumanReviewItem(BaseModel):
    """Item in the human review queue.

    Represents a word that requires human review due to very low confidence.
    """

    id: str | None = Field(None, description="UUID of the review item")
    document_id: str = Field(..., description="UUID of the document")
    matter_id: str = Field(..., description="UUID of the matter")
    bbox_id: str | None = Field(None, description="UUID of the bounding box")
    original_text: str = Field(..., description="Original OCR text")
    context_before: str | None = Field(None, description="Text before (up to 50 chars)")
    context_after: str | None = Field(None, description="Text after (up to 50 chars)")
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    status: HumanReviewStatus = Field(
        default=HumanReviewStatus.PENDING, description="Review status"
    )
    corrected_text: str | None = Field(None, description="Human-provided correction")
    reviewed_by: str | None = Field(None, description="UUID of reviewing user")
    reviewed_at: datetime | None = Field(None, description="When review was completed")
    created_at: datetime | None = Field(None, description="When item was queued")


class GeminiValidationRequest(BaseModel):
    """Request payload for Gemini batch validation."""

    words: list[LowConfidenceWord] = Field(
        ..., description="Words to validate", max_length=20
    )
    document_type: str | None = Field(
        None, description="Type of document (petition, appeal, etc.)"
    )


class GeminiValidationResponse(BaseModel):
    """Response from Gemini validation."""

    results: list[ValidationResult] = Field(..., description="Validation results")
    processing_time_ms: int | None = Field(None, description="Processing time in ms")
    tokens_used: int | None = Field(None, description="Tokens consumed")


class DocumentValidationSummary(BaseModel):
    """Summary of validation for a document."""

    document_id: str = Field(..., description="UUID of the document")
    validation_status: ValidationStatus = Field(..., description="Overall status")
    total_words_validated: int = Field(0, ge=0, description="Total words processed")
    pattern_corrections: int = Field(0, ge=0, description="Pattern-based corrections")
    gemini_corrections: int = Field(0, ge=0, description="Gemini corrections")
    human_review_pending: int = Field(0, ge=0, description="Items awaiting human review")
    human_review_completed: int = Field(0, ge=0, description="Human reviews completed")
    average_confidence_before: float | None = Field(
        None, ge=0, le=1, description="Average confidence before validation"
    )
    average_confidence_after: float | None = Field(
        None, ge=0, le=1, description="Average confidence after validation"
    )
