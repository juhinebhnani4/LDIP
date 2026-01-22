"""Clear ALL data from Supabase cloud database tables.

This script deletes all data from all tables while preserving the schema.
Tables are deleted in reverse dependency order to respect foreign key constraints.
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    exit(1)

client = create_client(url, key)

print(f"Connected to: {url}")
print("\n" + "="*60)
print("WARNING: This will DELETE ALL DATA from your Supabase database!")
print("="*60 + "\n")

confirm = input("Type 'DELETE ALL' to confirm: ")
if confirm != "DELETE ALL":
    print("Aborted.")
    exit(0)

# Tables in reverse dependency order (children first, parents last)
# Based on foreign key relationships from migrations
tables_to_clear = [
    # Evaluation tables
    "evaluation_results",
    "evaluation_datasets",
    "document_tables",
    # Leaf tables (no dependencies on them)
    "notifications",
    "summary_edits",
    "activities",
    "summary_verifications",
    "summary_verification_history",
    "exports",
    "document_ocr_chunks",
    "finding_verifications",
    "matter_query_history",
    "statement_comparisons",
    "anomalies",
    "processing_jobs",
    "alias_corrections",
    "mig_entity_edges",
    "mig_entity_nodes",
    "audit_logs",
    "events",
    "act_resolutions",
    "citations",
    "matter_memory",
    "findings",
    "entity_mentions",
    "bounding_boxes",
    "ocr_validation_errors",
    "ocr_validation_runs",
    "document_chunks",
    # Parent tables
    "documents",
    "matter_attorneys",
    "matters",
    "user_preferences",
    # Users table last
    "users",
]

print("\nClearing tables...")
cleared = 0
errors = []

for table in tables_to_clear:
    try:
        # Delete all rows from the table
        result = client.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        count = len(result.data) if result.data else 0
        if count > 0:
            print(f"  [OK] {table}: deleted {count} rows")
            cleared += count
        else:
            print(f"  [--] {table}: empty")
    except Exception as e:
        error_msg = str(e)
        if "could not find" in error_msg.lower() or "does not exist" in error_msg.lower() or "PGRST205" in error_msg:
            print(f"  [--] {table}: table doesn't exist (skipped)")
        else:
            print(f"  [ERR] {table}: {error_msg[:80]}")
            errors.append((table, error_msg))

print("\n" + "="*60)
print(f"Total rows deleted: {cleared}")
if errors:
    print(f"Errors: {len(errors)}")
    for table, err in errors:
        print(f"  - {table}: {err[:100]}")
print("="*60)

# Also clear storage buckets
print("\nClearing storage buckets...")
clear_storage = "YES"

if clear_storage == "YES":
    buckets = ["documents", "ocr-chunks"]
    for bucket in buckets:
        try:
            # List and delete all files in bucket
            files = client.storage.from_(bucket).list()
            if files:
                for folder in files:
                    if folder.get("name"):
                        # List files in folder
                        folder_files = client.storage.from_(bucket).list(folder["name"])
                        if folder_files:
                            paths = [f"{folder['name']}/{f['name']}" for f in folder_files if f.get("name")]
                            if paths:
                                client.storage.from_(bucket).remove(paths)
                                print(f"  ✓ {bucket}/{folder['name']}: deleted {len(paths)} files")
            print(f"  [OK] {bucket}: cleared")
        except Exception as e:
            print(f"  - {bucket}: {str(e)[:80]}")

print("\nDone! Your database is now empty.")
