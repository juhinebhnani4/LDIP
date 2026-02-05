#!/usr/bin/env python3
"""Recovery script for documents stuck at OCR_COMPLETE with 0 chunks.

This script triggers the finalize_chunked_document task for a stuck document.
The task's recovery mechanism will detect the 0 chunks and trigger downstream
processing (validate_ocr → chunk_document → embed_chunks → etc.).

Usage:
    python recover_stuck_document.py <document_id> <matter_id> [job_id]

Example:
    python recover_stuck_document.py f1a7f5bb-d106-4fef-812d-6f3a92a08b9e a7cbad0c-ee48-4f3e-8934-82ec1d01305d 4b04794f-797d-4dc4-a6a3-d0288138c8af
"""

import sys
import os

# Add the backend app to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.celery import celery_app


def recover_document(document_id: str, matter_id: str, job_id: str | None = None):
    """Trigger recovery for a stuck document.

    The finalize_chunked_document task has built-in recovery logic:
    - If document is OCR_COMPLETE but has 0 chunks, it triggers downstream processing
    """
    from app.workers.tasks.chunked_document_tasks import finalize_chunked_document

    print(f"Triggering recovery for document: {document_id}")
    print(f"Matter ID: {matter_id}")
    print(f"Job ID: {job_id or 'None'}")

    # Dispatch the recovery task
    result = finalize_chunked_document.apply_async(
        kwargs={
            "document_id": document_id,
            "matter_id": matter_id,
            "job_id": job_id,
        },
        queue="default",
    )

    print(f"Recovery task dispatched: {result.id}")
    print("The task will check if document has 0 chunks and trigger downstream if needed.")
    print("Monitor Celery logs for progress.")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    document_id = sys.argv[1]
    matter_id = sys.argv[2]
    job_id = sys.argv[3] if len(sys.argv) > 3 else None

    recover_document(document_id, matter_id, job_id)
