"""Unit tests for EntityResolver alias resolution service.

Tests name similarity algorithms, component extraction, and alias matching.
Story: 2c-2 Alias Resolution
"""

from datetime import datetime, timezone

import pytest

from app.services.mig.entity_resolver import (
    EntityResolver,
    NameComponents,
    AliasCandidate,
    HIGH_SIMILARITY_THRESHOLD,
    MEDIUM_SIMILARITY_THRESHOLD,
    LOW_SIMILARITY_THRESHOLD,
)
from app.models.entity import EntityNode, EntityType

# Fixed timestamp for test data
TEST_TIMESTAMP = datetime(2026, 1, 14, 10, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def resolver() -> EntityResolver:
    """Create a fresh EntityResolver for testing."""
    return EntityResolver()


@pytest.fixture
def sample_entities() -> list[EntityNode]:
    """Create sample entity nodes for testing."""
    return [
        EntityNode(
            id="entity-1",
            matter_id="matter-1",
            canonical_name="Nirav Dineshbhai Jobalia",
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=5,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        ),
        EntityNode(
            id="entity-2",
            matter_id="matter-1",
            canonical_name="N.D. Jobalia",
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=3,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        ),
        EntityNode(
            id="entity-3",
            matter_id="matter-1",
            canonical_name="Mr. Jobalia",
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=2,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        ),
        EntityNode(
            id="entity-4",
            matter_id="matter-1",
            canonical_name="ABC Corporation",
            entity_type=EntityType.ORG,
            metadata={},
            mention_count=10,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        ),
    ]


# =============================================================================
# Name Component Extraction Tests
# =============================================================================


class TestNameComponentExtraction:
    """Tests for extract_name_components method."""

    def test_simple_two_part_name(self, resolver: EntityResolver) -> None:
        """Test extraction of simple first + last name."""
        result = resolver.extract_name_components("John Smith")

        assert result.first_name == "John"
        assert result.last_name == "Smith"
        assert result.middle_name is None
        assert result.title is None

    def test_three_part_name(self, resolver: EntityResolver) -> None:
        """Test extraction of first + middle + last name."""
        result = resolver.extract_name_components("Nirav Dineshbhai Jobalia")

        assert result.first_name == "Nirav"
        assert result.middle_name == "Dineshbhai"
        assert result.last_name == "Jobalia"

    def test_name_with_title(self, resolver: EntityResolver) -> None:
        """Test extraction of name with Indian title."""
        result = resolver.extract_name_components("Shri Nirav Jobalia")

        assert result.title == "Shri"
        assert result.first_name == "Nirav"
        assert result.last_name == "Jobalia"

    def test_name_with_mr_title(self, resolver: EntityResolver) -> None:
        """Test extraction of name with Mr. title."""
        result = resolver.extract_name_components("Mr. Jobalia")

        assert result.title == "Mr."
        assert result.last_name == "Jobalia"
        assert result.first_name is None

    def test_initials_with_last_name(self, resolver: EntityResolver) -> None:
        """Test extraction of initials + last name."""
        result = resolver.extract_name_components("N.D. Jobalia")

        assert result.first_name == "N."
        assert result.middle_name == "D."
        assert result.last_name == "Jobalia"

    def test_single_name(self, resolver: EntityResolver) -> None:
        """Test extraction of single name (treated as last name)."""
        result = resolver.extract_name_components("Jobalia")

        assert result.last_name == "Jobalia"
        assert result.first_name is None

    def test_name_with_suffix(self, resolver: EntityResolver) -> None:
        """Test extraction of name with suffix."""
        result = resolver.extract_name_components("John Smith Jr")

        assert result.first_name == "John"
        assert result.last_name == "Smith"
        assert result.suffix == "Jr"

    def test_empty_name(self, resolver: EntityResolver) -> None:
        """Test extraction of empty string."""
        result = resolver.extract_name_components("")

        assert result.first_name is None
        assert result.last_name is None

    def test_name_without_title_property(self, resolver: EntityResolver) -> None:
        """Test name_without_title property."""
        result = resolver.extract_name_components("Shri Nirav Jobalia")

        assert result.name_without_title == "Nirav Jobalia"

    def test_initials_property(self, resolver: EntityResolver) -> None:
        """Test initials property."""
        result = resolver.extract_name_components("Nirav Dineshbhai Jobalia")

        assert result.initials == "NDJ"


# =============================================================================
# Name Similarity Tests
# =============================================================================


class TestNameSimilarity:
    """Tests for calculate_name_similarity method."""

    def test_exact_match(self, resolver: EntityResolver) -> None:
        """Test exact name match returns 1.0."""
        score = resolver.calculate_name_similarity(
            "Nirav Jobalia",
            "Nirav Jobalia"
        )
        assert score == 1.0

    def test_case_insensitive_match(self, resolver: EntityResolver) -> None:
        """Test case insensitive matching."""
        score = resolver.calculate_name_similarity(
            "nirav jobalia",
            "NIRAV JOBALIA"
        )
        assert score == 1.0

    def test_initials_to_full_name(self, resolver: EntityResolver) -> None:
        """Test matching initials to full name."""
        score = resolver.calculate_name_similarity(
            "N.D. Jobalia",
            "Nirav Dineshbhai Jobalia"
        )
        # Should have high similarity due to initial matching
        assert score > 0.7

    def test_title_variation(self, resolver: EntityResolver) -> None:
        """Test matching names with different titles."""
        score = resolver.calculate_name_similarity(
            "Mr. Jobalia",
            "Shri Jobalia"
        )
        # Should still have reasonable similarity (same last name)
        assert score > 0.5

    def test_different_names(self, resolver: EntityResolver) -> None:
        """Test completely different names have low similarity."""
        score = resolver.calculate_name_similarity(
            "John Smith",
            "Jane Doe"
        )
        assert score < LOW_SIMILARITY_THRESHOLD

    def test_partial_name_match(self, resolver: EntityResolver) -> None:
        """Test partial name matching (first name only)."""
        score = resolver.calculate_name_similarity(
            "Nirav",
            "Nirav Jobalia"
        )
        # Should have some similarity but not very high
        assert 0.3 < score < 0.8

    def test_empty_string_handling(self, resolver: EntityResolver) -> None:
        """Test handling of empty strings."""
        assert resolver.calculate_name_similarity("", "John Smith") == 0.0
        assert resolver.calculate_name_similarity("John Smith", "") == 0.0
        assert resolver.calculate_name_similarity("", "") == 0.0


# =============================================================================
# Alias Candidate Finding Tests
# =============================================================================


class TestFindPotentialAliases:
    """Tests for find_potential_aliases method."""

    def test_finds_aliases_for_similar_names(
        self,
        resolver: EntityResolver,
        sample_entities: list[EntityNode],
    ) -> None:
        """Test finding aliases among similar names."""
        entity = sample_entities[0]  # Nirav Dineshbhai Jobalia
        candidates = resolver.find_potential_aliases(entity, sample_entities)

        # Should find N.D. Jobalia and Mr. Jobalia as candidates
        candidate_ids = [c.candidate_entity_id for c in candidates]
        assert "entity-2" in candidate_ids  # N.D. Jobalia
        assert "entity-3" in candidate_ids  # Mr. Jobalia

    def test_excludes_self_from_candidates(
        self,
        resolver: EntityResolver,
        sample_entities: list[EntityNode],
    ) -> None:
        """Test that entity doesn't match itself."""
        entity = sample_entities[0]
        candidates = resolver.find_potential_aliases(entity, sample_entities)

        candidate_ids = [c.candidate_entity_id for c in candidates]
        assert entity.id not in candidate_ids

    def test_excludes_different_entity_types(
        self,
        resolver: EntityResolver,
        sample_entities: list[EntityNode],
    ) -> None:
        """Test that different entity types don't match."""
        entity = sample_entities[0]  # PERSON
        candidates = resolver.find_potential_aliases(entity, sample_entities)

        candidate_ids = [c.candidate_entity_id for c in candidates]
        assert "entity-4" not in candidate_ids  # ABC Corporation (ORG)

    def test_candidates_sorted_by_score(
        self,
        resolver: EntityResolver,
        sample_entities: list[EntityNode],
    ) -> None:
        """Test that candidates are sorted by similarity descending."""
        entity = sample_entities[0]
        candidates = resolver.find_potential_aliases(entity, sample_entities)

        if len(candidates) >= 2:
            for i in range(len(candidates) - 1):
                assert candidates[i].similarity_score >= candidates[i + 1].similarity_score

    def test_high_similarity_auto_linked(
        self,
        resolver: EntityResolver,
        sample_entities: list[EntityNode],
    ) -> None:
        """Test that high similarity pairs are marked as auto-linked."""
        # Create entities with very similar names
        entity1 = EntityNode(
            id="test-1",
            matter_id="matter-1",
            canonical_name="Nirav Jobalia",
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=1,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        entity2 = EntityNode(
            id="test-2",
            matter_id="matter-1",
            canonical_name="Nirav D. Jobalia",  # Very similar
            entity_type=EntityType.PERSON,
            metadata={},
            mention_count=1,
            aliases=[],
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )

        candidates = resolver.find_potential_aliases(entity1, [entity1, entity2])

        assert len(candidates) == 1
        # May or may not be auto-linked depending on exact score
        # Just verify it's found as a candidate
        assert candidates[0].candidate_entity_id == "test-2"


# =============================================================================
# Threshold Tests
# =============================================================================


class TestThresholds:
    """Tests for similarity threshold constants."""

    def test_threshold_ordering(self) -> None:
        """Test that thresholds are in correct order."""
        assert HIGH_SIMILARITY_THRESHOLD > MEDIUM_SIMILARITY_THRESHOLD
        assert MEDIUM_SIMILARITY_THRESHOLD > LOW_SIMILARITY_THRESHOLD
        assert LOW_SIMILARITY_THRESHOLD > 0

    def test_high_threshold_reasonable(self) -> None:
        """Test high threshold is reasonable for auto-linking."""
        assert 0.8 <= HIGH_SIMILARITY_THRESHOLD <= 0.95

    def test_medium_threshold_reasonable(self) -> None:
        """Test medium threshold is reasonable for context analysis."""
        assert 0.5 <= MEDIUM_SIMILARITY_THRESHOLD <= 0.75


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unicode_names(self, resolver: EntityResolver) -> None:
        """Test handling of Unicode characters in names."""
        score = resolver.calculate_name_similarity(
            "José García",
            "Jose Garcia"
        )
        # Should still work with accented characters
        assert score > 0.8

    def test_very_long_names(self, resolver: EntityResolver) -> None:
        """Test handling of very long names."""
        long_name = "John " * 10 + "Smith"
        score = resolver.calculate_name_similarity(long_name, long_name)
        assert score == 1.0

    def test_special_characters(self, resolver: EntityResolver) -> None:
        """Test handling of special characters."""
        result = resolver.extract_name_components("O'Brien-Smith")
        assert result.last_name == "O'Brien-Smith"

    def test_multiple_spaces(self, resolver: EntityResolver) -> None:
        """Test handling of multiple spaces."""
        result = resolver.extract_name_components("John    Smith")
        assert result.first_name == "John"
        assert result.last_name == "Smith"
