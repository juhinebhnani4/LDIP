"""Matter models for the role-per-matter authorization system."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MatterRole(str, Enum):
    """Role types for matter membership.

    Permissions:
    - owner: Full access, can delete matter, manage members
    - editor: Upload documents, run engines, verify findings
    - viewer: Read-only access to findings and documents
    """

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class MatterStatus(str, Enum):
    """Status types for matters."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class MatterMember(BaseModel):
    """A member of a matter with their role assignment."""

    id: str = Field(..., description="Membership record ID")
    user_id: str = Field(..., description="User ID of the member")
    email: str | None = Field(None, description="User email (populated from users table)")
    full_name: str | None = Field(None, description="User's full name")
    role: MatterRole = Field(..., description="Role on this matter")
    invited_by: str | None = Field(None, description="User ID who invited this member")
    invited_at: datetime | None = Field(None, description="When the member was invited")


class MatterBase(BaseModel):
    """Base matter properties shared across models."""

    title: str = Field(..., min_length=1, max_length=255, description="Matter title")
    description: str | None = Field(None, max_length=2000, description="Matter description")


class MatterCreate(MatterBase):
    """Request model for creating a new matter."""

    pass


class MatterUpdate(BaseModel):
    """Request model for updating an existing matter."""

    title: str | None = Field(None, min_length=1, max_length=255, description="Matter title")
    description: str | None = Field(None, max_length=2000, description="Matter description")
    status: MatterStatus | None = Field(None, description="Matter status")


class Matter(MatterBase):
    """Complete matter model returned from API."""

    id: str = Field(..., description="Matter UUID")
    status: MatterStatus = Field(default=MatterStatus.ACTIVE, description="Matter status")
    created_at: datetime = Field(..., description="When the matter was created")
    updated_at: datetime = Field(..., description="When the matter was last updated")
    role: MatterRole | None = Field(None, description="Current user's role on this matter")
    member_count: int = Field(default=0, description="Number of members on this matter")


class MatterWithMembers(Matter):
    """Matter model including list of members."""

    members: list[MatterMember] = Field(default_factory=list, description="List of matter members")


class MatterInvite(BaseModel):
    """Request model for inviting a member to a matter."""

    email: str = Field(..., description="Email address of the user to invite")
    role: MatterRole = Field(..., description="Role to assign to the invited user")


class MatterMemberUpdate(BaseModel):
    """Request model for updating a member's role."""

    role: MatterRole = Field(..., description="New role to assign")


# Response wrapper models following API response format
class MatterResponse(BaseModel):
    """API response wrapper for a single matter."""

    data: Matter


class MatterWithMembersResponse(BaseModel):
    """API response wrapper for a matter with members."""

    data: MatterWithMembers


class MatterListMeta(BaseModel):
    """Pagination metadata for matter list."""

    total: int = Field(..., description="Total number of matters")
    page: int = Field(default=1, description="Current page number")
    per_page: int = Field(default=20, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class MatterListResponse(BaseModel):
    """API response wrapper for matter list."""

    data: list[Matter]
    meta: MatterListMeta


class MemberListResponse(BaseModel):
    """API response wrapper for member list."""

    data: list[MatterMember]


class MemberResponse(BaseModel):
    """API response wrapper for a single member."""

    data: MatterMember
