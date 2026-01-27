"""Export service for document generation orchestration.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

This service orchestrates the export generation process:
- Creates export records in database
- Fetches section content from various sources
- Delegates to format-specific generators
- Handles file storage and download URLs

Implements:
- AC #3: Generate PDF, Word, and PowerPoint documents
- AC #4: Include verification status in exports
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.models.export import (
    ExportFormat,
    ExportGenerationResponse,
    ExportRecord,
    ExportRequest,
    ExportSectionEdit,
    ExportStatus,
    VerificationSummaryForExport,
)

if TYPE_CHECKING:
    from supabase import Client

logger = structlog.get_logger(__name__)


class ExportServiceError(Exception):
    """Export service error with code and message."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ExportService:
    """Service for generating document exports.

    Story 12-3: Main orchestration service for export generation.

    Example:
        >>> service = get_export_service()
        >>> result = await service.generate_export(
        ...     matter_id="uuid",
        ...     request=ExportRequest(format=ExportFormat.PDF, sections=["executive-summary"]),
        ...     user_id="user-uuid",
        ...     supabase=client,
        ... )
    """

    def __init__(self) -> None:
        """Initialize export service."""
        logger.info("export_service_initialized")

    async def generate_export(
        self,
        matter_id: str,
        request: ExportRequest,
        user_id: str,
        user_email: str,
        user_name: str,
        supabase: Client,
    ) -> ExportGenerationResponse:
        """Generate an export document.

        Story 12-3: AC #3, #4 - Generate document with verification status.

        Args:
            matter_id: Matter UUID.
            request: Export request with format and sections.
            user_id: User UUID generating the export.
            user_email: User email for verification summary.
            user_name: User name for verification summary.
            supabase: Supabase client.

        Returns:
            ExportGenerationResponse with export ID and status.

        Raises:
            ExportServiceError: If export generation fails.
        """
        export_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Get matter name for filename
        matter_name = await self._get_matter_name(matter_id, supabase)
        date_str = now.strftime("%Y-%m-%d")
        extension = self._get_file_extension(request.format)
        file_name = f"{matter_name}-Export-{date_str}.{extension}"

        logger.info(
            "export_generation_started",
            export_id=export_id,
            matter_id=matter_id,
            format=request.format.value,
            sections=request.sections,
            user_id=user_id,
        )

        try:
            # Get verification summary
            verification_summary = await self._get_verification_summary(
                matter_id,
                user_name,
                user_email,
                now,
                supabase,
            )

            # Fetch section content
            section_content = await self._fetch_section_content(
                matter_id,
                request.sections,
                request.section_edits,
                supabase,
            )

            # Generate document based on format
            # Story 4.3: Pass matter_id for certification
            file_bytes = await self._generate_document(
                request.format,
                matter_name,
                matter_id,
                section_content,
                verification_summary,
                request.include_verification_status,
            )

            # Upload to storage
            file_path = f"exports/{matter_id}/{export_id}/{file_name}"
            download_url = await self._upload_file(
                file_path,
                file_bytes,
                self._get_content_type(request.format),
                supabase,
            )

            # Create export record
            await self._create_export_record(
                export_id=export_id,
                matter_id=matter_id,
                request=request,
                file_path=file_path,
                file_name=file_name,
                download_url=download_url,
                verification_summary=verification_summary,
                user_id=user_id,
                created_at=now,
                supabase=supabase,
            )

            logger.info(
                "export_generation_completed",
                export_id=export_id,
                matter_id=matter_id,
                file_name=file_name,
            )

            return ExportGenerationResponse(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                download_url=download_url,
                file_name=file_name,
                message="Export generated successfully.",
            )

        except ExportServiceError:
            # Re-raise our own errors as-is
            raise
        except Exception as e:
            logger.error(
                "export_generation_failed",
                export_id=export_id,
                matter_id=matter_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Issue #9 fix: Sanitize error message - don't expose internal details
            raise ExportServiceError(
                code="EXPORT_GENERATION_FAILED",
                message="Failed to generate export. Please try again or contact support.",
            ) from e

    async def _get_matter_name(self, matter_id: str, supabase: Client) -> str:
        """Get matter name for filename generation."""
        try:
            result = supabase.table("matters").select("name").eq("id", matter_id).single().execute()
            name = result.data.get("name", "Matter")
            # Sanitize for filename
            return "".join(c for c in name if c.isalnum() or c in " -_")[:50].strip() or "Matter"
        except Exception:
            return "Matter"

    async def _get_verification_summary(
        self,
        matter_id: str,
        user_name: str,
        user_email: str,
        export_date: datetime,
        supabase: Client,
    ) -> VerificationSummaryForExport:
        """Get verification summary for export footer."""
        try:
            result = supabase.table("finding_verifications").select(
                "decision"
            ).eq("matter_id", matter_id).execute()

            total = len(result.data)
            verified = sum(1 for r in result.data if r["decision"] == "approved")
            pending = sum(1 for r in result.data if r["decision"] == "pending")

            return VerificationSummaryForExport(
                export_date=export_date,
                total_findings=total,
                verified_count=verified,
                pending_count=pending,
                warnings_dismissed=0,  # Updated by caller if applicable
                exported_by_name=user_name,
                exported_by_email=user_email,
            )
        except Exception:
            return VerificationSummaryForExport(
                export_date=export_date,
                total_findings=0,
                verified_count=0,
                pending_count=0,
                warnings_dismissed=0,
                exported_by_name=user_name,
                exported_by_email=user_email,
            )

    async def _fetch_section_content(
        self,
        matter_id: str,
        sections: list[str],
        section_edits: dict[str, ExportSectionEdit],
        supabase: Client,
    ) -> dict[str, dict]:
        """Fetch content for each section from database."""
        content: dict[str, dict] = {}

        for section_id in sections:
            edit = section_edits.get(section_id)

            match section_id:
                case "executive-summary":
                    content[section_id] = await self._fetch_summary_content(
                        matter_id, edit, supabase
                    )
                case "timeline":
                    content[section_id] = await self._fetch_timeline_content(
                        matter_id, edit, supabase
                    )
                case "entities":
                    content[section_id] = await self._fetch_entities_content(
                        matter_id, edit, supabase
                    )
                case "citations":
                    content[section_id] = await self._fetch_citations_content(
                        matter_id, edit, supabase
                    )
                case "key-findings":
                    content[section_id] = await self._fetch_findings_content(
                        matter_id, edit, supabase
                    )
                case "contradictions":
                    content[section_id] = await self._fetch_contradictions_content(
                        matter_id, edit, supabase
                    )
                case _:
                    content[section_id] = {"items": [], "title": section_id}

        return content

    async def _fetch_summary_content(
        self, matter_id: str, edit: ExportSectionEdit | None, supabase: Client
    ) -> dict:
        """Fetch executive summary content."""
        try:
            result = supabase.table("matter_summaries").select(
                "parties, subject_matter, current_status, key_issues, attention_items"
            ).eq("matter_id", matter_id).single().execute()

            data = result.data or {}

            # Apply text edit if provided
            if edit and edit.text_content is not None:
                return {"custom_content": edit.text_content, "title": "Executive Summary"}

            return {
                "title": "Executive Summary",
                "parties": data.get("parties", []),
                "subject_matter": data.get("subject_matter", {}),
                "current_status": data.get("current_status", {}),
                "key_issues": data.get("key_issues", []),
                "attention_items": data.get("attention_items", []),
            }
        except Exception:
            return {"title": "Executive Summary", "parties": [], "key_issues": []}

    async def _fetch_timeline_content(
        self, matter_id: str, edit: ExportSectionEdit | None, supabase: Client
    ) -> dict:
        """Fetch timeline events."""
        try:
            # Issue #8 fix: Correct table name is "events", not "timeline_events"
            result = supabase.table("events").select(
                "id, event_date, event_type, description, confidence"
            ).eq("matter_id", matter_id).order(
                "event_date", desc=False
            ).execute()

            events = result.data or []

            # Filter out removed items
            if edit and edit.removed_item_ids:
                events = [e for e in events if e["id"] not in edit.removed_item_ids]

            return {"title": "Timeline", "events": events}
        except Exception:
            return {"title": "Timeline", "events": []}

    async def _fetch_entities_content(
        self, matter_id: str, edit: ExportSectionEdit | None, supabase: Client
    ) -> dict:
        """Fetch entities/MIG data."""
        try:
            result = supabase.table("entities").select(
                "id, canonical_name, entity_type, aliases, mention_count"
            ).eq("matter_id", matter_id).order(
                "mention_count", desc=True
            ).limit(100).execute()

            entities = result.data or []

            # Filter out removed items
            if edit and edit.removed_item_ids:
                entities = [e for e in entities if e["id"] not in edit.removed_item_ids]

            return {"title": "Entities", "entities": entities}
        except Exception:
            return {"title": "Entities", "entities": []}

    async def _fetch_citations_content(
        self, matter_id: str, edit: ExportSectionEdit | None, supabase: Client
    ) -> dict:
        """Fetch citations data."""
        try:
            result = supabase.table("citations").select(
                "id, act_name, section, quote_text, verification_status, confidence"
            ).eq("matter_id", matter_id).order(
                "act_name", desc=False
            ).execute()

            citations = result.data or []

            # Filter out removed items
            if edit and edit.removed_item_ids:
                citations = [c for c in citations if c["id"] not in edit.removed_item_ids]

            return {"title": "Citations", "citations": citations}
        except Exception:
            return {"title": "Citations", "citations": []}

    async def _fetch_findings_content(
        self, matter_id: str, edit: ExportSectionEdit | None, supabase: Client
    ) -> dict:
        """Fetch key findings from verification records."""
        try:
            result = supabase.table("finding_verifications").select(
                "id, finding_type, finding_summary, decision, confidence_before"
            ).eq("matter_id", matter_id).eq(
                "decision", "approved"
            ).execute()

            findings = result.data or []

            # Filter out removed items
            if edit and edit.removed_item_ids:
                findings = [f for f in findings if f["id"] not in edit.removed_item_ids]

            return {"title": "Key Findings", "findings": findings}
        except Exception:
            return {"title": "Key Findings", "findings": []}

    async def _fetch_contradictions_content(
        self, matter_id: str, edit: ExportSectionEdit | None, supabase: Client
    ) -> dict:
        """Fetch contradictions data."""
        try:
            result = supabase.table("contradictions").select(
                "id, statement_a, statement_b, contradiction_type, severity, confidence"
            ).eq("matter_id", matter_id).order(
                "severity", desc=True
            ).execute()

            contradictions = result.data or []

            # Filter out removed items
            if edit and edit.removed_item_ids:
                contradictions = [
                    c for c in contradictions if c["id"] not in edit.removed_item_ids
                ]

            return {"title": "Contradictions", "contradictions": contradictions}
        except Exception:
            return {"title": "Contradictions", "contradictions": []}

    async def _generate_document(
        self,
        format: ExportFormat,
        matter_name: str,
        matter_id: str,
        section_content: dict[str, dict],
        verification_summary: VerificationSummaryForExport,
        include_verification: bool,
        include_certification: bool = True,
    ) -> bytes:
        """Generate document in the specified format.

        Story 4.3: Updated to include court-ready certification.
        """
        # Import generators here to avoid circular imports
        from app.services.export.docx_generator import DocxGenerator
        from app.services.export.pdf_generator import PDFGenerator
        from app.services.export.pptx_generator import PptxGenerator

        # Story 4.3: Generate certification for PDF exports
        certification = None
        if include_certification and format == ExportFormat.PDF:
            certification = await self._generate_certification(
                matter_id=matter_id,
                matter_name=matter_name,
                verification_summary=verification_summary,
            )

        match format:
            case ExportFormat.PDF:
                generator = PDFGenerator()
                return generator.generate(
                    matter_name,
                    section_content,
                    verification_summary if include_verification else None,
                    certification=certification,
                )
            case ExportFormat.WORD:
                generator = DocxGenerator()
                return generator.generate(
                    matter_name,
                    section_content,
                    verification_summary if include_verification else None,
                )
            case ExportFormat.POWERPOINT:
                generator = PptxGenerator()
                return generator.generate(
                    matter_name,
                    section_content,
                    verification_summary if include_verification else None,
                )

    async def _generate_certification(
        self,
        matter_id: str,
        matter_name: str,
        verification_summary: VerificationSummaryForExport,
    ):
        """Generate court-ready certification.

        Story 4.3: Creates certification with verification status snapshot.
        """
        from app.services.export.court_certification import (
            VerificationStatusSnapshot,
            get_court_certification_service,
        )

        # Create verification status snapshot
        total = verification_summary.total_findings
        verified = verification_summary.verified_count
        pending = verification_summary.pending_count
        verification_rate = (verified / total * 100) if total > 0 else 0.0

        status_snapshot = VerificationStatusSnapshot(
            total_findings=total,
            verified_count=verified,
            pending_count=pending,
            rejected_count=0,  # Not tracked in current model
            flagged_count=0,  # Not tracked in current model
            verification_rate=verification_rate,
        )

        service = get_court_certification_service()

        # Note: We create a placeholder certificate here
        # The actual hash will be computed on the final content
        # For now, we use an empty placeholder that will be filled in
        # by the calling code after content generation
        return await service.create_certificate(
            content_bytes=b"",  # Placeholder - computed later
            matter_id=matter_id,
            matter_name=matter_name,
            user_name=verification_summary.exported_by_name,
            user_email=verification_summary.exported_by_email,
            user_role="Attorney",  # Default role
            verification_status=status_snapshot,
        )

    async def _upload_file(
        self,
        file_path: str,
        file_bytes: bytes,
        content_type: str,
        supabase: Client,
    ) -> str:
        """Upload file to Supabase storage and return signed URL."""
        try:
            # Upload to exports bucket
            supabase.storage.from_("exports").upload(
                file_path,
                file_bytes,
                {"content-type": content_type},
            )

            # Create signed URL (valid for 1 hour)
            result = supabase.storage.from_("exports").create_signed_url(
                file_path,
                expires_in=3600,
            )

            return result.get("signedURL", result.get("signedUrl", ""))
        except Exception as e:
            logger.error("file_upload_failed", file_path=file_path, error=str(e))
            raise ExportServiceError(
                code="FILE_UPLOAD_FAILED",
                message=f"Failed to upload export file: {e}",
            ) from e

    async def _create_export_record(
        self,
        export_id: str,
        matter_id: str,
        request: ExportRequest,
        file_path: str,
        file_name: str,
        download_url: str,
        verification_summary: VerificationSummaryForExport,
        user_id: str,
        created_at: datetime,
        supabase: Client,
    ) -> ExportRecord:
        """Create export record in database."""
        try:
            record_data = {
                "id": export_id,
                "matter_id": matter_id,
                "format": request.format.value,
                "status": ExportStatus.COMPLETED.value,
                "file_path": file_path,
                "file_name": file_name,
                "sections_included": request.sections,
                "section_edits": {k: v.model_dump() for k, v in request.section_edits.items()},
                "verification_summary": verification_summary.model_dump(),
                "created_by": user_id,
                "created_at": created_at.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
            }

            supabase.table("exports").insert(record_data).execute()

            return ExportRecord(
                id=export_id,
                matter_id=matter_id,
                format=request.format,
                status=ExportStatus.COMPLETED,
                file_path=file_path,
                download_url=download_url,
                file_name=file_name,
                sections_included=request.sections,
                verification_summary=verification_summary.model_dump(),
                created_by=user_id,
                created_at=created_at,
                completed_at=datetime.now(UTC),
            )
        except Exception as e:
            # Issue #4 fix: Graceful handling when exports table doesn't exist
            # Log appropriately based on error type (table missing vs other errors)
            error_msg = str(e).lower()
            if "relation" in error_msg and "does not exist" in error_msg:
                logger.warning(
                    "exports_table_not_found",
                    export_id=export_id,
                    message="Exports table not yet created. Export succeeds but history not recorded.",
                )
            else:
                logger.error("export_record_creation_failed", export_id=export_id, error=str(e))
            # Don't fail the export if record creation fails
            return ExportRecord(
                id=export_id,
                matter_id=matter_id,
                format=request.format,
                status=ExportStatus.COMPLETED,
                file_path=file_path,
                download_url=download_url,
                file_name=file_name,
                sections_included=request.sections,
                verification_summary=verification_summary.model_dump(),
                created_by=user_id,
                created_at=created_at,
                completed_at=datetime.now(UTC),
            )

    @staticmethod
    def _get_file_extension(format: ExportFormat) -> str:
        """Get file extension for format."""
        match format:
            case ExportFormat.PDF:
                return "pdf"
            case ExportFormat.WORD:
                return "docx"
            case ExportFormat.POWERPOINT:
                return "pptx"

    @staticmethod
    def _get_content_type(format: ExportFormat) -> str:
        """Get MIME type for format."""
        match format:
            case ExportFormat.PDF:
                return "application/pdf"
            case ExportFormat.WORD:
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            case ExportFormat.POWERPOINT:
                return "application/vnd.openxmlformats-officedocument.presentationml.presentation"


# =============================================================================
# Story 12-3: Singleton Factory
# =============================================================================

_export_service: ExportService | None = None
_service_lock = threading.Lock()


def get_export_service() -> ExportService:
    """Get singleton ExportService instance.

    Returns:
        ExportService singleton instance.
    """
    global _export_service  # noqa: PLW0603

    if _export_service is None:
        with _service_lock:
            if _export_service is None:
                _export_service = ExportService()

    return _export_service


def reset_export_service() -> None:
    """Reset singleton for testing."""
    global _export_service  # noqa: PLW0603

    with _service_lock:
        _export_service = None

    logger.debug("export_service_reset")
