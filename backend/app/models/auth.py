"""Authentication models for JWT claims and user information."""

from pydantic import BaseModel, Field


class JWTClaims(BaseModel):
    """JWT claims structure matching Supabase token format.

    The JWT from Supabase contains these standard claims plus
    additional metadata about the user session.
    """

    sub: str = Field(..., description="User ID (UUID)")
    aud: str = Field(..., description="Audience - should be 'authenticated'")
    exp: int = Field(..., description="Expiration timestamp (Unix epoch)")
    iat: int = Field(..., description="Issued at timestamp (Unix epoch)")
    iss: str | None = Field(None, description="Issuer URL")
    email: str | None = Field(None, description="User email address")
    phone: str | None = Field(None, description="User phone number")
    role: str = Field("authenticated", description="User role")
    aal: str | None = Field(None, description="Authentication Assurance Level")
    session_id: str | None = Field(None, description="Session UUID")


class AuthenticatedUser(BaseModel):
    """Authenticated user information extracted from JWT.

    This is the standardized user object returned by auth dependencies
    for use throughout the application.
    """

    id: str = Field(..., description="User ID (UUID from JWT 'sub' claim)")
    email: str | None = Field(None, description="User email address")
    role: str = Field("authenticated", description="User role")
    session_id: str | None = Field(None, description="Session UUID for audit")
