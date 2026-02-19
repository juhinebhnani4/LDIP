"""Shared Docling converter provider.

Issue #4 fix: Consolidates duplicate Docling converter instances.

Both LayoutExtractor and TableExtractor use Docling with identical configuration.
This module provides a singleton converter to avoid:
- Duplicate ML model loading
- Memory waste from multiple instances
- Potential race conditions

Usage:
    from app.services.table_extraction.docling_provider import get_docling_converter

    converter = get_docling_converter()
    result = converter.convert(str(file_path))
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

logger = structlog.get_logger(__name__)

# Minimum supported Docling version
MIN_DOCLING_VERSION = "2.0.0"


class DoclingProviderError(Exception):
    """Exception raised when Docling initialization fails."""

    def __init__(
        self,
        message: str,
        code: str = "DOCLING_PROVIDER_ERROR",
        is_retryable: bool = False,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class DoclingProvider:
    """Singleton provider for Docling DocumentConverter.

    Manages a single shared Docling converter instance with:
    - Lazy initialization (only loads when first used)
    - Version validation
    - Consistent configuration (table structure enabled, OCR disabled)
    """

    _instance: DoclingProvider | None = None
    _converter: DocumentConverter | None = None

    def __new__(cls) -> DoclingProvider:
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize provider (only runs once due to singleton)."""
        self._settings = get_settings()

    @property
    def converter(self) -> DocumentConverter:
        """Get or create the shared Docling converter.

        Returns:
            DocumentConverter instance configured for PDF processing.

        Raises:
            DoclingProviderError: If Docling cannot be initialized.
        """
        if self._converter is None:
            self._converter = self._create_converter()
        return self._converter

    def _create_converter(self) -> DocumentConverter:
        """Create and configure the Docling converter.

        Returns:
            Configured DocumentConverter.

        Raises:
            DoclingProviderError: If initialization fails.
        """
        try:
            # Validate Docling version
            import docling  # noqa: F401
            from importlib.metadata import version as pkg_version
            from packaging import version

            docling_version = pkg_version("docling")
            if version.parse(docling_version) < version.parse(MIN_DOCLING_VERSION):
                logger.warning(
                    "docling_version_outdated",
                    installed=docling_version,
                    required=MIN_DOCLING_VERSION,
                )

            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            pipeline_options = PdfPipelineOptions()
            # Enable table structure detection
            pipeline_options.do_table_structure = True
            # Disable OCR - we use Google Document AI for text extraction
            pipeline_options.do_ocr = False
            # Safety timeout for large documents (prevents hung processes)
            # 120 seconds is generous - 400 pages typically takes 2-4 seconds
            pipeline_options.document_timeout = 120.0

            # Create format option for PDF with our pipeline options
            pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)

            converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={InputFormat.PDF: pdf_format_option},
            )

            logger.info(
                "docling_provider_initialized",
                docling_version=docling_version,
            )

            return converter

        except ImportError as e:
            logger.error("docling_import_failed", error=str(e))
            raise DoclingProviderError(
                "Docling not installed. Run: pip install docling",
                code="DOCLING_NOT_INSTALLED",
                is_retryable=False,
            ) from e

        except Exception as e:
            logger.error("docling_provider_init_failed", error=str(e))
            raise DoclingProviderError(
                f"Failed to initialize Docling: {e}",
                code="INIT_FAILED",
            ) from e

    def is_available(self) -> bool:
        """Check if Docling is available without initializing.

        Returns:
            True if Docling can be imported.
        """
        try:
            import docling  # noqa: F401

            return True
        except ImportError:
            return False


@lru_cache(maxsize=1)
def get_docling_provider() -> DoclingProvider:
    """Get the singleton DoclingProvider instance.

    Returns:
        DoclingProvider instance.
    """
    return DoclingProvider()


def get_docling_converter() -> DocumentConverter:
    """Get the shared Docling converter (convenience function).

    Returns:
        Shared DocumentConverter instance.

    Raises:
        DoclingProviderError: If Docling cannot be initialized.
    """
    return get_docling_provider().converter
