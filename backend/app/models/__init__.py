"""Pydantic models module."""

from app.models.auth import AuthenticatedUser, JWTClaims
from app.models.matter import (
    Matter,
    MatterCreate,
    MatterInvite,
    MatterListMeta,
    MatterListResponse,
    MatterMember,
    MatterMemberUpdate,
    MatterResponse,
    MatterRole,
    MatterStatus,
    MatterUpdate,
    MatterWithMembers,
    MatterWithMembersResponse,
    MemberListResponse,
    MemberResponse,
)

__all__ = [
    # Auth models
    "AuthenticatedUser",
    "JWTClaims",
    # Matter models
    "Matter",
    "MatterCreate",
    "MatterInvite",
    "MatterListMeta",
    "MatterListResponse",
    "MatterMember",
    "MatterMemberUpdate",
    "MatterResponse",
    "MatterRole",
    "MatterStatus",
    "MatterUpdate",
    "MatterWithMembers",
    "MatterWithMembersResponse",
    "MemberListResponse",
    "MemberResponse",
]
