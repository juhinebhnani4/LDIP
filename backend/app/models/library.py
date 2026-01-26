"""Library models for Shared Legal Library feature.

Defines Pydantic models for library documents, linking, and search.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LibraryDocumentType(str, Enum):
    """Type of library document."""

    ACT = "act"
    STATUTE = "statute"
    JUDGMENT = "judgment"
    REGULATION = "regulation"
    COMMENTARY = "commentary"
    CIRCULAR = "circular"


class LibraryDocumentSource(str, Enum):
    """Source of library document."""

    USER_UPLOAD = "user_upload"
    INDIA_CODE = "india_code"
    MANUAL_IMPORT = "manual_import"


class LibraryDocumentStatus(str, Enum):
    """Processing status of library document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Request/Response Models
# =============================================================================


class LibraryDocumentCreate(BaseModel):
    """Request model for creating a library document."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    filename: str = Field(..., description="Original filename")
    title: str = Field(..., description="Document title (e.g., 'Indian Contract Act, 1872')")
    short_title: str | None = Field(None, alias="shortTitle", description="Short title (e.g., 'Contract Act')")
    document_type: LibraryDocumentType = Field(..., alias="documentType", description="Type of document")
    year: int | None = Field(None, description="Year of enactment/publication")
    jurisdiction: str | None = Field(
        None, description="Jurisdiction: 'central', 'state:MH', etc."
    )


class LibraryDocument(BaseModel):
    """Library document response model."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    filename: str
    storage_path: str = Field(..., alias="storagePath")
    file_size: int = Field(..., alias="fileSize")
    page_count: int | None = Field(None, alias="pageCount")

    document_type: LibraryDocumentType = Field(..., alias="documentType")
    title: str
    short_title: str | None = Field(None, alias="shortTitle")
    year: int | None = None
    jurisdiction: str | None = None

    source: LibraryDocumentSource
    source_url: str | None = Field(None, alias="sourceUrl")

    status: LibraryDocumentStatus
    processing_started_at: datetime | None = Field(None, alias="processingStartedAt")
    processing_completed_at: datetime | None = Field(None, alias="processingCompletedAt")

    quality_flags: list[str] = Field(default_factory=list, alias="qualityFlags")

    added_by: str | None = Field(None, alias="addedBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class LibraryDocumentListItem(BaseModel):
    """Minimal library document for list views."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    title: str
    short_title: str | None = Field(None, alias="shortTitle")
    document_type: LibraryDocumentType = Field(..., alias="documentType")
    year: int | None = None
    jurisdiction: str | None = None
    status: LibraryDocumentStatus
    source: LibraryDocumentSource
    page_count: int | None = Field(None, alias="pageCount")
    created_at: datetime = Field(..., alias="createdAt")

    # For matter context
    is_linked: bool = Field(False, alias="isLinked")
    linked_at: datetime | None = Field(None, alias="linkedAt")


class MatterLibraryLink(BaseModel):
    """Link between a matter and a library document."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    matter_id: str = Field(..., alias="matterId")
    library_document_id: str = Field(..., alias="libraryDocumentId")
    linked_by: str = Field(..., alias="linkedBy")
    linked_at: datetime = Field(..., alias="linkedAt")


class LibraryLinkRequest(BaseModel):
    """Request to link a library document to a matter."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    library_document_id: str = Field(..., alias="libraryDocumentId", description="Library document UUID to link")


class LibraryDuplicate(BaseModel):
    """Potential duplicate library document."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    title: str
    year: int | None = None
    document_type: LibraryDocumentType = Field(..., alias="documentType")
    similarity: float = Field(..., ge=0.0, le=1.0)


class LibrarySearchResult(BaseModel):
    """Library chunk search result."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    chunk_id: str = Field(..., alias="chunkId")
    library_document_id: str = Field(..., alias="libraryDocumentId")
    document_title: str = Field(..., alias="documentTitle")
    document_type: LibraryDocumentType = Field(..., alias="documentType")
    content: str
    page_number: int | None = Field(None, alias="pageNumber")
    section_title: str | None = Field(None, alias="sectionTitle")
    chunk_type: str = Field(..., alias="chunkType")
    similarity: float
    is_library: bool = Field(True, alias="isLibrary")  # Flag to distinguish from matter chunks


class LibraryPaginationMeta(BaseModel):
    """Pagination metadata for library queries."""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    total: int
    page: int
    per_page: int = Field(..., alias="perPage")
    total_pages: int = Field(..., alias="totalPages")


class LibraryDocumentListResponse(BaseModel):
    """Paginated library document list response."""

    documents: list[LibraryDocumentListItem]
    pagination: LibraryPaginationMeta


class LinkedLibraryDocumentsResponse(BaseModel):
    """Response for linked library documents in a matter."""

    documents: list[LibraryDocumentListItem]
    total: int
