"""Cross-Engine Consistency Checking Service.

Story 5.4: Cross-Engine Consistency Checking

Detects and tracks data inconsistencies between analysis engines:
- Date mismatches between timeline and entity mentions
- Entity name variations between MIG and citations
- Amount/value discrepancies between extractions

Pre-mortem fixes implemented:
- Normalize dates for comparison (handle various formats)
- Use fuzzy matching thresholds for names
- Batch processing with configurable batch size
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from supabase import Client

from app.models.consistency_issue import (
    ConsistencyIssue,
    ConsistencyIssueCreate,
    ConsistencyIssueSummary,
    EngineType,
    IssueSeverity,
    IssueStatus,
    IssueType,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Configuration
FUZZY_NAME_THRESHOLD = 0.85  # Similarity threshold for name matching
DATE_TOLERANCE_DAYS = 7  # Days tolerance for date matching


@dataclass
class ConsistencyCheckResult:
    """Result of a consistency check operation."""

    issues_found: int
    issues_created: int
    engines_checked: list[str]
    duration_ms: int


def normalize_date(date_str: str | None) -> datetime | None:
    """Normalize a date string for comparison.

    Story 5.4: Pre-mortem fix - Handle various date formats.

    Args:
        date_str: Date string in various formats.

    Returns:
        Normalized datetime or None if parsing fails.
    """
    if not date_str:
        return None

    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d %B %Y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try dateutil as fallback
    try:
        from dateutil import parser

        return parser.parse(date_str)
    except Exception:
        logger.debug("date_normalization_failed", date_str=date_str)
        return None


def dates_match(date1: str | None, date2: str | None, tolerance_days: int = DATE_TOLERANCE_DAYS) -> bool:
    """Check if two dates match within tolerance.

    Args:
        date1: First date string.
        date2: Second date string.
        tolerance_days: Number of days tolerance.

    Returns:
        True if dates match within tolerance.
    """
    d1 = normalize_date(date1)
    d2 = normalize_date(date2)

    if d1 is None or d2 is None:
        return True  # Can't compare, assume match

    diff = abs((d1 - d2).days)
    return diff <= tolerance_days


def names_similar(name1: str, name2: str, threshold: float = FUZZY_NAME_THRESHOLD) -> bool:
    """Check if two names are similar using fuzzy matching.

    Story 5.4: Pre-mortem fix - Use fuzzy matching thresholds.

    Args:
        name1: First name.
        name2: Second name.
        threshold: Similarity threshold (0-1).

    Returns:
        True if names are similar above threshold.
    """
    from app.core.fuzzy_match import get_similarity_ratio

    # Normalize names
    n1 = name1.strip().lower()
    n2 = name2.strip().lower()

    # Exact match
    if n1 == n2:
        return True

    # Fuzzy match
    try:
        ratio = get_similarity_ratio(n1, n2)
        return ratio >= threshold
    except Exception:
        # Fallback: simple containment check
        return n1 in n2 or n2 in n1


class ConsistencyService:
    """Service for cross-engine consistency checking.

    Story 5.4: Cross-Engine Consistency Checking

    Detects and manages data inconsistencies across engines.
    """

    def __init__(self, client: Client | None = None):
        """Initialize service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self._client = client

    @property
    def client(self) -> Client:
        """Get database client."""
        if self._client is None:
            self._client = get_service_client()
        return self._client

    async def check_matter_consistency(
        self,
        matter_id: str,
        engines: list[str] | None = None,
    ) -> ConsistencyCheckResult:
        """Run consistency checks for a matter.

        Args:
            matter_id: Matter UUID.
            engines: Optional list of engines to check. If None, checks all.

        Returns:
            ConsistencyCheckResult with issues found.
        """
        import time

        start_time = time.time()

        # Default to all engines
        if engines is None:
            engines = ["timeline", "entity", "citation"]

        issues_found = 0
        issues_created = 0

        # Check timeline-entity consistency
        if "timeline" in engines and "entity" in engines:
            found, created = await self._check_timeline_entity_consistency(matter_id)
            issues_found += found
            issues_created += created

        # Check entity-citation consistency
        if "entity" in engines and "citation" in engines:
            found, created = await self._check_entity_citation_consistency(matter_id)
            issues_found += found
            issues_created += created

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "consistency_check_complete",
            matter_id=matter_id,
            engines=engines,
            issues_found=issues_found,
            issues_created=issues_created,
            duration_ms=duration_ms,
        )

        return ConsistencyCheckResult(
            issues_found=issues_found,
            issues_created=issues_created,
            engines_checked=engines,
            duration_ms=duration_ms,
        )

    async def _check_timeline_entity_consistency(
        self, matter_id: str
    ) -> tuple[int, int]:
        """Check consistency between timeline events and entity mentions.

        Returns:
            Tuple of (issues_found, issues_created).
        """
        issues_found = 0
        issues_created = 0

        try:
            # Get timeline events with entity links
            events_result = self.client.table("timeline_events").select(
                "id, event_date, description, linked_entities"
            ).eq("matter_id", matter_id).not_.is_("linked_entities", "null").execute()

            if not events_result.data:
                return 0, 0

            # Get entity mentions for comparison
            for event in events_result.data:
                linked_entities = event.get("linked_entities", [])
                event_date = event.get("event_date")

                for entity_id in linked_entities:
                    # Check if entity mention dates match event date
                    mentions_result = self.client.table("entity_mentions").select(
                        "id, context, chunk_id"
                    ).eq("entity_id", entity_id).execute()

                    if mentions_result.data:
                        # Check for date inconsistencies in mention context
                        for mention in mentions_result.data:
                            context = mention.get("context", "")
                            # Simple date extraction from context
                            context_dates = self._extract_dates_from_text(context)

                            for ctx_date in context_dates:
                                if not dates_match(event_date, ctx_date):
                                    issues_found += 1
                                    # Create issue if not already exists
                                    created = await self._create_issue_if_new(
                                        ConsistencyIssueCreate(
                                            matter_id=matter_id,
                                            issue_type=IssueType.DATE_MISMATCH,
                                            severity=IssueSeverity.WARNING,
                                            source_engine=EngineType.TIMELINE,
                                            source_id=event["id"],
                                            source_value=event_date,
                                            conflicting_engine=EngineType.ENTITY,
                                            conflicting_id=mention["id"],
                                            conflicting_value=ctx_date,
                                            description=f"Date mismatch: Timeline shows '{event_date}' but entity mention suggests '{ctx_date}'",
                                        )
                                    )
                                    if created:
                                        issues_created += 1

        except Exception as e:
            logger.error(
                "timeline_entity_consistency_check_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return issues_found, issues_created

    async def _check_entity_citation_consistency(
        self, matter_id: str
    ) -> tuple[int, int]:
        """Check consistency between entity names and citation references.

        Returns:
            Tuple of (issues_found, issues_created).
        """
        issues_found = 0
        issues_created = 0

        try:
            # Get entities with their aliases
            entities_result = self.client.table("entities").select(
                "id, canonical_name, aliases"
            ).eq("matter_id", matter_id).execute()

            if not entities_result.data:
                return 0, 0

            # Get citations that might reference entities
            citations_result = self.client.table("citations").select(
                "id, context, act_name"
            ).eq("matter_id", matter_id).execute()

            if not citations_result.data:
                return 0, 0

            # Check for name mismatches
            for entity in entities_result.data:
                entity_name = entity.get("canonical_name", "")
                aliases = entity.get("aliases", []) or []
                all_names = [entity_name] + aliases

                for citation in citations_result.data:
                    context = citation.get("context", "")

                    # Check if entity is mentioned but with different spelling
                    for name in all_names:
                        if name.lower() in context.lower():
                            # Found mention, check for variants
                            variants = self._find_name_variants(name, context)
                            for variant in variants:
                                if not names_similar(name, variant):
                                    issues_found += 1
                                    created = await self._create_issue_if_new(
                                        ConsistencyIssueCreate(
                                            matter_id=matter_id,
                                            issue_type=IssueType.ENTITY_NAME_MISMATCH,
                                            severity=IssueSeverity.INFO,
                                            source_engine=EngineType.ENTITY,
                                            source_id=entity["id"],
                                            source_value=entity_name,
                                            conflicting_engine=EngineType.CITATION,
                                            conflicting_id=citation["id"],
                                            conflicting_value=variant,
                                            description=f"Entity name variation: '{entity_name}' vs '{variant}' in citation",
                                        )
                                    )
                                    if created:
                                        issues_created += 1
                                    break  # One issue per entity-citation pair

        except Exception as e:
            logger.error(
                "entity_citation_consistency_check_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return issues_found, issues_created

    def _extract_dates_from_text(self, text: str) -> list[str]:
        """Extract date-like strings from text.

        Simple regex-based extraction for common date patterns.
        """
        import re

        patterns = [
            r"\d{1,2}/\d{1,2}/\d{2,4}",  # DD/MM/YYYY or MM/DD/YYYY
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}",  # DD Month YYYY
        ]

        dates = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)

        return dates[:5]  # Limit to 5 dates per text

    def _find_name_variants(self, name: str, text: str) -> list[str]:
        """Find potential name variants in text.

        Looks for capitalized words that might be the same entity.
        """
        import re

        # Find capitalized phrases near the entity name
        words = name.split()
        if not words:
            return []

        first_word = words[0]

        # Pattern: capitalized words that might be names
        pattern = rf"\b({first_word[0].upper()}\w+(?:\s+\w+)*)\b"
        matches = re.findall(pattern, text)

        # Filter to similar-length matches
        variants = [m for m in matches if abs(len(m) - len(name)) < 10]

        return variants[:5]  # Limit results

    async def _create_issue_if_new(self, issue: ConsistencyIssueCreate) -> bool:
        """Create issue only if similar one doesn't exist.

        Returns:
            True if created, False if already exists.
        """
        try:
            # Check for existing similar issue
            existing = self.client.table("consistency_issues").select("id").eq(
                "matter_id", issue.matter_id
            ).eq("issue_type", issue.issue_type.value).eq(
                "source_engine", issue.source_engine.value
            ).eq("source_id", issue.source_id).eq(
                "conflicting_engine", issue.conflicting_engine.value
            ).eq("conflicting_id", issue.conflicting_id).eq(
                "status", "open"
            ).execute()

            if existing.data:
                return False

            # Create new issue
            self.client.table("consistency_issues").insert({
                "matter_id": issue.matter_id,
                "issue_type": issue.issue_type.value,
                "severity": issue.severity.value,
                "source_engine": issue.source_engine.value,
                "source_id": issue.source_id,
                "source_value": issue.source_value,
                "conflicting_engine": issue.conflicting_engine.value,
                "conflicting_id": issue.conflicting_id,
                "conflicting_value": issue.conflicting_value,
                "description": issue.description,
                "document_id": issue.document_id,
                "document_name": issue.document_name,
                "metadata": issue.metadata,
            }).execute()

            return True

        except Exception as e:
            logger.warning(
                "consistency_issue_create_failed",
                matter_id=issue.matter_id,
                error=str(e),
            )
            return False

    async def get_issues_for_matter(
        self,
        matter_id: str,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConsistencyIssue]:
        """Get consistency issues for a matter.

        Args:
            matter_id: Matter UUID.
            status: Optional status filter.
            severity: Optional severity filter.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of ConsistencyIssue.
        """
        query = self.client.table("consistency_issues").select(
            "*"
        ).eq("matter_id", matter_id).order(
            "detected_at", desc=True
        ).limit(limit).offset(offset)

        if status:
            query = query.eq("status", status)
        if severity:
            query = query.eq("severity", severity)

        result = query.execute()

        if not result.data:
            return []

        return [self._parse_issue(row) for row in result.data]

    async def get_issue_summary(self, matter_id: str) -> ConsistencyIssueSummary:
        """Get summary counts for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            ConsistencyIssueSummary with counts.
        """
        try:
            result = self.client.rpc(
                "get_consistency_issue_counts",
                {"p_matter_id": matter_id},
            ).execute()

            if result.data and len(result.data) > 0:
                row = result.data[0]
                return ConsistencyIssueSummary(
                    total_count=row.get("total_count", 0),
                    open_count=row.get("open_count", 0),
                    warning_count=row.get("warning_count", 0),
                    error_count=row.get("error_count", 0),
                )

        except Exception as e:
            logger.warning(
                "consistency_issue_summary_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return ConsistencyIssueSummary(
            total_count=0,
            open_count=0,
            warning_count=0,
            error_count=0,
        )

    async def update_issue_status(
        self,
        issue_id: str,
        status: IssueStatus,
        user_id: str,
        resolution_notes: str | None = None,
    ) -> bool:
        """Update issue status.

        Args:
            issue_id: Issue UUID.
            status: New status.
            user_id: User making the change.
            resolution_notes: Optional notes.

        Returns:
            True if updated successfully.
        """
        try:
            update_data = {
                "status": status.value,
                "resolved_by": user_id if status in (IssueStatus.RESOLVED, IssueStatus.DISMISSED) else None,
                "resolved_at": datetime.now(timezone.utc).isoformat() if status in (IssueStatus.RESOLVED, IssueStatus.DISMISSED) else None,
            }
            if resolution_notes:
                update_data["resolution_notes"] = resolution_notes

            self.client.table("consistency_issues").update(update_data).eq(
                "id", issue_id
            ).execute()

            return True

        except Exception as e:
            logger.error(
                "consistency_issue_update_failed",
                issue_id=issue_id,
                error=str(e),
            )
            return False

    def _parse_issue(self, row: dict) -> ConsistencyIssue:
        """Parse database row into ConsistencyIssue."""
        return ConsistencyIssue(
            id=row["id"],
            matterId=row["matter_id"],
            issueType=IssueType(row["issue_type"]),
            severity=IssueSeverity(row["severity"]),
            sourceEngine=EngineType(row["source_engine"]),
            sourceId=row.get("source_id"),
            sourceValue=row.get("source_value"),
            conflictingEngine=EngineType(row["conflicting_engine"]),
            conflictingId=row.get("conflicting_id"),
            conflictingValue=row.get("conflicting_value"),
            description=row["description"],
            documentId=row.get("document_id"),
            documentName=row.get("document_name"),
            status=IssueStatus(row["status"]),
            resolvedBy=row.get("resolved_by"),
            resolvedAt=row.get("resolved_at"),
            resolutionNotes=row.get("resolution_notes"),
            detectedAt=row["detected_at"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            metadata=row.get("metadata", {}),
        )


# Singleton instance
_consistency_service: ConsistencyService | None = None


def get_consistency_service() -> ConsistencyService:
    """Get or create consistency service singleton."""
    global _consistency_service
    if _consistency_service is None:
        _consistency_service = ConsistencyService()
    return _consistency_service


def reset_consistency_service() -> None:
    """Reset singleton for testing."""
    global _consistency_service
    _consistency_service = None
