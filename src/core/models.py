"""Pydantic models for Jaanch Lite."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# =============================================================================
# Document & Chunk Models
# =============================================================================

class ChunkType(str, Enum):
    """Type of content chunk from ADE."""
    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    HEADER = "header"
    FOOTER = "footer"


class BoundingBox(BaseModel):
    """Bounding box coordinates (normalized 0-1)."""
    x0: float = Field(..., ge=0, le=1, description="Left coordinate")
    y0: float = Field(..., ge=0, le=1, description="Top coordinate")
    x1: float = Field(..., ge=0, le=1, description="Right coordinate")
    y1: float = Field(..., ge=0, le=1, description="Bottom coordinate")

    @classmethod
    def from_list(cls, coords: list[float]) -> "BoundingBox":
        """Create from [x0, y0, x1, y1] list."""
        return cls(x0=coords[0], y0=coords[1], x1=coords[2], y1=coords[3])

    def to_list(self) -> list[float]:
        """Convert to [x0, y0, x1, y1] list."""
        return [self.x0, self.y0, self.x1, self.y1]


class Chunk(BaseModel):
    """A document chunk with visual grounding."""
    chunk_id: str
    text: str
    page: int
    chunk_type: ChunkType = ChunkType.TEXT
    bbox: Optional[BoundingBox] = None
    document_id: Optional[str] = None
    matter_id: Optional[str] = None

    # Metadata
    token_count: Optional[int] = None
    embedding: Optional[list[float]] = None


# =============================================================================
# Citation Models
# =============================================================================

class CitationConfidence(str, Enum):
    """Confidence level for citation extraction."""
    HIGH = "high"      # >0.9 - Clear citation
    MEDIUM = "medium"  # 0.7-0.9 - Likely citation
    LOW = "low"        # <0.7 - Possible citation


class Citation(BaseModel):
    """An extracted legal citation."""
    act_name: str = Field(..., description="Full act name, e.g., 'Negotiable Instruments Act, 1881'")
    section: str = Field(..., description="Section number, e.g., '138'")
    subsection: Optional[str] = Field(None, description="Subsection, e.g., '(1)(a)'")
    clause: Optional[str] = Field(None, description="Clause reference")

    # Source information
    raw_text: str = Field(..., description="Original text containing the citation")
    source_chunk_id: Optional[str] = None
    source_page: Optional[int] = None
    source_bbox: Optional[BoundingBox] = None

    # Extraction metadata
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence 0-1")
    extraction_method: str = Field("hybrid", description="regex, llm, or hybrid")


class CitationExtractionResult(BaseModel):
    """Result from citation extraction."""
    citations: list[Citation]
    total_found: int = 0
    extraction_method: str = "hybrid"

    def __init__(self, **data):
        super().__init__(**data)
        self.total_found = len(self.citations)


# =============================================================================
# Verification Models
# =============================================================================

class VerificationStatus(str, Enum):
    """Status of citation verification."""
    VERIFIED = "verified"           # Citation matches act text
    MISMATCH = "mismatch"          # Citation doesn't match
    NOT_FOUND = "not_found"        # Section not found in act
    ACT_MISSING = "act_missing"    # Act not in library
    PENDING = "pending"            # Not yet verified


class VerificationResult(BaseModel):
    """Result of verifying a citation against an act."""
    citation: Citation
    status: VerificationStatus
    matched_text: Optional[str] = None
    similarity_score: Optional[float] = None
    act_chunk_id: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# Search Models
# =============================================================================

class SearchResult(BaseModel):
    """A search result with grounding."""
    chunk: Chunk
    score: float = Field(..., description="Relevance score")
    rank: int = Field(..., description="Result rank (1-based)")

    # Grounding info (from ADE)
    page: int
    bbox: Optional[BoundingBox] = None

    # Reranking info
    rerank_score: Optional[float] = None
    original_rank: Optional[int] = None


class SearchResponse(BaseModel):
    """Response from a search query."""
    query: str
    results: list[SearchResult]
    total_results: int = 0
    search_type: str = "hybrid"  # semantic, keyword, hybrid
    reranked: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        self.total_results = len(self.results)


# =============================================================================
# Acts Library Models
# =============================================================================

class KnownAct(BaseModel):
    """Metadata for a known Indian act."""
    normalized_name: str = Field(..., description="Lowercase, underscored name")
    canonical_name: str = Field(..., description="Display name with year")
    india_code_doc_id: Optional[str] = None
    india_code_filename: Optional[str] = None
    category: str = "general"
    is_active: bool = True
    aliases: list[str] = []
    replaces: Optional[str] = None  # Act this replaces (e.g., BNS replaces IPC)


class ActSection(BaseModel):
    """A section from an indexed act."""
    act_name: str
    section_number: str
    text: str
    page: Optional[int] = None
    chunk_id: str
