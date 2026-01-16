"""Word document (DOCX) generator.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

Generates Word documents from export content.
Creates valid DOCX files using the Office Open XML format.

Note: For production, consider using python-docx for richer formatting.
This implementation creates minimal valid DOCX without external dependencies.

Implements:
- AC #3: Generate Word format
- AC #4: Include verification status footer
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape as xml_escape

import structlog

from app.services.export.pdf_generator import truncate_text

if TYPE_CHECKING:
    from app.models.export import VerificationSummaryForExport

logger = structlog.get_logger(__name__)


class DocxGenerator:
    """Word document generator.

    Story 12-3: Generates DOCX exports from matter content.

    Creates valid Office Open XML documents without external dependencies.
    """

    def __init__(self) -> None:
        """Initialize DOCX generator."""
        pass

    def generate(
        self,
        matter_name: str,
        section_content: dict[str, dict],
        verification_summary: VerificationSummaryForExport | None = None,
    ) -> bytes:
        """Generate Word document.

        Args:
            matter_name: Matter name for title.
            section_content: Dictionary of section ID to content.
            verification_summary: Optional verification status to include.

        Returns:
            DOCX file bytes.
        """
        logger.info("docx_generation_started", matter_name=matter_name)

        # Build document content
        body_content = self._build_body(matter_name, section_content, verification_summary)

        # Create DOCX package
        docx_bytes = self._create_docx_package(body_content)

        logger.info("docx_generation_completed", matter_name=matter_name)
        return docx_bytes

    def _build_body(
        self,
        matter_name: str,
        section_content: dict[str, dict],
        verification_summary: VerificationSummaryForExport | None,
    ) -> str:
        """Build document body XML content."""
        paragraphs: list[str] = []

        # Title
        paragraphs.append(self._make_heading(f"Matter Export: {matter_name}", 1))
        paragraphs.append(
            self._make_paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                italic=True,
            )
        )
        paragraphs.append(self._make_paragraph(""))  # Empty paragraph

        # Sections
        for section_id, content in section_content.items():
            title = content.get("title", section_id.replace("-", " ").title())
            paragraphs.append(self._make_heading(title, 2))

            # Handle different section types
            if "custom_content" in content:
                for line in content["custom_content"].split("\n"):
                    paragraphs.append(self._make_paragraph(line))
            elif "parties" in content:
                paragraphs.extend(self._add_summary_content(content))
            elif "events" in content:
                paragraphs.extend(self._add_timeline_content(content))
            elif "entities" in content:
                paragraphs.extend(self._add_entities_content(content))
            elif "citations" in content:
                paragraphs.extend(self._add_citations_content(content))
            elif "findings" in content:
                paragraphs.extend(self._add_findings_content(content))
            elif "contradictions" in content:
                paragraphs.extend(self._add_contradictions_content(content))

            paragraphs.append(self._make_paragraph(""))  # Section spacing

        # Verification footer
        if verification_summary:
            paragraphs.append(self._make_heading("Verification Status", 2))
            paragraphs.append(
                self._make_paragraph(
                    f"Export Date: {verification_summary.export_date.strftime('%Y-%m-%d %H:%M UTC')}"
                )
            )
            paragraphs.append(
                self._make_paragraph(f"Total Findings: {verification_summary.total_findings}")
            )
            paragraphs.append(
                self._make_paragraph(f"Verified: {verification_summary.verified_count}")
            )
            paragraphs.append(
                self._make_paragraph(f"Pending: {verification_summary.pending_count}")
            )
            paragraphs.append(
                self._make_paragraph(
                    f"Exported By: {verification_summary.exported_by_name} "
                    f"({verification_summary.exported_by_email})"
                )
            )

        return "\n".join(paragraphs)

    def _add_summary_content(self, content: dict) -> list[str]:
        """Add executive summary content."""
        paras: list[str] = []

        # Parties
        parties = content.get("parties", [])
        if parties:
            paras.append(self._make_heading("Parties", 3))
            for party in parties:
                role = party.get("role", "Unknown")
                name = party.get("name", "Unknown")
                paras.append(self._make_bullet(f"{role}: {name}"))

        # Subject matter
        subject = content.get("subject_matter", {})
        if subject:
            paras.append(self._make_heading("Subject Matter", 3))
            if subject.get("description"):
                paras.append(self._make_paragraph(subject["description"]))

        # Current status
        status = content.get("current_status", {})
        if status:
            paras.append(self._make_heading("Current Status", 3))
            if status.get("stage"):
                paras.append(self._make_paragraph(f"Stage: {status['stage']}"))
            if status.get("description"):
                paras.append(self._make_paragraph(status["description"]))

        # Key issues
        issues = content.get("key_issues", [])
        if issues:
            paras.append(self._make_heading("Key Issues", 3))
            for issue in issues:
                if isinstance(issue, dict):
                    paras.append(self._make_bullet(issue.get("title", "Issue")))
                    if issue.get("description"):
                        paras.append(self._make_paragraph(f"  {issue['description']}"))
                else:
                    paras.append(self._make_bullet(str(issue)))

        return paras

    def _add_timeline_content(self, content: dict) -> list[str]:
        """Add timeline content."""
        paras: list[str] = []
        events = content.get("events", [])

        if not events:
            paras.append(self._make_paragraph("No timeline events recorded."))
            return paras

        for event in events:
            date = event.get("event_date", "Unknown date")
            event_type = event.get("event_type", "event")
            description = event.get("description", "")
            confidence = event.get("confidence", 0)

            paras.append(self._make_paragraph(f"[{date}] {event_type.upper()}", bold=True))
            paras.append(self._make_paragraph(description))
            paras.append(self._make_paragraph(f"Confidence: {confidence:.0f}%", italic=True))

        return paras

    def _add_entities_content(self, content: dict) -> list[str]:
        """Add entities content."""
        paras: list[str] = []
        entities = content.get("entities", [])

        if not entities:
            paras.append(self._make_paragraph("No entities extracted."))
            return paras

        for entity in entities:
            name = entity.get("canonical_name", "Unknown")
            entity_type = entity.get("entity_type", "entity")
            mentions = entity.get("mention_count", 0)
            aliases = entity.get("aliases", [])

            paras.append(self._make_bullet(f"{name} ({entity_type})"))
            paras.append(self._make_paragraph(f"  Mentions: {mentions}", italic=True))
            if aliases:
                paras.append(self._make_paragraph(f"  Aliases: {', '.join(aliases)}", italic=True))

        return paras

    def _add_citations_content(self, content: dict) -> list[str]:
        """Add citations content."""
        paras: list[str] = []
        citations = content.get("citations", [])

        if not citations:
            paras.append(self._make_paragraph("No citations found."))
            return paras

        for citation in citations:
            act = citation.get("act_name", "Unknown Act")
            section = citation.get("section", "")
            status = citation.get("verification_status", "unknown")
            confidence = citation.get("confidence", 0)

            paras.append(self._make_bullet(f"{act}, {section}"))
            paras.append(
                self._make_paragraph(
                    f"  Status: {status} | Confidence: {confidence:.0f}%", italic=True
                )
            )

        return paras

    def _add_findings_content(self, content: dict) -> list[str]:
        """Add key findings content."""
        paras: list[str] = []
        findings = content.get("findings", [])

        if not findings:
            paras.append(self._make_paragraph("No verified findings."))
            return paras

        for finding in findings:
            finding_type = finding.get("finding_type", "finding")
            summary = finding.get("finding_summary", "")
            confidence = finding.get("confidence_before", 0)

            paras.append(self._make_bullet(f"[{finding_type.upper()}] {summary}"))
            paras.append(
                self._make_paragraph(f"  Original Confidence: {confidence:.0f}%", italic=True)
            )

        return paras

    def _add_contradictions_content(self, content: dict) -> list[str]:
        """Add contradictions content."""
        paras: list[str] = []
        contradictions = content.get("contradictions", [])

        if not contradictions:
            paras.append(self._make_paragraph("No contradictions detected."))
            return paras

        for contradiction in contradictions:
            con_type = contradiction.get("contradiction_type", "contradiction")
            severity = contradiction.get("severity", "unknown")
            statement_a = contradiction.get("statement_a", "")
            statement_b = contradiction.get("statement_b", "")

            paras.append(self._make_paragraph(f"[{severity.upper()}] {con_type}", bold=True))
            # Issue #5 fix: Use word-boundary truncation
            paras.append(self._make_paragraph(f"Statement A: {truncate_text(statement_a, 200)}"))
            paras.append(self._make_paragraph(f"Statement B: {truncate_text(statement_b, 200)}"))

        return paras

    def _make_paragraph(
        self, text: str, bold: bool = False, italic: bool = False
    ) -> str:
        """Create a paragraph XML element."""
        escaped = xml_escape(text)
        rpr = ""
        if bold or italic:
            rpr_content = ""
            if bold:
                rpr_content += "<w:b/>"
            if italic:
                rpr_content += "<w:i/>"
            rpr = f"<w:rPr>{rpr_content}</w:rPr>"

        return f'<w:p><w:r>{rpr}<w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>'

    def _make_heading(self, text: str, level: int) -> str:
        """Create a heading paragraph."""
        escaped = xml_escape(text)
        style = f"Heading{level}"
        return (
            f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            f'<w:r><w:rPr><w:b/></w:rPr><w:t>{escaped}</w:t></w:r></w:p>'
        )

    def _make_bullet(self, text: str) -> str:
        """Create a bullet point paragraph."""
        escaped = xml_escape(text)
        return (
            '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
            f'<w:r><w:t>{escaped}</w:t></w:r></w:p>'
        )

    def _create_docx_package(self, body_content: str) -> bytes:
        """Create the DOCX ZIP package."""
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Content types
            zf.writestr("[Content_Types].xml", self._content_types_xml())

            # Relationships
            zf.writestr("_rels/.rels", self._rels_xml())
            zf.writestr("word/_rels/document.xml.rels", self._document_rels_xml())

            # Document content
            zf.writestr("word/document.xml", self._document_xml(body_content))

            # Styles
            zf.writestr("word/styles.xml", self._styles_xml())

            # Numbering (for bullets)
            zf.writestr("word/numbering.xml", self._numbering_xml())

        return buffer.getvalue()

    def _content_types_xml(self) -> str:
        """Generate [Content_Types].xml."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>'''

    def _rels_xml(self) -> str:
        """Generate _rels/.rels."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    def _document_rels_xml(self) -> str:
        """Generate word/_rels/document.xml.rels."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>'''

    def _document_xml(self, body_content: str) -> str:
        """Generate word/document.xml."""
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_content}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>'''

    def _styles_xml(self) -> str:
        """Generate word/styles.xml with heading styles."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
        <w:sz w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="200" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:pPr><w:spacing w:before="480" w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:pPr><w:spacing w:before="360" w:after="80"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="2E74B5"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:pPr><w:spacing w:before="240" w:after="60"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="24"/></w:rPr>
  </w:style>
</w:styles>'''

    def _numbering_xml(self) -> str:
        """Generate word/numbering.xml for bullet lists."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#8226;"/>
      <w:lvlJc w:val="left"/>
      <w:pPr>
        <w:ind w:left="720" w:hanging="360"/>
      </w:pPr>
      <w:rPr>
        <w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/>
      </w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1">
    <w:abstractNumId w:val="0"/>
  </w:num>
</w:numbering>'''
