"""Tests for export generation service.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

Tests for:
- Export eligibility with warning findings
- PDF document generation
- Word document generation
- PowerPoint generation
- Export API endpoints
"""

import pytest
from datetime import datetime, timezone

from app.models.export import (
    ExportFormat,
    ExportRequest,
    ExportSectionEdit,
    ExportStatus,
    VerificationSummaryForExport,
)
from app.models.verification import (
    ExportBlockingFinding,
    ExportEligibilityResult,
    ExportWarningFinding,
)
from app.services.export.pdf_generator import PDFGenerator
from app.services.export.docx_generator import DocxGenerator
from app.services.export.pptx_generator import PptxGenerator


# =============================================================================
# Story 12-3: Export Eligibility Tests (Task 8.1)
# =============================================================================


class TestExportEligibility:
    """Tests for export eligibility with blocking and warning findings."""

    def test_eligible_with_no_findings(self):
        """Test eligibility when there are no findings."""
        result = ExportEligibilityResult(
            eligible=True,
            blocking_findings=[],
            blocking_count=0,
            warning_findings=[],
            warning_count=0,
            message="All required verifications complete. Export is allowed.",
        )

        assert result.eligible is True
        assert result.blocking_count == 0
        assert result.warning_count == 0

    def test_blocked_with_low_confidence_findings(self):
        """Test eligibility blocked by low confidence findings."""
        blocking = ExportBlockingFinding(
            verification_id="ver-1",
            finding_id="find-1",
            finding_type="citation_mismatch",
            finding_summary="Citation does not match source",
            confidence=65.0,
        )

        result = ExportEligibilityResult(
            eligible=False,
            blocking_findings=[blocking],
            blocking_count=1,
            warning_findings=[],
            warning_count=0,
            message="Export blocked: 1 finding(s) require verification",
        )

        assert result.eligible is False
        assert result.blocking_count == 1
        assert result.blocking_findings[0].confidence == 65.0

    def test_eligible_with_warnings(self):
        """Test eligibility allowed with warning findings (70-90% confidence)."""
        warning = ExportWarningFinding(
            verification_id="ver-2",
            finding_id="find-2",
            finding_type="timeline_anomaly",
            finding_summary="Date order seems incorrect",
            confidence=75.0,
        )

        result = ExportEligibilityResult(
            eligible=True,
            blocking_findings=[],
            blocking_count=0,
            warning_findings=[warning],
            warning_count=1,
            message="Export allowed with 1 warning(s).",
        )

        assert result.eligible is True
        assert result.warning_count == 1
        assert result.warning_findings[0].confidence == 75.0


# =============================================================================
# Story 12-3: PDF Generator Tests (Task 8.2)
# =============================================================================


class TestPDFGenerator:
    """Tests for PDF document generation."""

    def test_generate_simple_pdf(self):
        """Test generating a simple PDF with text content."""
        generator = PDFGenerator()

        section_content = {
            "executive-summary": {
                "title": "Executive Summary",
                "parties": [
                    {"role": "Plaintiff", "name": "John Doe"},
                    {"role": "Defendant", "name": "Acme Corp"},
                ],
                "key_issues": [
                    {"title": "Contract Breach", "description": "Failure to deliver goods"},
                ],
            },
        }

        verification = VerificationSummaryForExport(
            export_date=datetime.now(timezone.utc),
            total_findings=5,
            verified_count=3,
            pending_count=2,
            warnings_dismissed=0,
            exported_by_name="Test User",
            exported_by_email="test@example.com",
        )

        pdf_bytes = generator.generate(
            matter_name="Test Matter",
            section_content=section_content,
            verification_summary=verification,
        )

        # Verify PDF header
        assert pdf_bytes.startswith(b"%PDF")
        # Verify PDF footer
        assert b"%%EOF" in pdf_bytes

    def test_generate_pdf_with_timeline(self):
        """Test generating PDF with timeline content."""
        generator = PDFGenerator()

        section_content = {
            "timeline": {
                "title": "Timeline",
                "events": [
                    {
                        "event_date": "2024-01-15",
                        "event_type": "contract_signed",
                        "description": "Contract executed between parties",
                        "confidence": 95,
                    },
                    {
                        "event_date": "2024-02-20",
                        "event_type": "breach",
                        "description": "First missed delivery deadline",
                        "confidence": 88,
                    },
                ],
            },
        }

        pdf_bytes = generator.generate(
            matter_name="Timeline Test",
            section_content=section_content,
        )

        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_pdf_without_verification(self):
        """Test generating PDF without verification summary."""
        generator = PDFGenerator()

        section_content = {
            "entities": {
                "title": "Entities",
                "entities": [
                    {
                        "canonical_name": "John Doe",
                        "entity_type": "person",
                        "mention_count": 15,
                        "aliases": ["J. Doe", "Johnny"],
                    },
                ],
            },
        }

        pdf_bytes = generator.generate(
            matter_name="Entities Test",
            section_content=section_content,
            verification_summary=None,
        )

        assert pdf_bytes.startswith(b"%PDF")


# =============================================================================
# Story 12-3: Word Generator Tests (Task 8.3)
# =============================================================================


class TestDocxGenerator:
    """Tests for Word document generation."""

    def test_generate_simple_docx(self):
        """Test generating a simple Word document."""
        generator = DocxGenerator()

        section_content = {
            "executive-summary": {
                "title": "Executive Summary",
                "parties": [
                    {"role": "Plaintiff", "name": "Jane Smith"},
                ],
                "current_status": {
                    "stage": "Discovery",
                    "description": "Document review in progress",
                },
            },
        }

        docx_bytes = generator.generate(
            matter_name="Test Matter",
            section_content=section_content,
        )

        # Verify ZIP header (DOCX is a ZIP file)
        assert docx_bytes[:4] == b"PK\x03\x04"

    def test_generate_docx_with_citations(self):
        """Test generating Word document with citations."""
        generator = DocxGenerator()

        section_content = {
            "citations": {
                "title": "Citations",
                "citations": [
                    {
                        "act_name": "Contract Act, 1872",
                        "section": "Section 73",
                        "verification_status": "verified",
                        "confidence": 92,
                    },
                    {
                        "act_name": "Sale of Goods Act",
                        "section": "Section 12",
                        "verification_status": "pending",
                        "confidence": 78,
                    },
                ],
            },
        }

        docx_bytes = generator.generate(
            matter_name="Citations Test",
            section_content=section_content,
        )

        assert docx_bytes[:4] == b"PK\x03\x04"


# =============================================================================
# Story 12-3: PowerPoint Generator Tests (Task 8.4)
# =============================================================================


class TestPptxGenerator:
    """Tests for PowerPoint generation."""

    def test_generate_simple_pptx(self):
        """Test generating a simple PowerPoint presentation."""
        generator = PptxGenerator()

        section_content = {
            "executive-summary": {
                "title": "Executive Summary",
                "parties": [
                    {"role": "Plaintiff", "name": "Client Corp"},
                ],
                "key_issues": [
                    {"title": "Main Issue"},
                ],
            },
        }

        pptx_bytes = generator.generate(
            matter_name="Test Presentation",
            section_content=section_content,
        )

        # Verify ZIP header (PPTX is a ZIP file)
        assert pptx_bytes[:4] == b"PK\x03\x04"

    def test_generate_pptx_with_contradictions(self):
        """Test generating PowerPoint with contradictions."""
        generator = PptxGenerator()

        section_content = {
            "contradictions": {
                "title": "Contradictions",
                "contradictions": [
                    {
                        "contradiction_type": "factual",
                        "severity": "high",
                        "statement_a": "Witness stated the event occurred on Monday.",
                        "statement_b": "Documents show the event was on Wednesday.",
                        "confidence": 85,
                    },
                ],
            },
        }

        pptx_bytes = generator.generate(
            matter_name="Contradictions Test",
            section_content=section_content,
        )

        assert pptx_bytes[:4] == b"PK\x03\x04"

    def test_generate_pptx_multiple_slides(self):
        """Test generating PowerPoint with multiple sections creating multiple slides."""
        generator = PptxGenerator()

        # Create content that will generate multiple slides
        section_content = {
            "timeline": {
                "title": "Timeline",
                "events": [
                    {
                        "event_date": f"2024-01-{i:02d}",
                        "event_type": "event",
                        "description": f"Event {i}",
                        "confidence": 90,
                    }
                    for i in range(1, 12)  # 11 events = 3 slides (5 per slide)
                ],
            },
        }

        pptx_bytes = generator.generate(
            matter_name="Multi-slide Test",
            section_content=section_content,
        )

        assert pptx_bytes[:4] == b"PK\x03\x04"


# =============================================================================
# Story 12-3: Export Request Model Tests (Task 8.5)
# =============================================================================


class TestExportRequestModel:
    """Tests for export request validation."""

    def test_valid_export_request(self):
        """Test valid export request."""
        request = ExportRequest(
            format=ExportFormat.PDF,
            sections=["executive-summary", "timeline"],
        )

        assert request.format == ExportFormat.PDF
        assert len(request.sections) == 2
        assert request.include_verification_status is True

    def test_export_request_with_edits(self):
        """Test export request with section edits."""
        request = ExportRequest(
            format=ExportFormat.WORD,
            sections=["timeline"],
            section_edits={
                "timeline": ExportSectionEdit(
                    removed_item_ids=["event-1", "event-2"],
                    added_notes=["Note about timeline"],
                ),
            },
        )

        assert request.format == ExportFormat.WORD
        assert len(request.section_edits) == 1
        assert "event-1" in request.section_edits["timeline"].removed_item_ids

    def test_export_request_all_formats(self):
        """Test all export formats are valid."""
        for fmt in ExportFormat:
            request = ExportRequest(
                format=fmt,
                sections=["executive-summary"],
            )
            assert request.format == fmt
