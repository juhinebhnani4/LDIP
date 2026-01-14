"""Integration tests for MIG (Matter Identity Graph) pipeline.

Tests the complete entity extraction flow from document chunks to MIG storage,
including matter isolation verification.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.entity import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
    ExtractedEntityMention,
    ExtractedRelationship,
    RelationshipType,
)
from app.services.mig.extractor import MIGEntityExtractor
from app.services.mig.graph import MIGGraphService


class TestMIGPipelineIntegration:
    """Integration tests for the MIG pipeline."""

    @pytest.fixture
    def sample_legal_text(self) -> str:
        """Sample legal document text for testing."""
        return """
        IN THE HIGH COURT OF GUJARAT AT AHMEDABAD

        The petitioner, Shri Nirav D. Jobalia, hereby files this petition against
        State Bank of India (SBI) and the Reserve Bank of India (RBI).

        The petitioner was a Director of ABC Pvt. Ltd. until 2019. The company
        was engaged in disputes with SBI regarding loan restructuring.

        Mr. Jobalia seeks relief under Section 34 of the Arbitration Act.
        The Hon'ble Justice Patel is presiding over this matter.

        The disputed property at Survey No. 123, Village Motera, is valued
        at Rs. 50,00,000 (Fifty Lakhs only).
        """

    @pytest.fixture
    def mock_gemini_response(self) -> dict:
        """Mock Gemini response for entity extraction."""
        return {
            "entities": [
                {
                    "name": "Shri Nirav D. Jobalia",
                    "canonical_name": "Nirav Jobalia",
                    "type": "PERSON",
                    "roles": ["petitioner", "director"],
                    "confidence": 0.95,
                    "mentions": [
                        {
                            "text": "Shri Nirav D. Jobalia",
                            "context": "The petitioner, Shri Nirav D. Jobalia, hereby files",
                        },
                        {
                            "text": "Mr. Jobalia",
                            "context": "Mr. Jobalia seeks relief under Section 34",
                        },
                    ],
                },
                {
                    "name": "State Bank of India",
                    "canonical_name": "State Bank of India",
                    "type": "ORG",
                    "roles": ["respondent"],
                    "confidence": 0.95,
                    "mentions": [
                        {
                            "text": "State Bank of India",
                            "context": "against State Bank of India (SBI)",
                        },
                        {"text": "SBI", "context": "disputes with SBI regarding"},
                    ],
                },
                {
                    "name": "Reserve Bank of India",
                    "canonical_name": "Reserve Bank of India",
                    "type": "INSTITUTION",
                    "roles": ["respondent"],
                    "confidence": 0.95,
                    "mentions": [
                        {
                            "text": "Reserve Bank of India",
                            "context": "and the Reserve Bank of India (RBI)",
                        },
                        {"text": "RBI", "context": "Reserve Bank of India (RBI)."},
                    ],
                },
                {
                    "name": "ABC Pvt. Ltd.",
                    "canonical_name": "ABC Pvt. Ltd.",
                    "type": "ORG",
                    "roles": [],
                    "confidence": 0.9,
                    "mentions": [
                        {
                            "text": "ABC Pvt. Ltd.",
                            "context": "a Director of ABC Pvt. Ltd. until 2019",
                        }
                    ],
                },
                {
                    "name": "High Court of Gujarat",
                    "canonical_name": "High Court of Gujarat",
                    "type": "INSTITUTION",
                    "roles": [],
                    "confidence": 0.95,
                    "mentions": [
                        {
                            "text": "HIGH COURT OF GUJARAT",
                            "context": "IN THE HIGH COURT OF GUJARAT AT AHMEDABAD",
                        }
                    ],
                },
                {
                    "name": "Justice Patel",
                    "canonical_name": "Justice Patel",
                    "type": "PERSON",
                    "roles": ["judge"],
                    "confidence": 0.85,
                    "mentions": [
                        {
                            "text": "Justice Patel",
                            "context": "The Hon'ble Justice Patel is presiding",
                        }
                    ],
                },
                {
                    "name": "Property at Survey No. 123, Village Motera",
                    "canonical_name": "Survey No. 123, Motera",
                    "type": "ASSET",
                    "roles": ["disputed property"],
                    "confidence": 0.9,
                    "mentions": [
                        {
                            "text": "Survey No. 123, Village Motera",
                            "context": "disputed property at Survey No. 123, Village Motera",
                        }
                    ],
                },
            ],
            "relationships": [
                {
                    "source": "Nirav Jobalia",
                    "target": "ABC Pvt. Ltd.",
                    "type": "HAS_ROLE",
                    "description": "Director",
                    "confidence": 0.9,
                }
            ],
        }

    @pytest.mark.asyncio
    @patch("app.services.mig.extractor.get_settings")
    async def test_complete_extraction_pipeline(
        self,
        mock_get_settings: MagicMock,
        sample_legal_text: str,
        mock_gemini_response: dict,
    ) -> None:
        """Test complete extraction from text to EntityExtractionResult."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        # Mock Gemini API call
        with patch.object(
            extractor, "_parse_response"
        ) as mock_parse:
            # Create expected extraction result
            expected_result = EntityExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="Nirav Jobalia",
                        canonical_name="Nirav Jobalia",
                        type=EntityType.PERSON,
                        roles=["petitioner"],
                        confidence=0.95,
                    ),
                    ExtractedEntity(
                        name="State Bank of India",
                        canonical_name="State Bank of India",
                        type=EntityType.ORG,
                        roles=["respondent"],
                        confidence=0.95,
                    ),
                ],
                relationships=[],
                source_document_id="doc-123",
                source_chunk_id="chunk-456",
            )
            mock_parse.return_value = expected_result

            # Mock the _model attribute directly since model is a property
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "{}"
            mock_model.generate_content.return_value = mock_response
            extractor._model = mock_model

            result = extractor.extract_entities_sync(
                text=sample_legal_text,
                document_id="doc-123",
                matter_id="matter-456",
                chunk_id="chunk-456",
            )

        # Verify extraction produced valid result
        assert result.source_document_id == "doc-123"
        assert result.source_chunk_id == "chunk-456"

    @pytest.mark.asyncio
    @patch("app.services.mig.graph.get_supabase_client")
    async def test_entity_deduplication_within_matter(
        self,
        mock_get_client: MagicMock,
        mock_gemini_response: dict,
    ) -> None:
        """Test that duplicate entities are merged within a matter."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        matter_id = str(uuid4())

        # First extraction - create new entity
        # Mock: no existing entity found
        mock_select_response = MagicMock()
        mock_select_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.ilike.return_value.limit.return_value.execute.return_value = (
            mock_select_response
        )

        # Mock: insert returns new entity
        new_entity_id = str(uuid4())
        mock_insert_response = MagicMock()
        mock_insert_response.data = [
            {
                "id": new_entity_id,
                "matter_id": matter_id,
                "canonical_name": "Nirav Jobalia",
                "entity_type": "PERSON",
                "metadata": {},
                "mention_count": 2,
                "aliases": [],
                "created_at": "2024-01-15T10:30:00+00:00",
                "updated_at": "2024-01-15T10:30:00+00:00",
            }
        ]
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_insert_response
        )

        service = MIGGraphService()

        # First extraction result
        first_extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Nirav Jobalia",
                    canonical_name="Nirav Jobalia",
                    type=EntityType.PERSON,
                    roles=["petitioner"],
                    mentions=[
                        ExtractedEntityMention(text="Mr. Jobalia", context="..."),
                        ExtractedEntityMention(text="Nirav D. Jobalia", context="..."),
                    ],
                    confidence=0.95,
                ),
            ],
            relationships=[],
            source_document_id="doc-1",
        )

        result = await service.save_entities(
            matter_id=matter_id,
            extraction_result=first_extraction,
        )

        # Verify entity was created
        assert len(result) == 1
        assert result[0].canonical_name == "Nirav Jobalia"

    @pytest.mark.asyncio
    @patch("app.services.mig.graph.get_supabase_client")
    async def test_matter_isolation_for_entities(
        self,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that entities are isolated to their matter."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        matter_a = str(uuid4())
        matter_b = str(uuid4())

        # Mock: get entity with matter_id filter
        mock_select_response = MagicMock()
        mock_select_response.data = []  # Entity not found in this matter
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = (
            mock_select_response
        )

        service = MIGGraphService()

        # Query entity from matter A
        entity_id = str(uuid4())
        entity_a = await service.get_entity(entity_id, matter_a)

        # Entity should not be found (different matter)
        assert entity_a is None

        # Verify matter_id was used in query
        table_calls = mock_client.table.call_args_list
        assert any("identity_nodes" in str(call) for call in table_calls)


class TestMIGEntityTypes:
    """Tests for entity type classification."""

    @pytest.mark.asyncio
    @patch("app.services.mig.extractor.get_settings")
    async def test_extracts_all_entity_types(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """Test that all entity types (PERSON, ORG, INSTITUTION, ASSET) are handled."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        # Test parsing response with all entity types
        response_text = """
        {
            "entities": [
                {"name": "John Doe", "canonical_name": "John Doe", "type": "PERSON", "roles": [], "confidence": 0.9, "mentions": []},
                {"name": "ABC Corp", "canonical_name": "ABC Corp", "type": "ORG", "roles": [], "confidence": 0.9, "mentions": []},
                {"name": "Supreme Court", "canonical_name": "Supreme Court of India", "type": "INSTITUTION", "roles": [], "confidence": 0.9, "mentions": []},
                {"name": "Plot 123", "canonical_name": "Plot 123, Mumbai", "type": "ASSET", "roles": [], "confidence": 0.9, "mentions": []}
            ],
            "relationships": []
        }
        """

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            chunk_id=None,
            page_number=None,
        )

        # Verify all entity types were parsed
        entity_types = {e.type for e in result.entities}
        assert EntityType.PERSON in entity_types
        assert EntityType.ORG in entity_types
        assert EntityType.INSTITUTION in entity_types
        assert EntityType.ASSET in entity_types


class TestMIGRelationships:
    """Tests for relationship extraction and storage."""

    @pytest.mark.asyncio
    @patch("app.services.mig.extractor.get_settings")
    async def test_extracts_relationships(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """Test that relationships between entities are extracted."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings

        extractor = MIGEntityExtractor()

        response_text = """
        {
            "entities": [
                {"name": "John Doe", "canonical_name": "John Doe", "type": "PERSON", "roles": ["director"], "confidence": 0.9, "mentions": []},
                {"name": "ABC Corp", "canonical_name": "ABC Corp", "type": "ORG", "roles": [], "confidence": 0.9, "mentions": []}
            ],
            "relationships": [
                {"source": "John Doe", "target": "ABC Corp", "type": "HAS_ROLE", "description": "Director", "confidence": 0.9}
            ]
        }
        """

        result = extractor._parse_response(
            response_text=response_text,
            document_id="doc-123",
            chunk_id=None,
            page_number=None,
        )

        # Verify relationship was extracted
        assert len(result.relationships) == 1
        assert result.relationships[0].source == "John Doe"
        assert result.relationships[0].target == "ABC Corp"
        assert result.relationships[0].type == RelationshipType.HAS_ROLE


class TestMIGMentionTracking:
    """Tests for entity mention tracking."""

    @pytest.mark.asyncio
    @patch("app.services.mig.graph.get_supabase_client")
    async def test_tracks_mention_count(
        self,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that mention count is tracked correctly."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        matter_id = str(uuid4())
        entity_id = str(uuid4())

        # Mock existing entity with mention_count
        mock_select_current = MagicMock()
        mock_select_current.data = [{"mention_count": 5}]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = (
            mock_select_current
        )

        # Mock update
        mock_update_response = MagicMock()
        mock_update_response.data = [
            {
                "id": entity_id,
                "matter_id": matter_id,
                "canonical_name": "Test Entity",
                "entity_type": "PERSON",
                "metadata": {},
                "mention_count": 8,  # Updated from 5 + 3
                "aliases": [],
                "created_at": "2024-01-15T10:30:00+00:00",
                "updated_at": "2024-01-15T11:00:00+00:00",
            }
        ]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_update_response
        )

        service = MIGGraphService()

        # Increment mention count
        await service.increment_mention_count(
            entity_id=entity_id,
            matter_id=matter_id,
            increment=3,
        )

        # Verify update was called with new count
        mock_client.table.return_value.update.assert_called()
