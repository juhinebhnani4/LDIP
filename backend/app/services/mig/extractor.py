"""Gemini-based MIG Entity Extraction Service.

Uses Gemini 3 Flash for extracting entities (people, organizations,
institutions, assets) and their relationships from legal document text.

CRITICAL: Uses Gemini for entity extraction per LLM routing rules -
this is an ingestion task, NOT user-facing reasoning.
"""

import asyncio
import json
import time
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.models.entity import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
    ExtractedEntityMention,
    ExtractedRelationship,
    RelationshipType,
)
from app.services.mig.prompts import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    ENTITY_EXTRACTION_USER_PROMPT,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
MAX_TEXT_LENGTH = 30000  # Max characters per extraction request


# =============================================================================
# Exceptions
# =============================================================================


class MIGExtractorError(Exception):
    """Base exception for MIG extractor operations."""

    def __init__(
        self,
        message: str,
        code: str = "MIG_EXTRACTOR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class MIGConfigurationError(MIGExtractorError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="MIG_NOT_CONFIGURED", is_retryable=False)


# =============================================================================
# Service Implementation
# =============================================================================


class MIGEntityExtractor:
    """Service for extracting entities from legal documents using Gemini 3 Flash.

    Extracts:
    - PERSON: Individual people (parties, witnesses, attorneys, judges)
    - ORG: Companies, corporations, partnerships, trusts
    - INSTITUTION: Government bodies, courts, tribunals
    - ASSET: Properties, bank accounts, financial instruments

    Also extracts relationships between entities when explicitly mentioned.

    Example:
        >>> extractor = MIGEntityExtractor()
        >>> result = await extractor.extract_entities(
        ...     text="The petitioner, Nirav Jobalia, filed against SBI.",
        ...     document_id="doc-123",
        ...     matter_id="matter-456",
        ... )
        >>> len(result.entities)
        2
        >>> result.entities[0].canonical_name
        'Nirav Jobalia'
    """

    def __init__(self) -> None:
        """Initialize MIG entity extractor."""
        self._model = None
        self._genai = None
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model

    @property
    def model(self):
        """Get or create Gemini model instance.

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            MIGConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise MIGConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=ENTITY_EXTRACTION_SYSTEM_PROMPT,
                )
                logger.info(
                    "mig_extractor_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("mig_extractor_init_failed", error=str(e))
                raise MIGConfigurationError(
                    f"Failed to initialize Gemini for MIG: {e}"
                ) from e

        return self._model

    async def extract_entities(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        chunk_id: str | None = None,
        page_number: int | None = None,
    ) -> EntityExtractionResult:
        """Extract entities and relationships from text.

        Args:
            text: Document text to extract entities from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.

        Returns:
            EntityExtractionResult containing extracted entities and relationships.

        Raises:
            MIGExtractorError: If extraction fails after retries.
        """
        # Handle empty text
        if not text or not text.strip():
            logger.debug(
                "mig_extraction_empty_text",
                document_id=document_id,
                matter_id=matter_id,
            )
            return EntityExtractionResult(
                entities=[],
                relationships=[],
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
            )

        # Truncate if too long
        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(
                "mig_extraction_text_truncated",
                original_length=len(text),
                max_length=MAX_TEXT_LENGTH,
                document_id=document_id,
            )
            text = text[:MAX_TEXT_LENGTH]

        start_time = time.time()
        prompt = ENTITY_EXTRACTION_USER_PROMPT.format(text=text)

        # Retry with exponential backoff
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                # Call Gemini asynchronously
                response = await self.model.generate_content_async(prompt)

                # Parse response
                result = self._parse_response(
                    response.text,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    page_number=page_number,
                )

                processing_time = int((time.time() - start_time) * 1000)

                logger.info(
                    "mig_extraction_complete",
                    document_id=document_id,
                    matter_id=matter_id,
                    entity_count=len(result.entities),
                    relationship_count=len(result.relationships),
                    processing_time_ms=processing_time,
                    attempts=attempt + 1,
                )

                return result

            except MIGConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "mig_extraction_rate_limited",
                        attempt=attempt + 1,
                        max_attempts=MAX_RETRIES,
                        retry_delay=retry_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "mig_extraction_failed",
            error=str(last_error),
            document_id=document_id,
            matter_id=matter_id,
            attempts=MAX_RETRIES,
        )

        # Return empty result on failure (graceful degradation)
        return EntityExtractionResult(
            entities=[],
            relationships=[],
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
        )

    def extract_entities_sync(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        chunk_id: str | None = None,
        page_number: int | None = None,
    ) -> EntityExtractionResult:
        """Synchronous wrapper for entity extraction.

        For use in Celery tasks or other synchronous contexts.

        Args:
            text: Document text to extract entities from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.

        Returns:
            EntityExtractionResult containing extracted entities and relationships.
        """
        # Handle empty text
        if not text or not text.strip():
            return EntityExtractionResult(
                entities=[],
                relationships=[],
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
            )

        # Truncate if too long
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]

        start_time = time.time()
        prompt = ENTITY_EXTRACTION_USER_PROMPT.format(text=text)

        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)

                result = self._parse_response(
                    response.text,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    page_number=page_number,
                )

                processing_time = int((time.time() - start_time) * 1000)

                logger.info(
                    "mig_extraction_sync_complete",
                    document_id=document_id,
                    matter_id=matter_id,
                    entity_count=len(result.entities),
                    relationship_count=len(result.relationships),
                    processing_time_ms=processing_time,
                    attempts=attempt + 1,
                )

                return result

            except MIGConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "mig_extraction_sync_rate_limited",
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "mig_extraction_sync_failed",
            error=str(last_error),
            document_id=document_id,
        )

        return EntityExtractionResult(
            entities=[],
            relationships=[],
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
        )

    def _parse_response(
        self,
        response_text: str,
        document_id: str,
        chunk_id: str | None,
        page_number: int | None,
    ) -> EntityExtractionResult:
        """Parse Gemini response into EntityExtractionResult.

        Args:
            response_text: Raw response from Gemini.
            document_id: Source document UUID.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.

        Returns:
            Parsed EntityExtractionResult.
        """
        try:
            # Clean up response text
            json_text = response_text.strip()

            # Remove markdown code blocks if present
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block:
                        json_lines.append(line)
                json_text = "\n".join(json_lines)

            # Parse JSON
            parsed = json.loads(json_text)

            if not isinstance(parsed, dict):
                logger.warning(
                    "mig_response_not_dict",
                    response_type=type(parsed).__name__,
                )
                return self._empty_result(document_id, chunk_id, page_number)

            # Parse entities
            entities: list[ExtractedEntity] = []
            raw_entities = parsed.get("entities", [])

            for raw_entity in raw_entities:
                try:
                    entity_type = self._parse_entity_type(raw_entity.get("type", ""))
                    if entity_type is None:
                        continue

                    mentions = [
                        ExtractedEntityMention(
                            text=m.get("text", ""),
                            context=m.get("context"),
                        )
                        for m in raw_entity.get("mentions", [])
                        if m.get("text")
                    ]

                    entity = ExtractedEntity(
                        name=raw_entity.get("name", ""),
                        canonical_name=raw_entity.get(
                            "canonical_name", raw_entity.get("name", "")
                        ),
                        type=entity_type,
                        roles=raw_entity.get("roles", []),
                        mentions=mentions,
                        confidence=float(raw_entity.get("confidence", 0.8)),
                    )

                    if entity.name:
                        entities.append(entity)

                except Exception as e:
                    logger.debug(
                        "mig_entity_parse_error",
                        error=str(e),
                        raw_entity=str(raw_entity)[:100],
                    )
                    continue

            # Parse relationships
            relationships: list[ExtractedRelationship] = []
            raw_relationships = parsed.get("relationships", [])

            for raw_rel in raw_relationships:
                try:
                    rel_type = self._parse_relationship_type(raw_rel.get("type", ""))
                    if rel_type is None:
                        continue

                    relationship = ExtractedRelationship(
                        source=raw_rel.get("source", ""),
                        target=raw_rel.get("target", ""),
                        type=rel_type,
                        description=raw_rel.get("description"),
                        confidence=float(raw_rel.get("confidence", 0.8)),
                    )

                    if relationship.source and relationship.target:
                        relationships.append(relationship)

                except Exception as e:
                    logger.debug(
                        "mig_relationship_parse_error",
                        error=str(e),
                    )
                    continue

            return EntityExtractionResult(
                entities=entities,
                relationships=relationships,
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "mig_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return self._empty_result(document_id, chunk_id, page_number)

        except Exception as e:
            logger.warning(
                "mig_response_parse_error",
                error=str(e),
            )
            return self._empty_result(document_id, chunk_id, page_number)

    def _parse_entity_type(self, type_str: str) -> EntityType | None:
        """Parse entity type string to enum."""
        type_upper = type_str.upper().strip()
        match type_upper:
            case "PERSON":
                return EntityType.PERSON
            case "ORG" | "ORGANIZATION":
                return EntityType.ORG
            case "INSTITUTION":
                return EntityType.INSTITUTION
            case "ASSET":
                return EntityType.ASSET
            case _:
                return None

    def _parse_relationship_type(self, type_str: str) -> RelationshipType | None:
        """Parse relationship type string to enum."""
        type_upper = type_str.upper().strip()
        match type_upper:
            case "ALIAS_OF":
                return RelationshipType.ALIAS_OF
            case "HAS_ROLE":
                return RelationshipType.HAS_ROLE
            case "RELATED_TO":
                return RelationshipType.RELATED_TO
            case _:
                return None

    def _empty_result(
        self,
        document_id: str,
        chunk_id: str | None,
        page_number: int | None,
    ) -> EntityExtractionResult:
        """Create empty extraction result."""
        return EntityExtractionResult(
            entities=[],
            relationships=[],
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_mig_extractor() -> MIGEntityExtractor:
    """Get singleton MIG entity extractor instance.

    Returns:
        MIGEntityExtractor instance.
    """
    return MIGEntityExtractor()
