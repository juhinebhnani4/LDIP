"""Cross-Engine Link Resolution Service.

Gap 5-3: Cross-Engine Correlation Links

Provides correlation and link resolution across engines:
- Timeline events ↔ Entities
- Timeline events ↔ Contradictions
- Entities ↔ Timeline events
- Entities ↔ Contradictions
- Contradictions ↔ Timeline events

Enables seamless navigation between analysis engines.
"""

from dataclasses import dataclass

import structlog
from supabase import Client

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class CrossLinkedTimelineEvent:
    """Timeline event with minimal data for cross-engine linking."""

    event_id: str
    event_date: str
    event_type: str
    description: str
    document_id: str | None
    document_name: str | None
    source_page: int | None
    confidence: float


@dataclass
class CrossLinkedContradiction:
    """Contradiction with minimal data for cross-engine linking."""

    contradiction_id: str
    contradiction_type: str
    severity: str
    explanation: str
    statement_a_excerpt: str
    statement_b_excerpt: str
    document_a_id: str
    document_a_name: str
    document_b_id: str
    document_b_name: str
    confidence: float


@dataclass
class CrossLinkedEntity:
    """Entity with minimal data for cross-engine linking."""

    entity_id: str
    canonical_name: str
    entity_type: str
    aliases: list[str]


@dataclass
class EntityJourney:
    """Complete journey of an entity across timeline events."""

    entity_id: str
    entity_name: str
    entity_type: str
    events: list[CrossLinkedTimelineEvent]
    total_events: int
    date_range_start: str | None
    date_range_end: str | None


@dataclass
class EntityContradictionSummary:
    """Summary of contradictions involving an entity."""

    entity_id: str
    entity_name: str
    contradictions: list[CrossLinkedContradiction]
    total_contradictions: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int


@dataclass
class TimelineEventContext:
    """Context for a timeline event including related entities and contradictions."""

    event_id: str
    event_date: str
    event_type: str
    description: str
    document_id: str | None
    document_name: str | None
    entities: list[CrossLinkedEntity]
    related_contradictions: list[CrossLinkedContradiction]


@dataclass
class ContradictionContext:
    """Context for a contradiction including related timeline events."""

    contradiction_id: str
    entity_id: str
    entity_name: str
    contradiction_type: str
    severity: str
    explanation: str
    related_events: list[CrossLinkedTimelineEvent]


# =============================================================================
# Service Implementation
# =============================================================================


class CrossEngineService:
    """Service for cross-engine link resolution.

    Provides methods to get related data across different analysis engines,
    enabling seamless navigation and correlation.
    """

    def __init__(self, supabase: Client) -> None:
        """Initialize cross-engine service.

        Args:
            supabase: Supabase client.
        """
        self._supabase = supabase

    def get_entity_journey(
        self,
        matter_id: str,
        entity_id: str,
        page: int = 1,
        per_page: int = 50,
    ) -> EntityJourney:
        """Get all timeline events for a specific entity.

        Returns the complete chronological journey of an entity through
        the timeline, enabling "entity journey" view.

        Uses the events.entities_involved array column which stores entity IDs
        directly in the events table.
        """
        logger.info(
            "get_entity_journey",
            matter_id=matter_id,
            entity_id=entity_id,
        )

        # First, get entity details
        entity_result = (
            self._supabase.table("identity_nodes")
            .select("id, canonical_name, entity_type, aliases")
            .eq("id", entity_id)
            .eq("matter_id", matter_id)
            .single()
            .execute()
        )

        if not entity_result.data:
            return EntityJourney(
                entity_id=entity_id,
                entity_name="Unknown",
                entity_type="unknown",
                events=[],
                total_events=0,
                date_range_start=None,
                date_range_end=None,
            )

        entity_data = entity_result.data

        # Query events that contain this entity in entities_involved array
        # Using cs (contains) operator for array containment
        offset = (page - 1) * per_page
        events_result = (
            self._supabase.table("events")
            .select(
                """
                id,
                event_date,
                event_type,
                description,
                document_id,
                source_page,
                confidence,
                documents(filename)
                """,
                count="exact",
            )
            .eq("matter_id", matter_id)
            .contains("entities_involved", [entity_id])
            .order("event_date", desc=False)
            .range(offset, offset + per_page - 1)
            .execute()
        )

        total_events = events_result.count if events_result.count else 0

        events: list[CrossLinkedTimelineEvent] = []
        date_range_start: str | None = None
        date_range_end: str | None = None

        for event_data in events_result.data or []:
            doc_data = event_data.get("documents")
            event_date_str = str(event_data["event_date"]) if event_data.get("event_date") else ""
            event = CrossLinkedTimelineEvent(
                event_id=event_data["id"],
                event_date=event_date_str,
                event_type=event_data["event_type"],
                description=event_data["description"],
                document_id=event_data.get("document_id"),
                document_name=doc_data.get("filename") if doc_data else None,
                source_page=event_data.get("source_page"),
                confidence=event_data.get("confidence", 1.0),
            )
            events.append(event)

            # Track date range
            if event.event_date:
                if not date_range_start or event.event_date < date_range_start:
                    date_range_start = event.event_date
                if not date_range_end or event.event_date > date_range_end:
                    date_range_end = event.event_date

        return EntityJourney(
            entity_id=entity_id,
            entity_name=entity_data.get("canonical_name", "Unknown"),
            entity_type=entity_data.get("entity_type", "unknown"),
            events=events,
            total_events=total_events,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
        )

    def get_entity_contradictions(
        self,
        matter_id: str,
        entity_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> EntityContradictionSummary:
        """Get all contradictions involving a specific entity.

        OPTIMIZED: Combined entity lookup with contradictions query and
        compute severity counts from a single query with count="exact".
        Reduced from 3 queries to 1.
        """
        logger.info(
            "get_entity_contradictions",
            matter_id=matter_id,
            entity_id=entity_id,
        )

        # Fetch contradictions with entity info (no nested chunk joins - those FKs don't exist)
        # We'll fetch chunk/document info separately if needed
        all_contradictions_result = (
            self._supabase.table("statement_comparisons")
            .select(
                """
                id,
                entity_id,
                contradiction_type,
                severity,
                explanation,
                confidence,
                statement_a_id,
                statement_b_id,
                identity_nodes!inner(
                    canonical_name
                )
                """,
                count="exact",
            )
            .eq("entity_id", entity_id)
            .eq("matter_id", matter_id)
            .eq("result", "contradiction")
            .order("severity", desc=False)
            .execute()
        )

        total_contradictions = all_contradictions_result.count if all_contradictions_result.count else 0

        if not all_contradictions_result.data:
            return EntityContradictionSummary(
                entity_id=entity_id,
                entity_name="Unknown",
                contradictions=[],
                total_contradictions=0,
                high_severity_count=0,
                medium_severity_count=0,
                low_severity_count=0,
            )

        # Get entity name from first result (using identity_nodes table)
        entity_name = all_contradictions_result.data[0].get("identity_nodes", {}).get("canonical_name", "Unknown")

        # Count severities from the fetched data (no extra query needed)
        high_count = 0
        medium_count = 0
        low_count = 0
        for item in all_contradictions_result.data:
            sev = item.get("severity", "low")
            if sev == "high":
                high_count += 1
            elif sev == "medium":
                medium_count += 1
            else:
                low_count += 1

        # Apply pagination in Python (data already fetched for count)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_data = all_contradictions_result.data[start_idx:end_idx]

        # Collect chunk IDs to fetch document info
        chunk_ids = set()
        for row in paginated_data:
            if row.get("statement_a_id"):
                chunk_ids.add(row["statement_a_id"])
            if row.get("statement_b_id"):
                chunk_ids.add(row["statement_b_id"])

        # Fetch chunk and document info in one query
        chunk_doc_map: dict[str, tuple[str, str, str]] = {}  # chunk_id -> (doc_id, doc_name, content)
        if chunk_ids:
            chunks_result = (
                self._supabase.table("chunks")
                .select("id, content, document_id, documents(filename)")
                .in_("id", list(chunk_ids))
                .execute()
            )
            for chunk in chunks_result.data or []:
                doc = chunk.get("documents") or {}
                chunk_doc_map[chunk["id"]] = (
                    chunk.get("document_id", ""),
                    doc.get("filename", "Unknown") if doc else "Unknown",
                    (chunk.get("content") or "")[:200],
                )

        contradictions: list[CrossLinkedContradiction] = []
        for row in paginated_data:
            stmt_a_id = row.get("statement_a_id", "")
            stmt_b_id = row.get("statement_b_id", "")

            # Get document info from our map
            doc_a_id, doc_a_name, excerpt_a = chunk_doc_map.get(stmt_a_id, ("", "Unknown", ""))
            doc_b_id, doc_b_name, excerpt_b = chunk_doc_map.get(stmt_b_id, ("", "Unknown", ""))

            contradictions.append(
                CrossLinkedContradiction(
                    contradiction_id=row["id"],
                    contradiction_type=row.get("contradiction_type", "semantic_contradiction"),
                    severity=row.get("severity", "low"),
                    explanation=row.get("explanation", ""),
                    statement_a_excerpt=excerpt_a,
                    statement_b_excerpt=excerpt_b,
                    document_a_id=doc_a_id,
                    document_a_name=doc_a_name,
                    document_b_id=doc_b_id,
                    document_b_name=doc_b_name,
                    confidence=row.get("confidence", 0.5),
                )
            )

        return EntityContradictionSummary(
            entity_id=entity_id,
            entity_name=entity_name,
            contradictions=contradictions,
            total_contradictions=total_contradictions,
            high_severity_count=high_count,
            medium_severity_count=medium_count,
            low_severity_count=low_count,
        )

    def get_timeline_event_context(
        self,
        matter_id: str,
        event_id: str,
    ) -> TimelineEventContext | None:
        """Get full context for a timeline event."""
        logger.info(
            "get_timeline_event_context",
            matter_id=matter_id,
            event_id=event_id,
        )

        # Get the timeline event (table is called 'events')
        event_result = (
            self._supabase.table("events")
            .select(
                """
                id,
                event_date,
                event_type,
                description,
                document_id,
                entities_involved,
                documents(filename)
                """
            )
            .eq("id", event_id)
            .eq("matter_id", matter_id)
            .single()
            .execute()
        )

        if not event_result.data:
            return None

        event_data = event_result.data
        doc_data = event_data.get("documents")

        # Get linked entities from entities_involved array
        entity_ids = event_data.get("entities_involved") or []
        entities: list[CrossLinkedEntity] = []

        if entity_ids:
            entities_result = (
                self._supabase.table("identity_nodes")
                .select("id, canonical_name, entity_type, aliases")
                .in_("id", entity_ids)
                .execute()
            )

            if entities_result.data:
                for ent_data in entities_result.data:
                    entities.append(
                        CrossLinkedEntity(
                            entity_id=ent_data["id"],
                            canonical_name=ent_data["canonical_name"],
                            entity_type=ent_data["entity_type"],
                            aliases=ent_data.get("aliases", []) or [],
                        )
                    )

        # Get contradictions for these entities
        related_contradictions: list[CrossLinkedContradiction] = []
        if entity_ids:
            contradictions_result = (
                self._supabase.table("statement_comparisons")
                .select(
                    """
                    id,
                    contradiction_type,
                    severity,
                    explanation,
                    confidence,
                    statement_a_content,
                    statement_b_content,
                    document_a_id,
                    document_b_id,
                    doc_a:documents!statement_comparisons_document_a_id_fkey(filename),
                    doc_b:documents!statement_comparisons_document_b_id_fkey(filename)
                    """
                )
                .in_("entity_id", entity_ids)
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
                .limit(10)
                .execute()
            )

            if contradictions_result.data:
                for row in contradictions_result.data:
                    doc_a = row.get("doc_a")
                    doc_b = row.get("doc_b")
                    related_contradictions.append(
                        CrossLinkedContradiction(
                            contradiction_id=row["id"],
                            contradiction_type=row.get("contradiction_type", "semantic_contradiction"),
                            severity=row.get("severity", "low"),
                            explanation=row.get("explanation", ""),
                            statement_a_excerpt=row.get("statement_a_content", "")[:200],
                            statement_b_excerpt=row.get("statement_b_content", "")[:200],
                            document_a_id=row.get("document_a_id", ""),
                            document_a_name=doc_a.get("filename", "Unknown") if doc_a else "Unknown",
                            document_b_id=row.get("document_b_id", ""),
                            document_b_name=doc_b.get("filename", "Unknown") if doc_b else "Unknown",
                            confidence=row.get("confidence", 0.5),
                        )
                    )

        return TimelineEventContext(
            event_id=event_data["id"],
            event_date=event_data["event_date"],
            event_type=event_data["event_type"],
            description=event_data["description"],
            document_id=event_data.get("document_id"),
            document_name=doc_data.get("filename") if doc_data else None,
            entities=entities,
            related_contradictions=related_contradictions,
        )

    def get_contradiction_context(
        self,
        matter_id: str,
        contradiction_id: str,
    ) -> ContradictionContext | None:
        """Get full context for a contradiction."""
        logger.info(
            "get_contradiction_context",
            matter_id=matter_id,
            contradiction_id=contradiction_id,
        )

        # Get the contradiction (uses identity_nodes table)
        contradiction_result = (
            self._supabase.table("statement_comparisons")
            .select(
                """
                id,
                entity_id,
                contradiction_type,
                severity,
                explanation,
                identity_nodes!inner(
                    canonical_name
                )
                """
            )
            .eq("id", contradiction_id)
            .eq("matter_id", matter_id)
            .single()
            .execute()
        )

        if not contradiction_result.data:
            return None

        contradiction_data = contradiction_result.data
        entity_data = contradiction_data.get("identity_nodes", {})
        entity_id = contradiction_data.get("entity_id")

        # Get timeline events for this entity using entities_involved array
        related_events: list[CrossLinkedTimelineEvent] = []
        if entity_id:
            events_result = (
                self._supabase.table("events")
                .select(
                    """
                    id,
                    event_date,
                    event_type,
                    description,
                    document_id,
                    source_page,
                    confidence,
                    documents(filename)
                    """
                )
                .eq("matter_id", matter_id)
                .contains("entities_involved", [entity_id])
                .order("event_date", desc=False)
                .limit(20)
                .execute()
            )

            if events_result.data:
                for event_data_item in events_result.data:
                    doc_data = event_data_item.get("documents")
                    event_date_str = str(event_data_item["event_date"]) if event_data_item.get("event_date") else ""
                    related_events.append(
                        CrossLinkedTimelineEvent(
                            event_id=event_data_item["id"],
                            event_date=event_date_str,
                            event_type=event_data_item["event_type"],
                            description=event_data_item["description"],
                            document_id=event_data_item.get("document_id"),
                            document_name=doc_data.get("filename") if doc_data else None,
                            source_page=event_data_item.get("source_page"),
                            confidence=event_data_item.get("confidence", 1.0),
                        )
                    )

        return ContradictionContext(
            contradiction_id=contradiction_data["id"],
            entity_id=entity_id or "",
            entity_name=entity_data.get("canonical_name", "Unknown"),
            contradiction_type=contradiction_data.get("contradiction_type", "semantic_contradiction"),
            severity=contradiction_data.get("severity", "low"),
            explanation=contradiction_data.get("explanation", ""),
            related_events=related_events,
        )


# =============================================================================
# Service Factory
# =============================================================================


_cross_engine_service: CrossEngineService | None = None


def get_cross_engine_service() -> CrossEngineService:
    """Get singleton cross-engine service instance.

    Returns:
        CrossEngineService singleton.
    """
    global _cross_engine_service
    if _cross_engine_service is None:
        client = get_service_client()
        if client is None:
            raise RuntimeError("Supabase client not configured")
        _cross_engine_service = CrossEngineService(client)
    return _cross_engine_service
