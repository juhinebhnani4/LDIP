"""Document models for file upload and storage."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Document type classification.

    Types:
    - case_file: Primary case documents (petitions, affidavits, etc.)
    - act: Legal acts and statutes for citation verification
    - annexure: Supporting documents and exhibits
    - other: Miscellaneous documents
    """

    CASE_FILE = "case_file"
    ACT = "act"
    ANNEXURE = "annexure"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """Processing status for documents.

    States:
    - pending: Uploaded, awaiting OCR processing
    - processing: OCR/extraction in progress
    - completed: Successfully processed
    - failed: Processing failed
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentBase(BaseModel):
    """Base document properties."""

    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    document_type: DocumentType = Field(
        default=DocumentType.CASE_FILE,
        description="Document classification type"
    )


class DocumentCreate(DocumentBase):
    """Internal model for creating a document record."""

    matter_id: str = Field(..., description="Matter UUID this document belongs to")
    storage_path: str = Field(..., description="Supabase Storage path")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    is_reference_material: bool = Field(
        default=False,
        description="True for Acts and reference docs"
    )
    uploaded_by: str = Field(..., description="User UUID who uploaded the document")


class Document(DocumentBase):
    """Complete document model returned from API."""

    id: str = Field(..., description="Document UUID")
    matter_id: str = Field(..., description="Matter UUID")
    storage_path: str = Field(..., description="Supabase Storage path")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    page_count: int | None = Field(None, description="Number of pages (null until OCR)")
    is_reference_material: bool = Field(
        default=False,
        description="True for Acts and reference docs"
    )
    uploaded_by: str = Field(..., description="User UUID who uploaded")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        description="Processing status"
    )
    processing_started_at: datetime | None = Field(
        None,
        description="When OCR processing started"
    )
    processing_completed_at: datetime | None = Field(
        None,
        description="When OCR processing completed"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class UploadedDocument(BaseModel):
    """Simplified document model for upload response."""

    document_id: str = Field(..., description="Document UUID")
    filename: str = Field(..., description="Original filename")
    storage_path: str = Field(..., description="Supabase Storage path")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    document_type: DocumentType = Field(..., description="Document classification")
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        description="Processing status"
    )


# Response wrapper models following API response format
class DocumentResponse(BaseModel):
    """API response wrapper for a single document."""

    data: UploadedDocument


class DocumentListResponse(BaseModel):
    """API response wrapper for multiple documents."""

    data: list[UploadedDocument]


class BulkUploadResponse(BaseModel):
    """API response for bulk upload (ZIP extraction)."""

    data: list[UploadedDocument]
    meta: dict = Field(
        default_factory=dict,
        description="Additional metadata about the upload"
    )


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class DocumentListItem(BaseModel):
    """Document item for list responses (subset of full Document)."""

    id: str = Field(..., description="Document UUID")
    matter_id: str = Field(..., description="Matter UUID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    document_type: DocumentType = Field(..., description="Document classification")
    is_reference_material: bool = Field(..., description="True for Acts and reference docs")
    status: DocumentStatus = Field(..., description="Processing status")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    uploaded_by: str = Field(..., description="User UUID who uploaded")


class DocumentListResponseWithPagination(BaseModel):
    """API response for paginated document list."""

    data: list[DocumentListItem]
    meta: PaginationMeta


class DocumentDetailResponse(BaseModel):
    """API response for document detail with signed URL."""

    data: Document


class DocumentUpdate(BaseModel):
    """Model for updating document metadata."""

    document_type: DocumentType | None = Field(
        None,
        description="New document classification type"
    )
    is_reference_material: bool | None = Field(
        None,
        description="Override reference material flag (auto-set for acts)"
    )


class BulkDocumentUpdate(BaseModel):
    """Model for bulk document type assignment."""

    document_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of document UUIDs to update"
    )
    document_type: DocumentType = Field(
        ...,
        description="Document type to assign to all documents"
    )


class BulkUpdateResponse(BaseModel):
    """Response for bulk update operation."""

    data: dict = Field(
        default_factory=dict,
        description="Update result details"
    )
