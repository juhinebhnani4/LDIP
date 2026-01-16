"""Export API routes for document generation.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

Provides endpoints for:
- Generating export documents (PDF, Word, PowerPoint)
- Getting export status and download URLs
- Listing export history for a matter

Implements:
- AC #3: Support PDF, Word, and PowerPoint formats
- AC #4: Include verification status in exports
"""

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

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
)
from app.services.export import (
    ExportService,
    ExportServiceError,
    get_export_service,
)

router = APIRouter(prefix="/matters/{matter_id}/exports", tags=["exports"])
logger = structlog.get_logger(__name__)


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
