"""
User management API routes.

Story 14.14: Settings Page Implementation
Endpoints for user profile and preferences management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from supabase import Client

from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/api/users", tags=["users"])


def get_supabase_client() -> Client | None:
    """Dependency for Supabase service client."""
    return get_service_client()


# =============================================================================
# Request/Response Models
# =============================================================================


class UserPreferences(BaseModel):
    """User preferences for notifications and appearance."""

    email_notifications_processing: bool = Field(
        default=True, description="Email notifications for document processing completion"
    )
    email_notifications_verification: bool = Field(
        default=True, description="Email notifications for verification reminders"
    )
    browser_notifications: bool = Field(
        default=False, description="Browser push notifications"
    )
    theme: Literal["light", "dark", "system"] = Field(
        default="system", description="UI theme preference"
    )


class UserPreferencesResponse(UserPreferences):
    """User preferences response with timestamps."""

    created_at: datetime
    updated_at: datetime


class UpdatePreferencesRequest(BaseModel):
    """Request to update user preferences (partial updates allowed)."""

    email_notifications_processing: Optional[bool] = None
    email_notifications_verification: Optional[bool] = None
    browser_notifications: Optional[bool] = None
    theme: Optional[Literal["light", "dark", "system"]] = None


class UserProfile(BaseModel):
    """User profile information."""

    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """Request to update user profile."""

    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)


# =============================================================================
# Helper Functions
# =============================================================================


async def ensure_preferences_exist(supabase: Client, user_id: str) -> None:
    """Create default preferences if they don't exist."""
    result = supabase.table("user_preferences").select("user_id").eq("user_id", user_id).execute()

    if not result.data:
        supabase.table("user_preferences").insert({"user_id": user_id}).execute()


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> UserPreferencesResponse:
    """
    Get current user's preferences.

    Creates default preferences if they don't exist.
    """
    user_id = current_user.id

    # Ensure preferences exist
    await ensure_preferences_exist(supabase, user_id)

    # Fetch preferences
    result = supabase.table("user_preferences").select("*").eq("user_id", user_id).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user preferences",
        )

    return UserPreferencesResponse(
        email_notifications_processing=result.data["email_notifications_processing"],
        email_notifications_verification=result.data["email_notifications_verification"],
        browser_notifications=result.data["browser_notifications"],
        theme=result.data["theme"],
        created_at=result.data["created_at"],
        updated_at=result.data["updated_at"],
    )


@router.patch("/me/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    request: UpdatePreferencesRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> UserPreferencesResponse:
    """
    Update current user's preferences.

    Partial updates are supported - only provided fields will be updated.
    """
    user_id = current_user.id

    # Ensure preferences exist
    await ensure_preferences_exist(supabase, user_id)

    # Build update data (only non-None fields)
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}

    if not update_data:
        # No updates, just return current preferences
        return await get_user_preferences(current_user, supabase)

    # Update preferences
    result = (
        supabase.table("user_preferences")
        .update(update_data)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user preferences",
        )

    updated = result.data[0]
    return UserPreferencesResponse(
        email_notifications_processing=updated["email_notifications_processing"],
        email_notifications_verification=updated["email_notifications_verification"],
        browser_notifications=updated["browser_notifications"],
        theme=updated["theme"],
        created_at=updated["created_at"],
        updated_at=updated["updated_at"],
    )


@router.get("/me/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfile:
    """Get current user's profile information."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email or "",
        full_name=None,  # User metadata not available in AuthenticatedUser
        avatar_url=None,  # User metadata not available in AuthenticatedUser
    )


@router.patch("/me/profile", response_model=UserProfile)
async def update_user_profile(
    request: UpdateProfileRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> UserProfile:
    """
    Update current user's profile.

    Updates user metadata in Supabase Auth.
    """
    user_id = current_user.id

    # Build metadata update
    metadata_update = {}
    if request.full_name is not None:
        metadata_update["full_name"] = request.full_name
    if request.avatar_url is not None:
        metadata_update["avatar_url"] = request.avatar_url

    if not metadata_update:
        # No updates
        return await get_user_profile(current_user)

    # Update user metadata via Supabase Admin API
    # Note: This requires service role key for admin operations
    try:
        result = supabase.auth.admin.update_user_by_id(
            user_id, {"user_metadata": metadata_update}
        )

        if result.user:
            return UserProfile(
                id=result.user.id,
                email=result.user.email or "",
                full_name=result.user.user_metadata.get("full_name") if result.user.user_metadata else None,
                avatar_url=result.user.user_metadata.get("avatar_url") if result.user.user_metadata else None,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}",
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to update profile",
    )
