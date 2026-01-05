"""Dependency injection for API routes.

This module provides FastAPI dependencies for:
- Database access (Supabase)
- Authentication (JWT-based)
- Authorization (role-based and matter-based)
- Matter access validation (Layer 4 of 4-layer isolation)

CRITICAL: All matter-related routes MUST use `validate_matter_access` or
`require_matter_role` to enforce Layer 4 security.
"""

import re
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Path, Request, status

from app.core.config import get_settings
from app.core.security import get_current_user, get_optional_user
from app.models.auth import AuthenticatedUser
from app.models.matter import MatterRole
from app.services.supabase.client import get_supabase_client
from app.services.matter_service import MatterService

logger = structlog.get_logger(__name__)

# UUID validation pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE
)

# Minimum response time for access denied (timing attack mitigation)
MIN_ACCESS_DENIED_TIME_MS = 100


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


# =============================================================================
# Layer 4: Matter Access Validation (Defense in Depth)
# =============================================================================


@dataclass
class MatterAccessContext:
    """Context for validated matter access.

    This class provides a typed context that confirms matter access
    has been validated for the current request.

    Attributes:
        matter_id: The validated matter UUID.
        user_id: The authenticated user's UUID.
        role: The user's role on this matter (if applicable).
        access_level: Type of access validated (any, viewer, editor, owner).
    """
    matter_id: str
    user_id: str
    role: MatterRole | None = None
    access_level: str = "any"


def _validate_uuid(value: str, name: str) -> None:
    """Validate that a value is a valid UUID.

    Args:
        value: The value to validate.
        name: Name of the parameter (for error messages).

    Raises:
        HTTPException: If the value is not a valid UUID.
    """
    if not value or not UUID_PATTERN.match(value):
        logger.warning(
            "invalid_uuid_parameter",
            parameter=name,
            value=value[:50] if value else None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": f"Invalid {name} format",
                    "details": {},
                }
            },
        )


def _apply_timing_mitigation(start_time: float) -> None:
    """Apply timing attack mitigation by ensuring minimum response time.

    This prevents attackers from using response time differences to
    enumerate valid matter IDs.

    Args:
        start_time: The start time of the request (time.time()).
    """
    elapsed_ms = (time.time() - start_time) * 1000

    if elapsed_ms < MIN_ACCESS_DENIED_TIME_MS:
        sleep_time = (MIN_ACCESS_DENIED_TIME_MS - elapsed_ms) / 1000
        time.sleep(sleep_time)


def validate_matter_access(
    require_role: MatterRole | None = None,
) -> Callable[..., MatterAccessContext]:
    """Create a dependency that validates matter access.

    This is the primary Layer 4 security dependency. It validates:
    1. The matter_id is a valid UUID (prevents injection)
    2. The user has access to the matter
    3. The user has the required role (if specified)

    Uses constant-time responses to prevent timing attacks.

    Args:
        require_role: Optional minimum role required (None = any role).

    Returns:
        A dependency function that returns MatterAccessContext.

    Example:
        @router.get("/matters/{matter_id}/documents")
        async def list_documents(
            access: MatterAccessContext = Depends(validate_matter_access())
        ):
            # User has verified access to access.matter_id
            ...

        @router.delete("/matters/{matter_id}")
        async def delete_matter(
            access: MatterAccessContext = Depends(validate_matter_access(MatterRole.OWNER))
        ):
            # Only owners can reach this point
            ...
    """

    async def matter_access_validator(
        request: Request,
        matter_id: str = Path(..., description="Matter ID"),
        user: AuthenticatedUser = Depends(get_current_user),
        matter_service: MatterService = Depends(get_matter_service),
    ) -> MatterAccessContext:
        start_time = time.time()

        # Validate matter_id format (prevents SQL injection attempts)
        _validate_uuid(matter_id, "matter_id")

        # Check user's access to this matter
        role = matter_service.get_user_role(matter_id, user.id)

        if role is None:
            # Log access attempt for audit
            logger.warning(
                "matter_access_denied",
                user_id=user.id,
                matter_id=matter_id,
                reason="no_membership",
                ip_address=request.client.host if request.client else None,
                path=request.url.path,
            )

            # Apply timing mitigation
            _apply_timing_mitigation(start_time)

            # Return 404 (not 403) to prevent matter enumeration
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

        # Check role requirement if specified
        if require_role is not None:
            role_hierarchy = {
                MatterRole.VIEWER: 0,
                MatterRole.EDITOR: 1,
                MatterRole.OWNER: 2,
            }

            user_level = role_hierarchy.get(role, -1)
            required_level = role_hierarchy.get(require_role, 0)

            if user_level < required_level:
                logger.warning(
                    "matter_access_denied",
                    user_id=user.id,
                    matter_id=matter_id,
                    reason="insufficient_role",
                    user_role=role.value,
                    required_role=require_role.value,
                    ip_address=request.client.host if request.client else None,
                    path=request.url.path,
                )

                # Apply timing mitigation
                _apply_timing_mitigation(start_time)

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": f"This action requires {require_role.value} role",
                            "details": {},
                        }
                    },
                )

        # Log successful access for audit
        logger.info(
            "matter_access_granted",
            user_id=user.id,
            matter_id=matter_id,
            role=role.value,
            path=request.url.path,
        )

        return MatterAccessContext(
            matter_id=matter_id,
            user_id=user.id,
            role=role,
            access_level=require_role.value if require_role else "any",
        )

    return matter_access_validator


# Convenience aliases for common access patterns
def require_matter_viewer() -> Callable[..., MatterAccessContext]:
    """Require at least viewer access to a matter."""
    return validate_matter_access(require_role=MatterRole.VIEWER)


def require_matter_editor() -> Callable[..., MatterAccessContext]:
    """Require at least editor access to a matter."""
    return validate_matter_access(require_role=MatterRole.EDITOR)


def require_matter_owner() -> Callable[..., MatterAccessContext]:
    """Require owner access to a matter."""
    return validate_matter_access(require_role=MatterRole.OWNER)


# =============================================================================
# Audit Logging Helper
# =============================================================================


def log_matter_access(
    user_id: str,
    matter_id: str,
    action: str,
    result: str,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a matter access event for audit purposes.

    This function provides consistent audit logging for all matter
    access events, both successful and failed.

    Args:
        user_id: The user attempting access.
        matter_id: The matter being accessed.
        action: The action being performed (view, edit, delete, etc.).
        result: The result (granted, denied, error).
        request: Optional FastAPI request for IP address.
        details: Optional additional details to log.
    """
    log_data = {
        "user_id": user_id,
        "matter_id": matter_id,
        "action": action,
        "result": result,
    }

    if request and request.client:
        log_data["ip_address"] = request.client.host
        log_data["path"] = request.url.path
        log_data["method"] = request.method

    if details:
        log_data.update(details)

    if result == "granted":
        logger.info("matter_access_audit", **log_data)
    else:
        logger.warning("matter_access_audit", **log_data)


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
    "MatterAccessContext",
    "validate_matter_access",
    "require_matter_viewer",
    "require_matter_editor",
    "require_matter_owner",
    "log_matter_access",
    "AuthenticatedUser",
    "MatterRole",
]
