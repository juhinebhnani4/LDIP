"""Redis Pub/Sub service for real-time status updates.

Provides document processing status broadcasting using Redis pub/sub
for real-time frontend updates.
"""

import json
from datetime import datetime
from functools import lru_cache

import redis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class PubSubServiceError(Exception):
    """Base exception for pub/sub operations."""

    def __init__(self, message: str, code: str = "PUBSUB_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class PubSubService:
    """Service for Redis pub/sub operations.

    Enables real-time broadcasting of document processing status
    to frontend clients via WebSocket or SSE.
    """

    # Channel naming convention per architecture: matter:{matter_id}:document:{document_id}:status
    CHANNEL_PATTERN = "matter:{matter_id}:document:{document_id}:status"

    def __init__(self, redis_url: str | None = None):
        """Initialize pub/sub service.

        Args:
            redis_url: Optional Redis URL. Uses settings if not provided.
        """
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """Get or create Redis client.

        Returns:
            Redis client instance.
        """
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                )
            except Exception as e:
                logger.error("redis_client_init_failed", error=str(e))
                raise PubSubServiceError(
                    f"Failed to connect to Redis: {e}",
                    code="REDIS_CONNECTION_FAILED"
                ) from e
        return self._client

    def _get_channel_name(self, matter_id: str, document_id: str) -> str:
        """Generate channel name for a document.

        Args:
            matter_id: Matter UUID.
            document_id: Document UUID.

        Returns:
            Channel name string.
        """
        return self.CHANNEL_PATTERN.format(
            matter_id=matter_id,
            document_id=document_id,
        )

    def publish_document_status(
        self,
        matter_id: str,
        document_id: str,
        status: str,
        page_count: int | None = None,
        ocr_confidence: float | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Publish document processing status update.

        Args:
            matter_id: Matter UUID.
            document_id: Document UUID.
            status: New status value.
            page_count: Number of pages (on completion).
            ocr_confidence: OCR confidence score (on completion).
            error_message: Error message (on failure).

        Returns:
            True if message was published successfully.
        """
        channel = self._get_channel_name(matter_id, document_id)

        message = {
            "document_id": document_id,
            "matter_id": matter_id,
            "status": status,
        }

        if page_count is not None:
            message["page_count"] = page_count
        if ocr_confidence is not None:
            message["ocr_confidence"] = ocr_confidence
        if error_message is not None:
            message["error_message"] = error_message

        try:
            # Publish to channel
            subscriber_count = self.client.publish(channel, json.dumps(message))

            logger.info(
                "document_status_published",
                channel=channel,
                status=status,
                subscriber_count=subscriber_count,
            )

            return True

        except Exception as e:
            logger.error(
                "document_status_publish_failed",
                channel=channel,
                status=status,
                error=str(e),
            )
            # Don't raise - status updates are non-critical
            return False

    def publish_processing_progress(
        self,
        matter_id: str,
        document_id: str,
        current_page: int,
        total_pages: int,
    ) -> bool:
        """Publish document processing progress update.

        For large documents, provides page-by-page progress updates.

        Args:
            matter_id: Matter UUID.
            document_id: Document UUID.
            current_page: Current page being processed.
            total_pages: Total pages in document.

        Returns:
            True if message was published successfully.
        """
        channel = self._get_channel_name(matter_id, document_id)

        message = {
            "document_id": document_id,
            "matter_id": matter_id,
            "status": "processing",
            "progress": {
                "current_page": current_page,
                "total_pages": total_pages,
                "percentage": round((current_page / total_pages) * 100, 1),
            },
        }

        try:
            self.client.publish(channel, json.dumps(message))
            return True
        except Exception as e:
            logger.warning(
                "document_progress_publish_failed",
                channel=channel,
                error=str(e),
            )
            return False


@lru_cache(maxsize=1)
def get_pubsub_service() -> PubSubService:
    """Get singleton pub/sub service instance.

    Returns:
        PubSubService instance.
    """
    return PubSubService()


def broadcast_document_status(
    matter_id: str,
    document_id: str,
    status: str,
    page_count: int | None = None,
    ocr_confidence: float | None = None,
    error_message: str | None = None,
) -> None:
    """Convenience function to broadcast document status.

    Safe to call from anywhere - will not raise exceptions.

    Args:
        matter_id: Matter UUID.
        document_id: Document UUID.
        status: New status value.
        page_count: Number of pages (on completion).
        ocr_confidence: OCR confidence score (on completion).
        error_message: Error message (on failure).
    """
    try:
        service = get_pubsub_service()
        service.publish_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status=status,
            page_count=page_count,
            ocr_confidence=ocr_confidence,
            error_message=error_message,
        )
    except Exception as e:
        # Never fail because of pub/sub issues
        logger.warning(
            "broadcast_document_status_failed",
            document_id=document_id,
            status=status,
            error=str(e),
        )


# =============================================================================
# Job Progress Broadcasting (Story 2c-3)
# =============================================================================

# Channel pattern for processing jobs: processing:{matter_id}
JOB_CHANNEL_PATTERN = "processing:{matter_id}"


def broadcast_job_progress(
    matter_id: str,
    job_id: str,
    stage: str,
    progress_pct: int,
    estimated_completion: datetime | None = None,
) -> None:
    """Broadcast job progress update.

    Safe to call from anywhere - will not raise exceptions.

    Args:
        matter_id: Matter UUID.
        job_id: Job UUID.
        stage: Current processing stage.
        progress_pct: Progress percentage (0-100).
        estimated_completion: Optional estimated completion timestamp.
    """
    try:
        service = get_pubsub_service()
        channel = JOB_CHANNEL_PATTERN.format(matter_id=matter_id)

        message = {
            "event": "job_progress",
            "job_id": job_id,
            "matter_id": matter_id,
            "stage": stage,
            "progress_pct": progress_pct,
        }

        if estimated_completion:
            message["estimated_completion"] = estimated_completion.isoformat()

        service.client.publish(channel, json.dumps(message))

        logger.debug(
            "job_progress_broadcast",
            job_id=job_id,
            stage=stage,
            progress_pct=progress_pct,
        )

    except Exception as e:
        # Never fail because of pub/sub issues
        logger.warning(
            "broadcast_job_progress_failed",
            job_id=job_id,
            stage=stage,
            error=str(e),
        )


def broadcast_job_status_change(
    matter_id: str,
    job_id: str,
    old_status: str,
    new_status: str,
) -> None:
    """Broadcast job status change.

    Safe to call from anywhere - will not raise exceptions.

    Args:
        matter_id: Matter UUID.
        job_id: Job UUID.
        old_status: Previous status.
        new_status: New status.
    """
    try:
        service = get_pubsub_service()
        channel = JOB_CHANNEL_PATTERN.format(matter_id=matter_id)

        message = {
            "event": "job_status_change",
            "job_id": job_id,
            "matter_id": matter_id,
            "old_status": old_status,
            "new_status": new_status,
        }

        service.client.publish(channel, json.dumps(message))

        logger.info(
            "job_status_change_broadcast",
            job_id=job_id,
            old_status=old_status,
            new_status=new_status,
        )

    except Exception as e:
        # Never fail because of pub/sub issues
        logger.warning(
            "broadcast_job_status_change_failed",
            job_id=job_id,
            new_status=new_status,
            error=str(e),
        )


def broadcast_processing_summary(
    matter_id: str,
    queued: int,
    processing: int,
    completed: int,
    failed: int,
) -> None:
    """Broadcast matter processing summary update.

    Safe to call from anywhere - will not raise exceptions.

    Args:
        matter_id: Matter UUID.
        queued: Number of queued jobs.
        processing: Number of processing jobs.
        completed: Number of completed jobs.
        failed: Number of failed jobs.
    """
    try:
        service = get_pubsub_service()
        channel = JOB_CHANNEL_PATTERN.format(matter_id=matter_id)

        message = {
            "event": "processing_summary",
            "matter_id": matter_id,
            "stats": {
                "queued": queued,
                "processing": processing,
                "completed": completed,
                "failed": failed,
            },
        }

        service.client.publish(channel, json.dumps(message))

        logger.debug(
            "processing_summary_broadcast",
            matter_id=matter_id,
            queued=queued,
            processing=processing,
        )

    except Exception as e:
        # Never fail because of pub/sub issues
        logger.warning(
            "broadcast_processing_summary_failed",
            matter_id=matter_id,
            error=str(e),
        )
