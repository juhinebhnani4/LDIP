"""Section index service for Act document section lookups.

Manages the section_index table for pre-computed section -> page mappings.
This optimizes split-view citation lookups by eliminating runtime bbox searches.

Story 3-4: Citation Verification Split-View
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import structlog
from supabase import Client

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Section header patterns for Indian Acts
SECTION_HEADER_PATTERNS = [
    # "123. Title of section" - most common format
    re.compile(r"^(\d+[A-Z]?)\.\s+([A-Z][a-z].*?)(?:\.\s*[-—]|\s*[-—]|$)", re.MULTILINE),
    # "Section 123" standalone
    re.compile(r"^Section\s+(\d+[A-Z]?(?:\(\d+\))?)\b", re.IGNORECASE | re.MULTILINE),
    # "[Section 123]" in brackets
    re.compile(r"^\[Section\s+(\d+[A-Z]?)\]", re.IGNORECASE | re.MULTILINE),
]

# TOC detection keywords
TOC_KEYWORDS = [
    "arrangement of sections",
    "table of contents",
    "contents",
    "index",
    "chapter",
    "part",
]

# Patterns indicating old Act references (to skip)
OLD_ACT_PATTERNS = [
    r"\b1956\b",
    r"\b1932\b",
    r"\b1881\b",
    r"old act",
    r"repealed",
]


@dataclass
class SectionLocation:
    """Location of a section in a document."""

    section_number: str
    page_number: int
    section_title: str | None = None
    confidence: float = 1.0
    is_toc: bool = False
    bbox_id: str | None = None
    source: str = "section_index"


class SectionIndexServiceError(Exception):
    """Base exception for section index service operations."""

    def __init__(self, message: str, code: str = "SECTION_INDEX_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class SectionIndexService:
    """Service for managing section index entries.

    Provides methods to:
    - Index sections from Act documents
    - Look up section page numbers
    - Detect TOC pages
    """

    def __init__(self, client: Client | None = None):
        """Initialize section index service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()

    def get_section_page(
        self,
        document_id: str,
        section_number: str,
    ) -> SectionLocation | None:
        """Get the page number for a section in a document.

        Tries the section_index table first, then falls back to bbox search.

        Args:
            document_id: Document UUID.
            section_number: Section number (e.g., "138", "138(1)", "138A").

        Returns:
            SectionLocation if found, None otherwise.
        """
        # Normalize section number
        normalized = self._normalize_section(section_number)

        # Try exact match in section_index (non-TOC)
        result = (
            self.client.table("section_index")
            .select("page_number, section_title, confidence, bbox_id")
            .eq("document_id", document_id)
            .eq("section_number", normalized)
            .eq("is_toc", False)
            .limit(1)
            .execute()
        )

        if result.data:
            row = result.data[0]
            return SectionLocation(
                section_number=normalized,
                page_number=row["page_number"],
                section_title=row.get("section_title"),
                confidence=row.get("confidence", 1.0),
                bbox_id=row.get("bbox_id"),
                source="section_index",
            )

        # Try base section number (strip letter suffix like "205A" -> "205")
        base_section = self._get_base_section(normalized)
        if base_section and base_section != normalized:
            result = (
                self.client.table("section_index")
                .select("page_number, section_title, confidence, bbox_id")
                .eq("document_id", document_id)
                .eq("section_number", base_section)
                .eq("is_toc", False)
                .limit(1)
                .execute()
            )

            if result.data:
                row = result.data[0]
                logger.info(
                    "section_found_via_base_fallback",
                    requested=normalized,
                    found=base_section,
                    page=row["page_number"],
                )
                return SectionLocation(
                    section_number=normalized,
                    page_number=row["page_number"],
                    section_title=row.get("section_title"),
                    confidence=row.get("confidence", 0.8) * 0.9,  # Slight confidence reduction
                    bbox_id=row.get("bbox_id"),
                    source="section_index_base",
                )

        # Fallback: Search bounding boxes
        return self._search_section_in_bboxes(document_id, normalized)

    def _search_section_in_bboxes(
        self,
        document_id: str,
        section_number: str,
    ) -> SectionLocation | None:
        """Search bounding boxes for section reference.

        Args:
            document_id: Document UUID.
            section_number: Normalized section number.

        Returns:
            SectionLocation if found, None otherwise.
        """
        # Get TOC pages to exclude
        toc_pages = self._get_toc_pages(document_id)
        min_content_page = max(toc_pages) + 1 if toc_pages else 11

        # Search for "section X" pattern, prefer higher pages
        result = (
            self.client.table("bounding_boxes")
            .select("page_number, text, id")
            .eq("document_id", document_id)
            .ilike("text", f"%section {section_number}%")
            .gte("page_number", min_content_page)
            .order("page_number", desc=True)
            .limit(20)
            .execute()
        )

        if not result.data:
            return None

        # Filter out old Act references
        for bbox in result.data:
            text_lower = bbox.get("text", "").lower()
            if not self._is_old_act_reference(text_lower):
                return SectionLocation(
                    section_number=section_number,
                    page_number=bbox["page_number"],
                    confidence=0.7,
                    bbox_id=str(bbox["id"]),
                    source="bbox_search",
                )

        # If all results were old Act references, use the first one anyway
        if result.data:
            bbox = result.data[0]
            return SectionLocation(
                section_number=section_number,
                page_number=bbox["page_number"],
                confidence=0.5,
                bbox_id=str(bbox["id"]),
                source="bbox_search_fallback",
            )

        return None

    def _get_toc_pages(self, document_id: str) -> list[int]:
        """Get list of TOC pages for a document.

        Args:
            document_id: Document UUID.

        Returns:
            List of page numbers that are TOC pages.
        """
        result = (
            self.client.table("toc_pages")
            .select("page_number")
            .eq("document_id", document_id)
            .execute()
        )

        if result.data:
            return [row["page_number"] for row in result.data]

        # Default: assume first 10 pages are TOC
        return list(range(1, 11))

    def index_document_sections(
        self,
        document_id: str,
        matter_id: str,
    ) -> int:
        """Index all sections in a document.

        Extracts section headers from bounding boxes and saves to section_index.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID.

        Returns:
            Number of sections indexed.
        """
        # First detect TOC pages
        toc_pages = self._detect_toc_pages(document_id)

        # Save TOC pages
        if toc_pages:
            self._save_toc_pages(document_id, toc_pages)

        min_content_page = max(toc_pages) + 1 if toc_pages else 11

        # Get all bounding boxes after TOC
        all_bboxes = self._get_all_bboxes(document_id, min_page=min_content_page)

        if not all_bboxes:
            logger.warning(
                "no_bboxes_for_section_indexing",
                document_id=document_id,
            )
            return 0

        # Extract sections from bboxes
        sections: list[dict[str, Any]] = []
        seen_sections: set[str] = set()

        for bbox in all_bboxes:
            text = bbox.get("text", "")
            page = bbox.get("page_number")

            if not text or not page:
                continue

            # Try each pattern
            for pattern in SECTION_HEADER_PATTERNS:
                for match in pattern.finditer(text):
                    section_num = self._normalize_section(match.group(1))

                    # Skip if already seen
                    if section_num in seen_sections:
                        continue
                    seen_sections.add(section_num)

                    # Get title if available (group 2)
                    title = None
                    if match.lastindex and match.lastindex >= 2:
                        title = match.group(2).strip()

                    sections.append({
                        "document_id": document_id,
                        "matter_id": matter_id,
                        "section_number": section_num,
                        "page_number": page,
                        "section_title": title,
                        "confidence": 0.9,
                        "is_toc": False,
                        "bbox_id": str(bbox["id"]),
                    })

        if not sections:
            logger.info(
                "no_sections_found_in_document",
                document_id=document_id,
            )
            return 0

        # Delete existing entries for this document
        self.client.table("section_index").delete().eq(
            "document_id", document_id
        ).execute()

        # Insert new entries
        self.client.table("section_index").insert(sections).execute()

        logger.info(
            "document_sections_indexed",
            document_id=document_id,
            section_count=len(sections),
        )

        return len(sections)

    def _detect_toc_pages(self, document_id: str) -> list[int]:
        """Detect TOC pages in a document.

        Args:
            document_id: Document UUID.

        Returns:
            List of page numbers that are likely TOC pages.
        """
        toc_pages: set[int] = set()

        # Search first 20 pages for TOC keywords
        for keyword in TOC_KEYWORDS:
            result = (
                self.client.table("bounding_boxes")
                .select("page_number")
                .eq("document_id", document_id)
                .ilike("text", f"%{keyword}%")
                .lte("page_number", 20)
                .execute()
            )

            for row in result.data or []:
                toc_pages.add(row["page_number"])

        # If no TOC detected, assume first 10 pages
        if not toc_pages:
            return list(range(1, 11))

        # Extend to include consecutive pages
        if toc_pages:
            min_toc = min(toc_pages)
            max_toc = max(toc_pages)
            return list(range(min_toc, max_toc + 1))

        return list(toc_pages)

    def _save_toc_pages(self, document_id: str, pages: list[int]) -> None:
        """Save TOC pages to database.

        Args:
            document_id: Document UUID.
            pages: List of TOC page numbers.
        """
        # Delete existing
        self.client.table("toc_pages").delete().eq("document_id", document_id).execute()

        # Insert new
        entries = [
            {
                "document_id": document_id,
                "page_number": page,
                "confidence": 0.8,
                "detected_via": "keyword",
            }
            for page in pages
        ]

        if entries:
            self.client.table("toc_pages").insert(entries).execute()

    def _get_all_bboxes(
        self,
        document_id: str,
        min_page: int = 1,
    ) -> list[dict[str, Any]]:
        """Get all bounding boxes for a document.

        Args:
            document_id: Document UUID.
            min_page: Minimum page number to include.

        Returns:
            List of bounding box dictionaries.
        """
        all_bboxes: list[dict[str, Any]] = []
        offset = 0
        batch_size = 1000

        while True:
            result = (
                self.client.table("bounding_boxes")
                .select("id, page_number, text")
                .eq("document_id", document_id)
                .gte("page_number", min_page)
                .order("page_number")
                .range(offset, offset + batch_size - 1)
                .execute()
            )

            if not result.data:
                break

            all_bboxes.extend(result.data)

            if len(result.data) < batch_size:
                break

            offset += batch_size

        return all_bboxes

    def _normalize_section(self, section: str) -> str:
        """Normalize section number for consistent matching.

        Args:
            section: Raw section string.

        Returns:
            Normalized section number.
        """
        # Remove whitespace
        normalized = re.sub(r"\s+", "", section)
        # Normalize subsection format
        normalized = re.sub(r"\((\d+)\)", r"(\1)", normalized)
        return normalized.upper() if normalized[-1:].isalpha() else normalized

    def _get_base_section(self, section: str) -> str | None:
        """Extract base section number from compound section references.

        Handles:
        - "205A" -> "205"
        - "205A(1)" -> "205"
        - "138(1)" -> "138"
        - "102.(1A)" -> "102"

        Args:
            section: Normalized section string.

        Returns:
            Base section number or None if no simplification possible.
        """
        # Pattern to extract base numeric section
        # Matches: digits optionally followed by letter and/or parenthetical
        match = re.match(r"^(\d+)", section)
        if match:
            base = match.group(1)
            # Only return if different from input
            if base != section:
                return base
        return None

    def _is_old_act_reference(self, text: str) -> bool:
        """Check if text references an old/repealed Act.

        Args:
            text: Text to check (should be lowercase).

        Returns:
            True if text references an old Act.
        """
        for pattern in OLD_ACT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


@lru_cache(maxsize=1)
def get_section_index_service() -> SectionIndexService:
    """Get singleton SectionIndexService instance.

    Returns:
        SectionIndexService instance.
    """
    return SectionIndexService()
