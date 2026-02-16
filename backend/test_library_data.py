#!/usr/bin/env python3
"""Add test data to library tables to verify UI.

This script adds a sample library document and links it to the Nirav Jobalia matter.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.supabase.client import get_service_client


def add_test_library_data():
    """Add test library document and link to matter."""
    client = get_service_client()

    # The Nirav Jobalia matter ID from the test
    matter_id = "91a4a4db-bc3d-40df-8dcc-49179ac49108"

    # Check if we already have library documents
    existing = client.table("library_documents").select("id, title").limit(5).execute()
    print(f"Existing library documents: {len(existing.data)}")
    for doc in existing.data:
        print(f"  - {doc['title']}")

    if existing.data:
        print("\nLibrary documents already exist. Checking links...")

        # Check links for this matter
        links = client.table("matter_library_links").select(
            "id, library_document_id, library_documents(title)"
        ).eq("matter_id", matter_id).execute()

        print(f"Links for matter {matter_id}: {len(links.data)}")
        for link in links.data:
            print(f"  - {link.get('library_documents', {}).get('title', 'Unknown')}")

        return

    print("\nNo library documents found. Adding test data...")

    # Get a user ID to use as added_by (get the first user from the matter)
    matter = client.table("matter_attorneys").select("user_id").eq("matter_id", matter_id).limit(1).execute()
    if not matter.data:
        print("Error: No user found for this matter")
        return

    user_id = matter.data[0]["user_id"]
    print(f"Using user_id: {user_id}")

    # Add test library documents
    test_docs = [
        {
            "filename": "Indian Contract Act, 1872.pdf",
            "storage_path": "documents/library/central_acts/indian_contract_act_1872.pdf",
            "file_size": 1024000,
            "page_count": 150,
            "document_type": "act",
            "title": "Indian Contract Act, 1872",
            "short_title": "Contract Act",
            "year": 1872,
            "jurisdiction": "central",
            "source": "india_code",
            "status": "completed",
            "added_by": user_id,
        },
        {
            "filename": "Companies Act, 2013.pdf",
            "storage_path": "documents/library/central_acts/companies_act_2013.pdf",
            "file_size": 2048000,
            "page_count": 450,
            "document_type": "act",
            "title": "Companies Act, 2013",
            "short_title": "Companies Act",
            "year": 2013,
            "jurisdiction": "central",
            "source": "india_code",
            "status": "completed",
            "added_by": user_id,
        },
        {
            "filename": "Income Tax Act, 1961.pdf",
            "storage_path": "documents/library/central_acts/income_tax_act_1961.pdf",
            "file_size": 3072000,
            "page_count": 800,
            "document_type": "act",
            "title": "Income Tax Act, 1961",
            "short_title": "Income Tax Act",
            "year": 1961,
            "jurisdiction": "central",
            "source": "india_code",
            "status": "completed",
            "added_by": user_id,
        },
    ]

    created_docs = []
    for doc in test_docs:
        result = client.table("library_documents").insert(doc).execute()
        if result.data:
            created_docs.append(result.data[0])
            print(f"Created: {doc['title']} -> {result.data[0]['id']}")

    # Link all to the matter
    for doc in created_docs:
        link = {
            "matter_id": matter_id,
            "library_document_id": doc["id"],
            "linked_by": user_id,
        }
        result = client.table("matter_library_links").insert(link).execute()
        if result.data:
            print(f"Linked: {doc['title']} to matter {matter_id}")

    print("\nTest data added successfully!")


if __name__ == "__main__":
    add_test_library_data()
