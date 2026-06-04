#!/usr/bin/env python3
"""Backfill missing embeddings for chunks that have embedding=NULL.

Directly calls OpenAI API and writes to Supabase, bypassing Celery.
Safe to run multiple times — only processes chunks with NULL embeddings.
"""
import sys

sys.path.insert(0, '.')

import os
import time

from dotenv import load_dotenv

load_dotenv()
from openai import OpenAI  # noqa: E402

from app.services.supabase.client import get_supabase_client  # noqa: E402

# Config — matches backend/app/services/rag/embedder.py
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 50  # OpenAI supports up to 2048, but keep batches small for reliability

def main():
    client = get_supabase_client()
    openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Find all chunks with NULL embeddings
    print("Querying chunks with missing embeddings...")
    chunks = client.table("chunks").select("id, content, document_id").is_("embedding", "null").execute()

    if not chunks.data:
        print("No chunks with missing embeddings found!")
        return

    # Group by document for reporting
    doc_counts = {}
    for c in chunks.data:
        did = c["document_id"]
        doc_counts[did] = doc_counts.get(did, 0) + 1

    print(f"\nFound {len(chunks.data)} chunks missing embeddings across {len(doc_counts)} documents:")
    for did, count in doc_counts.items():
        doc = client.table("documents").select("filename").eq("id", did).single().execute()
        print(f"  {doc.data['filename']}: {count} chunks")

    print(f"\nProcessing in batches of {BATCH_SIZE}...")

    total = len(chunks.data)
    processed = 0
    errors = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks.data[i:i + BATCH_SIZE]
        texts = [c["content"] or "" for c in batch]

        try:
            # Generate embeddings via OpenAI
            response = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
                dimensions=EMBEDDING_DIMENSIONS,
            )

            # Write each embedding to Supabase
            for j, embedding_data in enumerate(response.data):
                chunk_id = batch[j]["id"]
                embedding = embedding_data.embedding

                client.table("chunks").update({
                    "embedding": embedding,
                }).eq("id", chunk_id).execute()

            processed += len(batch)
            print(f"  Batch {i // BATCH_SIZE + 1}: {processed}/{total} chunks embedded")

            # Rate limit: small delay between batches
            time.sleep(0.5)

        except Exception as e:
            errors += len(batch)
            print(f"  ERROR in batch {i // BATCH_SIZE + 1}: {e}")
            time.sleep(2)  # Back off on error

    print(f"\nDone! Processed: {processed}, Errors: {errors}")

    # Verify
    remaining = client.table("chunks").select("id", count="exact").is_("embedding", "null").execute()
    print(f"Remaining chunks without embeddings: {remaining.count}")


if __name__ == "__main__":
    main()
