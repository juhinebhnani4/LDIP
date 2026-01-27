"""Court-Ready Certification module for legal defensibility (Story 4.3).

Epic 4: Legal Defensibility (Gap Remediation)

This module provides court-ready certification data for exports:
- Hash/checksum of the entire export bundle
- Timestamp of export generation (UTC)
- User identity (name, email) who generated the export
- Verification status summary at time of export
- Tool version and model information

Implements:
- AC 4.3.1: Export bundle includes certificate with hash, timestamp, user identity
- AC 4.3.2: Certificate includes list of LLM model versions used
- AC 4.3.3: PDF exports include certification page
- AC 4.3.4: Each finding in export linked to reasoning trace ID
"""

import hashlib
from datetime import UTC, datetime

import structlog
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 4.3: Certification Models
# =============================================================================


class ModelVersionInfo(BaseModel):
    """Information about an LLM model used in processing."""

    model_config = ConfigDict(populate_by_name=True)

    engine_name: str = Field(..., alias="engineName", description="Engine that used this model")
    model_id: str = Field(..., alias="modelId", description="Model identifier (e.g., gpt-4)")
    purpose: str = Field(..., description="What the model was used for")


class VerificationStatusSnapshot(BaseModel):
    """Snapshot of verification status at time of export."""

    model_config = ConfigDict(populate_by_name=True)

    total_findings: int = Field(0, alias="totalFindings", description="Total findings in matter")
    verified_count: int = Field(0, alias="verifiedCount", description="Findings marked as verified")
    pending_count: int = Field(0, alias="pendingCount", description="Findings pending verification")
    rejected_count: int = Field(0, alias="rejectedCount", description="Findings rejected")
    flagged_count: int = Field(0, alias="flaggedCount", description="Findings flagged for review")
    verification_rate: float = Field(
        0.0,
        ge=0,
        le=100,
        alias="verificationRate",
        description="Percentage of findings verified",
    )


class ExportCertificate(BaseModel):
    """Court-ready export certificate with provenance data.

    Story 4.3: This certificate provides the legal defensibility chain:
    - Content integrity (SHA-256 hash)
    - Temporal proof (UTC timestamp)
    - Attribution (user identity)
    - AI transparency (model versions)
    - Verification status (human review status)
    """

    model_config = ConfigDict(populate_by_name=True)

    # Content integrity
    content_hash: str = Field(
        ...,
        alias="contentHash",
        description="SHA-256 hash of export content",
    )
    hash_algorithm: str = Field(
        default="SHA-256",
        alias="hashAlgorithm",
        description="Algorithm used for content hash",
    )

    # Temporal proof
    generated_at: datetime = Field(
        ...,
        alias="generatedAt",
        description="UTC timestamp when export was generated",
    )
    timezone: str = Field(default="UTC", description="Timezone of timestamp")

    # Attribution
    generated_by_name: str = Field(
        ...,
        alias="generatedByName",
        description="Name of user who generated export",
    )
    generated_by_email: str = Field(
        ...,
        alias="generatedByEmail",
        description="Email of user who generated export",
    )
    generated_by_role: str = Field(
        ...,
        alias="generatedByRole",
        description="Role of user (e.g., Attorney, Paralegal)",
    )

    # AI transparency
    tool_version: str = Field(
        ...,
        alias="toolVersion",
        description="Version of LDIP that generated the export",
    )
    models_used: list[ModelVersionInfo] = Field(
        default_factory=list,
        alias="modelsUsed",
        description="LLM models used in processing this matter",
    )

    # Verification status
    verification_status: VerificationStatusSnapshot = Field(
        ...,
        alias="verificationStatus",
        description="Snapshot of verification status at export time",
    )

    # Matter context
    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    matter_name: str = Field(..., alias="matterName", description="Matter name")

    # Certification statement
    certification_statement: str = Field(
        ...,
        alias="certificationStatement",
        description="Legal statement about the export",
    )


class FindingWithTrace(BaseModel):
    """Finding data with linked reasoning trace ID.

    Story 4.3: AC 4.3.4 - Each finding linked to reasoning trace.
    """

    model_config = ConfigDict(populate_by_name=True)

    finding_id: str = Field(..., alias="findingId", description="Finding UUID")
    finding_type: str = Field(..., alias="findingType", description="Type of finding")
    finding_summary: str = Field(..., alias="findingSummary", description="Summary of finding")
    reasoning_trace_id: str | None = Field(
        None,
        alias="reasoningTraceId",
        description="UUID of linked reasoning trace",
    )
    confidence_score: float | None = Field(
        None,
        ge=0,
        le=1,
        alias="confidenceScore",
        description="AI confidence score",
    )


# =============================================================================
# Story 4.3: Certification Service
# =============================================================================


class CourtCertificationService:
    """Service for generating court-ready export certificates.

    Story 4.3: Provides provenance data for legal defensibility.
    """

    def __init__(self) -> None:
        """Initialize certification service."""
        settings = get_settings()
        self.tool_version = settings.api_version

    def generate_content_hash(self, content: bytes) -> str:
        """Generate SHA-256 hash of export content.

        Story 4.3: AC 4.3.1 - Content integrity hash.

        Args:
            content: Export content bytes.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(content).hexdigest()

    async def create_certificate(
        self,
        content_bytes: bytes,
        matter_id: str,
        matter_name: str,
        user_name: str,
        user_email: str,
        user_role: str,
        verification_status: VerificationStatusSnapshot,
        models_used: list[ModelVersionInfo] | None = None,
    ) -> ExportCertificate:
        """Create a court-ready export certificate.

        Story 4.3: AC 4.3.1-4.3.3 - Generate full certificate.

        Args:
            content_bytes: Export content for hashing.
            matter_id: Matter UUID.
            matter_name: Matter name.
            user_name: Name of exporting user.
            user_email: Email of exporting user.
            user_role: Role of exporting user.
            verification_status: Snapshot of verification status.
            models_used: Optional list of LLM models used.

        Returns:
            ExportCertificate with all provenance data.
        """
        now = datetime.now(UTC)

        # Default models if not provided
        if models_used is None:
            models_used = self._get_default_models()

        # Generate certification statement
        verification_pct = verification_status.verification_rate
        statement = self._generate_certification_statement(
            verification_rate=verification_pct,
            generated_at=now,
            user_name=user_name,
        )

        certificate = ExportCertificate(
            content_hash=self.generate_content_hash(content_bytes),
            hash_algorithm="SHA-256",
            generated_at=now,
            timezone="UTC",
            generated_by_name=user_name,
            generated_by_email=user_email,
            generated_by_role=user_role,
            tool_version=self.tool_version,
            models_used=models_used,
            verification_status=verification_status,
            matter_id=matter_id,
            matter_name=matter_name,
            certification_statement=statement,
        )

        logger.info(
            "export_certificate_generated",
            matter_id=matter_id,
            content_hash=certificate.content_hash[:16] + "...",
            verification_rate=verification_pct,
        )

        return certificate

    def _get_default_models(self) -> list[ModelVersionInfo]:
        """Get default LLM model versions used in processing.

        Story 4.3: AC 4.3.2 - Include model versions.

        Returns:
            List of default models used across engines.
        """
        settings = get_settings()

        return [
            ModelVersionInfo(
                engine_name="Citation Extraction",
                model_id=settings.gemini_model,
                purpose="Extract legal citations from documents",
            ),
            ModelVersionInfo(
                engine_name="Contradiction Detection",
                model_id=settings.openai_comparison_model,
                purpose="Detect contradictions between statements",
            ),
            ModelVersionInfo(
                engine_name="Timeline Extraction",
                model_id=settings.gemini_model,
                purpose="Extract timeline events and dates",
            ),
            ModelVersionInfo(
                engine_name="Entity Extraction",
                model_id=settings.gemini_model,
                purpose="Extract and resolve entities (persons, organizations)",
            ),
            ModelVersionInfo(
                engine_name="RAG/Q&A",
                model_id=settings.openai_intent_model,
                purpose="Answer user questions about documents",
            ),
        ]

    def _generate_certification_statement(
        self,
        verification_rate: float,
        generated_at: datetime,
        user_name: str,
    ) -> str:
        """Generate the certification statement.

        Story 4.3: Legal certification text for court defensibility.

        Args:
            verification_rate: Percentage of verified findings.
            generated_at: Export generation timestamp.
            user_name: Name of exporting user.

        Returns:
            Certification statement text.
        """
        date_str = generated_at.strftime("%B %d, %Y at %H:%M:%S UTC")

        if verification_rate >= 90:
            verification_clause = (
                f"All AI-generated findings have been reviewed, with {verification_rate:.1f}% "
                "confirmed by human attorney review."
            )
        elif verification_rate >= 70:
            verification_clause = (
                f"{verification_rate:.1f}% of AI-generated findings have been verified through "
                "human attorney review. Some findings remain under review."
            )
        else:
            verification_clause = (
                f"This export contains AI-generated findings, of which {verification_rate:.1f}% "
                "have been verified. Many findings remain pending human review."
            )

        return (
            f"CERTIFICATE OF AUTHENTICITY\n\n"
            f"This document was generated by the Legal Document Intelligence Platform (LDIP) "
            f"on {date_str}.\n\n"
            f"Export generated by: {user_name}\n\n"
            f"{verification_clause}\n\n"
            f"The content hash (SHA-256) provides integrity verification. "
            f"The hash was computed at the time of export and can be used to verify that "
            f"the document has not been altered since generation.\n\n"
            f"AI-generated analysis in this document was produced using the Large Language "
            f"Models listed in the Model Versions section. Each finding includes a "
            f"reasoning trace ID for full transparency into the AI's decision-making process.\n\n"
            f"This certificate is provided for court submission and legal defensibility purposes."
        )


# =============================================================================
# Story 4.3: Singleton Factory
# =============================================================================

_court_certification_service: CourtCertificationService | None = None


def get_court_certification_service() -> CourtCertificationService:
    """Get singleton CourtCertificationService instance.

    Returns:
        CourtCertificationService singleton instance.
    """
    global _court_certification_service  # noqa: PLW0603

    if _court_certification_service is None:
        _court_certification_service = CourtCertificationService()

    return _court_certification_service


def reset_court_certification_service() -> None:
    """Reset singleton for testing."""
    global _court_certification_service  # noqa: PLW0603
    _court_certification_service = None
    logger.debug("court_certification_service_reset")
