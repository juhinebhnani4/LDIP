"""Document models for file upload and storage."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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


class DocumentSource(str, Enum):
    """Document source indicating how the document was added.

    Sources:
    - user_upload: Manually uploaded by a user
    - auto_fetched: Automatically fetched from India Code
    - system: System-generated or internal documents
    """

    USER_UPLOAD = "user_upload"
    AUTO_FETCHED = "auto_fetched"
    SYSTEM = "system"


class DocumentStatus(str, Enum):
    """Processing status for documents.

    States:
    - pending: Uploaded, awaiting OCR processing
    - processing: OCR/extraction in progress
    - ocr_complete: OCR successfully extracted text
    - ocr_failed: OCR processing failed
    - chunking: Creating parent-child chunks for RAG
    - chunking_failed: Chunking process failed
    - embedding: Generating embeddings for semantic search
    - embedding_failed: Embedding generation failed
    - searchable: Fully processed and searchable via hybrid search
    - completed: All processing complete (alias for searchable)
    - failed: Processing failed (non-OCR)
    """

    PENDING = "pending"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    OCR_FAILED = "ocr_failed"
    CHUNKING = "chunking"
    CHUNKING_FAILED = "chunking_failed"
    EMBEDDING = "embedding"
    EMBEDDING_FAILED = "embedding_failed"
    SEARCHABLE = "searchable"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentBase(BaseModel):
    """Base document properties."""

    model_config = ConfigDict(populate_by_name=True)

    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    document_type: DocumentType = Field(
        default=DocumentType.CASE_FILE,
        alias="documentType",
        description="Document classification type"
    )


class DocumentCreate(DocumentBase):
    """Internal model for creating a document record."""

    matter_id: str = Field(..., alias="matterId", description="Matter UUID this document belongs to")
    storage_path: str = Field(..., alias="storagePath", description="Supabase Storage path")
    file_size: int = Field(..., ge=0, alias="fileSize", description="File size in bytes")
    is_reference_material: bool = Field(
        default=False,
        alias="isReferenceMaterial",
        description="True for Acts and reference docs"
    )
    source: DocumentSource = Field(
        default=DocumentSource.USER_UPLOAD,
        description="Document source: user_upload, auto_fetched, or system"
    )
    uploaded_by: str | None = Field(None, alias="uploadedBy", description="User UUID who uploaded (null for auto-fetched)")
    india_code_url: str | None = Field(
        None,
        alias="indiaCodeUrl",
        description="Original India Code URL for auto-fetched Acts"
    )


class Document(DocumentBase):
    """Complete document model returned from API."""

    id: str = Field(..., description="Document UUID")
    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    storage_path: str = Field(..., alias="storagePath", description="Supabase Storage path")
    file_size: int = Field(..., ge=0, alias="fileSize", description="File size in bytes")
    page_count: int | None = Field(None, alias="pageCount", description="Number of pages (null until OCR)")
    is_reference_material: bool = Field(
        default=False,
        alias="isReferenceMaterial",
        description="True for Acts and reference docs"
    )
    source: DocumentSource = Field(
        default=DocumentSource.USER_UPLOAD,
        description="Document source: user_upload, auto_fetched, or system"
    )
    uploaded_by: str | None = Field(None, alias="uploadedBy", description="User UUID who uploaded (null for auto-fetched)")
    uploaded_at: datetime = Field(..., alias="uploadedAt", description="Upload timestamp")
    india_code_url: str | None = Field(
        None,
        alias="indiaCodeUrl",
        description="Original India Code URL for auto-fetched Acts"
    )
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        description="Processing status"
    )
    processing_started_at: datetime | None = Field(
        None,
        alias="processingStartedAt",
        description="When OCR processing started"
    )
    processing_completed_at: datetime | None = Field(
        None,
        alias="processingCompletedAt",
        description="When OCR processing completed"
    )
    # OCR result fields
    extracted_text: str | None = Field(
        None,
        alias="extractedText",
        description="Full OCR-extracted text content"
    )
    ocr_confidence: float | None = Field(
        None, ge=0, le=1,
        alias="ocrConfidence",
        description="Average OCR confidence score (0-1)"
    )
    ocr_quality_score: float | None = Field(
        None, ge=0, le=1,
        alias="ocrQualityScore",
        description="Document AI image quality score (0-1)"
    )
    ocr_confidence_per_page: list[float] | None = Field(
        None,
        alias="ocrConfidencePerPage",
        description="Per-page OCR confidence scores (0-1)"
    )
    ocr_quality_status: str | None = Field(
        None,
        alias="ocrQualityStatus",
        description="OCR quality level: 'good' (>85%), 'fair' (70-85%), 'poor' (<70%)"
    )
    ocr_error: str | None = Field(
        None,
        alias="ocrError",
        description="Error details if OCR processing failed"
    )
    ocr_retry_count: int = Field(
        default=0,
        alias="ocrRetryCount",
        description="Number of OCR retry attempts"
    )
    validation_status: str | None = Field(
        None,
        alias="validationStatus",
        description="OCR validation status: 'pending', 'validated', 'requires_human_review'"
    )
    deleted_at: datetime | None = Field(
        None,
        alias="deletedAt",
        description="Soft delete timestamp (NULL = not deleted)"
    )
    created_at: datetime = Field(..., alias="createdAt", description="Record creation timestamp")
    updated_at: datetime = Field(..., alias="updatedAt", description="Last update timestamp")


class DocumentFeatures(BaseModel):
    """Feature availability flags for a document.

    Story 7.2: Progressive UI updates - indicates which features
    are available based on pipeline completion status.
    """

    model_config = ConfigDict(populate_by_name=True)

    search: bool = Field(
        default=False,
        description="Text search available (chunks created)"
    )
    semantic_search: bool = Field(
        default=False,
        alias="semanticSearch",
        description="Vector search available (embeddings generated)"
    )
    entities: bool = Field(
        default=False,
        description="Entity data available (extraction completed)"
    )
    timeline: bool = Field(
        default=False,
        description="Timeline events available (date extraction completed)"
    )
    citations: bool = Field(
        default=False,
        description="Citation data available (citation extraction completed)"
    )
    bbox_highlighting: bool = Field(
        default=False,
        alias="bboxHighlighting",
        description="Bounding box highlighting available for search results"
    )


class DocumentWithFeatures(Document):
    """Document with feature availability flags.

    Extends Document to include features dict showing which
    pipeline stages have completed for this document.
    """

    features: DocumentFeatures = Field(
        default_factory=DocumentFeatures,
        description="Feature availability based on pipeline status"
    )


class UploadedDocument(BaseModel):
    """Simplified document model for upload response."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(..., alias="documentId", description="Document UUID")
    filename: str = Field(..., description="Original filename")
    storage_path: str = Field(..., alias="storagePath", description="Supabase Storage path")
    file_size: int = Field(..., ge=0, alias="fileSize", description="File size in bytes")
    document_type: DocumentType = Field(..., alias="documentType", description="Document classification")
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

    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, alias="perPage", description="Items per page")
    total_pages: int = Field(..., ge=0, alias="totalPages", description="Total number of pages")


class DocumentListItem(BaseModel):
    """Document item for list responses (subset of full Document).

    IMPORTANT: Fields here must stay in sync with:
    1. DOCUMENT_LIST_SELECT_FIELDS in document_service.py
    2. DocumentListItem interface in frontend/src/types/document.ts

    When adding fields, update all three locations.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Document UUID")
    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., ge=0, alias="fileSize", description="File size in bytes")
    page_count: int | None = Field(None, alias="pageCount", description="Number of pages (null until OCR)")
    document_type: DocumentType = Field(..., alias="documentType", description="Document classification")
    is_reference_material: bool = Field(..., alias="isReferenceMaterial", description="True for Acts and reference docs")
    source: DocumentSource = Field(
        default=DocumentSource.USER_UPLOAD,
        description="Document source: user_upload, auto_fetched, or system"
    )
    status: DocumentStatus = Field(..., description="Processing status")
    uploaded_at: datetime = Field(..., alias="uploadedAt", description="Upload timestamp")
    uploaded_by: str | None = Field(None, alias="uploadedBy", description="User UUID who uploaded (null for auto-fetched)")
    ocr_confidence: float | None = Field(
        None, ge=0, le=1,
        alias="ocrConfidence",
        description="Average OCR confidence score (0-1)"
    )
    ocr_quality_status: str | None = Field(
        None,
        alias="ocrQualityStatus",
        description="OCR quality level: 'good', 'fair', or 'poor'"
    )


class DocumentListResponseWithPagination(BaseModel):
    """API response for paginated document list."""

    data: list[DocumentListItem]
    meta: PaginationMeta


class DocumentDetailResponse(BaseModel):
    """API response for document detail with signed URL and feature flags."""

    data: DocumentWithFeatures


class DocumentUpdate(BaseModel):
    """Model for updating document metadata."""

    model_config = ConfigDict(populate_by_name=True)

    document_type: DocumentType | None = Field(
        None,
        alias="documentType",
        description="New document classification type"
    )
    is_reference_material: bool | None = Field(
        None,
        alias="isReferenceMaterial",
        description="Override reference material flag (auto-set for acts)"
    )
    filename: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="New filename for the document"
    )


class BulkDocumentUpdate(BaseModel):
    """Model for bulk document type assignment."""

    model_config = ConfigDict(populate_by_name=True)

    document_ids: list[str] = Field(
        ...,
        min_length=1,
        alias="documentIds",
        description="List of document UUIDs to update"
    )
    document_type: DocumentType = Field(
        ...,
        alias="documentType",
        description="Document type to assign to all documents"
    )


class BulkUpdateResponse(BaseModel):
    """Response for bulk update operation."""

    data: dict = Field(
        default_factory=dict,
        description="Update result details"
    )
