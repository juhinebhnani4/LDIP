"""Tests for Matter Memory Service.

Story 7-3: Matter Memory PostgreSQL JSONB Storage
Story 7-4: Key Findings and Research Notes
Task 5.3: Unit tests for MatterMemoryService facade methods.
Task 5.4: Unit tests for Key Findings and Research Notes service methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.memory import (
    CachedEntity,
    EntityGraphCache,
    EntityRelationship,
    FindingEvidence,
    KeyFinding,
    KeyFindings,
    QueryHistory,
    QueryHistoryEntry,
    ResearchNote,
    ResearchNotes,
    TimelineCache,
    TimelineCacheEntry,
)
from app.services.memory.matter_service import (
    MatterMemoryService,
    get_matter_memory_service,
    reset_matter_memory_service,
)


# Valid UUIDs for testing
MATTER_ID = "12345678-1234-1234-1234-123456789abc"
USER_ID = "abcdefab-abcd-abcd-abcd-abcdefabcdef"


@pytest.fixture
def mock_repository() -> MagicMock:
    """Create a mock MatterMemoryRepository."""
    mock = MagicMock()

    # Setup async mock methods
    mock.append_query = AsyncMock(return_value="record-id")
    mock.get_query_history = AsyncMock(return_value=QueryHistory(entries=[]))
    mock.get_timeline_cache = AsyncMock(return_value=None)
    mock.set_timeline_cache = AsyncMock(return_value="record-id")
    mock.invalidate_timeline_cache = AsyncMock(return_value=True)
    mock.get_entity_graph_cache = AsyncMock(return_value=None)
    mock.set_entity_graph_cache = AsyncMock(return_value="record-id")
    mock.invalidate_entity_graph_cache = AsyncMock(return_value=True)
    mock.set_memory = AsyncMock(return_value="record-id")

    # Story 7-4: Key Findings and Research Notes mocks
    mock.get_key_findings = AsyncMock(return_value=KeyFindings(findings=[]))
    mock.add_key_finding = AsyncMock(return_value="record-id")
    mock.update_key_finding = AsyncMock(return_value=True)
    mock.delete_key_finding = AsyncMock(return_value=True)
    mock.get_key_finding_by_id = AsyncMock(return_value=None)

    mock.get_research_notes = AsyncMock(return_value=ResearchNotes(notes=[]))
    mock.add_research_note = AsyncMock(return_value="record-id")
    mock.update_research_note = AsyncMock(return_value=True)
    mock.delete_research_note = AsyncMock(return_value=True)
    mock.get_research_note_by_id = AsyncMock(return_value=None)
    mock.search_research_notes = AsyncMock(return_value=[])

    return mock


@pytest.fixture
def service(mock_repository: MagicMock) -> MatterMemoryService:
    """Create a MatterMemoryService with mock repository."""
    reset_matter_memory_service()
    return MatterMemoryService(mock_repository)


class TestLogQuery:
    """Tests for log_query method (Story 7-3: Task 5.3)."""

    @pytest.mark.asyncio
    async def test_log_query_basic(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should log query with required fields."""
        result = await service.log_query(
            matter_id=MATTER_ID,
            query_id="query-123",
            query_text="What is the timeline?",
            asked_by=USER_ID,
        )

        assert result == "record-id"
        mock_repository.append_query.assert_called_once()

        call_args = mock_repository.append_query.call_args
        assert call_args[0][0] == MATTER_ID
        entry = call_args[0][1]
        assert entry.query_id == "query-123"
        assert entry.query_text == "What is the timeline?"
        assert entry.asked_by == USER_ID

    @pytest.mark.asyncio
    async def test_log_query_with_optional_fields(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should log query with all optional fields."""
        result = await service.log_query(
            matter_id=MATTER_ID,
            query_id="query-123",
            query_text="What is the timeline?",
            asked_by=USER_ID,
            normalized_query="timeline",
            response_summary="Events from 2020-2025",
            engines_used=["timeline", "citation"],
            confidence=85.0,
            tokens_used=1500,
            cost_usd=0.045,
        )

        call_args = mock_repository.append_query.call_args
        entry = call_args[0][1]
        assert entry.normalized_query == "timeline"
        assert entry.engines_used == ["timeline", "citation"]
        assert entry.confidence == 85.0
        assert entry.tokens_used == 1500
        assert entry.cost_usd == 0.045


class TestGetQueryHistory:
    """Tests for get_query_history method."""

    @pytest.mark.asyncio
    async def test_get_query_history_delegates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should delegate to repository."""
        mock_repository.get_query_history.return_value = QueryHistory(
            entries=[
                QueryHistoryEntry(
                    query_id="q1",
                    query_text="Test",
                    asked_by=USER_ID,
                    asked_at="2026-01-14T10:00:00Z",
                )
            ]
        )

        history = await service.get_query_history(MATTER_ID, limit=50)

        mock_repository.get_query_history.assert_called_once_with(MATTER_ID, 50)
        assert len(history.entries) == 1


class TestMarkQueryVerified:
    """Tests for mark_query_verified method."""

    @pytest.mark.asyncio
    async def test_mark_query_verified_success(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should mark query as verified."""
        mock_repository.get_query_history.return_value = QueryHistory(
            entries=[
                QueryHistoryEntry(
                    query_id="query-123",
                    query_text="Test",
                    asked_by=USER_ID,
                    asked_at="2026-01-14T10:00:00Z",
                    verified=False,
                )
            ]
        )

        result = await service.mark_query_verified(
            matter_id=MATTER_ID,
            query_id="query-123",
            verified_by="attorney-456",
        )

        assert result is True
        mock_repository.set_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_query_verified_not_found(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return False when query not found."""
        mock_repository.get_query_history.return_value = QueryHistory(entries=[])

        result = await service.mark_query_verified(
            matter_id=MATTER_ID,
            query_id="nonexistent",
            verified_by="attorney-456",
        )

        assert result is False
        mock_repository.set_memory.assert_not_called()


class TestGetOrBuildTimeline:
    """Tests for get_or_build_timeline method."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return cached timeline when valid."""
        cached = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
        )
        mock_repository.get_timeline_cache.return_value = cached

        # No docs uploaded after cache = not stale
        result = await service.get_or_build_timeline(
            matter_id=MATTER_ID,
            last_document_upload=None,
        )

        assert result is cached
        mock_repository.set_timeline_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_no_builder(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return None when no cache and no builder."""
        mock_repository.get_timeline_cache.return_value = None

        result = await service.get_or_build_timeline(MATTER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_stale_rebuilds(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should rebuild when cache is stale."""
        # Stale cache
        stale_cache = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
            version=1,
        )
        mock_repository.get_timeline_cache.return_value = stale_cache

        # Builder function
        async def builder(matter_id: str) -> list[TimelineCacheEntry]:
            return [
                TimelineCacheEntry(
                    event_id="evt-1",
                    event_date="2025-01-01",
                    event_type="filing",
                    description="New filing",
                )
            ]

        # Doc uploaded after cache = stale
        result = await service.get_or_build_timeline(
            matter_id=MATTER_ID,
            last_document_upload="2026-01-14T12:00:00Z",
            builder_fn=builder,
        )

        assert result is not None
        assert result.event_count == 1
        assert result.version == 2  # Incremented
        mock_repository.set_timeline_cache.assert_called_once()


class TestSetTimelineCache:
    """Tests for set_timeline_cache method."""

    @pytest.mark.asyncio
    async def test_set_timeline_cache_creates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create new timeline cache."""
        events = [
            TimelineCacheEntry(
                event_id="evt-1",
                event_date="2025-01-01",
                event_type="filing",
                description="Filing",
            ),
            TimelineCacheEntry(
                event_id="evt-2",
                event_date="2025-06-15",
                event_type="hearing",
                description="Hearing",
            ),
        ]

        cache = await service.set_timeline_cache(
            matter_id=MATTER_ID,
            events=events,
            last_document_upload="2026-01-14T10:00:00Z",
        )

        assert cache.event_count == 2
        assert cache.version == 1  # First version
        # Events should be sorted
        assert cache.events[0].event_date == "2025-01-01"
        assert cache.events[1].event_date == "2025-06-15"


class TestGetOrBuildEntityGraph:
    """Tests for get_or_build_entity_graph method."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return cached entity graph when valid."""
        cached = EntityGraphCache(
            cached_at="2026-01-14T10:00:00Z",
            entities={},
            relationships=[],
            entity_count=0,
            relationship_count=0,
        )
        mock_repository.get_entity_graph_cache.return_value = cached

        result = await service.get_or_build_entity_graph(
            matter_id=MATTER_ID,
            last_document_upload=None,
        )

        assert result is cached
        mock_repository.set_entity_graph_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_no_builder(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return None when no cache and no builder."""
        mock_repository.get_entity_graph_cache.return_value = None

        result = await service.get_or_build_entity_graph(MATTER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_stale_rebuilds(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should rebuild when entity graph cache is stale (Issue 3 fix)."""
        # Stale cache - created before document upload
        stale_cache = EntityGraphCache(
            cached_at="2026-01-14T10:00:00Z",
            entities={},
            relationships=[],
            entity_count=0,
            relationship_count=0,
            version=1,
        )
        mock_repository.get_entity_graph_cache.return_value = stale_cache

        # Builder function
        async def builder(
            matter_id: str,
        ) -> tuple[dict[str, CachedEntity], list[EntityRelationship]]:
            entities = {
                "e1": CachedEntity(
                    entity_id="e1",
                    canonical_name="John Smith",
                    entity_type="PERSON",
                )
            }
            relationships = [
                EntityRelationship(
                    source_id="e1",
                    target_id="e2",
                    relationship_type="KNOWS",
                )
            ]
            return entities, relationships

        # Doc uploaded after cache = stale
        result = await service.get_or_build_entity_graph(
            matter_id=MATTER_ID,
            last_document_upload="2026-01-14T12:00:00Z",
            builder_fn=builder,
        )

        assert result is not None
        assert result.entity_count == 1
        assert result.relationship_count == 1
        assert result.version == 2  # Incremented from stale cache
        assert "e1" in result.entities
        mock_repository.set_entity_graph_cache.assert_called_once()


class TestSetEntityGraphCache:
    """Tests for set_entity_graph_cache method."""

    @pytest.mark.asyncio
    async def test_set_entity_graph_cache_creates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create new entity graph cache."""
        entities = {
            "e1": CachedEntity(
                entity_id="e1",
                canonical_name="John Smith",
                entity_type="PERSON",
            )
        }
        relationships = [
            EntityRelationship(
                source_id="e1",
                target_id="e2",
                relationship_type="KNOWS",
            )
        ]

        cache = await service.set_entity_graph_cache(
            matter_id=MATTER_ID,
            entities=entities,
            relationships=relationships,
            last_document_upload="2026-01-14T10:00:00Z",
        )

        assert cache.entity_count == 1
        assert cache.relationship_count == 1
        assert "e1" in cache.entities


class TestInvalidateMatterCaches:
    """Tests for invalidate_matter_caches method."""

    @pytest.mark.asyncio
    async def test_invalidates_both_caches(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should invalidate timeline and entity graph caches."""
        result = await service.invalidate_matter_caches(MATTER_ID)

        assert result["timeline_cache"] is True
        assert result["entity_graph_cache"] is True
        mock_repository.invalidate_timeline_cache.assert_called_once_with(MATTER_ID)
        mock_repository.invalidate_entity_graph_cache.assert_called_once_with(MATTER_ID)


class TestStalenessChecks:
    """Tests for is_timeline_stale and is_entity_graph_stale methods."""

    @pytest.mark.asyncio
    async def test_is_timeline_stale_no_cache(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return True when no cache exists."""
        mock_repository.get_timeline_cache.return_value = None

        stale = await service.is_timeline_stale(MATTER_ID, "2026-01-14T10:00:00Z")

        assert stale is True

    @pytest.mark.asyncio
    async def test_is_timeline_stale_with_cache(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should check staleness when cache exists."""
        mock_repository.get_timeline_cache.return_value = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
        )

        # Doc uploaded after cache = stale
        stale = await service.is_timeline_stale(MATTER_ID, "2026-01-14T12:00:00Z")

        assert stale is True

    @pytest.mark.asyncio
    async def test_is_entity_graph_stale_no_cache(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return True when no cache exists."""
        mock_repository.get_entity_graph_cache.return_value = None

        stale = await service.is_entity_graph_stale(MATTER_ID, "2026-01-14T10:00:00Z")

        assert stale is True


class TestServiceFactory:
    """Tests for factory functions."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_matter_memory_service()

    def test_get_matter_memory_service_singleton(self) -> None:
        """Factory should return same instance."""
        reset_matter_memory_service()

        with patch(
            "app.services.memory.matter_service.get_matter_memory_repository"
        ) as mock:
            mock.return_value = MagicMock()

            service1 = get_matter_memory_service()
            service2 = get_matter_memory_service()

            assert service1 is service2

    def test_get_matter_memory_service_with_repository(self) -> None:
        """Factory should accept custom repository."""
        reset_matter_memory_service()
        mock_repo = MagicMock()

        service = get_matter_memory_service(mock_repo)

        assert service._repository is mock_repo

    def test_reset_matter_memory_service(self) -> None:
        """Reset should clear the singleton."""
        with patch(
            "app.services.memory.matter_service.get_matter_memory_repository"
        ) as mock:
            mock.return_value = MagicMock()

            get_matter_memory_service()
            reset_matter_memory_service()

            service = get_matter_memory_service()
            assert service is not None


# =============================================================================
# Story 7-4: Key Findings Service Tests
# =============================================================================


class TestCreateKeyFinding:
    """Tests for create_key_finding method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_create_key_finding_basic(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create key finding with required fields."""
        finding = await service.create_key_finding(
            matter_id=MATTER_ID,
            finding_type="citation_verified",
            description="Citation to Smith v. Jones verified",
            created_by=USER_ID,
        )

        assert finding.finding_type == "citation_verified"
        assert finding.description == "Citation to Smith v. Jones verified"
        assert finding.created_by == USER_ID
        assert finding.finding_id  # Should have generated UUID
        mock_repository.add_key_finding.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_key_finding_with_evidence(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create key finding with evidence."""
        evidence = [
            FindingEvidence(
                document_id="doc-123",
                page=5,
                text_excerpt="Relevant quote",
            )
        ]

        finding = await service.create_key_finding(
            matter_id=MATTER_ID,
            finding_type="contradiction",
            description="Contradiction found",
            created_by=USER_ID,
            evidence=evidence,
            confidence=85.0,
        )

        assert len(finding.evidence) == 1
        assert finding.confidence == 85.0


class TestGetKeyFindings:
    """Tests for get_key_findings method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_get_key_findings_delegates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should delegate to repository."""
        await service.get_key_findings(MATTER_ID)

        mock_repository.get_key_findings.assert_called_once_with(MATTER_ID)


class TestVerifyKeyFinding:
    """Tests for verify_key_finding method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_verify_key_finding_success(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should verify finding."""
        result = await service.verify_key_finding(
            matter_id=MATTER_ID,
            finding_id="finding-123",
            verified_by="attorney-456",
        )

        assert result is True
        mock_repository.update_key_finding.assert_called_once()
        call_args = mock_repository.update_key_finding.call_args
        updates = call_args[0][2]
        assert updates["verified_by"] == "attorney-456"
        assert "verified_at" in updates


class TestUpdateKeyFinding:
    """Tests for update_key_finding method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_update_key_finding_with_updates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should update finding with provided fields."""
        result = await service.update_key_finding(
            matter_id=MATTER_ID,
            finding_id="finding-123",
            notes="Updated notes",
            confidence=95.0,
        )

        assert result is True
        mock_repository.update_key_finding.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_key_finding_no_updates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return False when no updates provided."""
        result = await service.update_key_finding(
            matter_id=MATTER_ID,
            finding_id="finding-123",
        )

        assert result is False
        mock_repository.update_key_finding.assert_not_called()


class TestGetVerifiedFindings:
    """Tests for get_verified_findings method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_get_verified_findings_filters(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should filter to only verified findings."""
        mock_repository.get_key_findings.return_value = KeyFindings(
            findings=[
                KeyFinding(
                    finding_id="f1",
                    finding_type="citation_verified",
                    description="Verified",
                    created_at="2026-01-14T10:00:00Z",
                    created_by=USER_ID,
                    verified_by="attorney-123",
                    verified_at="2026-01-14T11:00:00Z",
                ),
                KeyFinding(
                    finding_id="f2",
                    finding_type="contradiction",
                    description="Unverified",
                    created_at="2026-01-14T10:00:00Z",
                    created_by=USER_ID,
                ),
            ]
        )

        verified = await service.get_verified_findings(MATTER_ID)

        assert len(verified) == 1
        assert verified[0].finding_id == "f1"


class TestGetFindingsByType:
    """Tests for get_findings_by_type method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_get_findings_by_type_filters(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should filter findings by type."""
        mock_repository.get_key_findings.return_value = KeyFindings(
            findings=[
                KeyFinding(
                    finding_id="f1",
                    finding_type="citation_verified",
                    description="Citation 1",
                    created_at="2026-01-14T10:00:00Z",
                    created_by=USER_ID,
                ),
                KeyFinding(
                    finding_id="f2",
                    finding_type="contradiction",
                    description="Contradiction",
                    created_at="2026-01-14T10:00:00Z",
                    created_by=USER_ID,
                ),
            ]
        )

        citations = await service.get_findings_by_type(MATTER_ID, "citation_verified")

        assert len(citations) == 1
        assert citations[0].finding_type == "citation_verified"


# =============================================================================
# Story 7-4: Research Notes Service Tests
# =============================================================================


class TestCreateResearchNote:
    """Tests for create_research_note method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_create_research_note_basic(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create research note with required fields."""
        note = await service.create_research_note(
            matter_id=MATTER_ID,
            title="Case Analysis",
            created_by=USER_ID,
        )

        assert note.title == "Case Analysis"
        assert note.created_by == USER_ID
        assert note.note_id  # Should have generated UUID
        mock_repository.add_research_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_research_note_with_content(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create research note with full content."""
        note = await service.create_research_note(
            matter_id=MATTER_ID,
            title="Case Analysis",
            created_by=USER_ID,
            content="## Summary\n\nImportant findings...",
            tags=["precedent", "key-case"],
            linked_findings=["finding-123"],
        )

        assert note.content == "## Summary\n\nImportant findings..."
        assert note.tags == ["precedent", "key-case"]
        assert note.linked_findings == ["finding-123"]


class TestGetResearchNotes:
    """Tests for get_research_notes method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_get_research_notes_delegates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should delegate to repository."""
        await service.get_research_notes(MATTER_ID)

        mock_repository.get_research_notes.assert_called_once_with(MATTER_ID)


class TestUpdateResearchNote:
    """Tests for update_research_note method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_update_research_note_with_updates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should update note with provided fields."""
        result = await service.update_research_note(
            matter_id=MATTER_ID,
            note_id="note-123",
            title="Updated Title",
            content="Updated content",
        )

        assert result is True
        mock_repository.update_research_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_research_note_no_updates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return False when no updates provided."""
        result = await service.update_research_note(
            matter_id=MATTER_ID,
            note_id="note-123",
        )

        assert result is False
        mock_repository.update_research_note.assert_not_called()


class TestSearchResearchNotes:
    """Tests for search_research_notes method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_search_research_notes_delegates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should delegate to repository with filters."""
        await service.search_research_notes(
            matter_id=MATTER_ID,
            tag="precedent",
            title_contains="case",
        )

        mock_repository.search_research_notes.assert_called_once_with(
            MATTER_ID, tag="precedent", title_contains="case"
        )


class TestGetNotesForFinding:
    """Tests for get_notes_for_finding method (Story 7-4)."""

    @pytest.mark.asyncio
    async def test_get_notes_for_finding_filters(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should filter notes linked to specific finding."""
        mock_repository.get_research_notes.return_value = ResearchNotes(
            notes=[
                ResearchNote(
                    note_id="n1",
                    title="Note 1",
                    created_by=USER_ID,
                    created_at="2026-01-14T10:00:00Z",
                    linked_findings=["finding-123", "finding-456"],
                ),
                ResearchNote(
                    note_id="n2",
                    title="Note 2",
                    created_by=USER_ID,
                    created_at="2026-01-14T10:00:00Z",
                    linked_findings=["finding-789"],
                ),
            ]
        )

        notes = await service.get_notes_for_finding(MATTER_ID, "finding-123")

        assert len(notes) == 1
        assert notes[0].note_id == "n1"
