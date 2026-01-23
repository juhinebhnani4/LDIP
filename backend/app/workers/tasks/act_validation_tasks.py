"""Celery tasks for Act validation and auto-fetching.

This module provides async tasks for:
1. Validating extracted act names (garbage detection)
2. Auto-fetching valid Act PDFs from India Code
3. Updating validation cache and act resolutions
4. Creating document records for auto-fetched Acts

Part of Act Validation and Auto-Fetching feature.
"""

import asyncio
from typing import Any
from uuid import uuid4

import structlog

from app.core.config import get_settings
from app.engines.citation.abbreviations import normalize_act_name, get_canonical_name
from app.engines.citation.india_code import IndiaCodeClient, is_india_code_enabled
from app.engines.citation.validation import (
    ActValidationService,
    ValidationSource,
    ValidationStatus,
    is_validation_enabled,
)
from app.services.act_cache_service import get_act_cache_service
from app.services.supabase.client import get_service_client
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


# =============================================================================
# Database helpers
# =============================================================================


def _get_or_create_validation_cache(
    client: Any, normalized_name: str, canonical_name: str | None = None, year: int | None = None
) -> str | None:
    """Get or create a validation cache entry.

    Returns the cache entry ID or None on error.
    """
    try:
        result = client.rpc(
            "get_or_create_validation_cache",
            {
                "p_act_name_normalized": normalized_name,
                "p_act_name_canonical": canonical_name,
                "p_act_year": year,
            }
        ).execute()

        if result.data:
            return result.data
        return None
    except Exception as e:
        logger.error("get_or_create_validation_cache_error", error=str(e))
        return None


def _update_validation_cache(
    client: Any,
    normalized_name: str,
    status: str,
    source: str | None = None,
    india_code_url: str | None = None,
    india_code_doc_id: str | None = None,
    cached_storage_path: str | None = None,
    confidence: float | None = None,
    metadata: dict | None = None,
) -> bool:
    """Update a validation cache entry."""
    try:
        client.rpc(
            "update_validation_cache",
            {
                "p_act_name_normalized": normalized_name,
                "p_validation_status": status,
                "p_validation_source": source,
                "p_india_code_url": india_code_url,
                "p_india_code_doc_id": india_code_doc_id,
                "p_cached_storage_path": cached_storage_path,
                "p_validation_confidence": confidence,
                "p_validation_metadata": metadata,
            }
        ).execute()
        return True
    except Exception as e:
        logger.error("update_validation_cache_error", error=str(e))
        return False


def _update_act_resolution(
    client: Any,
    matter_id: str,
    normalized_name: str,
    resolution_status: str,
    is_valid: bool,
    validation_cache_id: str | None = None,
) -> bool:
    """Update an act resolution with validation results."""
    try:
        update_data = {
            "resolution_status": resolution_status,
            "is_valid": is_valid,
            "updated_at": "now()",
        }

        if validation_cache_id:
            update_data["validation_cache_id"] = validation_cache_id

        client.table("act_resolutions").update(update_data).eq(
            "matter_id", matter_id
        ).eq("act_name_normalized", normalized_name).execute()

        return True
    except Exception as e:
        logger.error(
            "update_act_resolution_error",
            matter_id=matter_id,
            normalized_name=normalized_name,
            error=str(e),
        )
        return False


def _create_document_for_auto_fetched_act(
    client: Any,
    matter_id: str,
    normalized_name: str,
    canonical_name: str | None,
    storage_path: str,
    india_code_url: str | None,
    file_size: int,
) -> str | None:
    """Create a document record for an auto-fetched Act.

    Args:
        client: Supabase client.
        matter_id: Matter UUID where this Act is referenced.
        normalized_name: Normalized act name (used for filename).
        canonical_name: Display name for the Act.
        storage_path: Global storage path to the cached Act PDF.
        india_code_url: Original URL from India Code.
        file_size: Size of the PDF in bytes.

    Returns:
        Document UUID if created, None if already exists or on error.
    """
    try:
        # Check if document already exists for this matter + act
        existing = client.table("documents").select("id").eq(
            "matter_id", matter_id
        ).eq(
            "storage_path", storage_path
        ).execute()

        if existing.data:
            # Already exists
            return existing.data[0]["id"]

        # Build filename from canonical name
        display_name = canonical_name or normalized_name.replace("_", " ").title()
        filename = f"{display_name}.pdf"

        # Create document record
        doc_id = str(uuid4())
        result = client.table("documents").insert({
            "id": doc_id,
            "matter_id": matter_id,
            "filename": filename,
            "storage_path": storage_path,
            "file_size": file_size,
            "document_type": "act",
            "is_reference_material": True,
            "source": "auto_fetched",
            "uploaded_by": None,  # System-fetched, no user
            "india_code_url": india_code_url,
            "status": "completed",  # Already processed (cached PDF)
        }).execute()

        if result.data:
            logger.info(
                "document_created_for_auto_fetched_act",
                matter_id=matter_id,
                document_id=doc_id,
                act_name=normalized_name,
            )
            return doc_id

        return None

    except Exception as e:
        logger.error(
            "create_document_for_auto_fetched_act_error",
            matter_id=matter_id,
            normalized_name=normalized_name,
            error=str(e),
        )
        return None


def _get_unvalidated_acts(client: Any, matter_id: str | None = None, limit: int = 50) -> list[dict]:
    """Get acts that haven't been validated yet."""
    try:
        query = client.table("act_resolutions").select(
            "id, matter_id, act_name_normalized, act_name_display, resolution_status"
        ).is_("validation_cache_id", "null")

        if matter_id:
            query = query.eq("matter_id", matter_id)

        # Only get missing acts (not already resolved)
        query = query.eq("resolution_status", "missing")
        query = query.limit(limit)

        result = query.execute()
        return result.data or []

    except Exception as e:
        logger.error("get_unvalidated_acts_error", error=str(e))
        return []


def _get_acts_needing_fetch(client: Any, limit: int = 5) -> list[dict]:
    """Get valid acts that need PDF fetching."""
    try:
        # Get acts where validation_status is 'valid' but no cached_storage_path
        result = client.table("act_validation_cache").select(
            "id, act_name_normalized, act_name_canonical, act_year, india_code_doc_id"
        ).eq(
            "validation_status", "valid"
        ).is_(
            "cached_storage_path", "null"
        ).limit(limit).execute()

        return result.data or []

    except Exception as e:
        logger.error("get_acts_needing_fetch_error", error=str(e))
        return []


# =============================================================================
# Celery Tasks
# =============================================================================


@celery_app.task(
    bind=True,
    name="app.workers.tasks.act_validation_tasks.validate_acts_for_matter",
    max_retries=3,
    default_retry_delay=60,
    rate_limit="10/m",
)
def validate_acts_for_matter(self, matter_id: str) -> dict:
    """Validate all unvalidated acts for a matter.

    This task:
    1. Gets all unvalidated act resolutions for the matter
    2. Runs garbage detection on each
    3. Updates validation cache and act resolution status
    4. Triggers auto-fetch for valid acts

    Args:
        matter_id: Matter UUID to validate acts for.

    Returns:
        Dict with validation results summary.
    """
    # Check feature flag
    if not is_validation_enabled():
        logger.info("validate_acts_disabled", matter_id=matter_id)
        return {"error": "Act validation is disabled", "validated": 0}

    logger.info("validate_acts_starting", matter_id=matter_id)

    settings = get_settings()

    client = get_service_client()
    if not client:
        logger.error("validate_acts_no_client", matter_id=matter_id)
        return {"error": "No Supabase client", "validated": 0}

    validation_service = ActValidationService()

    # Get unvalidated acts using configurable limit
    acts = _get_unvalidated_acts(client, matter_id, limit=settings.validation_max_acts_per_task)
    logger.info("validate_acts_found", matter_id=matter_id, count=len(acts))

    results = {
        "matter_id": matter_id,
        "total": len(acts),
        "valid": 0,
        "invalid": 0,
        "unknown": 0,
        "errors": 0,
    }

    for act in acts:
        act_display = act.get("act_name_display") or act.get("act_name_normalized", "")
        normalized = act.get("act_name_normalized", "")

        try:
            # Validate the act name
            validation = validation_service.validate(act_display)

            # Get or create cache entry
            cache_id = _get_or_create_validation_cache(
                client,
                validation.act_name_normalized,
                validation.act_name_canonical,
                validation.act_year,
            )

            # Update validation cache
            _update_validation_cache(
                client,
                validation.act_name_normalized,
                validation.validation_status.value,
                validation.validation_source.value,
                confidence=validation.confidence,
                metadata={
                    "garbage_patterns": validation.garbage_patterns_matched,
                    "is_known_act": validation.is_known_act,
                },
            )

            # Update act resolution based on validation
            if validation.validation_status == ValidationStatus.INVALID:
                _update_act_resolution(
                    client,
                    matter_id,
                    normalized,
                    "invalid",
                    is_valid=False,
                    validation_cache_id=cache_id,
                )
                results["invalid"] += 1
            elif validation.validation_status == ValidationStatus.VALID:
                # Still missing until PDF is fetched
                _update_act_resolution(
                    client,
                    matter_id,
                    normalized,
                    "missing",
                    is_valid=True,
                    validation_cache_id=cache_id,
                )
                results["valid"] += 1
            else:
                # Unknown - needs India Code lookup
                _update_act_resolution(
                    client,
                    matter_id,
                    normalized,
                    "missing",
                    is_valid=True,  # Assume valid until proven otherwise
                    validation_cache_id=cache_id,
                )
                results["unknown"] += 1

            logger.debug(
                "validate_act_complete",
                matter_id=matter_id,
                act_name=normalized,
                status=validation.validation_status.value,
            )

        except Exception as e:
            logger.error(
                "validate_act_error",
                matter_id=matter_id,
                act_name=normalized,
                error=str(e),
            )
            results["errors"] += 1

    # Trigger auto-fetch for valid acts if enabled
    settings = get_settings()
    if results["valid"] > 0 and settings.india_code_auto_fetch_enabled:
        fetch_acts_from_india_code.delay()

    logger.info("validate_acts_complete", **results)
    return results


@celery_app.task(
    bind=True,
    name="app.workers.tasks.act_validation_tasks.fetch_acts_from_india_code",
    max_retries=3,
    default_retry_delay=120,  # 2 minutes between retries
    rate_limit="5/m",  # Max 5 per minute
)
def fetch_acts_from_india_code(self) -> dict:
    """Fetch Act PDFs from India Code for valid acts.

    This task:
    1. Gets acts that are validated as 'valid' but not yet cached
    2. Attempts to fetch PDF from India Code (using known mappings first)
    3. Caches the PDF globally
    4. Updates validation cache and act resolutions

    Returns:
        Dict with fetch results summary.
    """
    # Check feature flags
    settings = get_settings()
    if not is_india_code_enabled():
        logger.info("fetch_acts_disabled_india_code")
        return {"error": "India Code integration is disabled", "fetched": 0}

    if not settings.india_code_auto_fetch_enabled:
        logger.info("fetch_acts_disabled_auto_fetch")
        return {"error": "Auto-fetch is disabled", "fetched": 0}

    logger.info("fetch_acts_starting")

    client = get_service_client()
    if not client:
        return {"error": "No Supabase client", "fetched": 0}

    cache_service = get_act_cache_service()

    # Get acts needing fetch using configurable limit
    acts = _get_acts_needing_fetch(client, limit=settings.validation_max_fetch_per_task)
    logger.info("fetch_acts_found", count=len(acts))

    results = {
        "total": len(acts),
        "fetched": 0,
        "known_mapping": 0,
        "searched": 0,
        "not_found": 0,
        "errors": 0,
    }

    # Run async fetch
    async def _fetch_all():
        async with IndiaCodeClient() as india_code:
            for act in acts:
                normalized = act.get("act_name_normalized", "")
                canonical = act.get("act_name_canonical")
                year = act.get("act_year")
                doc_id = act.get("india_code_doc_id")

                try:
                    # Check if already cached
                    if cache_service.is_cached(normalized):
                        storage_path = cache_service._get_storage_path(normalized)
                        _update_validation_cache(
                            client,
                            normalized,
                            "valid",
                            cached_storage_path=storage_path,
                        )
                        results["fetched"] += 1
                        continue

                    # Try known mapping first
                    pdf_url = india_code.get_known_pdf_url(normalized)
                    if pdf_url:
                        results["known_mapping"] += 1
                        known_doc_id = india_code.get_known_doc_id(normalized)

                        download = await india_code.download_pdf(
                            known_doc_id, pdf_url
                        )

                        if download.success and download.pdf_bytes:
                            storage_path = cache_service.cache_act(
                                normalized, download.pdf_bytes
                            )

                            _update_validation_cache(
                                client,
                                normalized,
                                "valid",
                                india_code_url=pdf_url,
                                india_code_doc_id=known_doc_id,
                                cached_storage_path=storage_path,
                            )

                            results["fetched"] += 1
                            logger.info(
                                "fetch_act_success_known",
                                normalized=normalized,
                                url=pdf_url,
                            )
                            continue
                        else:
                            logger.warning(
                                "fetch_act_download_failed_known",
                                normalized=normalized,
                                error=download.error_message,
                            )

                    # Try search if we have canonical name
                    if canonical:
                        results["searched"] += 1
                        search_results = await india_code.search_act(canonical, year)

                        if search_results:
                            first_result = search_results[0]
                            download = await india_code.download_pdf(first_result.doc_id)

                            if download.success and download.pdf_bytes:
                                storage_path = cache_service.cache_act(
                                    normalized, download.pdf_bytes
                                )

                                _update_validation_cache(
                                    client,
                                    normalized,
                                    "valid",
                                    india_code_url=first_result.handle_url,
                                    india_code_doc_id=first_result.doc_id,
                                    cached_storage_path=storage_path,
                                )

                                results["fetched"] += 1
                                logger.info(
                                    "fetch_act_success_search",
                                    normalized=normalized,
                                    doc_id=first_result.doc_id,
                                )
                                continue

                    # Not found - mark as not_on_indiacode
                    _update_validation_cache(
                        client,
                        normalized,
                        "not_on_indiacode",
                        ValidationSource.INDIA_CODE.value,
                    )
                    results["not_found"] += 1
                    logger.info("fetch_act_not_found", normalized=normalized)

                except Exception as e:
                    logger.error(
                        "fetch_act_error",
                        normalized=normalized,
                        error=str(e),
                    )
                    results["errors"] += 1

    # Run the async function
    asyncio.run(_fetch_all())

    # Update act resolutions for fetched acts
    _update_matter_resolutions_from_cache(client)

    logger.info("fetch_acts_complete", **results)
    return results


def _update_matter_resolutions_from_cache(client: Any) -> dict:
    """Update act resolutions in all matters where acts are now cached.

    Also creates document records for auto-fetched Acts in each matter.

    Returns dict with counts of resolutions and documents updated/created.
    """
    settings = get_settings()
    cache_service = get_act_cache_service()

    try:
        # Get all cached acts with additional details
        cached_result = client.table("act_validation_cache").select(
            "id, act_name_normalized, act_name_canonical, cached_storage_path, india_code_url"
        ).not_.is_("cached_storage_path", "null").execute()

        cached_acts = cached_result.data or []
        updated_resolutions = 0
        created_documents = 0

        for cached in cached_acts:
            normalized = cached.get("act_name_normalized")
            canonical = cached.get("act_name_canonical")
            cache_id = cached.get("id")
            storage_path = cached.get("cached_storage_path")
            india_code_url = cached.get("india_code_url")

            # Get all matching act_resolutions that are missing (not yet auto_fetched)
            resolutions_result = client.table("act_resolutions").select(
                "id, matter_id"
            ).eq(
                "act_name_normalized", normalized
            ).eq(
                "resolution_status", "missing"
            ).execute()

            missing_resolutions = resolutions_result.data or []

            for resolution in missing_resolutions:
                matter_id = resolution.get("matter_id")

                # Get file size from storage for document record
                file_size = 0
                try:
                    # Try to get size from storage metadata
                    prefix = settings.act_cache_storage_prefix
                    files = client.storage.from_("documents").list(
                        path=f"{prefix}/",
                        options={"search": f"{normalized}.pdf"}
                    )
                    for f in files or []:
                        if f.get("name") == f"{normalized}.pdf":
                            file_size = f.get("metadata", {}).get("size", 0)
                            break
                except Exception:
                    file_size = 0

                # Create document record for this matter
                doc_id = _create_document_for_auto_fetched_act(
                    client,
                    matter_id,
                    normalized,
                    canonical,
                    storage_path,
                    india_code_url,
                    file_size,
                )

                if doc_id:
                    created_documents += 1

                    # Update act_resolution with document_id
                    client.table("act_resolutions").update({
                        "resolution_status": "auto_fetched",
                        "user_action": "auto_fetched",
                        "validation_cache_id": cache_id,
                        "act_document_id": doc_id,
                        "updated_at": "now()",
                    }).eq(
                        "id", resolution.get("id")
                    ).execute()

                    updated_resolutions += 1

        result = {
            "resolutions_updated": updated_resolutions,
            "documents_created": created_documents,
        }
        logger.info("update_matter_resolutions_complete", **result)
        return result

    except Exception as e:
        logger.error("update_matter_resolutions_error", error=str(e))
        return {"resolutions_updated": 0, "documents_created": 0}


@celery_app.task(
    bind=True,
    name="app.workers.tasks.act_validation_tasks.validate_and_fetch_acts",
    max_retries=3,
    default_retry_delay=60,
)
def validate_and_fetch_acts(self, matter_id: str, act_names: list[str]) -> dict:
    """Combined task to validate and fetch acts for a matter.

    This is the main entry point for act validation after citation extraction.

    Args:
        matter_id: Matter UUID.
        act_names: List of act names extracted from documents.

    Returns:
        Dict with processing results.
    """
    logger.info(
        "validate_and_fetch_starting",
        matter_id=matter_id,
        act_count=len(act_names),
    )

    # First validate
    validation_result = validate_acts_for_matter(matter_id)

    # Then fetch (if there are valid acts)
    fetch_result = {"fetched": 0}
    if validation_result.get("valid", 0) > 0:
        fetch_result = fetch_acts_from_india_code()

    return {
        "matter_id": matter_id,
        "validation": validation_result,
        "fetch": fetch_result,
    }


# =============================================================================
# Scheduled task for background processing
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.act_validation_tasks.process_pending_validations",
)
def process_pending_validations() -> dict:
    """Process any pending act validations across all matters.

    This is a scheduled task that runs periodically to catch up
    on any validations that may have been missed.
    """
    logger.info("process_pending_validations_starting")

    client = get_service_client()
    if not client:
        return {"error": "No Supabase client"}

    # Get all unvalidated acts
    acts = _get_unvalidated_acts(client, matter_id=None, limit=100)

    # Group by matter for efficient processing
    matters: dict[str, list] = {}
    for act in acts:
        mid = act.get("matter_id")
        if mid not in matters:
            matters[mid] = []
        matters[mid].append(act)

    results = {
        "matters_processed": len(matters),
        "acts_processed": len(acts),
    }

    # Trigger validation for each matter
    for matter_id in matters:
        validate_acts_for_matter.delay(matter_id)

    logger.info("process_pending_validations_complete", **results)
    return results
