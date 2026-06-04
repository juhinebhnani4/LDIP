import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv()

from celery import chain  # noqa: E402

from app.workers.celery import celery_app  # noqa: E402
from app.workers.tasks.document_tasks import (  # noqa: E402
    calculate_confidence,
    chunk_document,
    embed_chunks,
    extract_entities,
    process_document,
    resolve_aliases,
    validate_ocr,
)

doc_id = "ed3313dc-0ff4-4079-8aee-656b48dad9e7"

print(f"Triggering full document processing pipeline for: {doc_id}")
print(f"Broker: {celery_app.conf.broker_url}")

# Create the same task chain as the upload endpoint
task_chain = chain(
    process_document.s(doc_id),
    validate_ocr.s(),
    calculate_confidence.s(),
    chunk_document.s(),
    embed_chunks.s(),
    extract_entities.s(),
    resolve_aliases.s(),
)

# Apply to high priority queue (document is small)
result = task_chain.apply_async(queue="high")
print(f"Chain Task ID: {result.id}")
print(f"Task Status: {result.status}")
