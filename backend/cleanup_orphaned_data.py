"""Clean up orphaned data from soft-deleted matters.

This script finds all matters that have been soft-deleted (deleted_at IS NOT NULL)
and removes their associated data from all related tables.
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
print("Cleaning up orphaned data from soft-deleted matters")
print("="*60 + "\n")

# First, find all soft-deleted matters
print("Finding soft-deleted matters...")
deleted_matters = client.table("matters").select("id, title, deleted_at").not_.is_("deleted_at", "null").execute()

if not deleted_matters.data:
    print("No soft-deleted matters found.")
    exit(0)

print(f"Found {len(deleted_matters.data)} soft-deleted matters:")
for m in deleted_matters.data:
    print(f"  - {m['id']}: {m['title']} (deleted: {m['deleted_at']})")

matter_ids = [m['id'] for m in deleted_matters.data]

print("\n" + "-"*60)
confirm = input("Type 'CLEANUP' to remove orphaned data from these matters: ")
if confirm != "CLEANUP":
    print("Aborted.")
    exit(0)

# Tables with matter_id foreign key (order matters for foreign key constraints)
# Delete from child tables first
tables_with_matter_id = [
    # Jobs and processing
    "processing_jobs",
    "document_ocr_chunks",

    # Memory and queries
    "matter_query_history",
    "matter_memory",

    # Timeline and events
    "timeline_events",
    "anomalies",

    # Entities
    "entity_mentions",
    "identity_nodes",
    "mig_entity_nodes",
    "mig_entity_edges",

    # Citations and findings
    "citations",
    "findings",
    "finding_verifications",
    "statement_comparisons",

    # Document-related (via document_id -> documents -> matter_id)
    # These need special handling
]

# Tables with document_id that link to documents
tables_with_document_id = [
    "document_chunks",
    "chunk_bounding_boxes",
    "bounding_boxes",
    "ocr_validation_runs",
    "ocr_validation_errors",
    "document_tables",
]

print("\nCleaning up orphaned data...")
total_deleted = 0

# First, get all document IDs for deleted matters
print("\nFinding documents from deleted matters...")
docs_result = client.table("documents").select("id").in_("matter_id", matter_ids).execute()
doc_ids = [d['id'] for d in docs_result.data] if docs_result.data else []
print(f"  Found {len(doc_ids)} documents to clean up")

# Clean up tables with document_id
if doc_ids:
    for table in tables_with_document_id:
        try:
            result = client.table(table).delete().in_("document_id", doc_ids).execute()
            count = len(result.data) if result.data else 0
            if count > 0:
                print(f"  [OK] {table}: deleted {count} rows")
                total_deleted += count
            else:
                print(f"  [--] {table}: no orphaned data")
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg.lower() or "PGRST205" in error_msg:
                print(f"  [--] {table}: table doesn't exist (skipped)")
            else:
                print(f"  [ERR] {table}: {error_msg[:80]}")

# Clean up tables with matter_id
for table in tables_with_matter_id:
    try:
        result = client.table(table).delete().in_("matter_id", matter_ids).execute()
        count = len(result.data) if result.data else 0
        if count > 0:
            print(f"  [OK] {table}: deleted {count} rows")
            total_deleted += count
        else:
            print(f"  [--] {table}: no orphaned data")
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg.lower() or "PGRST205" in error_msg:
            print(f"  [--] {table}: table doesn't exist (skipped)")
        else:
            print(f"  [ERR] {table}: {error_msg[:80]}")

# Clean up documents
print("\nCleaning up documents...")
try:
    result = client.table("documents").delete().in_("matter_id", matter_ids).execute()
    count = len(result.data) if result.data else 0
    if count > 0:
        print(f"  [OK] documents: deleted {count} rows")
        total_deleted += count
    else:
        print(f"  [--] documents: no orphaned data")
except Exception as e:
    print(f"  [ERR] documents: {str(e)[:80]}")

# Clean up matter_attorneys
print("\nCleaning up matter memberships...")
try:
    result = client.table("matter_attorneys").delete().in_("matter_id", matter_ids).execute()
    count = len(result.data) if result.data else 0
    if count > 0:
        print(f"  [OK] matter_attorneys: deleted {count} rows")
        total_deleted += count
except Exception as e:
    print(f"  [ERR] matter_attorneys: {str(e)[:80]}")

# Finally, hard-delete the soft-deleted matters
print("\nHard-deleting the soft-deleted matters...")
try:
    result = client.table("matters").delete().in_("id", matter_ids).execute()
    count = len(result.data) if result.data else 0
    if count > 0:
        print(f"  [OK] matters: deleted {count} rows")
        total_deleted += count
except Exception as e:
    print(f"  [ERR] matters: {str(e)[:80]}")

# Clean up storage
print("\nCleaning up storage files...")
for doc_id in doc_ids[:10]:  # Limit to first 10 for safety
    try:
        # List and delete files for this document
        files = client.storage.from_("documents").list(doc_id)
        if files:
            paths = [f"{doc_id}/{f['name']}" for f in files if f.get("name")]
            if paths:
                client.storage.from_("documents").remove(paths)
                print(f"  [OK] Deleted {len(paths)} files for document {doc_id[:8]}...")
    except Exception as e:
        pass  # Silently skip storage errors

print("\n" + "="*60)
print(f"Total rows deleted: {total_deleted}")
print("="*60)
print("\nDone! Orphaned data has been cleaned up.")
