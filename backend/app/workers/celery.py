"""Celery application configuration."""

import ssl
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

# Load .env file to set GOOGLE_APPLICATION_CREDENTIALS before importing settings
# This is needed because Google Cloud SDK reads directly from os.environ
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from app.core.config import get_settings

settings = get_settings()

# Create Celery application
celery_app = Celery(
    "ldip_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# SSL configuration for Upstash Redis (rediss:// protocol)
# Only apply SSL settings if using TLS connection
_uses_tls = settings.celery_broker_url.startswith("rediss://")
_ssl_config = {"ssl_cert_reqs": ssl.CERT_REQUIRED} if _uses_tls else {}

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result backend settings
    result_expires=3600,  # 1 hour
    # Worker settings
    # Using gevent pool for I/O-bound tasks (LLM API calls)
    # Higher concurrency is safe since tasks are mostly waiting on network I/O
    worker_prefetch_multiplier=1,
    worker_concurrency=50,  # Increased from 4 - gevent handles 50+ concurrent I/O tasks efficiently
    # Heartbeat and health settings
    broker_heartbeat=30,  # Send heartbeat every 30 seconds
    broker_heartbeat_checkrate=2,  # Check for heartbeat every 2 iterations
    worker_send_task_events=True,  # Enable task events for monitoring
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevents memory leaks)
    task_time_limit=3600,  # Hard timeout: 1 hour per task
    task_soft_time_limit=3300,  # Soft timeout: 55 minutes (gives 5 min cleanup)
    # Priority queues configuration
    task_queues={
        # Align with architecture convention: high / default / low
        "default": {"exchange": "default", "binding_key": "default"},
        "high": {"exchange": "high", "binding_key": "high"},
        "low": {"exchange": "low", "binding_key": "low"},
    },
    task_default_queue="default",
    # Task routing based on priority
    task_routes={
        # Document ingestion tasks can be long-running; keep in default until
        # we implement true priority routing by story.
        "app.workers.tasks.document_tasks.*": {"queue": "default"},
        "app.workers.tasks.chunked_document_tasks.*": {"queue": "default"},
        "app.workers.tasks.engine_tasks.*": {"queue": "default"},
    },
    # SSL configuration for Upstash Redis (rediss:// protocol)
    # These settings are required for TLS connections to serverless Redis
    broker_use_ssl=_ssl_config if _uses_tls else None,
    redis_backend_use_ssl=_ssl_config if _uses_tls else None,
    # Celery Beat schedule for periodic tasks
    beat_schedule={
        "recover-stale-jobs": {
            "task": "app.workers.tasks.maintenance_tasks.recover_stale_jobs",
            "schedule": settings.job_recovery_scan_interval * 60,  # Convert minutes to seconds
            "options": {"queue": "low"},  # Low priority queue
        },
        "cleanup-stale-chunks": {
            "task": "app.workers.tasks.maintenance_tasks.cleanup_stale_chunks",
            "schedule": 3600,  # Run every hour
            "args": [24],  # 24 hour retention period
            "options": {"queue": "low"},  # Low priority queue
        },
        # Story 19.1: Stale chunk recovery - runs every 60 seconds
        "recover-stale-chunks": {
            "task": "app.workers.tasks.maintenance_tasks.recover_stale_chunks",
            "schedule": 60,  # Every minute
            "options": {"queue": "low"},
        },
        # Story 19.2: Auto-merge trigger - runs every 2 minutes
        "trigger-pending-merges": {
            "task": "app.workers.tasks.maintenance_tasks.trigger_pending_merges",
            "schedule": 120,  # Every 2 minutes
            "options": {"queue": "low"},
        },
        # Story 19.3: SKIPPED large document recovery - runs every hour
        "recover-skipped-large-documents": {
            "task": "app.workers.tasks.maintenance_tasks.recover_skipped_large_documents",
            "schedule": 3600,  # Every hour
            "options": {"queue": "low"},
        },
        # Auto-fix missing extracted_text - runs every 5 minutes
        "fix-missing-extracted-text": {
            "task": "app.workers.tasks.maintenance_tasks.fix_missing_extracted_text",
            "schedule": 300,  # Every 5 minutes
            "options": {"queue": "low"},
        },
        # Act validation - process pending validations every 30 minutes
        "process-pending-act-validations": {
            "task": "app.workers.tasks.act_validation_tasks.process_pending_validations",
            "schedule": 1800,  # Every 30 minutes
            "options": {"queue": "low"},
        },
        # Dispatch stuck QUEUED jobs - runs every 5 minutes
        # This handles jobs that were set to QUEUED but no Celery task was dispatched
        "dispatch-stuck-queued-jobs": {
            "task": "app.workers.tasks.maintenance_tasks.dispatch_stuck_queued_jobs",
            "schedule": 300,  # Every 5 minutes
            "args": [10],  # Jobs QUEUED for more than 10 minutes
            "options": {"queue": "low"},
        },
        # Sync stale job status - runs every 15 minutes
        # This handles cases where tasks complete but job status wasn't updated
        "sync-stale-job-status": {
            "task": "app.workers.tasks.maintenance_tasks.sync_stale_job_status",
            "schedule": 900,  # Every 15 minutes
            "args": [30],  # Jobs stale for more than 30 minutes
            "options": {"queue": "low"},
        },
        # Sync missing entity_ids - runs every 10 minutes
        # Ensures chunks.entity_ids is populated from entity_mentions
        "sync-missing-entity-ids": {
            "task": "app.workers.tasks.maintenance_tasks.sync_missing_entity_ids",
            "schedule": 600,  # Every 10 minutes
            "options": {"queue": "low"},
        },
        # Resume stuck pipelines - runs every 30 minutes
        # Recovers documents stuck at ocr_complete or other intermediate states
        "resume-stuck-pipelines": {
            "task": "app.workers.tasks.maintenance_tasks.resume_stuck_pipelines",
            "schedule": 1800,  # Every 30 minutes
            "args": [1],  # Documents stuck for more than 1 hour
            "options": {"queue": "low"},
        },
        # Sync act_resolutions with documents - runs every 15 minutes
        # Ensures act_resolutions table stays in sync with documents table
        # Fixes cases where acts are uploaded but resolutions not updated
        "sync-act-resolutions-with-documents": {
            "task": "app.workers.tasks.maintenance_tasks.sync_act_resolutions_with_documents",
            "schedule": 900,  # Every 15 minutes
            "options": {"queue": "low"},
        },
        # Sync citation statuses with act_resolutions - runs every 15 minutes
        # Ensures citations show correct status when Act becomes available
        # Fixes cases where Act upload didn't trigger citation status update
        "sync-citation-statuses-with-resolutions": {
            "task": "app.workers.tasks.maintenance_tasks.sync_citation_statuses_with_resolutions",
            "schedule": 900,  # Every 15 minutes
            "options": {"queue": "low"},
        },
    },
)

# Auto-discover tasks from the tasks submodule
celery_app.autodiscover_tasks(["app.workers.tasks"])

# =============================================================================
# Pre-flight Import Validation
# =============================================================================
# Explicit imports to ensure tasks are registered and catch import errors early.
# This prevents silent failures where workers start but can't process tasks.
# (autodiscover can be unreliable on Windows)

import structlog

_logger = structlog.get_logger(__name__)

_TASK_MODULES = [
    "app.workers.tasks.act_validation_tasks",
    "app.workers.tasks.chunked_document_tasks",
    "app.workers.tasks.document_tasks",
    "app.workers.tasks.engine_tasks",
    "app.workers.tasks.maintenance_tasks",
    "app.workers.tasks.verification_tasks",
]

_import_errors: list[str] = []

try:
    from app.workers.tasks import (  # noqa: E402, F401
        act_validation_tasks,
        chunked_document_tasks,
        document_tasks,
        engine_tasks,
        maintenance_tasks,
        verification_tasks,
    )
    _logger.info(
        "celery_task_modules_imported",
        module_count=len(_TASK_MODULES),
        registered_tasks=len(celery_app.tasks),
    )
except ImportError as e:
    _import_errors.append(str(e))
    _logger.critical(
        "celery_task_import_failed",
        error=str(e),
        hint="Check for missing dependencies or syntax errors in task modules",
    )
    # Re-raise to prevent worker from starting with broken imports
    raise

# Validate expected critical tasks are registered
_CRITICAL_TASKS = [
    "app.workers.tasks.document_tasks.process_document",
    "app.workers.tasks.document_tasks.embed_chunks",
    "app.workers.tasks.document_tasks.extract_entities",
    "app.workers.tasks.document_tasks.resolve_aliases",
    "app.workers.tasks.maintenance_tasks.recover_stale_jobs",
    "app.workers.tasks.maintenance_tasks.dispatch_stuck_queued_jobs",
]

_missing_tasks = [t for t in _CRITICAL_TASKS if t not in celery_app.tasks]
if _missing_tasks:
    _logger.warning(
        "celery_missing_critical_tasks",
        missing_tasks=_missing_tasks,
        hint="Some critical tasks are not registered. Check task decorators.",
    )
