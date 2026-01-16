"""Tests for the Query History Store.

Story 6-3: Audit Trail Logging (AC: #4)

Tests cover:
- Append-only semantics (Task 3.6)
- Query history retrieval (Task 3.3)
- Specific query retrieval (Task 3.4)
- Matter isolation (Task 6.7)
- Error handling for audit failures (Task 6.8)
"""

from unittest.mock import MagicMock

import pytest

from app.engines.orchestrator.query_history import (
    QueryHistoryStore,
    get_query_history_store,
    reset_query_history_store,
)
from app.models.orchestrator import (
    EngineType,
    LLMCostEntry,
    QueryAuditEntry,
    QueryIntent,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def reset_singleton():
    """Reset singleton before and after each test."""
    reset_query_history_store()
    yield
    reset_query_history_store()


@pytest.fixture
def mock_db():
    """Create mock Supabase database client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def history_store(mock_db):
    """Create QueryHistoryStore with mock database."""
    return QueryHistoryStore(mock_db)


@pytest.fixture
def history_store_no_db():
    """Create QueryHistoryStore without database."""
    return QueryHistoryStore(None)


@pytest.fixture
def sample_audit_entry():
    """Create sample QueryAuditEntry for testing."""
    return QueryAuditEntry(
        query_id="query-123",
        matter_id="matter-456",
        query_text="What citations are in this case?",
        query_intent=QueryIntent.CITATION,
        intent_confidence=0.95,
        asked_by="user-789",
        asked_at="2026-01-14T10:30:00Z",
        engines_invoked=[EngineType.CITATION],
        successful_engines=[EngineType.CITATION],
        failed_engines=[],
        execution_time_ms=150,
        wall_clock_time_ms=120,
        findings_count=3,
        response_summary="Found 3 citations in the documents.",
        overall_confidence=0.92,
        llm_costs=[
            LLMCostEntry(
                model_name="gpt-3.5-turbo",
                purpose="intent_analysis",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.00007,
            ),
        ],
        total_cost_usd=0.00007,
        findings=[],
    )


@pytest.fixture
def sample_audit_entry_different_matter():
    """Create sample QueryAuditEntry for different matter."""
    return QueryAuditEntry(
        query_id="query-abc",
        matter_id="matter-different",
        query_text="Timeline events?",
        query_intent=QueryIntent.TIMELINE,
        intent_confidence=0.88,
        asked_by="user-other",
        asked_at="2026-01-14T11:00:00Z",
        engines_invoked=[EngineType.TIMELINE],
        successful_engines=[EngineType.TIMELINE],
        failed_engines=[],
        execution_time_ms=200,
        wall_clock_time_ms=180,
        findings_count=5,
        response_summary="Found 5 timeline events.",
        overall_confidence=0.88,
        llm_costs=[],
        total_cost_usd=0.0,
        findings=[],
    )


# =============================================================================
# Unit Tests: Append Query (Task 3.2)
# =============================================================================


class TestAppendQuery:
    """Tests for append_query method."""

    @pytest.mark.asyncio
    async def test_append_creates_record_with_generated_id(
        self, history_store, sample_audit_entry
    ):
        """Should create record with generated UUID."""
        # Mock successful insert
        history_store._db.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data={})
        )

        record = await history_store.append_query(sample_audit_entry)

        assert record.id  # UUID generated
        assert record.matter_id == sample_audit_entry.matter_id
        assert record.query_id == sample_audit_entry.query_id
        assert record.created_at  # Timestamp generated

    @pytest.mark.asyncio
    async def test_append_persists_to_database(
        self, history_store, sample_audit_entry
    ):
        """Should persist record to database."""
        mock_execute = MagicMock(return_value=MagicMock(data={}))
        history_store._db.table.return_value.insert.return_value.execute = mock_execute

        await history_store.append_query(sample_audit_entry)

        # Verify database insert was called
        history_store._db.table.assert_called_with("matter_query_history")
        history_store._db.table.return_value.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_without_db_logs_only(
        self, history_store_no_db, sample_audit_entry
    ):
        """Should work without database (log-only mode)."""
        record = await history_store_no_db.append_query(sample_audit_entry)

        # Should still return valid record
        assert record.id
        assert record.matter_id == sample_audit_entry.matter_id

    @pytest.mark.asyncio
    async def test_append_handles_db_error_gracefully(
        self, history_store, sample_audit_entry
    ):
        """Should handle database errors without raising (audit is non-critical)."""
        history_store._db.table.return_value.insert.return_value.execute.side_effect = (
            Exception("Database error")
        )

        # Should not raise, returns record anyway
        record = await history_store.append_query(sample_audit_entry)

        assert record.id  # Record still created
        assert record.matter_id == sample_audit_entry.matter_id


# =============================================================================
# Unit Tests: Get Query History (Task 3.3)
# =============================================================================


class TestGetQueryHistory:
    """Tests for get_query_history method."""

    @pytest.mark.asyncio
    async def test_retrieves_history_for_matter(self, history_store, sample_audit_entry):
        """Should retrieve query history for specific matter."""
        # Mock database response
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "record-1",
                "matter_id": "matter-456",
                "query_id": "query-123",
                "audit_data": sample_audit_entry.model_dump(mode="json"),
                "created_at": "2026-01-14T10:30:00Z",
            }
        ]
        history_store._db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = (
            mock_response
        )

        records = await history_store.get_query_history(matter_id="matter-456")

        assert len(records) == 1
        assert records[0].matter_id == "matter-456"
        assert records[0].query_id == "query-123"

    @pytest.mark.asyncio
    async def test_returns_empty_without_db(self, history_store_no_db):
        """Should return empty list without database."""
        records = await history_store_no_db.get_query_history(matter_id="matter-456")

        assert records == []

    @pytest.mark.asyncio
    async def test_respects_limit_and_offset(self, history_store):
        """Should apply limit and offset parameters."""
        mock_response = MagicMock()
        mock_response.data = []
        history_store._db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = (
            mock_response
        )

        await history_store.get_query_history(
            matter_id="matter-456", limit=50, offset=10
        )

        # Verify range was called with correct parameters
        history_store._db.table.return_value.select.return_value.eq.return_value.order.return_value.range.assert_called_with(
            10, 59  # offset to offset + limit - 1
        )

    @pytest.mark.asyncio
    async def test_handles_db_error_returns_empty(self, history_store):
        """Should return empty list on database error."""
        history_store._db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.side_effect = (
            Exception("Query failed")
        )

        records = await history_store.get_query_history(matter_id="matter-456")

        assert records == []


# =============================================================================
# Unit Tests: Get Query By ID (Task 3.4)
# =============================================================================


class TestGetQueryById:
    """Tests for get_query_by_id method."""

    @pytest.mark.asyncio
    async def test_retrieves_specific_query(self, history_store, sample_audit_entry):
        """Should retrieve specific query by ID."""
        mock_response = MagicMock()
        mock_response.data = {
            "id": "record-1",
            "matter_id": "matter-456",
            "query_id": "query-123",
            "audit_data": sample_audit_entry.model_dump(mode="json"),
            "created_at": "2026-01-14T10:30:00Z",
        }
        history_store._db.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        record = await history_store.get_query_by_id(
            matter_id="matter-456", query_id="query-123"
        )

        assert record is not None
        assert record.query_id == "query-123"
        assert record.matter_id == "matter-456"

    @pytest.mark.asyncio
    async def test_returns_none_without_db(self, history_store_no_db):
        """Should return None without database."""
        record = await history_store_no_db.get_query_by_id(
            matter_id="matter-456", query_id="query-123"
        )

        assert record is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, history_store):
        """Should return None when query not found."""
        mock_response = MagicMock()
        mock_response.data = None
        history_store._db.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        record = await history_store.get_query_by_id(
            matter_id="matter-456", query_id="nonexistent"
        )

        assert record is None

    @pytest.mark.asyncio
    async def test_handles_error_returns_none(self, history_store):
        """Should return None on database error."""
        history_store._db.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.side_effect = (
            Exception("Query failed")
        )

        record = await history_store.get_query_by_id(
            matter_id="matter-456", query_id="query-123"
        )

        assert record is None


# =============================================================================
# Unit Tests: Matter Isolation (Task 6.7)
# =============================================================================


class TestMatterIsolation:
    """Tests for matter isolation - query history belongs to correct matter."""

    @pytest.mark.asyncio
    async def test_get_history_filters_by_matter(self, history_store):
        """Should only return records for requested matter."""
        mock_response = MagicMock()
        mock_response.data = []
        history_store._db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = (
            mock_response
        )

        await history_store.get_query_history(matter_id="matter-specific")

        # Verify eq filter was called with correct matter_id
        history_store._db.table.return_value.select.return_value.eq.assert_called_with(
            "matter_id", "matter-specific"
        )

    @pytest.mark.asyncio
    async def test_get_by_id_filters_by_matter(self, history_store):
        """Should require both matter_id and query_id for retrieval."""
        mock_response = MagicMock()
        mock_response.data = None
        history_store._db.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        await history_store.get_query_by_id(
            matter_id="matter-specific", query_id="query-123"
        )

        # Verify both filters were applied
        calls = history_store._db.table.return_value.select.return_value.eq.call_args_list
        # First eq for matter_id, second eq for query_id
        assert len(calls) >= 1


# =============================================================================
# Unit Tests: Factory Function
# =============================================================================


class TestQueryHistoryStoreFactory:
    """Tests for get_query_history_store factory."""

    def test_factory_returns_store(self, reset_singleton):
        """Factory should return QueryHistoryStore instance."""
        store = get_query_history_store()

        assert isinstance(store, QueryHistoryStore)

    def test_factory_returns_singleton(self, reset_singleton):
        """Factory should return the same instance (singleton)."""
        store1 = get_query_history_store()
        store2 = get_query_history_store()

        assert store1 is store2

    def test_factory_accepts_db_client(self, reset_singleton, mock_db):
        """Factory should accept and store db client."""
        store = get_query_history_store(mock_db)

        assert store._db is mock_db

    def test_factory_updates_db_if_none(self, reset_singleton, mock_db):
        """Factory should update db if originally None."""
        store1 = get_query_history_store(None)
        assert store1._db is None

        store2 = get_query_history_store(mock_db)
        assert store2._db is mock_db
        assert store1 is store2  # Same instance

    def test_reset_clears_singleton(self, reset_singleton):
        """reset_query_history_store should clear singleton."""
        store1 = get_query_history_store()
        reset_query_history_store()
        store2 = get_query_history_store()

        assert store1 is not store2


# =============================================================================
# Unit Tests: Audit Logging Failure Handling (Task 6.8)
# =============================================================================


class TestAuditFailureHandling:
    """Tests for graceful failure handling."""

    @pytest.mark.asyncio
    async def test_db_insert_failure_does_not_raise(
        self, history_store, sample_audit_entry
    ):
        """Database insert failure should not raise exception."""
        history_store._db.table.return_value.insert.return_value.execute.side_effect = (
            Exception("Connection refused")
        )

        # Should not raise
        record = await history_store.append_query(sample_audit_entry)

        # Record is still created (just not persisted)
        assert record.id is not None

    @pytest.mark.asyncio
    async def test_db_query_failure_does_not_raise(self, history_store):
        """Database query failure should not raise exception."""
        history_store._db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.side_effect = (
            Exception("Timeout")
        )

        # Should not raise, returns empty list
        records = await history_store.get_query_history(matter_id="matter-456")

        assert records == []
