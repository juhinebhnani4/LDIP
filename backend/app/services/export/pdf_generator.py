"""PDF document generator.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

Generates PDF documents from export content using basic HTML-to-PDF conversion.
Uses simple string formatting for lightweight generation without external dependencies.

Note: For production, consider using weasyprint, reportlab, or fpdf2.
This implementation provides a minimal working version.

Implements:
- AC #3: Generate PDF format
- AC #4: Include verification status footer
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.models.export import VerificationSummaryForExport

logger = structlog.get_logger(__name__)


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text at word boundary.

    Issue #5 fix: Truncates at word boundary to avoid cutting words mid-way.

    Args:
        text: Text to truncate.
        max_length: Maximum length before truncation.
        suffix: Suffix to append when truncated.

    Returns:
        Truncated text with suffix if needed.
    """
    if not text or len(text) <= max_length:
        return text

    # Try to find a word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    # If we found a space and it's not too far back, use it
    if last_space > max_length * 0.7:  # At least 70% of max_length
        truncated = truncated[:last_space]

    return truncated.rstrip() + suffix


class PDFGenerator:
    """PDF document generator.

    Story 12-3: Generates PDF exports from matter content.

    Note: This is a minimal implementation that generates a simple text-based PDF.
    For production use, integrate with a proper PDF library like reportlab or weasyprint.
    """

    def __init__(self) -> None:
        """Initialize PDF generator."""
        self._page_width = 612  # Letter width in points
        self._page_height = 792  # Letter height in points
        self._margin = 72  # 1 inch margins

    def generate(
        self,
        matter_name: str,
        section_content: dict[str, dict],
        verification_summary: "VerificationSummaryForExport | None" = None,
    ) -> bytes:
        """Generate PDF document.

        Args:
            matter_name: Matter name for title.
            section_content: Dictionary of section ID to content.
            verification_summary: Optional verification status to include.

        Returns:
            PDF file bytes.
        """
        logger.info("pdf_generation_started", matter_name=matter_name)

        # Build PDF using minimal PDF structure
        # This creates a valid PDF without external dependencies
        pdf_content = self._build_pdf(matter_name, section_content, verification_summary)

        logger.info("pdf_generation_completed", matter_name=matter_name)
        return pdf_content

    def _build_pdf(
        self,
        matter_name: str,
        section_content: dict[str, dict],
        verification_summary: "VerificationSummaryForExport | None",
    ) -> bytes:
        """Build minimal PDF structure.

        This creates a basic but valid PDF file.
        For more features, integrate reportlab or similar.
        """
        # Collect all text content
        text_lines: list[str] = []

        # Title
        text_lines.append(f"MATTER EXPORT: {matter_name}")
        text_lines.append("=" * 50)
        text_lines.append("")
        text_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        text_lines.append("")

        # Sections
        for section_id, content in section_content.items():
            title = content.get("title", section_id.replace("-", " ").title())
            text_lines.append("")
            text_lines.append(f"## {title.upper()}")
            text_lines.append("-" * 40)
            text_lines.append("")

            # Handle different section types
            if "custom_content" in content:
                text_lines.append(content["custom_content"])
            elif "parties" in content:
                self._add_summary_content(text_lines, content)
            elif "events" in content:
                self._add_timeline_content(text_lines, content)
            elif "entities" in content:
                self._add_entities_content(text_lines, content)
            elif "citations" in content:
                self._add_citations_content(text_lines, content)
            elif "findings" in content:
                self._add_findings_content(text_lines, content)
            elif "contradictions" in content:
                self._add_contradictions_content(text_lines, content)

            text_lines.append("")

        # Verification footer
        if verification_summary:
            text_lines.append("")
            text_lines.append("=" * 50)
            text_lines.append("VERIFICATION STATUS")
            text_lines.append("-" * 40)
            text_lines.append(
                f"Export Date: {verification_summary.export_date.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            text_lines.append(f"Total Findings: {verification_summary.total_findings}")
            text_lines.append(f"Verified: {verification_summary.verified_count}")
            text_lines.append(f"Pending: {verification_summary.pending_count}")
            text_lines.append(
                f"Exported By: {verification_summary.exported_by_name} ({verification_summary.exported_by_email})"
            )

        # Build minimal PDF structure
        return self._create_minimal_pdf("\n".join(text_lines))

    def _add_summary_content(self, lines: list[str], content: dict) -> None:
        """Add executive summary content."""
        # Parties
        parties = content.get("parties", [])
        if parties:
            lines.append("PARTIES:")
            for party in parties:
                role = party.get("role", "Unknown")
                name = party.get("name", "Unknown")
                lines.append(f"  - {role}: {name}")

        # Subject matter
        subject = content.get("subject_matter", {})
        if subject:
            lines.append("")
            lines.append("SUBJECT MATTER:")
            if subject.get("description"):
                lines.append(f"  {subject['description']}")

        # Current status
        status = content.get("current_status", {})
        if status:
            lines.append("")
            lines.append("CURRENT STATUS:")
            if status.get("stage"):
                lines.append(f"  Stage: {status['stage']}")
            if status.get("description"):
                lines.append(f"  {status['description']}")

        # Key issues
        issues = content.get("key_issues", [])
        if issues:
            lines.append("")
            lines.append("KEY ISSUES:")
            for issue in issues:
                if isinstance(issue, dict):
                    lines.append(f"  - {issue.get('title', 'Issue')}")
                    if issue.get("description"):
                        lines.append(f"    {issue['description']}")
                else:
                    lines.append(f"  - {issue}")

    def _add_timeline_content(self, lines: list[str], content: dict) -> None:
        """Add timeline content."""
        events = content.get("events", [])
        if not events:
            lines.append("No timeline events recorded.")
            return

        for event in events:
            date = event.get("event_date", "Unknown date")
            event_type = event.get("event_type", "event")
            description = event.get("description", "")
            confidence = event.get("confidence", 0)

            lines.append(f"[{date}] {event_type.upper()}")
            lines.append(f"  {description}")
            lines.append(f"  Confidence: {confidence:.0f}%")
            lines.append("")

    def _add_entities_content(self, lines: list[str], content: dict) -> None:
        """Add entities content."""
        entities = content.get("entities", [])
        if not entities:
            lines.append("No entities extracted.")
            return

        for entity in entities:
            name = entity.get("canonical_name", "Unknown")
            entity_type = entity.get("entity_type", "entity")
            mentions = entity.get("mention_count", 0)
            aliases = entity.get("aliases", [])

            lines.append(f"- {name} ({entity_type})")
            lines.append(f"  Mentions: {mentions}")
            if aliases:
                lines.append(f"  Aliases: {', '.join(aliases)}")
            lines.append("")

    def _add_citations_content(self, lines: list[str], content: dict) -> None:
        """Add citations content."""
        citations = content.get("citations", [])
        if not citations:
            lines.append("No citations found.")
            return

        for citation in citations:
            act = citation.get("act_name", "Unknown Act")
            section = citation.get("section", "")
            status = citation.get("verification_status", "unknown")
            confidence = citation.get("confidence", 0)

            lines.append(f"- {act}, {section}")
            lines.append(f"  Status: {status} | Confidence: {confidence:.0f}%")
            lines.append("")

    def _add_findings_content(self, lines: list[str], content: dict) -> None:
        """Add key findings content."""
        findings = content.get("findings", [])
        if not findings:
            lines.append("No verified findings.")
            return

        for finding in findings:
            finding_type = finding.get("finding_type", "finding")
            summary = finding.get("finding_summary", "")
            confidence = finding.get("confidence_before", 0)

            lines.append(f"- [{finding_type.upper()}] {summary}")
            lines.append(f"  Original Confidence: {confidence:.0f}%")
            lines.append("")

    def _add_contradictions_content(self, lines: list[str], content: dict) -> None:
        """Add contradictions content."""
        contradictions = content.get("contradictions", [])
        if not contradictions:
            lines.append("No contradictions detected.")
            return

        for contradiction in contradictions:
            con_type = contradiction.get("contradiction_type", "contradiction")
            severity = contradiction.get("severity", "unknown")
            statement_a = contradiction.get("statement_a", "")
            statement_b = contradiction.get("statement_b", "")

            lines.append(f"[{severity.upper()}] {con_type}")
            # Issue #5 fix: Use word-boundary truncation
            lines.append(f"  Statement A: {truncate_text(statement_a, 200)}")
            lines.append(f"  Statement B: {truncate_text(statement_b, 200)}")
            lines.append("")

    def _create_minimal_pdf(self, text: str) -> bytes:
        """Create a minimal valid PDF file with the given text content.

        This creates a simple single-page PDF without external dependencies.
        The text is rendered as-is in a basic fixed-width font.
        """
        # Escape special PDF characters
        escaped_text = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )

        # Split into lines and limit line length
        lines = []
        for line in escaped_text.split("\n"):
            # Word wrap at ~80 chars
            while len(line) > 80:
                lines.append(line[:80])
                line = line[80:]
            lines.append(line)

        # Calculate page layout
        line_height = 12
        chars_per_page = 60  # Lines per page
        pages_needed = (len(lines) // chars_per_page) + 1

        # Build PDF structure
        objects: list[str] = []
        xref_offsets: list[int] = []
        current_offset = 0

        # Helper to add object and track offset
        def add_object(content: str) -> int:
            nonlocal current_offset
            xref_offsets.append(current_offset)
            current_offset += len(content.encode("latin-1"))
            objects.append(content)
            return len(xref_offsets)

        # PDF Header
        header = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        current_offset = len(header.encode("latin-1"))

        # Object 1: Catalog
        add_object("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Object 2: Pages
        page_refs = " ".join([f"{i + 3} 0 R" for i in range(pages_needed)])
        add_object(f"2 0 obj\n<< /Type /Pages /Kids [{page_refs}] /Count {pages_needed} >>\nendobj\n")

        # Create pages
        content_obj_start = 3 + pages_needed
        for page_num in range(pages_needed):
            page_obj_num = 3 + page_num
            content_obj_num = content_obj_start + page_num

            # Page object
            add_object(
                f"{page_obj_num} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_obj_num} 0 R /Resources << /Font << /F1 {content_obj_start + pages_needed} 0 R >> >> >>\n"
                f"endobj\n"
            )

        # Create content streams
        for page_num in range(pages_needed):
            start_line = page_num * chars_per_page
            end_line = min(start_line + chars_per_page, len(lines))
            page_lines = lines[start_line:end_line]

            # Build text content
            text_ops = ["BT", "/F1 10 Tf", "72 720 Td", "12 TL"]
            for line in page_lines:
                text_ops.append(f"({line}) Tj T*")
            text_ops.append("ET")
            content = "\n".join(text_ops)

            stream_length = len(content)
            add_object(
                f"{content_obj_start + page_num} 0 obj\n"
                f"<< /Length {stream_length} >>\n"
                f"stream\n{content}\nendstream\n"
                f"endobj\n"
            )

        # Font object (Courier for monospace)
        font_obj_num = content_obj_start + pages_needed
        add_object(
            f"{font_obj_num} 0 obj\n"
            f"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\n"
            f"endobj\n"
        )

        # Build final PDF
        pdf_parts = [header]
        pdf_parts.extend(objects)

        # XRef table
        xref_start = current_offset + len(header.encode("latin-1")) - len(header)
        xref_start = sum(len(o.encode("latin-1")) for o in objects) + len(header.encode("latin-1"))

        xref_lines = [f"xref\n0 {len(xref_offsets) + 1}\n0000000000 65535 f \n"]
        offset = len(header.encode("latin-1"))
        for obj_content in objects:
            xref_lines.append(f"{offset:010d} 00000 n \n")
            offset += len(obj_content.encode("latin-1"))

        pdf_parts.extend(xref_lines)

        # Trailer
        pdf_parts.append(
            f"trailer\n<< /Size {len(xref_offsets) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        )

        return "".join(pdf_parts).encode("latin-1")
