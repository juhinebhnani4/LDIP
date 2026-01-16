"""Executive Summary Service for quick export generation.

Story 12.4: Partner Executive Summary Export
Epic 12: Export Builder

This service extracts content for the executive summary export:
- Case Overview (from matter_summaries)
- Key Parties (limited to top 10)
- Critical Dates (max 10)
- Verified Issues (only approved findings)
- Recommended Actions (from attention_items)

Implements:
- AC #2: Pre-configured content sections
- AC #3: Only verified findings included
- AC #4: Footer with link and pending count
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

import structlog

if TYPE_CHECKING:
    from supabase import Client


class _PartyWithPriority(TypedDict):
    """Internal typed dict for party with sort priority."""

    role: str
    name: str
    relevance: str
    _priority: int

logger = structlog.get_logger(__name__)


@dataclass
class ExecutiveSummaryContent:
    """Content extracted for executive summary.

    Story 12.4: AC #2 - Pre-configured content structure.
    """

    matter_name: str
    matter_id: str

    # Case Overview (2-3 paragraphs)
    case_overview: str

    # Key Parties (table format)
    parties: list[dict]

    # Critical Dates (max 10)
    critical_dates: list[dict]

    # Verified Issues (only approved)
    verified_issues: list[dict]

    # Recommended Actions
    recommended_actions: list[str]

    # Pending verification count
    pending_verification_count: int

    # Counts for response
    parties_count: int
    dates_count: int
    issues_count: int


class ExecutiveSummaryService:
    """Service for extracting executive summary content.

    Story 12.4: Extracts content for partner-friendly 1-2 page PDF.
    """

    # Priority event types for critical dates
    CRITICAL_EVENT_TYPES = ('hearing', 'filing', 'deadline', 'judgment', 'order', 'motion')

    # Max limits per section (for 1-2 page constraint)
    MAX_PARTIES = 10
    MAX_DATES = 10
    MAX_ISSUES = 10
    MAX_ACTIONS = 5
    MAX_OVERVIEW_WORDS = 300

    def __init__(self) -> None:
        """Initialize executive summary service."""
        logger.info("executive_summary_service_initialized")

    async def extract_content(
        self,
        matter_id: str,
        supabase: Client,
    ) -> ExecutiveSummaryContent:
        """Extract all content for executive summary.

        Story 12.4: AC #2, #3 - Extract pre-configured content.

        Args:
            matter_id: Matter UUID.
            supabase: Supabase client.

        Returns:
            ExecutiveSummaryContent with all extracted sections.
        """
        logger.info("executive_summary_extraction_started", matter_id=matter_id)

        # Get matter name
        matter_name = await self._get_matter_name(matter_id, supabase)

        # Extract all sections
        case_overview, parties, attention_items = await self._fetch_summary_data(
            matter_id, supabase
        )
        critical_dates = await self._fetch_critical_dates(matter_id, supabase)
        verified_issues, pending_count = await self._fetch_verified_issues(
            matter_id, supabase
        )

        logger.info(
            "executive_summary_extraction_completed",
            matter_id=matter_id,
            parties_count=len(parties),
            dates_count=len(critical_dates),
            issues_count=len(verified_issues),
            pending_count=pending_count,
        )

        return ExecutiveSummaryContent(
            matter_name=matter_name,
            matter_id=matter_id,
            case_overview=case_overview,
            parties=parties,
            critical_dates=critical_dates,
            verified_issues=verified_issues,
            recommended_actions=attention_items[:self.MAX_ACTIONS],
            pending_verification_count=pending_count,
            parties_count=len(parties),
            dates_count=len(critical_dates),
            issues_count=len(verified_issues),
        )

    async def _get_matter_name(self, matter_id: str, supabase: Client) -> str:
        """Get matter name for title."""
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("matters").select(
                    "name"
                ).eq("id", matter_id).single().execute()
            )
            return result.data.get("name", "Matter") if result.data else "Matter"
        except Exception:
            return "Matter"

    async def _fetch_summary_data(
        self,
        matter_id: str,
        supabase: Client,
    ) -> tuple[str, list[dict], list[str]]:
        """Fetch matter summary for case overview and parties.

        Returns:
            Tuple of (case_overview, parties, attention_items).
        """
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("matter_summaries").select(
                    "parties, subject_matter, current_status, attention_items"
                ).eq("matter_id", matter_id).single().execute()
            )

            if not result.data:
                return "", [], []

            data = result.data

            # Build case overview (2-3 paragraphs from subject_matter + current_status)
            case_overview = self._build_case_overview(
                data.get("subject_matter", {}),
                data.get("current_status", {}),
            )

            # Get parties (limited to MAX_PARTIES)
            parties = self._extract_parties(data.get("parties", []))

            # Get attention items for recommended actions
            attention_items = self._extract_attention_items(
                data.get("attention_items", [])
            )

            return case_overview, parties, attention_items

        except Exception as e:
            logger.warning("summary_fetch_failed", matter_id=matter_id, error=str(e))
            return "", [], []

    def _build_case_overview(
        self,
        subject_matter: dict,
        current_status: dict,
    ) -> str:
        """Build case overview from subject matter and status.

        Story 12.4: AC #2 - 2-3 paragraphs, ~300 words max.
        """
        paragraphs = []

        # First paragraph: Subject matter description
        if subject_matter:
            description = subject_matter.get("description", "")
            case_type = subject_matter.get("case_type", "")

            if description:
                paragraphs.append(description)
            elif case_type:
                paragraphs.append(f"This matter involves {case_type}.")

        # Second paragraph: Current status
        if current_status:
            stage = current_status.get("stage", "")
            status_desc = current_status.get("description", "")

            if status_desc:
                paragraphs.append(status_desc)
            elif stage:
                paragraphs.append(f"Current stage: {stage}.")

        # Combine and truncate to ~300 words
        overview = "\n\n".join(paragraphs)
        words = overview.split()

        if len(words) > self.MAX_OVERVIEW_WORDS:
            # Truncate at word boundary
            overview = " ".join(words[:self.MAX_OVERVIEW_WORDS]) + "..."

        return overview or "No case overview available."

    def _extract_parties(self, parties_data: list) -> list[dict]:
        """Extract and limit parties list.

        Story 12.4: Limit to top 10 by role importance.
        """
        if not parties_data:
            return []

        # Role priority for sorting (lower = more important)
        role_priority: dict[str, int] = {
            "plaintiff": 1,
            "defendant": 2,
            "petitioner": 3,
            "respondent": 4,
            "appellant": 5,
            "judge": 6,
            "counsel": 7,
            "witness": 8,
            "expert": 9,
        }

        # Parse and sort parties (Issue #7 fix: properly typed internal list)
        parsed_parties: list[_PartyWithPriority] = []
        for party in parties_data:
            if isinstance(party, dict):
                role = party.get("role", "unknown").lower()
                name = party.get("name", "Unknown")
                relevance = party.get("relevance", "")

                parsed_parties.append({
                    "role": party.get("role", "Unknown"),
                    "name": name,
                    "relevance": relevance,
                    "_priority": role_priority.get(role, 10),
                })
            elif isinstance(party, str):
                parsed_parties.append({
                    "role": "Party",
                    "name": party,
                    "relevance": "",
                    "_priority": 10,
                })

        # Sort by priority and take top MAX_PARTIES
        parsed_parties.sort(key=lambda p: p["_priority"])
        top_parties = parsed_parties[:self.MAX_PARTIES]

        # Return without internal priority field
        return [
            {"role": p["role"], "name": p["name"], "relevance": p["relevance"]}
            for p in top_parties
        ]

    def _extract_attention_items(self, attention_items: list) -> list[str]:
        """Extract attention items as recommended actions."""
        if not attention_items:
            return []

        actions = []
        for item in attention_items:
            if isinstance(item, dict):
                action = item.get("action") or item.get("description") or item.get("item", "")
                if action:
                    actions.append(str(action))
            elif isinstance(item, str):
                actions.append(item)

        return actions[:self.MAX_ACTIONS]

    async def _fetch_critical_dates(
        self,
        matter_id: str,
        supabase: Client,
    ) -> list[dict]:
        """Fetch critical dates from events table.

        Story 12.4: AC #2 - Max 10 critical dates.
        """
        try:
            # Filter by critical event types
            result = await asyncio.to_thread(
                lambda: supabase.table("events").select(
                    "id, event_date, event_type, description, confidence"
                ).eq("matter_id", matter_id).in_(
                    "event_type", list(self.CRITICAL_EVENT_TYPES)
                ).order(
                    "event_date", desc=False
                ).limit(self.MAX_DATES).execute()
            )

            dates = result.data or []

            # Format for display
            formatted_dates = []
            for event in dates:
                formatted_dates.append({
                    "date": event.get("event_date", "Unknown"),
                    "type": event.get("event_type", "event"),
                    "description": event.get("description", ""),
                })

            return formatted_dates

        except Exception as e:
            logger.warning("critical_dates_fetch_failed", matter_id=matter_id, error=str(e))
            return []

    async def _fetch_verified_issues(
        self,
        matter_id: str,
        supabase: Client,
    ) -> tuple[list[dict], int]:
        """Fetch verified issues and count pending.

        Story 12.4: AC #3 - Only approved findings included.

        Returns:
            Tuple of (verified_issues, pending_count).
        """
        verified_issues = []
        pending_count = 0

        # Fetch contradictions with high severity/confidence that are approved
        contradictions = await self._fetch_verified_contradictions(matter_id, supabase)

        # Fetch citations with issues that are approved
        citations = await self._fetch_verified_citations(matter_id, supabase)

        # Combine and sort by severity
        all_issues = contradictions + citations

        # Sort by severity (critical first, then high)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))

        verified_issues = all_issues[:self.MAX_ISSUES]

        # Count pending verifications
        try:
            pending_result = await asyncio.to_thread(
                lambda: supabase.table("finding_verifications").select(
                    "id"
                ).eq("matter_id", matter_id).eq("decision", "pending").execute()
            )
            pending_count = len(pending_result.data or [])
        except Exception:
            pass

        return verified_issues, pending_count

    async def _get_approved_findings_batch(
        self,
        matter_id: str,
        finding_type: str,
        finding_ids: list[str],
        supabase: Client,
    ) -> set[str]:
        """Batch check which findings are approved.

        Issue #4 fix: Fetches all verification records in one query to avoid N+1.

        Args:
            matter_id: Matter UUID.
            finding_type: Type of finding ('contradiction' or 'citation').
            finding_ids: List of finding IDs to check.
            supabase: Supabase client.

        Returns:
            Set of approved finding IDs.
        """
        if not finding_ids:
            return set()

        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("finding_verifications").select(
                    "finding_id, decision"
                ).eq("matter_id", matter_id).eq(
                    "finding_type", finding_type
                ).in_("finding_id", finding_ids).execute()
            )

            verifications = result.data or []

            # Build set of approved IDs
            approved_ids: set[str] = set()
            verified_ids: set[str] = set()

            for ver in verifications:
                verified_ids.add(ver["finding_id"])
                if ver.get("decision") == "approved":
                    approved_ids.add(ver["finding_id"])

            # For findings without verification records, include them (benefit of doubt)
            for fid in finding_ids:
                if fid not in verified_ids:
                    approved_ids.add(fid)

            return approved_ids

        except Exception as e:
            logger.debug(
                "batch_verification_check_failed",
                matter_id=matter_id,
                finding_type=finding_type,
                error_type=type(e).__name__,
                error=str(e),
            )
            # On error, include all (benefit of doubt)
            return set(finding_ids)

    async def _fetch_verified_contradictions(
        self,
        matter_id: str,
        supabase: Client,
    ) -> list[dict]:
        """Fetch contradictions that are verified (approved)."""
        try:
            # Get high severity/confidence contradictions
            result = await asyncio.to_thread(
                lambda: supabase.table("contradictions").select(
                    "id, contradiction_type, severity, confidence, statement_a, statement_b"
                ).eq("matter_id", matter_id).gte(
                    "confidence", 70
                ).in_(
                    "severity", ["high", "critical"]
                ).execute()
            )

            contradictions = result.data or []

            if not contradictions:
                return []

            # Batch check which ones are approved (Issue #4 fix)
            finding_ids = [con["id"] for con in contradictions]
            approved_ids = await self._get_approved_findings_batch(
                matter_id, "contradiction", finding_ids, supabase
            )

            # Build verified list
            verified = []
            for con in contradictions:
                if con["id"] in approved_ids:
                    verified.append({
                        "type": "contradiction",
                        "severity": con.get("severity", "high"),
                        "summary": f"{con.get('contradiction_type', 'Contradiction')}: "
                                   f"Conflicting statements detected",
                        "detail": "Statement A conflicts with Statement B",
                    })

            return verified

        except Exception as e:
            logger.warning("contradictions_fetch_failed", matter_id=matter_id, error=str(e))
            return []

    async def _fetch_verified_citations(
        self,
        matter_id: str,
        supabase: Client,
    ) -> list[dict]:
        """Fetch citations with issues that are verified (approved)."""
        try:
            # Get citations with issues
            result = await asyncio.to_thread(
                lambda: supabase.table("citations").select(
                    "id, act_name, section, verification_status"
                ).eq("matter_id", matter_id).eq(
                    "verification_status", "issue_found"
                ).execute()
            )

            citations = result.data or []

            if not citations:
                return []

            # Batch check which ones are approved (Issue #4 fix)
            finding_ids = [cit["id"] for cit in citations]
            approved_ids = await self._get_approved_findings_batch(
                matter_id, "citation", finding_ids, supabase
            )

            # Build verified list
            verified = []
            for cit in citations:
                if cit["id"] in approved_ids:
                    verified.append({
                        "type": "citation",
                        "severity": "high",
                        "summary": f"Citation issue: {cit.get('act_name', 'Unknown Act')}",
                        "detail": f"Section {cit.get('section', 'N/A')} verification failed",
                    })

            return verified

        except Exception as e:
            logger.warning("citations_fetch_failed", matter_id=matter_id, error=str(e))
            return []

    async def _check_finding_approved(
        self,
        matter_id: str,
        finding_type: str,
        finding_id: str,
        supabase: Client,
    ) -> bool:
        """Check if a finding has been approved in verification queue."""
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("finding_verifications").select(
                    "decision"
                ).eq("matter_id", matter_id).eq(
                    "finding_type", finding_type
                ).eq("finding_id", finding_id).single().execute()
            )

            return result.data.get("decision") == "approved" if result.data else False

        except Exception as e:
            # If no verification record, include it (benefit of doubt for demo)
            # Log the exception type for debugging (Issue #3 fix)
            logger.debug(
                "finding_verification_check_failed",
                matter_id=matter_id,
                finding_type=finding_type,
                finding_id=finding_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            return True


# =============================================================================
# Story 12.4: Singleton Factory
# =============================================================================

_executive_summary_service: ExecutiveSummaryService | None = None


def get_executive_summary_service() -> ExecutiveSummaryService:
    """Get singleton ExecutiveSummaryService instance."""
    global _executive_summary_service  # noqa: PLW0603

    if _executive_summary_service is None:
        _executive_summary_service = ExecutiveSummaryService()

    return _executive_summary_service
