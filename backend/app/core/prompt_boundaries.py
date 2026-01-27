"""Prompt Boundary Utilities for LLM Security.

Story 1.1: Implement Structured XML Prompt Boundaries

Provides XML boundary wrapping for LLM prompts to prevent prompt injection attacks.
All document content from user uploads MUST be wrapped in <document_content> tags
to ensure the LLM treats it as data, not instructions.

SECURITY: This is a critical security control. Adversarial text like
"Ignore previous instructions" in uploaded documents will be contained
within XML boundaries and processed as data, not commands.

ADR-001: Prompt isolation + LLM detection defense in depth.
"""

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# XML Boundary Tags
# =============================================================================

# Opening/closing tags for different content types
SYSTEM_OPEN = "<system>"
SYSTEM_CLOSE = "</system>"

DOCUMENT_CONTENT_OPEN = "<document_content>"
DOCUMENT_CONTENT_CLOSE = "</document_content>"

USER_QUERY_OPEN = "<user_query>"
USER_QUERY_CLOSE = "</user_query>"

CONTEXT_OPEN = "<context>"
CONTEXT_CLOSE = "</context>"

METADATA_OPEN = "<metadata>"
METADATA_CLOSE = "</metadata>"


# =============================================================================
# Sanitization Patterns
# =============================================================================

# Patterns that might indicate injection attempts (for logging/detection)
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"new\s+instructions?:\s*",
    r"system:\s*",
    r"assistant:\s*",
    r"</?(system|document_content|user_query|context)>",  # Nested tag attempts
    r"you\s+are\s+now\s+a\s+",
    r"act\s+as\s+(if\s+you\s+are\s+)?a\s+",
    r"pretend\s+(to\s+be|you\s+are)\s+",
    r"override\s+(your\s+)?(instructions?|rules?|guidelines?)",
]

# Compiled pattern for efficiency
_INJECTION_PATTERN = re.compile(
    "|".join(INJECTION_PATTERNS),
    re.IGNORECASE | re.MULTILINE,
)


# =============================================================================
# Core Boundary Functions
# =============================================================================


def wrap_document_content(content: str) -> str:
    """Wrap document content in XML boundaries for prompt injection protection.

    CRITICAL: All text extracted from user-uploaded documents MUST pass through
    this function before being included in any LLM prompt.

    Args:
        content: Raw text content from a document.

    Returns:
        Content wrapped in <document_content> tags.

    Example:
        >>> wrap_document_content("Contract dated Jan 15, 2024")
        '<document_content>Contract dated Jan 15, 2024</document_content>'
    """
    if not content:
        return f"{DOCUMENT_CONTENT_OPEN}{DOCUMENT_CONTENT_CLOSE}"

    # Escape any existing XML-like tags in the content to prevent nesting attacks
    sanitized = _escape_xml_tags(content)

    return f"{DOCUMENT_CONTENT_OPEN}{sanitized}{DOCUMENT_CONTENT_CLOSE}"


def wrap_user_query(query: str) -> str:
    """Wrap user query in XML boundaries.

    Args:
        query: User's question or search query.

    Returns:
        Query wrapped in <user_query> tags.

    Example:
        >>> wrap_user_query("Who are the parties in this case?")
        '<user_query>Who are the parties in this case?</user_query>'
    """
    if not query:
        return f"{USER_QUERY_OPEN}{USER_QUERY_CLOSE}"

    # Escape any XML-like tags in the query
    sanitized = _escape_xml_tags(query)

    return f"{USER_QUERY_OPEN}{sanitized}{USER_QUERY_CLOSE}"


def wrap_context(context: str, source: str | None = None) -> str:
    """Wrap context information (like retrieved chunks) in XML boundaries.

    Args:
        context: Context text (e.g., retrieved document excerpts).
        source: Optional source identifier for the context.

    Returns:
        Context wrapped in <context> tags with optional source attribute.

    Example:
        >>> wrap_context("The contract states...", source="doc_123_p1")
        '<context source="doc_123_p1">The contract states...</context>'
    """
    if not context:
        return f"{CONTEXT_OPEN}{CONTEXT_CLOSE}"

    sanitized = _escape_xml_tags(context)

    if source:
        return f'<context source="{_escape_attribute(source)}">{sanitized}</context>'

    return f"{CONTEXT_OPEN}{sanitized}{CONTEXT_CLOSE}"


def wrap_metadata(metadata: dict[str, Any]) -> str:
    """Wrap metadata in XML boundaries.

    Args:
        metadata: Dictionary of metadata key-value pairs.

    Returns:
        Metadata formatted as XML with <metadata> wrapper.

    Example:
        >>> wrap_metadata({"page": 1, "document": "contract.pdf"})
        '<metadata><page>1</page><document>contract.pdf</document></metadata>'
    """
    if not metadata:
        return f"{METADATA_OPEN}{METADATA_CLOSE}"

    parts = []
    for key, value in metadata.items():
        safe_key = _escape_xml_tags(str(key))
        safe_value = _escape_xml_tags(str(value))
        parts.append(f"<{safe_key}>{safe_value}</{safe_key}>")

    return f"{METADATA_OPEN}{''.join(parts)}{METADATA_CLOSE}"


# =============================================================================
# Compound Wrappers for Common Patterns
# =============================================================================


def format_document_excerpt(
    content: str,
    document_name: str | None = None,
    page_number: int | str | None = None,
    index: int | None = None,
) -> str:
    """Format a document excerpt with proper XML boundaries and metadata.

    This is the standard format for including document content in prompts.
    Used by RAG, citation extraction, entity extraction, and other engines.

    Args:
        content: Text content from the document.
        document_name: Name of the source document.
        page_number: Page number in the source document.
        index: Optional index number for referencing (e.g., [1], [2]).

    Returns:
        Formatted excerpt with XML boundaries.

    Example:
        >>> format_document_excerpt(
        ...     "The petitioner claims...",
        ...     document_name="Petition.pdf",
        ...     page_number=3,
        ...     index=1
        ... )
        '<excerpt index="1">
        <metadata><document>Petition.pdf</document><page>3</page></metadata>
        <document_content>The petitioner claims...</document_content>
        </excerpt>'
    """
    parts = []

    # Build metadata
    metadata = {}
    if document_name:
        metadata["document"] = document_name
    if page_number is not None:
        metadata["page"] = page_number

    # Open excerpt tag
    if index is not None:
        parts.append(f'<excerpt index="{index}">')
    else:
        parts.append("<excerpt>")

    # Add metadata if present
    if metadata:
        parts.append(wrap_metadata(metadata))

    # Add content
    parts.append(wrap_document_content(content))

    # Close excerpt
    parts.append("</excerpt>")

    return "\n".join(parts)


def format_multiple_excerpts(
    excerpts: list[dict[str, Any]],
) -> str:
    """Format multiple document excerpts for inclusion in a prompt.

    Args:
        excerpts: List of excerpt dicts with keys:
            - content: Text content (required)
            - document_name: Source document name
            - page_number: Page number
            Each excerpt will be numbered starting at 1.

    Returns:
        All excerpts formatted with XML boundaries, separated by newlines.
    """
    if not excerpts:
        return "<excerpts></excerpts>"

    formatted = []
    for i, excerpt in enumerate(excerpts, 1):
        formatted.append(
            format_document_excerpt(
                content=excerpt.get("content", ""),
                document_name=excerpt.get("document_name") or excerpt.get("documentName"),
                page_number=excerpt.get("page_number") or excerpt.get("pageNumber"),
                index=i,
            )
        )

    return f"<excerpts>\n{chr(10).join(formatted)}\n</excerpts>"


# =============================================================================
# Injection Detection (for Story 1.2)
# =============================================================================


def detect_injection_patterns(text: str) -> list[dict[str, Any]]:
    """Scan text for potential prompt injection patterns.

    This is a lightweight detection for logging/flagging purposes.
    Story 1.2 implements full LLM-based detection for suspicious documents.

    Args:
        text: Text to scan for injection patterns.

    Returns:
        List of detected patterns with match details.
    """
    if not text:
        return []

    detections = []
    for match in _INJECTION_PATTERN.finditer(text):
        detections.append({
            "pattern": match.group(),
            "start": match.start(),
            "end": match.end(),
            "context": text[max(0, match.start() - 30):min(len(text), match.end() + 30)],
        })

    if detections:
        logger.warning(
            "prompt_injection_patterns_detected",
            count=len(detections),
            patterns=[d["pattern"] for d in detections],
        )

    return detections


def has_injection_patterns(text: str) -> bool:
    """Quick check if text contains potential injection patterns.

    Args:
        text: Text to check.

    Returns:
        True if potential injection patterns found.
    """
    if not text:
        return False
    return bool(_INJECTION_PATTERN.search(text))


# =============================================================================
# Internal Helpers
# =============================================================================


def _escape_xml_tags(text: str) -> str:
    """Escape XML-like tags in text to prevent boundary escape attacks.

    Converts < and > to their escaped forms within the text content.
    This prevents adversarial content from breaking out of XML boundaries.

    Args:
        text: Text that may contain XML-like content.

    Returns:
        Text with < and > escaped.
    """
    if not text:
        return ""

    # Escape angle brackets to prevent tag injection
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    return text


def _escape_attribute(value: str) -> str:
    """Escape a value for use in an XML attribute.

    Args:
        value: Attribute value to escape.

    Returns:
        Escaped attribute value safe for XML.
    """
    if not value:
        return ""

    # Escape quotes and angle brackets
    value = value.replace("&", "&amp;")
    value = value.replace('"', "&quot;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")

    return value


# =============================================================================
# Legacy Compatibility
# =============================================================================


def wrap_content_for_prompt(
    content: str,
    content_type: str = "document",
) -> str:
    """Generic wrapper for backward compatibility.

    Args:
        content: Content to wrap.
        content_type: Type of content ("document", "query", "context").

    Returns:
        Appropriately wrapped content.
    """
    match content_type:
        case "document":
            return wrap_document_content(content)
        case "query":
            return wrap_user_query(content)
        case "context":
            return wrap_context(content)
        case _:
            # Default to document content for safety
            return wrap_document_content(content)
