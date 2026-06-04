#!/usr/bin/env python3
"""Cleanup script for corrupted entity aliases.

Fixes data quality issues where different numbered entities were incorrectly
merged as aliases (e.g., "Respondent No.2" having aliases like "Respondent No.3").

Usage:
    python scripts/cleanup_entity_aliases.py [--dry-run] [--matter-id UUID]

Options:
    --dry-run     Show what would be fixed without making changes
    --matter-id   Only process a specific matter (otherwise processes all)
"""

import argparse
import asyncio
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase.client import get_supabase_client

# Numbered role pattern (same as entity_resolver.py)
NUMBERED_ROLE_PATTERN = re.compile(
    r'^(respondent|applicant|petitioner|defendant|plaintiff|appellant|'
    r'opposite\s*party|o\.?p\.?|op|opp|claimant|complainant|witness|accused)'
    r'\s*(?:no\.?|number)?\s*\.?\s*(\d+)$',
    re.IGNORECASE
)

NUMBERED_ROLE_PATTERN_PLURAL = re.compile(
    r'^(respondents?|applicants?|petitioners?|defendants?|plaintiffs?|appellants?|'
    r'opposite\s*parties|o\.?p\.?s?|ops?|claimants?|complainants?|witnesses|accused)'
    r'\s*(?:nos?\.?|numbers?)?\s*\.?\s*(\d+)$',
    re.IGNORECASE
)


def extract_numbered_role(name: str) -> tuple[str, int] | None:
    """Extract role and number from numbered role entity names."""
    if not name:
        return None

    normalized = " ".join(name.split())

    match = NUMBERED_ROLE_PATTERN.match(normalized)
    if match:
        role = match.group(1).lower().strip().rstrip('s')
        number = int(match.group(2))
        return (role, number)

    match = NUMBERED_ROLE_PATTERN_PLURAL.match(normalized)
    if match:
        role = match.group(1).lower().strip().rstrip('s')
        number = int(match.group(2))
        return (role, number)

    return None


def is_conflicting_alias(canonical_name: str, alias: str) -> bool:
    """Check if an alias conflicts with the canonical name (different numbered role)."""
    canonical_role = extract_numbered_role(canonical_name)
    alias_role = extract_numbered_role(alias)

    if canonical_role is not None and alias_role is not None:
        base_role1, num1 = canonical_role
        base_role2, num2 = alias_role

        # Same role type but different numbers = BAD alias
        if base_role1 == base_role2 and num1 != num2:
            return True

    return False


def analyze_entity(row: dict) -> dict:
    """Analyze an entity for alias issues.

    Returns dict with:
        - id: entity id
        - canonical_name: entity canonical name
        - aliases: current aliases
        - bad_aliases: aliases that should be removed
        - good_aliases: aliases that should be kept
        - entity_type: entity type
    """
    entity_id = row["id"]
    canonical_name = row["canonical_name"]
    aliases = row.get("aliases") or []
    entity_type = row["entity_type"]

    bad_aliases = []
    good_aliases = []

    for alias in aliases:
        if is_conflicting_alias(canonical_name, alias):
            bad_aliases.append(alias)
        else:
            good_aliases.append(alias)

    return {
        "id": entity_id,
        "canonical_name": canonical_name,
        "entity_type": entity_type,
        "aliases": aliases,
        "bad_aliases": bad_aliases,
        "good_aliases": good_aliases,
        "needs_fix": len(bad_aliases) > 0,
    }


async def cleanup_aliases(dry_run: bool = True, matter_id: str | None = None):
    """Main cleanup function."""
    print("=" * 60)
    print("Entity Alias Cleanup Script")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify database)'}")
    if matter_id:
        print(f"Scope: Matter {matter_id}")
    else:
        print("Scope: All matters")
    print()

    client = get_supabase_client()
    if not client:
        print("ERROR: Could not connect to Supabase")
        return

    # Query entities with aliases
    query = client.table("identity_nodes").select("*")
    if matter_id:
        query = query.eq("matter_id", matter_id)

    # Filter to only entities that have aliases
    response = query.execute()

    if not response.data:
        print("No entities found.")
        return

    # Analyze all entities
    entities_with_issues = []
    total_entities = 0
    total_with_aliases = 0

    for row in response.data:
        total_entities += 1
        aliases = row.get("aliases") or []

        if aliases:
            total_with_aliases += 1
            analysis = analyze_entity(row)
            if analysis["needs_fix"]:
                entities_with_issues.append(analysis)

    print(f"Total entities scanned: {total_entities}")
    print(f"Entities with aliases: {total_with_aliases}")
    print(f"Entities with BAD aliases: {len(entities_with_issues)}")
    print()

    if not entities_with_issues:
        print("No issues found. All aliases are valid.")
        return

    # Show details
    print("=" * 60)
    print("ISSUES FOUND:")
    print("=" * 60)

    for entity in entities_with_issues:
        print(f"\nEntity: {entity['canonical_name']}")
        print(f"  ID: {entity['id']}")
        print(f"  Type: {entity['entity_type']}")
        print("  BAD aliases to REMOVE:")
        for bad in entity["bad_aliases"]:
            print(f"    - {bad}")
        if entity["good_aliases"]:
            print("  GOOD aliases to KEEP:")
            for good in entity["good_aliases"]:
                print(f"    + {good}")

    print()

    if dry_run:
        print("DRY RUN - No changes made.")
        print("Run with --no-dry-run to apply fixes.")
        return

    # Apply fixes
    print("=" * 60)
    print("APPLYING FIXES:")
    print("=" * 60)

    fixed_count = 0
    error_count = 0

    for entity in entities_with_issues:
        try:
            # Update entity with only good aliases
            result = (
                client.table("identity_nodes")
                .update({
                    "aliases": entity["good_aliases"],
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", entity["id"])
                .execute()
            )

            if result.data:
                print(f"  FIXED: {entity['canonical_name']}")
                print(f"         Removed {len(entity['bad_aliases'])} bad aliases")
                fixed_count += 1
            else:
                print(f"  ERROR: Could not update {entity['canonical_name']}")
                error_count += 1

        except Exception as e:
            print(f"  ERROR: {entity['canonical_name']} - {e}")
            error_count += 1

    print()
    print("=" * 60)
    print(f"SUMMARY: Fixed {fixed_count} entities, {error_count} errors")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Cleanup corrupted entity aliases")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be fixed without making changes (default: True)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually apply the fixes",
    )
    parser.add_argument(
        "--matter-id",
        type=str,
        help="Only process a specific matter",
    )

    args = parser.parse_args()

    # --no-dry-run overrides --dry-run
    dry_run = not args.no_dry_run

    asyncio.run(cleanup_aliases(dry_run=dry_run, matter_id=args.matter_id))


if __name__ == "__main__":
    main()
