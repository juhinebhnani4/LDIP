"""Summary Service for Matter Executive Summary generation.

Story 14.1: Summary API Endpoint (Task 2)

Generates AI-powered executive summaries for matters by:
1. Querying database tables for stats and attention items
2. Using GPT-4 for subject matter and key issues generation
3. Caching results in Redis with 1-hour TTL
4. Applying language policing to all generated content

CRITICAL: Uses GPT-4 per LLM routing rules (ADR-002).
Summary generation = user-facing, accuracy critical.
"""

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.core.cost_tracking import (
    BatchCostAggregator,
    CostTracker,
    LLMProvider,
    persist_cost,
)
from app.engines.summary.prompts import (
    CURRENT_STATUS_SYSTEM_PROMPT,
    KEY_ISSUES_SYSTEM_PROMPT,
    SUBJECT_MATTER_SYSTEM_PROMPT,
    format_current_status_prompt,
    format_key_issues_prompt,
    format_subject_matter_prompt,
)
from app.models.summary import (
    AttentionItem,
    AttentionItemType,
    Citation,
    CurrentStatus,
    KeyIssue,
    KeyIssueVerificationStatus,
    MatterStats,
    MatterSummary,
    PartyInfo,
    PartyRole,
    SubjectMatter,
    SubjectMatterSource,
    SummarySectionTypeEnum,
)
from app.services.memory.redis_client import get_redis_client
from app.services.memory.redis_keys import SUMMARY_CACHE_TTL, summary_cache_key
from app.services.safety.language_policing import get_language_policing_service
from app.services.summary_edit_service import (
    get_summary_edit_service,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)

# =============================================================================
# Story 14.1: Configuration Constants
# =============================================================================

# Maximum number of parties to return in summary (sorted by role importance)
MAX_PARTIES = 4

# Maximum number of key issues to extract
MAX_KEY_ISSUES = 5

# Maximum chunks to use for GPT-4 generation context
MAX_CHUNKS_FOR_SUMMARY = 10


# =============================================================================
# Story 14.1: Exceptions
# =============================================================================


class SummaryServiceError(Exception):
    """Base exception for summary service operations."""

    def __init__(
        self,
        message: str,
        code: str = "SUMMARY_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class SummaryGenerationError(SummaryServiceError):
    """Raised when summary generation fails."""

    def __init__(self, message: str):
        super().__init__(message, code="GENERATION_FAILED", status_code=500)


class OpenAIConfigurationError(SummaryServiceError):
    """Raised when OpenAI is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="OPENAI_NOT_CONFIGURED", status_code=503)


# =============================================================================
# Story 14.1: Summary Service (Task 2.1 - 2.9)
# =============================================================================


class SummaryService:
    """Service for generating matter executive summaries.

    Story 14.1: Implements AC #3-7 for summary generation.

    Workflow:
    1. Check Redis cache for existing summary
    2. If cache miss, generate new summary:
       a. Query database for stats, attention items, parties
       b. Retrieve top chunks via RAG
       c. Call GPT-4 for subject matter, key issues, current status
       d. Apply language policing to all outputs
    3. Cache result in Redis with 1-hour TTL
    4. Return summary

    Example:
        >>> service = SummaryService()
        >>> summary = await service.get_summary("matter-123")
        >>> summary.stats.total_pages
        156
    """

    def __init__(self) -> None:
        """Initialize summary service."""
        self._openai_client = None
        self._supabase_client = None
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_comparison_model  # GPT-4o for summaries

    @property
    def openai_client(self):
        """Get or create OpenAI client.

        Returns:
            AsyncOpenAI client instance.

        Raises:
            OpenAIConfigurationError: If API key is not configured.
        """
        if self._openai_client is None:
            if not self.api_key:
                raise OpenAIConfigurationError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY."
                )

            try:
                import httpx
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(
                    api_key=self.api_key,
                    timeout=httpx.Timeout(120.0, connect=10.0),
                )
                logger.info(
                    "summary_service_openai_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("summary_service_openai_init_failed", error=str(e))
                raise OpenAIConfigurationError(
                    f"Failed to initialize OpenAI client: {e}"
                ) from e

        return self._openai_client

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            SummaryServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise SummaryServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    # =========================================================================
    # Main API (Task 2.1)
    # =========================================================================

    async def get_summary(
        self,
        matter_id: str,
        force_refresh: bool = False,
    ) -> MatterSummary:
        """Get or generate matter summary.

        Story 14.1: Main entry point for summary retrieval.

        Args:
            matter_id: Matter UUID.
            force_refresh: If True, bypass cache and regenerate.

        Returns:
            MatterSummary with all components.

        Raises:
            SummaryServiceError: If generation fails.
        """
        # Check cache first (unless force_refresh)
        if not force_refresh:
            cached = await self.get_cached_summary(matter_id)
            if cached:
                logger.info(
                    "summary_cache_hit",
                    matter_id=matter_id,
                )
                return cached

        logger.info(
            "summary_generating",
            matter_id=matter_id,
            force_refresh=force_refresh,
        )

        # Generate new summary in parallel
        (
            stats,
            attention_items,
            parties,
            top_chunks,
            recent_events,
        ) = await asyncio.gather(
            self.get_stats(matter_id),
            self.get_attention_items(matter_id),
            self.get_parties(matter_id),
            self._get_top_chunks(matter_id, limit=15),  # More chunks for comprehensive overview
            self._get_recent_events(matter_id),
        )

        # Generate GPT-4 content in parallel
        subject_matter, key_issues, current_status = await asyncio.gather(
            self.generate_subject_matter(matter_id, top_chunks),
            self.get_key_issues(matter_id, top_chunks),
            self.get_current_status(matter_id, top_chunks, recent_events),
        )

        # BUG-005 fix: Case Overview (GPT-4) is authoritative for party names.
        # Entity extraction (Gemini) often hallucinates names (e.g., "Prisoner",
        # "State of Maharashtra"). Use overview names as primary, enriched with
        # entity metadata (entity_id, citations, pages) when available.
        #
        # BUG-005b fix: Use fuzzy name matching so entity source_document
        # traceability is preserved even when names don't exactly match
        # (e.g., "Jyoti H. Mehta" vs "Smt. Jyoti Harshad Mehta").
        overview_parties = self._parse_parties_from_overview(
            subject_matter.description
        )
        if overview_parties:
            # Build all entities per role (not just first) for better matching
            entities_by_role: dict[PartyRole, list[PartyInfo]] = {}
            for p in parties:
                entities_by_role.setdefault(p.role, []).append(p)

            enriched = []
            used_entity_ids: set[str] = set()

            for op in overview_parties:
                entity_match = self._find_best_entity_match(
                    op, entities_by_role, parties, used_entity_ids
                )
                if entity_match:
                    used_entity_ids.add(entity_match.entity_id)
                    names_match = (
                        entity_match.entity_name.lower().strip()
                        == op.entity_name.lower().strip()
                    )
                    # When names don't match, fix page to 1 (cover page)
                    # and create a corrected citation so the link stays clickable.
                    corrected_page = entity_match.source_page if names_match else 1
                    corrected_citation = entity_match.citation
                    if not names_match and entity_match.citation:
                        corrected_citation = entity_match.citation.model_copy(
                            update={"page": 1, "excerpt": None}
                        )
                    enriched.append(PartyInfo(
                        entity_id=entity_match.entity_id,
                        entity_name=op.entity_name,  # Overview name wins
                        role=op.role,
                        source_document=entity_match.source_document,
                        source_page=corrected_page,
                        is_verified=entity_match.is_verified,
                        citation=corrected_citation,
                    ))
                else:
                    enriched.append(op)
            parties = enriched
        # else: no overview available, keep entity-extracted parties as-is

        # Build summary
        summary = MatterSummary(
            matter_id=matter_id,
            attention_items=attention_items,
            parties=parties,
            subject_matter=subject_matter,
            current_status=current_status,
            key_issues=key_issues,
            stats=stats,
            generated_at=datetime.now(UTC).isoformat(),
        )

        # Only cache if summary generation actually succeeded
        if self.is_summary_valid(summary):
            await self._cache_summary(matter_id, summary)
        else:
            logger.warning(
                "summary_not_cached_due_to_failures",
                matter_id=matter_id,
                subject_matter_failed=summary.subject_matter.description == "Unable to generate summary at this time.",
                key_issues_empty=len(summary.key_issues) == 0,
            )

        logger.info(
            "summary_generated",
            matter_id=matter_id,
            attention_items=len(attention_items),
            parties=len(parties),
            key_issues=len(key_issues),
        )

        return summary

    # =========================================================================
    # Attention Items (Task 2.2) - AC #5
    # =========================================================================

    async def get_attention_items(self, matter_id: str) -> list[AttentionItem]:
        """Get attention items requiring user action.

        Story 14.1: AC #5 - Dynamically computed from database.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of AttentionItem objects.
        """
        items = []

        # Query contradiction count
        contradiction_count = await self._count_contradictions(matter_id)
        if contradiction_count > 0:
            items.append(
                AttentionItem(
                    type=AttentionItemType.CONTRADICTION,
                    count=contradiction_count,
                    label="contradictions detected",
                    target_tab="verification",
                )
            )

        # Query citation issues
        citation_issues = await self._count_citation_issues(matter_id)
        if citation_issues > 0:
            items.append(
                AttentionItem(
                    type=AttentionItemType.CITATION_ISSUE,
                    count=citation_issues,
                    label="citations need verification",
                    target_tab="citations",
                )
            )

        # Query timeline anomalies
        timeline_gaps = await self._count_timeline_anomalies(matter_id)
        if timeline_gaps > 0:
            items.append(
                AttentionItem(
                    type=AttentionItemType.TIMELINE_GAP,
                    count=timeline_gaps,
                    label="timeline gaps identified",
                    target_tab="timeline",
                )
            )

        return items

    async def _count_contradictions(self, matter_id: str) -> int:
        """Count contradictions from statement_comparisons table."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("statement_comparisons")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("result", "contradiction")
                .execute()
            )
            return result.count or 0
        except Exception as e:
            logger.warning("count_contradictions_failed", error=str(e))
            return 0

    async def _count_citation_issues(self, matter_id: str) -> int:
        """Count unverified citations using the same filtered logic as the Citations tab.

        BUG-LT3-K fix: Previously this was a raw count that included citations from
        Act documents and invalid act names. Now uses get_citation_counts_by_act which
        filters those out, keeping the attention item count consistent with what the
        Citations tab actually shows.
        """
        try:
            from app.engines.citation.storage import get_citation_storage_service

            storage = get_citation_storage_service()
            counts = await storage.get_citation_counts_by_act(matter_id)
            return sum(c.get("pending_count", 0) for c in counts)
        except Exception as e:
            logger.warning("count_citation_issues_failed", error=str(e))
            return 0

    async def _count_timeline_anomalies(self, matter_id: str) -> int:
        """Count anomalies from anomalies table."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("anomalies")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )
            return result.count or 0
        except Exception as e:
            logger.warning("count_timeline_anomalies_failed", error=str(e))
            return 0

    # =========================================================================
    # Parties (Task 2.3) - AC #6
    # =========================================================================

    async def get_parties(self, matter_id: str) -> list[PartyInfo]:
        """Get parties from MIG (Matter Identity Graph), excluding soft-deleted docs.

        Story 14.1: AC #6 - Parties extracted from entity_mentions.
        Story 14.6: AC #9 - Include citation data for CitationLink.

        Improved approach:
        1. Query identity_nodes for entities with party roles in metadata
        2. Get first mention for each party entity to find source document
        3. Filter to only include mentions from active (non-deleted) documents

        Args:
            matter_id: Matter UUID.

        Returns:
            List of PartyInfo objects.
        """
        try:
            # First get active document IDs
            docs_result = await asyncio.to_thread(
                lambda: self.supabase.table("documents")
                .select("id, filename")
                .eq("matter_id", matter_id)
                .is_("deleted_at", "null")
                .execute()
            )
            active_docs = {d["id"]: d["filename"] for d in docs_result.data or []}
            active_doc_ids = list(active_docs.keys())

            if not active_doc_ids:
                return []

            # Step 1: Get all PERSON entities for this matter (parties are people)
            # We fetch more entities and filter for party roles in Python
            # since Supabase doesn't support JSON field contains queries efficiently
            entities_result = await asyncio.to_thread(
                lambda: self.supabase.table("identity_nodes")
                .select("id, canonical_name, entity_type, metadata")
                .eq("matter_id", matter_id)
                .in_("entity_type", ["PERSON", "ORG"])
                .order("mention_count", desc=True)
                .limit(100)
                .execute()
            )

            # Step 2: Filter for entities with party roles
            party_entities = []
            for entity in entities_result.data or []:
                metadata = entity.get("metadata", {}) or {}
                roles = metadata.get("roles", [])

                # Skip generic placeholder names like "Respondent No.1"
                name = entity.get("canonical_name", "")
                if self._is_placeholder_party_name(name):
                    continue

                # Determine party role
                role = None
                for r in roles:
                    r_lower = r.lower() if isinstance(r, str) else ""
                    if "petitioner" in r_lower or "appellant" in r_lower or "complainant" in r_lower:
                        role = PartyRole.PETITIONER
                        break
                    elif "respondent" in r_lower or "defendant" in r_lower or "accused" in r_lower:
                        role = PartyRole.RESPONDENT
                        break
                    elif "applicant" in r_lower:
                        # Applicant could be petitioner in some contexts
                        role = PartyRole.PETITIONER
                        break

                if role:
                    party_entities.append({
                        "entity_id": entity["id"],
                        "canonical_name": name,
                        "role": role,
                    })

            if not party_entities:
                return []

            # Step 3: Get first mention for each party entity to find source document
            party_entity_ids = [p["entity_id"] for p in party_entities]
            mentions_result = await asyncio.to_thread(
                lambda: self.supabase.table("entity_mentions")
                .select("entity_id, document_id, page_number")
                .in_("entity_id", party_entity_ids[:20])  # Limit to top 20 parties
                .in_("document_id", active_doc_ids)
                .execute()
            )

            # Build map of entity_id -> first mention
            entity_mentions: dict[str, dict] = {}
            for mention in mentions_result.data or []:
                entity_id = mention["entity_id"]
                if entity_id not in entity_mentions:
                    entity_mentions[entity_id] = mention

            # Step 4: Build PartyInfo objects
            parties = []
            for party in party_entities:
                entity_id = party["entity_id"]
                mention = entity_mentions.get(entity_id)

                if mention:
                    document_id = mention["document_id"]
                    source_document = active_docs.get(document_id, "Unknown")
                    source_page = mention.get("page_number")
                else:
                    document_id = ""
                    source_document = "Unknown"
                    source_page = None

                # Check if this party entity has been verified
                is_verified = await self._check_party_verified(matter_id, entity_id)

                # Story 14.6: Build citation for party source
                citation = None
                if document_id:
                    citation = Citation(
                        document_id=document_id,
                        document_name=source_document,
                        page=source_page,
                        excerpt=None,
                    )

                parties.append(
                    PartyInfo(
                        entity_id=entity_id,
                        entity_name=party["canonical_name"],
                        role=party["role"],
                        source_document=source_document,
                        source_page=source_page,
                        is_verified=is_verified,
                        citation=citation,
                    )
                )

            # Sort: petitioners first, then respondents, then others
            role_order = {
                PartyRole.PETITIONER: 0,
                PartyRole.RESPONDENT: 1,
                PartyRole.OTHER: 2,
            }
            parties.sort(key=lambda p: role_order.get(p.role, 2))

            return parties[:MAX_PARTIES]

        except Exception as e:
            logger.warning("get_parties_failed", error=str(e), matter_id=matter_id)
            return []

    # ------------------------------------------------------------------
    # Party name matching helpers (BUG-005b)
    # ------------------------------------------------------------------

    _NAME_STOPWORDS = frozenset({
        "smt", "shri", "shrimati", "mr", "mrs", "ms", "dr", "sri",
        "kumari", "late", "hon", "honble", "justice",
        "the", "of", "and", "vs", "v", "through", "by", "in", "at",
        "no", "nos", "etc", "ors", "anr", "another", "others",
    })

    @staticmethod
    def _name_tokens(name: str) -> set[str]:
        """Extract meaningful tokens from a name, stripping honorifics and filler."""
        cleaned = re.sub(r"[.,;:!?()[\]{}<>\"'/\\]+", " ", name.lower())
        tokens = {t for t in cleaned.split() if len(t) > 1}
        return tokens - SummaryService._NAME_STOPWORDS

    @staticmethod
    def _name_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
        """Token-overlap similarity. Divides by the smaller set so partial
        names ("Jyoti Mehta" vs "Smt. Jyoti Harshad Mehta") still score 1.0."""
        if not tokens_a or not tokens_b:
            return 0.0
        overlap = tokens_a & tokens_b
        return len(overlap) / min(len(tokens_a), len(tokens_b))

    def _find_best_entity_match(
        self,
        overview_party: PartyInfo,
        entities_by_role: dict,
        all_entities: list[PartyInfo],
        used_ids: set[str],
    ) -> PartyInfo | None:
        """Find the best MIG entity for an overview party.

        Multi-level strategy:
        1. Exact name within same role
        2. Fuzzy name (>=0.5 token overlap) within same role
        3. Fuzzy name (>=0.6 token overlap) across all entities
        """
        target = overview_party.entity_name.lower().strip()
        target_tokens = self._name_tokens(overview_party.entity_name)

        same_role = entities_by_role.get(overview_party.role, [])

        # Level 1: exact name, same role
        for entity in same_role:
            if entity.entity_id not in used_ids and entity.entity_name.lower().strip() == target:
                return entity

        # Level 2: fuzzy name, same role (threshold 0.5)
        best, best_score = None, 0.0
        for entity in same_role:
            if entity.entity_id in used_ids:
                continue
            score = self._name_similarity(target_tokens, self._name_tokens(entity.entity_name))
            if score > best_score:
                best_score, best = score, entity
        if best and best_score >= 0.5:
            return best

        # Level 3: fuzzy name, any role (threshold 0.6 — stricter for cross-role)
        best, best_score = None, 0.0
        for entity in all_entities:
            if entity.entity_id in used_ids:
                continue
            score = self._name_similarity(target_tokens, self._name_tokens(entity.entity_name))
            if score > best_score:
                best_score, best = score, entity
        if best and best_score >= 0.6:
            return best

        return None

    def _is_placeholder_party_name(self, name: str) -> bool:
        """Check if a name is a generic placeholder like 'Respondent No.1'.

        These are extracted from documents but are not actual party names.
        """
        if not name:
            return True
        name_lower = name.lower().strip()

        # Exact matches for generic terms
        exact_placeholders = [
            "respondent",
            "petitioner",
            "appellant",
            "defendant",
            "applicant",
            "complainant",
            "accused",
            "custodian",
            "the custodian",
            "the respondent",
            "the petitioner",
            "the appellant",
            "the defendant",
        ]
        if name_lower in exact_placeholders:
            return True

        # Patterns for numbered placeholders like "Respondent No.1", "Respondent 2"
        numbered_pattern = re.compile(
            r"^(respondent|petitioner|appellant|defendant|applicant|complainant)\s*(no\.?|nos\.?|number)?\s*\d*$",
            re.IGNORECASE,
        )
        if numbered_pattern.match(name_lower):
            return True

        # Startswith patterns
        placeholders = [
            "respondent no",
            "petitioner no",
            "appellant no",
            "defendant no",
            "applicant no",
            "respondent nos",
            "petitioner nos",
            "appellant nos",
        ]
        for placeholder in placeholders:
            if name_lower.startswith(placeholder):
                return True

        return False

    def _parse_parties_from_overview(self, description: str) -> list[PartyInfo]:
        """Parse party names from the GPT-4 case overview markdown.

        BUG-005 fix: Entity extraction sometimes hallucinates party names
        (e.g., "State of Maharashtra" instead of "State of Uttar Pradesh").
        The GPT-4 case overview reads the full document and is always correct.
        Use its Parties section as ground truth.

        Args:
            description: The case overview markdown text.

        Returns:
            List of PartyInfo objects parsed from the overview.
        """
        parties = []
        if not description:
            return parties

        # Match "Petitioner/Applicant/Appellant: Name(s)" patterns
        petitioner_pattern = re.compile(
            r"\*?\*?(?:Petitioner|Applicant|Appellant)(?:/\w+)?(?:\(s\))?\s*:\*?\*?\s*(.+)",
            re.IGNORECASE,
        )
        respondent_pattern = re.compile(
            r"\*?\*?(?:Respondent|Defendant)(?:\(s\))?\s*:\*?\*?\s*(.+)",
            re.IGNORECASE,
        )

        for line in description.split("\n"):
            line = line.strip().lstrip("•-* ")

            pet_match = petitioner_pattern.search(line)
            if pet_match:
                name = pet_match.group(1).strip().rstrip("*")
                if name and not self._is_placeholder_party_name(name):
                    parties.append(
                        PartyInfo(
                            entity_id=str(uuid.uuid4()),
                            entity_name=name,
                            role=PartyRole.PETITIONER,
                            source_document="Case Overview",
                            source_page=1,
                            is_verified=False,
                            citation=None,
                        )
                    )

            resp_match = respondent_pattern.search(line)
            if resp_match:
                name = resp_match.group(1).strip().rstrip("*")
                # Remove trailing parenthetical descriptions
                name = re.sub(r"\s*\(.*\)\s*$", "", name).strip()
                if name and not self._is_placeholder_party_name(name):
                    parties.append(
                        PartyInfo(
                            entity_id=str(uuid.uuid4()),
                            entity_name=name,
                            role=PartyRole.RESPONDENT,
                            source_document="Case Overview",
                            source_page=1,
                            is_verified=False,
                            citation=None,
                        )
                    )

        return parties

    async def _check_party_verified(self, matter_id: str, entity_id: str) -> bool:
        """Check if a party entity has been verified.

        Story 14.4: AC #7 - Now uses summary_verifications table.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID.

        Returns:
            True if entity has verified status in summary_verifications.
        """
        try:
            # Story 14.4: Check summary_verifications table for party verification
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_verifications")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("section_type", SummarySectionTypeEnum.PARTIES.value)
                .eq("section_id", entity_id)
                .eq("decision", "verified")
                .execute()
            )
            return (result.count or 0) > 0
        except Exception as e:
            logger.debug(
                "check_party_verified_failed",
                error=str(e),
                entity_id=entity_id,
            )
            return False

    async def _check_section_verified(
        self,
        matter_id: str,
        section_type: SummarySectionTypeEnum,
        section_id: str,
    ) -> bool:
        """Check if a summary section has been verified.

        Story 14.4: AC #7 - Check summary_verifications table.

        Args:
            matter_id: Matter UUID.
            section_type: Type of section.
            section_id: Section identifier.

        Returns:
            True if section has verified decision.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_verifications")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("section_type", section_type.value)
                .eq("section_id", section_id)
                .eq("decision", "verified")
                .execute()
            )
            return (result.count or 0) > 0
        except Exception as e:
            logger.debug(
                "check_section_verified_failed",
                error=str(e),
                section_type=section_type.value,
                section_id=section_id,
            )
            return False

    async def _get_issue_verification_status(
        self,
        matter_id: str,
        issue_id: str,
    ) -> KeyIssueVerificationStatus:
        """Get verification status for a key issue.

        Story 14.4: AC #7 - Map summary_verifications to KeyIssueVerificationStatus.

        Args:
            matter_id: Matter UUID.
            issue_id: Issue identifier.

        Returns:
            KeyIssueVerificationStatus (verified, pending, or flagged).
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("summary_verifications")
                .select("decision")
                .eq("matter_id", matter_id)
                .eq("section_type", SummarySectionTypeEnum.KEY_ISSUE.value)
                .eq("section_id", issue_id)
                .limit(1)
                .execute()
            )

            if not result.data:
                return KeyIssueVerificationStatus.PENDING

            decision = result.data[0].get("decision")
            if decision == "verified":
                return KeyIssueVerificationStatus.VERIFIED
            elif decision == "flagged":
                return KeyIssueVerificationStatus.FLAGGED
            else:
                return KeyIssueVerificationStatus.PENDING

        except Exception as e:
            logger.debug(
                "get_issue_verification_status_failed",
                error=str(e),
                issue_id=issue_id,
            )
            return KeyIssueVerificationStatus.PENDING

    # =========================================================================
    # Stats (Task 2.4) - AC #7
    # =========================================================================

    async def get_stats(self, matter_id: str) -> MatterStats:
        """Compute matter statistics from database.

        Story 14.1: AC #7 - Stats computed from actual database tables.

        Args:
            matter_id: Matter UUID.

        Returns:
            MatterStats with all computed values.
        """
        # Run all count queries in parallel
        (
            total_pages,
            entities_found,
            events_extracted,
            citations_found,
            verification_stats,
        ) = await asyncio.gather(
            self._get_total_pages(matter_id),
            self._get_entities_count(matter_id),
            self._get_events_count(matter_id),
            self._get_citations_count(matter_id),
            self._get_verification_stats(matter_id),
        )

        return MatterStats(
            total_pages=total_pages,
            entities_found=entities_found,
            events_extracted=events_extracted,
            citations_found=citations_found,
            verification_percent=verification_stats,
        )

    async def _get_total_pages(self, matter_id: str) -> int:
        """Get total pages from documents table (excluding soft-deleted)."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("documents")
                .select("page_count")
                .eq("matter_id", matter_id)
                .is_("deleted_at", "null")
                .execute()
            )
            return sum(
                row.get("page_count", 0) or 0 for row in result.data or []
            )
        except Exception as e:
            logger.warning("get_total_pages_failed", error=str(e))
            return 0

    async def _get_entities_count(self, matter_id: str) -> int:
        """Count entities from identity_nodes table.

        Only counts non-merged entities (merged_into_id IS NULL) to match
        what the Entities tab displays.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("identity_nodes")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .is_("merged_into_id", "null")  # Only active (non-merged) entities
                .execute()
            )
            return result.count or 0
        except Exception as e:
            logger.warning("get_entities_count_failed", error=str(e))
            return 0

    async def _get_events_count(self, matter_id: str) -> int:
        """Count events from events table."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("events")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )
            return result.count or 0
        except Exception as e:
            logger.warning("get_events_count_failed", error=str(e))
            return 0

    async def _get_citations_count(self, matter_id: str) -> int:
        """Count citations using the same filtered logic as the Citations tab.

        BUG-LT3-K fix: Previously this was a raw COUNT(*) on the citations table,
        which included citations from Act documents (self-referencing) and invalid
        act names. The Citations tab filtered these out via get_citation_counts_by_act,
        causing a mismatch (e.g., 21 vs 19). Now both use the same source of truth.
        """
        try:
            from app.engines.citation.storage import get_citation_storage_service

            storage = get_citation_storage_service()
            counts = await storage.get_citation_counts_by_act(matter_id)
            return sum(c["citation_count"] for c in counts)
        except Exception as e:
            logger.warning("get_citations_count_failed", error=str(e))
            return 0

    async def _get_verification_stats(self, matter_id: str) -> float:
        """Calculate verification percentage from finding_verifications table."""
        try:
            # LATENCY FIX: Parallelize both count queries
            total_result, approved_result = await asyncio.gather(
                asyncio.to_thread(
                    lambda: self.supabase.table("finding_verifications")
                    .select("id", count="exact")
                    .eq("matter_id", matter_id)
                    .execute()
                ),
                asyncio.to_thread(
                    lambda: self.supabase.table("finding_verifications")
                    .select("id", count="exact")
                    .eq("matter_id", matter_id)
                    .eq("decision", "approved")
                    .execute()
                ),
            )
            total = total_result.count or 0
            approved = approved_result.count or 0

            if total == 0:
                return 0.0

            return round((approved / total) * 100, 1)
        except Exception as e:
            logger.warning("get_verification_stats_failed", error=str(e))
            return 0.0

    # =========================================================================
    # GPT-4 Generation (Task 2.5, 2.6, 2.7)
    # =========================================================================

    async def generate_subject_matter(
        self,
        matter_id: str,
        chunks: list[dict],
    ) -> SubjectMatter:
        """Generate subject matter description using GPT-4.

        Story 14.1: AC #3 - GPT-4 for executive summary generation.
        Story 14.4: AC #7 - Check real verification status.
        Story 14.6: AC #9 - Include citations and edited content.

        Args:
            matter_id: Matter UUID.
            chunks: Top chunks retrieved via RAG.

        Returns:
            SubjectMatter with AI-generated description.
        """
        if not chunks:
            return SubjectMatter(
                description="No documents available to generate summary.",
                sources=[],
                is_verified=False,
            )

        try:
            user_prompt = format_subject_matter_prompt(chunks)

            # Cost tracking for GPT-4 usage
            cost_tracker = CostTracker(
                provider=LLMProvider.OPENAI_GPT4O,
                operation="summary_subject_matter",
                matter_id=matter_id,
            )

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SUBJECT_MATTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            # Track tokens from response
            if response.usage:
                cached_tokens = 0
                if response.usage.prompt_tokens_details:
                    cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0
                cost_tracker.add_tokens(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    cached_input_tokens=cached_tokens,
                )
            cost_tracker.log_cost()
            await persist_cost(cost_tracker)

            response_text = response.choices[0].message.content
            parsed = json.loads(response_text)

            # Validate that GPT-4 didn't echo the schema placeholder
            raw_description = parsed.get("description", "")
            _placeholder_markers = [
                "YOUR FULL CASE OVERVIEW HERE",
                "formatted case overview with all sections using markdown",
                "<your complete case overview",
            ]
            if any(m.lower() in raw_description.lower() for m in _placeholder_markers):
                logger.warning(
                    "subject_matter_placeholder_detected",
                    matter_id=matter_id,
                    description_preview=raw_description[:100],
                )
                # Re-attempt with stronger instruction
                retry_response = await self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": SUBJECT_MATTER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": response_text},
                        {
                            "role": "user",
                            "content": "That description is a placeholder, not actual analysis. "
                            "Re-read the document excerpts and write the REAL case overview "
                            "with specific details (names, dates, case numbers) from the documents.",
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.5,
                )
                # Track cost for retry call
                retry_tracker = CostTracker(
                    provider=LLMProvider.OPENAI_GPT4O,
                    operation="summary_subject_matter_retry",
                    matter_id=matter_id,
                )
                if retry_response.usage:
                    retry_tracker.add_tokens(
                        input_tokens=retry_response.usage.prompt_tokens or 0,
                        output_tokens=retry_response.usage.completion_tokens or 0,
                        cached_input_tokens=getattr(retry_response.usage, 'prompt_tokens_details', None)
                        and getattr(retry_response.usage.prompt_tokens_details, 'cached_tokens', 0) or 0,
                    )
                retry_tracker.log_cost()
                await persist_cost(retry_tracker)

                retry_text = retry_response.choices[0].message.content
                parsed = json.loads(retry_text)
                raw_description = parsed.get("description", "")

            # BUG-003 FIX: Structural section validator.
            # Verify the Case Overview contains all required sections.  If any
            # are missing, retry once with explicit instructions listing the
            # missing sections.  This makes correctness structural rather than
            # relying solely on prompt compliance.
            _required_sections = {
                "Case Type": r"\*\*Case Type",
                "Parties": r"\*\*Parties",
                "Core Dispute": r"\*\*Core Dispute",
                "Background": r"\*\*Background",
            }
            missing = [
                name
                for name, pattern in _required_sections.items()
                if not re.search(pattern, raw_description, re.IGNORECASE)
            ]
            if missing and not any(
                m.lower() in raw_description.lower() for m in _placeholder_markers
            ):
                logger.warning(
                    "subject_matter_missing_sections",
                    matter_id=matter_id,
                    missing_sections=missing,
                )
                section_retry_response = await self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": SUBJECT_MATTER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": response_text},
                        {
                            "role": "user",
                            "content": (
                                "Your response is missing these required sections: "
                                f"{', '.join(missing)}. "
                                "Regenerate the complete case overview with ALL "
                                "required sections: Case Type, Forum, Parties, "
                                "Core Dispute, Background, Relief Sought, Current Stage."
                            ),
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.4,
                )
                retry_tracker = CostTracker(
                    provider=LLMProvider.OPENAI_GPT4O,
                    operation="summary_subject_matter_section_retry",
                    matter_id=matter_id,
                )
                if section_retry_response.usage:
                    retry_tracker.add_tokens(
                        input_tokens=section_retry_response.usage.prompt_tokens or 0,
                        output_tokens=section_retry_response.usage.completion_tokens or 0,
                        cached_input_tokens=getattr(
                            section_retry_response.usage, "prompt_tokens_details", None
                        )
                        and getattr(
                            section_retry_response.usage.prompt_tokens_details,
                            "cached_tokens",
                            0,
                        )
                        or 0,
                    )
                retry_tracker.log_cost()
                await persist_cost(retry_tracker)

                retry_text = section_retry_response.choices[0].message.content
                retry_parsed = json.loads(retry_text)
                retry_description = retry_parsed.get("description", "")

                # Accept retry if it has MORE required sections than original
                retry_missing = [
                    name
                    for name, pattern in _required_sections.items()
                    if not re.search(pattern, retry_description, re.IGNORECASE)
                ]
                if len(retry_missing) < len(missing):
                    raw_description = retry_description
                    parsed = retry_parsed
                    logger.info(
                        "subject_matter_section_retry_improved",
                        matter_id=matter_id,
                        original_missing=missing,
                        retry_missing=retry_missing,
                    )
                else:
                    logger.info(
                        "subject_matter_section_retry_no_improvement",
                        matter_id=matter_id,
                        missing_sections=missing,
                    )

            # Apply language policing
            policing = get_language_policing_service()
            policed_description = policing.sanitize_text(raw_description).sanitized_text

            sources = [
                SubjectMatterSource(
                    document_name=s.get("documentName", ""),
                    page_range=s.get("pageRange", ""),
                )
                for s in parsed.get("sources", [])
            ]

            # Story 14.4: Check real verification status from summary_verifications
            is_verified = await self._check_section_verified(
                matter_id,
                SummarySectionTypeEnum.SUBJECT_MATTER,
                "main",
            )

            # Story 14.6: Check for user edits
            edit_service = get_summary_edit_service()
            edit = await edit_service.get_edit(
                matter_id=matter_id,
                section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
                section_id="main",
            )
            edited_content = edit.edited_content if edit else None

            # Story 14.6: Build citations from chunks
            citations = await self._build_citations_from_chunks(matter_id, chunks[:3])

            return SubjectMatter(
                description=policed_description,
                sources=sources,
                is_verified=is_verified,
                edited_content=edited_content,
                citations=citations,
            )

        except Exception as e:
            logger.error(
                "generate_subject_matter_failed",
                error=str(e),
                error_type=type(e).__name__,
                matter_id=matter_id,
                exc_info=True,
            )
            return SubjectMatter(
                description="Unable to generate summary at this time.",
                sources=[],
                is_verified=False,
            )

    async def get_key_issues(
        self,
        matter_id: str,
        chunks: list[dict],
    ) -> list[KeyIssue]:
        """Extract key issues using GPT-4.

        Story 14.1: AC #3 - GPT-4 for key issues extraction.
        Story 14.4: AC #7 - Check real verification status for each issue.

        Args:
            matter_id: Matter UUID.
            chunks: Top chunks retrieved via RAG.

        Returns:
            List of KeyIssue objects.
        """
        if not chunks:
            return []

        try:
            user_prompt = format_key_issues_prompt(chunks)

            # Cost tracking for GPT-4 usage
            cost_tracker = CostTracker(
                provider=LLMProvider.OPENAI_GPT4O,
                operation="summary_key_issues",
                matter_id=matter_id,
            )

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": KEY_ISSUES_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            # Track tokens from response
            if response.usage:
                cached_tokens = 0
                if response.usage.prompt_tokens_details:
                    cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0
                cost_tracker.add_tokens(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    cached_input_tokens=cached_tokens,
                )
            cost_tracker.log_cost()
            await persist_cost(cost_tracker)

            response_text = response.choices[0].message.content
            parsed = json.loads(response_text)

            # Apply language policing to each issue
            policing = get_language_policing_service()

            issues = []
            for item in parsed.get("issues", [])[:MAX_KEY_ISSUES]:
                policed_title = policing.sanitize_text(
                    item.get("title", "")
                ).sanitized_text

                issue_id = item.get("id", f"issue-{uuid.uuid4().hex[:8]}")

                # Story 14.4: Check real verification status for this issue
                verification = await self._get_issue_verification_status(
                    matter_id, issue_id
                )

                issues.append(
                    KeyIssue(
                        id=issue_id,
                        number=item.get("number", len(issues) + 1),
                        title=policed_title,
                        verification_status=verification,
                    )
                )

            return issues

        except Exception as e:
            logger.error(
                "get_key_issues_failed",
                error=str(e),
                error_type=type(e).__name__,
                matter_id=matter_id,
                exc_info=True,
            )
            return []

    async def get_current_status(
        self,
        matter_id: str,
        chunks: list[dict],
        events: list[dict] | None = None,
    ) -> CurrentStatus:
        """Get current status using GPT-4.

        Story 14.1: AC #2 - Current status with last order.
        Story 14.4: AC #7 - Check real verification status.
        Story 14.6: AC #9 - Include citation and edited content.

        Args:
            matter_id: Matter UUID.
            chunks: Top chunks retrieved via RAG.
            events: Optional recent timeline events.

        Returns:
            CurrentStatus with last order details.
        """
        # Default status if no data
        default_status = CurrentStatus(
            last_order_date=None,
            description="No orders found in the uploaded documents.",
            source_document="N/A",
            source_page=1,
            is_verified=False,
        )

        if not chunks and not events:
            return default_status

        try:
            user_prompt = format_current_status_prompt(chunks, events)

            # Cost tracking for GPT-4 usage
            cost_tracker = CostTracker(
                provider=LLMProvider.OPENAI_GPT4O,
                operation="summary_current_status",
                matter_id=matter_id,
            )

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": CURRENT_STATUS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            # Track tokens from response
            if response.usage:
                cached_tokens = 0
                if response.usage.prompt_tokens_details:
                    cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0
                cost_tracker.add_tokens(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    cached_input_tokens=cached_tokens,
                )
            cost_tracker.log_cost()
            await persist_cost(cost_tracker)

            response_text = response.choices[0].message.content
            parsed = json.loads(response_text)

            # Apply language policing
            policing = get_language_policing_service()
            policed_description = policing.sanitize_text(
                parsed.get("description", "")
            ).sanitized_text

            # Parse date
            last_order_date = parsed.get("lastOrderDate", "Unknown")
            if last_order_date == "Unknown":
                last_order_date = None

            source_document = parsed.get("sourceDocument", "Unknown")
            source_page = parsed.get("sourcePage", 1)

            # Story 14.4: Check real verification status from summary_verifications
            is_verified = await self._check_section_verified(
                matter_id,
                SummarySectionTypeEnum.CURRENT_STATUS,
                "main",
            )

            # Story 14.6: Check for user edits
            edit_service = get_summary_edit_service()
            edit = await edit_service.get_edit(
                matter_id=matter_id,
                section_type=SummarySectionTypeEnum.CURRENT_STATUS,
                section_id="main",
            )
            edited_content = edit.edited_content if edit else None

            # Story 14.6: Build citation for source document
            citation = await self._build_citation_for_document(
                matter_id, source_document, source_page
            )

            return CurrentStatus(
                last_order_date=last_order_date,
                description=policed_description,
                source_document=source_document,
                source_page=source_page,
                is_verified=is_verified,
                edited_content=edited_content,
                citation=citation,
            )

        except Exception as e:
            logger.error(
                "get_current_status_failed",
                error=str(e),
                error_type=type(e).__name__,
                matter_id=matter_id,
                exc_info=True,
            )
            return default_status

    # =========================================================================
    # RAG Helpers
    # =========================================================================

    async def _get_top_chunks(
        self,
        matter_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Retrieve top chunks for summary generation (excluding soft-deleted docs).

        Samples chunks across ALL documents to get representative content,
        rather than just taking the most recent chunks (which could all be
        from one document).

        Args:
            matter_id: Matter UUID.
            limit: Maximum chunks to retrieve.

        Returns:
            List of chunk dictionaries with content and metadata.
        """
        try:
            # Get active document IDs (non-deleted, non-reference material)
            # Reference material like Acts should not dominate the case summary
            docs_result = await asyncio.to_thread(
                lambda: self.supabase.table("documents")
                .select("id, is_reference_material")
                .eq("matter_id", matter_id)
                .is_("deleted_at", "null")
                .execute()
            )

            # Separate case documents from reference material
            case_doc_ids = []
            reference_doc_ids = []
            for d in docs_result.data or []:
                if d.get("is_reference_material"):
                    reference_doc_ids.append(d["id"])
                else:
                    case_doc_ids.append(d["id"])

            # Prioritize case documents, fall back to reference if no case docs
            active_doc_ids = case_doc_ids if case_doc_ids else reference_doc_ids

            if not active_doc_ids:
                return []

            # Get chunks distributed across documents
            # Take first chunk from each document, then cycle through
            all_chunks = []
            chunks_per_doc = max(1, limit // len(active_doc_ids))

            for doc_id in active_doc_ids:
                result = await asyncio.to_thread(
                    lambda did=doc_id: self.supabase.table("chunks")
                    .select("id, content, page_number, document_id, documents(filename)")
                    .eq("document_id", did)
                    .order("page_number")
                    .limit(chunks_per_doc)
                    .execute()
                )

                for row in result.data or []:
                    doc_data = row.get("documents", {}) or {}
                    all_chunks.append({
                        "content": row.get("content", ""),
                        "document_name": doc_data.get("filename", "Unknown"),
                        "page_number": row.get("page_number"),
                    })

            # Return up to limit chunks
            return all_chunks[:limit]

        except Exception as e:
            logger.warning("get_top_chunks_failed", error=str(e))
            return []

    async def _get_recent_events(
        self,
        matter_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """Get most recent timeline events (excluding soft-deleted docs).

        Args:
            matter_id: Matter UUID.
            limit: Maximum events to retrieve.

        Returns:
            List of event dictionaries.
        """
        try:
            # Get active document IDs first
            docs_result = await asyncio.to_thread(
                lambda: self.supabase.table("documents")
                .select("id")
                .eq("matter_id", matter_id)
                .is_("deleted_at", "null")
                .execute()
            )
            active_doc_ids = [d["id"] for d in docs_result.data or []]

            if not active_doc_ids:
                return []

            result = await asyncio.to_thread(
                lambda: self.supabase.table("events")
                .select("id, event_date, description, event_type, document_id, documents(filename)")
                .eq("matter_id", matter_id)
                .in_("document_id", active_doc_ids)
                .order("event_date", desc=True)
                .limit(limit)
                .execute()
            )

            events = []
            for row in result.data or []:
                doc_data = row.get("documents", {}) or {}
                events.append({
                    "event_date": row.get("event_date", ""),
                    "description": row.get("description", ""),
                    "event_type": row.get("event_type", ""),
                    "document_name": doc_data.get("filename", ""),
                })

            return events

        except Exception as e:
            logger.warning("get_recent_events_failed", error=str(e))
            return []

    # =========================================================================
    # Story 14.6: Citation Helpers
    # =========================================================================

    async def _build_citations_from_chunks(
        self,
        matter_id: str,
        chunks: list[dict],
    ) -> list[Citation]:
        """Build Citation objects from chunk data.

        Story 14.6: AC #9 - Converts chunk metadata to Citation models.

        Args:
            matter_id: Matter UUID.
            chunks: List of chunk dictionaries with content and metadata.

        Returns:
            List of Citation objects.
        """
        citations = []
        for chunk in chunks:
            document_name = chunk.get("document_name", "")
            # Don't default to 1 - allow None for unknown pages
            page_number = chunk.get("page_number")
            content = chunk.get("content", "")

            # Look up document ID from documents table
            document_id = await self._get_document_id_by_name(matter_id, document_name)
            if document_id:
                # Truncate excerpt to 200 chars
                excerpt = content[:200] + "..." if len(content) > 200 else content

                citations.append(
                    Citation(
                        document_id=document_id,
                        document_name=document_name,
                        page=page_number,  # Allow None - don't default to 1
                        excerpt=excerpt,
                    )
                )

        return citations

    async def _build_citation_for_document(
        self,
        matter_id: str,
        document_name: str,
        page: int,
    ) -> Citation | None:
        """Build a single Citation object for a document reference.

        Story 14.6: AC #9 - Converts document reference to Citation model.

        Args:
            matter_id: Matter UUID.
            document_name: Name of the document.
            page: Page number.

        Returns:
            Citation object or None if document not found.
        """
        if not document_name or document_name == "Unknown" or document_name == "N/A":
            return None

        document_id = await self._get_document_id_by_name(matter_id, document_name)
        if not document_id:
            return None

        return Citation(
            document_id=document_id,
            document_name=document_name,
            page=page,
            excerpt=None,
        )

    async def _get_document_id_by_name(
        self,
        matter_id: str,
        document_name: str,
    ) -> str | None:
        """Look up document ID by name (excluding soft-deleted).

        Args:
            matter_id: Matter UUID.
            document_name: Document name to search for.

        Returns:
            Document UUID or None if not found.
        """
        if not document_name:
            return None

        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("documents")
                .select("id")
                .eq("matter_id", matter_id)
                .eq("filename", document_name)
                .is_("deleted_at", "null")
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0].get("id")
            return None

        except Exception as e:
            logger.debug(
                "get_document_id_by_name_failed",
                document_name=document_name,
                error=str(e),
            )
            return None

    # =========================================================================
    # Summary Validation
    # =========================================================================

    def is_summary_valid(self, summary: MatterSummary) -> bool:
        """Check if summary generation actually succeeded.

        BUG-003 FIX: Requires subject_matter AND at least one of the other
        sections to succeed.  Previously used OR (any-one-ok), which cached
        incomplete summaries missing key sections.

        Args:
            summary: The generated summary to validate.

        Returns:
            True if subject_matter succeeded and at least one other section did.
        """
        subject_matter_ok = (
            summary.subject_matter.description
            != "Unable to generate summary at this time."
            and len(summary.subject_matter.description) > 50
        )
        key_issues_ok = len(summary.key_issues) > 0
        current_status_ok = (
            summary.current_status.description
            != "No orders found in the uploaded documents."
            or summary.current_status.last_order_date is not None
        )

        # Subject matter is mandatory; at least one other section must also pass
        return subject_matter_ok and (key_issues_ok or current_status_ok)

    # =========================================================================
    # Redis Caching (Task 2.8) - AC #4
    # =========================================================================

    async def get_cached_summary(self, matter_id: str) -> MatterSummary | None:
        """Get summary from Redis cache.

        Story 14.1: AC #4 - Summary cached with 1-hour TTL.

        Args:
            matter_id: Matter UUID.

        Returns:
            Cached MatterSummary or None if not found.
        """
        try:
            redis = await get_redis_client()
            key = summary_cache_key(matter_id)
            cached = await redis.get(key)

            if cached:
                # Parse JSON and validate
                data = json.loads(cached)
                return MatterSummary.model_validate(data)

            return None

        except Exception as e:
            logger.warning(
                "summary_cache_get_failed",
                error=str(e),
                matter_id=matter_id,
            )
            return None

    async def _cache_summary(
        self,
        matter_id: str,
        summary: MatterSummary,
    ) -> None:
        """Cache summary in Redis.

        Story 14.1: AC #4 - 1-hour TTL.

        Args:
            matter_id: Matter UUID.
            summary: Summary to cache.
        """
        try:
            redis = await get_redis_client()
            key = summary_cache_key(matter_id)
            # Use by_alias=True to match frontend camelCase
            data = summary.model_dump_json(by_alias=True)
            await redis.setex(key, SUMMARY_CACHE_TTL, data)

            logger.debug(
                "summary_cached",
                matter_id=matter_id,
                ttl=SUMMARY_CACHE_TTL,
            )

        except Exception as e:
            logger.warning(
                "summary_cache_set_failed",
                error=str(e),
                matter_id=matter_id,
            )

    async def invalidate_cache(self, matter_id: str) -> bool:
        """Invalidate cached summary for a matter.

        Story 14.1: AC #4 - Invalidate on document upload.

        Args:
            matter_id: Matter UUID.

        Returns:
            True if cache was invalidated.
        """
        try:
            redis = await get_redis_client()
            key = summary_cache_key(matter_id)
            result = await redis.delete(key)

            logger.info(
                "summary_cache_invalidated",
                matter_id=matter_id,
                deleted=result > 0,
            )

            return result > 0

        except Exception as e:
            logger.warning(
                "summary_cache_invalidate_failed",
                error=str(e),
                matter_id=matter_id,
            )
            return False


# =============================================================================
# Story 14.1: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_summary_service() -> SummaryService:
    """Get singleton summary service instance.

    Returns:
        SummaryService instance.
    """
    return SummaryService()
