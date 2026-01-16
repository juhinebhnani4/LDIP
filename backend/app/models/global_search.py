"""Global Search models for cross-matter search API.

Defines request/response models for the global search endpoint.
This endpoint searches across ALL matters the user has access to.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GlobalSearchResultItem(BaseModel):
    """Single global search result item.

    Uses camelCase aliases to match frontend SearchResult interface
    from GlobalSearch.tsx.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Result UUID (chunk ID or matter ID)")
    type: Literal["matter", "document"] = Field(
        ..., description="Result type: 'matter' or 'document'"
    )
    title: str = Field(..., description="Result title (document name or matter title)")
    matter_id: str = Field(
        ..., alias="matterId", description="Matter UUID this result belongs to"
    )
    matter_title: str = Field(
        ..., alias="matterTitle", description="Title of the matter"
    )
    matched_content: str = Field(
        ...,
        alias="matchedContent",
        description="Snippet of matched content (50-100 chars)",
    )


class GlobalSearchMeta(BaseModel):
    """Metadata about the global search results."""

    query: str = Field(..., description="Original search query")
    total: int = Field(..., description="Total number of results returned")


class GlobalSearchResponse(BaseModel):
    """Response model for global search endpoint.

    Follows project API response format with data and meta.
    """

    data: list[GlobalSearchResultItem] = Field(..., description="Search results")
    meta: GlobalSearchMeta = Field(..., description="Search metadata")


class GlobalSearchErrorDetail(BaseModel):
    """Error detail model for global search errors."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error details")


class GlobalSearchErrorResponse(BaseModel):
    """Error response model for global search endpoint."""

    error: GlobalSearchErrorDetail = Field(..., description="Error information")
