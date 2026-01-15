#!/usr/bin/env python3
"""Setup Supabase Storage bucket for document uploads.

This script ensures the 'documents' storage bucket exists with proper configuration.
Designed for CI/CD pipelines and new environment setup.

Usage:
    python scripts/setup_storage_bucket.py

Environment variables required:
    SUPABASE_URL: Your Supabase project URL
    SUPABASE_SERVICE_KEY: Service role key (required for bucket creation)

Note: This script uses the service role key intentionally as bucket creation
requires admin privileges.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_storage_bucket() -> bool:
    """Create the documents storage bucket if it doesn't exist.

    Returns:
        True if bucket exists or was created successfully.
    """
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase package not installed. Run: pip install supabase")
        return False

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
        print("  Set these in your .env file or CI/CD secrets")
        return False

    print(f"Connecting to Supabase: {url[:50]}...")
    client = create_client(url, key)

    bucket_name = "documents"

    # Check if bucket already exists
    try:
        buckets = client.storage.list_buckets()
        existing_names = [b.name for b in buckets]

        if bucket_name in existing_names:
            print(f"✓ Bucket '{bucket_name}' already exists")
            return True

    except Exception as e:
        print(f"WARNING: Could not list buckets: {e}")
        # Continue to try creating - might fail with better error

    # Create the bucket
    try:
        print(f"Creating bucket '{bucket_name}'...")
        client.storage.create_bucket(
            bucket_name,
            options={
                "public": False,  # Private bucket - requires auth
                "file_size_limit": 500 * 1024 * 1024,  # 500MB
                "allowed_mime_types": ["application/pdf", "application/zip", "application/x-zip-compressed"],
            }
        )
        print(f"✓ Bucket '{bucket_name}' created successfully")
        return True

    except Exception as e:
        error_str = str(e).lower()
        if "already exists" in error_str or "duplicate" in error_str:
            print(f"✓ Bucket '{bucket_name}' already exists")
            return True
        print(f"ERROR: Failed to create bucket: {e}")
        return False


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("LDIP Storage Bucket Setup")
    print("=" * 60)

    # Try to load .env file if python-dotenv is available
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"Loaded environment from: {env_path}")
    except ImportError:
        pass  # dotenv not required

    success = setup_storage_bucket()

    print("=" * 60)
    if success:
        print("Storage setup complete!")
        return 0
    else:
        print("Storage setup FAILED. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
