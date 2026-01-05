"""Security utilities for Supabase JWT validation."""

import jwt
from jwt.exceptions import PyJWTError

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.models.auth import AuthenticatedUser

logger = structlog.get_logger(__name__)

# HTTP Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Validate JWT token and extract user information.

    Performs local JWT validation using the Supabase JWT secret.
    This avoids the ~600ms latency of calling Supabase API per request.

    Args:
        credentials: HTTP Bearer token credentials.
        settings: Application settings containing JWT secret.

    Returns:
        AuthenticatedUser with user information from JWT claims.

    Raises:
        HTTPException: If token is missing, invalid, or expired.
    """
    if credentials is None:
        logger.debug("jwt_validation_failed", reason="missing_token")
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

    if not settings.supabase_jwt_secret:
        logger.error("jwt_validation_failed", reason="missing_jwt_secret")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SERVER_ERROR",
                    "message": "Authentication service misconfigured",
                    "details": {},
                }
            },
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

        user = AuthenticatedUser(
            id=payload["sub"],
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
            session_id=payload.get("session_id"),
        )

        logger.debug(
            "jwt_validation_success",
            user_id=user.id,
            has_email=bool(user.email),
        )

        return user

    except jwt.ExpiredSignatureError:
        logger.warning("jwt_validation_failed", reason="token_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "TOKEN_EXPIRED",
                    "message": "Authentication token has expired",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    except jwt.InvalidAudienceError:
        logger.warning("jwt_validation_failed", reason="invalid_audience")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Invalid or expired token",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    except PyJWTError as e:
        logger.warning("jwt_validation_failed", reason="invalid_token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Invalid or expired token",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser | None:
    """Optionally validate JWT token if present.

    Use this for routes that support both authenticated and anonymous access.

    Args:
        credentials: HTTP Bearer token credentials.
        settings: Application settings.

    Returns:
        AuthenticatedUser if token present and valid, None otherwise.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, settings)
    except HTTPException:
        return None
