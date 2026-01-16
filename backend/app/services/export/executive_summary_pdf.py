"""Executive Summary PDF Generator.

Story 12.4: Partner Executive Summary Export
Epic 12: Export Builder

Generates a concise 1-2 page PDF for senior partners containing:
- Case Overview
- Key Parties table
- Critical Dates
- Verified Issues (with badges)
- Recommended Actions
- Footer with pending count and link

Implements:
- AC #2: Single-page PDF optimized for quick review
- AC #3: Verified status badges, pending count note
- AC #4: Footer with LDIP branding and workspace link
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.services.export.executive_summary_service import ExecutiveSummaryContent
from app.services.export.pdf_generator import truncate_text

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class ExecutiveSummaryPDFGenerator:
    """Specialized PDF generator for executive summaries.

    Story 12.4: Generates compact 1-2 page PDF for partners.
    """

    # Page layout constants
    LINES_PER_PAGE = 60  # ~60 lines per page at 10pt Courier
    MAX_PAGES = 2

    # Content truncation thresholds (in order of truncation priority)
    TRUNCATION_PRIORITIES = [
        ("recommended_actions", 3),  # Reduce to 3 first
        ("critical_dates", 5),       # Then reduce dates to 5
        ("verified_issues", 5),      # Then reduce issues to 5
    ]

    def __init__(self, frontend_url: str | None = None) -> None:
        """Initialize PDF generator.

        Args:
            frontend_url: Base URL for workspace link (e.g., https://app.ldip.ai).
        """
        self.frontend_url = frontend_url or "https://app.ldip.ai"

    def generate(
        self,
        content: ExecutiveSummaryContent,
        export_date: datetime | None = None,
    ) -> bytes:
        """Generate executive summary PDF.

        Story 12.4: AC #2, #3, #4 - Generate 1-2 page PDF.

        Args:
            content: Extracted executive summary content.
            export_date: Export timestamp (defaults to now).

        Returns:
            PDF file bytes.
        """
        logger.info(
            "executive_summary_pdf_generation_started",
            matter_id=content.matter_id,
        )

        if export_date is None:
            export_date = datetime.now(UTC)

        # Build PDF content
        lines = self._build_content_lines(content, export_date)

        # Check page count and truncate if needed
        lines = self._enforce_page_limit(lines, content)

        # Generate PDF
        pdf_bytes = self._create_minimal_pdf("\n".join(lines))

        logger.info(
            "executive_summary_pdf_generation_completed",
            matter_id=content.matter_id,
            line_count=len(lines),
        )

        return pdf_bytes

    def _build_content_lines(
        self,
        content: ExecutiveSummaryContent,
        export_date: datetime,
    ) -> list[str]:
        """Build all content lines for PDF."""
        lines: list[str] = []

        # Header
        lines.extend(self._build_header(content, export_date))

        # Case Overview (never truncated)
        lines.extend(self._build_case_overview(content.case_overview))

        # Key Parties table
        lines.extend(self._build_parties_table(content.parties))

        # Critical Dates
        lines.extend(self._build_critical_dates(content.critical_dates))

        # Verified Issues
        lines.extend(self._build_verified_issues(content.verified_issues))

        # Recommended Actions
        lines.extend(self._build_recommended_actions(content.recommended_actions))

        # Footer
        lines.extend(self._build_footer(content, export_date))

        return lines

    def _build_header(
        self,
        content: ExecutiveSummaryContent,
        export_date: datetime,
    ) -> list[str]:
        """Build header section."""
        return [
            "=" * 60,
            "EXECUTIVE SUMMARY",
            "=" * 60,
            "",
            f"Matter: {content.matter_name}",
            f"Generated: {export_date.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

    def _build_case_overview(self, overview: str) -> list[str]:
        """Build case overview section."""
        lines = [
            "CASE OVERVIEW",
            "-" * 40,
            "",
        ]

        # Word wrap overview at 70 chars
        for paragraph in overview.split("\n\n"):
            wrapped = self._word_wrap(paragraph, 70)
            lines.extend(wrapped)
            lines.append("")

        return lines

    def _build_parties_table(self, parties: list[dict]) -> list[str]:
        """Build key parties table."""
        lines = [
            "KEY PARTIES",
            "-" * 40,
        ]

        if not parties:
            lines.append("No parties recorded.")
            lines.append("")
            return lines

        # Table header
        lines.append(f"{'Role':<15} {'Name':<25} {'Relevance':<20}")
        lines.append("-" * 60)

        # Table rows
        for party in parties:
            role = truncate_text(str(party.get("role", "Unknown")), 14, "")
            name = truncate_text(str(party.get("name", "Unknown")), 24, "")
            relevance = truncate_text(str(party.get("relevance", "")), 19, "")
            lines.append(f"{role:<15} {name:<25} {relevance:<20}")

        lines.append("")
        return lines

    def _build_critical_dates(self, dates: list[dict]) -> list[str]:
        """Build critical dates section."""
        lines = [
            "CRITICAL DATES",
            "-" * 40,
        ]

        if not dates:
            lines.append("No critical dates recorded.")
            lines.append("")
            return lines

        for date_item in dates:
            date_str = str(date_item.get("date", "Unknown"))
            event_type = str(date_item.get("type", "event")).upper()
            description = truncate_text(str(date_item.get("description", "")), 50, "...")

            lines.append(f"- [{date_str}] {event_type}: {description}")

        lines.append("")
        return lines

    def _build_verified_issues(self, issues: list[dict]) -> list[str]:
        """Build verified issues section with badges."""
        lines = [
            "VERIFIED ISSUES",
            "-" * 40,
        ]

        if not issues:
            lines.append("No verified issues.")
            lines.append("")
            return lines

        for issue in issues:
            severity = str(issue.get("severity", "unknown")).upper()
            summary = truncate_text(str(issue.get("summary", "Issue")), 50, "...")

            # Add [VERIFIED] badge per AC #3
            lines.append(f"[{severity}] {summary} [VERIFIED]")

        lines.append("")
        return lines

    def _build_recommended_actions(self, actions: list[str]) -> list[str]:
        """Build recommended actions section."""
        lines = [
            "RECOMMENDED ACTIONS",
            "-" * 40,
        ]

        if not actions:
            lines.append("No recommended actions.")
            lines.append("")
            return lines

        for i, action in enumerate(actions, 1):
            wrapped = self._word_wrap(f"{i}. {action}", 65)
            lines.extend(wrapped)

        lines.append("")
        return lines

    def _build_footer(
        self,
        content: ExecutiveSummaryContent,
        export_date: datetime,
    ) -> list[str]:
        """Build footer with pending count and link.

        Story 12.4: AC #3, #4 - Footer with pending count and link.
        """
        workspace_url = f"{self.frontend_url}/matters/{content.matter_id}"

        lines = [
            "-" * 60,
            "",
        ]

        # Pending verification note (AC #3)
        if content.pending_verification_count > 0:
            lines.append(
                f"{content.pending_verification_count} additional findings pending verification"
            )

        # LDIP branding and link (AC #4)
        lines.append("")
        lines.append("Generated from full analysis - open LDIP for complete details")
        lines.append(workspace_url)
        lines.append("")

        return lines

    def _enforce_page_limit(
        self,
        lines: list[str],
        content: ExecutiveSummaryContent,
    ) -> list[str]:
        """Ensure content fits within MAX_PAGES.

        Story 12.4: AC #3 - Document fits on 1-2 pages maximum.

        Truncation priority:
        1. Recommended Actions (reduce to 3)
        2. Critical Dates (reduce to 5)
        3. Verified Issues (reduce to 5)
        """
        max_lines = self.LINES_PER_PAGE * self.MAX_PAGES

        # If within limit, return as-is
        if len(lines) <= max_lines:
            return lines

        logger.info(
            "executive_summary_truncation_required",
            original_lines=len(lines),
            max_lines=max_lines,
        )

        # Apply truncation in priority order
        # Issue #5 fix: Create a deep copy to avoid mutating the original content object
        truncated_content = copy.deepcopy(content)

        for section, limit in self.TRUNCATION_PRIORITIES:
            if len(lines) <= max_lines:
                break

            if section == "recommended_actions":
                truncated_content.recommended_actions = truncated_content.recommended_actions[:limit]
            elif section == "critical_dates":
                truncated_content.critical_dates = truncated_content.critical_dates[:limit]
            elif section == "verified_issues":
                truncated_content.verified_issues = truncated_content.verified_issues[:limit]

            # Rebuild lines (Issue #6 fix: use timezone-aware datetime)
            lines = self._build_content_lines(
                truncated_content,
                datetime.now(UTC),
            )

        return lines[:max_lines]

    def _word_wrap(self, text: str, width: int) -> list[str]:
        """Wrap text at word boundaries."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                current_line += (" " + word) if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines or [""]

    def _create_minimal_pdf(self, text: str) -> bytes:
        """Create a minimal valid PDF file with the given text content.

        Reuses the same approach as PDFGenerator for consistency.
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
        chars_per_page = 60  # Lines per page
        pages_needed = (len(lines) // chars_per_page) + 1

        # Build PDF structure
        objects: list[str] = []

        # PDF Header
        header = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"

        # Object 1: Catalog
        objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Object 2: Pages
        page_refs = " ".join([f"{i + 3} 0 R" for i in range(pages_needed)])
        objects.append(f"2 0 obj\n<< /Type /Pages /Kids [{page_refs}] /Count {pages_needed} >>\nendobj\n")

        # Create pages
        content_obj_start = 3 + pages_needed
        for page_num in range(pages_needed):
            page_obj_num = 3 + page_num
            content_obj_num = content_obj_start + page_num

            # Page object
            objects.append(
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
            stream_content = "\n".join(text_ops)

            stream_length = len(stream_content)
            objects.append(
                f"{content_obj_start + page_num} 0 obj\n"
                f"<< /Length {stream_length} >>\n"
                f"stream\n{stream_content}\nendstream\n"
                f"endobj\n"
            )

        # Font object (Courier for monospace)
        font_obj_num = content_obj_start + pages_needed
        objects.append(
            f"{font_obj_num} 0 obj\n"
            f"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\n"
            f"endobj\n"
        )

        # Build final PDF
        pdf_parts = [header]
        pdf_parts.extend(objects)

        # XRef table
        xref_start = sum(len(o.encode("latin-1")) for o in objects) + len(header.encode("latin-1"))

        xref_lines = [f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"]
        offset = len(header.encode("latin-1"))
        for obj_content in objects:
            xref_lines.append(f"{offset:010d} 00000 n \n")
            offset += len(obj_content.encode("latin-1"))

        pdf_parts.extend(xref_lines)

        # Trailer
        pdf_parts.append(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        )

        return "".join(pdf_parts).encode("latin-1")
