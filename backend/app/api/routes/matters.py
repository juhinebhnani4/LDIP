"""Matter API routes with role-based access control."""

from math import ceil

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    AuthenticatedUser,
    MatterMembership,
    MatterRole,
    TabStatsService,
    get_current_user,
    get_matter_service,
    get_tab_stats_service_dep,
    require_matter_role,
)
from app.core.rate_limit import STANDARD_RATE_LIMIT, limiter
from app.models.matter import (
    MatterCreate,
    MatterInvite,
    MatterListMeta,
    MatterListResponse,
    MatterMemberUpdate,
    MatterResponse,
    MatterStatus,
    MatterUpdate,
    MatterWithMembersResponse,
    MemberListResponse,
    MemberResponse,
)
from app.models.tab_stats import TabStatsResponse
from app.services.matter_service import (
    CannotRemoveOwnerError,
    MatterNotFoundError,
    MatterService,
    MatterServiceError,
    MemberAlreadyExistsError,
    UserNotFoundError,
)
from app.services.tab_stats_service import TabStatsServiceError

router = APIRouter(prefix="/matters", tags=["matters"])
logger = structlog.get_logger(__name__)


def _handle_service_error(error: MatterServiceError) -> HTTPException:
    """Convert service errors to HTTP exceptions."""
    return HTTPException(
        status_code=error.status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


@router.post("", response_model=MatterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(STANDARD_RATE_LIMIT)
async def create_matter(
    request: Request,  # Required for rate limiter
    data: MatterCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> MatterResponse:
    """Create a new matter.

    The creating user is automatically assigned as owner.

    Args:
        data: Matter creation data.
        user: Authenticated user.
        matter_service: Matter service.

    Returns:
        Created matter with owner role.
    """
    try:
        matter = matter_service.create_matter(user.id, data)
        return MatterResponse(data=matter)
    except MatterServiceError as e:
        raise _handle_service_error(e)


@router.get("", response_model=MatterListResponse)
@limiter.limit(STANDARD_RATE_LIMIT)
async def list_matters(
    request: Request,  # Required for rate limiter
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: MatterStatus | None = Query(None, alias="status", description="Filter by status"),
    user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> MatterListResponse:
    """List all matters the user has access to.

    Args:
        page: Page number (1-indexed).
        per_page: Number of items per page.
        status_filter: Optional status filter.
        user: Authenticated user.
        matter_service: Matter service.

    Returns:
        Paginated list of matters.
    """
    matters, total = matter_service.get_user_matters(
        user.id, page=page, per_page=per_page, status_filter=status_filter
    )

    return MatterListResponse(
        data=matters,
        meta=MatterListMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=ceil(total / per_page) if total > 0 else 1,
        ),
    )


@router.get("/{matter_id}", response_model=MatterWithMembersResponse)
@limiter.limit(STANDARD_RATE_LIMIT)
async def get_matter(
    request: Request,  # Required for rate limiter
    matter_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> MatterWithMembersResponse:
    """Get a matter with its members.

    Requires any role on the matter.

    Args:
        matter_id: Matter ID.
        user: Authenticated user.
        matter_service: Matter service.

    Returns:
        Matter with members list.
    """
    try:
        matter = matter_service.get_matter(matter_id, user.id)
        return MatterWithMembersResponse(data=matter)
    except MatterNotFoundError as e:
        raise _handle_service_error(e)


@router.patch("/{matter_id}", response_model=MatterResponse)
@limiter.limit(STANDARD_RATE_LIMIT)
async def update_matter(
    request: Request,  # Required for rate limiter
    matter_id: str,
    data: MatterUpdate,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    matter_service: MatterService = Depends(get_matter_service),
) -> MatterResponse:
    """Update matter details.

    Requires editor or owner role.

    Args:
        matter_id: Matter ID.
        data: Update data.
        membership: User's matter membership (validated by dependency).
        matter_service: Matter service.

    Returns:
        Updated matter.
    """
    try:
        matter = matter_service.update_matter(
            matter_id, membership.user_id, data
        )
        return MatterResponse(data=matter)
    except MatterServiceError as e:
        raise _handle_service_error(e)


@router.delete("/{matter_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(STANDARD_RATE_LIMIT)
async def delete_matter(
    request: Request,  # Required for rate limiter
    matter_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER])
    ),
    matter_service: MatterService = Depends(get_matter_service),
) -> None:
    """Soft-delete a matter.

    Requires owner role.

    Args:
        matter_id: Matter ID.
        membership: User's matter membership (validated by dependency).
        matter_service: Matter service.
    """
    try:
        matter_service.delete_matter(matter_id, membership.user_id)
    except MatterServiceError as e:
        raise _handle_service_error(e)


# =============================================================================
# Story 14.12: Tab Stats Endpoint
# =============================================================================


@router.get("/{matter_id}/tab-stats", response_model=TabStatsResponse)
@limiter.limit(STANDARD_RATE_LIMIT)
async def get_tab_stats(
    request: Request,  # Required for rate limiter
    matter_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    tab_stats_service: TabStatsService = Depends(get_tab_stats_service_dep),
) -> TabStatsResponse:
    """Get tab statistics for workspace tab bar.

    Story 14.12: Tab Stats API

    Returns aggregated counts and processing status for all workspace tabs:
    - summary, timeline, entities, citations, contradictions, verification, documents

    Requires any role on the matter (OWNER, EDITOR, VIEWER).

    Args:
        matter_id: Matter ID.
        membership: User's matter membership (validated by dependency).
        tab_stats_service: Tab stats service.

    Returns:
        TabStatsResponse with counts and processing status for all tabs.
    """
    try:
        data = await tab_stats_service.get_tab_stats(matter_id)
        return TabStatsResponse(data=data)
    except TabStatsServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        )


# Member management endpoints


@router.get("/{matter_id}/members", response_model=MemberListResponse)
@limiter.limit(STANDARD_RATE_LIMIT)
async def list_members(
    request: Request,  # Required for rate limiter
    matter_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    matter_service: MatterService = Depends(get_matter_service),
) -> MemberListResponse:
    """List all members of a matter.

    Requires any role on the matter.

    Args:
        matter_id: Matter ID.
        membership: User's matter membership (validated by dependency).
        matter_service: Matter service.

    Returns:
        List of members.
    """
    try:
        members = matter_service.get_members(matter_id, membership.user_id)
        return MemberListResponse(data=members)
    except MatterServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/{matter_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def invite_member(
    request: Request,  # Required for rate limiter
    matter_id: str,
    data: MatterInvite,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER])
    ),
    matter_service: MatterService = Depends(get_matter_service),
) -> MemberResponse:
    """Invite a new member to a matter.

    Requires owner role.

    Args:
        matter_id: Matter ID.
        data: Invite data (email and role).
        membership: User's matter membership (validated by dependency).
        matter_service: Matter service.

    Returns:
        Created member record.
    """
    try:
        member = matter_service.invite_member(
            matter_id,
            membership.user_id,
            data.email,
            data.role,
        )
        return MemberResponse(data=member)
    except (
        MatterServiceError,
        MemberAlreadyExistsError,
        UserNotFoundError,
    ) as e:
        raise _handle_service_error(e)


@router.patch("/{matter_id}/members/{user_id}", response_model=MemberResponse)
@limiter.limit(STANDARD_RATE_LIMIT)
async def update_member_role(
    request: Request,  # Required for rate limiter
    matter_id: str,
    user_id: str,
    data: MatterMemberUpdate,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER])
    ),
    matter_service: MatterService = Depends(get_matter_service),
) -> MemberResponse:
    """Update a member's role.

    Requires owner role. Cannot demote self from owner.

    Args:
        matter_id: Matter ID.
        user_id: ID of the member to update.
        data: New role data.
        membership: User's matter membership (validated by dependency).
        matter_service: Matter service.

    Returns:
        Updated member record.
    """
    try:
        member = matter_service.update_member_role(
            matter_id,
            membership.user_id,
            user_id,
            data.role,
        )
        return MemberResponse(data=member)
    except (MatterServiceError, CannotRemoveOwnerError) as e:
        raise _handle_service_error(e)


@router.delete("/{matter_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(STANDARD_RATE_LIMIT)
async def remove_member(
    request: Request,  # Required for rate limiter
    matter_id: str,
    user_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER])
    ),
    matter_service: MatterService = Depends(get_matter_service),
) -> None:
    """Remove a member from a matter.

    Requires owner role. Cannot remove self.

    Args:
        matter_id: Matter ID.
        user_id: ID of the member to remove.
        membership: User's matter membership (validated by dependency).
        matter_service: Matter service.
    """
    try:
        matter_service.remove_member(
            matter_id,
            membership.user_id,
            user_id,
        )
    except (MatterServiceError, CannotRemoveOwnerError) as e:
        raise _handle_service_error(e)
