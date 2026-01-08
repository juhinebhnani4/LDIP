"""Low-confidence word extraction for OCR validation.

Extracts words from bounding boxes that need validation based on
confidence thresholds and provides surrounding context.
"""

from functools import lru_cache

import structlog
from supabase import Client

from app.core.config import get_settings
from app.models.ocr_validation import LowConfidenceWord
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


class ValidationExtractorError(Exception):
    """Base exception for validation extractor operations."""

    def __init__(self, message: str, code: str = "EXTRACTOR_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationExtractor:
    """Service for extracting low-confidence words from bounding boxes.

    Identifies words that need validation based on confidence thresholds
    and extracts surrounding context for validation.
    """

    def __init__(self, client: Client | None = None):
        """Initialize validation extractor.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()
        settings = get_settings()
        self.gemini_threshold = settings.ocr_validation_gemini_threshold
        self.human_threshold = settings.ocr_validation_human_threshold
        self.context_chars = 50  # Characters of context before/after

    def extract_low_confidence_words(
        self,
        document_id: str,
    ) -> tuple[list[LowConfidenceWord], list[LowConfidenceWord]]:
        """Extract low-confidence words from document bounding boxes.

        Identifies words that need Gemini validation (<85% confidence)
        and words that need human review (<50% confidence).

        Args:
            document_id: Document UUID.

        Returns:
            Tuple of (words_for_gemini, words_for_human_review).
            words_for_gemini: Words with confidence < 85% (but >= 50%)
            words_for_human_review: Words with confidence < 50%

        Raises:
            ValidationExtractorError: If extraction fails.
        """
        if self.client is None:
            raise ValidationExtractorError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        logger.info(
            "validation_extraction_starting",
            document_id=document_id,
            gemini_threshold=self.gemini_threshold,
            human_threshold=self.human_threshold,
        )

        try:
            # Fetch all bounding boxes for the document, ordered by page and position
            result = self.client.table("bounding_boxes").select(
                "id, page_number, x, y, width, height, text, confidence"
            ).eq(
                "document_id", document_id
            ).order(
                "page_number"
            ).order(
                "y"
            ).order(
                "x"
            ).execute()

            if not result.data:
                logger.info(
                    "validation_extraction_no_boxes",
                    document_id=document_id,
                )
                return [], []

            # Build context by grouping by page
            pages: dict[int, list[dict]] = {}
            for box in result.data:
                page_num = box["page_number"]
                if page_num not in pages:
                    pages[page_num] = []
                pages[page_num].append(box)

            words_for_gemini: list[LowConfidenceWord] = []
            words_for_human: list[LowConfidenceWord] = []

            for page_num, boxes in pages.items():
                # Build full page text for context extraction
                page_text = " ".join(box["text"] for box in boxes if box["text"])

                for i, box in enumerate(boxes):
                    confidence = box.get("confidence")
                    text = box.get("text", "")

                    # Skip if no confidence or high confidence
                    if confidence is None or confidence >= self.gemini_threshold:
                        continue

                    # Skip empty text
                    if not text or not text.strip():
                        continue

                    # Extract surrounding context
                    context_before, context_after = self._extract_context(
                        boxes, i, page_text
                    )

                    word = LowConfidenceWord(
                        bbox_id=box["id"],
                        text=text,
                        confidence=confidence,
                        page=page_num,
                        context_before=context_before,
                        context_after=context_after,
                        x=box["x"],
                        y=box["y"],
                        width=box["width"],
                        height=box["height"],
                    )

                    # Route based on confidence threshold
                    if confidence < self.human_threshold:
                        words_for_human.append(word)
                    else:
                        words_for_gemini.append(word)

            logger.info(
                "validation_extraction_complete",
                document_id=document_id,
                total_boxes=len(result.data),
                gemini_words=len(words_for_gemini),
                human_words=len(words_for_human),
            )

            return words_for_gemini, words_for_human

        except Exception as e:
            logger.error(
                "validation_extraction_failed",
                document_id=document_id,
                error=str(e),
            )
            raise ValidationExtractorError(
                message=f"Failed to extract low-confidence words: {e!s}",
                code="EXTRACTION_FAILED"
            ) from e

    def _extract_context(
        self,
        boxes: list[dict],
        current_index: int,
        page_text: str,
    ) -> tuple[str, str]:
        """Extract surrounding context for a word.

        Args:
            boxes: List of bounding boxes on the page.
            current_index: Index of the current word.
            page_text: Full text of the page.

        Returns:
            Tuple of (context_before, context_after).
        """
        current_text = boxes[current_index].get("text", "")

        # Find position of current text in page text
        try:
            pos = page_text.find(current_text)
            if pos == -1:
                # Fallback to using adjacent boxes
                return self._extract_context_from_adjacent(boxes, current_index)

            # Extract context before
            start = max(0, pos - self.context_chars)
            context_before = page_text[start:pos].strip()

            # Extract context after
            end_pos = pos + len(current_text)
            end = min(len(page_text), end_pos + self.context_chars)
            context_after = page_text[end_pos:end].strip()

            return context_before, context_after

        except Exception:
            # Fallback to adjacent boxes
            return self._extract_context_from_adjacent(boxes, current_index)

    def _extract_context_from_adjacent(
        self,
        boxes: list[dict],
        current_index: int,
    ) -> tuple[str, str]:
        """Extract context from adjacent bounding boxes.

        Fallback method when position-based extraction fails.

        Args:
            boxes: List of bounding boxes on the page.
            current_index: Index of the current word.

        Returns:
            Tuple of (context_before, context_after).
        """
        context_before_parts: list[str] = []
        context_after_parts: list[str] = []
        chars_before = 0
        chars_after = 0

        # Collect words before (going backwards)
        for i in range(current_index - 1, -1, -1):
            text = boxes[i].get("text", "")
            if chars_before + len(text) > self.context_chars:
                # Truncate to fit
                remaining = self.context_chars - chars_before
                if remaining > 0:
                    context_before_parts.insert(0, text[-remaining:])
                break
            context_before_parts.insert(0, text)
            chars_before += len(text) + 1  # +1 for space

        # Collect words after
        for i in range(current_index + 1, len(boxes)):
            text = boxes[i].get("text", "")
            if chars_after + len(text) > self.context_chars:
                # Truncate to fit
                remaining = self.context_chars - chars_after
                if remaining > 0:
                    context_after_parts.append(text[:remaining])
                break
            context_after_parts.append(text)
            chars_after += len(text) + 1  # +1 for space

        return (
            " ".join(context_before_parts),
            " ".join(context_after_parts),
        )

    def get_words_by_page(
        self,
        words: list[LowConfidenceWord],
    ) -> dict[int, list[LowConfidenceWord]]:
        """Group words by page number.

        Useful for batch processing Gemini requests by page.

        Args:
            words: List of low-confidence words.

        Returns:
            Dictionary mapping page numbers to words.
        """
        pages: dict[int, list[LowConfidenceWord]] = {}
        for word in words:
            if word.page not in pages:
                pages[word.page] = []
            pages[word.page].append(word)
        return pages


@lru_cache(maxsize=1)
def get_validation_extractor() -> ValidationExtractor:
    """Get singleton validation extractor instance.

    Returns:
        ValidationExtractor instance.
    """
    return ValidationExtractor()
