"""Tests for activity service.

Story 14.5: Dashboard Real APIs

Test Categories:
- Activity creation
- Activity retrieval
- Mark as read
- Unread count
- Activity creation for matter members
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.activity import ActivityTypeEnum
from app.services.activity_service import (
    ActivityService,
    ActivityServiceError,
)


@pytest.fixture
def activity_service():
    """Get activity service instance."""
    return ActivityService()


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    return MagicMock()


def create_mock_activity_row(
    activity_id: str | None = None,
    user_id: str | None = None,
    matter_id: str | None = None,
    activity_type: str = "processing_complete",
    description: str = "Test activity",
    is_read: bool = False,
) -> dict:
    """Create mock activity database row."""
    return {
        "id": activity_id or str(uuid4()),
        "user_id": user_id or str(uuid4()),
        "matter_id": matter_id,
        "type": activity_type,
        "description": description,
        "metadata": {},
        "is_read": is_read,
        "created_at": datetime.now(UTC).isoformat(),
    }


class TestActivityCreation:
    """Test activity creation."""

    @pytest.mark.asyncio
    async def test_creates_activity_successfully(
        self, activity_service, mock_supabase
    ) -> None:
        """Should create activity with correct data."""
        user_id = str(uuid4())
        matter_id = str(uuid4())
        activity_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = [
            create_mock_activity_row(
                activity_id=activity_id,
                user_id=user_id,
                matter_id=matter_id,
                activity_type="processing_complete",
                description="Document processing complete",
            )
        ]

        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            result = await activity_service.create_activity(
                user_id=user_id,
                type=ActivityTypeEnum.PROCESSING_COMPLETE,
                description="Document processing complete",
                matter_id=matter_id,
                metadata={"doc_count": 5},
            )

        assert result.id == activity_id
        assert result.type == ActivityTypeEnum.PROCESSING_COMPLETE
        assert result.description == "Document processing complete"
        assert result.is_read is False

    @pytest.mark.asyncio
    async def test_creates_activity_without_matter_id(
        self, activity_service, mock_supabase
    ) -> None:
        """Should create activity without matter_id."""
        user_id = str(uuid4())
        activity_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = [
            create_mock_activity_row(
                activity_id=activity_id,
                user_id=user_id,
                matter_id=None,
                activity_type="matter_opened",
                description="Matter opened",
            )
        ]

        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            result = await activity_service.create_activity(
                user_id=user_id,
                type=ActivityTypeEnum.MATTER_OPENED,
                description="Matter opened",
            )

        assert result.id == activity_id
        assert result.matter_id is None

    @pytest.mark.asyncio
    async def test_create_activity_handles_insert_failure(
        self, activity_service, mock_supabase
    ) -> None:
        """Should raise error when insert fails."""
        user_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = []  # Empty result = failure

        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ), pytest.raises(ActivityServiceError) as exc_info:
            await activity_service.create_activity(
                user_id=user_id,
                type=ActivityTypeEnum.PROCESSING_COMPLETE,
                description="Test",
            )

        assert exc_info.value.code == "INSERT_FAILED"


class TestActivityRetrieval:
    """Test activity retrieval."""

    @pytest.mark.asyncio
    async def test_gets_activities_successfully(
        self, activity_service, mock_supabase
    ) -> None:
        """Should retrieve activities for user."""
        user_id = str(uuid4())
        matter_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = [
            {
                **create_mock_activity_row(
                    user_id=user_id,
                    matter_id=matter_id,
                    activity_type="processing_complete",
                ),
                "matters": {"title": "Test Matter"},
            }
        ]

        mock_count_result = MagicMock()
        mock_count_result.count = 1

        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            mock_result
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_count_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            activities, total = await activity_service.get_activities(
                user_id=user_id, limit=10
            )

        assert len(activities) == 1
        assert activities[0].matter_name == "Test Matter"
        assert total == 1

    @pytest.mark.asyncio
    async def test_limits_activities_to_max(
        self, activity_service, mock_supabase
    ) -> None:
        """Should clamp limit to 50 max."""
        user_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = []
        mock_count_result = MagicMock()
        mock_count_result.count = 0

        mock_query = MagicMock()
        mock_query.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            mock_result
        )

        mock_supabase.table.return_value.select.return_value = mock_query
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_count_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            await activity_service.get_activities(user_id=user_id, limit=100)

        # Verify limit was clamped to 50
        mock_query.eq.return_value.order.return_value.limit.assert_called_with(50)


class TestMarkAsRead:
    """Test marking activities as read."""

    @pytest.mark.asyncio
    async def test_marks_activity_as_read(
        self, activity_service, mock_supabase
    ) -> None:
        """Should mark activity as read."""
        user_id = str(uuid4())
        activity_id = str(uuid4())
        matter_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = [
            {
                **create_mock_activity_row(
                    activity_id=activity_id,
                    user_id=user_id,
                    matter_id=matter_id,
                    is_read=True,
                ),
                "matters": {"title": "Test Matter"},
            }
        ]

        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.select.return_value.execute.return_value = (
            mock_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            result = await activity_service.mark_as_read(
                activity_id=activity_id, user_id=user_id
            )

        assert result is not None
        assert result.is_read is True

    @pytest.mark.asyncio
    async def test_returns_none_for_not_found_activity(
        self, activity_service, mock_supabase
    ) -> None:
        """Should return None when activity not found."""
        user_id = str(uuid4())
        activity_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.data = []

        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.select.return_value.execute.return_value = (
            mock_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            result = await activity_service.mark_as_read(
                activity_id=activity_id, user_id=user_id
            )

        assert result is None


class TestUnreadCount:
    """Test unread count retrieval."""

    @pytest.mark.asyncio
    async def test_gets_unread_count(
        self, activity_service, mock_supabase
    ) -> None:
        """Should return count of unread activities."""
        user_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.count = 5

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            count = await activity_service.get_unread_count(user_id=user_id)

        assert count == 5


class TestCreateActivityForMatterMembers:
    """Test activity creation for all matter members."""

    @pytest.mark.asyncio
    async def test_creates_activities_for_all_members(
        self, activity_service, mock_supabase
    ) -> None:
        """Should create activities for all matter members."""
        matter_id = str(uuid4())
        user_ids = [str(uuid4()), str(uuid4()), str(uuid4())]

        # Mock matter_attorneys query
        mock_members_result = MagicMock()
        mock_members_result.data = [{"user_id": uid} for uid in user_ids]

        # Mock activities insert
        mock_insert_result = MagicMock()
        mock_insert_result.data = [
            create_mock_activity_row(user_id=uid, matter_id=matter_id)
            for uid in user_ids
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_members_result
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_insert_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            count = await activity_service.create_activity_for_matter_members(
                matter_id=matter_id,
                type=ActivityTypeEnum.PROCESSING_COMPLETE,
                description="Processing complete",
            )

        assert count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_for_no_members(
        self, activity_service, mock_supabase
    ) -> None:
        """Should return 0 when matter has no members."""
        matter_id = str(uuid4())

        mock_members_result = MagicMock()
        mock_members_result.data = []

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_members_result
        )

        with patch.object(
            activity_service, "_supabase_client", mock_supabase
        ):
            count = await activity_service.create_activity_for_matter_members(
                matter_id=matter_id,
                type=ActivityTypeEnum.PROCESSING_COMPLETE,
                description="Processing complete",
            )

        assert count == 0
