#!/usr/bin/env python
"""Re-validate all act resolutions with improved garbage detection.

This script clears validation_cache_id and re-runs validation for all acts
in a matter (or all matters if no matter_id specified).

Usage:
    python revalidate_acts.py [matter_id]
"""

import sys
import asyncio
from uuid import UUID

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.core.logging import get_logger
from app.engines.citation.validation import ActValidationService, ValidationStatus
from app.services.supabase.client import get_service_client

logger = get_logger(__name__)


def revalidate_matter(matter_id: str | None = None):
    """Re-validate all act resolutions for a matter."""
    client = get_service_client()
    if not client:
        print("ERROR: No Supabase client")
        return

    validation_service = ActValidationService()

    # Get all act resolutions
    query = client.table("act_resolutions").select(
        "id, matter_id, act_name_normalized, act_name_display, resolution_status"
    )

    if matter_id:
        query = query.eq("matter_id", matter_id)

    result = query.execute()
    acts = result.data or []

    print(f"Found {len(acts)} act resolutions to re-validate")

    stats = {"valid": 0, "invalid": 0, "unknown": 0, "errors": 0}

    for act in acts:
        act_display = act.get("act_name_display") or act.get("act_name_normalized", "")
        normalized = act.get("act_name_normalized", "")
        act_id = act.get("id")
        current_status = act.get("resolution_status")

        try:
            # Re-validate
            validation = validation_service.validate(act_display)

            # Determine new status
            if validation.validation_status == ValidationStatus.INVALID:
                new_status = "invalid"
                stats["invalid"] += 1
            elif validation.validation_status == ValidationStatus.VALID:
                # Keep current status if already available/auto_fetched
                if current_status in ("available", "auto_fetched"):
                    new_status = current_status
                else:
                    new_status = "missing"
                stats["valid"] += 1
            else:
                new_status = "missing"  # Unknown acts stay as missing
                stats["unknown"] += 1

            # Delete invalid acts (since DB constraint may not allow 'invalid' status yet)
            # Once migration 20260122000004 is applied, we can update to 'invalid' instead
            if new_status == "invalid" and current_status != "invalid":
                client.table("act_resolutions").delete().eq("id", act_id).execute()
                print(f"  [DELETED] {repr(act_display[:60])}")

        except Exception as e:
            print(f"  [ERROR] {repr(act_display[:40])}: {e}")
            stats["errors"] += 1

    print(f"\nResults: {stats}")


if __name__ == "__main__":
    matter_id = sys.argv[1] if len(sys.argv) > 1 else None
    if matter_id:
        print(f"Re-validating acts for matter: {matter_id}")
    else:
        print("Re-validating acts for ALL matters")
    revalidate_matter(matter_id)
