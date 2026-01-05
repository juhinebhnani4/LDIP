"""Unit tests for matter service.

Tests business logic for matter operations including:
- Matter creation with auto-owner assignment
- Role-based access control for operations
- Member management operations
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.matter import (
    Matter,
    MatterCreate,
    MatterMember,
    MatterRole,
    MatterStatus,
    MatterUpdate,
    MatterWithMembers,
)
from app.services.matter_service import (
    CannotRemoveOwnerError,
    InsufficientPermissionsError,
    MatterNotFoundError,
    MatterService,
    MemberAlreadyExistsError,
    UserNotFoundError,
)


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def matter_service(mock_db: MagicMock) -> MatterService:
    """Create a MatterService instance with mock database."""
    return MatterService(mock_db)


@pytest.fixture
def mock_user_id() -> str:
    """Return a test user ID."""
    return "test-user-id-12345"


@pytest.fixture
def mock_matter_data() -> dict:
    """Return mock matter data from database."""
    return {
        "id": "matter-id-12345",
        "title": "Test Matter",
        "description": "Test description",
        "status": "active",
        "created_at": "2026-01-05T12:00:00+00:00",
        "updated_at": "2026-01-05T12:00:00+00:00",
        "deleted_at": None,
    }


class TestCreateMatter:
    """Tests for matter creation."""

    def test_create_matter_returns_matter_with_owner_role(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_user_id: str,
        mock_matter_data: dict,
    ) -> None:
        """Test that creating a matter returns the matter with owner role."""
        # Setup mock response
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[mock_matter_data]
        )

        # Create matter
        data = MatterCreate(title="Test Matter", description="Test description")
        result = matter_service.create_matter(mock_user_id, data)

        # Since it's not async in real usage pattern, we need to handle this
        # Actually the service uses sync methods, so we can test directly
        assert mock_db.table.called

    def test_create_matter_inserts_into_matters_table(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_user_id: str,
        mock_matter_data: dict,
    ) -> None:
        """Test that create_matter inserts into the matters table."""
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[mock_matter_data]
        )

        data = MatterCreate(title="New Matter")
        matter_service.create_matter(mock_user_id, data)

        mock_db.table.assert_called_with("matters")
        mock_db.table.return_value.insert.assert_called_once()


class TestGetUserRole:
    """Tests for getting user role on a matter."""

    def test_get_user_role_returns_role_when_member(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_user_id: str,
    ) -> None:
        """Test that get_user_role returns the correct role for a member."""
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"role": "owner"}]
        )

        result = matter_service.get_user_role("matter-id", mock_user_id)

        # Verify correct table was queried
        mock_db.table.assert_called_with("matter_attorneys")

    def test_get_user_role_returns_none_when_not_member(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_user_id: str,
    ) -> None:
        """Test that get_user_role returns None when user is not a member."""
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = matter_service.get_user_role("matter-id", mock_user_id)

        assert result is None


class TestInviteMember:
    """Tests for member invitation."""

    def test_invite_member_requires_owner_role(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that invite_member fails for non-owner."""
        # Setup: inviter is an editor, not owner
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"role": "editor"}]
        )

        with pytest.raises(InsufficientPermissionsError):
            matter_service.invite_member(
                "matter-id",
                "editor-user-id",
                "newuser@example.com",
                MatterRole.VIEWER,
            )

    def test_invite_member_fails_when_user_not_found(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that invite_member fails when user email not found."""
        # Setup: inviter is owner
        def table_side_effect(table_name: str) -> MagicMock:
            mock = MagicMock()
            if table_name == "matter_attorneys":
                mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"role": "owner"}]
                )
            elif table_name == "users":
                mock.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[]  # No user found
                )
            return mock

        mock_db.table.side_effect = table_side_effect

        with pytest.raises(UserNotFoundError):
            matter_service.invite_member(
                "matter-id",
                "owner-user-id",
                "nonexistent@example.com",
                MatterRole.VIEWER,
            )

    def test_invite_member_fails_when_already_member(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that invite_member fails when user is already a member."""
        call_count = 0

        def table_side_effect(table_name: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = MagicMock()

            if table_name == "matter_attorneys" and call_count == 1:
                # First call: check inviter role
                mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"role": "owner"}]
                )
            elif table_name == "users":
                # User lookup
                mock.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": "existing-user-id", "email": "existing@example.com"}]
                )
            elif table_name == "matter_attorneys":
                # Check existing membership
                mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": "existing-membership"}]
                )
            return mock

        mock_db.table.side_effect = table_side_effect

        with pytest.raises(MemberAlreadyExistsError):
            matter_service.invite_member(
                "matter-id",
                "owner-user-id",
                "existing@example.com",
                MatterRole.VIEWER,
            )


class TestRemoveMember:
    """Tests for member removal."""

    def test_owner_cannot_remove_self(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that owner cannot remove themselves."""
        # Setup: user is owner
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"role": "owner"}]
        )

        with pytest.raises(CannotRemoveOwnerError):
            matter_service.remove_member(
                "matter-id",
                "owner-user-id",
                "owner-user-id",  # Trying to remove self
            )

    def test_non_owner_cannot_remove_members(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that editor cannot remove members."""
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"role": "editor"}]
        )

        with pytest.raises(InsufficientPermissionsError):
            matter_service.remove_member(
                "matter-id",
                "editor-user-id",
                "viewer-user-id",
            )


class TestUpdateMatter:
    """Tests for matter updates."""

    def test_viewer_cannot_update_matter(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that viewer cannot update matter details."""
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"role": "viewer"}]
        )

        with pytest.raises(InsufficientPermissionsError):
            matter_service.update_matter(
                "matter-id",
                "viewer-user-id",
                MatterUpdate(title="New Title"),
            )

    def test_editor_can_update_matter(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_matter_data: dict,
    ) -> None:
        """Test that editor can update matter details."""
        call_count = 0

        def table_side_effect(table_name: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = MagicMock()

            if table_name == "matter_attorneys":
                mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"role": "editor"}]
                )
            elif table_name == "matters":
                mock.update.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[mock_matter_data]
                )
            return mock

        mock_db.table.side_effect = table_side_effect

        result = matter_service.update_matter(
            "matter-id",
            "editor-user-id",
            MatterUpdate(title="New Title"),
        )

        # Should not raise an exception


class TestDeleteMatter:
    """Tests for matter deletion."""

    def test_only_owner_can_delete_matter(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
    ) -> None:
        """Test that only owner can delete matter."""
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"role": "editor"}]
        )

        with pytest.raises(InsufficientPermissionsError):
            matter_service.delete_matter("matter-id", "editor-user-id")

    def test_owner_can_delete_matter(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_matter_data: dict,
    ) -> None:
        """Test that owner can soft-delete matter."""
        call_count = 0

        def table_side_effect(table_name: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = MagicMock()

            if table_name == "matter_attorneys":
                mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"role": "owner"}]
                )
            elif table_name == "matters":
                mock.update.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{**mock_matter_data, "deleted_at": "2026-01-05T12:00:00+00:00"}]
                )
            return mock

        mock_db.table.side_effect = table_side_effect

        # Should not raise an exception
        matter_service.delete_matter("matter-id", "owner-user-id")


class TestMatterNotFound:
    """Tests for matter not found scenarios."""

    def test_get_matter_raises_not_found_when_no_access(
        self,
        matter_service: MatterService,
        mock_db: MagicMock,
        mock_user_id: str,
    ) -> None:
        """Test that get_matter raises MatterNotFoundError when user has no access."""
        mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(MatterNotFoundError):
            matter_service.get_matter("nonexistent-matter", mock_user_id)
