"""Export API routes for document generation.

Story 12-3: Export Verification Check and Format Generation
Story 12-4: Partner Executive Summary Export
Epic 12: Export Builder

Provides endpoints for:
- Generating export documents (PDF, Word, PowerPoint)
- Getting export status and download URLs
- Listing export history for a matter
- Quick export: Executive Summary (Story 12.4)

Implements:
- AC #3: Support PDF, Word, and PowerPoint formats
- AC #4: Include verification status in exports
- Story 12.4: One-click executive summary export
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from app.api.deps import (
    MatterMembership,
    MatterRole,
    get_db,
    require_matter_role,
)
from app.models.export import (
    ExportGenerationResponse,
    ExportRequest,
    ExportResponse,
    ExportStatus,
)
from app.services.export import (
    ExecutiveSummaryPDFGenerator,
    ExportService,
    ExportServiceError,
    get_executive_summary_service,
    get_export_service,
)

router = APIRouter(prefix="/matters/{matter_id}/exports", tags=["exports"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Story 12.4: Executive Summary Response Model
# =============================================================================


class ExecutiveSummaryContentSummary(BaseModel):
    """Summary of content included in executive summary.

    Story 12.4: AC #2, #3 - Content counts for response.
    """

    parties_included: int = Field(..., description="Number of parties included")
    dates_included: int = Field(..., description="Number of critical dates included")
    issues_included: int = Field(..., description="Number of verified issues included")
    pending_verification_count: int = Field(
        ..., description="Count of findings pending verification (AC #3)"
    )


class ExecutiveSummaryData(BaseModel):
    """Data payload for executive summary generation.

    Story 12.4: Quick export data with content summary.
    """

    export_id: str = Field(..., description="Export UUID for tracking")
    status: ExportStatus = Field(..., description="Current status (completed)")
    download_url: str | None = Field(None, description="Signed download URL")
    file_name: str = Field(..., description="Generated filename")
    content_summary: ExecutiveSummaryContentSummary = Field(
        ..., description="Summary of content included"
    )


class ExecutiveSummaryResponse(BaseModel):
    """Response for executive summary generation.

    Story 12.4: Quick export response wrapped in data per project-context.md.
    """

    data: ExecutiveSummaryData = Field(..., description="Executive summary data")


def _get_export_service() -> ExportService:
    """Get export service instance.

    Story 12-3: Service factory for dependency injection.
    """
    return get_export_service()


# =============================================================================
# Story 12-3: Generate Export Endpoint (Task 2.6)
# =============================================================================


@router.post(
    "",
    response_model=ExportGenerationResponse,
    responses={
        200: {"description": "Export generation started/completed"},
        400: {"description": "Invalid request"},
        403: {"description": "Export blocked by verification"},
        404: {"description": "Matter not found"},
    },
)
async def generate_export(
    matter_id: str = Path(..., description="Matter UUID"),
    request: ExportRequest = Body(...),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    db=Depends(get_db),
    service: ExportService = Depends(_get_export_service),
) -> ExportGenerationResponse:
    """Generate an export document.

    Story 12-3: AC #3, #4 - Generate document with verification status.

    Supports PDF, Word, and PowerPoint formats.
    The export is generated synchronously and returned with a download URL.

    Args:
        matter_id: Matter UUID.
        request: Export request with format and sections.
        membership: Validated matter membership (editor/owner required).
        db: Supabase client.
        service: Export service.

    Returns:
        ExportGenerationResponse with export ID and download URL.
    """
    logger.info(
        "export_generation_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
        format=request.format.value,
        sections=request.sections,
    )

    # Get user info for verification summary
    try:
        user_result = db.table("profiles").select(
            "email, full_name"
        ).eq("id", membership.user_id).single().execute()

        user_email = user_result.data.get("email", "unknown@example.com") if user_result.data else "unknown@example.com"
        user_name = user_result.data.get("full_name", "Unknown User") if user_result.data else "Unknown User"
    except Exception:
        user_email = "unknown@example.com"
        user_name = "Unknown User"

    try:
        result = await service.generate_export(
            matter_id=matter_id,
            request=request,
            user_id=membership.user_id,
            user_email=user_email,
            user_name=user_name,
            supabase=db,
        )

        logger.info(
            "export_generation_completed",
            matter_id=matter_id,
            export_id=result.export_id,
            file_name=result.file_name,
        )

        return result

    except ExportServiceError as e:
        logger.error(
            "export_generation_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 12-3: Get Export Endpoint (Task 2.7)
# =============================================================================


@router.get(
    "/{export_id}",
    response_model=ExportResponse,
    responses={
        200: {"description": "Export record"},
        404: {"description": "Export not found"},
    },
)
async def get_export(
    matter_id: str = Path(..., description="Matter UUID"),
    export_id: str = Path(..., description="Export UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
) -> ExportResponse:
    """Get an export record by ID.

    Story 12-3: Get export details including download URL.

    Args:
        matter_id: Matter UUID.
        export_id: Export UUID.
        membership: Validated matter membership.
        db: Supabase client.

    Returns:
        ExportResponse with export record.
    """
    try:
        result = db.table("exports").select(
            "*"
        ).eq("id", export_id).eq("matter_id", matter_id).single().execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "EXPORT_NOT_FOUND",
                        "message": f"Export {export_id} not found",
                        "details": {"export_id": export_id},
                    }
                },
            )

        # Generate fresh download URL if file exists
        if result.data.get("file_path"):
            try:
                signed_url = db.storage.from_("exports").create_signed_url(
                    result.data["file_path"],
                    expires_in=3600,
                )
                result.data["download_url"] = signed_url.get("signedURL", signed_url.get("signedUrl", ""))
            except Exception:
                pass

        return ExportResponse(data=result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_export_failed",
            export_id=export_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "GET_EXPORT_FAILED",
                    "message": f"Failed to get export: {e}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 12-3: List Exports Endpoint (Task 2.8)
# =============================================================================


@router.get(
    "",
    responses={
        200: {"description": "List of export records"},
        404: {"description": "Matter not found"},
    },
)
async def list_exports(
    matter_id: str = Path(..., description="Matter UUID"),
    limit: int = 10,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
) -> dict:
    """List export history for a matter.

    Story 12-3: List recent exports for download/reference.

    Args:
        matter_id: Matter UUID.
        limit: Max exports to return (default 10).
        membership: Validated matter membership.
        db: Supabase client.

    Returns:
        List of export records.
    """
    try:
        result = db.table("exports").select(
            "id, format, status, file_name, created_at, completed_at"
        ).eq("matter_id", matter_id).order(
            "created_at", desc=True
        ).limit(limit).execute()

        return {"data": result.data or []}

    except Exception as e:
        logger.error(
            "list_exports_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LIST_EXPORTS_FAILED",
                    "message": f"Failed to list exports: {e}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 12.4: Executive Summary Quick Export Endpoint
# =============================================================================


@router.post(
    "/executive-summary",
    response_model=ExecutiveSummaryResponse,
    responses={
        200: {"description": "Executive summary generated successfully"},
        400: {"description": "Generation failed"},
        403: {"description": "Access denied"},
        404: {"description": "Matter not found"},
    },
)
async def generate_executive_summary(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    db=Depends(get_db),
) -> ExecutiveSummaryResponse:
    """Generate a one-click executive summary PDF.

    Story 12.4: AC #1, #2, #3, #4 - Quick export for partners.

    This endpoint generates a pre-configured 1-2 page PDF containing:
    - Case Overview (2-3 paragraphs)
    - Key Parties (max 10)
    - Critical Dates (max 10)
    - Verified Issues only (with badges)
    - Recommended Actions (max 5)
    - Footer with pending count and workspace link

    No configuration required - just call and download.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership (editor/owner required).
        db: Supabase client.

    Returns:
        ExecutiveSummaryResponse with download URL and content summary.
    """
    logger.info(
        "executive_summary_generation_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    try:
        # Extract content
        summary_service = get_executive_summary_service()
        content = await summary_service.extract_content(matter_id, db)

        # Generate PDF
        now = datetime.now(UTC)
        pdf_generator = ExecutiveSummaryPDFGenerator()
        pdf_bytes = pdf_generator.generate(content, now)

        # Generate filename
        date_str = now.strftime("%Y-%m-%d")
        safe_name = "".join(
            c for c in content.matter_name if c.isalnum() or c in " -_"
        )[:50].strip() or "Matter"
        file_name = f"{safe_name}-Executive-Summary-{date_str}.pdf"

        # Upload to storage
        export_id = str(uuid.uuid4())
        file_path = f"exports/{matter_id}/{export_id}/{file_name}"

        try:
            db.storage.from_("exports").upload(
                file_path,
                pdf_bytes,
                {"content-type": "application/pdf"},
            )

            # Create signed URL (valid for 1 hour)
            signed_result = db.storage.from_("exports").create_signed_url(
                file_path,
                expires_in=3600,
            )
            download_url = signed_result.get("signedURL", signed_result.get("signedUrl", ""))

        except Exception as upload_error:
            logger.error(
                "executive_summary_upload_failed",
                matter_id=matter_id,
                error=str(upload_error),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "UPLOAD_FAILED",
                        "message": "Failed to upload executive summary.",
                        "details": {},
                    }
                },
            ) from upload_error

        logger.info(
            "executive_summary_generation_completed",
            matter_id=matter_id,
            export_id=export_id,
            file_name=file_name,
            parties=content.parties_count,
            dates=content.dates_count,
            issues=content.issues_count,
        )

        return ExecutiveSummaryResponse(
            data=ExecutiveSummaryData(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                download_url=download_url,
                file_name=file_name,
                content_summary=ExecutiveSummaryContentSummary(
                    parties_included=content.parties_count,
                    dates_included=content.dates_count,
                    issues_included=content.issues_count,
                    pending_verification_count=content.pending_verification_count,
                ),
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "executive_summary_generation_failed",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "GENERATION_FAILED",
                    "message": "Failed to generate executive summary. Please try again.",
                    "details": {},
                }
            },
        ) from e
