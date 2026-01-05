"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Path, status

from app.core.config import get_settings
from app.core.security import get_current_user, get_optional_user
from app.models.auth import AuthenticatedUser
from app.models.matter import MatterRole
from app.services.supabase.client import get_supabase_client
from app.services.matter_service import MatterService

logger = structlog.get_logger(__name__)


async def get_db() -> AsyncGenerator[Any, None]:
    """Get database client (Supabase).

    This dependency provides the Supabase client for database operations.
    The client handles connection pooling internally.

    Yields:
        Supabase client instance.
    """
    client = get_supabase_client()
    if client is None:
        logger.warning("supabase_not_configured")
    yield client


def require_role(
    allowed_roles: list[str],
) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Create a dependency that requires a specific role.

    This is a dependency factory for role-based access control.
    Use it to protect routes that require specific user roles.

    Args:
        allowed_roles: List of roles that are allowed to access the route.

    Returns:
        A dependency function that validates the user's role.

    Example:
        @router.get("/admin/users")
        async def list_users(
            user: AuthenticatedUser = Depends(require_role(["admin"]))
        ):
            ...
    """

    async def role_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            logger.warning(
                "access_denied",
                user_id=user.id,
                required_roles=allowed_roles,
                user_role=user.role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You don't have permission to access this resource",
                        "details": {},
                    }
                },
            )
        return user

    return role_checker


def get_matter_service(
    db: Any = Depends(get_db),
) -> MatterService:
    """Get matter service instance.

    Args:
        db: Supabase client.

    Returns:
        MatterService instance.
    """
    return MatterService(db)


class MatterMembership:
    """Represents a user's membership on a matter."""

    def __init__(self, matter_id: str, user_id: str, role: MatterRole):
        self.matter_id = matter_id
        self.user_id = user_id
        self.role = role


def require_matter_role(
    allowed_roles: list[MatterRole],
) -> Callable[..., Any]:
    """Create a dependency that requires specific matter roles.

    This is a dependency factory for matter-level role-based access control.
    Use it to protect routes that require specific roles on a matter.

    Args:
        allowed_roles: List of MatterRole enums that are allowed.

    Returns:
        A dependency function that validates the user's role on the matter.

    Example:
        @router.delete("/matters/{matter_id}")
        async def delete_matter(
            matter_id: str,
            membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER]))
        ):
            # Only owners can delete
            ...
    """

    async def matter_role_checker(
        matter_id: str = Path(..., description="Matter ID"),
        user: AuthenticatedUser = Depends(get_current_user),
        matter_service: MatterService = Depends(get_matter_service),
    ) -> MatterMembership:
        role = matter_service.get_user_role(matter_id, user.id)

        if role is None:
            logger.warning(
                "matter_access_denied",
                user_id=user.id,
                matter_id=matter_id,
                reason="no_membership",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "MATTER_NOT_FOUND",
                        "message": "Matter not found or you don't have access",
                        "details": {},
                    }
                },
            )

        if role not in allowed_roles:
            logger.warning(
                "matter_access_denied",
                user_id=user.id,
                matter_id=matter_id,
                user_role=role.value,
                required_roles=[r.value for r in allowed_roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"This action requires one of these roles: {', '.join(r.value for r in allowed_roles)}",
                        "details": {},
                    }
                },
            )

        return MatterMembership(matter_id=matter_id, user_id=user.id, role=role)

    return matter_role_checker


# Re-export commonly used dependencies for convenience
__all__ = [
    "get_db",
    "get_settings",
    "get_current_user",
    "get_optional_user",
    "require_role",
    "require_matter_role",
    "get_matter_service",
    "MatterMembership",
    "AuthenticatedUser",
    "MatterRole",
]
