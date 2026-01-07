"""OCR service module for Google Document AI integration.

This module provides OCR processing capabilities using Google Document AI,
including text extraction, bounding box extraction, and confidence scoring.
"""

from app.services.ocr.bbox_extractor import extract_bounding_boxes
from app.services.ocr.processor import OCRProcessor, OCRServiceError, get_ocr_processor

__all__ = [
    "OCRProcessor",
    "OCRServiceError",
    "get_ocr_processor",
    "extract_bounding_boxes",
]
