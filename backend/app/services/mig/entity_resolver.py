"""Alias Resolution Service for MIG (Matter Identity Graph).

Provides name similarity algorithms and alias resolution for entity names.
Links name variants (e.g., "Nirav Jobalia", "N.D. Jobalia", "Mr. Jobalia")
to a single canonical entity using:
- String similarity algorithms (Jaro-Winkler)
- Name component matching (first/last name)
- Title normalization
- Contextual analysis via Gemini for ambiguous cases

CRITICAL: Uses Gemini for contextual analysis per LLM routing rules -
this is a pattern matching task, NOT user-facing reasoning.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from functools import lru_cache

import structlog
from rapidfuzz.distance import JaroWinkler as JaroWinklerModule

from app.core.config import get_settings
from app.models.entity import EntityEdgeCreate, EntityNode, EntityType, RelationshipType
from app.services.mig.alias_prompts import (
    ALIAS_BATCH_SYSTEM_PROMPT,
    ALIAS_BATCH_USER_PROMPT,
    ALIAS_CONTEXT_SYSTEM_PROMPT,
    ALIAS_CONTEXT_USER_PROMPT,
    format_pairs_for_batch,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Indian honorific titles (common in legal documents)
INDIAN_TITLES = frozenset({
    "shri", "smt", "kumari", "dr", "adv", "advocate", "hon", "honourable",
    "justice", "mr", "mrs", "ms", "miss", "prof", "professor",
})

# Standard title normalization mapping
TITLE_NORMALIZATIONS = {
    "shri": "mr",
    "smt": "mrs",
    "kumari": "ms",
    "adv": "advocate",
    "hon": "honourable",
    "prof": "professor",
}

# Common suffixes to strip
SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "esq"})

# Similarity thresholds
HIGH_SIMILARITY_THRESHOLD = 0.85  # Auto-link threshold
MEDIUM_SIMILARITY_THRESHOLD = 0.60  # Context analysis threshold
LOW_SIMILARITY_THRESHOLD = 0.40  # Skip threshold

# Context analysis confidence threshold
CONTEXT_CONFIDENCE_THRESHOLD = 0.70  # Below this, don't auto-link

# Gemini retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0

# Batch size for context analysis
CONTEXT_ANALYSIS_BATCH_SIZE = 5


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class NameComponents:
    """Parsed components of a name.

    Supports Indian naming conventions including:
    - Patronymics (middle name derived from father's name)
    - Various titles (Shri, Smt, Adv, etc.)
    """

    title: str | None = None
    first_name: str | None = None
    middle_name: str | None = None  # Often patronymic in Indian names
    last_name: str | None = None
    suffix: str | None = None
    raw_name: str = ""

    @property
    def name_without_title(self) -> str:
        """Get full name without title."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)

    @property
    def initials(self) -> str:
        """Get initials from name components."""
        initials = []
        if self.first_name:
            initials.append(self.first_name[0].upper())
        if self.middle_name:
            initials.append(self.middle_name[0].upper())
        if self.last_name:
            initials.append(self.last_name[0].upper())
        return "".join(initials)


@dataclass
class AliasCandidate:
    """Candidate alias pair for resolution."""

    entity_id: str
    entity_name: str
    candidate_entity_id: str
    candidate_name: str
    similarity_score: float
    name_similarity: float = 0.0
    component_similarity: float = 0.0
    initial_match_score: float = 0.0
    context_confidence: float | None = None
    is_auto_linked: bool = False

    @property
    def final_score(self) -> float:
        """Calculate final score including context if available."""
        if self.context_confidence is not None:
            return (self.similarity_score + self.context_confidence) / 2
        return self.similarity_score


@dataclass
class AliasResolutionResult:
    """Result of alias resolution for a matter."""

    matter_id: str
    entities_processed: int = 0
    alias_pairs_found: int = 0
    aliases_created: int = 0
    high_confidence_links: int = 0
    medium_confidence_links: int = 0
    skipped_low_confidence: int = 0
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Exceptions
# =============================================================================


class AliasResolutionError(Exception):
    """Base exception for alias resolution operations."""

    def __init__(
        self,
        message: str,
        code: str = "ALIAS_RESOLUTION_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


# =============================================================================
# Service Implementation
# =============================================================================


class EntityResolver:
    """Service for resolving name variants and linking aliases.

    Handles:
    - Name similarity calculation using multiple algorithms
    - Name component extraction (title, first, middle, last, suffix)
    - Indian name patterns (patronymics, honorifics)
    - Initial variant matching (N.D. -> Nirav D.)
    - Contextual disambiguation via Gemini

    Example:
        >>> resolver = EntityResolver()
        >>> score = resolver._calculate_name_similarity(
        ...     "N.D. Jobalia", "Nirav D. Jobalia"
        ... )
        >>> score > 0.7
        True
    """

    def __init__(self) -> None:
        """Initialize entity resolver."""
        # JaroWinkler is a module, use its functions directly
        self._jaro = JaroWinklerModule

    # =========================================================================
    # Public Methods
    # =========================================================================

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate overall similarity between two names.

        Uses weighted combination of:
        - Jaro-Winkler string similarity (40%)
        - Component matching (30%)
        - Initial expansion matching (20%)
        - Normalized (title-free) matching (10%)

        Args:
            name1: First name to compare.
            name2: Second name to compare.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not name1 or not name2:
            return 0.0

        # Normalize for comparison
        n1_lower = name1.lower().strip()
        n2_lower = name2.lower().strip()

        # Exact match
        if n1_lower == n2_lower:
            return 1.0

        # Extract components
        comp1 = self.extract_name_components(name1)
        comp2 = self.extract_name_components(name2)

        # Calculate component scores
        jaro_score = self._jaro.normalized_similarity(n1_lower, n2_lower)
        component_score = self._calculate_component_match(comp1, comp2)
        initial_score = self._calculate_initial_match(comp1, comp2)
        normalized_score = self._calculate_normalized_match(comp1, comp2)

        # Weighted combination
        final_score = (
            jaro_score * 0.4
            + component_score * 0.3
            + initial_score * 0.2
            + normalized_score * 0.1
        )

        return min(1.0, final_score)

    def extract_name_components(self, name: str) -> NameComponents:
        """Extract name components (title, first, middle, last, suffix).

        Handles Indian naming conventions:
        - Patronymics: "Nirav Dineshbhai Jobalia"
        - Honorifics: "Shri", "Smt", "Adv"
        - Initials: "N.D. Jobalia"

        Args:
            name: Name string to parse.

        Returns:
            NameComponents with parsed elements.
        """
        if not name:
            return NameComponents(raw_name="")

        # Normalize whitespace
        name = " ".join(name.split())
        components = NameComponents(raw_name=name)

        # Split into parts
        parts = name.split()
        if not parts:
            return components

        # Expand combined initials like "N.D." into ["N.", "D."]
        expanded_parts = []
        for part in parts:
            if self._is_combined_initials(part):
                # Split "N.D." into ["N.", "D."]
                for initial in part.split("."):
                    if initial:
                        expanded_parts.append(initial + ".")
            else:
                expanded_parts.append(part)
        parts = expanded_parts

        # Extract title if present
        first_part_lower = parts[0].lower().rstrip(".")
        if first_part_lower in INDIAN_TITLES:
            components.title = parts[0]
            parts = parts[1:]

        if not parts:
            return components

        # Extract suffix if present
        last_part_lower = parts[-1].lower().rstrip(".")
        if last_part_lower in SUFFIXES:
            components.suffix = parts[-1]
            parts = parts[:-1]

        if not parts:
            return components

        # Handle initials (e.g., "N.D.")
        # Check if we have initials pattern
        is_initials = all(self._is_initial(p) for p in parts[:-1]) if len(parts) > 1 else False

        if len(parts) == 1:
            # Single name - treat as last name
            components.last_name = parts[0]
        elif len(parts) == 2:
            if is_initials:
                # "N. Jobalia" -> first initial + last name
                components.first_name = parts[0]
                components.last_name = parts[1]
            else:
                # "Nirav Jobalia" -> first + last
                components.first_name = parts[0]
                components.last_name = parts[1]
        elif len(parts) == 3:
            if is_initials:
                # "N.D. Jobalia" -> first initial + middle initial + last
                components.first_name = parts[0]
                components.middle_name = parts[1]
                components.last_name = parts[2]
            else:
                # "Nirav Dineshbhai Jobalia" -> first + middle + last
                components.first_name = parts[0]
                components.middle_name = parts[1]
                components.last_name = parts[2]
        else:
            # More than 3 parts - first, everything in middle, last
            components.first_name = parts[0]
            components.middle_name = " ".join(parts[1:-1])
            components.last_name = parts[-1]

        return components

    def find_potential_aliases(
        self,
        entity: EntityNode,
        candidates: list[EntityNode],
    ) -> list[AliasCandidate]:
        """Find potential alias candidates for an entity.

        Args:
            entity: Entity to find aliases for.
            candidates: List of candidate entities to compare against.

        Returns:
            List of AliasCandidate objects sorted by similarity score.
        """
        alias_candidates = []

        for candidate in candidates:
            # Skip self-comparison
            if entity.id == candidate.id:
                continue

            # Skip different entity types (PERSON vs ORG don't alias)
            if entity.entity_type != candidate.entity_type:
                continue

            # Calculate similarity
            similarity = self.calculate_name_similarity(
                entity.canonical_name,
                candidate.canonical_name,
            )

            # Skip low similarity
            if similarity < LOW_SIMILARITY_THRESHOLD:
                continue

            # Extract component scores for debugging
            comp1 = self.extract_name_components(entity.canonical_name)
            comp2 = self.extract_name_components(candidate.canonical_name)

            alias_candidates.append(
                AliasCandidate(
                    entity_id=entity.id,
                    entity_name=entity.canonical_name,
                    candidate_entity_id=candidate.id,
                    candidate_name=candidate.canonical_name,
                    similarity_score=similarity,
                    name_similarity=self._jaro.normalized_similarity(
                        entity.canonical_name.lower(),
                        candidate.canonical_name.lower(),
                    ),
                    component_similarity=self._calculate_component_match(comp1, comp2),
                    initial_match_score=self._calculate_initial_match(comp1, comp2),
                    is_auto_linked=similarity >= HIGH_SIMILARITY_THRESHOLD,
                )
            )

        # Sort by similarity score descending
        alias_candidates.sort(key=lambda x: x.similarity_score, reverse=True)

        return alias_candidates

    async def analyze_context_for_alias(
        self,
        name1: str,
        context1: str,
        name2: str,
        context2: str,
    ) -> float:
        """Use Gemini to analyze context for alias determination.

        For medium-similarity pairs where string similarity alone is insufficient,
        uses Gemini Flash to analyze surrounding document context.

        Args:
            name1: First name.
            context1: Context text around first name.
            name2: Second name.
            context2: Context text around second name.

        Returns:
            Confidence score (0-1) that names refer to same entity.
        """
        # Initialize Gemini
        model = self._get_gemini_model()
        if model is None:
            logger.warning("alias_context_gemini_unavailable")
            return 0.5  # Return neutral score if Gemini unavailable

        # Build prompt
        prompt = ALIAS_CONTEXT_USER_PROMPT.format(
            name1=name1,
            context1=context1 or "(no context available)",
            name2=name2,
            context2=context2 or "(no context available)",
        )

        # Call Gemini with retry
        retry_delay = INITIAL_RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            try:
                response = await model.generate_content_async(prompt)
                result = self._parse_context_response(response.text)

                logger.debug(
                    "alias_context_analysis_complete",
                    name1=name1,
                    name2=name2,
                    same_entity=result.get("same_entity"),
                    confidence=result.get("confidence"),
                )

                return float(result.get("confidence", 0.5))

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "alias_context_rate_limited",
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                else:
                    logger.warning(
                        "alias_context_analysis_failed",
                        name1=name1,
                        name2=name2,
                        error=str(e),
                    )
                    break

        return 0.5  # Return neutral score on failure

    async def analyze_batch_context(
        self,
        pairs: list[dict],
    ) -> dict[str, float]:
        """Analyze multiple name pairs in a single Gemini call.

        More efficient than individual calls for medium-similarity pairs.

        Args:
            pairs: List of dicts with keys: pair_id, name1, context1, name2, context2

        Returns:
            Dict mapping pair_id to confidence score.
        """
        if not pairs:
            return {}

        model = self._get_gemini_model()
        if model is None:
            return {p["pair_id"]: 0.5 for p in pairs}

        # Format pairs for batch prompt
        pairs_text = format_pairs_for_batch(pairs)
        prompt = ALIAS_BATCH_USER_PROMPT.format(pairs_text=pairs_text)

        retry_delay = INITIAL_RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            try:
                response = await model.generate_content_async(prompt)
                results = self._parse_batch_response(response.text)

                # Map results by pair_id
                confidence_map = {}
                for result in results:
                    pair_id = result.get("pair_id", "")
                    confidence = float(result.get("confidence", 0.5))
                    confidence_map[pair_id] = confidence

                logger.debug(
                    "alias_batch_analysis_complete",
                    pairs_count=len(pairs),
                    results_count=len(confidence_map),
                )

                return confidence_map

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "429" in error_str or "rate" in error_str

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                else:
                    logger.warning(
                        "alias_batch_analysis_failed",
                        pairs_count=len(pairs),
                        error=str(e),
                    )
                    break

        # Return neutral scores on failure
        return {p["pair_id"]: 0.5 for p in pairs}

    async def resolve_aliases(
        self,
        matter_id: str,
        entities: list[EntityNode],
        entity_contexts: dict[str, str] | None = None,
    ) -> tuple[AliasResolutionResult, list[EntityEdgeCreate]]:
        """Resolve aliases among a set of entities.

        Three-phase resolution:
        1. High similarity (>0.85): Auto-link as aliases
        2. Medium similarity (0.60-0.85): Use Gemini context analysis
        3. Low similarity (<0.60): Skip

        Args:
            matter_id: Matter UUID for isolation.
            entities: List of entities to analyze.
            entity_contexts: Optional dict mapping entity_id to context text.

        Returns:
            Tuple of (AliasResolutionResult, list of EntityEdgeCreate to create).
        """
        start_time = time.time()
        result = AliasResolutionResult(matter_id=matter_id)
        edges_to_create: list[EntityEdgeCreate] = []

        if not entities:
            return result, edges_to_create

        # Group entities by type
        entities_by_type: dict[EntityType, list[EntityNode]] = {}
        for entity in entities:
            if entity.entity_type not in entities_by_type:
                entities_by_type[entity.entity_type] = []
            entities_by_type[entity.entity_type].append(entity)

        result.entities_processed = len(entities)

        # Process each type group
        for entity_type, type_entities in entities_by_type.items():
            if len(type_entities) < 2:
                continue

            # Find all potential alias pairs
            seen_pairs: set[tuple[str, str]] = set()
            high_confidence_pairs: list[AliasCandidate] = []
            medium_confidence_pairs: list[AliasCandidate] = []

            for entity in type_entities:
                candidates = self.find_potential_aliases(entity, type_entities)

                for candidate in candidates:
                    # Create normalized pair key (smaller ID first)
                    pair_key = tuple(sorted([candidate.entity_id, candidate.candidate_entity_id]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    result.alias_pairs_found += 1

                    if candidate.is_auto_linked:
                        high_confidence_pairs.append(candidate)
                    elif candidate.similarity_score >= MEDIUM_SIMILARITY_THRESHOLD:
                        medium_confidence_pairs.append(candidate)
                    else:
                        result.skipped_low_confidence += 1

            # Process high-confidence pairs (auto-link)
            for candidate in high_confidence_pairs:
                edge = EntityEdgeCreate(
                    source_entity_id=candidate.entity_id,
                    target_entity_id=candidate.candidate_entity_id,
                    relationship_type=RelationshipType.ALIAS_OF,
                    matter_id=matter_id,
                    confidence=candidate.similarity_score,
                    metadata={
                        "auto_linked": True,
                        "name_similarity": candidate.name_similarity,
                        "component_similarity": candidate.component_similarity,
                    },
                )
                edges_to_create.append(edge)
                result.high_confidence_links += 1

            # Process medium-confidence pairs with context analysis
            if medium_confidence_pairs and entity_contexts:
                # Batch context analysis
                batch_pairs = []
                for i, candidate in enumerate(medium_confidence_pairs):
                    batch_pairs.append({
                        "pair_id": f"pair_{i}",
                        "name1": candidate.entity_name,
                        "context1": entity_contexts.get(candidate.entity_id, ""),
                        "name2": candidate.candidate_name,
                        "context2": entity_contexts.get(candidate.candidate_entity_id, ""),
                    })

                # Process in batches
                for batch_start in range(0, len(batch_pairs), CONTEXT_ANALYSIS_BATCH_SIZE):
                    batch = batch_pairs[batch_start:batch_start + CONTEXT_ANALYSIS_BATCH_SIZE]
                    confidence_map = await self.analyze_batch_context(batch)

                    for j, pair_data in enumerate(batch):
                        pair_id = pair_data["pair_id"]
                        candidate_idx = batch_start + j
                        candidate = medium_confidence_pairs[candidate_idx]

                        context_confidence = confidence_map.get(pair_id, 0.5)
                        candidate.context_confidence = context_confidence

                        # Link if combined score is high enough
                        if candidate.final_score >= CONTEXT_CONFIDENCE_THRESHOLD:
                            edge = EntityEdgeCreate(
                                source_entity_id=candidate.entity_id,
                                target_entity_id=candidate.candidate_entity_id,
                                relationship_type=RelationshipType.ALIAS_OF,
                                matter_id=matter_id,
                                confidence=candidate.final_score,
                                metadata={
                                    "auto_linked": False,
                                    "context_analyzed": True,
                                    "name_similarity": candidate.name_similarity,
                                    "context_confidence": context_confidence,
                                },
                            )
                            edges_to_create.append(edge)
                            result.medium_confidence_links += 1
                        else:
                            result.skipped_low_confidence += 1

        # Apply transitive closure: if A=B and B=C, then A=C
        edges_to_create = self._apply_transitive_closure(edges_to_create, matter_id)

        result.aliases_created = len(edges_to_create)

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(
            "alias_resolution_complete",
            matter_id=matter_id,
            entities_processed=result.entities_processed,
            pairs_found=result.alias_pairs_found,
            aliases_created=result.aliases_created,
            high_confidence=result.high_confidence_links,
            medium_confidence=result.medium_confidence_links,
            skipped=result.skipped_low_confidence,
            processing_time_ms=processing_time,
        )

        return result, edges_to_create

    # =========================================================================
    # Private Methods - Gemini Integration
    # =========================================================================

    def _get_gemini_model(self):
        """Get Gemini model for context analysis.

        Returns:
            Gemini GenerativeModel or None if not configured.
        """
        if not hasattr(self, "_gemini_model"):
            settings = get_settings()
            api_key = settings.gemini_api_key

            if not api_key:
                logger.warning("alias_gemini_not_configured")
                self._gemini_model = None
                return None

            try:
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                self._gemini_model = genai.GenerativeModel(
                    settings.gemini_model,
                    system_instruction=ALIAS_CONTEXT_SYSTEM_PROMPT,
                )
                logger.debug("alias_gemini_initialized", model=settings.gemini_model)
            except Exception as e:
                logger.error("alias_gemini_init_failed", error=str(e))
                self._gemini_model = None

        return self._gemini_model

    def _parse_context_response(self, response_text: str) -> dict:
        """Parse Gemini context analysis response.

        Args:
            response_text: Raw response from Gemini.

        Returns:
            Parsed dict with same_entity, confidence, reasoning, indicators.
        """
        try:
            # Clean up response
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

            return json.loads(json_text)

        except json.JSONDecodeError as e:
            logger.warning(
                "alias_context_parse_error",
                error=str(e),
                response_preview=response_text[:100] if response_text else "",
            )
            return {"same_entity": False, "confidence": 0.5}

    def _parse_batch_response(self, response_text: str) -> list[dict]:
        """Parse Gemini batch analysis response.

        Args:
            response_text: Raw response from Gemini.

        Returns:
            List of result dicts with pair_id, same_entity, confidence.
        """
        try:
            json_text = response_text.strip()

            # Remove markdown code blocks
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

            if isinstance(parsed, list):
                return parsed
            return []

        except json.JSONDecodeError as e:
            logger.warning(
                "alias_batch_parse_error",
                error=str(e),
            )
            return []

    # =========================================================================
    # Private Methods - Transitive Closure
    # =========================================================================

    def _apply_transitive_closure(
        self,
        edges: list[EntityEdgeCreate],
        matter_id: str,
    ) -> list[EntityEdgeCreate]:
        """Apply transitive closure to alias edges.

        If A=B and B=C, creates edge A=C.
        Uses Union-Find algorithm for efficient closure computation.

        Args:
            edges: List of ALIAS_OF edges to process.
            matter_id: Matter UUID.

        Returns:
            Extended list of edges including transitive connections.
        """
        if len(edges) < 2:
            return edges

        # Build adjacency sets
        entity_to_aliases: dict[str, set[str]] = {}
        for edge in edges:
            source = edge.source_entity_id
            target = edge.target_entity_id

            if source not in entity_to_aliases:
                entity_to_aliases[source] = set()
            if target not in entity_to_aliases:
                entity_to_aliases[target] = set()

            entity_to_aliases[source].add(target)
            entity_to_aliases[target].add(source)

        # Union-Find with path compression
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])  # Path compression
            return parent[x]

        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Apply unions for existing edges
        for edge in edges:
            union(edge.source_entity_id, edge.target_entity_id)

        # Group entities by their root
        groups: dict[str, list[str]] = {}
        for entity_id in entity_to_aliases:
            root = find(entity_id)
            if root not in groups:
                groups[root] = []
            groups[root].append(entity_id)

        # Track existing edges for deduplication
        existing_pairs: set[tuple[str, str]] = set()
        for edge in edges:
            pair = tuple(sorted([edge.source_entity_id, edge.target_entity_id]))
            existing_pairs.add(pair)

        # Generate transitive edges for groups with >2 entities
        transitive_edges: list[EntityEdgeCreate] = []
        for group_entities in groups.values():
            if len(group_entities) <= 2:
                continue

            # Create edges between all pairs in the group
            for i, entity_a in enumerate(group_entities):
                for entity_b in group_entities[i + 1:]:
                    pair = tuple(sorted([entity_a, entity_b]))
                    if pair not in existing_pairs:
                        transitive_edge = EntityEdgeCreate(
                            source_entity_id=pair[0],
                            target_entity_id=pair[1],
                            relationship_type=RelationshipType.ALIAS_OF,
                            matter_id=matter_id,
                            confidence=0.75,  # Lower confidence for transitive
                            metadata={
                                "auto_linked": True,
                                "transitive": True,
                            },
                        )
                        transitive_edges.append(transitive_edge)
                        existing_pairs.add(pair)

        if transitive_edges:
            logger.info(
                "transitive_aliases_added",
                original_count=len(edges),
                transitive_count=len(transitive_edges),
            )

        return edges + transitive_edges

    # =========================================================================
    # Private Methods - Similarity Calculations
    # =========================================================================

    def _calculate_component_match(
        self,
        comp1: NameComponents,
        comp2: NameComponents,
    ) -> float:
        """Calculate component-wise name match score.

        Compares first, middle, and last name components.

        Args:
            comp1: First name components.
            comp2: Second name components.

        Returns:
            Component match score between 0.0 and 1.0.
        """
        scores = []

        # Last name match (most important)
        if comp1.last_name and comp2.last_name:
            last_score = self._jaro.normalized_similarity(
                comp1.last_name.lower(),
                comp2.last_name.lower(),
            )
            scores.append(last_score * 1.5)  # Weight last name higher
        elif comp1.last_name or comp2.last_name:
            scores.append(0.0)

        # First name match
        if comp1.first_name and comp2.first_name:
            # Handle initials
            f1 = comp1.first_name.rstrip(".")
            f2 = comp2.first_name.rstrip(".")

            if self._is_initial(comp1.first_name) or self._is_initial(comp2.first_name):
                # Initial match (e.g., "N" matches "Nirav")
                if f1[0].lower() == f2[0].lower():
                    scores.append(0.8)
                else:
                    scores.append(0.0)
            else:
                first_score = self._jaro.normalized_similarity(
                    f1.lower(), f2.lower()
                )
                scores.append(first_score)
        elif comp1.first_name or comp2.first_name:
            scores.append(0.2)  # One has first name, other doesn't

        # Middle name match
        if comp1.middle_name and comp2.middle_name:
            m1 = comp1.middle_name.rstrip(".")
            m2 = comp2.middle_name.rstrip(".")

            if self._is_initial(comp1.middle_name) or self._is_initial(comp2.middle_name):
                # Initial match
                if m1[0].lower() == m2[0].lower():
                    scores.append(0.7)
                else:
                    scores.append(0.0)
            else:
                middle_score = self._jaro.normalized_similarity(
                    m1.lower(), m2.lower()
                )
                scores.append(middle_score)

        if not scores:
            return 0.0

        return min(1.0, sum(scores) / len(scores))

    def _calculate_initial_match(
        self,
        comp1: NameComponents,
        comp2: NameComponents,
    ) -> float:
        """Calculate initial expansion match score.

        Handles cases like "N.D." matching "Nirav D." or "Nirav Dineshbhai".

        Args:
            comp1: First name components.
            comp2: Second name components.

        Returns:
            Initial match score between 0.0 and 1.0.
        """
        # Check if one has initials and the other has full names
        comp1_has_initials = self._has_initials(comp1)
        comp2_has_initials = self._has_initials(comp2)

        # Both have initials or neither has - compare directly
        if comp1_has_initials == comp2_has_initials:
            if comp1.initials.lower() == comp2.initials.lower():
                return 1.0
            # Neither has initials style names - this metric not applicable
            if not comp1_has_initials:
                return 0.0
            # Both have initials but they don't match
            return 0.0

        # One has initials, other has full names
        initials_comp = comp1 if comp1_has_initials else comp2
        full_comp = comp2 if comp1_has_initials else comp1

        matches = 0
        total = 0

        # Compare first name/initial
        if initials_comp.first_name and full_comp.first_name:
            total += 1
            init_first = initials_comp.first_name.rstrip(".")[0].lower()
            if full_comp.first_name[0].lower() == init_first:
                matches += 1

        # Compare middle name/initial
        if initials_comp.middle_name and full_comp.middle_name:
            total += 1
            init_middle = initials_comp.middle_name.rstrip(".")[0].lower()
            if full_comp.middle_name[0].lower() == init_middle:
                matches += 1

        # Compare last names (should match exactly or closely)
        if initials_comp.last_name and full_comp.last_name:
            total += 1
            last_score = self._jaro.normalized_similarity(
                initials_comp.last_name.lower(),
                full_comp.last_name.lower(),
            )
            if last_score > 0.9:
                matches += 1

        return matches / total if total > 0 else 0.0

    def _calculate_normalized_match(
        self,
        comp1: NameComponents,
        comp2: NameComponents,
    ) -> float:
        """Calculate match score after title normalization.

        Strips titles and compares remaining name.
        "Mr. Jobalia" should match "Nirav Jobalia" on last name.

        Args:
            comp1: First name components.
            comp2: Second name components.

        Returns:
            Normalized match score between 0.0 and 1.0.
        """
        # Compare names without titles
        name1 = comp1.name_without_title.lower()
        name2 = comp2.name_without_title.lower()

        if not name1 or not name2:
            return 0.0

        # Direct comparison of title-stripped names
        return self._jaro.normalized_similarity(name1, name2)

    def _is_initial(self, name_part: str) -> bool:
        """Check if a name part is a single initial (e.g., "N.", "N")."""
        if not name_part:
            return False

        # Remove periods and check if it's exactly 1 character
        stripped = name_part.replace(".", "")
        return len(stripped) == 1 and stripped.isalpha()

    def _is_combined_initials(self, name_part: str) -> bool:
        """Check if a name part is combined initials (e.g., "N.D.", "A.B.C.")."""
        if not name_part:
            return False

        # Must contain at least one period
        if "." not in name_part:
            return False

        # Split by period and check each part is a single letter
        parts = [p for p in name_part.split(".") if p]
        return len(parts) >= 2 and all(len(p) == 1 and p.isalpha() for p in parts)

    def _has_initials(self, comp: NameComponents) -> bool:
        """Check if name components contain initials."""
        if comp.first_name and self._is_initial(comp.first_name):
            return True
        if comp.middle_name and self._is_initial(comp.middle_name):
            return True
        return False


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_entity_resolver() -> EntityResolver:
    """Get singleton entity resolver instance.

    Returns:
        EntityResolver instance.
    """
    return EntityResolver()
