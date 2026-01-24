"""Data quality validation and metrics for extraction engines.

This module provides utilities to track and validate source page linkage
across all extraction engines (citations, timeline, entities).

Key principles:
1. NEVER silently fall back to page 1 - allow NULL and handle in UI
2. Log warnings when source_page is missing for records with document_id
3. Track metrics for monitoring data quality

Usage:
    from app.core.data_quality import (
        validate_source_page,
        DataQualityMetrics,
        log_missing_source_page,
    )

    # In extraction code
    source_page = validate_source_page(
        page_number=chunk.page_number,
        context="citation_extraction",
        document_id=doc_id,
        record_id=citation_id,
    )

    # Track metrics
    metrics = DataQualityMetrics("citation_engine")
    metrics.record(has_source_page=bool(source_page), has_bbox=bool(bbox_ids))
    metrics.report()
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DataQualityMetrics:
    """Track data quality metrics for an extraction engine.

    Example:
        metrics = DataQualityMetrics("timeline_extraction")
        for event in events:
            metrics.record(
                has_source_page=event.source_page is not None,
                has_bbox=bool(event.source_bbox_ids),
            )
        summary = metrics.report()
    """

    engine_name: str
    total_records: int = 0
    with_source_page: int = 0
    with_bbox_ids: int = 0
    null_source_page: int = 0
    _logged: bool = field(default=False, repr=False)

    def record(
        self,
        has_source_page: bool,
        has_bbox: bool = False,
    ) -> None:
        """Record a single record's data quality.

        Args:
            has_source_page: Whether the record has a valid source_page.
            has_bbox: Whether the record has bbox_ids for highlighting.
        """
        self.total_records += 1
        if has_source_page:
            self.with_source_page += 1
        else:
            self.null_source_page += 1
        if has_bbox:
            self.with_bbox_ids += 1

    def report(self) -> dict[str, Any]:
        """Generate and log a quality report.

        Returns:
            Dictionary with quality metrics.
        """
        if self.total_records == 0:
            return {
                "engine": self.engine_name,
                "total_records": 0,
                "source_page_coverage": 0,
                "bbox_coverage": 0,
            }

        source_page_coverage = self.with_source_page / self.total_records
        bbox_coverage = self.with_bbox_ids / self.total_records

        report = {
            "engine": self.engine_name,
            "total_records": self.total_records,
            "with_source_page": self.with_source_page,
            "null_source_page": self.null_source_page,
            "source_page_coverage": round(source_page_coverage, 3),
            "with_bbox_ids": self.with_bbox_ids,
            "bbox_coverage": round(bbox_coverage, 3),
        }

        # Log warning if coverage is low
        if not self._logged:
            if source_page_coverage < 0.8 and self.total_records > 5:
                logger.warning(
                    "low_source_page_coverage",
                    engine=self.engine_name,
                    coverage=f"{source_page_coverage:.1%}",
                    total=self.total_records,
                    missing=self.null_source_page,
                )
            elif source_page_coverage < 1.0 and self.total_records > 0:
                logger.info(
                    "data_quality_report",
                    engine=self.engine_name,
                    source_page_coverage=f"{source_page_coverage:.1%}",
                    bbox_coverage=f"{bbox_coverage:.1%}",
                    total=self.total_records,
                )
            self._logged = True

        return report


def validate_source_page(
    page_number: int | None,
    context: str,
    document_id: str | None = None,
    record_id: str | None = None,
    record_type: str = "record",
) -> int | None:
    """Validate and return source page, logging if missing.

    This function replaces the pattern `page_number or 1` which silently
    creates incorrect data. Instead, it:
    1. Returns the page_number if valid
    2. Returns None if missing (allows proper UI handling)
    3. Logs a warning for tracking

    Args:
        page_number: The source page number (may be None).
        context: Where this validation is happening (for logging).
        document_id: Optional document ID for context.
        record_id: Optional record ID for context.
        record_type: Type of record (citation, event, entity).

    Returns:
        The page_number if valid, None otherwise.
    """
    if page_number is not None and page_number > 0:
        return page_number

    # Log warning for missing source page when we have a document
    if document_id:
        logger.debug(
            "missing_source_page",
            context=context,
            record_type=record_type,
            document_id=document_id[:8] if document_id else None,
            record_id=record_id[:8] if record_id else None,
        )

    return None


def log_missing_source_page(
    context: str,
    document_id: str | None = None,
    record_id: str | None = None,
    additional_info: dict | None = None,
) -> None:
    """Log a warning for missing source page.

    Use this when you need to log without validation logic.

    Args:
        context: Where this is happening.
        document_id: Optional document ID.
        record_id: Optional record ID.
        additional_info: Additional context to log.
    """
    logger.warning(
        "source_page_missing",
        context=context,
        document_id=document_id[:8] if document_id else None,
        record_id=record_id[:8] if record_id else None,
        **(additional_info or {}),
    )


def get_safe_page_for_navigation(
    source_page: int | None,
    fallback_message: str = "Page unknown",
) -> tuple[int, bool]:
    """Get a page number safe for navigation with confidence flag.

    For UI components that MUST have a page number, this provides
    a fallback while indicating it's uncertain.

    Args:
        source_page: The source page (may be None).
        fallback_message: Message to log if falling back.

    Returns:
        Tuple of (page_number, is_confident).
        - page_number: The page to navigate to (1 if unknown)
        - is_confident: Whether we're confident this is correct
    """
    if source_page is not None and source_page > 0:
        return (source_page, True)

    return (1, False)


# SQL queries for monitoring data quality
MONITORING_QUERIES = {
    "events_missing_source_page": """
        SELECT
            matter_id,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE source_page IS NULL) as null_pages,
            ROUND(
                COUNT(*) FILTER (WHERE source_page IS NULL)::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            ) as null_pct
        FROM events
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY matter_id
        HAVING COUNT(*) FILTER (WHERE source_page IS NULL)::numeric
               / NULLIF(COUNT(*), 0) > 0.3
        ORDER BY null_pct DESC;
    """,
    "citations_page_1_concentration": """
        SELECT
            matter_id,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE source_page = 1) as page_1_count,
            ROUND(
                COUNT(*) FILTER (WHERE source_page = 1)::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            ) as page_1_pct
        FROM citations
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY matter_id
        HAVING COUNT(*) > 10
           AND COUNT(*) FILTER (WHERE source_page = 1)::numeric
               / NULLIF(COUNT(*), 0) > 0.5
        ORDER BY page_1_pct DESC;
    """,
    "chunks_missing_page_number": """
        SELECT
            d.matter_id,
            COUNT(*) as total_chunks,
            COUNT(*) FILTER (WHERE c.page_number IS NULL) as null_pages,
            ROUND(
                COUNT(*) FILTER (WHERE c.page_number IS NULL)::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            ) as null_pct
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.created_at > NOW() - INTERVAL '7 days'
        GROUP BY d.matter_id
        HAVING COUNT(*) FILTER (WHERE c.page_number IS NULL)::numeric
               / NULLIF(COUNT(*), 0) > 0.2
        ORDER BY null_pct DESC;
    """,
}
