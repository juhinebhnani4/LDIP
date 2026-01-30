"""Regex patterns for Indian legal citation extraction.

Patterns cover various formats:
- Section 138 of Negotiable Instruments Act, 1881
- u/s 302 IPC
- S. 420 of the Indian Penal Code
- Under Section 138(1)(a) of NI Act
- धारा 302 भारतीय दंड संहिता (Hindi)
"""

import re
from typing import NamedTuple


class CitationMatch(NamedTuple):
    """A regex match for a citation."""
    section: str
    subsection: str | None
    act_name: str
    raw_text: str
    start: int
    end: int


# =============================================================================
# Citation Regex Patterns
# =============================================================================

CITATION_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Pattern 1: "Section X of [Act Name], Year"
    # Examples: "Section 138 of Negotiable Instruments Act, 1881"
    (
        "section_of",
        re.compile(
            r"(?:Section|Sec\.?|S\.)\s*"
            r"(\d+[A-Za-z]?)"                          # Section number
            r"(?:\s*\(([^)]+)\))?"                     # Optional subsection
            r"\s+(?:of\s+)?(?:the\s+)?"
            r"([A-Za-z][A-Za-z\s,&'-]+?"               # Act name
            r"(?:Act|Code|Sanhita|Adhiniyam|Rules|Regulations))"
            r"(?:[,\s]+(\d{4}))?",                     # Optional year
            re.IGNORECASE
        )
    ),

    # Pattern 2: "u/s X [Act]" (under section)
    # Examples: "u/s 302 IPC", "u/s. 138 NI Act"
    (
        "under_section",
        re.compile(
            r"(?:u/s\.?|under\s+section)\s*"
            r"(\d+[A-Za-z]?)"                          # Section number
            r"(?:\s*\(([^)]+)\))?"                     # Optional subsection
            r"(?:\s+(?:of\s+)?(?:the\s+)?)?"
            r"([A-Za-z][A-Za-z\s,&'-]*?"
            r"(?:Act|Code|IPC|CrPC|CPC|NI Act|BNS|BNSS|BSA))",
            re.IGNORECASE
        )
    ),

    # Pattern 3: "S. X [Act Name]" (abbreviated section)
    # Examples: "S. 420 Indian Penal Code", "Ss. 302, 307 IPC"
    (
        "abbreviated",
        re.compile(
            r"(?:Ss?\.)\s*"
            r"(\d+[A-Za-z]?(?:\s*,\s*\d+[A-Za-z]?)*)"  # Section(s)
            r"(?:\s*\(([^)]+)\))?"                     # Optional subsection
            r"\s+(?:of\s+)?(?:the\s+)?"
            r"([A-Za-z][A-Za-z\s,&'-]+?"
            r"(?:Act|Code|IPC|CrPC|CPC))"
            r"(?:[,\s]+(\d{4}))?",
            re.IGNORECASE
        )
    ),

    # Pattern 4: "Under the provisions of [Act] Section X"
    # Examples: "Under the provisions of Companies Act, 2013, Section 185"
    (
        "provisions_of",
        re.compile(
            r"(?:under\s+)?(?:the\s+)?provisions?\s+of\s+"
            r"(?:the\s+)?"
            r"([A-Za-z][A-Za-z\s,&'-]+?"
            r"(?:Act|Code|Sanhita|Adhiniyam))"
            r"(?:[,\s]+(\d{4}))?"
            r"[,\s]+(?:Section|Sec\.?|S\.)\s*"
            r"(\d+[A-Za-z]?)"
            r"(?:\s*\(([^)]+)\))?",
            re.IGNORECASE
        )
    ),

    # Pattern 5: Article references (Constitution)
    # Examples: "Article 21 of the Constitution", "Art. 14"
    (
        "article",
        re.compile(
            r"(?:Article|Art\.)\s*"
            r"(\d+[A-Za-z]?)"
            r"(?:\s*\(([^)]+)\))?"
            r"(?:\s+(?:of\s+)?(?:the\s+)?"
            r"(Constitution(?:\s+of\s+India)?|Indian\s+Constitution))?",
            re.IGNORECASE
        )
    ),

    # Pattern 6: Rule references
    # Examples: "Rule 3 of CCS Rules", "Order XXI Rule 97 CPC"
    (
        "rule",
        re.compile(
            r"(?:Order\s+[IVXLCDM]+\s+)?"
            r"(?:Rule|R\.)\s*"
            r"(\d+[A-Za-z]?)"
            r"(?:\s*\(([^)]+)\))?"
            r"(?:\s+(?:of\s+)?(?:the\s+)?"
            r"([A-Za-z][A-Za-z\s,&'-]+?Rules))"
            r"(?:[,\s]+(\d{4}))?",
            re.IGNORECASE
        )
    ),

    # Pattern 7: Clause references
    # Examples: "Clause 49 of Listing Agreement"
    (
        "clause",
        re.compile(
            r"(?:Clause|Cl\.)\s*"
            r"(\d+[A-Za-z]?)"
            r"(?:\s*\(([^)]+)\))?"
            r"(?:\s+(?:of\s+)?(?:the\s+)?"
            r"([A-Za-z][A-Za-z\s,&'-]+))?",
            re.IGNORECASE
        )
    ),

    # Pattern 8: Hindi citations (Bharatiya codes)
    # Examples: "धारा 302 भारतीय दंड संहिता"
    (
        "hindi",
        re.compile(
            r"धारा\s*"
            r"(\d+[A-Za-z]?)"
            r"(?:\s*\(([^)]+)\))?"
            r"\s+"
            r"(भारतीय[^\d]+(?:संहिता|अधिनियम))",
            re.UNICODE
        )
    ),
]


def extract_citations_regex(text: str) -> list[CitationMatch]:
    """Extract citations using regex patterns.

    Args:
        text: Text to search for citations

    Returns:
        List of CitationMatch objects
    """
    matches: list[CitationMatch] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern_name, pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())

            # Skip overlapping matches
            if any(
                s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1]
                for s in seen_spans
            ):
                continue

            seen_spans.add(span)

            # Extract groups based on pattern
            groups = match.groups()

            if pattern_name == "provisions_of":
                # Different group order
                act_name = groups[0]
                year = groups[1]
                section = groups[2]
                subsection = groups[3] if len(groups) > 3 else None
            elif pattern_name == "article":
                section = groups[0]
                subsection = groups[1]
                act_name = groups[2] or "Constitution of India"
                year = None
            else:
                section = groups[0]
                subsection = groups[1] if len(groups) > 1 else None
                act_name = groups[2] if len(groups) > 2 else ""
                year = groups[3] if len(groups) > 3 else None

            # Clean up act name
            if act_name:
                act_name = act_name.strip(" ,")
                if year:
                    act_name = f"{act_name}, {year}"

            matches.append(CitationMatch(
                section=section.strip() if section else "",
                subsection=subsection.strip() if subsection else None,
                act_name=act_name,
                raw_text=match.group(0),
                start=match.start(),
                end=match.end(),
            ))

    return matches


def is_valid_section(section: str) -> bool:
    """Check if section number is valid.

    Args:
        section: Section number string

    Returns:
        True if valid section format
    """
    if not section:
        return False

    # Must start with a digit
    if not section[0].isdigit():
        return False

    # Check format: digits optionally followed by letter
    return bool(re.match(r"^\d+[A-Za-z]?$", section))
