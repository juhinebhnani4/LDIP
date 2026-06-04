#!/usr/bin/env python3
"""Merge duplicate entities in the Matter Identity Graph.

This script identifies duplicate entity records for the same person/org
and merges them into a single canonical entity. It:
1. Groups entities by last name similarity
2. Within each group, identifies merge candidates using name similarity
3. Picks the highest-mention-count entity as canonical
4. Merges aliases from duplicates into the canonical entity
5. Updates entities_involved arrays in events to use canonical IDs
6. Optionally deletes merged duplicates

Usage:
    python scripts/merge_duplicate_entities.py <matter_id> [--dry-run] [--threshold 0.92] [--delete]

    --dry-run:    Show what would be merged without making changes
    --threshold:  Similarity threshold for merging (default: 0.92, applied to core names after suffix stripping)
    --delete:     Delete duplicate entities after merging (default: soft merge only)
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import re
from collections import defaultdict

import structlog
from rapidfuzz.distance import JaroWinkler as JaroWinklerModule

from app.models.entity import EntityNode, EntityType
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# ── Suffix / prefix patterns to strip before core-name comparison ────────────
# Order matters: longer patterns first to avoid partial matches
ORG_SUFFIX_PATTERNS = [
    r"\bprivate\s+limited\b\.?",
    r"\bpvt\.?\s*ltd\.?",
    r"\blimited\b\.?",
    r"\bltd\.?",
    r"\bincorporated\b\.?",
    r"\binc\.?",
    r"\bcorporation\b\.?",
    r"\bcorp\.?",
    r"\bllc\.?",
    r"\bllp\.?",
    r"\b(?:&|and)\s+(?:associates|co\.?|company|sons|partners)\b",
    r"\benterprises?\b",
    r"\bindustries\b",
    r"\bfoundation\b",
    r"\btrust\b",
    r"\bsociety\b",
    r"\bgroup\b",
    r"\bholdings?\b",
    r"\binternational\b",
    r"\bof\s+india\b",
    r"\bof\s+maharashtra\b",
    r"\bof\s+gujarat\b",
    r"\bof\s+rajasthan\b",
    r"\bof\s+delhi\b",
    r"\bof\s+mumbai\b",
    r"\bof\s+chennai\b",
    r"\bof\s+kolkata\b",
    r"\bof\s+bangalore\b",
]

# Compiled single pattern for suffix stripping (case-insensitive)
_ORG_SUFFIX_RE = re.compile(
    r"\s*(?:" + "|".join(ORG_SUFFIX_PATTERNS) + r")\s*",
    re.IGNORECASE,
)

# Legal party role patterns — these should NEVER be merged across numbers
ROLE_PATTERNS = re.compile(
    r"^(?:respondent|petitioner|appellant|complainant|applicant|accused|witness|defendant|plaintiff)"
    r"\s*(?:no\.?\s*\d+|#\s*\d+)",
    re.IGNORECASE,
)

# Case/application number patterns — these should NEVER be merged across numbers
CASE_NUMBER_PATTERN = re.compile(
    r"^(?:MA|MP|CA|IA|WP|SLP|CRL|CMP|Miscellaneous\s+Application)\s*\.?\s*(?:No\.?\s*)?\d+",
    re.IGNORECASE,
)

# Minimum core name length for org entities (below this, require exact match)
MIN_ORG_CORE_LENGTH = 4


def load_entities(matter_id: str, batch_size: int = 500) -> list[EntityNode]:
    """Load all entities for a matter using pagination."""
    client = get_service_client()
    all_entities: list[EntityNode] = []
    page = 0

    while True:
        offset = page * batch_size
        response = (
            client.table("identity_nodes")
            .select("*")
            .eq("matter_id", matter_id)
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        if not response.data:
            break

        for row in response.data:
            entity = EntityNode(
                id=row["id"],
                matter_id=row["matter_id"],
                canonical_name=row["canonical_name"],
                entity_type=EntityType(row["entity_type"])
                if row.get("entity_type")
                else EntityType.PERSON,
                aliases=row.get("aliases") or [],
                mention_count=row.get("mention_count", 0),
                metadata=row.get("metadata") or {},
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                merged_into_id=row.get("merged_into_id"),
                merged_at=row.get("merged_at"),
                merged_by=row.get("merged_by"),
            )
            all_entities.append(entity)

        if len(response.data) < batch_size:
            break
        page += 1

    print(f"Loaded {len(all_entities)} entities in {page + 1} pages")
    return all_entities


def normalize_name(name: str) -> str:
    """Strip titles and normalize a name for comparison."""
    if not name:
        return ""
    title_words = (
        "shri",
        "smt",
        "kumari",
        "dr",
        "adv",
        "advocate",
        "hon",
        "hon'ble",
        "honourable",
        "justice",
        "mr",
        "mrs",
        "ms",
        "miss",
        "prof",
        "professor",
    )
    pattern = r"^(?:" + "|".join(re.escape(t) for t in title_words) + r")\.?\s+"
    cleaned = re.sub(pattern, "", name.strip(), flags=re.IGNORECASE)
    # Normalize whitespace and case
    cleaned = " ".join(cleaned.split())
    return cleaned


def is_role_pattern(name: str) -> bool:
    """Check if name is a numbered legal party reference (Respondent No.2, etc.)."""
    return bool(ROLE_PATTERNS.match(normalize_name(name).strip()))


def is_case_number(name: str) -> bool:
    """Check if name is a case/application number (MA 8 of 2016, etc.)."""
    return bool(CASE_NUMBER_PATTERN.match(normalize_name(name).strip()))


def extract_core_name(name: str, entity_type: EntityType | None = None) -> str:
    """Extract core name by stripping org suffixes/prefixes.

    For PERSON entities, just normalizes (strips titles).
    For ORG entities, additionally strips common suffixes like Ltd, Pvt Ltd, etc.

    Returns:
        Core name string (lowercased, whitespace-normalized).
        Empty string if name is empty after stripping.
    """
    normalized = normalize_name(name)
    if not normalized:
        return ""

    # Only strip org suffixes for ORG entities (or unknown type)
    if entity_type is None or entity_type != EntityType.PERSON:
        core = _ORG_SUFFIX_RE.sub(" ", normalized)
        # Clean up leftover punctuation and whitespace
        core = re.sub(r"[,.\-]+$", "", core.strip())
        core = " ".join(core.split())
        if core:
            return core.lower()

    return normalized.lower()


def extract_last_name(name: str) -> str:
    """Extract the last name component from a name."""
    normalized = normalize_name(name)
    parts = normalized.split()
    if not parts:
        return ""
    # Last word is typically the surname
    return parts[-1].lower().rstrip(".'s")


def calculate_similarity(
    name1: str,
    name2: str,
    entity_type: EntityType | None = None,
) -> float:
    """Calculate name similarity using Jaro-Winkler on core names (suffix-stripped).

    For ORG entities, strips common suffixes (Ltd, Pvt Ltd, etc.) before comparing
    so that "Hindustan Lever Ltd" vs "Neeta Enterprises Pvt. Ltd." compares
    "hindustan lever" vs "neeta enterprises" instead of being inflated by shared suffixes.

    For very short org core names (< 4 chars), requires exact match to prevent
    false positives like "MCS" vs "ACC".

    Returns 0.0 for numbered role patterns (Respondent No.2 vs No.3).
    """
    # Block numbered party patterns and case numbers — never merge these
    if is_role_pattern(name1) or is_role_pattern(name2):
        return 0.0
    if is_case_number(name1) or is_case_number(name2):
        return 0.0

    core1 = extract_core_name(name1, entity_type)
    core2 = extract_core_name(name2, entity_type)

    if not core1 or not core2:
        return 0.0
    if core1 == core2:
        return 1.0

    # For very short org cores, require exact match
    if entity_type != EntityType.PERSON and (
        len(core1) < MIN_ORG_CORE_LENGTH or len(core2) < MIN_ORG_CORE_LENGTH
    ):
        return 1.0 if core1 == core2 else 0.0

    return JaroWinklerModule.normalized_similarity(core1, core2)


def find_merge_groups(
    entities: list[EntityNode],
    threshold: float = 0.92,
) -> list[list[EntityNode]]:
    """Find groups of duplicate entities that should be merged.

    Groups entities by last name, then finds merge candidates within each group.

    Returns:
        List of merge groups, each group being a list of EntityNode objects.
        The first entity in each group is the canonical (highest mention count).
    """
    # Group by entity type first
    by_type: dict[EntityType, list[EntityNode]] = defaultdict(list)
    for entity in entities:
        by_type[entity.entity_type].append(entity)

    merge_groups: list[list[EntityNode]] = []

    for entity_type, type_entities in by_type.items():
        # Group by last name similarity
        last_name_groups: dict[str, list[EntityNode]] = defaultdict(list)
        for entity in type_entities:
            last_name = extract_last_name(entity.canonical_name)
            if not last_name or len(last_name) < 2:
                continue

            # Find matching last name group
            matched = False
            for group_key in list(last_name_groups.keys()):
                if JaroWinklerModule.normalized_similarity(last_name, group_key) > 0.85:
                    last_name_groups[group_key].append(entity)
                    matched = True
                    break

            if not matched:
                last_name_groups[last_name].append(entity)

        # Within each last name group, find merge candidates
        for _last_name, group in last_name_groups.items():
            if len(group) < 2:
                continue

            # Build merge clusters using Union-Find
            parent: dict[str, str] = {e.id: e.id for e in group}

            def find(x: str, parent=parent) -> str:
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            def union(x: str, y: str, parent=parent) -> None:
                px, py = find(x), find(y)
                if px != py:
                    parent[px] = py

            # Compare all pairs
            for i, e1 in enumerate(group):
                for e2 in group[i + 1 :]:
                    sim = calculate_similarity(
                        e1.canonical_name, e2.canonical_name, entity_type
                    )
                    if sim >= threshold:
                        union(e1.id, e2.id)

            # Collect clusters
            clusters: dict[str, list[EntityNode]] = defaultdict(list)
            for entity in group:
                root = find(entity.id)
                clusters[root].append(entity)

            # Only include clusters with 2+ entities
            for cluster in clusters.values():
                if len(cluster) >= 2:
                    # Sort by mention_count descending — first is canonical
                    cluster.sort(key=lambda e: e.mention_count or 0, reverse=True)
                    merge_groups.append(cluster)

    return merge_groups


def execute_merge(
    matter_id: str,
    merge_groups: list[list[EntityNode]],
    delete_dupes: bool = False,
) -> dict:
    """Execute the merge operations in the database.

    For each merge group:
    1. Collect all aliases from duplicates
    2. Update canonical entity with merged aliases and aggregated mention count
    3. Update events.entities_involved to replace duplicate IDs with canonical ID
    4. Update statement_comparisons.entity_id to point to canonical
    5. Optionally delete duplicate entity records

    Returns:
        Summary dict with counts.
    """
    client = get_service_client()
    total_merged = 0
    total_events_updated = 0
    total_contradictions_updated = 0

    for group in merge_groups:
        canonical = group[0]
        duplicates = group[1:]

        if not duplicates:
            continue

        # Collect all aliases
        all_aliases = set(canonical.aliases or [])
        all_aliases.add(canonical.canonical_name)
        total_mentions = canonical.mention_count or 0

        for dupe in duplicates:
            all_aliases.add(dupe.canonical_name)
            for alias in dupe.aliases or []:
                all_aliases.add(alias)
            total_mentions += dupe.mention_count or 0

        # Remove canonical name from aliases
        all_aliases.discard(canonical.canonical_name)

        # Update canonical entity
        client.table("identity_nodes").update(
            {
                "aliases": list(all_aliases),
                "mention_count": total_mentions,
            }
        ).eq("id", canonical.id).execute()

        print(f"  Updated canonical '{canonical.canonical_name}' ({canonical.id})")
        print(
            f"    Merged aliases: {list(all_aliases)[:5]}{'...' if len(all_aliases) > 5 else ''}"
        )
        print(f"    Total mentions: {total_mentions}")

        # Update events.entities_involved — replace duplicate IDs with canonical
        for dupe in duplicates:
            # Find events that reference this duplicate entity
            events_response = (
                client.table("events")
                .select("id, entities_involved")
                .eq("matter_id", matter_id)
                .contains("entities_involved", [dupe.id])
                .execute()
            )

            if events_response.data:
                for event_row in events_response.data:
                    old_entities = event_row["entities_involved"] or []
                    # Replace dupe ID with canonical ID
                    new_entities = list(
                        set(
                            canonical.id if eid == dupe.id else eid
                            for eid in old_entities
                        )
                    )
                    client.table("events").update(
                        {
                            "entities_involved": new_entities,
                        }
                    ).eq("id", event_row["id"]).execute()
                    total_events_updated += 1

            # Update statement_comparisons.entity_id
            comparisons_response = (
                client.table("statement_comparisons")
                .select("id")
                .eq("entity_id", dupe.id)
                .execute()
            )

            if comparisons_response.data:
                for comp_row in comparisons_response.data:
                    client.table("statement_comparisons").update(
                        {
                            "entity_id": canonical.id,
                        }
                    ).eq("id", comp_row["id"]).execute()
                    total_contradictions_updated += 1

            # Delete or mark duplicate
            if delete_dupes:
                client.table("identity_nodes").delete().eq("id", dupe.id).execute()
                print(f"    Deleted duplicate '{dupe.canonical_name}' ({dupe.id})")
            else:
                # Soft merge: add metadata indicating merged
                client.table("identity_nodes").update(
                    {
                        "metadata": {
                            **(dupe.metadata or {}),
                            "merged_into": canonical.id,
                            "merged_canonical_name": canonical.canonical_name,
                        },
                    }
                ).eq("id", dupe.id).execute()
                print(f"    Soft-merged duplicate '{dupe.canonical_name}' ({dupe.id})")

            total_merged += 1

    return {
        "groups_processed": len(merge_groups),
        "entities_merged": total_merged,
        "events_updated": total_events_updated,
        "contradictions_updated": total_contradictions_updated,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Merge duplicate entities in the Matter Identity Graph"
    )
    parser.add_argument("matter_id", help="Matter UUID to process")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without making changes",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.92,
        help="Similarity threshold for merging (default: 0.92, on core names after suffix stripping)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete duplicate entities after merging (default: soft merge)",
    )

    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"Entity Deduplication for matter: {args.matter_id}")
    print(f"Threshold: {args.threshold}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Delete duplicates: {args.delete}")
    print(f"{'=' * 60}\n")

    # Load all entities
    entities = load_entities(args.matter_id)

    if not entities:
        print("No entities found!")
        return 1

    # Find merge groups
    merge_groups = find_merge_groups(entities, threshold=args.threshold)

    if not merge_groups:
        print("No duplicate entities found!")
        return 0

    print(f"\nFound {len(merge_groups)} merge groups:\n")

    for i, group in enumerate(merge_groups, 1):
        canonical = group[0]
        duplicates = group[1:]
        core_canonical = extract_core_name(
            canonical.canonical_name, canonical.entity_type
        )
        print(
            f"  Group {i}: Canonical = '{canonical.canonical_name}' "
            f"(mentions: {canonical.mention_count}, core: '{core_canonical}')"
        )
        for dupe in duplicates:
            sim = calculate_similarity(
                canonical.canonical_name, dupe.canonical_name, canonical.entity_type
            )
            core_dupe = extract_core_name(dupe.canonical_name, dupe.entity_type)
            print(
                f"    -> Merge '{dupe.canonical_name}' "
                f"(mentions: {dupe.mention_count}, sim: {sim:.2f}, core: '{core_dupe}')"
            )

    total_to_merge = sum(len(g) - 1 for g in merge_groups)
    print(f"\nTotal entities to merge: {total_to_merge}")

    if args.dry_run:
        print("\nDRY RUN — no changes made.")
        return 0

    # Execute merge
    print("\nExecuting merge...\n")
    result = execute_merge(args.matter_id, merge_groups, delete_dupes=args.delete)

    print(f"\n{'=' * 60}")
    print("MERGE COMPLETED")
    print(f"  Groups processed: {result['groups_processed']}")
    print(f"  Entities merged: {result['entities_merged']}")
    print(f"  Events updated: {result['events_updated']}")
    print(f"  Contradictions updated: {result['contradictions_updated']}")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
