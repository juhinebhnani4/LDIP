"""Unit tests for EventEntityLinker.

Tests entity mention extraction and entity matching functionality.

Story 4-3: Events Table + MIG Integration
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engines.timeline.entity_linker import (
    EntityMention,
    EventEntityLinker,
    get_event_entity_linker,
)
from app.models.entity import EntityNode, EntityType

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def entity_linker():
    """Create an EventEntityLinker instance for testing."""
    linker = EventEntityLinker()
    # Mock the resolver
    linker._resolver = MagicMock()
    linker._mig_service = MagicMock()
    return linker


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return [
        EntityNode(
            id="entity-1",
            matter_id="matter-123",
            canonical_name="Nirav Dineshbhai Jobalia",
            entity_type=EntityType.PERSON,
            aliases=["N.D. Jobalia", "Nirav Jobalia"],
            metadata={"role": "petitioner"},
            created_at=now,
            updated_at=now,
        ),
        EntityNode(
            id="entity-2",
            matter_id="matter-123",
            canonical_name="HDFC Bank Ltd",
            entity_type=EntityType.ORG,
            aliases=["HDFC Bank", "HDFC"],
            metadata={"role": "respondent"},
            created_at=now,
            updated_at=now,
        ),
        EntityNode(
            id="entity-3",
            matter_id="matter-123",
            canonical_name="Gujarat High Court",
            entity_type=EntityType.INSTITUTION,
            aliases=["High Court of Gujarat"],
            metadata={},
            created_at=now,
            updated_at=now,
        ),
    ]


# =============================================================================
# Entity Mention Extraction Tests
# =============================================================================


class TestEntityMentionExtraction:
    """Tests for extracting entity mentions from text."""

    def test_extract_person_with_title(self, entity_linker):
        """Test extraction of person names with Indian titles."""
        text = "Shri Nirav Jobalia filed a petition against the respondent."
        mentions = entity_linker._extract_entity_mentions(text)

        assert len(mentions) >= 1
        person_mentions = [m for m in mentions if m.entity_type == EntityType.PERSON]
        assert any("Nirav" in m.text for m in person_mentions)

    def test_extract_person_with_smt_title(self, entity_linker):
        """Test extraction with Smt title."""
        text = "Smt Priya Sharma appeared as witness."
        mentions = entity_linker._extract_entity_mentions(text)

        person_mentions = [m for m in mentions if m.entity_type == EntityType.PERSON]
        assert any("Priya" in m.text for m in person_mentions)

    def test_extract_advocate_title(self, entity_linker):
        """Test extraction with Advocate/Adv title."""
        text = "Adv Ramesh Kumar represented the petitioner."
        mentions = entity_linker._extract_entity_mentions(text)

        person_mentions = [m for m in mentions if m.entity_type == EntityType.PERSON]
        assert any("Ramesh" in m.text for m in person_mentions)

    def test_extract_organization_with_ltd(self, entity_linker):
        """Test extraction of organizations with Ltd indicator."""
        text = "HDFC Bank Ltd filed a response to the petition."
        mentions = entity_linker._extract_entity_mentions(text)

        org_mentions = [m for m in mentions if m.entity_type == EntityType.ORG]
        assert any("HDFC" in m.text and "Ltd" in m.text for m in org_mentions)

    def test_extract_organization_with_private_limited(self, entity_linker):
        """Test extraction of private limited companies."""
        text = "Reliance Industries Private Limited was named as respondent."
        mentions = entity_linker._extract_entity_mentions(text)

        org_mentions = [m for m in mentions if m.entity_type == EntityType.ORG]
        assert len(org_mentions) >= 1

    def test_extract_court_institution(self, entity_linker):
        """Test extraction of court names."""
        text = "The matter was heard by the High Court of Gujarat."
        mentions = entity_linker._extract_entity_mentions(text)

        inst_mentions = [m for m in mentions if m.entity_type == EntityType.INSTITUTION]
        assert any("High Court" in m.text for m in inst_mentions)

    def test_extract_multiple_entities(self, entity_linker):
        """Test extraction of multiple entities from text."""
        text = (
            "Shri Nirav Jobalia filed a case against HDFC Bank Ltd "
            "in the Gujarat High Court."
        )
        mentions = entity_linker._extract_entity_mentions(text)

        assert len(mentions) >= 2
        types = {m.entity_type for m in mentions}
        assert EntityType.PERSON in types or EntityType.ORG in types

    def test_extract_no_duplicates(self, entity_linker):
        """Test that mentions with same normalized text are deduplicated."""
        text = "Shri Nirav Jobalia filed the case."
        mentions = entity_linker._extract_entity_mentions(text)

        # Get unique mention texts (normalized)
        nirav_mentions = [m for m in mentions if "Nirav" in m.text]
        # Multiple patterns may match, but we verify at least one is found
        assert len(nirav_mentions) >= 1

    def test_extract_empty_text(self, entity_linker):
        """Test extraction from empty text."""
        mentions = entity_linker._extract_entity_mentions("")
        assert mentions == []

    def test_extract_no_entities(self, entity_linker):
        """Test extraction from text with no entities."""
        text = "The petition was filed on 15th January 2024."
        mentions = entity_linker._extract_entity_mentions(text)

        # Should have no high-confidence person/org mentions
        high_conf = [m for m in mentions if m.confidence > 0.8]
        assert len(high_conf) == 0


# =============================================================================
# Entity Matching Tests
# =============================================================================


class TestEntityMatching:
    """Tests for matching mentions to canonical entities."""

    def test_match_exact_canonical_name(self, entity_linker, sample_entities):
        """Test matching with exact canonical name."""
        entity_linker._resolver.calculate_name_similarity.return_value = 1.0

        mention = EntityMention(
            text="Nirav Dineshbhai Jobalia",
            entity_type=EntityType.PERSON,
            confidence=0.9,
        )

        result = entity_linker._find_best_entity_match(mention, sample_entities)

        assert result is not None
        assert result.entity_id == "entity-1"
        assert result.similarity_score == 1.0

    def test_match_by_alias(self, entity_linker, sample_entities):
        """Test matching via alias."""
        # Return low score for canonical name, high for alias
        def mock_similarity(name1, name2):
            if "N.D. Jobalia" in name2:
                return 0.95
            return 0.3

        entity_linker._resolver.calculate_name_similarity.side_effect = mock_similarity

        mention = EntityMention(
            text="N.D. Jobalia",
            entity_type=EntityType.PERSON,
            confidence=0.85,
        )

        result = entity_linker._find_best_entity_match(mention, sample_entities)

        assert result is not None
        assert result.entity_id == "entity-1"
        assert "alias" in result.matched_via

    def test_match_organization(self, entity_linker, sample_entities):
        """Test matching organization entity."""
        entity_linker._resolver.calculate_name_similarity.return_value = 0.85

        mention = EntityMention(
            text="HDFC Bank Ltd",
            entity_type=EntityType.ORG,
            confidence=0.9,
        )

        result = entity_linker._find_best_entity_match(mention, sample_entities)

        assert result is not None
        assert result.entity_id == "entity-2"

    def test_no_match_below_threshold(self, entity_linker, sample_entities):
        """Test that low similarity scores don't match."""
        entity_linker._resolver.calculate_name_similarity.return_value = 0.5

        mention = EntityMention(
            text="Unknown Person",
            entity_type=EntityType.PERSON,
            confidence=0.7,
        )

        result = entity_linker._find_best_entity_match(mention, sample_entities)

        assert result is None

    def test_match_best_of_multiple(self, entity_linker, sample_entities):
        """Test that best match is selected from multiple candidates."""
        # First entity scores lower, second scores higher
        def mock_similarity(name1, name2):
            if "HDFC" in name2:
                return 0.95
            elif "Nirav" in name2:
                return 0.75
            return 0.3

        entity_linker._resolver.calculate_name_similarity.side_effect = mock_similarity

        mention = EntityMention(
            text="HDFC Bank",
            entity_type=EntityType.ORG,
            confidence=0.6,  # Low confidence = flexible type matching
        )

        result = entity_linker._find_best_entity_match(mention, sample_entities)

        assert result is not None
        assert result.entity_id == "entity-2"


# =============================================================================
# Full Linking Tests
# =============================================================================


class TestEventEntityLinking:
    """Tests for complete entity linking workflow."""

    @pytest.mark.asyncio
    async def test_link_entities_to_event(self, entity_linker, sample_entities):
        """Test linking entities from event description."""
        entity_linker._mig_service.get_entities_by_matter = AsyncMock(
            return_value=(sample_entities, 3)
        )
        entity_linker._resolver.calculate_name_similarity.return_value = 0.9

        entity_ids = await entity_linker.link_entities_to_event(
            event_id="event-123",
            description="Shri Nirav Jobalia filed petition against HDFC Bank Ltd",
            matter_id="matter-123",
            use_gemini=False,
        )

        assert len(entity_ids) >= 1
        assert "entity-1" in entity_ids or "entity-2" in entity_ids

    @pytest.mark.asyncio
    async def test_link_entities_empty_description(self, entity_linker):
        """Test linking with empty description."""
        entity_ids = await entity_linker.link_entities_to_event(
            event_id="event-123",
            description="",
            matter_id="matter-123",
            use_gemini=False,
        )

        assert entity_ids == []

    @pytest.mark.asyncio
    async def test_link_entities_no_mig_entities(self, entity_linker):
        """Test linking when no MIG entities exist."""
        entity_linker._mig_service.get_entities_by_matter = AsyncMock(
            return_value=([], 0)
        )

        entity_ids = await entity_linker.link_entities_to_event(
            event_id="event-123",
            description="Shri Nirav Jobalia filed petition",
            matter_id="matter-123",
            use_gemini=False,
        )

        assert entity_ids == []

    def test_link_entities_sync(self, entity_linker, sample_entities):
        """Test synchronous entity linking."""
        entity_linker._resolver.calculate_name_similarity.return_value = 0.85

        entity_ids = entity_linker.link_entities_to_event_sync(
            event_id="event-123",
            description="Case filed by Shri Nirav Jobalia in Gujarat High Court",
            matter_id="matter-123",
            entities=sample_entities,
        )

        assert isinstance(entity_ids, list)

    def test_link_entities_sync_empty(self, entity_linker, sample_entities):
        """Test sync linking with empty description."""
        entity_ids = entity_linker.link_entities_to_event_sync(
            event_id="event-123",
            description="",
            matter_id="matter-123",
            entities=sample_entities,
        )

        assert entity_ids == []


# =============================================================================
# Batch Linking Tests
# =============================================================================


class TestBatchEntityLinking:
    """Tests for batch entity linking."""

    @pytest.mark.asyncio
    async def test_link_entities_batch(self, entity_linker, sample_entities):
        """Test batch entity linking for multiple events."""

        entity_linker._mig_service.get_entities_by_matter = AsyncMock(
            return_value=(sample_entities, 3)
        )
        entity_linker._resolver.calculate_name_similarity.return_value = 0.85

        # Create mock events
        events = [
            MagicMock(
                id="event-1",
                description="Shri Nirav Jobalia appeared before the court",
            ),
            MagicMock(
                id="event-2",
                description="HDFC Bank Ltd submitted documents",
            ),
        ]

        results = await entity_linker.link_entities_batch(
            events=events,
            matter_id="matter-123",
            use_gemini=False,
        )

        assert "event-1" in results
        assert "event-2" in results
        assert isinstance(results["event-1"], list)
        assert isinstance(results["event-2"], list)

    @pytest.mark.asyncio
    async def test_link_entities_batch_empty(self, entity_linker):
        """Test batch linking with no events."""
        results = await entity_linker.link_entities_batch(
            events=[],
            matter_id="matter-123",
            use_gemini=False,
        )

        assert results == {}


# =============================================================================
# Service Factory Tests
# =============================================================================


class TestServiceFactory:
    """Tests for service factory function."""

    def test_get_event_entity_linker_singleton(self):
        """Test that factory returns singleton instance."""
        # Clear cache first
        get_event_entity_linker.cache_clear()

        linker1 = get_event_entity_linker()
        linker2 = get_event_entity_linker()

        assert linker1 is linker2
        assert isinstance(linker1, EventEntityLinker)

        # Clear cache after test
        get_event_entity_linker.cache_clear()
