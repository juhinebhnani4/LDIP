"""Entity Linking Service for Timeline Events.

Links events to canonical entities from the Matter Identity Graph (MIG).
Uses the existing EntityResolver for name matching and optionally
Gemini for complex entity mention extraction.

CRITICAL: Uses Gemini for entity extraction per LLM routing rules -
this is an ingestion task, NOT user-facing reasoning.

Story 4-3: Events Table + MIG Integration
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.models.entity import EntityNode, EntityType
from app.models.timeline import RawEvent
from app.services.mig.entity_resolver import EntityResolver, get_entity_resolver
from app.services.mig.graph import MIGGraphService, get_mig_graph_service

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Confidence threshold for entity linking
# Can be overridden via ENTITY_LINK_CONFIDENCE_THRESHOLD env var
import os as _os

LINK_CONFIDENCE_THRESHOLD = float(
    _os.environ.get("ENTITY_LINK_CONFIDENCE_THRESHOLD", "0.7")
)

# Maximum retries for Gemini calls
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0

# Batch size for entity linking
MAX_BATCH_SIZE = 20

# Indian title patterns for entity mention extraction
INDIAN_TITLE_PATTERNS = [
    r"\bShri\b", r"\bSmt\b", r"\bKumari\b", r"\bDr\.?\b",
    r"\bAdv\.?\b", r"\bAdvocate\b", r"\bHon\.?\b", r"\bHon'ble\b",
    r"\bJustice\b", r"\bMr\.?\b", r"\bMrs\.?\b", r"\bMs\.?\b",
]

# Organization indicators
ORG_INDICATORS = [
    r"\bLtd\.?\b", r"\bLimited\b", r"\bPvt\.?\b", r"\bPrivate\b",
    r"\bCorp\.?\b", r"\bCorporation\b", r"\bInc\.?\b",
    r"\bBank\b", r"\bCompany\b", r"\bAssociation\b",
    r"\bTrust\b", r"\bFoundation\b", r"\bBoard\b",
]

# Entity extraction prompt for Gemini (when names are ambiguous)
ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are an entity extraction specialist for Indian legal documents.
Your task is to identify entity mentions (people, organizations, institutions) in event descriptions.

Focus on:
1. Named individuals with titles (Shri, Smt, Adv, Hon'ble Justice, etc.)
2. Organizations (banks, companies, trusts, government bodies)
3. Institutions (courts, tribunals, authorities)

Return ONLY a JSON array of extracted entity mentions. Each mention should include:
- text: The exact entity mention as it appears
- type: PERSON, ORG, or INSTITUTION
- confidence: 0-1 score of extraction confidence

Do NOT include:
- Generic references ("the petitioner", "the respondent")
- Pronouns
- Job titles without names
"""

ENTITY_EXTRACTION_USER_PROMPT = """Extract entity mentions from this legal event description:

"{description}"

Return a JSON array of entity mentions found. If no specific entities are mentioned, return an empty array [].

Example output:
[
  {{"text": "Nirav Dineshbhai Jobalia", "type": "PERSON", "confidence": 0.95}},
  {{"text": "HDFC Bank Ltd", "type": "ORG", "confidence": 0.90}}
]"""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EntityMention:
    """An entity mention extracted from event text."""

    text: str
    entity_type: EntityType
    confidence: float = 0.8


@dataclass
class EntityLinkResult:
    """Result of linking an entity mention to a canonical entity."""

    mention_text: str
    entity_id: str
    canonical_name: str
    entity_type: EntityType
    similarity_score: float
    matched_via: str = "canonical_name"  # or "alias"


@dataclass
class EventEntityLinkingResult:
    """Result of entity linking for a single event."""

    event_id: str
    entity_ids: list[str] = field(default_factory=list)
    link_details: list[EntityLinkResult] = field(default_factory=list)
    mentions_found: int = 0
    mentions_linked: int = 0
    processing_time_ms: int = 0


# =============================================================================
# Exceptions
# =============================================================================


class EntityLinkerError(Exception):
    """Base exception for entity linker operations."""

    def __init__(
        self,
        message: str,
        code: str = "ENTITY_LINKER_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class LinkerConfigurationError(EntityLinkerError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="LINKER_NOT_CONFIGURED", is_retryable=False)


# =============================================================================
# Service Implementation
# =============================================================================


class EventEntityLinker:
    """Service for linking timeline events to MIG entities.

    Links entities mentioned in event descriptions to canonical entities
    in the Matter Identity Graph using:
    - Pattern-based extraction (titles, organization indicators)
    - Name similarity matching via EntityResolver
    - Optional Gemini extraction for complex cases

    Example:
        >>> linker = EventEntityLinker()
        >>> entity_ids = await linker.link_entities_to_event(
        ...     event_id="event-123",
        ...     description="Shri Nirav Jobalia filed a petition on 15/01/2024",
        ...     matter_id="matter-456",
        ... )
        >>> entity_ids
        ["entity-uuid-1"]
    """

    def __init__(self) -> None:
        """Initialize event entity linker."""
        self._model = None
        self._genai = None
        self._resolver: EntityResolver | None = None
        self._mig_service: MIGGraphService | None = None
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model

    @property
    def resolver(self) -> EntityResolver:
        """Get entity resolver instance."""
        if self._resolver is None:
            self._resolver = get_entity_resolver()
        return self._resolver

    @property
    def mig_service(self) -> MIGGraphService:
        """Get MIG graph service instance."""
        if self._mig_service is None:
            self._mig_service = get_mig_graph_service()
        return self._mig_service

    @property
    def model(self):
        """Get or create Gemini model instance.

        Returns:
            Gemini GenerativeModel instance or None if not configured.
        """
        if self._model is None:
            if not self.api_key:
                logger.debug("entity_linker_gemini_not_configured")
                return None

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=ENTITY_EXTRACTION_SYSTEM_PROMPT,
                )
                logger.info(
                    "entity_linker_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.warning("entity_linker_gemini_init_failed", error=str(e))
                return None

        return self._model

    # =========================================================================
    # Public Methods
    # =========================================================================

    async def link_entities_to_event(
        self,
        event_id: str,
        description: str,
        matter_id: str,
        use_gemini: bool = False,
    ) -> list[str]:
        """Link entities mentioned in an event description to canonical entities.

        Args:
            event_id: Event UUID.
            description: Event description text to extract entities from.
            matter_id: Matter UUID for entity lookup.
            use_gemini: If True, use Gemini for complex entity extraction.

        Returns:
            List of matched entity_id UUIDs.
        """
        start_time = time.time()

        if not description or not description.strip():
            return []

        # Step 1: Extract potential entity mentions from text
        mentions = self._extract_entity_mentions(description)

        # Optionally use Gemini for additional extraction
        if use_gemini and self.model:
            gemini_mentions = await self._extract_mentions_with_gemini(description)
            # Merge mentions, avoiding duplicates
            existing_texts = {m.text.lower() for m in mentions}
            for gm in gemini_mentions:
                if gm.text.lower() not in existing_texts:
                    mentions.append(gm)
                    existing_texts.add(gm.text.lower())

        if not mentions:
            logger.debug(
                "entity_linking_no_mentions",
                event_id=event_id,
                description_preview=description[:100],
            )
            return []

        # Step 2: Load all entities for the matter using pagination to avoid OOM
        entities = await self._load_entities_paginated(matter_id)

        if not entities:
            logger.debug(
                "entity_linking_no_mig_entities",
                event_id=event_id,
                matter_id=matter_id,
            )
            return []

        # Step 3: Match mentions to entities
        matched_entity_ids: set[str] = set()

        for mention in mentions:
            match = self._find_best_entity_match(mention, entities)
            if match:
                matched_entity_ids.add(match.entity_id)

        processing_time = int((time.time() - start_time) * 1000)

        logger.debug(
            "entity_linking_complete",
            event_id=event_id,
            mentions_found=len(mentions),
            entities_linked=len(matched_entity_ids),
            processing_time_ms=processing_time,
        )

        return list(matched_entity_ids)

    async def link_entities_batch(
        self,
        events: list[RawEvent],
        matter_id: str,
        use_gemini: bool = False,
    ) -> dict[str, list[str]]:
        """Batch entity linking for multiple events.

        More efficient than individual calls - loads matter entities once.

        Args:
            events: List of RawEvent objects to link.
            matter_id: Matter UUID for entity lookup.
            use_gemini: If True, use Gemini for complex extraction.

        Returns:
            Dict mapping event_id to list of entity_ids.
        """
        start_time = time.time()

        if not events:
            return {}

        # Load all entities for the matter once using pagination to avoid OOM
        entities = await self._load_entities_paginated(matter_id)

        if not entities:
            logger.info(
                "entity_linking_batch_no_entities",
                matter_id=matter_id,
                events_count=len(events),
            )
            return {e.id: [] for e in events}

        results: dict[str, list[str]] = {}

        for event in events:
            # Extract mentions
            mentions = self._extract_entity_mentions(event.description)

            if use_gemini and self.model:
                gemini_mentions = await self._extract_mentions_with_gemini(
                    event.description
                )
                existing_texts = {m.text.lower() for m in mentions}
                for gm in gemini_mentions:
                    if gm.text.lower() not in existing_texts:
                        mentions.append(gm)
                        existing_texts.add(gm.text.lower())

            # Match mentions to entities
            matched_entity_ids: set[str] = set()
            for mention in mentions:
                match = self._find_best_entity_match(mention, entities)
                if match:
                    matched_entity_ids.add(match.entity_id)

            results[event.id] = list(matched_entity_ids)

        processing_time = int((time.time() - start_time) * 1000)

        total_linked = sum(len(ids) for ids in results.values())
        events_with_links = sum(1 for ids in results.values() if ids)

        logger.info(
            "entity_linking_batch_complete",
            matter_id=matter_id,
            events_processed=len(events),
            events_with_links=events_with_links,
            total_entities_linked=total_linked,
            processing_time_ms=processing_time,
        )

        return results

    def link_entities_to_event_sync(
        self,
        event_id: str,
        description: str,
        matter_id: str,
        entities: list[EntityNode],
    ) -> list[str]:
        """Synchronous entity linking for Celery tasks.

        Requires pre-loaded entities list to avoid async calls.

        Args:
            event_id: Event UUID.
            description: Event description text.
            matter_id: Matter UUID (for logging).
            entities: Pre-loaded list of EntityNode objects for the matter.

        Returns:
            List of matched entity_id UUIDs.
        """
        if not description or not description.strip():
            return []

        # Extract mentions (pattern-based only in sync mode)
        mentions = self._extract_entity_mentions(description)

        if not mentions or not entities:
            return []

        # Match mentions to entities
        matched_entity_ids: set[str] = set()
        for mention in mentions:
            match = self._find_best_entity_match(mention, entities)
            if match:
                matched_entity_ids.add(match.entity_id)

        return list(matched_entity_ids)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _load_entities_paginated(
        self,
        matter_id: str,
        batch_size: int = 500,
    ) -> list[EntityNode]:
        """Load all entities for a matter using pagination to avoid OOM.

        Args:
            matter_id: Matter UUID.
            batch_size: Number of entities per page (default 500).

        Returns:
            List of EntityNode objects.
        """
        all_entities: list[EntityNode] = []
        page = 1

        while True:
            entities, total = await self.mig_service.get_entities_by_matter(
                matter_id=matter_id,
                page=page,
                per_page=batch_size,
            )

            all_entities.extend(entities)

            # Check if we've loaded all entities
            if len(all_entities) >= total or not entities:
                break
            page += 1

        logger.debug(
            "entities_loaded_paginated",
            matter_id=matter_id,
            total_entities=len(all_entities),
            pages_loaded=page,
        )

        return all_entities

    # =========================================================================
    # Entity Mention Extraction
    # =========================================================================

    def _extract_entity_mentions(self, text: str) -> list[EntityMention]:
        """Extract potential entity mentions using pattern matching.

        Looks for:
        - Names with Indian titles (Shri, Smt, Adv, etc.)
        - Organization indicators (Ltd, Bank, etc.)
        - Capitalized proper nouns

        Args:
            text: Text to extract mentions from.

        Returns:
            List of EntityMention objects.
        """
        if not text:
            return []

        mentions: list[EntityMention] = []
        seen_texts: set[str] = set()

        # Pattern 1: Title + Name (e.g., "Shri Nirav Jobalia")
        try:
            title_pattern = (
                r"(?:" + "|".join(INDIAN_TITLE_PATTERNS) + r")\s+"
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})"
            )
            for match in re.finditer(title_pattern, text, re.IGNORECASE):
                full_match = match.group(0).strip()
                if full_match.lower() not in seen_texts:
                    mentions.append(
                        EntityMention(
                            text=full_match,
                            entity_type=EntityType.PERSON,
                            confidence=0.9,
                        )
                    )
                    seen_texts.add(full_match.lower())
        except re.error as e:
            logger.warning("entity_extraction_title_pattern_error", error=str(e))

        # Pattern 2: Organizations with indicators
        for indicator in ORG_INDICATORS:
            try:
                org_pattern = rf"([A-Z][A-Za-z\s&]+\s*{indicator})"
                for match in re.finditer(org_pattern, text):
                    org_text = match.group(1).strip()
                    if len(org_text) > 3 and org_text.lower() not in seen_texts:
                        mentions.append(
                            EntityMention(
                                text=org_text,
                                entity_type=EntityType.ORG,
                                confidence=0.85,
                            )
                        )
                        seen_texts.add(org_text.lower())
            except re.error as e:
                logger.warning(
                    "entity_extraction_org_pattern_error",
                    indicator=indicator,
                    error=str(e),
                )

        # Pattern 3: Court/Institution names
        try:
            court_pattern = (
                r"((?:High Court|Supreme Court|District Court|Sessions Court|"
                r"Tribunal|Authority|Commission|Board|Council)[^,\.]*)"
            )
            for match in re.finditer(court_pattern, text, re.IGNORECASE):
                inst_text = match.group(1).strip()
                if len(inst_text) > 5 and inst_text.lower() not in seen_texts:
                    mentions.append(
                        EntityMention(
                            text=inst_text,
                            entity_type=EntityType.INSTITUTION,
                            confidence=0.85,
                        )
                    )
                    seen_texts.add(inst_text.lower())
        except re.error as e:
            logger.warning("entity_extraction_court_pattern_error", error=str(e))

        # Pattern 4: Capitalized proper nouns (potential person names)
        # Match 2-4 consecutive capitalized words
        try:
            proper_noun_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
            for match in re.finditer(proper_noun_pattern, text):
                name = match.group(1).strip()
                # Filter out common false positives
                lower_name = name.lower()
                if (
                    lower_name not in seen_texts
                    and len(name) > 5
                    and not self._is_common_phrase(lower_name)
                ):
                    mentions.append(
                        EntityMention(
                            text=name,
                            entity_type=EntityType.PERSON,
                            confidence=0.6,  # Lower confidence for bare proper nouns
                        )
                    )
                    seen_texts.add(lower_name)
        except re.error as e:
            logger.warning("entity_extraction_proper_noun_pattern_error", error=str(e))

        return mentions

    def _is_common_phrase(self, text: str) -> bool:
        """Check if text is a common phrase (not an entity)."""
        common_phrases = {
            "the petitioner", "the respondent", "the court",
            "the above", "the same", "the said", "the matter",
            "high court", "supreme court", "district court",
            "civil suit", "writ petition", "special leave",
        }
        return text in common_phrases

    async def _extract_mentions_with_gemini(
        self, description: str
    ) -> list[EntityMention]:
        """Use Gemini to extract entity mentions for complex cases.

        Args:
            description: Event description text.

        Returns:
            List of EntityMention objects.
        """
        if not self.model:
            return []

        prompt = ENTITY_EXTRACTION_USER_PROMPT.format(description=description)

        retry_delay = INITIAL_RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.model.generate_content_async(prompt)
                return self._parse_gemini_extraction(response.text)

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "entity_extraction_rate_limited",
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                else:
                    logger.warning(
                        "entity_extraction_gemini_failed",
                        error=str(e),
                    )
                    break

        return []

    def _parse_gemini_extraction(self, response_text: str) -> list[EntityMention]:
        """Parse Gemini entity extraction response.

        Args:
            response_text: Raw response from Gemini.

        Returns:
            List of EntityMention objects.
        """
        try:
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

            if not isinstance(parsed, list):
                return []

            mentions = []
            for item in parsed:
                if isinstance(item, dict) and "text" in item:
                    entity_type_str = item.get("type", "PERSON").upper()
                    try:
                        entity_type = EntityType(entity_type_str)
                    except ValueError:
                        entity_type = EntityType.PERSON

                    mentions.append(
                        EntityMention(
                            text=item["text"],
                            entity_type=entity_type,
                            confidence=float(item.get("confidence", 0.8)),
                        )
                    )

            return mentions

        except json.JSONDecodeError as e:
            logger.warning(
                "entity_extraction_parse_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return []

    # =========================================================================
    # Entity Matching
    # =========================================================================

    def _find_best_entity_match(
        self,
        mention: EntityMention,
        entities: list[EntityNode],
    ) -> EntityLinkResult | None:
        """Find the best matching entity for a mention.

        Uses EntityResolver for name similarity calculation.

        Args:
            mention: Entity mention to match.
            entities: List of candidate entities.

        Returns:
            EntityLinkResult if match found above threshold, else None.
        """
        best_match: EntityLinkResult | None = None
        best_score = 0.0

        for entity in entities:
            # Skip different entity types (PERSON won't match ORG)
            # But allow flexible matching since extraction might be wrong
            if (
                mention.entity_type != entity.entity_type
                and mention.confidence > 0.8  # High confidence = stricter matching
            ):
                continue

            # Check canonical name
            canonical_score = self.resolver.calculate_name_similarity(
                mention.text, entity.canonical_name
            )

            if canonical_score > best_score and canonical_score >= LINK_CONFIDENCE_THRESHOLD:
                best_score = canonical_score
                best_match = EntityLinkResult(
                    mention_text=mention.text,
                    entity_id=entity.id,
                    canonical_name=entity.canonical_name,
                    entity_type=entity.entity_type,
                    similarity_score=canonical_score,
                    matched_via="canonical_name",
                )

            # Check aliases
            for alias in entity.aliases or []:
                alias_score = self.resolver.calculate_name_similarity(
                    mention.text, alias
                )

                if alias_score > best_score and alias_score >= LINK_CONFIDENCE_THRESHOLD:
                    best_score = alias_score
                    best_match = EntityLinkResult(
                        mention_text=mention.text,
                        entity_id=entity.id,
                        canonical_name=entity.canonical_name,
                        entity_type=entity.entity_type,
                        similarity_score=alias_score,
                        matched_via=f"alias:{alias}",
                    )

        if best_match:
            logger.debug(
                "entity_match_found",
                mention=mention.text,
                entity_id=best_match.entity_id,
                canonical_name=best_match.canonical_name,
                score=best_score,
                matched_via=best_match.matched_via,
            )

        return best_match


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_event_entity_linker() -> EventEntityLinker:
    """Get singleton event entity linker instance.

    Returns:
        EventEntityLinker instance.
    """
    return EventEntityLinker()
