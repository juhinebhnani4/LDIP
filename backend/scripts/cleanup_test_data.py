#!/usr/bin/env python3
"""Cleanup script to remove test data and reduce Supabase egress.

This script safely removes test matters and associated data while
PRESERVING all data owned by Nirav Jobalia.

Usage:
    # Dry run (default) - shows what would be deleted
    python scripts/cleanup_test_data.py

    # Actually delete (requires confirmation)
    python scripts/cleanup_test_data.py --execute

    # Force delete without confirmation (DANGEROUS)
    python scripts/cleanup_test_data.py --execute --force

Environment variables required:
    SUPABASE_URL: Your Supabase project URL
    SUPABASE_SERVICE_KEY: Service role key
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_supabase_client():
    """Get Supabase client with service role."""
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase package not installed. Run: pip install supabase")
        sys.exit(1)

    # Try to load .env
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except ImportError:
        pass

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required")
        sys.exit(1)

    return create_client(url, key)


def get_protected_user_ids(client) -> set:
    """Get user IDs that should NEVER have their data deleted."""
    protected_patterns = [
        "%nirav%",
        "%jobalia%",
        "%njobalia%",
        "%n.jobalia%",
    ]

    protected_ids = set()

    for pattern in protected_patterns:
        result = client.table("users").select("id, email").ilike("email", pattern).execute()
        for user in result.data:
            protected_ids.add(user["id"])
            print(f"  Protected user: {user['email']} ({user['id']})")

    return protected_ids


def get_test_matters(client, protected_user_ids: set, days_old: int = 7) -> list:
    """Find test matters that are safe to delete.

    Criteria for test matters:
    1. NOT owned by protected users
    2. Created more than X days ago (default 7)
    3. Name contains 'test', 'demo', 'temp', or similar
    """
    cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

    # Get all matters with owner info
    result = client.table("matters").select(
        "id, title, created_at, matter_attorneys(user_id, role)"
    ).lt("created_at", cutoff_date).execute()

    test_matters = []
    test_keywords = ["test", "demo", "temp", "sample", "example", "dummy", "trial"]

    for matter in result.data:
        # Find owner
        owner_id = None
        for attorney in matter.get("matter_attorneys", []):
            if attorney.get("role") == "owner":
                owner_id = attorney.get("user_id")
                break

        # Skip if owner is protected
        if owner_id in protected_user_ids:
            continue

        # Check if title suggests test data
        title_lower = matter["title"].lower()
        is_test = any(keyword in title_lower for keyword in test_keywords)

        test_matters.append({
            "id": matter["id"],
            "title": matter["title"],
            "created_at": matter["created_at"],
            "owner_id": owner_id,
            "is_test_name": is_test,
        })

    return test_matters


def get_storage_usage(client, matter_ids: list) -> dict:
    """Get storage bucket usage for matters."""
    usage = {
        "documents": {"files": 0, "size": 0},
        "ocr-chunks": {"files": 0, "size": 0},
    }

    for bucket_name in ["documents", "ocr-chunks"]:
        try:
            for matter_id in matter_ids:
                # List files in matter folder
                files = client.storage.from_(bucket_name).list(matter_id)
                if files:
                    for folder in files:
                        if isinstance(folder, dict) and folder.get("name"):
                            # List files in subfolder
                            subfolder_files = client.storage.from_(bucket_name).list(
                                f"{matter_id}/{folder['name']}"
                            )
                            if subfolder_files:
                                for f in subfolder_files:
                                    if isinstance(f, dict):
                                        usage[bucket_name]["files"] += 1
                                        usage[bucket_name]["size"] += f.get("metadata", {}).get("size", 0)
        except Exception as e:
            print(f"  Warning: Could not check {bucket_name} bucket: {e}")

    return usage


def get_database_row_counts(client, matter_ids: list) -> dict:
    """Get row counts for tables that will be affected."""
    tables = [
        "chunks",
        "documents",
        "processing_jobs",
        "events",
        "entities",
        "entity_mentions",
        "citations",
        "findings",
        "matter_memory",
        "audit_logs",
    ]

    counts = {}
    matter_id_list = matter_ids  # For the IN clause

    for table in tables:
        try:
            result = client.table(table).select("id", count="exact").in_("matter_id", matter_id_list).execute()
            counts[table] = result.count or 0
        except Exception as e:
            counts[table] = f"Error: {e}"

    return counts


def delete_storage_files(client, matter_ids: list, dry_run: bool = True) -> int:
    """Delete storage files for matters."""
    deleted_count = 0

    for bucket_name in ["documents", "ocr-chunks"]:
        try:
            for matter_id in matter_ids:
                # Get all files recursively
                files_to_delete = []

                try:
                    folders = client.storage.from_(bucket_name).list(matter_id)
                    if folders:
                        for folder in folders:
                            if isinstance(folder, dict) and folder.get("name"):
                                subfolder_path = f"{matter_id}/{folder['name']}"
                                subfolder_files = client.storage.from_(bucket_name).list(subfolder_path)
                                if subfolder_files:
                                    for f in subfolder_files:
                                        if isinstance(f, dict) and f.get("name"):
                                            files_to_delete.append(f"{subfolder_path}/{f['name']}")
                except Exception:
                    pass

                if files_to_delete:
                    if dry_run:
                        print(f"  Would delete {len(files_to_delete)} files from {bucket_name}/{matter_id}")
                    else:
                        client.storage.from_(bucket_name).remove(files_to_delete)
                        print(f"  Deleted {len(files_to_delete)} files from {bucket_name}/{matter_id}")
                    deleted_count += len(files_to_delete)

        except Exception as e:
            print(f"  Warning: Error processing {bucket_name}: {e}")

    return deleted_count


def delete_matter_data(client, matter_ids: list, dry_run: bool = True) -> dict:
    """Delete database records for matters (cascade will handle most)."""
    deleted = {}

    # Delete in order to respect foreign keys (or rely on CASCADE)
    # Most tables have ON DELETE CASCADE from matters, so deleting matters should cascade

    # Tables without CASCADE that need manual deletion
    manual_tables = ["audit_logs", "processing_jobs"]

    for table in manual_tables:
        try:
            if dry_run:
                result = client.table(table).select("id", count="exact").in_("matter_id", matter_ids).execute()
                deleted[table] = result.count or 0
            else:
                result = client.table(table).delete().in_("matter_id", matter_ids).execute()
                deleted[table] = len(result.data) if result.data else 0
        except Exception as e:
            deleted[table] = f"Error: {e}"

    # Delete matters (will cascade to most other tables)
    try:
        if dry_run:
            deleted["matters"] = len(matter_ids)
        else:
            result = client.table("matters").delete().in_("id", matter_ids).execute()
            deleted["matters"] = len(result.data) if result.data else 0
    except Exception as e:
        deleted["matters"] = f"Error: {e}"

    return deleted


def cleanup_orphaned_storage(client, dry_run: bool = True) -> int:
    """Find and delete storage files for matters that no longer exist."""
    deleted_count = 0

    # Get all existing matter IDs
    result = client.table("matters").select("id").execute()
    existing_matter_ids = {m["id"] for m in result.data}

    for bucket_name in ["documents", "ocr-chunks"]:
        try:
            # List top-level folders (matter IDs)
            folders = client.storage.from_(bucket_name).list("")
            if folders:
                for folder in folders:
                    if isinstance(folder, dict) and folder.get("name"):
                        folder_name = folder["name"]
                        # Check if this looks like a UUID and doesn't exist in matters
                        if len(folder_name) == 36 and folder_name not in existing_matter_ids:
                            # This is an orphaned folder
                            files_to_delete = []
                            try:
                                subfolders = client.storage.from_(bucket_name).list(folder_name)
                                if subfolders:
                                    for sf in subfolders:
                                        if isinstance(sf, dict) and sf.get("name"):
                                            sf_path = f"{folder_name}/{sf['name']}"
                                            sf_files = client.storage.from_(bucket_name).list(sf_path)
                                            if sf_files:
                                                for f in sf_files:
                                                    if isinstance(f, dict) and f.get("name"):
                                                        files_to_delete.append(f"{sf_path}/{f['name']}")
                            except Exception:
                                pass

                            if files_to_delete:
                                if dry_run:
                                    print(f"  Would delete {len(files_to_delete)} orphaned files from {bucket_name}/{folder_name}")
                                else:
                                    client.storage.from_(bucket_name).remove(files_to_delete)
                                    print(f"  Deleted {len(files_to_delete)} orphaned files from {bucket_name}/{folder_name}")
                                deleted_count += len(files_to_delete)

        except Exception as e:
            print(f"  Warning: Error checking {bucket_name} for orphans: {e}")

    return deleted_count


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def main():
    parser = argparse.ArgumentParser(description="Cleanup test data to reduce Supabase egress")
    parser.add_argument("--execute", action="store_true", help="Actually delete (default is dry run)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--days", type=int, default=7, help="Only delete matters older than X days (default: 7)")
    parser.add_argument("--include-non-test", action="store_true", help="Include matters without test/demo in name")
    args = parser.parse_args()

    dry_run = not args.execute

    print("=" * 70)
    print("LDIP Test Data Cleanup Script")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (will delete!)'}")
    print(f"Cutoff: Matters older than {args.days} days")
    print()

    client = get_supabase_client()

    # Step 1: Identify protected users
    print("Step 1: Identifying protected users...")
    protected_ids = get_protected_user_ids(client)
    print(f"  Found {len(protected_ids)} protected user(s)")
    print()

    # Step 2: Find test matters
    print("Step 2: Finding test matters...")
    test_matters = get_test_matters(client, protected_ids, args.days)

    if not args.include_non_test:
        # Filter to only matters with test-like names
        test_matters = [m for m in test_matters if m["is_test_name"]]

    if not test_matters:
        print("  No test matters found to clean up!")
        print()
        print("Step 3: Checking for orphaned storage files...")
        orphan_count = cleanup_orphaned_storage(client, dry_run)
        if orphan_count > 0:
            print(f"  Found {orphan_count} orphaned files")
        else:
            print("  No orphaned files found")
        return

    print(f"  Found {len(test_matters)} test matter(s):")
    for m in test_matters:
        test_indicator = " [TEST]" if m["is_test_name"] else ""
        print(f"    - {m['title']}{test_indicator} (created: {m['created_at'][:10]})")
    print()

    matter_ids = [m["id"] for m in test_matters]

    # Step 3: Check storage usage
    print("Step 3: Checking storage usage...")
    storage_usage = get_storage_usage(client, matter_ids)
    for bucket, usage in storage_usage.items():
        print(f"  {bucket}: {usage['files']} files ({format_size(usage['size'])})")
    print()

    # Step 4: Check database row counts
    print("Step 4: Checking database row counts...")
    row_counts = get_database_row_counts(client, matter_ids)
    for table, count in row_counts.items():
        print(f"  {table}: {count} rows")
    print()

    # Step 5: Check for orphaned storage
    print("Step 5: Checking for orphaned storage files...")
    orphan_count = cleanup_orphaned_storage(client, dry_run=True)  # Always dry run first
    print(f"  Found {orphan_count} orphaned files")
    print()

    # Summary
    total_files = sum(u["files"] for u in storage_usage.values()) + orphan_count
    total_rows = sum(c for c in row_counts.values() if isinstance(c, int))

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Matters to delete: {len(test_matters)}")
    print(f"Storage files to delete: {total_files}")
    print(f"Database rows to delete: ~{total_rows}")
    print()

    if dry_run:
        print("This was a DRY RUN. No data was deleted.")
        print("To actually delete, run with --execute flag")
        return

    # Confirmation
    if not args.force:
        print("WARNING: This will PERMANENTLY DELETE the above data!")
        confirm = input("Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            print("Aborted.")
            return

    # Execute deletion
    print()
    print("Executing deletion...")

    # Delete storage files
    print("  Deleting storage files...")
    deleted_files = delete_storage_files(client, matter_ids, dry_run=False)

    # Delete orphaned files
    if orphan_count > 0:
        print("  Deleting orphaned files...")
        cleanup_orphaned_storage(client, dry_run=False)

    # Delete database records
    print("  Deleting database records...")
    deleted_records = delete_matter_data(client, matter_ids, dry_run=False)

    print()
    print("=" * 70)
    print("CLEANUP COMPLETE")
    print("=" * 70)
    print(f"Deleted {deleted_files} storage files")
    print(f"Deleted records: {deleted_records}")


if __name__ == "__main__":
    main()
