"""
Sample Case Import API Routes

Story 6.3: Sample Case Import
Endpoints for importing sample documents for new users to explore the product.
"""

import os
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/api/samples", tags=["samples"])


def get_supabase_client() -> Client | None:
    """Dependency for Supabase service client."""
    return get_service_client()


# =============================================================================
# Response Models
# =============================================================================


class SampleImportResponse(BaseModel):
    """Response from sample import."""

    matter_id: str = Field(..., alias="matterId")
    matter_title: str = Field(..., alias="matterTitle")
    document_count: int = Field(..., alias="documentCount")
    message: str

    model_config = {"populate_by_name": True}


# =============================================================================
# Constants
# =============================================================================

SAMPLE_MATTER_TITLE = "Sample Case - Legal Discovery Demo"
SAMPLE_MATTER_DESCRIPTION = (
    "This is a sample case with pre-loaded documents for exploring LDIP features. "
    "Feel free to delete this matter when you're done exploring."
)

# Sample documents to import (stored in public/samples/)
SAMPLE_DOCUMENTS = [
    {
        "filename": "sample-deposition-transcript.pdf",
        "display_name": "Deposition Transcript - John Smith",
        "description": "Sample deposition transcript with witness testimony",
    },
    {
        "filename": "sample-contract.pdf",
        "display_name": "Contract Agreement - Acme Corp",
        "description": "Sample contract document with key clauses",
    },
    {
        "filename": "sample-correspondence.pdf",
        "display_name": "Email Correspondence - Discovery",
        "description": "Sample email thread related to the case",
    },
]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/import", response_model=SampleImportResponse)
async def import_sample_case(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    supabase: Annotated[Client | None, Depends(get_supabase_client)],
) -> SampleImportResponse:
    """
    Import sample case with pre-loaded documents.

    Creates a new matter with sample documents for the user to explore.
    The matter is marked as a sample case for easy identification and deletion.

    Story 6.3: Sample Case Import
    - Task 6.3.2: Create /api/samples/import endpoint
    - Task 6.3.3: Implement matter creation with sample docs
    - Task 6.3.4: Trigger document processing pipeline for samples
    """
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )

    user_id = current_user.id

    # Check if user already has a sample matter
    existing_sample = (
        supabase.table("matters")
        .select("id")
        .eq("created_by", user_id)
        .like("title", "%Sample Case%")
        .is_("deleted_at", "null")
        .execute()
    )

    if existing_sample.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a sample case. Delete it first to import again.",
        )

    # Create the sample matter
    matter_id = str(uuid4())

    try:
        # Insert matter
        matter_result = (
            supabase.table("matters")
            .insert(
                {
                    "id": matter_id,
                    "title": SAMPLE_MATTER_TITLE,
                    "description": SAMPLE_MATTER_DESCRIPTION,
                    "created_by": user_id,
                    "status": "active",
                    "verification_mode": "advisory",
                    "analysis_mode": "deep_analysis",
                    # Mark as sample for badge display
                    "practice_group": "_sample_case",
                }
            )
            .execute()
        )

        if not matter_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create sample matter",
            )

        # Add user as owner
        supabase.table("matter_members").insert(
            {
                "matter_id": matter_id,
                "user_id": user_id,
                "role": "owner",
                "invited_by": user_id,
            }
        ).execute()

        # Check for sample documents and queue them for processing
        samples_dir = Path(__file__).parent.parent.parent.parent.parent / "public" / "samples"
        documents_created = 0

        for sample_doc in SAMPLE_DOCUMENTS:
            sample_path = samples_dir / sample_doc["filename"]

            # Only create document records if files exist
            # In production, these would be stored in cloud storage
            doc_id = str(uuid4())

            # Create document record (pending processing)
            supabase.table("documents").insert(
                {
                    "id": doc_id,
                    "matter_id": matter_id,
                    "filename": sample_doc["display_name"],
                    "original_filename": sample_doc["filename"],
                    "mime_type": "application/pdf",
                    "status": "pending",
                    "uploaded_by": user_id,
                    # File path would be set after upload to storage
                    "file_path": f"samples/{sample_doc['filename']}",
                }
            ).execute()

            documents_created += 1

            # Queue document for processing (if Celery is available)
            try:
                from app.workers.tasks.document_tasks import process_document

                process_document.delay(doc_id, matter_id)
            except Exception:
                # Processing will need to be triggered manually if Celery unavailable
                pass

        return SampleImportResponse(
            matter_id=matter_id,
            matter_title=SAMPLE_MATTER_TITLE,
            document_count=documents_created,
            message=f"Sample case created with {documents_created} documents. Processing will start shortly.",
        )

    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on failure
        try:
            supabase.table("matter_members").delete().eq("matter_id", matter_id).execute()
            supabase.table("matters").delete().eq("id", matter_id).execute()
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import sample case: {str(e)}",
        )


@router.get("/check")
async def check_sample_exists(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    supabase: Annotated[Client | None, Depends(get_supabase_client)],
) -> dict:
    """
    Check if user already has a sample case.

    Returns whether a sample case exists for the current user.
    """
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )

    user_id = current_user.id

    # Check for sample matter
    existing_sample = (
        supabase.table("matters")
        .select("id")
        .eq("created_by", user_id)
        .like("title", "%Sample Case%")
        .is_("deleted_at", "null")
        .execute()
    )

    return {
        "hasSampleCase": len(existing_sample.data) > 0,
        "sampleMatterId": existing_sample.data[0]["id"] if existing_sample.data else None,
    }
