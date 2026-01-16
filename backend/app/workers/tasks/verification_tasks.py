"""Celery tasks for citation verification.

Implements batch verification of citations against uploaded Act documents.
Runs verification asynchronously and broadcasts real-time progress updates.

Story 3-3: Citation Verification (AC: #5)
"""

import asyncio

import structlog

from app.engines.citation import (
    get_citation_storage_service,
    get_citation_verifier,
)
from app.models.citation import VerificationStatus
from app.services.pubsub_service import (
    broadcast_citation_verified,
    broadcast_verification_complete,
    broadcast_verification_progress,
)
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [30, 60, 120]  # Exponential backoff


def _run_async(coro):
    """Run async coroutine in sync context for Celery tasks.

    Uses asyncio.run() which creates a single event loop per call and
    properly cleans up. For batch operations, prefer using the async
    batch functions directly with a single asyncio.run() call.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.
    """
    return asyncio.run(coro)


async def _verify_citations_batch_async(
    task_id: str,
    matter_id: str,
    act_name: str,
    act_document_id: str,
) -> dict:
    """Async implementation of batch citation verification.

    Processes all citations in a single event loop to avoid the overhead
    of creating new event loops per citation (Event Loop Storm fix).

    Args:
        task_id: Celery task ID for logging.
        matter_id: Matter UUID.
        act_name: Name of the Act.
        act_document_id: UUID of the uploaded Act document.

    Returns:
        Dictionary with verification results.
    """
    storage = get_citation_storage_service()
    verifier = get_citation_verifier()

    # Results tracking
    results = {
        "total": 0,
        "verified": 0,
        "mismatch": 0,
        "not_found": 0,
        "errors": 0,
    }

    # Get all citations for this Act
    citations = await storage.get_citations_for_act(
        matter_id=matter_id,
        act_name=act_name,
        exclude_verified=True,
    )

    total_citations = len(citations)
    results["total"] = total_citations

    if total_citations == 0:
        logger.info(
            "verification_task_no_citations",
            task_id=task_id,
            matter_id=matter_id,
            act_name=act_name,
        )
        return results

    logger.info(
        "verification_task_processing",
        task_id=task_id,
        matter_id=matter_id,
        act_name=act_name,
        citation_count=total_citations,
    )

    # Process each citation within the same event loop
    for i, citation in enumerate(citations):
        try:
            # Verify the citation (async)
            result = await verifier.verify_citation(
                citation=citation,
                act_document_id=act_document_id,
                act_name=act_name,
            )

            # Update citation in database (async)
            await storage.update_citation_verification(
                citation_id=citation.id,
                matter_id=matter_id,
                verification_status=result.status,
                target_act_document_id=act_document_id,
                target_page=result.target_page,
                target_bbox_ids=result.target_bbox_ids,
                confidence=result.similarity_score,
            )

            # Update results counter
            if result.status == VerificationStatus.VERIFIED:
                results["verified"] += 1
            elif result.status == VerificationStatus.MISMATCH:
                results["mismatch"] += 1
            elif result.status == VerificationStatus.SECTION_NOT_FOUND:
                results["not_found"] += 1

            # Broadcast individual citation result
            broadcast_citation_verified(
                matter_id=matter_id,
                citation_id=citation.id,
                status=result.status.value,
                explanation=result.explanation,
                similarity_score=result.similarity_score,
            )

            # Broadcast progress every citation
            processed = i + 1
            broadcast_verification_progress(
                matter_id=matter_id,
                act_name=act_name,
                verified_count=processed,
                total_count=total_citations,
                task_id=task_id,
            )

            logger.debug(
                "citation_verified",
                citation_id=citation.id,
                status=result.status.value,
                progress=f"{processed}/{total_citations}",
            )

        except Exception as e:
            logger.error(
                "citation_verification_error",
                citation_id=citation.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            results["errors"] += 1

            # Fix Issue 6: Mark failed citations as ERROR status
            try:
                await storage.update_citation_verification(
                    citation_id=citation.id,
                    matter_id=matter_id,
                    verification_status=VerificationStatus.ACT_UNAVAILABLE,
                )
            except Exception:
                pass  # Best effort - don't fail the batch for this

    # Broadcast completion
    broadcast_verification_complete(
        matter_id=matter_id,
        act_name=act_name,
        total_verified=total_citations,
        verified_count=results["verified"],
        mismatch_count=results["mismatch"],
        not_found_count=results["not_found"],
        task_id=task_id,
    )

    return results


@celery_app.task(
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=60,
    acks_late=True,
)
def verify_citations_for_act(
    self,
    matter_id: str,
    act_name: str,
    act_document_id: str,
) -> dict:
    """Verify all citations for a specific Act.

    Triggered when an Act document is uploaded. Verifies all citations
    referencing that Act against the uploaded document.

    Uses a single event loop for the entire batch to avoid Event Loop Storm.

    Args:
        matter_id: Matter UUID.
        act_name: Name of the Act (display name for matching citations).
        act_document_id: UUID of the uploaded Act document.

    Returns:
        Dictionary with verification results:
        - total: Total citations processed
        - verified: Number successfully verified
        - mismatch: Number with mismatches
        - not_found: Number with section not found
        - errors: Number of processing errors
    """
    task_id = self.request.id
    logger.info(
        "verification_task_started",
        task_id=task_id,
        matter_id=matter_id,
        act_name=act_name,
        act_document_id=act_document_id,
    )

    try:
        # Run entire batch in a single event loop (Event Loop Storm fix)
        results = asyncio.run(
            _verify_citations_batch_async(
                task_id=task_id,
                matter_id=matter_id,
                act_name=act_name,
                act_document_id=act_document_id,
            )
        )

        logger.info(
            "verification_task_complete",
            task_id=task_id,
            matter_id=matter_id,
            act_name=act_name,
            results=results,
        )

        return results

    except Exception as e:
        logger.error(
            "verification_task_failed",
            task_id=task_id,
            matter_id=matter_id,
            act_name=act_name,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Retry if transient error
        if self.request.retries < MAX_RETRIES:
            retry_delay = RETRY_DELAYS[min(self.request.retries, len(RETRY_DELAYS) - 1)]
            raise self.retry(exc=e, countdown=retry_delay)

        # Return partial results on final failure
        return {
            "total": 0,
            "verified": 0,
            "mismatch": 0,
            "not_found": 0,
            "errors": 1,
        }


async def _verify_single_citation_async(
    matter_id: str,
    citation_id: str,
    act_document_id: str,
    act_name: str,
) -> dict:
    """Async implementation of single citation verification.

    Args:
        matter_id: Matter UUID.
        citation_id: Citation UUID to verify.
        act_document_id: UUID of the Act document.
        act_name: Name of the Act.

    Returns:
        Dictionary with verification result.
    """
    storage = get_citation_storage_service()
    verifier = get_citation_verifier()

    result_dict = {
        "status": "error",
        "explanation": "Verification failed",
        "similarity_score": 0.0,
        "target_page": None,
        "success": False,
    }

    # Get the citation
    citation = await storage.get_citation(citation_id, matter_id)

    if not citation:
        result_dict["explanation"] = f"Citation {citation_id} not found"
        return result_dict

    # Verify (async)
    result = await verifier.verify_citation(
        citation=citation,
        act_document_id=act_document_id,
        act_name=act_name,
    )

    # Update in database (async)
    await storage.update_citation_verification(
        citation_id=citation.id,
        matter_id=matter_id,
        verification_status=result.status,
        target_act_document_id=act_document_id,
        target_page=result.target_page,
        target_bbox_ids=result.target_bbox_ids,
        confidence=result.similarity_score,
    )

    # Broadcast result
    broadcast_citation_verified(
        matter_id=matter_id,
        citation_id=citation_id,
        status=result.status.value,
        explanation=result.explanation,
        similarity_score=result.similarity_score,
    )

    return {
        "status": result.status.value,
        "explanation": result.explanation,
        "similarity_score": result.similarity_score,
        "target_page": result.target_page,
        "success": True,
    }


@celery_app.task(
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=60,
    acks_late=True,
)
def verify_single_citation(
    self,
    matter_id: str,
    citation_id: str,
    act_document_id: str,
    act_name: str,
) -> dict:
    """Verify a single citation against an Act document.

    Used for on-demand verification or re-verification.

    Args:
        matter_id: Matter UUID.
        citation_id: Citation UUID to verify.
        act_document_id: UUID of the Act document.
        act_name: Name of the Act.

    Returns:
        Dictionary with verification result:
        - status: Verification status
        - explanation: Human-readable explanation
        - similarity_score: Match similarity (0-100)
        - target_page: Page in Act document
        - success: Whether verification completed
    """
    task_id = self.request.id
    logger.info(
        "single_verification_task_started",
        task_id=task_id,
        citation_id=citation_id,
        act_document_id=act_document_id,
    )

    try:
        # Run in a single event loop
        result_dict = asyncio.run(
            _verify_single_citation_async(
                matter_id=matter_id,
                citation_id=citation_id,
                act_document_id=act_document_id,
                act_name=act_name,
            )
        )

        logger.info(
            "single_verification_complete",
            task_id=task_id,
            citation_id=citation_id,
            status=result_dict.get("status"),
        )

        return result_dict

    except Exception as e:
        logger.error(
            "single_verification_failed",
            task_id=task_id,
            citation_id=citation_id,
            error=str(e),
        )

        # Retry if transient error
        if self.request.retries < MAX_RETRIES:
            retry_delay = RETRY_DELAYS[min(self.request.retries, len(RETRY_DELAYS) - 1)]
            raise self.retry(exc=e, countdown=retry_delay)

        return {
            "status": "error",
            "explanation": f"Verification failed: {str(e)}",
            "similarity_score": 0.0,
            "target_page": None,
            "success": False,
        }


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def trigger_verification_on_act_upload(
    self,
    matter_id: str,
    act_name: str,
    act_document_id: str,
) -> dict:
    """Trigger verification when an Act document is uploaded.

    Called automatically when an Act is marked as uploaded.
    First updates citation statuses from act_unavailable to pending,
    then triggers the verification task.

    Args:
        matter_id: Matter UUID.
        act_name: Display name of the uploaded Act.
        act_document_id: UUID of the uploaded Act document.

    Returns:
        Dictionary with trigger result:
        - citations_updated: Number of citations status updated
        - task_id: ID of the verification task started
        - success: Whether trigger completed
    """
    logger.info(
        "verification_trigger_started",
        matter_id=matter_id,
        act_name=act_name,
        act_document_id=act_document_id,
    )

    storage = get_citation_storage_service()

    result = {
        "citations_updated": 0,
        "task_id": None,
        "success": False,
    }

    try:
        # Update citation statuses from act_unavailable to pending
        updated_count = _run_async(
            storage.bulk_update_verification_status(
                matter_id=matter_id,
                act_name=act_name,
                from_status=VerificationStatus.ACT_UNAVAILABLE,
                to_status=VerificationStatus.PENDING,
            )
        )
        result["citations_updated"] = updated_count

        if updated_count == 0:
            # Check if there are any citations for this Act at all
            citations = _run_async(
                storage.get_citations_for_act(
                    matter_id=matter_id,
                    act_name=act_name,
                )
            )
            if not citations:
                logger.info(
                    "verification_trigger_no_citations",
                    matter_id=matter_id,
                    act_name=act_name,
                )
                result["success"] = True
                return result

        # Start the verification task
        verification_task = verify_citations_for_act.delay(
            matter_id=matter_id,
            act_name=act_name,
            act_document_id=act_document_id,
        )

        result["task_id"] = verification_task.id
        result["success"] = True

        logger.info(
            "verification_trigger_complete",
            matter_id=matter_id,
            act_name=act_name,
            citations_updated=updated_count,
            verification_task_id=verification_task.id,
        )

        return result

    except Exception as e:
        logger.error(
            "verification_trigger_failed",
            matter_id=matter_id,
            act_name=act_name,
            error=str(e),
        )
        return result
