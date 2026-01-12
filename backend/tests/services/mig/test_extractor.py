"""Unit tests for the MIG Entity Extractor service."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.entity import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
    ExtractedEntityMention,
    ExtractedRelationship,
    RelationshipType,
)
from app.services.mig.extractor import (
    MIGEntityExtractor,
    MIGConfigurationError,
    MIGExtractorError,
    get_mig_extractor,
    MAX_TEXT_LENGTH,
)


class TestExtractedEntity:
    """Tests for ExtractedEntity model."""

    def test_creates_entity_with_all_fields(self) -> None:
        """Should create entity with all fields."""
        entity = ExtractedEntity(
            name="Shri Nirav D. Jobalia",
            canonical_name="Nirav Jobalia",
            type=EntityType.PERSON,
            roles=["plaintiff", "petitioner"],
            mentions=[
                ExtractedEntityMention(text="Mr. Jobalia", context="...filed by Mr. Jobalia...")
            ],
            confidence=0.95,
        )

        assert entity.name == "Shri Nirav D. Jobalia"
        assert entity.canonical_name == "Nirav Jobalia"
        assert entity.type == EntityType.PERSON
        assert "plaintiff" in entity.roles
        assert len(entity.mentions) == 1
        assert entity.confidence == 0.95

    def test_creates_entity_with_defaults(self) -> None:
        """Should create entity with default values."""
        entity = ExtractedEntity(
            name="State Bank of India",
            canonical_name="State Bank of India",
            type=EntityType.ORG,
        )

        assert entity.roles == []
        assert entity.mentions == []
        assert entity.confidence == 1.0


class TestExtractedRelationship:
    """Tests for ExtractedRelationship model."""

    def test_creates_relationship(self) -> None:
        """Should create relationship with all fields."""
        rel = ExtractedRelationship(
            source="Nirav Jobalia",
            target="ABC Corp",
            type=RelationshipType.HAS_ROLE,
            description="Director of",
            confidence=0.9,
        )

        assert rel.source == "Nirav Jobalia"
        assert rel.target == "ABC Corp"
        assert rel.type == RelationshipType.HAS_ROLE
        assert rel.description == "Director of"
        assert rel.confidence == 0.9


class TestEntityExtractionResult:
    """Tests for EntityExtractionResult model."""

    def test_creates_result_with_all_fields(self) -> None:
        """Should create extraction result with all fields."""
        result = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test Person",
                    canonical_name="Test Person",
                    type=EntityType.PERSON,
                )
            ],
            relationships=[
                ExtractedRelationship(
                    source="Test Person",
                    target="Test Org",
                    type=RelationshipType.HAS_ROLE,
                )
            ],
            source_document_id="doc-123",
            source_chunk_id="chunk-456",
            page_number=5,
        )

        assert len(result.entities) == 1
        assert len(result.relationships) == 1
        assert result.source_document_id == "doc-123"
        assert result.source_chunk_id == "chunk-456"
        assert result.page_number == 5

    def test_creates_empty_result(self) -> None:
        """Should create empty extraction result."""
        result = EntityExtractionResult()

        assert result.entities == []
        assert result.relationships == []
        assert result.source_document_id is None


class TestMIGExtractorError:
    """Tests for MIGExtractorError exception."""

    def test_creates_error_with_defaults(self) -> None:
        """Should create error with default values."""
        error = MIGExtractorError(message="Test error")

        assert error.message == "Test error"
        assert error.code == "MIG_EXTRACTOR_ERROR"
        assert error.is_retryable is True

    def test_creates_non_retryable_error(self) -> None:
        """Should create non-retryable error."""
        error = MIGExtractorError(
            message="API key not configured",
            code="MIG_NOT_CONFIGURED",
            is_retryable=False,
        )

        assert error.code == "MIG_NOT_CONFIGURED"
        assert error.is_retryable is False


class TestMIGConfigurationError:
    """Tests for MIGConfigurationError exception."""

    def test_creates_configuration_error(self) -> None:
        """Should create configuration error with correct code."""
        error = MIGConfigurationError(message="Gemini API key not configured")

        assert error.message == "Gemini API key not configured"
        assert error.code == "MIG_NOT_CONFIGURED"
        assert error.is_retryable is False


class TestMIGEntityExtractorInit:
    """Tests for MIGEntityExtractor initialization."""

    @patch("app.services.mig.extractor.get_settings")
    def test_lazy_model_initialization(self, mock_get_settings: MagicMock) -> None:
        """Should not create model on init (lazy initialization)."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        assert extractor._model is None
        assert extractor.api_key == "test-key"
        assert extractor.model_name == "gemini-1.5-flash"

    @patch("app.services.mig.extractor.get_settings")
    def test_raises_error_when_api_key_missing(self, mock_get_settings: MagicMock) -> None:
        """Should raise MIGConfigurationError when API key is missing."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = ""
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        with pytest.raises(MIGConfigurationError) as exc_info:
            _ = extractor.model

        assert "API key not configured" in str(exc_info.value)


class TestMIGEntityExtractorExtract:
    """Tests for MIGEntityExtractor.extract_entities method."""

    @pytest.fixture
    def mock_gemini_response(self) -> dict:
        """Mock Gemini API response with entities."""
        return {
            "entities": [
                {
                    "name": "Nirav D. Jobalia",
                    "canonical_name": "Nirav Jobalia",
                    "type": "PERSON",
                    "roles": ["plaintiff"],
                    "confidence": 0.95,
                    "mentions": [
                        {"text": "Mr. Jobalia", "context": "...plaintiff Mr. Jobalia filed..."}
                    ],
                },
                {
                    "name": "State Bank of India",
                    "canonical_name": "State Bank of India",
                    "type": "ORG",
                    "roles": ["respondent"],
                    "confidence": 0.95,
                    "mentions": [
                        {"text": "SBI", "context": "...the respondent SBI failed to..."}
                    ],
                },
            ],
            "relationships": [
                {
                    "source": "Nirav Jobalia",
                    "target": "ABC Corp",
                    "type": "HAS_ROLE",
                    "description": "Director",
                    "confidence": 0.9,
                }
            ],
        }

    @patch("app.services.mig.extractor.get_settings")
    def test_returns_empty_result_for_empty_text(self, mock_get_settings: MagicMock) -> None:
        """Should return empty result for empty text."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        result = extractor.extract_entities_sync(
            text="",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.entities) == 0
        assert len(result.relationships) == 0
        assert result.source_document_id == "doc-123"

    @patch("app.services.mig.extractor.get_settings")
    def test_parses_gemini_response_correctly(
        self, mock_get_settings: MagicMock, mock_gemini_response: dict
    ) -> None:
        """Should parse Gemini response into EntityExtractionResult."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        # Test the response parsing directly
        result = extractor._parse_response(
            response_text=json.dumps(mock_gemini_response),
            document_id="doc-123",
            chunk_id="chunk-456",
            page_number=5,
        )

        assert len(result.entities) == 2
        assert result.entities[0].canonical_name == "Nirav Jobalia"
        assert result.entities[0].type == EntityType.PERSON
        assert "plaintiff" in result.entities[0].roles

        assert result.entities[1].canonical_name == "State Bank of India"
        assert result.entities[1].type == EntityType.ORG

        assert len(result.relationships) == 1
        assert result.relationships[0].source == "Nirav Jobalia"
        assert result.relationships[0].type == RelationshipType.HAS_ROLE

        assert result.source_document_id == "doc-123"
        assert result.source_chunk_id == "chunk-456"
        assert result.page_number == 5

    @patch("app.services.mig.extractor.get_settings")
    def test_handles_malformed_json_response(self, mock_get_settings: MagicMock) -> None:
        """Should return empty result for malformed JSON."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        result = extractor._parse_response(
            response_text="not valid json {{{",
            document_id="doc-123",
            chunk_id=None,
            page_number=None,
        )

        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @patch("app.services.mig.extractor.get_settings")
    def test_handles_markdown_code_blocks(self, mock_get_settings: MagicMock) -> None:
        """Should handle JSON wrapped in markdown code blocks."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        response_with_markdown = """```json
{
  "entities": [
    {
      "name": "Test Person",
      "canonical_name": "Test Person",
      "type": "PERSON",
      "roles": [],
      "confidence": 0.9,
      "mentions": []
    }
  ],
  "relationships": []
}
```"""

        result = extractor._parse_response(
            response_text=response_with_markdown,
            document_id="doc-123",
            chunk_id=None,
            page_number=None,
        )

        assert len(result.entities) == 1
        assert result.entities[0].canonical_name == "Test Person"

    @patch("app.services.mig.extractor.get_settings")
    def test_handles_invalid_entity_type(self, mock_get_settings: MagicMock) -> None:
        """Should skip entities with invalid type."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        response = json.dumps({
            "entities": [
                {
                    "name": "Valid Person",
                    "canonical_name": "Valid Person",
                    "type": "PERSON",
                    "confidence": 0.9,
                },
                {
                    "name": "Invalid Entity",
                    "canonical_name": "Invalid Entity",
                    "type": "UNKNOWN_TYPE",  # Invalid type
                    "confidence": 0.9,
                },
            ],
            "relationships": [],
        })

        result = extractor._parse_response(
            response_text=response,
            document_id="doc-123",
            chunk_id=None,
            page_number=None,
        )

        # Should only include valid entity
        assert len(result.entities) == 1
        assert result.entities[0].canonical_name == "Valid Person"


class TestMIGEntityExtractorHelpers:
    """Tests for MIGEntityExtractor helper methods."""

    @patch("app.services.mig.extractor.get_settings")
    def test_parse_entity_type_person(self, mock_get_settings: MagicMock) -> None:
        """Should parse PERSON entity type."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        assert extractor._parse_entity_type("PERSON") == EntityType.PERSON
        assert extractor._parse_entity_type("person") == EntityType.PERSON
        assert extractor._parse_entity_type(" Person ") == EntityType.PERSON

    @patch("app.services.mig.extractor.get_settings")
    def test_parse_entity_type_org(self, mock_get_settings: MagicMock) -> None:
        """Should parse ORG entity type."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        assert extractor._parse_entity_type("ORG") == EntityType.ORG
        assert extractor._parse_entity_type("ORGANIZATION") == EntityType.ORG

    @patch("app.services.mig.extractor.get_settings")
    def test_parse_entity_type_returns_none_for_invalid(
        self, mock_get_settings: MagicMock
    ) -> None:
        """Should return None for invalid entity type."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        assert extractor._parse_entity_type("INVALID") is None
        assert extractor._parse_entity_type("") is None

    @patch("app.services.mig.extractor.get_settings")
    def test_parse_relationship_type(self, mock_get_settings: MagicMock) -> None:
        """Should parse relationship types correctly."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        assert extractor._parse_relationship_type("ALIAS_OF") == RelationshipType.ALIAS_OF
        assert extractor._parse_relationship_type("HAS_ROLE") == RelationshipType.HAS_ROLE
        assert extractor._parse_relationship_type("RELATED_TO") == RelationshipType.RELATED_TO
        assert extractor._parse_relationship_type("INVALID") is None


class TestGetMIGExtractor:
    """Tests for get_mig_extractor factory function."""

    @patch("app.services.mig.extractor.get_settings")
    def test_returns_singleton_instance(self, mock_get_settings: MagicMock) -> None:
        """Should return the same instance on subsequent calls."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        # Clear the cache first
        get_mig_extractor.cache_clear()

        extractor1 = get_mig_extractor()
        extractor2 = get_mig_extractor()

        assert extractor1 is extractor2
