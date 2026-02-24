"""
Sample Case Import API Routes

Story 6.3: Sample Case Import
Endpoints for importing sample documents for new users to explore the product.
"""

import structlog
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)
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

# Sample documents with content to generate minimal PDFs
SAMPLE_DOCUMENTS = [
    {
        "filename": "sample-deposition-transcript.pdf",
        "display_name": "Deposition Transcript - John Smith",
        "document_type": "case_file",
        "content": (
            "DEPOSITION TRANSCRIPT\n"
            "Case No. 2025-CV-1234\n"
            "In the Matter of: Smith v. Acme Corporation\n\n"
            "WITNESS: John Smith\n"
            "DATE: January 15, 2025\n"
            "LOCATION: Conference Room, 123 Legal Ave\n\n"
            "Q: Please state your full name for the record.\n"
            "A: My name is John Michael Smith.\n\n"
            "Q: What is your current occupation?\n"
            "A: I am a Senior Project Manager at TechGlobal Inc.\n\n"
            "Q: How long have you been employed there?\n"
            "A: I have been with TechGlobal for approximately seven years, "
            "since March 2018.\n\n"
            "Q: Can you describe the contract in question?\n"
            "A: Yes. In June 2023, Acme Corporation entered into a service "
            "agreement with TechGlobal for the delivery of a custom software "
            "platform. The contract value was approximately 2.5 million dollars "
            "with a delivery timeline of eighteen months.\n\n"
            "Q: Were there any issues with the deliverables?\n"
            "A: Yes. By December 2023, Acme had missed three critical milestones "
            "outlined in Schedule B of the agreement. The quality assurance "
            "reports showed that over forty percent of the delivered modules "
            "failed acceptance testing.\n\n"
            "Q: What actions did your company take?\n"
            "A: We issued a formal notice of breach on January 5, 2024, "
            "pursuant to Section 12.3 of the agreement.\n\n"
            "[END OF EXCERPT]"
        ),
    },
    {
        "filename": "sample-contract.pdf",
        "display_name": "Contract Agreement - Acme Corp",
        "document_type": "case_file",
        "content": (
            "SERVICE AGREEMENT\n\n"
            "This Service Agreement (the 'Agreement') is entered into as of "
            "June 1, 2023, by and between:\n\n"
            "ACME CORPORATION, a Delaware corporation ('Service Provider'), and\n"
            "TECHGLOBAL INC., a California corporation ('Client').\n\n"
            "1. SCOPE OF SERVICES\n"
            "Service Provider shall design, develop, and deliver a custom "
            "software platform as described in Exhibit A.\n\n"
            "2. COMPENSATION\n"
            "Client shall pay Service Provider a total fee of $2,500,000 "
            "payable in milestones as set forth in Schedule B.\n\n"
            "3. TERM\n"
            "This Agreement shall commence on the Effective Date and continue "
            "for a period of eighteen (18) months unless earlier terminated.\n\n"
            "4. DELIVERY MILESTONES\n"
            "4.1 Phase 1 - Requirements & Design: September 1, 2023\n"
            "4.2 Phase 2 - Core Development: December 15, 2023\n"
            "4.3 Phase 3 - Integration & Testing: March 1, 2024\n"
            "4.4 Phase 4 - Final Delivery: June 1, 2024\n\n"
            "5. ACCEPTANCE CRITERIA\n"
            "All deliverables must pass acceptance testing as defined in "
            "Schedule C with a minimum 95% pass rate.\n\n"
            "12. BREACH AND REMEDIES\n"
            "12.3 In the event of a material breach, the non-breaching party "
            "shall provide written notice specifying the breach and allowing "
            "30 days for cure.\n\n"
            "IN WITNESS WHEREOF, the parties have executed this Agreement.\n\n"
            "ACME CORPORATION          TECHGLOBAL INC.\n"
            "By: _______________       By: _______________\n"
            "Name: Robert Chen         Name: Sarah Johnson\n"
            "Title: CEO                Title: CTO"
        ),
    },
    {
        "filename": "sample-correspondence.pdf",
        "display_name": "Email Correspondence - Discovery",
        "document_type": "case_file",
        "content": (
            "EMAIL CORRESPONDENCE - PRIVILEGED AND CONFIDENTIAL\n\n"
            "---\n"
            "From: Sarah Johnson <sjohnson@techglobal.com>\n"
            "To: Robert Chen <rchen@acmecorp.com>\n"
            "Date: November 12, 2023\n"
            "Subject: Milestone 2 Delay Concerns\n\n"
            "Dear Robert,\n\n"
            "I am writing to express our concern regarding the Phase 2 "
            "deliverables. As of today, we have not received the core "
            "development modules that were due on October 15th.\n\n"
            "Our technical team reports that only 3 of the 8 required modules "
            "have been delivered, and of those, two failed initial QA review.\n\n"
            "Please provide an updated timeline at your earliest convenience.\n\n"
            "Best regards,\nSarah Johnson, CTO\n\n"
            "---\n"
            "From: Robert Chen <rchen@acmecorp.com>\n"
            "To: Sarah Johnson <sjohnson@techglobal.com>\n"
            "Date: November 15, 2023\n"
            "Subject: RE: Milestone 2 Delay Concerns\n\n"
            "Dear Sarah,\n\n"
            "Thank you for your patience. We have experienced some staffing "
            "challenges that have impacted our delivery timeline. I assure you "
            "we are committed to the project.\n\n"
            "We expect to deliver the remaining modules by December 1st.\n\n"
            "Regards,\nRobert Chen, CEO\n\n"
            "---\n"
            "From: Sarah Johnson <sjohnson@techglobal.com>\n"
            "To: Legal Team <legal@techglobal.com>\n"
            "Date: January 3, 2024\n"
            "Subject: FW: Contract Breach - Acme Corporation\n\n"
            "Team,\n\n"
            "Please find below the correspondence trail with Acme. As of "
            "today, they have missed all Phase 2 milestones and the delivered "
            "modules have a 40% failure rate in acceptance testing.\n\n"
            "Please prepare a formal notice of breach per Section 12.3.\n\n"
            "Sarah Johnson"
        ),
    },
]

STORAGE_BUCKET = "documents"


def _generate_minimal_pdf(text_content: str) -> bytes:
    """Generate a minimal valid PDF with text content.

    Creates a single-page PDF using raw PDF syntax.
    No external dependencies required.
    """
    # Encode text for PDF (escape special chars)
    safe_text = (
        text_content
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )

    # Split into lines and create PDF text commands
    lines = safe_text.split("\n")
    text_commands = []
    y_pos = 750  # Start near top
    for line in lines:
        if y_pos < 50:
            break  # Stop near bottom of page
        text_commands.append(f"BT /F1 10 Tf {50} {y_pos} Td ({line}) Tj ET")
        y_pos -= 14  # Line spacing

    stream_content = "\n".join(text_commands)
    stream_bytes = stream_content.encode("latin-1", errors="replace")

    # Build PDF structure
    pdf_parts = []
    offsets = []

    # Header
    pdf_parts.append(b"%PDF-1.4\n")

    # Object 1: Catalog
    offsets.append(len(b"".join(pdf_parts)))
    pdf_parts.append(
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    )

    # Object 2: Pages
    offsets.append(len(b"".join(pdf_parts)))
    pdf_parts.append(
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    )

    # Object 3: Page
    offsets.append(len(b"".join(pdf_parts)))
    pdf_parts.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )

    # Object 4: Content stream
    offsets.append(len(b"".join(pdf_parts)))
    stream_length = len(stream_bytes)
    pdf_parts.append(
        f"4 0 obj\n<< /Length {stream_length} >>\nstream\n".encode()
    )
    pdf_parts.append(stream_bytes)
    pdf_parts.append(b"\nendstream\nendobj\n")

    # Object 5: Font
    offsets.append(len(b"".join(pdf_parts)))
    pdf_parts.append(
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 "
        b"/BaseFont /Helvetica >>\nendobj\n"
    )

    # Cross-reference table
    xref_offset = len(b"".join(pdf_parts))
    xref = f"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n"
    pdf_parts.append(xref.encode())

    # Trailer
    pdf_parts.append(
        f"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )

    return b"".join(pdf_parts)


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
    Generates minimal sample PDFs and uploads them to Supabase Storage.

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

    # Check if user already has a sample matter (via matter_attorneys; matters has no created_by)
    ma_result = (
        supabase.table("matter_attorneys")
        .select("matter_id, matters(id, title, deleted_at)")
        .eq("user_id", user_id)
        .execute()
    )
    existing_sample = [
        row for row in (ma_result.data or [])
        if row.get("matters")
        and (row["matters"].get("title") or "").find("Sample Case") >= 0
        and not row["matters"].get("deleted_at")
    ]

    if existing_sample:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a sample case. Delete it first to import again.",
        )

    # Create the sample matter
    matter_id = str(uuid4())

    try:
        # Insert matter (matters table has no created_by; creator is set via matter_attorneys)
        matter_result = (
            supabase.table("matters")
            .insert(
                {
                    "id": matter_id,
                    "title": SAMPLE_MATTER_TITLE,
                    "description": SAMPLE_MATTER_DESCRIPTION,
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

        # Add user as owner (table is matter_attorneys, not matter_members)
        supabase.table("matter_attorneys").insert(
            {
                "matter_id": matter_id,
                "user_id": user_id,
                "role": "owner",
                "invited_by": user_id,
            }
        ).execute()

        # Generate and upload sample documents
        documents_created = 0

        for sample_doc in SAMPLE_DOCUMENTS:
            doc_id = str(uuid4())
            filename = sample_doc["filename"]

            # Generate a minimal PDF with sample content
            pdf_bytes = _generate_minimal_pdf(sample_doc["content"])

            # Upload to Supabase Storage using standard path pattern:
            # {matter_id}/uploads/{filename}
            storage_path = f"{matter_id}/uploads/{filename}"

            try:
                supabase.storage.from_(STORAGE_BUCKET).upload(
                    path=storage_path,
                    file=pdf_bytes,
                    file_options={"content-type": "application/pdf"},
                )
                logger.info(
                    "sample_pdf_uploaded",
                    matter_id=matter_id,
                    storage_path=storage_path,
                    file_size=len(pdf_bytes),
                )
            except Exception as upload_err:
                logger.warning(
                    "sample_pdf_upload_failed",
                    matter_id=matter_id,
                    filename=filename,
                    error=str(upload_err),
                )
                # Continue creating the record even if upload fails
                # The document will show as pending with no viewable file

            # Create document record
            supabase.table("documents").insert(
                {
                    "id": doc_id,
                    "matter_id": matter_id,
                    "filename": sample_doc["display_name"],
                    "storage_path": storage_path,
                    "file_size": len(pdf_bytes),
                    "document_type": sample_doc["document_type"],
                    "status": "pending",
                    "uploaded_by": user_id,
                }
            ).execute()

            documents_created += 1

            # Queue document for processing (if Celery is available)
            try:
                from app.workers.tasks.document_tasks import process_document

                process_document.delay(doc_id)
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
        # Cleanup on failure (matter_attorneys CASCADE when matter deleted; delete matter last)
        try:
            supabase.table("matter_attorneys").delete().eq("matter_id", matter_id).execute()
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

    # Check for sample matter via matter_attorneys (matters has no created_by)
    ma_result = (
        supabase.table("matter_attorneys")
        .select("matter_id, matters(id, title, deleted_at)")
        .eq("user_id", user_id)
        .execute()
    )
    sample_rows = [
        row for row in (ma_result.data or [])
        if row.get("matters")
        and (row["matters"].get("title") or "").find("Sample Case") >= 0
        and not row["matters"].get("deleted_at")
    ]

    return {
        "hasSampleCase": len(sample_rows) > 0,
        "sampleMatterId": sample_rows[0]["matter_id"] if sample_rows else None,
    }
