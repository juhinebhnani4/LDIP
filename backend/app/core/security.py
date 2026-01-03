"""Security utilities for Supabase JWT validation."""

from typing import Any

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# HTTP Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Validate JWT token and extract user information.

    This is a placeholder implementation. Full implementation will
    validate the JWT against Supabase and extract user claims.

    Args:
        credentials: HTTP Bearer token credentials.
        settings: Application settings.

    Returns:
        User information dictionary.

    Raises:
        HTTPException: If token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing authentication token",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # TODO: Implement actual JWT validation with Supabase
    # For now, return a placeholder user
    # In production, this would:
    # 1. Decode and verify the JWT signature using Supabase JWT secret
    # 2. Check token expiration
    # 3. Extract user_id, email, role from claims
    # 4. Optionally fetch additional user data from database

    logger.debug("jwt_validation_placeholder", token_length=len(token))

    # Placeholder: return minimal user info
    # This will be replaced with actual JWT parsing
    return {
        "id": "placeholder-user-id",
        "email": "placeholder@example.com",
        "role": "user",
    }


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any] | None:
    """Optionally validate JWT token if present.

    Args:
        credentials: HTTP Bearer token credentials.
        settings: Application settings.

    Returns:
        User information dictionary if token present and valid, None otherwise.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, settings)
    except HTTPException:
        return None
