"""OCR service module for Google Document AI integration.

This module provides OCR processing capabilities using Google Document AI,
including text extraction, bounding box extraction, confidence scoring,
Gemini-based validation for low-confidence results, and quality assessment.
"""

from app.services.ocr.bbox_extractor import extract_bounding_boxes
from app.services.ocr.confidence_calculator import (
    ConfidenceCalculatorError,
    calculate_document_confidence,
    update_document_confidence,
)
from app.services.ocr.gemini_validator import (
    GeminiOCRValidator,
    GeminiValidatorError,
    get_gemini_validator,
)
from app.services.ocr.human_review_service import (
    HumanReviewService,
    HumanReviewServiceError,
    get_human_review_service,
)
from app.services.ocr.pattern_corrector import (
    PatternCorrector,
    apply_pattern_corrections,
    get_pattern_corrector,
)
from app.services.ocr.processor import OCRProcessor, OCRServiceError, get_ocr_processor
from app.services.ocr.validation_extractor import (
    ValidationExtractor,
    ValidationExtractorError,
    get_validation_extractor,
)

__all__ = [
    # Core OCR
    "OCRProcessor",
    "OCRServiceError",
    "get_ocr_processor",
    "extract_bounding_boxes",
    # Validation
    "ValidationExtractor",
    "ValidationExtractorError",
    "get_validation_extractor",
    # Pattern correction
    "PatternCorrector",
    "apply_pattern_corrections",
    "get_pattern_corrector",
    # Gemini validation
    "GeminiOCRValidator",
    "GeminiValidatorError",
    "get_gemini_validator",
    # Human review
    "HumanReviewService",
    "HumanReviewServiceError",
    "get_human_review_service",
    # Confidence calculation
    "ConfidenceCalculatorError",
    "calculate_document_confidence",
    "update_document_confidence",
]
