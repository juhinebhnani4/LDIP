#!/usr/bin/env python3
"""Run library migration script.

This script migrates Acts from the documents table to the library_documents table.
"""

import os
import sys

# Add the backend app to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.supabase.client import get_service_client


def run_migration():
    """Run the library migration."""
    client = get_service_client()

    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "supabase",
        "migrations",
        "20260126100001_migrate_acts_to_library.sql",
    )

    print(f"Reading migration from: {migration_path}")

    with open(migration_path) as f:
        migration_sql = f.read()

    print("Running migration...")
    print("-" * 60)

    # Execute the migration using Supabase's RPC
    # Note: This requires the execute_sql function to be available
    # or we need to use the direct Postgres connection

    try:
        # Try using supabase-py's rpc
        result = client.rpc("exec_sql", {"sql": migration_sql}).execute()
        print("Migration completed via RPC")
        print(result)
    except Exception as e:
        print(f"RPC failed (expected): {e}")
        print("\nAttempting direct execution...")

        # Use psycopg2 for direct execution
        try:
            import psycopg2

            # Get database URL from environment
            db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")

            if not db_url:
                # Construct from SUPABASE_URL
                supabase_url = os.environ.get("SUPABASE_URL", "")
                # Extract project ref from URL
                if "supabase.co" in supabase_url:
                    project_ref = supabase_url.replace("https://", "").split(".")[0]
                    db_host = f"db.{project_ref}.supabase.co"
                    db_password = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
                    db_url = (
                        f"postgresql://postgres:{db_password}@{db_host}:5432/postgres"
                    )
                else:
                    # Local development
                    db_url = "postgresql://postgres:postgres@localhost:54322/postgres"

            print("Connecting to database...")
            conn = psycopg2.connect(db_url)
            conn.autocommit = True

            with conn.cursor() as cur:
                cur.execute(migration_sql)

            conn.close()
            print("Migration completed via psycopg2!")

        except ImportError:
            print("psycopg2 not installed. Please run:")
            print("  pip install psycopg2-binary")
            print("\nOr run the migration manually in Supabase SQL Editor.")

        except Exception as e2:
            print(f"Direct execution failed: {e2}")
            print("\nPlease run the migration manually in Supabase SQL Editor.")
            print(f"Migration file: {migration_path}")


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv()

    run_migration()
