"""Security utilities for Supabase JWT validation."""

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError

from app.core.config import Settings, get_settings
from app.models.auth import AuthenticatedUser

logger = structlog.get_logger(__name__)

# HTTP Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)

# Cache for JWKS public keys
_jwks_cache: dict | None = None


def _get_jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    """Get or create a JWKS client for fetching public keys.

    Args:
        supabase_url: The Supabase project URL.

    Returns:
        PyJWKClient instance for fetching public keys.
    """
    global _jwks_cache
    if _jwks_cache is None:
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_cache = {"client": jwt.PyJWKClient(jwks_url, cache_keys=True)}
    return _jwks_cache["client"]


def _decode_jwt(token: str, settings: Settings) -> dict:
    """Decode JWT token using appropriate algorithm.

    Supports both HS256 (legacy) and ES256 (new ECC) tokens.

    Args:
        token: The JWT token string.
        settings: Application settings.

    Returns:
        Decoded JWT payload.

    Raises:
        PyJWTError: If token validation fails.
    """
    # First, peek at the header to determine algorithm
    unverified_header = jwt.get_unverified_header(token)
    algorithm = unverified_header.get("alg", "HS256")

    if algorithm == "ES256":
        # Use JWKS for ES256 tokens (new Supabase ECC keys)
        jwks_client = _get_jwks_client(settings.supabase_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    else:
        # Use HS256 with legacy JWT secret
        if not settings.supabase_jwt_secret:
            raise ValueError("JWT secret not configured for HS256 tokens")
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Validate JWT token and extract user information.

    Performs local JWT validation using either:
    - JWKS public keys for ES256 tokens (new Supabase ECC keys)
    - Supabase JWT secret for HS256 tokens (legacy)

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

    if not settings.supabase_url:
        logger.error("jwt_validation_failed", reason="missing_supabase_url")
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
        payload = _decode_jwt(credentials.credentials, settings)

        user = AuthenticatedUser(
            id=payload["sub"],
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
            session_id=payload.get("session_id"),
        )

        # Bind user context to all subsequent logs in this request (Story 13.1)
        # Note: Do not log full email to protect user privacy
        structlog.contextvars.bind_contextvars(user_id=user.id)

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
        ) from None

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
        ) from None

    except PyJWTError as e:
        logger.warning(
            "jwt_validation_failed",
            reason="invalid_token",
            error=str(e),
            error_type=type(e).__name__,
        )
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
        ) from None
    except Exception as e:
        logger.warning(
            "jwt_validation_failed",
            reason="unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
        )
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
        ) from None


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
