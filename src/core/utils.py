"""Utility functions for Jaanch Lite."""

import re
import hashlib
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


def normalize_act_name(name: str) -> str:
    """Normalize act name for matching.

    Examples:
        "Negotiable Instruments Act, 1881" -> "negotiable_instruments_act_1881"
        "IPC" -> "ipc"
        "The Companies Act, 2013" -> "companies_act_2013"
    """
    # Remove common prefixes
    name = re.sub(r"^(the|an?)\s+", "", name, flags=re.IGNORECASE)

    # Remove punctuation except hyphens
    name = re.sub(r"[^\w\s-]", "", name)

    # Replace spaces/hyphens with underscores
    name = re.sub(r"[\s-]+", "_", name)

    # Lowercase
    return name.lower().strip("_")


def extract_year_from_act(name: str) -> Optional[int]:
    """Extract year from act name.

    Examples:
        "Negotiable Instruments Act, 1881" -> 1881
        "Companies Act 2013" -> 2013
    """
    match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", name)
    if match:
        return int(match.group(1))
    return None


def generate_chunk_id(text: str, page: int, index: int) -> str:
    """Generate unique chunk ID.

    Args:
        text: Chunk text content
        page: Page number
        index: Chunk index on page

    Returns:
        Unique chunk ID like "chunk_p5_i3_a1b2c3d4"
    """
    content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"chunk_p{page}_i{index}_{content_hash}"


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Estimate token count for text.

    Simple estimation: ~4 chars per token for English.
    For accurate counts, use tiktoken.
    """
    # Simple estimation
    return len(text) // 4


def truncate_text(text: str, max_chars: int = 500, suffix: str = "...") -> str:
    """Truncate text to max chars with suffix."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def clean_text_for_embedding(text: str) -> str:
    """Clean text before generating embeddings.

    - Remove excessive whitespace
    - Remove special characters that don't add meaning
    - Normalize unicode
    """
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    return text.strip()


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, create if not."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, max_length: int = 100) -> str:
    """Convert string to safe filename.

    Args:
        name: Original name
        max_length: Maximum filename length

    Returns:
        Safe filename string
    """
    # Remove/replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)

    # Remove leading/trailing spaces and dots
    safe = safe.strip(". ")

    # Truncate if too long
    if len(safe) > max_length:
        safe = safe[:max_length]

    return safe or "unnamed"


def format_citation(act_name: str, section: str, subsection: Optional[str] = None) -> str:
    """Format a citation for display.

    Examples:
        ("Negotiable Instruments Act, 1881", "138", None) -> "Section 138 of Negotiable Instruments Act, 1881"
        ("IPC", "302", "(1)") -> "Section 302(1) of IPC"
    """
    section_str = f"Section {section}"
    if subsection:
        section_str += subsection

    return f"{section_str} of {act_name}"
