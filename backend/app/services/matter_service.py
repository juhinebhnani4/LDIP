"""Matter service for role-per-matter authorization system.

This service provides business logic for matter operations with role-based
access control. All operations respect the user's role on the matter.
"""

from datetime import datetime
from typing import Any

import structlog
from supabase import Client

from app.models.matter import (
    Matter,
    MatterCreate,
    MatterMember,
    MatterRole,
    MatterStatus,
    MatterUpdate,
    MatterWithMembers,
)

logger = structlog.get_logger(__name__)


class MatterServiceError(Exception):
    """Base exception for matter service errors."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MatterNotFoundError(MatterServiceError):
    """Matter not found or user has no access."""

    def __init__(self, matter_id: str):
        super().__init__(
            code="MATTER_NOT_FOUND",
            message=f"Matter not found or you don't have access",
            status_code=404,
        )


class InsufficientPermissionsError(MatterServiceError):
    """User lacks required role for operation."""

    def __init__(self, required_role: str, action: str):
        super().__init__(
            code="INSUFFICIENT_PERMISSIONS",
            message=f"Only matter {required_role}s can {action}",
            status_code=403,
        )


class MemberAlreadyExistsError(MatterServiceError):
    """User already has a role on this matter."""

    def __init__(self, email: str):
        super().__init__(
            code="MEMBER_ALREADY_EXISTS",
            message=f"User {email} is already a member of this matter",
            status_code=409,
        )


class CannotRemoveOwnerError(MatterServiceError):
    """Cannot remove the last owner from a matter."""

    def __init__(self):
        super().__init__(
            code="CANNOT_REMOVE_OWNER",
            message="Cannot remove yourself as owner. Transfer ownership first.",
            status_code=400,
        )


class UserNotFoundError(MatterServiceError):
    """User with given email not found."""

    def __init__(self, email: str):
        super().__init__(
            code="USER_NOT_FOUND",
            message=f"No user found with email: {email}",
            status_code=404,
        )


class MatterService:
    """Service for matter operations with role-based access control."""

    def __init__(self, db: Client):
        """Initialize matter service.

        Args:
            db: Supabase client for database operations.
        """
        self.db = db

    def _batch_fetch_user_info(self, user_ids: list[str]) -> dict[str, dict[str, str | None]]:
        """Batch fetch user info for multiple user IDs.

        Args:
            user_ids: List of user IDs to fetch info for.

        Returns:
            Dictionary mapping user_id to {email, full_name}.
        """
        if not user_ids:
            return {}

        # Fetch all users in a single query
        result = self.db.table("users").select("id, email, full_name").in_("id", user_ids).execute()

        return {
            user["id"]: {"email": user.get("email"), "full_name": user.get("full_name")}
            for user in result.data
        }

    def create_matter(
        self, user_id: str, data: MatterCreate
    ) -> Matter:
        """Create a new matter.

        The creating user is automatically assigned as owner via database trigger.

        Args:
            user_id: ID of the user creating the matter.
            data: Matter creation data.

        Returns:
            The created matter with owner role.
        """
        logger.info("creating_matter", user_id=user_id, title=data.title)

        # Insert matter
        result = self.db.table("matters").insert({
            "title": data.title,
            "description": data.description,
        }).execute()

        if not result.data:
            logger.error("matter_creation_failed", user_id=user_id)
            raise MatterServiceError(
                code="CREATION_FAILED",
                message="Failed to create matter",
                status_code=500,
            )

        matter_data = result.data[0]
        matter_id = matter_data["id"]

        # Explicitly create matter_attorney record for owner
        # (We do this explicitly because auth.uid() is null with service role key)
        self.db.table("matter_attorneys").insert({
            "matter_id": matter_id,
            "user_id": user_id,
            "role": "owner",
        }).execute()

        logger.info("matter_created", matter_id=matter_id, user_id=user_id)

        return Matter(
            id=matter_data["id"],
            title=matter_data["title"],
            description=matter_data.get("description"),
            status=MatterStatus(matter_data.get("status", "active")),
            created_at=datetime.fromisoformat(matter_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(matter_data["updated_at"].replace("Z", "+00:00")),
            role=MatterRole.OWNER,  # Creator is always owner
            member_count=1,  # Just the owner
        )

    def get_user_matters(
        self,
        user_id: str,
        page: int = 1,
        per_page: int = 20,
        status_filter: MatterStatus | None = None,
    ) -> tuple[list[Matter], int]:
        """Get all matters the user has access to.

        Args:
            user_id: ID of the user.
            page: Page number (1-indexed).
            per_page: Number of items per page.
            status_filter: Optional status filter.

        Returns:
            Tuple of (matters list, total count).
        """
        logger.debug("getting_user_matters", user_id=user_id, page=page)

        # Build query - RLS handles access filtering
        query = self.db.table("matters").select(
            "*, matter_attorneys!inner(role, user_id)",
            count="exact"
        ).is_("deleted_at", "null")

        if status_filter:
            query = query.eq("status", status_filter.value)

        # Add pagination
        offset = (page - 1) * per_page
        result = query.range(offset, offset + per_page - 1).order("created_at", desc=True).execute()

        total = result.count or 0
        matters = []

        for row in result.data:
            # Find user's role in the matter_attorneys join
            user_role = None
            for ma in row.get("matter_attorneys", []):
                if ma["user_id"] == user_id:
                    user_role = MatterRole(ma["role"])
                    break

            matters.append(Matter(
                id=row["id"],
                title=row["title"],
                description=row.get("description"),
                status=MatterStatus(row.get("status", "active")),
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
                role=user_role,
                member_count=len(row.get("matter_attorneys", [])),
            ))

        return matters, total

    def get_matter(
        self, matter_id: str, user_id: str
    ) -> MatterWithMembers:
        """Get a single matter with members.

        Args:
            matter_id: ID of the matter to retrieve.
            user_id: ID of the requesting user.

        Returns:
            Matter with members list.

        Raises:
            MatterNotFoundError: If matter not found or user has no access.
        """
        logger.debug("getting_matter", matter_id=matter_id, user_id=user_id)

        # RLS handles access check
        result = self.db.table("matters").select(
            "*, matter_attorneys(id, user_id, role, invited_by, invited_at)"
        ).eq("id", matter_id).is_("deleted_at", "null").execute()

        if not result.data:
            raise MatterNotFoundError(matter_id)

        row = result.data[0]
        matter_attorneys = row.get("matter_attorneys", [])

        # Batch fetch all user info in a single query (fixes N+1)
        user_ids = [ma["user_id"] for ma in matter_attorneys]
        user_info_map = self._batch_fetch_user_info(user_ids)

        # Build members list with user info
        members = []
        user_role = None

        for ma in matter_attorneys:
            user_info = user_info_map.get(ma["user_id"], {})

            member = MatterMember(
                id=ma["id"],
                user_id=ma["user_id"],
                email=user_info.get("email"),
                full_name=user_info.get("full_name"),
                role=MatterRole(ma["role"]),
                invited_by=ma.get("invited_by"),
                invited_at=datetime.fromisoformat(ma["invited_at"].replace("Z", "+00:00")) if ma.get("invited_at") else None,
            )
            members.append(member)

            if ma["user_id"] == user_id:
                user_role = MatterRole(ma["role"])

        return MatterWithMembers(
            id=row["id"],
            title=row["title"],
            description=row.get("description"),
            status=MatterStatus(row.get("status", "active")),
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            role=user_role,
            member_count=len(members),
            members=members,
        )

    def get_user_role(
        self, matter_id: str, user_id: str
    ) -> MatterRole | None:
        """Get user's role on a specific matter.

        Args:
            matter_id: ID of the matter.
            user_id: ID of the user.

        Returns:
            User's role or None if no membership.
        """
        result = self.db.table("matter_attorneys").select("role").eq(
            "matter_id", matter_id
        ).eq("user_id", user_id).execute()

        if not result.data:
            return None

        return MatterRole(result.data[0]["role"])

    def update_matter(
        self, matter_id: str, user_id: str, data: MatterUpdate
    ) -> Matter:
        """Update matter details.

        Requires editor or owner role.

        Args:
            matter_id: ID of the matter to update.
            user_id: ID of the user performing the update.
            data: Update data.

        Returns:
            Updated matter.

        Raises:
            MatterNotFoundError: If matter not found.
            InsufficientPermissionsError: If user is not editor or owner.
        """
        # Check role (RLS also handles this)
        role = self.get_user_role(matter_id, user_id)
        if role is None:
            raise MatterNotFoundError(matter_id)
        if role == MatterRole.VIEWER:
            raise InsufficientPermissionsError("owner or editor", "update matter details")

        logger.info("updating_matter", matter_id=matter_id, user_id=user_id)

        update_data: dict[str, Any] = {}
        if data.title is not None:
            update_data["title"] = data.title
        if data.description is not None:
            update_data["description"] = data.description
        if data.status is not None:
            update_data["status"] = data.status.value

        if not update_data:
            # No changes, just return current matter
            matter = self.get_matter(matter_id, user_id)
            return Matter(
                id=matter.id,
                title=matter.title,
                description=matter.description,
                status=matter.status,
                created_at=matter.created_at,
                updated_at=matter.updated_at,
                role=matter.role,
                member_count=matter.member_count,
            )

        result = self.db.table("matters").update(update_data).eq("id", matter_id).execute()

        if not result.data:
            raise MatterNotFoundError(matter_id)

        row = result.data[0]

        # Get actual member count
        member_count_result = self.db.table("matter_attorneys").select(
            "id", count="exact"
        ).eq("matter_id", matter_id).execute()
        member_count = member_count_result.count or 0

        return Matter(
            id=row["id"],
            title=row["title"],
            description=row.get("description"),
            status=MatterStatus(row.get("status", "active")),
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            role=role,
            member_count=member_count,
        )

    def delete_matter(
        self, matter_id: str, user_id: str
    ) -> None:
        """Soft-delete a matter.

        Requires owner role.

        Args:
            matter_id: ID of the matter to delete.
            user_id: ID of the user performing the delete.

        Raises:
            MatterNotFoundError: If matter not found.
            InsufficientPermissionsError: If user is not owner.
        """
        role = self.get_user_role(matter_id, user_id)
        if role is None:
            raise MatterNotFoundError(matter_id)
        if role != MatterRole.OWNER:
            raise InsufficientPermissionsError("owner", "delete matter")

        logger.info("deleting_matter", matter_id=matter_id, user_id=user_id)

        # Soft delete
        from datetime import timezone
        result = self.db.table("matters").update({
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", matter_id).execute()

        if not result.data:
            raise MatterNotFoundError(matter_id)

    def invite_member(
        self,
        matter_id: str,
        inviter_id: str,
        email: str,
        role: MatterRole,
    ) -> MatterMember:
        """Invite a new member to a matter.

        Requires owner role.

        Args:
            matter_id: ID of the matter.
            inviter_id: ID of the user sending the invite.
            email: Email of the user to invite.
            role: Role to assign.

        Returns:
            The created member record.

        Raises:
            MatterNotFoundError: If matter not found.
            InsufficientPermissionsError: If inviter is not owner.
            MemberAlreadyExistsError: If user already has a role.
            UserNotFoundError: If no user with given email.
        """
        inviter_role = self.get_user_role(matter_id, inviter_id)
        if inviter_role is None:
            raise MatterNotFoundError(matter_id)
        if inviter_role != MatterRole.OWNER:
            raise InsufficientPermissionsError("owner", "invite members")

        # Find user by email
        user_result = self.db.table("users").select("id, email, full_name").eq("email", email).execute()
        if not user_result.data:
            raise UserNotFoundError(email)

        user = user_result.data[0]
        user_id = user["id"]

        # Check if already a member
        existing = self.db.table("matter_attorneys").select("id").eq(
            "matter_id", matter_id
        ).eq("user_id", user_id).execute()

        if existing.data:
            raise MemberAlreadyExistsError(email)

        logger.info(
            "inviting_member",
            matter_id=matter_id,
            inviter_id=inviter_id,
            invitee_email=email,
            role=role.value,
        )

        # Create membership
        result = self.db.table("matter_attorneys").insert({
            "matter_id": matter_id,
            "user_id": user_id,
            "role": role.value,
            "invited_by": inviter_id,
        }).execute()

        if not result.data:
            raise MatterServiceError(
                code="INVITE_FAILED",
                message="Failed to create member invitation",
                status_code=500,
            )

        ma = result.data[0]
        return MatterMember(
            id=ma["id"],
            user_id=ma["user_id"],
            email=user.get("email"),
            full_name=user.get("full_name"),
            role=MatterRole(ma["role"]),
            invited_by=ma.get("invited_by"),
            invited_at=datetime.fromisoformat(ma["invited_at"].replace("Z", "+00:00")) if ma.get("invited_at") else None,
        )

    def get_members(
        self, matter_id: str, user_id: str
    ) -> list[MatterMember]:
        """Get all members of a matter.

        Args:
            matter_id: ID of the matter.
            user_id: ID of the requesting user.

        Returns:
            List of members.

        Raises:
            MatterNotFoundError: If matter not found or user has no access.
        """
        # Check access
        role = self.get_user_role(matter_id, user_id)
        if role is None:
            raise MatterNotFoundError(matter_id)

        result = self.db.table("matter_attorneys").select(
            "id, user_id, role, invited_by, invited_at"
        ).eq("matter_id", matter_id).execute()

        # Batch fetch all user info in a single query (fixes N+1)
        user_ids = [ma["user_id"] for ma in result.data]
        user_info_map = self._batch_fetch_user_info(user_ids)

        members = []
        for ma in result.data:
            user_info = user_info_map.get(ma["user_id"], {})

            members.append(MatterMember(
                id=ma["id"],
                user_id=ma["user_id"],
                email=user_info.get("email"),
                full_name=user_info.get("full_name"),
                role=MatterRole(ma["role"]),
                invited_by=ma.get("invited_by"),
                invited_at=datetime.fromisoformat(ma["invited_at"].replace("Z", "+00:00")) if ma.get("invited_at") else None,
            ))

        return members

    def update_member_role(
        self,
        matter_id: str,
        requester_id: str,
        member_user_id: str,
        new_role: MatterRole,
    ) -> MatterMember:
        """Update a member's role.

        Requires owner role. Cannot demote self from owner.

        Args:
            matter_id: ID of the matter.
            requester_id: ID of the user making the request.
            member_user_id: ID of the member to update.
            new_role: New role to assign.

        Returns:
            Updated member record.

        Raises:
            MatterNotFoundError: If matter not found.
            InsufficientPermissionsError: If requester is not owner.
            CannotRemoveOwnerError: If trying to demote self from owner.
        """
        requester_role = self.get_user_role(matter_id, requester_id)
        if requester_role is None:
            raise MatterNotFoundError(matter_id)
        if requester_role != MatterRole.OWNER:
            raise InsufficientPermissionsError("owner", "update member roles")

        # Check if trying to demote self from owner
        if requester_id == member_user_id and new_role != MatterRole.OWNER:
            raise CannotRemoveOwnerError()

        logger.info(
            "updating_member_role",
            matter_id=matter_id,
            requester_id=requester_id,
            member_user_id=member_user_id,
            new_role=new_role.value,
        )

        result = self.db.table("matter_attorneys").update({
            "role": new_role.value,
        }).eq("matter_id", matter_id).eq("user_id", member_user_id).execute()

        if not result.data:
            raise MatterNotFoundError(matter_id)

        ma = result.data[0]

        # Get user info (single lookup, consistent with batch pattern)
        user_info_map = self._batch_fetch_user_info([member_user_id])
        user_info = user_info_map.get(member_user_id, {})

        return MatterMember(
            id=ma["id"],
            user_id=ma["user_id"],
            email=user_info.get("email"),
            full_name=user_info.get("full_name"),
            role=MatterRole(ma["role"]),
            invited_by=ma.get("invited_by"),
            invited_at=datetime.fromisoformat(ma["invited_at"].replace("Z", "+00:00")) if ma.get("invited_at") else None,
        )

    def remove_member(
        self,
        matter_id: str,
        requester_id: str,
        member_user_id: str,
    ) -> None:
        """Remove a member from a matter.

        Requires owner role. Cannot remove self.

        Args:
            matter_id: ID of the matter.
            requester_id: ID of the user making the request.
            member_user_id: ID of the member to remove.

        Raises:
            MatterNotFoundError: If matter not found.
            InsufficientPermissionsError: If requester is not owner.
            CannotRemoveOwnerError: If trying to remove self.
        """
        requester_role = self.get_user_role(matter_id, requester_id)
        if requester_role is None:
            raise MatterNotFoundError(matter_id)
        if requester_role != MatterRole.OWNER:
            raise InsufficientPermissionsError("owner", "remove members")

        # Cannot remove self
        if requester_id == member_user_id:
            raise CannotRemoveOwnerError()

        logger.info(
            "removing_member",
            matter_id=matter_id,
            requester_id=requester_id,
            member_user_id=member_user_id,
        )

        result = self.db.table("matter_attorneys").delete().eq(
            "matter_id", matter_id
        ).eq("user_id", member_user_id).execute()

        if not result.data:
            raise MatterNotFoundError(matter_id)
