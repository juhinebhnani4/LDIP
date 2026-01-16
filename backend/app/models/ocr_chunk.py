"""OCR chunk models for large document parallel processing.

Models for tracking OCR chunk processing state, supporting large PDF
processing via chunked parallel OCR (Epic 15).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChunkStatus(str, Enum):
    """OCR chunk processing status.

    States:
    - pending: Awaiting OCR processing
    - processing: OCR in progress
    - completed: Successfully processed
    - failed: Processing failed
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid status transitions for state machine validation
VALID_STATUS_TRANSITIONS: dict[ChunkStatus, set[ChunkStatus]] = {
    ChunkStatus.PENDING: {ChunkStatus.PROCESSING},
    ChunkStatus.PROCESSING: {ChunkStatus.COMPLETED, ChunkStatus.FAILED},
    ChunkStatus.FAILED: {ChunkStatus.PENDING},  # Retry resets to pending
    ChunkStatus.COMPLETED: set(),  # Terminal state
}


class DocumentOCRChunk(BaseModel):
    """OCR chunk record from database.

    Represents a chunk of pages from a document being processed
    by the parallel OCR pipeline.
    """

    id: str = Field(..., alias="id")
    matter_id: str = Field(..., alias="matterId")
    document_id: str = Field(..., alias="documentId")
    chunk_index: int = Field(..., ge=0, alias="chunkIndex")
    page_start: int = Field(..., ge=1, alias="pageStart")
    page_end: int = Field(..., ge=1, alias="pageEnd")
    status: ChunkStatus
    error_message: str | None = Field(None, alias="errorMessage")
    result_storage_path: str | None = Field(None, alias="resultStoragePath")
    result_checksum: str | None = Field(None, alias="resultChecksum")
    processing_started_at: datetime | None = Field(None, alias="processingStartedAt")
    processing_completed_at: datetime | None = Field(None, alias="processingCompletedAt")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = {"populate_by_name": True}


class DocumentOCRChunkCreate(BaseModel):
    """Input model for creating a new OCR chunk via API.

    Used by API routes for request validation. The service layer
    uses explicit parameters for internal calls.
    """

    document_id: str = Field(..., alias="documentId")
    matter_id: str = Field(..., alias="matterId")
    chunk_index: int = Field(..., ge=0, alias="chunkIndex")
    page_start: int = Field(..., ge=1, alias="pageStart")
    page_end: int = Field(..., ge=1, alias="pageEnd")

    model_config = {"populate_by_name": True}


class DocumentOCRChunkUpdate(BaseModel):
    """Input model for updating OCR chunk status via API.

    Used by API routes for request validation. Supports partial updates.
    The service layer uses dedicated methods (update_status, update_result).
    """

    status: ChunkStatus | None = None
    error_message: str | None = Field(None, alias="errorMessage")
    result_storage_path: str | None = Field(None, alias="resultStoragePath")
    result_checksum: str | None = Field(None, alias="resultChecksum")

    model_config = {"populate_by_name": True}


class ChunkProgress(BaseModel):
    """Summary of chunk processing progress for a document.

    Provides aggregated status counts for progress tracking.
    """

    total: int = Field(..., ge=0, description="Total number of chunks")
    pending: int = Field(..., ge=0, description="Chunks awaiting processing")
    processing: int = Field(..., ge=0, description="Chunks currently processing")
    completed: int = Field(..., ge=0, description="Successfully completed chunks")
    failed: int = Field(..., ge=0, description="Failed chunks")

    @property
    def progress_pct(self) -> int:
        """Calculate completion percentage."""
        if self.total == 0:
            return 100
        return int((self.completed / self.total) * 100)

    @property
    def is_complete(self) -> bool:
        """Check if all chunks are processed (completed or failed)."""
        return self.pending == 0 and self.processing == 0

    @property
    def has_failures(self) -> bool:
        """Check if any chunks failed."""
        return self.failed > 0


class ChunkSpec(BaseModel):
    """Specification for a single chunk in batch creation.

    Used with create_chunks_for_document to define multiple chunks.
    """

    chunk_index: int = Field(..., ge=0, alias="chunkIndex")
    page_start: int = Field(..., ge=1, alias="pageStart")
    page_end: int = Field(..., ge=1, alias="pageEnd")

    model_config = {"populate_by_name": True}
