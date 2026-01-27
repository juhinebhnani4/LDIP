"""Celery application configuration."""

import ssl
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
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
    task_acks_on_failure_or_timeout=True,  # Explicit: ack failed/timed-out tasks to prevent infinite redelivery
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
    worker_max_memory_per_child=400000,  # 400MB in KB - restart if memory exceeds this (Python high watermark protection)
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
        "app.workers.tasks.library_tasks.*": {"queue": "default"},
    },
    # === BROKER TRANSPORT OPTIONS ===
    # CRITICAL: visibility_timeout must exceed task_time_limit to prevent duplicate execution
    # Redis redelivers unacknowledged tasks after visibility_timeout expires
    # Default is 1 hour; we set 2 hours to handle long-running tasks safely
    broker_transport_options={
        'visibility_timeout': 7200,  # 2 hours - must exceed task_time_limit (3600)
        **(_ssl_config if _uses_tls else {}),  # Merge SSL config if TLS enabled
    },
    # Result backend resilience for Redis connection drops
    result_backend_transport_options={
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
        'retry_on_timeout': True,
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
        # Story 4.2: Archive reasoning traces - runs daily at 2 AM
        # Moves traces older than 30 days to Supabase Storage (cold storage)
        "archive-reasoning-traces": {
            "task": "app.workers.tasks.reasoning_archive_tasks.archive_reasoning_traces",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
            "options": {"queue": "low"},
        },
        # Story gap-5.2: LLM Quota Monitoring - runs every 5 minutes
        # Checks quota thresholds and triggers alerts when usage exceeds limits
        "check-llm-quotas": {
            "task": "app.workers.tasks.quota_monitoring_tasks.check_llm_quotas",
            "schedule": 300,  # Every 5 minutes
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
    "app.workers.tasks.email_tasks",
    "app.workers.tasks.engine_tasks",
    "app.workers.tasks.library_tasks",
    "app.workers.tasks.maintenance_tasks",
    "app.workers.tasks.quota_monitoring_tasks",
    "app.workers.tasks.reasoning_archive_tasks",
    "app.workers.tasks.verification_tasks",
]

_import_errors: list[str] = []

try:
    from app.workers.tasks import (  # noqa: E402, F401
        act_validation_tasks,
        chunked_document_tasks,
        document_tasks,
        email_tasks,
        engine_tasks,
        library_tasks,
        maintenance_tasks,
        quota_monitoring_tasks,
        reasoning_archive_tasks,
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


# =============================================================================
# Dead Letter Queue (DLQ) Signal Handler
# =============================================================================
# Logs permanently failed tasks (after all retries exhausted) for debugging
# and monitoring. These are tasks that cannot be recovered automatically.

from celery.signals import task_failure, task_retry


@task_failure.connect
def handle_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **kw,
):
    """Log permanently failed tasks to DLQ for investigation.

    This signal fires when a task raises an exception and will NOT be retried.
    Tasks that exhaust all retries end up here.

    Use this data to:
    1. Debug recurring failures
    2. Monitor failure patterns
    3. Manually retry or fix data issues
    """
    # Get retry info from task request if available
    retries = 0
    max_retries = 0
    if sender and hasattr(sender, "request"):
        retries = getattr(sender.request, "retries", 0)
    if sender and hasattr(sender, "max_retries"):
        max_retries = sender.max_retries or 0

    # Determine if this is a permanent failure (exhausted retries)
    is_permanent = retries >= max_retries if max_retries > 0 else True

    # Sanitize kwargs to avoid logging sensitive data
    safe_kwargs = {}
    if kwargs:
        for key, value in kwargs.items():
            if "password" in key.lower() or "secret" in key.lower() or "token" in key.lower():
                safe_kwargs[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 200:
                safe_kwargs[key] = f"{value[:200]}...[truncated]"
            else:
                safe_kwargs[key] = value

    log_level = "critical" if is_permanent else "error"
    log_func = _logger.critical if is_permanent else _logger.error

    log_func(
        "celery_task_failed_dlq" if is_permanent else "celery_task_failed",
        task_name=sender.name if sender else "unknown",
        task_id=task_id,
        retries=retries,
        max_retries=max_retries,
        is_permanent_failure=is_permanent,
        exception_type=type(exception).__name__ if exception else None,
        exception_message=str(exception)[:500] if exception else None,
        args=args[:5] if args and len(args) > 5 else args,  # Limit logged args
        kwargs=safe_kwargs,
    )


@task_retry.connect
def handle_task_retry(
    sender=None,
    request=None,
    reason=None,
    einfo=None,
    **kw,
):
    """Log task retries for monitoring retry patterns.

    Helps identify:
    1. Tasks that frequently need retries (may need optimization)
    2. Transient failures (network, rate limits, etc.)
    3. Retry storms that could overwhelm the system
    """
    retries = request.retries if request else 0
    max_retries = sender.max_retries if sender and hasattr(sender, "max_retries") else 0

    _logger.warning(
        "celery_task_retrying",
        task_name=sender.name if sender else "unknown",
        task_id=request.id if request else None,
        retry_number=retries + 1,  # Current retry attempt (1-based)
        max_retries=max_retries,
        reason=str(reason)[:200] if reason else None,
    )
