"""Statement Query Engine for retrieving entity-grouped statements.

Story 5-1: Implement Entity-Grouped Statement Querying

Retrieves all statements (chunks) mentioning an entity, including:
- Direct entity_id matches in chunks.entity_ids array
- Alias matches via EntityResolver (AC #2)
- Grouped by document source (AC #1)
- Extracted dates and amounts (AC #3)

CRITICAL: Does NOT use LLM - regex-based extraction per cost optimization rules.

NOTE: Statements use chunk-level bbox_ids (intentional). Unlike citations or entity
mentions where per-item filtering is needed, contradictions require showing the
full statement context. The extracted dates/amounts are derived values for
comparison, not separate sourced items requiring individual highlighting.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.models.contradiction import (
    DocumentStatements,
    EntityStatements,
    Statement,
    StatementValue,
    StatementValueType,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants - Indian Date/Amount Patterns
# =============================================================================

# Indian date formats (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY)
DATE_PATTERNS = [
    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    (
        r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b",
        lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}",
    ),
    # "dated 15th of January, 2024" - legal format
    (
        r"dated\s+(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(\w+)[,\s]+(\d{4})",
        "_parse_legal_date",
    ),
    # "15th January 2024" or "15 January, 2024"
    (
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)[,\s]+(\d{4})\b",
        "_parse_written_date",
    ),
    # YYYY-MM-DD (ISO format)
    (
        r"\b(\d{4})-(\d{2})-(\d{2})\b",
        lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
    ),
]

# Month name mapping for written dates
MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}

# Indian amount patterns
AMOUNT_PATTERNS = [
    # Rs. X,XX,XXX or Rs X,XX,XXX (Indian comma notation)
    (r"Rs\.?\s*([\d,]+(?:\.\d{2})?)", "_parse_rupees"),
    # X crores/crore
    (r"\b([\d,]+(?:\.\d+)?)\s*crores?\b", "_parse_crores"),
    # X lakhs/lakh
    (r"\b([\d,]+(?:\.\d+)?)\s*lakhs?\b", "_parse_lakhs"),
    # X rupees
    (r"\b([\d,]+(?:\.\d{2})?)\s*rupees?\b", "_parse_rupees_word"),
    # USD $ X,XXX
    (r"\$\s*([\d,]+(?:\.\d{2})?)", "_parse_usd"),
    # X% or X percent (no trailing \b after % as it's not a word char)
    (r"\b(\d+(?:\.\d+)?)\s*(%|percent\b)", "_parse_percentage"),
]


# =============================================================================
# Value Extractor - Regex-based extraction (NO LLM)
# =============================================================================


class ValueExtractor:
    """Extracts dates and amounts from statement text using regex patterns.

    CRITICAL: Uses regex-based extraction (NOT LLM) per cost optimization rules.
    This is a pattern matching task that can be verified downstream in Story 5-2.

    Supports Indian formats:
    - Dates: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, "dated X of Y, 20XX"
    - Amounts: Rs. X, X lakhs, X crores, X rupees, 1,00,000 (Indian comma)

    Example:
        >>> extractor = ValueExtractor()
        >>> dates = extractor.extract_dates("dated 15th of January, 2024")
        >>> dates[0].normalized
        '2024-01-15'
    """

    def extract_dates(self, text: str) -> list[StatementValue]:
        """Extract dates from text using regex patterns.

        Args:
            text: Statement text to extract dates from.

        Returns:
            List of StatementValue objects with type=DATE.
        """
        if not text:
            return []

        dates: list[StatementValue] = []
        seen: set[str] = set()  # Avoid duplicates

        for pattern, normalizer in DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_text = match.group(0)

                # Skip if we've seen this exact text
                if raw_text in seen:
                    continue

                try:
                    if callable(normalizer):
                        normalized = normalizer(match)
                    elif normalizer == "_parse_legal_date":
                        normalized = self._parse_legal_date(match)
                    elif normalizer == "_parse_written_date":
                        normalized = self._parse_written_date(match)
                    else:
                        continue

                    if normalized and self._is_valid_date(normalized):
                        dates.append(
                            StatementValue(
                                type=StatementValueType.DATE,
                                raw_text=raw_text,
                                normalized=normalized,
                                confidence=0.9,
                            )
                        )
                        seen.add(raw_text)

                except (ValueError, KeyError) as e:
                    logger.debug(
                        "date_extraction_failed",
                        raw_text=raw_text,
                        error=str(e),
                    )
                    continue

        return dates

    def extract_amounts(self, text: str) -> list[StatementValue]:
        """Extract amounts from text using regex patterns.

        Supports Indian currency notation (lakhs, crores, Rs.)
        and standard formats (USD, percentages).

        Args:
            text: Statement text to extract amounts from.

        Returns:
            List of StatementValue objects with type=AMOUNT or QUANTITY.
        """
        if not text:
            return []

        amounts: list[StatementValue] = []
        seen: set[str] = set()

        for pattern, method_name in AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_text = match.group(0)

                if raw_text in seen:
                    continue

                try:
                    method = getattr(self, method_name)
                    normalized = method(match)

                    if normalized:
                        value_type = (
                            StatementValueType.QUANTITY
                            if method_name == "_parse_percentage"
                            else StatementValueType.AMOUNT
                        )

                        amounts.append(
                            StatementValue(
                                type=value_type,
                                raw_text=raw_text,
                                normalized=normalized,
                                confidence=0.9,
                            )
                        )
                        seen.add(raw_text)

                except (ValueError, AttributeError) as e:
                    logger.debug(
                        "amount_extraction_failed",
                        raw_text=raw_text,
                        error=str(e),
                    )
                    continue

        return amounts

    def extract_all_values(self, text: str) -> tuple[list[StatementValue], list[StatementValue]]:
        """Extract both dates and amounts from text.

        Args:
            text: Statement text to extract from.

        Returns:
            Tuple of (dates, amounts) lists.
        """
        return self.extract_dates(text), self.extract_amounts(text)

    # =========================================================================
    # Private Methods - Date Parsing
    # =========================================================================

    def _parse_legal_date(self, match: re.Match) -> str | None:
        """Parse "dated 15th of January, 2024" format."""
        day = match.group(1).zfill(2)
        month_str = match.group(2).lower()
        year = match.group(3)

        month = MONTH_MAP.get(month_str)
        if not month:
            return None

        return f"{year}-{month}-{day}"

    def _parse_written_date(self, match: re.Match) -> str | None:
        """Parse "15th January 2024" format."""
        day = match.group(1).zfill(2)
        month_str = match.group(2).lower()
        year = match.group(3)

        month = MONTH_MAP.get(month_str)
        if not month:
            return None

        return f"{year}-{month}-{day}"

    def _is_valid_date(self, date_str: str) -> bool:
        """Validate that a date string is a valid date."""
        try:
            parts = date_str.split("-")
            if len(parts) != 3:
                return False

            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

            # Basic validation
            if year < 1900 or year > 2100:
                return False
            if month < 1 or month > 12:
                return False
            return not (day < 1 or day > 31)

        except (ValueError, IndexError):
            return False

    # =========================================================================
    # Private Methods - Amount Parsing
    # =========================================================================

    def _parse_rupees(self, match: re.Match) -> str:
        """Parse Rs. X,XX,XXX format (Indian notation)."""
        amount_str = match.group(1).replace(",", "")
        return amount_str

    def _parse_crores(self, match: re.Match) -> str:
        """Parse X crores (1 crore = 10,000,000)."""
        amount_str = match.group(1).replace(",", "")
        amount = float(amount_str) * 10_000_000
        return str(int(amount))

    def _parse_lakhs(self, match: re.Match) -> str:
        """Parse X lakhs (1 lakh = 100,000)."""
        amount_str = match.group(1).replace(",", "")
        amount = float(amount_str) * 100_000
        return str(int(amount))

    def _parse_rupees_word(self, match: re.Match) -> str:
        """Parse 'X rupees' format."""
        amount_str = match.group(1).replace(",", "")
        return amount_str

    def _parse_usd(self, match: re.Match) -> str:
        """Parse $X,XXX format."""
        amount_str = match.group(1).replace(",", "")
        return f"USD:{amount_str}"

    def _parse_percentage(self, match: re.Match) -> str:
        """Parse X% format."""
        return f"{match.group(1)}%"


# =============================================================================
# Statement Query Engine
# =============================================================================


@dataclass
class ChunkData:
    """Internal data class for chunk query results."""

    id: str
    document_id: str
    content: str
    page_number: int | None
    entity_ids: list[str]


class StatementQueryEngine:
    """Engine for querying entity-grouped statements from chunks.

    Retrieves all chunks mentioning an entity (by entity_id or aliases)
    and groups them by document source with extracted values.

    CRITICAL: Always validates matter_id for 4-layer isolation (Layer 4).

    Example:
        >>> engine = StatementQueryEngine(supabase_client)
        >>> result = await engine.get_statements_for_entity(
        ...     entity_id="entity-123",
        ...     matter_id="matter-456",
        ...     include_aliases=True,
        ... )
        >>> result.total_statements
        15
    """

    def __init__(self, supabase_client) -> None:
        """Initialize statement query engine.

        Args:
            supabase_client: Supabase client instance.
        """
        self._client = supabase_client
        self._value_extractor = ValueExtractor()

    async def get_statements_for_entity(
        self,
        entity_id: str,
        matter_id: str,
        document_ids: list[str] | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> EntityStatements:
        """Get statements for a single entity_id (no alias resolution).

        Args:
            entity_id: Entity UUID to query.
            matter_id: Matter UUID for isolation (CRITICAL).
            document_ids: Optional filter by document IDs.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            EntityStatements with grouped statements.
        """
        import asyncio

        # Query chunks where entity_id is in entity_ids array
        # CRITICAL: Always include matter_id filter
        def _query():
            query = (
                self._client.table("chunks")
                .select("id, document_id, content, page_number, bbox_ids, entity_ids")
                .eq("matter_id", matter_id)
                .contains("entity_ids", [entity_id])
            )

            if document_ids:
                query = query.in_("document_id", document_ids)

            # Order by document then page
            query = query.order("document_id").order("page_number")

            # Pagination
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        # Get entity name
        entity_name = await self._get_entity_name(entity_id, matter_id)

        # Convert to statements
        return await self._build_entity_statements(
            entity_id=entity_id,
            entity_name=entity_name,
            chunks=response.data or [],
            aliases_included=[],
        )

    async def get_statements_for_canonical_entity(
        self,
        entity_id: str,
        matter_id: str,
        include_aliases: bool = True,
        document_ids: list[str] | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> EntityStatements:
        """Get statements for an entity including all aliases (AC #2).

        Uses MIGGraphService to resolve aliases and queries chunks
        mentioning the canonical entity or any of its aliases.

        Args:
            entity_id: Canonical entity UUID.
            matter_id: Matter UUID for isolation (CRITICAL).
            include_aliases: If True, include alias entity matches.
            document_ids: Optional filter by document IDs.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            EntityStatements with statements from entity and all aliases.
        """
        import asyncio

        # Get all entity IDs to search (canonical + aliases)
        entity_ids_to_search = [entity_id]
        aliases_included: list[str] = []

        if include_aliases:
            alias_entities = await self._get_alias_entities(entity_id, matter_id)
            for alias_entity in alias_entities:
                entity_ids_to_search.append(alias_entity["id"])
                aliases_included.append(alias_entity["canonical_name"])

        # Query chunks containing any of the entity IDs
        # Using overlap operator for array containment
        def _query():
            query = (
                self._client.table("chunks")
                .select("id, document_id, content, page_number, bbox_ids, entity_ids")
                .eq("matter_id", matter_id)
                .overlaps("entity_ids", entity_ids_to_search)
            )

            if document_ids:
                query = query.in_("document_id", document_ids)

            query = query.order("document_id").order("page_number")

            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        entity_name = await self._get_entity_name(entity_id, matter_id)

        return await self._build_entity_statements(
            entity_id=entity_id,
            entity_name=entity_name,
            chunks=response.data or [],
            aliases_included=aliases_included,
        )

    async def count_statements_for_entity(
        self,
        entity_id: str,
        matter_id: str,
        include_aliases: bool = True,
    ) -> int:
        """Count total statements for an entity.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID for isolation.
            include_aliases: If True, include alias entity matches.

        Returns:
            Total count of statements.
        """
        import asyncio

        entity_ids_to_search = [entity_id]

        if include_aliases:
            alias_entities = await self._get_alias_entities(entity_id, matter_id)
            for alias_entity in alias_entities:
                entity_ids_to_search.append(alias_entity["id"])

        def _count():
            return (
                self._client.table("chunks")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .overlaps("entity_ids", entity_ids_to_search)
                .execute()
            )

        response = await asyncio.to_thread(_count)
        return response.count or 0

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_entity_name(self, entity_id: str, matter_id: str) -> str:
        """Get entity canonical name by ID."""
        import asyncio

        def _query():
            return (
                self._client.table("identity_nodes")
                .select("canonical_name")
                .eq("id", entity_id)
                .eq("matter_id", matter_id)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return response.data[0].get("canonical_name", "Unknown")
        return "Unknown"

    async def _get_alias_entities(
        self,
        entity_id: str,
        matter_id: str,
    ) -> list[dict]:
        """Get all alias entities for an entity via MIGGraphService.

        Uses the existing MIGGraphService.get_all_aliases() method.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID.

        Returns:
            List of alias entity dicts with id and canonical_name.
        """
        from app.services.mig.graph import get_mig_graph_service

        mig_service = get_mig_graph_service()
        aliases = await mig_service.get_all_aliases(entity_id, matter_id)

        return [
            {"id": alias.id, "canonical_name": alias.canonical_name}
            for alias in aliases
        ]

    async def _get_document_names(
        self,
        document_ids: list[str],
    ) -> dict[str, str]:
        """Get document names by IDs."""
        import asyncio

        if not document_ids:
            return {}

        def _query():
            return (
                self._client.table("documents")
                .select("id, filename")
                .in_("id", document_ids)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        return {
            doc["id"]: doc.get("filename", "Unknown")
            for doc in (response.data or [])
        }

    async def _build_entity_statements(
        self,
        entity_id: str,
        entity_name: str,
        chunks: list[dict],
        aliases_included: list[str],
    ) -> EntityStatements:
        """Build EntityStatements from chunk query results.

        Groups chunks by document and extracts values from each.

        Args:
            entity_id: Entity UUID.
            entity_name: Entity canonical name.
            chunks: Raw chunk data from database.
            aliases_included: List of alias names included in search.

        Returns:
            EntityStatements with grouped and enriched statements.
        """
        # Group chunks by document_id
        documents_map: dict[str, list[dict]] = {}
        document_ids: set[str] = set()

        for chunk in chunks:
            doc_id = chunk.get("document_id")
            if doc_id:
                document_ids.add(doc_id)
                if doc_id not in documents_map:
                    documents_map[doc_id] = []
                documents_map[doc_id].append(chunk)

        # Fetch document names from database
        doc_names = await self._get_document_names(list(document_ids))

        # Build DocumentStatements
        document_statements: list[DocumentStatements] = []

        for doc_id, doc_chunks in documents_map.items():
            statements: list[Statement] = []

            for chunk in doc_chunks:
                content = chunk.get("content", "")
                dates, amounts = self._value_extractor.extract_all_values(content)

                statements.append(
                    Statement(
                        entity_id=entity_id,
                        chunk_id=chunk.get("id", ""),
                        document_id=doc_id,
                        content=content,
                        dates=dates,
                        amounts=amounts,
                        page_number=chunk.get("page_number"),
                        bbox_ids=[str(b) for b in chunk.get("bbox_ids") or []],
                        confidence=1.0,
                    )
                )

            document_statements.append(
                DocumentStatements(
                    document_id=doc_id,
                    document_name=doc_names.get(doc_id),
                    statements=statements,
                    statement_count=len(statements),
                )
            )

        total_statements = sum(ds.statement_count for ds in document_statements)

        return EntityStatements(
            entity_id=entity_id,
            entity_name=entity_name,
            total_statements=total_statements,
            documents=document_statements,
            aliases_included=aliases_included,
        )


# =============================================================================
# Service Factories
# =============================================================================


@lru_cache(maxsize=1)
def get_value_extractor() -> ValueExtractor:
    """Get singleton value extractor instance.

    Returns:
        ValueExtractor instance.
    """
    return ValueExtractor()


def get_statement_query_engine() -> StatementQueryEngine:
    """Get statement query engine instance.

    Note: Not cached as it requires Supabase client which may vary.

    Returns:
        StatementQueryEngine instance.
    """
    from app.services.supabase.client import get_supabase_client

    client = get_supabase_client()
    return StatementQueryEngine(client)
