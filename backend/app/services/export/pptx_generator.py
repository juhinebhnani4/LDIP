"""PowerPoint (PPTX) generator.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

Generates PowerPoint presentations from export content.
Creates valid PPTX files using the Office Open XML format.

Note: For production, consider using python-pptx for richer formatting.
This implementation creates minimal valid PPTX without external dependencies.

Implements:
- AC #3: Generate PowerPoint format
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


class PptxGenerator:
    """PowerPoint presentation generator.

    Story 12-3: Generates PPTX exports from matter content.

    Creates valid Office Open XML presentations without external dependencies.
    Each major section becomes a slide.
    """

    def __init__(self) -> None:
        """Initialize PPTX generator."""
        pass

    def generate(
        self,
        matter_name: str,
        section_content: dict[str, dict],
        verification_summary: VerificationSummaryForExport | None = None,
    ) -> bytes:
        """Generate PowerPoint presentation.

        Args:
            matter_name: Matter name for title slide.
            section_content: Dictionary of section ID to content.
            verification_summary: Optional verification status to include.

        Returns:
            PPTX file bytes.
        """
        logger.info("pptx_generation_started", matter_name=matter_name)

        # Build slides
        slides = self._build_slides(matter_name, section_content, verification_summary)

        # Create PPTX package
        pptx_bytes = self._create_pptx_package(slides)

        logger.info("pptx_generation_completed", matter_name=matter_name)
        return pptx_bytes

    def _build_slides(
        self,
        matter_name: str,
        section_content: dict[str, dict],
        verification_summary: VerificationSummaryForExport | None,
    ) -> list[dict]:
        """Build slide content dictionaries."""
        slides: list[dict] = []

        # Title slide
        slides.append({
            "type": "title",
            "title": f"Matter Export: {matter_name}",
            "subtitle": f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        })

        # Section slides
        for section_id, content in section_content.items():
            title = content.get("title", section_id.replace("-", " ").title())

            if "custom_content" in content:
                slides.append({
                    "type": "content",
                    "title": title,
                    "body": [content["custom_content"]],
                })
            elif "parties" in content:
                slides.extend(self._create_summary_slides(title, content))
            elif "events" in content:
                slides.extend(self._create_timeline_slides(title, content))
            elif "entities" in content:
                slides.extend(self._create_entities_slides(title, content))
            elif "citations" in content:
                slides.extend(self._create_citations_slides(title, content))
            elif "findings" in content:
                slides.extend(self._create_findings_slides(title, content))
            elif "contradictions" in content:
                slides.extend(self._create_contradictions_slides(title, content))

        # Verification slide
        if verification_summary:
            slides.append({
                "type": "content",
                "title": "Verification Status",
                "body": [
                    f"Export Date: {verification_summary.export_date.strftime('%Y-%m-%d %H:%M UTC')}",
                    f"Total Findings: {verification_summary.total_findings}",
                    f"Verified: {verification_summary.verified_count}",
                    f"Pending: {verification_summary.pending_count}",
                    f"Exported By: {verification_summary.exported_by_name}",
                ],
            })

        return slides

    def _create_summary_slides(self, title: str, content: dict) -> list[dict]:
        """Create executive summary slides."""
        slides: list[dict] = []

        # Overview slide with parties
        parties = content.get("parties", [])
        if parties:
            party_lines = [f"{p.get('role', 'Unknown')}: {p.get('name', 'Unknown')}" for p in parties]
            slides.append({
                "type": "content",
                "title": f"{title} - Parties",
                "body": party_lines[:8],  # Limit to 8 items per slide
            })

        # Key issues slide
        issues = content.get("key_issues", [])
        if issues:
            issue_lines = []
            for issue in issues[:6]:
                if isinstance(issue, dict):
                    issue_lines.append(issue.get("title", "Issue"))
                else:
                    issue_lines.append(str(issue))
            slides.append({
                "type": "content",
                "title": f"{title} - Key Issues",
                "body": issue_lines,
            })

        # Status slide
        status = content.get("current_status", {})
        if status:
            status_lines = []
            if status.get("stage"):
                status_lines.append(f"Stage: {status['stage']}")
            if status.get("description"):
                status_lines.append(status["description"][:200])
            if status_lines:
                slides.append({
                    "type": "content",
                    "title": f"{title} - Current Status",
                    "body": status_lines,
                })

        return slides if slides else [{"type": "content", "title": title, "body": ["No summary data available."]}]

    def _create_timeline_slides(self, title: str, content: dict) -> list[dict]:
        """Create timeline slides."""
        events = content.get("events", [])
        if not events:
            return [{"type": "content", "title": title, "body": ["No timeline events recorded."]}]

        slides: list[dict] = []
        # Group events into slides of 5
        for i in range(0, len(events), 5):
            batch = events[i:i + 5]
            lines = []
            for event in batch:
                date = event.get("event_date", "Unknown")
                desc = event.get("description", "")[:100]
                lines.append(f"{date}: {desc}")

            slides.append({
                "type": "content",
                "title": f"{title} ({i + 1}-{i + len(batch)})",
                "body": lines,
            })

        return slides

    def _create_entities_slides(self, title: str, content: dict) -> list[dict]:
        """Create entities slides."""
        entities = content.get("entities", [])
        if not entities:
            return [{"type": "content", "title": title, "body": ["No entities extracted."]}]

        slides: list[dict] = []
        # Group entities into slides of 6
        for i in range(0, min(len(entities), 30), 6):
            batch = entities[i:i + 6]
            lines = [
                f"{e.get('canonical_name', 'Unknown')} ({e.get('entity_type', 'entity')}) - {e.get('mention_count', 0)} mentions"
                for e in batch
            ]
            slides.append({
                "type": "content",
                "title": f"{title} ({i + 1}-{i + len(batch)})",
                "body": lines,
            })

        return slides

    def _create_citations_slides(self, title: str, content: dict) -> list[dict]:
        """Create citations slides."""
        citations = content.get("citations", [])
        if not citations:
            return [{"type": "content", "title": title, "body": ["No citations found."]}]

        slides: list[dict] = []
        # Group citations into slides of 5
        for i in range(0, min(len(citations), 25), 5):
            batch = citations[i:i + 5]
            lines = [
                f"{c.get('act_name', 'Unknown')}, {c.get('section', '')} ({c.get('verification_status', 'unknown')})"
                for c in batch
            ]
            slides.append({
                "type": "content",
                "title": f"{title} ({i + 1}-{i + len(batch)})",
                "body": lines,
            })

        return slides

    def _create_findings_slides(self, title: str, content: dict) -> list[dict]:
        """Create key findings slides."""
        findings = content.get("findings", [])
        if not findings:
            return [{"type": "content", "title": title, "body": ["No verified findings."]}]

        slides: list[dict] = []
        # Group findings into slides of 4
        for i in range(0, min(len(findings), 20), 4):
            batch = findings[i:i + 4]
            lines = [
                f"[{f.get('finding_type', 'finding').upper()}] {f.get('finding_summary', '')[:80]}"
                for f in batch
            ]
            slides.append({
                "type": "content",
                "title": f"{title} ({i + 1}-{i + len(batch)})",
                "body": lines,
            })

        return slides

    def _create_contradictions_slides(self, title: str, content: dict) -> list[dict]:
        """Create contradictions slides."""
        contradictions = content.get("contradictions", [])
        if not contradictions:
            return [{"type": "content", "title": title, "body": ["No contradictions detected."]}]

        slides: list[dict] = []
        # One contradiction per slide (they need more space)
        for i, contradiction in enumerate(contradictions[:10]):
            con_type = contradiction.get("contradiction_type", "contradiction")
            severity = contradiction.get("severity", "unknown")
            statement_a = contradiction.get("statement_a", "")
            statement_b = contradiction.get("statement_b", "")

            slides.append({
                "type": "content",
                "title": f"{title} - {con_type.title()} ({severity.upper()})",
                "body": [
                    # Issue #5 fix: Use word-boundary truncation
                    f"Statement A: {truncate_text(statement_a, 100)}",
                    f"Statement B: {truncate_text(statement_b, 100)}",
                ],
            })

        return slides

    def _create_pptx_package(self, slides: list[dict]) -> bytes:
        """Create the PPTX ZIP package."""
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Content types
            zf.writestr("[Content_Types].xml", self._content_types_xml(len(slides)))

            # Relationships
            zf.writestr("_rels/.rels", self._rels_xml())
            zf.writestr("ppt/_rels/presentation.xml.rels", self._presentation_rels_xml(len(slides)))

            # Presentation
            zf.writestr("ppt/presentation.xml", self._presentation_xml(len(slides)))

            # Slide layouts
            zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", self._layout_rels_xml())
            zf.writestr("ppt/slideLayouts/_rels/slideLayout2.xml.rels", self._layout_rels_xml())
            zf.writestr("ppt/slideLayouts/slideLayout1.xml", self._title_layout_xml())
            zf.writestr("ppt/slideLayouts/slideLayout2.xml", self._content_layout_xml())

            # Slide master
            zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", self._master_rels_xml())
            zf.writestr("ppt/slideMasters/slideMaster1.xml", self._slide_master_xml())

            # Theme
            zf.writestr("ppt/theme/theme1.xml", self._theme_xml())

            # Individual slides
            for i, slide in enumerate(slides, 1):
                layout_id = 1 if slide["type"] == "title" else 2
                zf.writestr(
                    f"ppt/slides/_rels/slide{i}.xml.rels",
                    self._slide_rels_xml(layout_id),
                )
                zf.writestr(
                    f"ppt/slides/slide{i}.xml",
                    self._slide_xml(slide),
                )

        return buffer.getvalue()

    def _content_types_xml(self, slide_count: int) -> str:
        """Generate [Content_Types].xml."""
        slide_overrides = "\n".join([
            f'  <Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            for i in range(1, slide_count + 1)
        ])

        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{slide_overrides}
</Types>'''

    def _rels_xml(self) -> str:
        """Generate _rels/.rels."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>'''

    def _presentation_rels_xml(self, slide_count: int) -> str:
        """Generate ppt/_rels/presentation.xml.rels."""
        slide_rels = "\n".join([
            f'  <Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
            for i in range(1, slide_count + 1)
        ])
        master_id = slide_count + 1
        theme_id = slide_count + 2

        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{slide_rels}
  <Relationship Id="rId{master_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId{theme_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>'''

    def _presentation_xml(self, slide_count: int) -> str:
        """Generate ppt/presentation.xml."""
        slide_list = "\n".join([
            f'      <p:sldId id="{256 + i}" r:id="rId{i}"/>'
            for i in range(1, slide_count + 1)
        ])
        master_id = slide_count + 1

        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId{master_id}"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
{slide_list}
  </p:sldIdLst>
  <p:sldSz cx="9144000" cy="6858000" type="screen4x3"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>'''

    def _layout_rels_xml(self) -> str:
        """Generate slide layout relationships."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>'''

    def _master_rels_xml(self) -> str:
        """Generate slide master relationships."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>'''

    def _slide_rels_xml(self, layout_id: int) -> str:
        """Generate slide relationships."""
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout{layout_id}.xml"/>
</Relationships>'''

    def _slide_master_xml(self) -> str:
        """Generate slide master."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:bg>
      <p:bgRef idx="1001">
        <a:schemeClr val="bg1"/>
      </p:bgRef>
    </p:bg>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst>
    <p:sldLayoutId id="2147483649" r:id="rId1"/>
    <p:sldLayoutId id="2147483650" r:id="rId2"/>
  </p:sldLayoutIdLst>
</p:sldMaster>'''

    def _title_layout_xml(self) -> str:
        """Generate title slide layout."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" type="title">
  <p:cSld name="Title Slide">
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sldLayout>'''

    def _content_layout_xml(self) -> str:
        """Generate content slide layout."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" type="obj">
  <p:cSld name="Title and Content">
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sldLayout>'''

    def _theme_xml(self) -> str:
        """Generate theme."""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="LDIP Theme">
  <a:themeElements>
    <a:clrScheme name="LDIP">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="44546A"/></a:dk2>
      <a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
      <a:accent1><a:srgbClr val="2E74B5"/></a:accent1>
      <a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
      <a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>
      <a:accent4><a:srgbClr val="FFC000"/></a:accent4>
      <a:accent5><a:srgbClr val="4472C4"/></a:accent5>
      <a:accent6><a:srgbClr val="70AD47"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="LDIP">
      <a:majorFont>
        <a:latin typeface="Calibri Light"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
      </a:majorFont>
      <a:minorFont>
        <a:latin typeface="Calibri"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
      </a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="LDIP">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="25400"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="38100"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>'''

    def _slide_xml(self, slide: dict) -> str:
        """Generate individual slide XML."""
        title = xml_escape(slide.get("title", ""))

        if slide["type"] == "title":
            subtitle = xml_escape(slide.get("subtitle", ""))
            return self._title_slide_xml(title, subtitle)
        else:
            body_lines = [xml_escape(line) for line in slide.get("body", [])]
            return self._content_slide_xml(title, body_lines)

    def _title_slide_xml(self, title: str, subtitle: str) -> str:
        """Generate title slide content."""
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Title"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="457200" y="2286000"/>
            <a:ext cx="8229600" cy="1371600"/>
          </a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr"/>
          <a:lstStyle/>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr lang="en-US" sz="4400" b="1">
                <a:solidFill><a:schemeClr val="dk1"/></a:solidFill>
              </a:rPr>
              <a:t>{title}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="3" name="Subtitle"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="457200" y="3886200"/>
            <a:ext cx="8229600" cy="914400"/>
          </a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="t"/>
          <a:lstStyle/>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr lang="en-US" sz="2000" i="1">
                <a:solidFill><a:schemeClr val="dk2"/></a:solidFill>
              </a:rPr>
              <a:t>{subtitle}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sld>'''

    def _content_slide_xml(self, title: str, body_lines: list[str]) -> str:
        """Generate content slide content."""
        # Build body paragraphs
        body_paras = "\n".join([
            f'''          <a:p>
            <a:pPr marL="342900" indent="-342900">
              <a:buFont typeface="Arial"/>
              <a:buChar char="&#8226;"/>
            </a:pPr>
            <a:r>
              <a:rPr lang="en-US" sz="1800"/>
              <a:t>{line}</a:t>
            </a:r>
          </a:p>'''
            for line in body_lines
        ])

        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Title"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="457200" y="274638"/>
            <a:ext cx="8229600" cy="857250"/>
          </a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="b"/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="en-US" sz="3200" b="1">
                <a:solidFill><a:srgbClr val="2E74B5"/></a:solidFill>
              </a:rPr>
              <a:t>{title}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="3" name="Content"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="457200" y="1371600"/>
            <a:ext cx="8229600" cy="4648200"/>
          </a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
{body_paras}
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sld>'''
