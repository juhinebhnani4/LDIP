"""OCR Noise Cleaner for post-processing engine outputs.

Cleans common OCR artifacts from document processing:
- Non-Latin script garbage (random Hindi/Gujarati/etc. characters)
- Repeated character patterns
- Control characters and excessive whitespace
- Malformed Unicode sequences

CRITICAL: Preserves intentional non-Latin content (e.g., proper names in other scripts)
by only removing isolated garbage sequences, not coherent text.
"""

import re
import unicodedata
from functools import lru_cache

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# OCR Noise Patterns
# =============================================================================

# Pattern: Isolated Devanagari/Gujarati characters mixed with Latin text
# Matches: single non-Latin chars or short sequences (1-5 chars) surrounded by Latin
MIXED_SCRIPT_NOISE = re.compile(
    r'(?<=[a-zA-Z0-9\s.,;:!?\-])'  # Preceded by Latin/punctuation
    r'[\u0900-\u097F\u0A80-\u0AFF\u0980-\u09FF]{1,5}'  # Short Devanagari/Gujarati/Bengali
    r'(?=[a-zA-Z0-9\s.,;:!?\-])',  # Followed by Latin/punctuation
    re.UNICODE
)

# Pattern: Repeated characters (OCR stutter) - e.g., "aaaaaaa" or "======"
REPEATED_CHARS = re.compile(r'(.)\1{5,}')

# Pattern: Excessive whitespace
EXCESSIVE_WHITESPACE = re.compile(r'[ \t]{3,}')

# Pattern: Multiple newlines
EXCESSIVE_NEWLINES = re.compile(r'\n{4,}')

# Pattern: Random special characters sequences (OCR garbage)
SPECIAL_CHAR_GARBAGE = re.compile(r'[^\w\s.,;:!?\-\'\"(){}[\]@#$%&*+=/<>]{3,}')

# Pattern: Repeated punctuation (OCR stutter) - e.g., "***", ":::", "..."
# These are common OCR artifacts from scanned legal documents
REPEATED_PUNCTUATION = re.compile(r'([.:*\'\"]{2,}\s*){2,}')

# Pattern: Mixed punctuation gibberish - sequences like "..::.. : *** **"
# Matches: punctuation-heavy sequences with low alphanumeric ratio
PUNCTUATION_GIBBERISH = re.compile(
    r'(?<![a-zA-Z])'  # Not preceded by letter
    r'[.:*\'\"_\-,;!?\s]{6,}'  # 6+ chars of punctuation/space mix
    r'(?![a-zA-Z])',  # Not followed by letter
    re.UNICODE
)

# Pattern: Asterisk sequences (common OCR artifact)
ASTERISK_NOISE = re.compile(r'\*{2,}')

# Pattern: Isolated box drawing characters (common OCR error)
BOX_DRAWING = re.compile(r'[\u2500-\u257F]+')

# Pattern: Isolated combining diacritical marks
ORPHAN_DIACRITICS = re.compile(r'[\u0300-\u036F]+(?!\w)')

# Pattern: PDF artifact characters
PDF_ARTIFACTS = re.compile(r'[\ufeff\u200b\u200c\u200d\u2028\u2029]+')


# =============================================================================
# OCR Cleaner Implementation
# =============================================================================

class OCRCleaner:
    """Cleans OCR noise from text while preserving meaningful content.

    Example:
        >>> cleaner = get_ocr_cleaner()
        >>> cleaned = cleaner.clean("The date was 1992 ોોતત at which time...")
        >>> cleaned
        'The date was 1992 at which time...'
    """

    def __init__(self, aggressive: bool = False) -> None:
        """Initialize OCR cleaner.

        Args:
            aggressive: If True, use more aggressive cleaning (may remove
                       some valid content). Default False for safety.
        """
        self.aggressive = aggressive
        logger.debug("ocr_cleaner_initialized", aggressive=aggressive)

    def clean(self, text: str) -> str:
        """Clean OCR noise from text.

        Args:
            text: Text to clean.

        Returns:
            Cleaned text with OCR artifacts removed.
        """
        if not text:
            return text

        original_length = len(text)
        cleaned = text

        # Step 1: Remove PDF artifacts (zero-width chars, BOM, etc.)
        cleaned = PDF_ARTIFACTS.sub('', cleaned)

        # Step 2: Remove isolated box drawing characters
        cleaned = BOX_DRAWING.sub(' ', cleaned)

        # Step 3: Remove orphan diacritical marks
        cleaned = ORPHAN_DIACRITICS.sub('', cleaned)

        # Step 4: Remove mixed script noise (isolated non-Latin in Latin context)
        cleaned = MIXED_SCRIPT_NOISE.sub(' ', cleaned)

        # Step 5: Collapse repeated characters (>5 same char)
        cleaned = REPEATED_CHARS.sub(r'\1\1', cleaned)

        # Step 6: Remove punctuation-based OCR artifacts (always applied)
        # These patterns catch garbage like "...:::... : *** **..'' ****"
        cleaned = ASTERISK_NOISE.sub(' ', cleaned)
        cleaned = REPEATED_PUNCTUATION.sub(' ', cleaned)
        cleaned = PUNCTUATION_GIBBERISH.sub(' ', cleaned)

        # Step 7: Remove special character garbage sequences (aggressive only)
        if self.aggressive:
            cleaned = SPECIAL_CHAR_GARBAGE.sub(' ', cleaned)

        # Step 8: Normalize whitespace
        cleaned = EXCESSIVE_WHITESPACE.sub(' ', cleaned)
        cleaned = EXCESSIVE_NEWLINES.sub('\n\n', cleaned)

        # Step 9: Strip and normalize
        cleaned = cleaned.strip()

        # Log if significant cleaning occurred
        removed_chars = original_length - len(cleaned)
        if removed_chars > 0:
            removal_pct = (removed_chars / original_length) * 100
            if removal_pct > 5:
                logger.info(
                    "ocr_cleaning_significant",
                    original_length=original_length,
                    cleaned_length=len(cleaned),
                    removed_chars=removed_chars,
                    removal_pct=round(removal_pct, 2),
                )

        return cleaned

    def clean_for_display(self, text: str) -> str:
        """Clean text for display in UI (more aggressive).

        Uses stricter cleaning rules appropriate for user-facing content.

        Args:
            text: Text to clean.

        Returns:
            Cleaned text suitable for display.
        """
        # Use aggressive cleaning for display
        aggressive_cleaner = OCRCleaner(aggressive=True)
        cleaned = aggressive_cleaner.clean(text)

        # Additional display-specific cleaning
        # Remove any remaining non-printable characters
        cleaned = ''.join(
            c for c in cleaned
            if c.isprintable() or c in '\n\t'
        )

        return cleaned

    def contains_noise(self, text: str) -> bool:
        """Check if text contains likely OCR noise.

        Args:
            text: Text to check.

        Returns:
            True if text likely contains OCR artifacts.
        """
        if not text:
            return False

        # Check for mixed script patterns
        if MIXED_SCRIPT_NOISE.search(text):
            return True

        # Check for repeated character patterns
        if REPEATED_CHARS.search(text):
            return True

        # Check for punctuation-based OCR artifacts
        if REPEATED_PUNCTUATION.search(text):
            return True
        if PUNCTUATION_GIBBERISH.search(text):
            return True
        if ASTERISK_NOISE.search(text):
            return True

        # Check for box drawing characters
        if BOX_DRAWING.search(text):
            return True

        # Check for excessive special characters
        special_char_count = sum(
            1 for c in text
            if not c.isalnum() and not c.isspace() and c not in '.,;:!?\-\'"(){}[]'
        )
        if len(text) > 0 and (special_char_count / len(text)) > 0.1:
            return True

        return False


# =============================================================================
# Factory Function
# =============================================================================

@lru_cache(maxsize=1)
def get_ocr_cleaner(aggressive: bool = False) -> OCRCleaner:
    """Get singleton OCR cleaner instance.

    Args:
        aggressive: Whether to use aggressive cleaning.

    Returns:
        OCRCleaner instance.
    """
    return OCRCleaner(aggressive=aggressive)


# =============================================================================
# Convenience Functions
# =============================================================================

def clean_ocr_text(text: str) -> str:
    """Clean OCR noise from text (convenience function).

    Args:
        text: Text to clean.

    Returns:
        Cleaned text.
    """
    return get_ocr_cleaner().clean(text)


def clean_for_display(text: str) -> str:
    """Clean text for display (convenience function).

    Args:
        text: Text to clean.

    Returns:
        Cleaned text suitable for display.
    """
    return get_ocr_cleaner().clean_for_display(text)
