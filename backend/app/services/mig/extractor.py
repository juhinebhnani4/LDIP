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
    ExtractionStatus,
    RelationshipType,
)
from app.services.mig.prompts import (
    BATCH_ENTITY_EXTRACTION_PROMPT,
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
        self._event_loop_id: int | None = None  # Track event loop to detect changes
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model

    def _get_current_loop_id(self) -> int | None:
        """Get the ID of the current event loop, or None if no loop is running."""
        try:
            loop = asyncio.get_running_loop()
            return id(loop)
        except RuntimeError:
            # No running event loop
            return None

    def _reset_model(self) -> None:
        """Reset the model instance.

        This is needed when the event loop changes (e.g., new asyncio.run() call)
        because the google.generativeai library maintains internal gRPC connections
        that hold references to the event loop.
        """
        self._model = None
        self._genai = None
        self._event_loop_id = None

    @property
    def model(self):
        """Get or create Gemini model instance.

        IMPORTANT: Automatically resets the model when a new event loop is detected.
        This prevents "Event loop is closed" errors when multiple Celery tasks
        run entity extraction in sequence (each asyncio.run() creates a new loop).

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            MIGConfigurationError: If API key is not configured.
        """
        # Check if event loop has changed - if so, we need a fresh model
        current_loop_id = self._get_current_loop_id()
        if self._model is not None and self._event_loop_id != current_loop_id:
            logger.debug(
                "mig_extractor_loop_changed",
                old_loop_id=self._event_loop_id,
                new_loop_id=current_loop_id,
            )
            self._reset_model()

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
                self._event_loop_id = current_loop_id
                logger.info(
                    "mig_extractor_initialized",
                    model=self.model_name,
                    event_loop_id=current_loop_id,
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
        bbox_ids: list[str] | None = None,
    ) -> EntityExtractionResult:
        """Extract entities and relationships from text.

        Args:
            text: Document text to extract entities from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs for source highlighting.

        Returns:
            EntityExtractionResult containing extracted entities and relationships.

        Raises:
            MIGExtractorError: If extraction fails after retries.
        """
        # Handle empty text - this is success with no entities, not an error
        if not text or not text.strip():
            logger.debug(
                "mig_extraction_empty_text",
                document_id=document_id,
                matter_id=matter_id,
            )
            return EntityExtractionResult(
                status=ExtractionStatus.SUCCESS,
                entities=[],
                relationships=[],
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
                source_bbox_ids=bbox_ids or [],
            )

        # Track truncation metadata
        was_truncated = False
        original_length = len(text)
        processed_length = original_length

        # Truncate if too long
        if len(text) > MAX_TEXT_LENGTH:
            was_truncated = True
            processed_length = MAX_TEXT_LENGTH
            logger.warning(
                "mig_extraction_text_truncated",
                original_length=original_length,
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
                    bbox_ids=bbox_ids,
                )

                # Add truncation metadata to result
                result.was_truncated = was_truncated
                if was_truncated:
                    result.original_length = original_length
                    result.processed_length = processed_length

                processing_time = int((time.time() - start_time) * 1000)

                logger.info(
                    "mig_extraction_complete",
                    document_id=document_id,
                    matter_id=matter_id,
                    entity_count=len(result.entities),
                    relationship_count=len(result.relationships),
                    processing_time_ms=processing_time,
                    attempts=attempt + 1,
                    was_truncated=was_truncated,
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

        # Return error result on failure (Story 3.2: distinct error state)
        return EntityExtractionResult(
            status=ExtractionStatus.ERROR,
            error_message="Entity extraction failed after multiple retries",
            entities=[],
            relationships=[],
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
            source_bbox_ids=bbox_ids or [],
        )

    def extract_entities_sync(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        chunk_id: str | None = None,
        page_number: int | None = None,
        bbox_ids: list[str] | None = None,
    ) -> EntityExtractionResult:
        """Synchronous wrapper for entity extraction.

        For use in Celery tasks or other synchronous contexts.

        Args:
            text: Document text to extract entities from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs for source highlighting.

        Returns:
            EntityExtractionResult containing extracted entities and relationships.
        """
        # Handle empty text - this is success with no entities, not an error
        if not text or not text.strip():
            return EntityExtractionResult(
                status=ExtractionStatus.SUCCESS,
                entities=[],
                relationships=[],
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
                source_bbox_ids=bbox_ids or [],
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
                    bbox_ids=bbox_ids,
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

        # Return error result on failure (Story 3.2: distinct error state)
        return EntityExtractionResult(
            status=ExtractionStatus.ERROR,
            error_message="Entity extraction failed after multiple retries",
            entities=[],
            relationships=[],
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
            source_bbox_ids=bbox_ids or [],
        )

    def _parse_response(
        self,
        response_text: str,
        document_id: str,
        chunk_id: str | None,
        page_number: int | None,
        bbox_ids: list[str] | None = None,
    ) -> EntityExtractionResult:
        """Parse Gemini response into EntityExtractionResult.

        Args:
            response_text: Raw response from Gemini.
            document_id: Source document UUID.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs for source highlighting.

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
                return self._empty_result(
                    document_id, chunk_id, page_number, bbox_ids,
                    is_error=True, error_message="Unexpected response format from extraction"
                )

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
                source_bbox_ids=bbox_ids or [],
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "mig_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return self._empty_result(
                document_id, chunk_id, page_number, bbox_ids,
                is_error=True, error_message="Failed to parse extraction response"
            )

        except Exception as e:
            logger.warning(
                "mig_response_parse_error",
                error=str(e),
            )
            return self._empty_result(
                document_id, chunk_id, page_number, bbox_ids,
                is_error=True, error_message="Failed to parse extraction response"
            )

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
        bbox_ids: list[str] | None = None,
        *,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> EntityExtractionResult:
        """Create empty extraction result.

        Args:
            document_id: Source document UUID.
            chunk_id: Optional source chunk UUID.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs.
            is_error: If True, marks result as error state (Story 3.2).
            error_message: Error message when is_error=True.

        Returns:
            Empty EntityExtractionResult with appropriate status.
        """
        return EntityExtractionResult(
            status=ExtractionStatus.ERROR if is_error else ExtractionStatus.SUCCESS,
            error_message=error_message if is_error else None,
            entities=[],
            relationships=[],
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
            source_bbox_ids=bbox_ids or [],
        )

    async def extract_entities_batch(
        self,
        chunks: list[dict],
        document_id: str,
        matter_id: str,
    ) -> list[EntityExtractionResult]:
        """Extract entities from multiple chunks in a single API call.

        MEGA-BATCH OPTIMIZATION: Combines multiple chunks into one prompt,
        reducing API calls from N to 1 and improving throughput 3-5x.

        Args:
            chunks: List of chunk dicts with 'id', 'content', 'page_number', 'bbox_ids'.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.

        Returns:
            List of EntityExtractionResult, one per input chunk.
        """
        if not chunks:
            return []

        # Build sections text
        sections_parts = []
        chunk_map: dict[str, dict] = {}  # chunk_id -> chunk info

        total_text_length = 0
        max_batch_length = 25000  # Leave room for prompt overhead

        for chunk in chunks:
            chunk_id = chunk.get("id", "")
            content = chunk.get("content", "")
            page_number = chunk.get("page_number")
            bbox_ids = chunk.get("bbox_ids") or []

            if not content or not content.strip():
                continue

            # Truncate individual chunks if needed
            if len(content) > 6000:
                content = content[:6000]

            # Check if adding this chunk would exceed limit
            section_text = f"=== SECTION {chunk_id} (page: {page_number}) ===\n{content}\n"
            if total_text_length + len(section_text) > max_batch_length:
                break

            sections_parts.append(section_text)
            chunk_map[chunk_id] = {
                "chunk_id": chunk_id,
                "page_number": page_number,
                "bbox_ids": [str(b) for b in bbox_ids] if bbox_ids else [],
            }
            total_text_length += len(section_text)

        if not sections_parts:
            return [
                self._empty_result(
                    document_id,
                    c.get("id"),
                    c.get("page_number"),
                    [str(b) for b in c.get("bbox_ids") or []] if c.get("bbox_ids") else [],
                )
                for c in chunks
            ]

        sections_text = "\n".join(sections_parts)
        prompt = BATCH_ENTITY_EXTRACTION_PROMPT.format(sections=sections_text)

        start_time = time.time()
        results: list[EntityExtractionResult] = []

        try:
            response = await self.model.generate_content_async(prompt)
            parsed_sections = self._parse_batch_response(
                response.text,
                document_id=document_id,
                chunk_map=chunk_map,
            )

            # Build results list matching input order
            for chunk in chunks:
                chunk_id = chunk.get("id", "")
                if chunk_id in parsed_sections:
                    results.append(parsed_sections[chunk_id])
                else:
                    # Chunk not in response (maybe filtered out or failed)
                    chunk_bbox_ids = [str(b) for b in chunk.get("bbox_ids") or []] if chunk.get("bbox_ids") else []
                    results.append(self._empty_result(
                        document_id,
                        chunk_id,
                        chunk.get("page_number"),
                        chunk_bbox_ids,
                    ))

            processing_time = int((time.time() - start_time) * 1000)
            total_entities = sum(len(r.entities) for r in results)

            logger.info(
                "mig_batch_extraction_complete",
                document_id=document_id,
                matter_id=matter_id,
                chunks_processed=len(chunk_map),
                total_entities=total_entities,
                processing_time_ms=processing_time,
            )

            return results

        except Exception as e:
            logger.error(
                "mig_batch_extraction_failed",
                document_id=document_id,
                error=str(e),
                chunks_count=len(chunks),
            )
            # Return error results for all chunks on failure (Story 3.2)
            return [
                self._empty_result(
                    document_id,
                    c.get("id"),
                    c.get("page_number"),
                    [str(b) for b in c.get("bbox_ids") or []] if c.get("bbox_ids") else [],
                    is_error=True,
                    error_message="Batch extraction failed",
                )
                for c in chunks
            ]

    def _parse_batch_response(
        self,
        response_text: str,
        document_id: str,
        chunk_map: dict[str, dict],
    ) -> dict[str, EntityExtractionResult]:
        """Parse batch extraction response.

        Args:
            response_text: Raw response from Gemini.
            document_id: Source document UUID.
            chunk_map: Map of chunk_id -> chunk info (includes page_number, bbox_ids).

        Returns:
            Dict mapping chunk_id -> EntityExtractionResult.
        """
        results: dict[str, EntityExtractionResult] = {}

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

            parsed = json.loads(json_text)

            if not isinstance(parsed, dict):
                return results

            # Parse sections
            sections = parsed.get("sections", [])
            for section in sections:
                section_id = section.get("section_id", "")
                if section_id not in chunk_map:
                    continue

                chunk_info = chunk_map[section_id]

                # Build a temporary parsed dict to reuse existing parsing
                temp_parsed = {
                    "entities": section.get("entities", []),
                    "relationships": section.get("relationships", []),
                }

                # Parse using existing method (pass bbox_ids from chunk_map)
                result = self._parse_response(
                    json.dumps(temp_parsed),
                    document_id=document_id,
                    chunk_id=section_id,
                    page_number=chunk_info.get("page_number"),
                    bbox_ids=chunk_info.get("bbox_ids"),
                )
                results[section_id] = result

        except json.JSONDecodeError as e:
            logger.warning(
                "mig_batch_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
        except Exception as e:
            logger.warning(
                "mig_batch_response_parse_error",
                error=str(e),
            )

        return results


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
