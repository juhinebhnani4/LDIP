"""Celery tasks for Act validation and auto-fetching.

This module provides async tasks for:
1. Validating extracted act names (garbage detection)
2. Auto-fetching valid Act PDFs from India Code
3. Updating validation cache and act resolutions
4. Creating document records for auto-fetched Acts

Part of Act Validation and Auto-Fetching feature.
"""

from typing import Any
from uuid import uuid4

import structlog

from app.core.config import get_settings
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
from app.workers.utils import run_async

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


def _extract_year_from_name(name: str) -> int | None:
    """Extract year from act name like 'Indian Contract Act, 1872'."""
    import re
    match = re.search(r'\b(1[89]\d{2}|20\d{2})\b', name)
    return int(match.group(1)) if match else None


def _find_library_document_by_title(client: Any, title: str) -> dict | None:
    """Find a library document by title using trigram similarity (GAP-12 standardized).

    Uses the find_library_duplicates RPC for consistent dedup across all paths.
    Falls back to exact ilike match if RPC fails.
    """
    try:
        year = _extract_year_from_name(title)
        result = client.rpc(
            "find_library_duplicates",
            {
                "search_title": title,
                "search_year": year,
                "similarity_threshold": 0.6,
            },
        ).execute()

        if result.data:
            best = result.data[0]
            # Fetch storage_path (RPC doesn't return it, but callers need it)
            doc_result = client.table("library_documents").select(
                "id, title, storage_path"
            ).eq("id", best["id"]).limit(1).execute()
            if doc_result.data:
                return doc_result.data[0]
            return {"id": best["id"], "title": best["title"], "storage_path": None}

        return None
    except Exception as e:
        logger.warning("find_library_document_rpc_error", title=title, error=str(e))
        # Fallback: exact ilike match if RPC fails
        try:
            result = client.table("library_documents").select(
                "id, title, storage_path"
            ).ilike("title", title).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None


def _link_act_from_library(
    client: Any,
    matter_id: str,
    normalized_name: str,
    canonical_name: str | None,
    storage_path: str,
    india_code_url: str | None,
    file_size: int,
    on_complete_callbacks: list[dict] | None = None,
) -> str | None:
    """Link an Act from the shared library to a matter.

    This is the preferred approach for Acts - they go into the shared library
    and are linked to matters via matter_library_links.

    Args:
        client: Supabase client.
        matter_id: Matter UUID where this Act is referenced.
        normalized_name: Normalized act name.
        canonical_name: Display name for the Act.
        storage_path: Global storage path to the cached Act PDF.
        india_code_url: Original URL from India Code.
        file_size: Size of the PDF in bytes.
        on_complete_callbacks: Optional callbacks to fire after library
            processing (chunk + embed) completes.

    Returns:
        Library document UUID if linked/created, None on error.
    """
    try:
        display_name = canonical_name or normalized_name.replace("_", " ").title()
        filename = f"{display_name}.pdf"
        year = _extract_year_from_name(display_name)

        # 1. Check if this Act already exists in the library
        library_doc = _find_library_document_by_title(client, display_name)

        if library_doc:
            library_doc_id = library_doc["id"]
            logger.info(
                "act_found_in_library",
                library_document_id=library_doc_id,
                title=display_name,
            )
            # Check if this library doc actually has chunks (it may need processing)
            chunk_check = client.table("library_chunks").select("id", count="exact").eq(
                "library_document_id", library_doc_id
            ).execute()
            if not chunk_check.count:
                # Library doc exists but was never processed — trigger OCR + processing
                storage_path_existing = library_doc.get("storage_path")
                if storage_path_existing:
                    from app.workers.tasks.library_tasks import (
                        ocr_and_process_library_document,
                    )
                    ocr_kwargs = {
                        "library_document_id": library_doc_id,
                        "storage_path": storage_path_existing,
                    }
                    if on_complete_callbacks:
                        ocr_kwargs["on_complete_callbacks"] = on_complete_callbacks
                    ocr_and_process_library_document.apply_async(
                        kwargs=ocr_kwargs,
                        queue="default",
                    )
                    logger.info("act_ocr_processing_triggered_existing", library_document_id=library_doc_id)
        else:
            # 2. Create new library document
            library_doc_id = str(uuid4())
            result = client.table("library_documents").insert({
                "id": library_doc_id,
                "filename": filename,
                "storage_path": storage_path,
                "file_size": file_size,
                "document_type": "act",
                "title": display_name,
                "short_title": normalized_name.replace("_", " ").title(),
                "year": year,
                "jurisdiction": "central",
                "source": "india_code",
                "source_url": india_code_url,
                "status": "pending",
                "added_by": None,  # System-added
            }).execute()

            if not result.data:
                logger.error(
                    "library_document_create_failed",
                    title=display_name,
                )
                return None

            logger.info(
                "library_document_created_for_act",
                library_document_id=library_doc_id,
                title=display_name,
            )

            # Trigger OCR + processing for the new library document
            from app.workers.tasks.library_tasks import ocr_and_process_library_document
            ocr_kwargs = {
                "library_document_id": library_doc_id,
                "storage_path": storage_path,
            }
            if on_complete_callbacks:
                ocr_kwargs["on_complete_callbacks"] = on_complete_callbacks
            ocr_and_process_library_document.apply_async(
                kwargs=ocr_kwargs,
                queue="default",
            )
            logger.info("act_ocr_processing_triggered", library_document_id=library_doc_id)

        # 3. Check if already linked to this matter
        existing_link = client.table("matter_library_links").select("id").eq(
            "matter_id", matter_id
        ).eq(
            "library_document_id", library_doc_id
        ).execute()

        if existing_link.data:
            logger.info(
                "act_already_linked_to_matter",
                matter_id=matter_id,
                library_document_id=library_doc_id,
            )
            return library_doc_id

        # 4. Get a user_id for linked_by (from any document in this matter)
        user_result = client.table("documents").select("uploaded_by").eq(
            "matter_id", matter_id
        ).not_.is_("uploaded_by", "null").limit(1).execute()
        linked_by = user_result.data[0]["uploaded_by"] if user_result.data else None

        if not linked_by:
            # Fall back to any user who has access to this matter
            # This is a system operation, so we need some valid user
            logger.warning(
                "no_user_found_for_library_link",
                matter_id=matter_id,
            )
            # Try to get from matter_members or similar
            # For now, skip linking if no user available (edge case)
            return library_doc_id

        # 5. Create the link
        link_result = client.table("matter_library_links").insert({
            "matter_id": matter_id,
            "library_document_id": library_doc_id,
            "linked_by": linked_by,
        }).execute()

        if link_result.data:
            logger.info(
                "act_linked_to_matter_from_library",
                matter_id=matter_id,
                library_document_id=library_doc_id,
                title=display_name,
            )

        return library_doc_id

    except Exception as e:
        logger.error(
            "link_act_from_library_error",
            matter_id=matter_id,
            normalized_name=normalized_name,
            error=str(e),
        )
        return None


def _create_document_for_auto_fetched_act(
    client: Any,
    matter_id: str,
    normalized_name: str,
    canonical_name: str | None,
    storage_path: str,
    india_code_url: str | None,
    file_size: int,
    on_complete_callbacks: list[dict] | None = None,
) -> str | None:
    """Link an auto-fetched Act from the shared library to a matter.

    NOTE: This function now routes Acts through the shared library instead of
    creating documents directly in the matter. Acts are shared resources that
    should be in library_documents and linked via matter_library_links.

    Args:
        client: Supabase client.
        matter_id: Matter UUID where this Act is referenced.
        normalized_name: Normalized act name (used for filename).
        canonical_name: Display name for the Act.
        storage_path: Global storage path to the cached Act PDF.
        india_code_url: Original URL from India Code.
        file_size: Size of the PDF in bytes.
        on_complete_callbacks: Callbacks to fire after processing completes.

    Returns:
        Library document UUID if linked, None on error.
    """
    # Use the library-based approach for Acts
    return _link_act_from_library(
        client=client,
        matter_id=matter_id,
        normalized_name=normalized_name,
        canonical_name=canonical_name,
        storage_path=storage_path,
        india_code_url=india_code_url,
        file_size=file_size,
        on_complete_callbacks=on_complete_callbacks,
    )


def _get_unvalidated_acts(client: Any, matter_id: str | None = None, limit: int = 50) -> list[dict]:
    """Get acts that need validation or re-evaluation.

    Returns two categories:
    1. Acts never validated (no validation_cache_id)
    2. Acts validated but still stuck in 'missing' (need auto-fetch transition)
    """
    try:
        # Query 1: Acts never validated (no cache entry)
        query1 = client.table("act_resolutions").select(
            "id, matter_id, act_name_normalized, act_name_display, resolution_status, validation_cache_id"
        ).is_("validation_cache_id", "null").eq("resolution_status", "missing")

        if matter_id:
            query1 = query1.eq("matter_id", matter_id)

        result1 = query1.limit(limit).execute()
        unvalidated = result1.data or []

        # Query 2: Acts validated but still stuck in 'missing' (need re-evaluation for auto-fetch)
        remaining = limit - len(unvalidated)
        if remaining > 0:
            query2 = client.table("act_resolutions").select(
                "id, matter_id, act_name_normalized, act_name_display, resolution_status, validation_cache_id"
            ).not_.is_("validation_cache_id", "null").eq("resolution_status", "missing")

            if matter_id:
                query2 = query2.eq("matter_id", matter_id)

            result2 = query2.limit(remaining).execute()
            unvalidated.extend(result2.data or [])

        return unvalidated

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
            # If act already has a validation cache entry, skip re-validation
            # and just transition missing → auto_fetching if auto-fetch is enabled
            existing_cache_id = act.get("validation_cache_id")
            if existing_cache_id:
                if settings.india_code_auto_fetch_enabled:
                    _update_act_resolution(
                        client, matter_id, normalized, "auto_fetching",
                        is_valid=True, validation_cache_id=existing_cache_id,
                    )
                    results["valid"] += 1
                continue

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
                # Use auto_fetching if auto-fetch is enabled, otherwise stay missing
                status = "auto_fetching" if settings.india_code_auto_fetch_enabled else "missing"
                _update_act_resolution(
                    client,
                    matter_id,
                    normalized,
                    status,
                    is_valid=True,
                    validation_cache_id=cache_id,
                )
                results["valid"] += 1
            else:
                # Unknown — regex can't decide. Use LLM fallback before
                # assuming valid and sending to India Code (wastes fetches).
                try:
                    from app.engines.citation.validation import (
                        validate_act_name_with_llm,
                    )
                    llm_result = run_async(validate_act_name_with_llm(
                        act_name=act_display,
                        context=None,
                        document_id=None,
                        matter_id=matter_id,
                    ))

                    if not llm_result.is_valid:
                        # LLM says garbage — mark invalid
                        _update_validation_cache(
                            client,
                            validation.act_name_normalized,
                            ValidationStatus.INVALID.value,
                            ValidationSource.GARBAGE_DETECTION.value,
                            confidence=llm_result.confidence,
                            metadata={
                                "llm_reason": llm_result.reason,
                                "garbage_patterns": validation.garbage_patterns_matched,
                            },
                        )
                        _update_act_resolution(
                            client,
                            matter_id,
                            normalized,
                            "invalid",
                            is_valid=False,
                            validation_cache_id=cache_id,
                        )
                        results["invalid"] += 1
                        logger.info(
                            "validate_act_llm_invalid",
                            act_name=normalized,
                            reason=llm_result.reason,
                            confidence=llm_result.confidence,
                        )
                        continue

                    if llm_result.canonical_name:
                        # LLM identified a valid canonical name
                        _update_validation_cache(
                            client,
                            validation.act_name_normalized,
                            ValidationStatus.VALID.value,
                            "llm_validation",
                            confidence=llm_result.confidence,
                            metadata={
                                "llm_canonical": llm_result.canonical_name,
                                "llm_reason": llm_result.reason,
                            },
                        )
                except Exception as llm_err:
                    logger.warning(
                        "validate_act_llm_fallback_error",
                        act_name=normalized,
                        error=str(llm_err),
                    )
                    # Fall through to default behavior on LLM failure

                # Proceed with India Code lookup (either LLM confirmed or LLM unavailable)
                status = "auto_fetching" if settings.india_code_auto_fetch_enabled else "missing"
                _update_act_resolution(
                    client,
                    matter_id,
                    normalized,
                    status,
                    is_valid=True,
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
        fetch_acts_from_india_code.apply_async(
            queue="low",  # Background processing, low priority
        )

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

                            if not download.success:
                                logger.warning(
                                    "fetch_act_download_failed_search",
                                    normalized=normalized,
                                    doc_id=first_result.doc_id,
                                    error=download.error_message,
                                )

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
                        error_type=type(e).__name__,
                        error=str(e) or "(no message)",
                    )
                    results["errors"] += 1

    # Run the async function
    run_async(_fetch_all())

    # Update act resolutions for fetched acts
    _update_matter_resolutions_from_cache(client)

    logger.info("fetch_acts_complete", **results)
    return results


def _update_matter_resolutions_from_cache(client: Any) -> dict:
    """Update act resolutions in all matters where acts are now cached.

    Also creates document records for auto-fetched Acts in each matter.
    Handles failure path: marks acts as not_on_indiacode if validation says so.
    Broadcasts updates to frontends for all affected matters.

    Returns dict with counts of resolutions and documents updated/created.
    """
    settings = get_settings()
    cache_service = get_act_cache_service()

    # Track affected matter_ids for broadcasting
    affected_matter_ids: set[str] = set()

    try:
        # === SUCCESS PATH: Update resolutions where PDFs are now cached ===
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

            # Get all matching act_resolutions that are missing or auto_fetching
            resolutions_result = client.table("act_resolutions").select(
                "id, matter_id"
            ).eq(
                "act_name_normalized", normalized
            ).in_(
                "resolution_status", ["missing", "auto_fetching"]
            ).execute()

            pending_resolutions = resolutions_result.data or []

            for resolution in pending_resolutions:
                matter_id = resolution.get("matter_id")

                # Get file size from storage for document record
                file_size = 0
                try:
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
                # Pass verification as a callback so it fires AFTER library
                # processing (chunk + embed) completes — prevents race condition
                # where verification runs before chunks exist.
                # NOTE: act_document_id is set in the callback kwargs below
                # after we know the library_document_id.
                doc_id = _create_document_for_auto_fetched_act(
                    client,
                    matter_id,
                    normalized,
                    canonical,
                    storage_path,
                    india_code_url,
                    file_size,
                    on_complete_callbacks=[{
                        "task_name": "app.workers.tasks.verification_tasks.trigger_verification_on_act_upload",
                        "kwargs": {
                            "matter_id": matter_id,
                            "act_name": canonical or normalized,
                            # act_document_id auto-injected by fire_library_callbacks
                        },
                        "queue": "default",
                    }],
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
                    affected_matter_ids.add(matter_id)

                    # NOTE: Verification is NOT triggered here. It is passed as a
                    # callback to the library processing pipeline (chunk → embed →
                    # fire_library_callbacks) so it only fires AFTER chunks and
                    # embeddings exist. See _link_act_from_library which receives
                    # on_complete_callbacks and passes them to ocr_and_process_library_document.
                    logger.info(
                        "verification_deferred_to_library_processing_callback",
                        matter_id=matter_id,
                        act_name=normalized,
                        library_document_id=doc_id,
                    )

        # === FAILURE PATH: Mark acts as not_on_indiacode if validation says so ===
        try:
            not_found_result = client.table("act_validation_cache").select(
                "id, act_name_normalized"
            ).eq(
                "validation_status", "not_on_indiacode"
            ).execute()

            not_found_acts = not_found_result.data or []
            failed_resolutions = 0

            for nf in not_found_acts:
                normalized = nf.get("act_name_normalized")
                cache_id = nf.get("id")

                # Find resolutions stuck in auto_fetching or missing for this act
                stuck_result = client.table("act_resolutions").select(
                    "id, matter_id"
                ).eq(
                    "act_name_normalized", normalized
                ).in_(
                    "resolution_status", ["auto_fetching", "missing"]
                ).execute()

                stuck_resolutions = stuck_result.data or []

                for resolution in stuck_resolutions:
                    matter_id = resolution.get("matter_id")
                    client.table("act_resolutions").update({
                        "resolution_status": "not_on_indiacode",
                        "validation_cache_id": cache_id,
                        "updated_at": "now()",
                    }).eq(
                        "id", resolution.get("id")
                    ).execute()

                    failed_resolutions += 1
                    affected_matter_ids.add(matter_id)

            if failed_resolutions > 0:
                logger.info(
                    "auto_fetching_failures_resolved",
                    failed_resolutions=failed_resolutions,
                )
        except Exception as fe:
            logger.warning("failure_path_error", error=str(fe))

        # === BROADCAST: Notify frontends for all affected matters ===
        for mid in affected_matter_ids:
            try:
                from app.engines.citation.discovery import compute_resolution_stats
                from app.models.citation import ActResolution

                res_result = client.table("act_resolutions").select(
                    "id, matter_id, act_name_normalized, act_name_display, "
                    "act_document_id, resolution_status, user_action, citation_count, "
                    "first_seen_at, created_at, updated_at"
                ).eq("matter_id", mid).execute()

                resolutions = [
                    ActResolution(
                        id=r["id"],
                        matterId=r["matter_id"],
                        actNameNormalized=r["act_name_normalized"],
                        actNameDisplay=r.get("act_name_display"),
                        actDocumentId=r.get("act_document_id"),
                        resolutionStatus=r["resolution_status"],
                        userAction=r["user_action"],
                        citationCount=r.get("citation_count", 0),
                        firstSeenAt=r.get("first_seen_at"),
                        createdAt=r["created_at"],
                        updatedAt=r["updated_at"],
                    )
                    for r in (res_result.data or [])
                ]

                stats = compute_resolution_stats(resolutions, include_invalid=False)

                from app.services.pubsub_service import broadcast_act_discovery_update
                broadcast_act_discovery_update(
                    matter_id=mid,
                    total_acts=stats.total_acts,
                    missing_count=stats.missing_count,
                    available_count=stats.available_count + stats.auto_fetched_count,
                    auto_fetching_count=stats.auto_fetching_count,
                )
            except Exception as be:
                logger.warning(
                    "broadcast_after_resolution_update_failed",
                    matter_id=mid,
                    error=str(be),
                )

        result = {
            "resolutions_updated": updated_resolutions,
            "documents_created": created_documents,
            "matters_broadcast": len(affected_matter_ids),
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
        validate_acts_for_matter.apply_async(
            args=[matter_id],
            queue="low",  # Background processing, low priority
        )

    # Also trigger fetch to handle any acts stuck in auto_fetching
    # (e.g., from crashed workers or incomplete previous runs)
    settings = get_settings()
    if settings.india_code_auto_fetch_enabled:
        fetch_acts_from_india_code.apply_async(queue="low")

    logger.info("process_pending_validations_complete", **results)
    return results
