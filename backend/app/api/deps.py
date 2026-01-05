"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from fastapi import Depends, HTTPException, status

from app.core.config import get_settings
from app.core.security import get_current_user, get_optional_user
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_supabase_client

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


# Re-export commonly used dependencies for convenience
__all__ = [
    "get_db",
    "get_settings",
    "get_current_user",
    "get_optional_user",
    "require_role",
    "AuthenticatedUser",
]
