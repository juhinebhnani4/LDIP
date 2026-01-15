"""Entity models for MIG (Matter Identity Graph).

Pydantic models for entity extraction, storage, and API responses.
Supports the MIG system for tracking people, organizations, institutions,
and assets mentioned in legal documents.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Enums
# =============================================================================


class EntityType(str, Enum):
    """Entity types extracted from legal documents.

    Types:
    - PERSON: Individual people (parties, witnesses, attorneys, judges)
    - ORG: Companies, corporations, partnerships, LLPs, trusts
    - INSTITUTION: Government bodies, courts, tribunals, regulatory agencies
    - ASSET: Properties, bank accounts, financial instruments, disputed items
    """

    PERSON = "PERSON"
    ORG = "ORG"
    INSTITUTION = "INSTITUTION"
    ASSET = "ASSET"


class RelationshipType(str, Enum):
    """Relationship types between entities in the MIG.

    Types:
    - ALIAS_OF: Same entity with different names (handled in Story 2C.2)
    - HAS_ROLE: Entity has a role in relation to another (e.g., Director of)
    - RELATED_TO: General relationship between entities
    """

    ALIAS_OF = "ALIAS_OF"
    HAS_ROLE = "HAS_ROLE"
    RELATED_TO = "RELATED_TO"


# =============================================================================
# Entity Node Models
# =============================================================================


class EntityNodeBase(BaseModel):
    """Base entity node properties."""

    canonical_name: str = Field(..., description="Normalized entity name")
    entity_type: EntityType = Field(..., description="Entity type classification")


class EntityNodeCreate(EntityNodeBase):
    """Model for creating an entity node record."""

    matter_id: str = Field(..., description="Matter UUID for isolation")
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata (roles, aliases found, first_mention_doc)",
    )


class EntityNode(EntityNodeBase):
    """Complete entity node model returned from API."""

    id: str = Field(..., description="Entity UUID")
    matter_id: str = Field(..., description="Matter UUID")
    metadata: dict = Field(default_factory=dict, description="Entity metadata")
    mention_count: int = Field(default=0, description="Number of mentions")
    aliases: list[str] = Field(default_factory=list, description="Known aliases")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata_none(cls, v: dict | None) -> dict:
        """Convert None to empty dict for metadata from DB."""
        return v if v is not None else {}

    @field_validator("aliases", mode="before")
    @classmethod
    def coerce_aliases_none(cls, v: list | None) -> list:
        """Convert None to empty list for aliases from DB."""
        return v if v is not None else []

    @field_validator("mention_count", mode="before")
    @classmethod
    def coerce_mention_count_none(cls, v: int | None) -> int:
        """Convert None to 0 for mention_count from DB."""
        return v if v is not None else 0


class EntityNodeWithRelations(EntityNode):
    """Entity node with relationships and mentions for detailed view."""

    relationships: list["EntityEdge"] = Field(
        default_factory=list, description="Related entities"
    )
    recent_mentions: list["EntityMention"] = Field(
        default_factory=list, description="Recent mentions"
    )


# =============================================================================
# Entity Edge Models
# =============================================================================


class EntityEdgeBase(BaseModel):
    """Base entity edge properties."""

    source_entity_id: str = Field(..., description="Source entity UUID")
    target_entity_id: str = Field(..., description="Target entity UUID")
    relationship_type: RelationshipType = Field(
        ..., description="Relationship type classification"
    )


class EntityEdgeCreate(EntityEdgeBase):
    """Model for creating an entity edge record."""

    matter_id: str = Field(..., description="Matter UUID for isolation")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )
    metadata: dict = Field(
        default_factory=dict, description="Additional metadata (description)"
    )


class EntityEdge(EntityEdgeBase):
    """Complete entity edge model returned from API."""

    id: str = Field(..., description="Edge UUID")
    matter_id: str = Field(..., description="Matter UUID")
    confidence: float = Field(..., description="Extraction confidence")
    metadata: dict = Field(default_factory=dict, description="Edge metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Populated when fetching edges with entity details
    source_entity_name: str | None = Field(
        None, description="Source entity canonical name"
    )
    target_entity_name: str | None = Field(
        None, description="Target entity canonical name"
    )


# =============================================================================
# Entity Mention Models
# =============================================================================


class EntityMentionBase(BaseModel):
    """Base entity mention properties."""

    mention_text: str = Field(..., description="Exact text of the mention")
    context: str | None = Field(None, description="Surrounding text (±50 chars)")


class EntityMentionCreate(EntityMentionBase):
    """Model for creating an entity mention record."""

    entity_id: str = Field(..., description="Entity UUID")
    document_id: str = Field(..., description="Source document UUID")
    chunk_id: str | None = Field(None, description="Source chunk UUID")
    page_number: int | None = Field(None, description="Page number")
    bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding box UUIDs"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )


class EntityMention(EntityMentionBase):
    """Complete entity mention model returned from API."""

    id: str = Field(..., description="Mention UUID")
    entity_id: str = Field(..., description="Entity UUID")
    document_id: str = Field(..., description="Source document UUID")
    chunk_id: str | None = Field(None, description="Source chunk UUID")
    page_number: int | None = Field(None, description="Page number")
    bbox_ids: list[str] = Field(default_factory=list, description="Bounding box UUIDs")
    confidence: float = Field(..., description="Extraction confidence")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Populated when fetching mentions with document details
    document_name: str | None = Field(None, description="Source document name")


# =============================================================================
# Gemini Extraction Models
# =============================================================================


class ExtractedEntityMention(BaseModel):
    """Entity mention extracted from Gemini response."""

    text: str = Field(..., description="Mention text as it appears")
    context: str | None = Field(None, description="Surrounding context")


class ExtractedEntity(BaseModel):
    """Entity extracted from Gemini response."""

    name: str = Field(..., description="Name as it appears in text")
    canonical_name: str = Field(..., description="Normalized name")
    type: EntityType = Field(..., description="Entity type")
    roles: list[str] = Field(default_factory=list, description="Roles in the document")
    mentions: list[ExtractedEntityMention] = Field(
        default_factory=list, description="All mentions found"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )


class ExtractedRelationship(BaseModel):
    """Relationship extracted from Gemini response."""

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    type: RelationshipType = Field(..., description="Relationship type")
    description: str | None = Field(None, description="Relationship description")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )


class EntityExtractionResult(BaseModel):
    """Complete extraction result from Gemini.

    Contains all entities and relationships extracted from a text chunk.
    """

    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="Extracted entities"
    )
    relationships: list[ExtractedRelationship] = Field(
        default_factory=list, description="Extracted relationships"
    )
    source_document_id: str | None = Field(None, description="Source document UUID")
    source_chunk_id: str | None = Field(None, description="Source chunk UUID")
    page_number: int | None = Field(None, description="Page number if available")


# =============================================================================
# API Response Models
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class EntityListItem(BaseModel):
    """Entity item for list responses (subset of EntityNode)."""

    id: str = Field(..., description="Entity UUID")
    canonical_name: str = Field(..., description="Normalized entity name")
    entity_type: EntityType = Field(..., description="Entity type")
    mention_count: int = Field(..., description="Number of mentions")
    metadata: dict = Field(default_factory=dict, description="Entity metadata")


class EntitiesListResponse(BaseModel):
    """API response for entity list endpoints."""

    data: list[EntityListItem]
    meta: PaginationMeta


class EntityResponse(BaseModel):
    """API response for single entity retrieval."""

    data: EntityNodeWithRelations


class EntityMentionsResponse(BaseModel):
    """API response for entity mentions list."""

    data: list[EntityMention]
    meta: PaginationMeta


# =============================================================================
# Error Models
# =============================================================================


class EntityErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error context")


class EntityErrorResponse(BaseModel):
    """Error response structure."""

    error: EntityErrorDetail


# Forward reference resolution
EntityNodeWithRelations.model_rebuild()
