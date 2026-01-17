"""Merge Trigger Service for auto-triggering merge when all chunks complete.

Story 19.2: Auto-merge trigger for orphaned completed chunks.

Safety net for chunked document processing - ensures merge happens
even if the parent task crashed or failed to detect completion.
"""

from functools import lru_cache

import structlog

from app.models.document import DocumentStatus
from app.services.document_service import DocumentService, get_document_service
from app.services.ocr_chunk_service import OCRChunkService, get_ocr_chunk_service

logger = structlog.get_logger(__name__)


class MergeTriggerService:
    """Service for triggering merge when all chunks are completed."""

    def __init__(
        self,
        chunk_service: OCRChunkService | None = None,
        doc_service: DocumentService | None = None,
    ) -> None:
        self._chunk_service = chunk_service
        self._doc_service = doc_service

    @property
    def chunk_service(self) -> OCRChunkService:
        if self._chunk_service is None:
            self._chunk_service = get_ocr_chunk_service()
        return self._chunk_service

    @property
    def doc_service(self) -> DocumentService:
        if self._doc_service is None:
            self._doc_service = get_document_service()
        return self._doc_service

    async def check_and_trigger_merges(self) -> dict:
        """Check for completed chunked documents and trigger merges.

        Returns:
            Dict with triggered merge counts and details.
        """
        results = {
            "checked": 0,
            "triggered": 0,
            "skipped": 0,
            "already_complete": 0,
            "errors": [],
        }

        # Find documents with all chunks completed
        ready_docs = await self.chunk_service.find_documents_ready_for_merge()
        results["checked"] = len(ready_docs)

        if not ready_docs:
            logger.debug("no_documents_ready_for_merge")
            return results

        for doc_info in ready_docs:
            document_id = doc_info["document_id"]
            matter_id = doc_info["matter_id"]

            try:
                # Check if document is still in PROCESSING status
                document = self.doc_service.get_document(document_id)
                if not document:
                    logger.warning(
                        "merge_trigger_document_not_found",
                        document_id=document_id,
                    )
                    results["errors"].append({
                        "document_id": document_id,
                        "error": "Document not found",
                    })
                    continue

                # Skip if already completed or failed
                if document.status in (
                    DocumentStatus.OCR_COMPLETE,
                    DocumentStatus.COMPLETED,
                ):
                    logger.debug(
                        "merge_trigger_skipped_already_done",
                        document_id=document_id,
                        status=document.status.value,
                    )
                    results["already_complete"] += 1
                    continue

                # Skip if document is failed
                if document.status in (
                    DocumentStatus.OCR_FAILED,
                    DocumentStatus.FAILED,
                ):
                    logger.debug(
                        "merge_trigger_skipped_failed_status",
                        document_id=document_id,
                        status=document.status.value,
                    )
                    results["skipped"] += 1
                    continue

                # Get the job_id for this document
                job_id = self._get_job_id_for_document(document_id)

                # Trigger merge task
                self._dispatch_merge_task(document_id, matter_id, job_id)
                results["triggered"] += 1

                logger.info(
                    "merge_triggered_for_completed_chunks",
                    document_id=document_id,
                    matter_id=matter_id,
                    chunk_count=doc_info["chunk_count"],
                    job_id=job_id,
                )

            except Exception as e:
                logger.error(
                    "merge_trigger_error",
                    document_id=document_id,
                    error=str(e),
                )
                results["errors"].append({
                    "document_id": document_id,
                    "error": str(e),
                })

        return results

    def _get_job_id_for_document(self, document_id: str) -> str | None:
        """Get the job ID for a document from processing_jobs table."""
        try:
            from app.services.supabase.client import get_service_client

            client = get_service_client()
            response = (
                client.table("processing_jobs")
                .select("id")
                .eq("document_id", document_id)
                .in_("status", ["PROCESSING", "QUEUED"])
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]["id"]
        except Exception as e:
            logger.warning(
                "failed_to_get_job_id",
                document_id=document_id,
                error=str(e),
            )
        return None

    def _dispatch_merge_task(
        self,
        document_id: str,
        matter_id: str,
        job_id: str | None,
    ) -> None:
        """Dispatch the merge and finalization task."""
        from app.workers.tasks.chunked_document_tasks import finalize_chunked_document

        finalize_chunked_document.apply_async(
            kwargs={
                "document_id": document_id,
                "matter_id": matter_id,
                "job_id": job_id,
            },
            countdown=2,  # Small delay to avoid race conditions
        )


@lru_cache(maxsize=1)
def get_merge_trigger_service() -> MergeTriggerService:
    """Get or create the MergeTriggerService singleton."""
    return MergeTriggerService()
