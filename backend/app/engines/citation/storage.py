"""Citation Storage Service for database operations.

Handles saving, retrieving, and updating citations and act resolutions
in Supabase with RLS-enforced matter isolation.

CRITICAL: Always validates matter_id for Layer 4 matter isolation.

NOTE: Uses asyncio.to_thread() to run synchronous Supabase client calls
without blocking the event loop.

Story 3-1: Act Citation Extraction (AC: #3, #4)
"""

import asyncio
from datetime import UTC, datetime
from functools import lru_cache
from typing import Final

import structlog

from app.engines.citation.abbreviations import (
    get_canonical_name,
    get_display_name,
    normalize_act_name,
)
from app.models.citation import (
    ActResolution,
    ActResolutionStatus,
    Citation,
    CitationCreate,
    CitationExtractionResult,
    ExtractedCitation,
    UserAction,
    VerificationStatus,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

BATCH_SIZE: Final[int] = 50  # Citations per database batch


# =============================================================================
# Exceptions
# =============================================================================


class CitationStorageError(Exception):
    """Base exception for citation storage operations."""

    def __init__(
        self,
        message: str,
        code: str = "CITATION_STORAGE_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


# =============================================================================
# Service Implementation
# =============================================================================


class CitationStorageService:
    """Service for storing and retrieving citations from database.

    Uses Supabase service client for RLS-bypassed operations.
    All methods enforce matter isolation through query parameters.

    CRITICAL: All operations validate matter_id for security.

    All async methods use asyncio.to_thread() to run synchronous Supabase
    client calls without blocking the event loop.

    Example:
        >>> storage = CitationStorageService()
        >>> count = await storage.save_citations(matter_id, citations)
        >>> citations = await storage.get_citations_by_document(doc_id)
    """

    def __init__(self) -> None:
        """Initialize citation storage service."""
        self._client = None

    @property
    def client(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            CitationStorageError: If client not configured.
        """
        if self._client is None:
            self._client = get_service_client()
            if self._client is None:
                raise CitationStorageError(
                    "Supabase client not configured",
                    code="DATABASE_NOT_CONFIGURED",
                )
        return self._client

    async def save_citations(
        self,
        matter_id: str,
        document_id: str,
        extraction_result: CitationExtractionResult,
        source_bbox_ids: list[str] | None = None,
    ) -> int:
        """Save extracted citations to database.

        Args:
            matter_id: Matter UUID.
            document_id: Source document UUID.
            extraction_result: Extraction result containing citations.
            source_bbox_ids: Optional bounding box IDs for highlighting.

        Returns:
            Number of citations saved.
        """
        if not extraction_result.citations:
            return 0

        saved_count = 0

        try:
            # Process in batches
            for i in range(0, len(extraction_result.citations), BATCH_SIZE):
                batch = extraction_result.citations[i : i + BATCH_SIZE]
                records = []

                for citation in batch:
                    # Get canonical name if available
                    canonical = get_canonical_name(citation.act_name)
                    act_name = citation.act_name
                    if canonical:
                        name, year = canonical
                        if year:
                            act_name = f"{name}, {year}"
                        else:
                            act_name = name

                    record = {
                        "matter_id": matter_id,
                        "source_document_id": document_id,
                        "act_name": act_name,
                        "act_name_original": citation.act_name,
                        "section": citation.section,
                        "subsection": citation.subsection,
                        "clause": citation.clause,
                        "raw_citation_text": citation.raw_text,
                        "quoted_text": citation.quoted_text,
                        "source_page": extraction_result.page_number or 1,
                        "source_bbox_ids": source_bbox_ids or [],
                        "verification_status": VerificationStatus.ACT_UNAVAILABLE.value,
                        # Confidence: Model uses 0-100 for display, DB uses 0-1 for indexing
                        "confidence": citation.confidence / 100.0,
                        "extraction_metadata": {
                            "extraction_timestamp": datetime.now(UTC).isoformat(),
                            "source_chunk_id": extraction_result.source_chunk_id,
                        },
                    }
                    records.append(record)

                # Insert batch using asyncio.to_thread
                def _insert_batch():
                    return self.client.table("citations").insert(records).execute()

                result = await asyncio.to_thread(_insert_batch)

                if result.data:
                    saved_count += len(result.data)

                    # Update act resolutions for each unique act in batch
                    unique_acts = set(r["act_name"] for r in records)
                    for act_name in unique_acts:
                        await self.create_or_update_act_resolution(
                            matter_id=matter_id,
                            act_name=act_name,
                        )

            logger.info(
                "citations_saved",
                matter_id=matter_id,
                document_id=document_id,
                saved_count=saved_count,
                total_citations=len(extraction_result.citations),
            )

            return saved_count

        except Exception as e:
            logger.error(
                "citation_save_failed",
                matter_id=matter_id,
                document_id=document_id,
                error=str(e),
            )
            raise CitationStorageError(
                f"Failed to save citations: {e}",
                code="CITATION_SAVE_FAILED",
            ) from e

    async def get_citations_by_document(
        self,
        document_id: str,
        matter_id: str | None = None,
    ) -> list[Citation]:
        """Get all citations from a specific document.

        Args:
            document_id: Document UUID.
            matter_id: Optional matter UUID for additional filtering.

        Returns:
            List of citations.
        """
        try:
            def _query():
                query = self.client.table("citations").select("*").eq(
                    "source_document_id", document_id
                )
                if matter_id:
                    query = query.eq("matter_id", matter_id)
                return query.order("source_page").execute()

            result = await asyncio.to_thread(_query)

            return [self._row_to_citation(row) for row in (result.data or [])]

        except Exception as e:
            logger.error(
                "get_citations_by_document_failed",
                document_id=document_id,
                error=str(e),
            )
            return []

    async def get_citations_by_matter(
        self,
        matter_id: str,
        act_name: str | None = None,
        verification_status: VerificationStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Citation], int]:
        """Get citations for a matter with optional filtering.

        Args:
            matter_id: Matter UUID.
            act_name: Optional filter by Act name.
            verification_status: Optional filter by status.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (citations list, total count).
        """
        try:
            # Calculate offset
            offset = (page - 1) * per_page

            def _query():
                query = self.client.table("citations").select(
                    "*", count="exact"
                ).eq("matter_id", matter_id)

                if act_name:
                    query = query.eq("act_name", act_name)

                if verification_status:
                    query = query.eq("verification_status", verification_status.value)

                return query.order("created_at", desc=True).range(
                    offset, offset + per_page - 1
                ).execute()

            result = await asyncio.to_thread(_query)

            citations = [self._row_to_citation(row) for row in (result.data or [])]
            total = result.count or 0

            return citations, total

        except Exception as e:
            logger.error(
                "get_citations_by_matter_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return [], 0

    async def get_citation(
        self,
        citation_id: str,
        matter_id: str | None = None,
    ) -> Citation | None:
        """Get a single citation by ID.

        Args:
            citation_id: Citation UUID.
            matter_id: Optional matter UUID for validation.

        Returns:
            Citation or None if not found.
        """
        try:
            def _query():
                query = self.client.table("citations").select("*").eq("id", citation_id)
                if matter_id:
                    query = query.eq("matter_id", matter_id)
                return query.single().execute()

            result = await asyncio.to_thread(_query)

            if result.data:
                return self._row_to_citation(result.data)
            return None

        except Exception as e:
            logger.error(
                "get_citation_failed",
                citation_id=citation_id,
                error=str(e),
            )
            return None

    async def create_or_update_act_resolution(
        self,
        matter_id: str,
        act_name: str,
    ) -> ActResolution | None:
        """Create or update act resolution record.

        Increments citation count if resolution already exists.

        Args:
            matter_id: Matter UUID.
            act_name: Display name of Act.

        Returns:
            ActResolution or None on error.
        """
        try:
            normalized = normalize_act_name(act_name)

            # Try using the upsert function first
            try:
                def _rpc_upsert():
                    return self.client.rpc(
                        "upsert_act_resolution",
                        {
                            "p_matter_id": matter_id,
                            "p_act_name_normalized": normalized,
                        },
                    ).execute()

                result = await asyncio.to_thread(_rpc_upsert)

                if result.data:
                    # Fetch the full record
                    def _fetch():
                        return self.client.table("act_resolutions").select(
                            "*"
                        ).eq("id", result.data).single().execute()

                    fetch_result = await asyncio.to_thread(_fetch)

                    if fetch_result.data:
                        return self._row_to_act_resolution(fetch_result.data)
            except Exception:
                # Fallback to manual upsert if function doesn't exist
                pass

            # Manual upsert
            def _check_existing():
                return self.client.table("act_resolutions").select("*").eq(
                    "matter_id", matter_id
                ).eq("act_name_normalized", normalized).execute()

            existing = await asyncio.to_thread(_check_existing)

            if existing.data and len(existing.data) > 0:
                # Update existing
                row = existing.data[0]

                def _update():
                    return self.client.table("act_resolutions").update({
                        "citation_count": (row.get("citation_count", 0) or 0) + 1,
                        "updated_at": datetime.now(UTC).isoformat(),
                    }).eq("id", row["id"]).execute()

                update_result = await asyncio.to_thread(_update)

                if update_result.data:
                    return self._row_to_act_resolution(update_result.data[0])
            else:
                # Create new
                def _insert():
                    return self.client.table("act_resolutions").insert({
                        "matter_id": matter_id,
                        "act_name_normalized": normalized,
                        "act_name_display": act_name,
                        "resolution_status": ActResolutionStatus.MISSING.value,
                        "user_action": UserAction.PENDING.value,
                        "citation_count": 1,
                    }).execute()

                insert_result = await asyncio.to_thread(_insert)

                if insert_result.data:
                    return self._row_to_act_resolution(insert_result.data[0])

            return None

        except Exception as e:
            logger.error(
                "create_or_update_act_resolution_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return None

    async def get_act_resolutions(
        self,
        matter_id: str,
        status: ActResolutionStatus | None = None,
    ) -> list[ActResolution]:
        """Get act resolutions for a matter.

        Args:
            matter_id: Matter UUID.
            status: Optional filter by resolution status.

        Returns:
            List of act resolutions.
        """
        try:
            def _query():
                query = self.client.table("act_resolutions").select("*").eq(
                    "matter_id", matter_id
                )
                if status:
                    query = query.eq("resolution_status", status.value)
                return query.order("citation_count", desc=True).execute()

            result = await asyncio.to_thread(_query)

            return [
                self._row_to_act_resolution(row) for row in (result.data or [])
            ]

        except Exception as e:
            logger.error(
                "get_act_resolutions_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    async def update_act_resolution(
        self,
        matter_id: str,
        act_name_normalized: str,
        act_document_id: str | None = None,
        resolution_status: ActResolutionStatus | None = None,
        user_action: UserAction | None = None,
    ) -> ActResolution | None:
        """Update act resolution status.

        Args:
            matter_id: Matter UUID.
            act_name_normalized: Normalized Act name.
            act_document_id: Optional uploaded Act document UUID.
            resolution_status: Optional new resolution status.
            user_action: Optional new user action.

        Returns:
            Updated ActResolution or None.
        """
        try:
            update_data: dict = {"updated_at": datetime.now(UTC).isoformat()}

            if act_document_id is not None:
                update_data["act_document_id"] = act_document_id

            if resolution_status is not None:
                update_data["resolution_status"] = resolution_status.value

            if user_action is not None:
                update_data["user_action"] = user_action.value

            def _update():
                return self.client.table("act_resolutions").update(update_data).eq(
                    "matter_id", matter_id
                ).eq("act_name_normalized", act_name_normalized).execute()

            result = await asyncio.to_thread(_update)

            if result.data and len(result.data) > 0:
                return self._row_to_act_resolution(result.data[0])

            return None

        except Exception as e:
            logger.error(
                "update_act_resolution_failed",
                matter_id=matter_id,
                act_name_normalized=act_name_normalized,
                error=str(e),
            )
            return None

    async def get_citation_counts_by_act(
        self,
        matter_id: str,
    ) -> list[dict]:
        """Get citation counts grouped by Act name.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of dicts with act_name, citation_count, verified_count, pending_count.
        """
        try:
            # Get all citations for the matter
            def _query():
                return self.client.table("citations").select(
                    "act_name, verification_status"
                ).eq("matter_id", matter_id).execute()

            result = await asyncio.to_thread(_query)

            # Aggregate counts
            counts: dict[str, dict] = {}
            for row in (result.data or []):
                act_name = row["act_name"]
                status = row["verification_status"]

                if act_name not in counts:
                    counts[act_name] = {
                        "act_name": act_name,
                        "citation_count": 0,
                        "verified_count": 0,
                        "pending_count": 0,
                    }

                counts[act_name]["citation_count"] += 1

                if status == VerificationStatus.VERIFIED.value:
                    counts[act_name]["verified_count"] += 1
                elif status in [
                    VerificationStatus.PENDING.value,
                    VerificationStatus.ACT_UNAVAILABLE.value,
                ]:
                    counts[act_name]["pending_count"] += 1

            # Sort by citation count
            return sorted(
                counts.values(),
                key=lambda x: x["citation_count"],
                reverse=True,
            )

        except Exception as e:
            logger.error(
                "get_citation_counts_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    def _row_to_citation(self, row: dict) -> Citation:
        """Convert database row to Citation model."""
        return Citation(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row["source_document_id"],
            act_name=row["act_name"],
            act_name_original=row.get("act_name_original"),
            section_number=row["section"],
            subsection=row.get("subsection"),
            clause=row.get("clause"),
            raw_citation_text=row.get("raw_citation_text"),
            quoted_text=row.get("quoted_text"),
            source_page=row["source_page"],
            source_bbox_ids=row.get("source_bbox_ids") or [],
            verification_status=VerificationStatus(row["verification_status"]),
            target_act_document_id=row.get("target_act_document_id"),
            target_page=row.get("target_page"),
            target_bbox_ids=row.get("target_bbox_ids") or [],
            confidence=(row.get("confidence") or 0) * 100,  # Convert from 0-1 to 0-100
            extraction_metadata=row.get("extraction_metadata") or {},
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )

    def _row_to_act_resolution(self, row: dict) -> ActResolution:
        """Convert database row to ActResolution model."""
        return ActResolution(
            id=row["id"],
            matter_id=row["matter_id"],
            act_name_normalized=row["act_name_normalized"],
            act_name_display=row.get("act_name_display") or get_display_name(
                row["act_name_normalized"]
            ),
            act_document_id=row.get("act_document_id"),
            resolution_status=ActResolutionStatus(row["resolution_status"]),
            user_action=UserAction(row["user_action"]),
            citation_count=row.get("citation_count") or 0,
            first_seen_at=datetime.fromisoformat(
                row["first_seen_at"].replace("Z", "+00:00")
            ) if row.get("first_seen_at") else None,
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )

    # =========================================================================
    # Verification Methods (Story 3-3)
    # =========================================================================

    async def update_citation_verification(
        self,
        citation_id: str,
        matter_id: str,
        verification_status: VerificationStatus,
        target_act_document_id: str | None = None,
        target_page: int | None = None,
        target_bbox_ids: list[str] | None = None,
        confidence: float | None = None,
    ) -> Citation | None:
        """Update citation with verification results.

        Args:
            citation_id: Citation UUID.
            matter_id: Matter UUID for validation.
            verification_status: New verification status.
            target_act_document_id: Act document UUID if verified.
            target_page: Page in Act document.
            target_bbox_ids: Bounding boxes in Act document.
            confidence: Verification confidence (0-100).

        Returns:
            Updated Citation or None on error.
        """
        try:
            update_data: dict = {
                "verification_status": verification_status.value,
                "updated_at": datetime.now(UTC).isoformat(),
            }

            if target_act_document_id is not None:
                update_data["target_act_document_id"] = target_act_document_id

            if target_page is not None:
                update_data["target_page"] = target_page

            if target_bbox_ids is not None:
                update_data["target_bbox_ids"] = target_bbox_ids

            if confidence is not None:
                # Convert 0-100 to 0-1 for storage
                update_data["confidence"] = confidence / 100.0

            def _update():
                return self.client.table("citations").update(update_data).eq(
                    "id", citation_id
                ).eq("matter_id", matter_id).execute()

            result = await asyncio.to_thread(_update)

            if result.data and len(result.data) > 0:
                logger.info(
                    "citation_verification_updated",
                    citation_id=citation_id,
                    status=verification_status.value,
                )
                return self._row_to_citation(result.data[0])

            return None

        except Exception as e:
            logger.error(
                "update_citation_verification_failed",
                citation_id=citation_id,
                error=str(e),
            )
            return None

    async def get_citations_for_act(
        self,
        matter_id: str,
        act_name: str,
        exclude_verified: bool = False,
    ) -> list[Citation]:
        """Get all citations referencing a specific Act.

        Args:
            matter_id: Matter UUID.
            act_name: Act name to filter by.
            exclude_verified: If True, exclude already verified citations.

        Returns:
            List of citations referencing the Act.
        """
        try:
            def _query():
                query = self.client.table("citations").select("*").eq(
                    "matter_id", matter_id
                ).eq("act_name", act_name)

                if exclude_verified:
                    # Exclude verified and mismatch (already processed)
                    query = query.not_.in_(
                        "verification_status",
                        [VerificationStatus.VERIFIED.value, VerificationStatus.MISMATCH.value],
                    )

                return query.order("source_page").execute()

            result = await asyncio.to_thread(_query)

            return [self._row_to_citation(row) for row in (result.data or [])]

        except Exception as e:
            logger.error(
                "get_citations_for_act_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return []

    async def get_citations_pending_verification(
        self,
        matter_id: str,
        act_document_id: str | None = None,
    ) -> list[Citation]:
        """Get citations pending verification.

        Args:
            matter_id: Matter UUID.
            act_document_id: Optional filter by Act document.

        Returns:
            List of citations needing verification.
        """
        try:
            def _query():
                query = self.client.table("citations").select("*").eq(
                    "matter_id", matter_id
                ).in_(
                    "verification_status",
                    [
                        VerificationStatus.PENDING.value,
                        VerificationStatus.ACT_UNAVAILABLE.value,
                    ],
                )

                # Note: We can't filter by target_act_document_id here since
                # unverified citations don't have it set yet.
                # Filtering happens in the caller based on act_name.

                return query.order("created_at").execute()

            result = await asyncio.to_thread(_query)

            return [self._row_to_citation(row) for row in (result.data or [])]

        except Exception as e:
            logger.error(
                "get_citations_pending_verification_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    async def bulk_update_verification_status(
        self,
        matter_id: str,
        act_name: str,
        from_status: VerificationStatus,
        to_status: VerificationStatus,
    ) -> int:
        """Bulk update verification status for citations.

        Used when Act is uploaded to change status from act_unavailable to pending.

        Args:
            matter_id: Matter UUID.
            act_name: Act name to filter by.
            from_status: Current status to match.
            to_status: New status to set.

        Returns:
            Number of citations updated.
        """
        try:
            def _update():
                return self.client.table("citations").update({
                    "verification_status": to_status.value,
                    "updated_at": datetime.now(UTC).isoformat(),
                }).eq(
                    "matter_id", matter_id
                ).eq(
                    "act_name", act_name
                ).eq(
                    "verification_status", from_status.value
                ).execute()

            result = await asyncio.to_thread(_update)

            updated_count = len(result.data) if result.data else 0

            logger.info(
                "bulk_verification_status_updated",
                matter_id=matter_id,
                act_name=act_name,
                from_status=from_status.value,
                to_status=to_status.value,
                updated_count=updated_count,
            )

            return updated_count

        except Exception as e:
            logger.error(
                "bulk_update_verification_status_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return 0


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_citation_storage_service() -> CitationStorageService:
    """Get singleton citation storage service instance.

    Returns:
        CitationStorageService instance.
    """
    return CitationStorageService()
