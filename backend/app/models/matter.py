"""Matter models for the role-per-matter authorization system.

CRITICAL: All response models use camelCase aliases to match frontend TypeScript types.
This ensures seamless API integration without manual field transformation.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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


class VerificationMode(str, Enum):
    """Verification mode for matter exports.

    Story 3.1: Configurable verification gates per matter.
    Gap #1: Allow configurable verification requirements.

    Modes:
    - advisory: Default mode. Acknowledgment only - exports show warning but allow download.
    - required: Court-ready mode. 100% verification required before export is allowed.
    """

    ADVISORY = "advisory"
    REQUIRED = "required"


class DataResidency(str, Enum):
    """Data residency region for API routing.

    Story 7.3: Data Residency Controls
    Gap #20: Data residency controls for client sovereignty requirements.

    Regions:
    - default: Auto-select based on firm settings
    - us: US regional endpoints
    - eu: EU regional endpoints (GDPR compliance)
    - asia: Asia regional endpoints
    """

    DEFAULT = "default"
    US = "us"
    EU = "eu"
    ASIA = "asia"


class AnalysisMode(str, Enum):
    """Analysis mode for document processing.

    Story 6.4: Analysis Mode Toggle
    Gap #8: Processing intensity control per matter.

    Modes:
    - quick_scan: Faster processing, skips contradiction engine, larger chunks
    - deep_analysis: Full processing with all engines (default)
    """

    QUICK_SCAN = "quick_scan"
    DEEP_ANALYSIS = "deep_analysis"


class MatterMember(BaseModel):
    """A member of a matter with their role assignment."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Membership record ID")
    user_id: str = Field(..., alias="userId", description="User ID of the member")
    email: str | None = Field(None, description="User email (populated from users table)")
    full_name: str | None = Field(None, alias="fullName", description="User's full name")
    role: MatterRole = Field(..., description="Role on this matter")
    invited_by: str | None = Field(None, alias="invitedBy", description="User ID who invited this member")
    invited_at: datetime | None = Field(None, alias="invitedAt", description="When the member was invited")


class MatterBase(BaseModel):
    """Base matter properties shared across models."""

    title: str = Field(..., min_length=1, max_length=255, description="Matter title")
    description: str | None = Field(None, max_length=2000, description="Matter description")


class MatterCreate(MatterBase):
    """Request model for creating a new matter."""

    model_config = ConfigDict(populate_by_name=True)

    practice_group: str | None = Field(
        None,
        alias="practiceGroup",
        max_length=100,
        description="Practice group for cost reporting (Story 7.2)",
    )
    data_residency: DataResidency = Field(
        default=DataResidency.DEFAULT,
        alias="dataResidency",
        description="Data residency region for API routing (Story 7.3)",
    )
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.DEEP_ANALYSIS,
        alias="analysisMode",
        description="Analysis mode: quick_scan or deep_analysis (Story 6.4)",
    )


class MatterUpdate(BaseModel):
    """Request model for updating an existing matter."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(None, min_length=1, max_length=255, description="Matter title")
    description: str | None = Field(None, max_length=2000, description="Matter description")
    status: MatterStatus | None = Field(None, description="Matter status")
    verification_mode: VerificationMode | None = Field(
        None,
        alias="verificationMode",
        description="Verification requirement mode: advisory or required (Story 3.1)",
    )
    practice_group: str | None = Field(
        None,
        alias="practiceGroup",
        max_length=100,
        description="Practice group for cost reporting (Story 7.2)",
    )
    analysis_mode: AnalysisMode | None = Field(
        None,
        alias="analysisMode",
        description="Analysis mode: quick_scan or deep_analysis (Story 6.4)",
    )
    # Note: data_residency is NOT updateable after creation (immutable once documents uploaded)


class Matter(MatterBase):
    """Complete matter model returned from API."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Matter UUID")
    status: MatterStatus = Field(default=MatterStatus.ACTIVE, description="Matter status")
    verification_mode: VerificationMode = Field(
        default=VerificationMode.ADVISORY,
        alias="verificationMode",
        description="Verification requirement mode: advisory or required (Story 3.1)",
    )
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.DEEP_ANALYSIS,
        alias="analysisMode",
        description="Analysis mode: quick_scan or deep_analysis (Story 6.4)",
    )
    practice_group: str | None = Field(
        None,
        alias="practiceGroup",
        description="Practice group for cost reporting (Story 7.2)",
    )
    data_residency: DataResidency = Field(
        default=DataResidency.DEFAULT,
        alias="dataResidency",
        description="Data residency region for API routing (Story 7.3)",
    )
    created_at: datetime = Field(..., alias="createdAt", description="When the matter was created")
    updated_at: datetime = Field(..., alias="updatedAt", description="When the matter was last updated")
    deleted_at: datetime | None = Field(None, alias="deletedAt", description="Soft delete timestamp (NULL = not deleted)")
    role: MatterRole | None = Field(None, description="Current user's role on this matter")
    member_count: int = Field(default=0, alias="memberCount", description="Number of members on this matter")


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

    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(..., description="Total number of matters")
    page: int = Field(default=1, description="Current page number")
    per_page: int = Field(default=20, alias="perPage", description="Items per page")
    total_pages: int = Field(..., alias="totalPages", description="Total number of pages")


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
